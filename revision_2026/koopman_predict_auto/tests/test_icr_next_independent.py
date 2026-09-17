from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from recompute_icr_next import (
    compare_records,
    independent_aggregate,
    independent_icr,
    independent_physics,
    validate_units,
)
from plot_icr_next import REQUIRED_N2_FIGURE_STEMS


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict:
    return json.loads((ROOT / "config" / "protocol_icr_next.json").read_text(encoding="utf-8"))


def _params() -> dict:
    return {
        "schema": "synthetic",
        "units": {
            "vehicle.lf_m": "m",
            "vehicle.lr_m": "m",
            "payload.length_m": "m",
            "payload.width_m": "m",
            "payload.mass_kg": "kg",
            "payload.gravity_mps2": "m/s^2",
            "connector.ultimate_force_n": "N",
        },
        "values": {
            "vehicle": {"lf_m": 1.2, "lr_m": 1.3},
            "payload": {"length_m": 5.0, "width_m": 2.0, "mass_kg": 2000.0, "gravity_mps2": 9.81},
            "connector": {"ultimate_force_n": 15000.0},
            "vehicle_anchor_body_m": [[-0.4, -0.25], [-0.4, 0.25], [0.4, -0.25], [0.4, 0.25]],
        },
    }


def test_independent_icr_hand_calculation_straight_and_mirror() -> None:
    speed = np.full(4, 2.0)
    yaw = 0.1
    angle = np.full(4, np.arctan(2.5 * yaw / 2.0))
    result = independent_icr(speed, yaw, 2.5, angle)
    assert np.max(np.abs(result["signed4_mps"])) <= 1.0e-15
    straight = independent_icr(speed, 0.0, 2.5, np.zeros(4))
    assert straight["peak_mps"] == 0.0
    mirror = independent_icr(speed, -yaw, 2.5, -angle)
    assert np.allclose(result["series_mps"], mirror["series_mps"], rtol=0.0, atol=1.0e-15)


def test_independent_unit_contract_rejects_wrong_unit() -> None:
    params = _params()
    assert validate_units(params)["passed"]
    params["units"]["connector.ultimate_force_n"] = "kN"
    result = validate_units(params)
    assert result["passed"] is False
    assert "connector.ultimate_force_n" in result["issues"][0]


def _synthetic_arrays() -> dict[str, np.ndarray]:
    count, substeps = 2, 10
    support_each = 2000.0 * 9.81 / 4.0
    return {
        "time_s": np.asarray([0.02, 0.04]),
        "distance_m": np.asarray([0.04, 0.08]),
        "state30": np.zeros((count, 30)),
        "requested_control4x2": np.zeros((count, 4, 2)),
        "actual_steering_rad": np.zeros((count, 4)),
        "actual_steering_substeps_rad": np.zeros((count, substeps, 4)),
        "actual_steering_rate_substeps_radps": np.zeros((count, substeps, 4)),
        "icr_target_speed4_mps": np.full((count, 4), 2.0),
        "icr_target_yaw_rate_radps": np.zeros(count),
        "tire_raw_utilization": np.full((count, 4), 0.2),
        "payload_support_load4_n": np.full((count, 4), support_each),
        "support_constraint_relative_residual3": np.zeros((count, 3)),
        "force_payload_body_n": np.zeros((count, 4, 2)),
        "internal_force_vector_n": np.zeros((count, 8)),
        "command_phase": np.asarray(["CRUISE", "CRUISE"]),
    }


def test_independent_physics_matches_synthetic_hand_values() -> None:
    identity = {
        "trajectory_id": 0,
        "direction": "left",
        "plant": "V1-ES",
        "actuator_mode": "A3",
    }
    row, switches = independent_physics(
        identity,
        _synthetic_arrays(),
        {"params_json": json.dumps(_params())},
        _protocol(),
        None,
    )
    assert row["shape_contract_passed"] is True
    assert row["unit_contract_passed"] is True
    assert row["actual_icr_peak_mps"] == 0.0
    assert row["support_sum_residual_max_n"] == 0.0
    assert row["connector_force_peak_n"] == 0.0
    assert row["internal_vector_recompute_max_abs_n"] == 0.0
    assert switches == []


def test_primary_independent_tire_and_angle_tamper_is_detected() -> None:
    independent = [{"direction": "left", "plant": "V1-ES", "actuator_mode": "A3", "tire": 0.3, "angle": 0.2}]
    primary = [dict(independent[0])]
    metrics = {"tire": 1.0e-12, "angle": 1.0e-12}
    assert compare_records(primary, independent, ("direction", "plant", "actuator_mode"), metrics, "synthetic")["passed"]
    primary[0]["tire"] += 1.0e-4
    assert not compare_records(primary, independent, ("direction", "plant", "actuator_mode"), metrics, "synthetic")["passed"]
    primary[0] = dict(independent[0])
    primary[0]["angle"] += 1.0e-4
    assert not compare_records(primary, independent, ("direction", "plant", "actuator_mode"), metrics, "synthetic")["passed"]


def _aggregate_rows() -> list[dict]:
    rows = []
    trajectory = 0
    for direction in ("left", "right"):
        for plant in ("V1-ES", "R3-ES"):
            for mode in ("A0", "A1", "A2", "A3"):
                rows.append(
                    {
                        "trajectory_id": trajectory,
                        "direction": direction,
                        "plant": plant,
                        "actuator_mode": mode,
                        "shape_contract_passed": True,
                        "unit_contract_passed": True,
                        "finite": True,
                    }
                )
                trajectory += 1
    return rows


def test_independent_aggregate_detects_hash_missing_duplicate_and_unexpected() -> None:
    rows = _aggregate_rows()
    checks = [{"trajectory_id": row["trajectory_id"], "passed": True} for row in rows]
    assert independent_aggregate(rows, checks, _protocol())["passed"]
    bad_hash = [dict(item) for item in checks]
    bad_hash[3]["passed"] = False
    assert not independent_aggregate(rows, bad_hash, _protocol())["passed"]
    assert not independent_aggregate(rows[:-1], checks[:-1], _protocol())["passed"]
    duplicate = rows + [dict(rows[0])]
    assert not independent_aggregate(duplicate, checks + [{"trajectory_id": 16, "passed": True}], _protocol())["passed"]
    unexpected = [dict(item) for item in rows]
    unexpected[-1]["actuator_mode"] = "A4"
    assert not independent_aggregate(unexpected, checks, _protocol())["passed"]


def test_independent_script_does_not_import_primary_metric_paths() -> None:
    source = (ROOT / "scripts" / "recompute_icr_next.py").read_text(encoding="utf-8")
    assert "from audit_icr_next" not in source
    assert "import audit_icr_next" not in source
    assert "_offline_request_attribution" not in source
    assert "import run_icr_fix" not in source


def test_figure_manifest_contract_covers_registered_evidence() -> None:
    assert set(REQUIRED_N2_FIGURE_STEMS) == {
        "steering_request_actual_a0_a3",
        "yaw_vehicle_payload_system",
        "force_components_a0_a3",
        "support_load_a0_a3",
        "array_stretch_internal_force",
    }

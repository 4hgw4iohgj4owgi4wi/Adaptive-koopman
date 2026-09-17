from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import audit_icr_next
from causal_schema import build_schema_icr, validate_schema_icr_next_contract
from run_icr_next import _json_safe, validate_protocol


PHYSICAL_GATES = (
    "actuator_rate",
    "actuator_angle",
    "tire",
    "support_nonnegative",
    "connector_ultimate",
)
INTEGRITY_GATES = (
    "finite",
    "time_grid",
    "completion",
    "support_constraints",
    "geometry_icr",
    "g0_icr",
    "action_reaction",
    "internal_null",
    "replay",
    "scenario",
)


def _protocol() -> dict:
    path = Path(__file__).resolve().parents[1] / "config" / "protocol_icr_next.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _legacy(state: dict) -> dict:
    mode = state["mode"]
    gates = {
        **{name: bool(state[name]) for name in INTEGRITY_GATES},
        "actuator_rate": state["rate_peak"] <= 1.2,
        "actuator_angle": bool(state["actuator_angle"]),
        "tire": bool(state["tire"]),
        "support_nonnegative": bool(state["support_nonnegative"]),
        "connector_ultimate": bool(state["connector_ultimate"]),
        "a3_parent_common_fields": bool(state["a3_parent_common_fields"]),
    }
    return {
        "passed": all(gates.values()),
        "actual_rate_peak_radps": float(state["rate_peak"]),
        "actual_angle_peak_rad": float(state["angle_peak"]),
        "support_sum_residual_max_n": 0.0,
        "g0_peak_mps": 0.0,
        "a3_parent_common_max_abs": 0.0 if mode == "A3" else None,
        **{f"gate_{name}": value for name, value in gates.items()},
    }


def _identity(mode: str, *, trajectory_id: int = 0, direction: str = "left", plant: str = "V1-ES") -> dict:
    return {
        "trajectory_id": trajectory_id,
        "seed": 910021,
        "direction": direction,
        "plant": plant,
        "actuator_mode": mode,
        "replay_hash_match": True,
    }


@pytest.fixture
def semantic_stub(monkeypatch: pytest.MonkeyPatch):
    state = {
        "mode": "A0",
        **{name: True for name in INTEGRITY_GATES},
        "rate_peak": 1.2,
        "angle_peak": np.deg2rad(15.0),
        "actuator_angle": True,
        "tire": True,
        "support_nonnegative": True,
        "connector_ultimate": True,
        "a3_parent_common_fields": True,
    }

    def fake_legacy(identity, arrays, summary, protocol, parent_comparison):
        return _legacy(state)

    def fake_events(identity, arrays, summary, protocol):
        failures = []
        if state["rate_peak"] > 1.2:
            failures.append("actuator_rate")
        if not state["actuator_angle"]:
            failures.append("actuator_angle")
        for name in ("tire", "support_nonnegative", "connector_ultimate"):
            if not state[name]:
                failures.append(name)
        return [
            {
                "gate": gate,
                "valid_interval_end_sample_exclusive": 1,
            }
            for gate in failures
        ]

    monkeypatch.setattr(audit_icr_next, "audit_trajectory_legacy_metrics", fake_legacy)
    monkeypatch.setattr(audit_icr_next, "counterfactual_domain_events", fake_events)
    return state


def _audit(state: dict, mode: str) -> dict:
    state["mode"] = mode
    return audit_icr_next.audit_trajectory(
        _identity(mode), {"time_s": np.asarray([0.02, 0.04])}, {}, _protocol(), None
    )


@pytest.mark.parametrize("mode", ["A0", "A1"])
@pytest.mark.parametrize("gate", PHYSICAL_GATES)
def test_counterfactual_physical_ood_is_reported_and_nonblocking(
    semantic_stub: dict, mode: str, gate: str
) -> None:
    if gate == "actuator_rate":
        semantic_stub["rate_peak"] = 1.2001
    else:
        semantic_stub[gate] = False
    row = _audit(semantic_stub, mode)
    assert row["diagnostic_integrity"] == "PASS"
    assert row["deployment_feasibility"] == "NOT_APPLICABLE"
    assert row["counterfactual_ood"] is True
    assert row["semantic_status"] == "PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD"
    assert row["stage_blocking"] is False


@pytest.mark.parametrize(
    "gate", ["actuator_rate", "tire", "support_nonnegative", "connector_ultimate"]
)
def test_a2_registered_deployment_gate_blocks(semantic_stub: dict, gate: str) -> None:
    if gate == "actuator_rate":
        semantic_stub["rate_peak"] = 1.2001
    else:
        semantic_stub[gate] = False
    row = _audit(semantic_stub, "A2")
    assert row["deployment_feasibility"] == "FAIL"
    assert row["semantic_status"] == "BLOCKED_PHYSICAL_BASELINE"
    assert row["stage_blocking"] is True


def test_a2_angle_is_report_only(semantic_stub: dict) -> None:
    semantic_stub["actuator_angle"] = False
    row = _audit(semantic_stub, "A2")
    assert row["deployment_report_actuator_angle"] is False
    assert row["deployment_feasibility"] == "PASS"
    assert row["stage_blocking"] is False


@pytest.mark.parametrize(
    "gate",
    [
        "actuator_rate",
        "actuator_angle",
        "tire",
        "support_nonnegative",
        "connector_ultimate",
        "a3_parent_common_fields",
    ],
)
def test_a3_every_deployment_gate_blocks(semantic_stub: dict, gate: str) -> None:
    if gate == "actuator_rate":
        semantic_stub["rate_peak"] = 1.2001
    else:
        semantic_stub[gate] = False
    row = _audit(semantic_stub, "A3")
    assert row["deployment_feasibility"] == "FAIL" or row["diagnostic_integrity"] == "FAIL"
    assert row["stage_blocking"] is True


@pytest.mark.parametrize("field", INTEGRITY_GATES)
def test_every_integrity_fault_blocks_every_mode(semantic_stub: dict, field: str) -> None:
    semantic_stub[field] = False
    for mode in ("A0", "A1", "A2", "A3"):
        row = _audit(semantic_stub, mode)
        assert row["diagnostic_integrity"] == "FAIL"
        assert row["semantic_status"] == "BLOCKED_DIAGNOSTIC_INTEGRITY"
        assert row["stage_blocking"] is True


def _aggregate_rows() -> list[dict]:
    rows = []
    trajectory_id = 0
    for direction in ("left", "right"):
        for plant in ("V1-ES", "R3-ES"):
            for mode in ("A0", "A1", "A2", "A3"):
                rows.append(
                    {
                        **_identity(mode, trajectory_id=trajectory_id, direction=direction, plant=plant),
                        "diagnostic_integrity": "PASS",
                        "deployment_feasibility": "NOT_APPLICABLE" if mode in {"A0", "A1"} else "PASS",
                        "counterfactual_ood": False,
                        "a3_parent_common_max_abs": 0.0 if mode == "A3" else None,
                        "g0_peak_mps": 0.0,
                    }
                )
                trajectory_id += 1
    return rows


def test_aggregate_accepts_exact_16_identities() -> None:
    result = audit_icr_next.aggregate_stage(_aggregate_rows(), [], _protocol())
    assert result["stage_passed"] is True
    assert result["stage_status"] == "PASS"


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unexpected"])
def test_aggregate_rejects_identity_faults(fault: str) -> None:
    rows = _aggregate_rows()
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(dict(rows[0]))
    else:
        rows[-1] = {**rows[-1], "actuator_mode": "A4"}
    result = audit_icr_next.aggregate_stage(rows, [], _protocol())
    assert result["stage_passed"] is False
    assert result["stage_status"] == "BLOCKED_DIAGNOSTIC_INTEGRITY"


def test_aggregate_prioritizes_integrity_then_physical_baseline() -> None:
    rows = _aggregate_rows()
    rows[0]["diagnostic_integrity"] = "FAIL"
    rows[-1]["deployment_feasibility"] = "FAIL"
    assert audit_icr_next.aggregate_stage(rows, [], _protocol())["stage_status"] == "BLOCKED_DIAGNOSTIC_INTEGRITY"
    rows[0]["diagnostic_integrity"] = "PASS"
    assert audit_icr_next.aggregate_stage(rows, [], _protocol())["stage_status"] == "BLOCKED_PHYSICAL_BASELINE"


def test_illegal_mode_rejected(semantic_stub: dict) -> None:
    with pytest.raises(ValueError):
        _audit(semantic_stub, "A4")


def test_protocol_has_unique_mode_pilot_and_tolerance_contract() -> None:
    protocol = _protocol()
    mathematical = protocol["n2"]["mathematical_mode_order"]
    execution = protocol["n2"]["execution_mode_order"]
    assert len(mathematical) == len(set(mathematical)) == 4
    assert set(mathematical) == set(execution) == {"A0", "A1", "A2", "A3"}
    assert protocol["n2"]["pilot_order"][0]["actuator_mode"] == "A3"
    assert protocol["protocol_id"].endswith("v2")
    assert validate_protocol(protocol)["passed"]


def test_duplicate_seed_block_is_rejected() -> None:
    protocol = _protocol()
    protocol["seed_blocks"]["DUPLICATE"] = [910021, 910021]
    with pytest.raises(ValueError):
        validate_protocol(protocol)


def test_schema_future_input_role_is_rejected() -> None:
    schema = build_schema_icr()
    assert validate_schema_icr_next_contract(schema)["future_input_count"] == 0
    schema["inputs"][0] = {**schema["inputs"][0], "time": "t_k+1"}
    with pytest.raises(ValueError):
        validate_schema_icr_next_contract(schema)


def test_json_safe_preserves_native_types_and_rejects_nan() -> None:
    value = _json_safe(
        {
            "bool": np.bool_(True),
            "int": np.int64(2),
            "float": np.float64(3.5),
            "array": np.asarray([1.0, 2.0]),
        }
    )
    decoded = json.loads(json.dumps(value, allow_nan=False))
    assert decoded == {"bool": True, "int": 2, "float": 3.5, "array": [1.0, 2.0]}
    with pytest.raises(ValueError):
        json.dumps(_json_safe({"bad": np.float64(np.nan)}), allow_nan=False)

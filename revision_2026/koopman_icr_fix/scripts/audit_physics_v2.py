from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from contracts import write_json
from run_k2 import MIRROR_INDEX, mirror_audit


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def audit_array_contracts(
    arrays: dict[str, np.ndarray], summary: dict, protocol: dict, actuator_mode: str
) -> dict:
    config = protocol["p2"]
    actuator = protocol["actuator"]
    time_s = np.asarray(arrays["time_s"], dtype=float)
    steps = np.diff(time_s)
    expected_step = float(protocol["k2"]["model_step_s"])
    step_error = np.abs(steps - expected_step)
    actual_substeps = np.asarray(arrays["actual_steering_substeps_rad"], dtype=float)
    rate_substeps = np.asarray(
        arrays["actual_steering_rate_substeps_radps"], dtype=float
    )
    maximum_angle = float(np.max(np.abs(actual_substeps)))
    maximum_rate = float(np.max(np.abs(rate_substeps)))
    maximum_tire = float(np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float)))
    requested_icr = float(
        np.max(np.asarray(arrays["requested_icr_residual_mps"], dtype=float))
    )
    actual_icr = float(
        np.max(np.asarray(arrays["actual_steering_icr_residual_mps"], dtype=float))
    )
    internal_relative = float(summary["internal_null_max_n"]) / max(
        float(summary["internal_force_peak_n"]), 1.0
    )
    finite = bool(
        all(
            np.all(np.isfinite(value))
            for key, value in arrays.items()
            if np.asarray(value).dtype.kind not in {"O", "U", "S"}
        )
    )
    time_grid_passed = bool(
        steps.size > 0
        and np.all(np.isfinite(steps))
        and np.all(steps > 0.0)
        and np.max(step_error) <= float(config["time_step_atol_s"])
    )
    completion_passed = bool(
        summary["status"] == "PASS"
        and float(summary["distance_m"]) >= float(config["distance_target_m"])
    )
    angle_passed = bool(
        maximum_angle
        <= np.deg2rad(float(actuator["angle_max_deg"]))
        + float(config["angle_atol_rad"])
    )
    rate_passed = bool(
        actuator_mode != "dynamic"
        or maximum_rate
        <= float(actuator["rate_max_radps"]) + float(config["rate_atol_radps"])
    )
    tire_passed = maximum_tire <= float(config["tire_raw_utilization_max"])
    requested_icr_passed = requested_icr <= float(
        config["requested_icr_residual_atol_mps"]
    )
    action_reaction_passed = float(summary["action_reaction_max_n"]) <= float(
        config["action_reaction_atol_n"]
    )
    internal_passed = internal_relative <= float(
        config["internal_null_relative_atol"]
    )
    connector_passed = not bool(summary["ultimate_force_exceeded"])
    phase = np.asarray(arrays["command_phase"]).astype(str)
    primary = phase == "STEP_PRIMARY"
    reverse = phase == "STEP_REVERSE"
    front = np.asarray(arrays["virtual_front_deg"], dtype=float)
    rear = np.asarray(arrays["virtual_rear_deg"], dtype=float)
    acceleration = np.asarray(arrays["base_acceleration_mps2"], dtype=float)
    accel_phase = phase == "ACCEL_TO_30M"
    scenario_passed = bool(
        np.any(accel_phase)
        and np.allclose(acceleration[accel_phase], 0.25, rtol=0.0, atol=1.0e-15)
        and abs(np.sum(primary) * expected_step - 5.0) <= expected_step + 1.0e-12
        and abs(np.sum(reverse) * expected_step - 5.0) <= expected_step + 1.0e-12
        and np.allclose(np.abs(front[primary]), 5.0, rtol=0.0, atol=1.0e-15)
        and np.allclose(np.abs(rear[primary]), 2.5, rtol=0.0, atol=1.0e-15)
        and np.allclose(np.abs(front[reverse]), 5.0, rtol=0.0, atol=1.0e-15)
        and np.allclose(np.abs(rear[reverse]), 2.5, rtol=0.0, atol=1.0e-15)
    )
    gates = {
        "finite": finite,
        "time_grid": time_grid_passed,
        "completion": completion_passed,
        "angle": angle_passed,
        "rate": rate_passed,
        "tire_raw_utilization": tire_passed,
        "requested_icr": requested_icr_passed,
        "action_reaction": action_reaction_passed,
        "internal_null": internal_passed,
        "connector_ultimate": connector_passed,
        "scenario_contract": scenario_passed,
    }
    return {
        "finite": finite,
        "sample_count": int(time_s.size),
        "step_min_s": float(np.min(steps)),
        "step_max_s": float(np.max(steps)),
        "max_abs_step_error_s": float(np.max(step_error)),
        "final_distance_m": float(summary["distance_m"]),
        "distance_overshoot_m": float(summary["distance_overshoot_m"]),
        "max_actual_angle_rad": maximum_angle,
        "max_actual_angle_deg": float(np.rad2deg(maximum_angle)),
        "max_actual_rate_radps": maximum_rate,
        "tire_raw_utilization_max": maximum_tire,
        "requested_icr_residual_max_mps": requested_icr,
        "actual_steering_icr_residual_max_mps": actual_icr,
        "action_reaction_max_n": float(summary["action_reaction_max_n"]),
        "internal_null_relative": internal_relative,
        "connector_force_peak_n": float(summary["force_peak_n"]),
        "rated_force_exceeded": bool(summary["rated_force_exceeded"]),
        "ultimate_force_exceeded": bool(summary["ultimate_force_exceeded"]),
        "gates": gates,
        "passed": all(gates.values()),
    }


def actuator_mirror_audit(
    trajectories: list[tuple[dict, dict[str, np.ndarray]]], atol: float
) -> dict:
    rows = []
    missing = 0
    grouped = {}
    for identity, arrays in trajectories:
        key = (
            identity["base_family_id"],
            identity["plant"],
            identity["actuator_mode"],
        )
        grouped.setdefault(key, {})[identity["direction"]] = arrays
    maxima = {"actual": 0.0, "rate": 0.0, "request": 0.0}
    for (base, plant, mode), pair in sorted(grouped.items()):
        if set(pair) != {"left", "right"}:
            missing += 1
            continue
        left = pair["left"]
        right = pair["right"]
        if len(left["time_s"]) != len(right["time_s"]):
            rows.append(
                {
                    "base_family_id": base,
                    "plant": plant,
                    "actuator_mode": mode,
                    "same_length": False,
                    "passed": False,
                }
            )
            continue
        errors = {
            "actual": float(
                np.max(
                    np.abs(
                        left["actual_steering_rad"][:, MIRROR_INDEX]
                        + right["actual_steering_rad"]
                    )
                )
            ),
            "rate": float(
                np.max(
                    np.abs(
                        left["actual_steering_rate_substeps_radps"][:, :, MIRROR_INDEX]
                        + right["actual_steering_rate_substeps_radps"]
                    )
                )
            ),
            "request": float(
                np.max(
                    np.abs(
                        left["requested_control4x2"][:, MIRROR_INDEX, 1]
                        + right["requested_control4x2"][:, :, 1]
                    )
                )
            ),
        }
        for key, value in errors.items():
            maxima[key] = max(maxima[key], value)
        rows.append(
            {
                "base_family_id": base,
                "plant": plant,
                "actuator_mode": mode,
                "same_length": True,
                "actual_angle_max_abs_rad": errors["actual"],
                "actual_rate_max_abs_radps": errors["rate"],
                "request_angle_max_abs_rad": errors["request"],
                "passed": all(value <= atol for value in errors.values()),
            }
        )
    failed = sum(not row["passed"] for row in rows)
    return {
        "passed": bool(rows and missing == 0 and failed == 0),
        "pair_count": len(rows),
        "missing_pair_count": missing,
        "failed_pair_count": failed,
        "maxima": maxima,
        "rows": rows,
    }


def audit_p2(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    protocol: dict,
    output: Path,
) -> dict:
    rows = []
    mirror_input = []
    by_pair = {}
    for identity, arrays, summary in trajectories:
        audit = audit_array_contracts(
            arrays, summary, protocol, identity["actuator_mode"]
        )
        row = {
            **identity,
            **{key: value for key, value in audit.items() if key != "gates"},
            **{f"gate_{key}": value for key, value in audit["gates"].items()},
            "replay_hash_match": bool(identity["replay_hash_match"]),
        }
        row["passed"] = bool(row["passed"] and row["replay_hash_match"])
        rows.append(row)
        mirror_input.append((identity, arrays))
        key = (identity["base_family_id"], identity["direction"], identity["plant"])
        by_pair.setdefault(key, {})[identity["actuator_mode"]] = row

    comparisons = []
    for (base, direction, plant), pair in sorted(by_pair.items()):
        if set(pair) != {"instant", "dynamic"}:
            comparisons.append(
                {
                    "base_family_id": base,
                    "direction": direction,
                    "plant": plant,
                    "pair_complete": False,
                }
            )
            continue
        a0 = pair["instant"]
        a1 = pair["dynamic"]
        old = float(a0["tire_raw_utilization_max"])
        new = float(a1["tire_raw_utilization_max"])
        comparisons.append(
            {
                "base_family_id": base,
                "direction": direction,
                "plant": plant,
                "pair_complete": True,
                "a0_tire_raw_utilization_max": old,
                "a1_tire_raw_utilization_max": new,
                "a1_minus_a0": new - old,
                "a1_reduction_percent": 100.0 * (old - new) / max(old, 1.0e-12),
                "a0_connector_force_peak_n": a0["connector_force_peak_n"],
                "a1_connector_force_peak_n": a1["connector_force_peak_n"],
                "a0_actual_icr_residual_max_mps": a0[
                    "actual_steering_icr_residual_max_mps"
                ],
                "a1_actual_icr_residual_max_mps": a1[
                    "actual_steering_icr_residual_max_mps"
                ],
            }
        )

    legacy_mirror = {}
    for mode in ("instant", "dynamic"):
        selected = [item for item in mirror_input if item[0]["actuator_mode"] == mode]
        legacy_mirror[mode] = mirror_audit(
            selected, float(protocol["p2"]["mirror_atol"])
        )
    actuator_mirror = actuator_mirror_audit(
        mirror_input, float(protocol["p2"]["mirror_atol"])
    )
    dynamic_rows = [row for row in rows if row["actuator_mode"] == "dynamic"]
    instant_rows = [row for row in rows if row["actuator_mode"] == "instant"]
    gates = {
        "trajectory_count": len(rows) == 24 and len(dynamic_rows) == len(instant_rows) == 12,
        "candidate_trajectory_contracts": bool(
            len(dynamic_rows) == 12 and all(row["passed"] for row in dynamic_rows)
        ),
        "candidate_tire_envelope": bool(
            len(dynamic_rows) == 12
            and all(row["gate_tire_raw_utilization"] for row in dynamic_rows)
        ),
        "candidate_mirror": bool(
            legacy_mirror["dynamic"]["passed"] and actuator_mirror["passed"]
        ),
        "paired_a0_a1": bool(
            len(comparisons) == 12 and all(row["pair_complete"] for row in comparisons)
        ),
    }
    passed = all(gates.values())
    write_csv(output / "physics_audit_v2.csv", rows)
    write_csv(output / "a0_a1_comparison.csv", comparisons)
    write_csv(output / "actuator_mirror_audit.csv", actuator_mirror["rows"])
    for mode, result in legacy_mirror.items():
        write_csv(output / f"mirror_audit_{mode}.csv", result["rows"])
    mirror_json = {
        "legacy": {
            mode: {key: value for key, value in result.items() if key != "rows"}
            for mode, result in legacy_mirror.items()
        },
        "actuator": {key: value for key, value in actuator_mirror.items() if key != "rows"},
    }
    write_json(output / "mirror_audit.json", mirror_json)
    summary = {
        "stage": "P2",
        "passed": passed,
        "trajectory_count": len(rows),
        "candidate_trajectory_count": len(dynamic_rows),
        "candidate_failed_trajectory_count": sum(not row["passed"] for row in dynamic_rows),
        "candidate_tire_failed_trajectory_count": sum(
            not row["gate_tire_raw_utilization"] for row in dynamic_rows
        ),
        "candidate_tire_raw_utilization_min": float(
            min(row["tire_raw_utilization_max"] for row in dynamic_rows)
        ),
        "candidate_tire_raw_utilization_max": float(
            max(row["tire_raw_utilization_max"] for row in dynamic_rows)
        ),
        "instant_tire_raw_utilization_min": float(
            min(row["tire_raw_utilization_max"] for row in instant_rows)
        ),
        "instant_tire_raw_utilization_max": float(
            max(row["tire_raw_utilization_max"] for row in instant_rows)
        ),
        "candidate_max_actual_angle_deg": float(
            max(row["max_actual_angle_deg"] for row in dynamic_rows)
        ),
        "candidate_max_actual_rate_radps": float(
            max(row["max_actual_rate_radps"] for row in dynamic_rows)
        ),
        "candidate_requested_icr_residual_max_mps": float(
            max(row["requested_icr_residual_max_mps"] for row in dynamic_rows)
        ),
        "candidate_actual_icr_residual_max_mps": float(
            max(row["actual_steering_icr_residual_max_mps"] for row in dynamic_rows)
        ),
        "candidate_connector_force_peak_n": float(
            max(row["connector_force_peak_n"] for row in dynamic_rows)
        ),
        "gates": gates,
        "failed_gates": [key for key, value in gates.items() if not value],
        "artifacts": {
            "physics_audit": str(output / "physics_audit_v2.csv"),
            "a0_a1_comparison": str(output / "a0_a1_comparison.csv"),
            "mirror_audit": str(output / "mirror_audit.json"),
        },
    }
    write_json(output / "audit_summary.json", summary)
    return summary

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from contracts import write_json
from icr_metrics import summarize_residual
from run_k2 import MIRROR_INDEX, mirror_audit


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def recovery_times(values: np.ndarray, phases: np.ndarray, dt_s: float, threshold: float) -> list[float | None]:
    phases = np.asarray(phases).astype(str)
    values = np.asarray(values, dtype=float)
    starts = [
        index
        for index in range(1, len(phases))
        if phases[index] != phases[index - 1]
        and phases[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
    ]
    output = []
    for start in starts:
        found = next(
            (index for index in range(start, len(values)) if abs(values[index]) <= threshold),
            None,
        )
        output.append(None if found is None else float((found - start) * dt_s))
    return output


def _yaw_peaks(arrays: dict[str, np.ndarray], summary: dict) -> tuple[float, float]:
    state = np.asarray(arrays["state30"], dtype=float)
    params = json.loads(summary["params_json"])["values"]
    vehicle_inertia = float(params["vehicle"]["yaw_inertia_kgm2"])
    payload_inertia = float(params["derived"]["payload_yaw_inertia_kgm2"])
    vehicle_yaw = state[:, [5, 11, 17, 23]]
    payload_yaw = state[:, 29]
    system = (
        vehicle_inertia * np.sum(vehicle_yaw, axis=1) + payload_inertia * payload_yaw
    ) / (4.0 * vehicle_inertia + payload_inertia)
    return float(np.max(np.abs(payload_yaw))), float(np.max(np.abs(system)))


def audit_trajectory(identity: dict, arrays: dict[str, np.ndarray], summary: dict, protocol: dict) -> dict:
    config = protocol["f3"]
    dt_s = float(protocol["k2"]["model_step_s"])
    time_s = np.asarray(arrays["time_s"], dtype=float)
    steps = np.diff(time_s)
    tire = float(np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float)))
    support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
    total_normal = np.asarray(arrays["vehicle_total_normal_load4_n"], dtype=float)
    support_relative = np.asarray(
        arrays["support_constraint_relative_residual3"], dtype=float
    )
    geom = np.asarray(arrays["icr_geometry_residual_mps"], dtype=float)
    request = np.asarray(arrays["icr_request_residual_mps"], dtype=float)
    actual = np.asarray(arrays["icr_actual_residual_mps"], dtype=float)
    request_stats = summarize_residual(request, float(config["diagnostic_icr_threshold_mps"]))
    actual_stats = summarize_residual(actual, float(config["diagnostic_icr_threshold_mps"]))
    maximum_angle = float(
        np.max(np.abs(np.asarray(arrays["actual_steering_substeps_rad"], dtype=float)))
    )
    maximum_rate = float(
        np.max(np.abs(np.asarray(arrays["actual_steering_rate_substeps_radps"], dtype=float)))
    )
    internal_relative = float(summary["internal_null_max_n"]) / max(
        float(summary["internal_force_peak_n"]), 1.0
    )
    finite = bool(
        all(
            np.all(np.isfinite(value))
            for value in arrays.values()
            if np.asarray(value).dtype.kind not in {"O", "U", "S"}
        )
    )
    phase = np.asarray(arrays["command_phase"]).astype(str)
    primary = phase == "STEP_PRIMARY"
    reverse = phase == "STEP_REVERSE"
    front = np.asarray(arrays["virtual_front_deg"], dtype=float)
    rear = np.asarray(arrays["virtual_rear_deg"], dtype=float)
    scenario = bool(
        np.any(phase == "ACCEL_TO_30M")
        and abs(np.sum(primary) * dt_s - 5.0) <= dt_s + 1.0e-12
        and abs(np.sum(reverse) * dt_s - 5.0) <= dt_s + 1.0e-12
        and np.allclose(np.abs(front[primary]), 5.0, atol=1.0e-15, rtol=0.0)
        and np.allclose(np.abs(rear[primary]), 2.5, atol=1.0e-15, rtol=0.0)
        and np.allclose(np.abs(front[reverse]), 5.0, atol=1.0e-15, rtol=0.0)
        and np.allclose(np.abs(rear[reverse]), 2.5, atol=1.0e-15, rtol=0.0)
    )
    gates = {
        "finite": finite,
        "time_grid": bool(
            steps.size
            and np.all(steps > 0.0)
            and np.max(np.abs(steps - dt_s)) <= float(config["time_step_atol_s"])
        ),
        "completion": bool(
            summary["status"] == "PASS"
            and float(summary["distance_m"]) >= float(config["distance_target_m"])
        ),
        "support_nonnegative": float(np.min(support)) >= float(config["support_min_atol_n"]),
        "support_constraints": float(np.max(np.abs(support_relative)))
        <= float(config["support_constraint_relative_atol"]),
        "tire": tire <= float(config["tire_raw_utilization_max"]),
        "actuator_angle": maximum_angle
        <= np.deg2rad(float(protocol["actuator"]["angle_max_deg"]))
        + float(config["angle_atol_rad"]),
        "actuator_rate": maximum_rate
        <= float(protocol["actuator"]["rate_max_radps"])
        + float(config["rate_atol_radps"]),
        "geometry_icr": float(np.max(np.abs(geom)))
        <= float(config["geometry_residual_atol_mps"]),
        "connector_ultimate": not bool(summary["ultimate_force_exceeded"]),
        "action_reaction": float(summary["action_reaction_max_n"])
        <= float(config["action_reaction_atol_n"]),
        "internal_null": internal_relative <= float(config["internal_null_relative_atol"]),
        "replay": bool(identity["replay_hash_match"]),
        "scenario": scenario,
    }
    payload_yaw_peak, system_yaw_peak = _yaw_peaks(arrays, summary)
    return {
        "sample_count": len(time_s),
        "duration_s": float(summary["duration_s"]),
        "distance_m": float(summary["distance_m"]),
        "support_min_n": float(np.min(support)),
        "support_max_n": float(np.max(support)),
        "support_min_by_vehicle_n": json.dumps(np.min(support, axis=0).tolist()),
        "support_max_by_vehicle_n": json.dumps(np.max(support, axis=0).tolist()),
        "total_normal_min_n": float(np.min(total_normal)),
        "support_constraint_relative_max": float(np.max(np.abs(support_relative))),
        "tire_raw_utilization_max": tire,
        "actual_angle_max_deg": float(np.rad2deg(maximum_angle)),
        "actual_rate_max_radps": maximum_rate,
        "geom_peak_mps": float(np.max(np.abs(geom))),
        "request_peak_mps": request_stats["peak_mps"],
        "request_p95_mps": request_stats["p95_mps"],
        "request_rms_mps": request_stats["rms_mps"],
        "request_fraction_gt_0p5": request_stats["fraction_above_threshold"],
        "request_recovery_s": json.dumps(recovery_times(request, phase, dt_s, float(config["diagnostic_icr_threshold_mps"]))),
        "actual_peak_mps": actual_stats["peak_mps"],
        "actual_p95_mps": actual_stats["p95_mps"],
        "actual_rms_mps": actual_stats["rms_mps"],
        "actual_fraction_gt_0p5": actual_stats["fraction_above_threshold"],
        "actual_recovery_s": json.dumps(recovery_times(actual, phase, dt_s, float(config["diagnostic_icr_threshold_mps"]))),
        "connector_force_peak_n": float(summary["force_peak_n"]),
        "payload_yaw_rate_peak_radps": payload_yaw_peak,
        "system_yaw_rate_peak_radps": system_yaw_peak,
        "action_reaction_max_n": float(summary["action_reaction_max_n"]),
        "internal_null_relative": internal_relative,
        "passed": all(gates.values()),
        **{f"gate_{name}": value for name, value in gates.items()},
    }


def audit_f3(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    protocol: dict,
    output: Path,
) -> dict:
    rows = []
    mirror_source = {"L0": [], "L1": []}
    grouped = {}
    for identity, arrays, summary in trajectories:
        audit = audit_trajectory(identity, arrays, summary, protocol)
        rows.append({**identity, **audit})
        mirror_source[identity["load_mode"]].append((identity, arrays))
        key = (identity["base_family_id"], identity["direction"], identity["plant"])
        grouped.setdefault(key, {})[identity["load_mode"]] = ({**identity, **audit}, arrays, summary)

    mirror_results = {
        mode: mirror_audit(items, float(protocol["f3"]["mirror_atol"]))
        for mode, items in mirror_source.items()
    }
    support_mirror_rows = []
    support_mirror_max = 0.0
    icr_mirror_max = 0.0
    for mode, items in mirror_source.items():
        pairs = {}
        for identity, arrays in items:
            pairs.setdefault((identity["base_family_id"], identity["plant"]), {})[
                identity["direction"]
            ] = arrays
        for (base, plant), pair in sorted(pairs.items()):
            if set(pair) != {"left", "right"} or len(pair["left"]["time_s"]) != len(pair["right"]["time_s"]):
                support_mirror_rows.append({"load_mode": mode, "base_family_id": base, "plant": plant, "passed": False})
                continue
            left, right = pair["left"], pair["right"]
            mirrored_support = left["payload_support_load4_n"][:, MIRROR_INDEX]
            support_scale = np.maximum(np.maximum(np.abs(mirrored_support), np.abs(right["payload_support_load4_n"])), 1.0)
            support_error = float(np.max(np.abs(mirrored_support - right["payload_support_load4_n"]) / support_scale))
            icr_error = max(
                float(np.max(np.abs(left["icr_geometry_residual_mps"] - right["icr_geometry_residual_mps"]))),
                float(np.max(np.abs(left["icr_request_residual_mps"] - right["icr_request_residual_mps"]))),
                float(np.max(np.abs(left["icr_actual_residual_mps"] - right["icr_actual_residual_mps"]))),
                float(np.max(np.abs(left["icr_request_signed4_mps"][:, MIRROR_INDEX] + right["icr_request_signed4_mps"]))),
                float(np.max(np.abs(left["icr_actual_signed4_mps"][:, MIRROR_INDEX] + right["icr_actual_signed4_mps"]))),
            )
            support_mirror_max = max(support_mirror_max, support_error)
            icr_mirror_max = max(icr_mirror_max, icr_error)
            support_mirror_rows.append(
                {
                    "load_mode": mode,
                    "base_family_id": base,
                    "plant": plant,
                    "support_relative_error": support_error,
                    "icr_max_abs_error_mps": icr_error,
                    "passed": support_error <= float(protocol["f3"]["mirror_atol"])
                    and icr_error <= float(protocol["f3"]["mirror_atol"]),
                }
            )

    comparisons = []
    tradeoff_count = 0
    pair_identity_failure_count = 0
    for (base, direction, plant), pair in sorted(grouped.items()):
        if set(pair) != {"L0", "L1"}:
            pair_identity_failure_count += 1
            continue
        (l0, l0_arrays, l0_summary), (l1, l1_arrays, l1_summary) = pair["L0"], pair["L1"]
        identity_ok = bool(
            l0_summary["params_sha256"] == l1_summary["params_sha256"]
            and l0_summary["initial_state_sha256"] == l1_summary["initial_state_sha256"]
            and l0["gate_scenario"]
            and l1["gate_scenario"]
            and l0["seed"] == l1["seed"]
            and l0["direction"] == l1["direction"]
            and l0["plant"] == l1["plant"]
        )
        pair_identity_failure_count += int(not identity_ok)
        def change(new: float, old: float) -> float:
            return (new - old) / max(abs(old), 1.0e-12)
        changes = {
            "payload_yaw_peak_relative_change": change(l1["payload_yaw_rate_peak_radps"], l0["payload_yaw_rate_peak_radps"]),
            "system_yaw_peak_relative_change": change(l1["system_yaw_rate_peak_radps"], l0["system_yaw_rate_peak_radps"]),
            "connector_peak_relative_change": change(l1["connector_force_peak_n"], l0["connector_force_peak_n"]),
        }
        tradeoff = any(value > float(protocol["f3"]["tradeoff_relative_limit"]) for value in changes.values())
        tradeoff_count += int(tradeoff)
        comparisons.append(
            {
                "base_family_id": base,
                "direction": direction,
                "plant": plant,
                "pair_identity_passed": identity_ok,
                "l0_tire_peak": l0["tire_raw_utilization_max"],
                "l1_tire_peak": l1["tire_raw_utilization_max"],
                "l0_support_min_n": l0["support_min_n"],
                "l1_support_min_n": l1["support_min_n"],
                **changes,
                "tradeoff_review": tradeoff,
            }
        )

    write_csv(output / "physics_audit_focus.csv", rows)
    write_csv(output / "l0_l1_comparison.csv", comparisons)
    write_csv(output / "support_icr_mirror.csv", support_mirror_rows)
    for mode, result in mirror_results.items():
        write_csv(output / f"legacy_mirror_{mode.lower()}.csv", result["rows"])
    l1_rows = [row for row in rows if row["load_mode"] == "L1"]
    l0_rows = [row for row in rows if row["load_mode"] == "L0"]
    gates = {
        "trajectory_count": len(rows) == 24 and len(l0_rows) == len(l1_rows) == 12,
        "l1_all_hard_contracts": len(l1_rows) == 12 and all(row["passed"] for row in l1_rows),
        "l1_tire_envelope": len(l1_rows) == 12 and all(row["gate_tire"] for row in l1_rows),
        "l1_support_nonnegative": len(l1_rows) == 12 and all(row["gate_support_nonnegative"] for row in l1_rows),
        "l1_support_constraints": len(l1_rows) == 12 and all(row["gate_support_constraints"] for row in l1_rows),
        "l0_baseline_contracts": len(l0_rows) == 12 and all(row["passed"] for row in l0_rows),
        "mirror": all(result["passed"] for result in mirror_results.values())
        and bool(support_mirror_rows)
        and all(bool(row["passed"]) for row in support_mirror_rows),
        "pair_identity": len(comparisons) == 12 and pair_identity_failure_count == 0,
    }
    passed = all(gates.values())
    summary = {
        "stage": "F3",
        "passed": passed,
        "trajectory_count": len(rows),
        "l1_count": len(l1_rows),
        "l1_failed_count": sum(not row["passed"] for row in l1_rows),
        "l1_tire_peak_range": [
            min(row["tire_raw_utilization_max"] for row in l1_rows),
            max(row["tire_raw_utilization_max"] for row in l1_rows),
        ],
        "l0_tire_peak_range": [
            min(row["tire_raw_utilization_max"] for row in l0_rows),
            max(row["tire_raw_utilization_max"] for row in l0_rows),
        ],
        "l1_support_load_range_n": [
            min(row["support_min_n"] for row in l1_rows),
            max(row["support_max_n"] for row in l1_rows),
        ],
        "l1_support_constraint_relative_max": max(
            row["support_constraint_relative_max"] for row in l1_rows
        ),
        "l1_icr_geometry_peak_mps": max(row["geom_peak_mps"] for row in l1_rows),
        "l1_icr_request_peak_range_mps": [
            min(row["request_peak_mps"] for row in l1_rows),
            max(row["request_peak_mps"] for row in l1_rows),
        ],
        "l1_icr_actual_peak_range_mps": [
            min(row["actual_peak_mps"] for row in l1_rows),
            max(row["actual_peak_mps"] for row in l1_rows),
        ],
        "l1_connector_force_peak_n": max(row["connector_force_peak_n"] for row in l1_rows),
        "support_mirror_relative_max": support_mirror_max,
        "icr_mirror_max_abs_mps": icr_mirror_max,
        "pair_identity_failure_count": pair_identity_failure_count,
        "tradeoff_review_count": tradeoff_count,
        "tradeoff_review_required": tradeoff_count > 0,
        "gates": gates,
        "failed_gates": [name for name, value in gates.items() if not value],
        "artifacts": {
            "physics_audit": str(output / "physics_audit_focus.csv"),
            "l0_l1_comparison": str(output / "l0_l1_comparison.csv"),
            "support_icr_mirror": str(output / "support_icr_mirror.csv"),
        },
    }
    write_json(output / "audit_summary.json", summary)
    return summary

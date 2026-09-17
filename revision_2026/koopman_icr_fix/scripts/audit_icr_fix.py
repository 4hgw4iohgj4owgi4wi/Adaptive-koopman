from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from icr_metrics import summarize_residual


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def recovery_times(
    values: np.ndarray, phases: np.ndarray, dt_s: float, threshold: float
) -> list[float | None]:
    values = np.asarray(values, dtype=float)
    phases = np.asarray(phases).astype(str)
    starts = [
        index
        for index in range(1, len(phases))
        if phases[index] != phases[index - 1]
        and phases[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
    ]
    output: list[float | None] = []
    for start in starts:
        found = next(
            (index for index in range(start, len(values)) if abs(values[index]) <= threshold),
            None,
        )
        output.append(None if found is None else float((found - start) * dt_s))
    return output


def _yaw_peaks(arrays: Mapping[str, np.ndarray], summary: dict) -> tuple[float, float]:
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


def compare_common_fields(
    candidate: Mapping[str, np.ndarray], reference: Mapping[str, np.ndarray]
) -> dict:
    excluded_prefixes = (
        "request_g0_",
        "request_g1_",
        "request_g2_",
        "request_heading_",
        "request_feedback_",
        "request_clip_",
        "icr_g0_",
        "icr_g1_",
        "icr_g2_",
    )
    excluded_exact = {"actuator_mode"}
    common = sorted(
        key
        for key in set(candidate) & set(reference)
        if key not in excluded_exact and not key.startswith(excluded_prefixes)
    )
    first = None
    maximum = 0.0
    compared = 0
    for key in common:
        left = np.asarray(candidate[key])
        right = np.asarray(reference[key])
        if left.shape != right.shape:
            first = {
                "field": key,
                "reason": "shape",
                "candidate_shape": list(left.shape),
                "reference_shape": list(right.shape),
            }
            maximum = float("1e300")
            break
        if left.dtype.kind in {"O", "U", "S"} or right.dtype.kind in {"O", "U", "S"}:
            equal = np.array_equal(left.astype(str), right.astype(str))
            error = 0.0 if equal else float("1e300")
            index = None
        else:
            difference = np.abs(left.astype(float) - right.astype(float))
            error = float(np.max(difference)) if difference.size else 0.0
            index = (
                list(np.unravel_index(int(np.argmax(difference)), difference.shape))
                if difference.size and error > 0.0
                else None
            )
        compared += 1
        maximum = max(maximum, error)
        if error > 0.0 and first is None:
            first = {"field": key, "max_abs": error, "index": index}
    return {
        "common_field_count": compared,
        "candidate_only": sorted(set(candidate) - set(reference)),
        "reference_only": sorted(set(reference) - set(candidate)),
        "max_abs": maximum,
        "first_different": first,
    }


def audit_trajectory(
    identity: dict,
    arrays: Mapping[str, np.ndarray],
    summary: dict,
    protocol: dict,
    parent_comparison: dict | None,
) -> dict:
    config = protocol["f3"]
    dt_s = float(protocol["k2"]["model_step_s"])
    time_s = np.asarray(arrays["time_s"], dtype=float)
    steps = np.diff(time_s)
    support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
    total_normal = np.asarray(arrays["vehicle_total_normal_load4_n"], dtype=float)
    constraints = np.asarray(arrays["support_constraint_relative_residual3"], dtype=float)
    tire = float(np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float)))
    geom = np.asarray(arrays["icr_geometry_residual_mps"], dtype=float)
    g0 = np.asarray(arrays["icr_g0_residual_mps"], dtype=float)
    actual = np.asarray(arrays["icr_actual_residual_mps"], dtype=float)
    actual_stats = summarize_residual(
        actual, float(config["diagnostic_icr_threshold_mps"])
    )
    request = np.asarray(arrays["requested_control4x2"], dtype=float)[:, :, 1]
    actual_angle = np.asarray(arrays["actual_steering_rad"], dtype=float)
    tracking = np.max(np.abs(request - actual_angle), axis=1)
    rates = np.asarray(arrays["actual_steering_rate_substeps_radps"], dtype=float)
    angles = np.asarray(arrays["actual_steering_substeps_rad"], dtype=float)
    rate_masks = np.asarray(arrays["actuator_rate_limited_mask"], dtype=bool)
    angle_masks = np.asarray(arrays["actuator_angle_limited_mask"], dtype=bool)
    force = np.asarray(arrays["force_payload_body_n"], dtype=float)
    impulse = np.asarray(arrays["force_interval_impulse_world_ns"], dtype=float)
    force_peak4 = np.max(np.linalg.norm(force, axis=2), axis=0)
    impulse_peak4 = np.max(np.linalg.norm(impulse, axis=2), axis=0)
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
    mode = identity["actuator_mode"]
    parent_max = None if parent_comparison is None else parent_comparison["max_abs"]
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
        "support_constraints": float(np.max(np.abs(constraints)))
        <= float(config["support_constraint_relative_atol"]),
        "tire": tire <= float(config["tire_raw_utilization_max"]),
        "actuator_angle": float(np.max(np.abs(angles)))
        <= np.deg2rad(float(protocol["actuator"]["angle_max_deg"]))
        + float(config["angle_atol_rad"]),
        "actuator_rate": True
        if mode in {"A0", "A1"}
        else float(np.max(np.abs(rates)))
        <= float(protocol["actuator"]["rate_max_radps"])
        + float(config["rate_atol_radps"]),
        "geometry_icr": float(np.max(np.abs(geom)))
        <= float(config["geometry_residual_atol_mps"]),
        "g0_icr": float(np.max(np.abs(g0)))
        <= float(config["geometry_residual_atol_mps"]),
        "connector_ultimate": not bool(summary["ultimate_force_exceeded"]),
        "action_reaction": float(summary["action_reaction_max_n"])
        <= float(config["action_reaction_atol_n"]),
        "internal_null": internal_relative <= float(config["internal_null_relative_atol"]),
        "replay": bool(identity["replay_hash_match"]),
        "scenario": scenario,
        "a3_parent_common_fields": True
        if mode != "A3"
        else parent_max is not None
        and parent_max <= float(config["a3_parent_common_field_atol"]),
    }
    payload_yaw, system_yaw = _yaw_peaks(arrays, summary)
    return {
        **identity,
        "sample_count": len(time_s),
        "duration_s": float(summary["duration_s"]),
        "distance_m": float(summary["distance_m"]),
        "actual_icr_peak_mps": actual_stats["peak_mps"],
        "actual_icr_p95_mps": actual_stats["p95_mps"],
        "actual_icr_rms_mps": actual_stats["rms_mps"],
        "actual_icr_fraction_gt_0p5": actual_stats["fraction_above_threshold"],
        "actual_icr_recovery_s": json.dumps(
            recovery_times(
                actual, phase, dt_s, float(config["diagnostic_icr_threshold_mps"])
            )
        ),
        "tracking_peak_rad": float(np.max(tracking)),
        "tracking_p95_rad": float(np.percentile(tracking, 95)),
        "tracking_rms_rad": float(np.sqrt(np.mean(tracking**2))),
        "actual_rate_peak_radps": float(np.max(np.abs(rates))),
        "rate_mask_fraction": float(np.mean(rate_masks)),
        "angle_mask_fraction": float(np.mean(angle_masks)),
        "tire_raw_utilization_max": tire,
        "support_min_n": float(np.min(support)),
        "total_normal_min_n": float(np.min(total_normal)),
        "connector_force_peak_n": float(np.max(force_peak4)),
        "connector_force_peak4_n": json.dumps(force_peak4.tolist()),
        "connector_impulse_peak4_ns": json.dumps(impulse_peak4.tolist()),
        "payload_yaw_rate_peak_radps": payload_yaw,
        "system_yaw_rate_peak_radps": system_yaw,
        "action_reaction_max_n": float(summary["action_reaction_max_n"]),
        "internal_null_relative": internal_relative,
        "g0_peak_mps": float(np.max(np.abs(g0))),
        "a3_parent_common_max_abs": parent_max,
        "passed": all(gates.values()),
        **{f"gate_{name}": value for name, value in gates.items()},
    }


def actuator_attribution(audit_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    metrics = (
        "actual_icr_peak_mps",
        "actual_icr_p95_mps",
        "actual_icr_rms_mps",
        "actual_icr_fraction_gt_0p5",
        "tracking_peak_rad",
        "tracking_p95_rad",
        "tracking_rms_rad",
        "rate_mask_fraction",
        "angle_mask_fraction",
        "tire_raw_utilization_max",
        "connector_force_peak_n",
        "payload_yaw_rate_peak_radps",
        "system_yaw_rate_peak_radps",
    )
    mode_rows: list[dict] = []
    contribution_rows: list[dict] = []
    groups: dict[tuple[str, str], dict[str, dict]] = {}
    for row in audit_rows:
        groups.setdefault((row["direction"], row["plant"]), {})[
            row["actuator_mode"]
        ] = row
    previous = {"A0": None, "A1": "A0", "A2": "A1", "A3": "A2"}
    names = {"A1": "lag", "A2": "rate", "A3": "angle"}
    for (direction, plant), modes in sorted(groups.items()):
        for mode in ("A0", "A1", "A2", "A3"):
            row = dict(modes[mode])
            prior = previous[mode]
            for metric in metrics:
                row[f"delta_from_previous_{metric}"] = (
                    None if prior is None else float(row[metric]) - float(modes[prior][metric])
                )
                if prior is not None:
                    contribution_rows.append(
                        {
                            "direction": direction,
                            "plant": plant,
                            "contribution": names[mode],
                            "difference": f"{mode}-{prior}",
                            "metric": metric,
                            "delta": float(row[metric]) - float(modes[prior][metric]),
                        }
                    )
            mode_rows.append(row)
    return mode_rows, contribution_rows


def audit_run(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    protocol: dict,
    parent_arrays: dict[tuple[str, str], dict[str, np.ndarray]],
    output: Path,
) -> dict:
    rows: list[dict] = []
    comparisons: list[dict] = []
    for identity, arrays, summary in trajectories:
        comparison = None
        if identity["actuator_mode"] == "A3":
            comparison = compare_common_fields(
                arrays, parent_arrays[(identity["direction"], identity["plant"])]
            )
            comparisons.append({**identity, **comparison})
        rows.append(audit_trajectory(identity, arrays, summary, protocol, comparison))
    write_csv(output / "physics_audit.csv", rows)
    write_csv(output / "a3_parent_comparison.csv", comparisons)
    modes, contributions = actuator_attribution(rows)
    write_csv(output / "actuator_attribution.csv", modes)
    write_csv(output / "actuator_contributions.csv", contributions)
    failed = [row for row in rows if not row["passed"]]
    failed_gates = sorted(
        {
            key.removeprefix("gate_")
            for row in failed
            for key, value in row.items()
            if key.startswith("gate_") and not bool(value)
        }
    )
    result = {
        "passed": not failed,
        "trajectory_count": len(rows),
        "failed_trajectory_count": len(failed),
        "failed_gates": failed_gates,
        "a3_parent_common_max_abs": max(
            float(item["max_abs"]) for item in comparisons
        ),
        "g0_peak_max_mps": max(float(row["g0_peak_mps"]) for row in rows),
    }
    (output / "audit_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return result

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_substep import EventSubstepConfig, advance_outer_step
from four_vehicle_common import ModelParams, connector_diagnostics, initialize_state, rotation, split_state
from paired_maneuvers_r3 import scenario_command, staged_100m_command
from steering_allocator import allocate_controls
from step_features import aggregate_control_interval, aggregate_step_audit


FACTORS = (("V1-F2", "V1", "F2"), ("V1-ES", "V1", "ES"), ("R3-F2", "R3", "F2"), ("R3-ES", "R3", "ES"))
DIRECTIONAL = ("connector_longitudinal", "connector_lateral", "connector_diagonal_1", "connector_diagonal_2")
SCENARIOS = ("100m", "straight", "single_lane_change_left", "hairpin_left", "line_curve_transition_left", *DIRECTIONAL)
DURATIONS = {"straight": 8.0, "single_lane_change_left": 8.0, "hairpin_left": 9.0, "line_curve_transition_left": 7.0, **{name: 2.0 for name in DIRECTIONAL}}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def command_for(name: str, t: float, distance: float, time_at_30: float | None, decel_state: tuple[float, float] | None, seed: int = 0):
    if name != "100m":
        return scenario_command(name, t, seed=seed)
    time_since_30 = 0.0 if time_at_30 is None else t - time_at_30
    if time_since_30 >= 10.0:
        if decel_state is None:
            raise RuntimeError("deceleration state was not frozen")
        return staged_100m_command(distance, time_since_30, *decel_state)
    return staged_100m_command(distance, time_since_30)


def simulate(name: str, label: str, law: str, mode: str, seed: int = 0) -> tuple[dict, dict]:
    params = ModelParams()
    state = initialize_state(params, 2.0)
    initial_state = state.copy()
    config = EventSubstepConfig()
    control_dt = 0.020
    plant_dt = 0.002
    target_duration = DURATIONS.get(name)
    time_s = 0.0
    distance_m = 0.0
    time_at_30 = None
    decel_state = None
    previous_position = state[24:26].copy()
    records = {key: [] for key in (
        "time_s", "distance_m", "state30", "control4x2", "base_acceleration_mps2", "virtual_front_deg", "virtual_rear_deg",
        "force_payload_body_n", "force_direction_body_rad", "force_active_mask", "internal_force_vector_n", "tension_proxy_n",
        "payload_wrench", "signed_gap_m", "smoothing_fraction", "tire_raw_utilization", "vehicle_yaw_rad", "payload_yaw_rad",
        "force_interval_mean_world_n", "force_interval_mean_body_n", "force_interval_impulse_world_ns", "internal_force_interval_mean_n",
        "tension_proxy_interval_mean_n", "contact_fraction", "smoothing_weight_mean", "event_counts16",
    )}
    force_norm_2ms = []
    force_time_2ms = []
    damping_integral = np.zeros(4)
    total_force_integral = np.zeros(4)
    action_reaction_max = 0.0
    internal_null_max = 0.0
    steering_clip_count = 0
    steering_total_count = 0
    event_count = 0
    status = "PASS"
    started = time.perf_counter()
    while True:
        if name == "100m":
            if distance_m >= 100.0:
                break
            if time_s >= 80.0:
                status = "TIME_CAP_BEFORE_100M"
                break
        elif time_s >= float(target_duration) - 1e-12:
            break
        _, payload = split_state(state)
        if name == "100m" and distance_m >= 30.0 and time_at_30 is None:
            time_at_30 = time_s
        if name == "100m" and time_at_30 is not None and time_s - time_at_30 >= 10.0 and decel_state is None:
            decel_state = (float(payload[3]), distance_m)
        command = command_for(name, time_s, distance_m, time_at_30, decel_state, seed=seed)
        controls, allocation = allocate_controls(
            state,
            command.acceleration_mps2,
            command.virtual_front_deg,
            command.virtual_rear_deg,
            params,
        )
        controls[:, 0] += np.asarray(command.vehicle_accel_offset_mps2, dtype=float)
        controls[:, 1] += np.deg2rad(np.asarray(command.vehicle_steer_offset_deg, dtype=float))
        steering_limit = np.deg2rad(15.0)
        post_offset_clipped = np.abs(controls[:, 1]) > steering_limit
        steering_clip_count += int(np.sum(np.asarray(allocation["steering_clipped"], dtype=bool) | post_offset_clipped))
        steering_total_count += 4
        controls[:, 1] = np.clip(controls[:, 1], -steering_limit, steering_limit)
        step_features = []
        for _ in range(10):
            h = min(plant_dt, (target_duration - time_s) if target_duration is not None else plant_dt)
            state, audit = advance_outer_step(state, controls, law, params, h, mode, config)
            if audit["status"] != "PASS":
                status = audit["status"]
                break
            feature = aggregate_step_audit(state, controls, audit)
            step_features.append(feature)
            time_s += h
            diag = audit["endpoint_diagnostics"]
            force_time_2ms.append(time_s)
            force_norm_2ms.append(np.asarray(diag["force_norm_n"], dtype=float))
            action_reaction_max = max(action_reaction_max, float(np.max(np.linalg.norm(diag["action_reaction_residual_n"], axis=1))))
            internal_null_max = max(internal_null_max, float(np.linalg.norm(diag["internal_null_residual"])))
            event_count += len(audit["events"])
            for segment in audit["interval_segments"]:
                dt = float(segment["dt_s"])
                damping_integral += np.abs(np.asarray(segment.get("damping_force_n", np.zeros(4)), dtype=float)) * dt
                total_force_integral += np.asarray(segment["force_midpoint_n"], dtype=float) * dt
            position = state[24:26]
            distance_m += float(np.linalg.norm(position - previous_position))
            previous_position = position.copy()
            if name == "100m" and distance_m >= 100.0:
                break
        if not step_features:
            break
        endpoint = connector_diagnostics(state, params, law)
        _, payload = split_state(state)
        vehicles, _ = split_state(state)
        interval_duration = sum(feature["interval_duration_s"] for feature in step_features)
        interval = aggregate_control_interval(step_features, expected_duration_s=interval_duration)
        records["time_s"].append(time_s)
        records["distance_m"].append(distance_m)
        records["state30"].append(state.copy())
        records["control4x2"].append(controls.copy())
        records["base_acceleration_mps2"].append(command.acceleration_mps2)
        records["virtual_front_deg"].append(command.virtual_front_deg)
        records["virtual_rear_deg"].append(command.virtual_rear_deg)
        records["force_payload_body_n"].append(endpoint["force_payload_body_n"].copy())
        records["force_direction_body_rad"].append(endpoint["force_direction_body_rad"].copy())
        records["force_active_mask"].append(endpoint["force_active_mask"].copy())
        records["internal_force_vector_n"].append(endpoint["internal_force_vector_n"].copy())
        records["tension_proxy_n"].append([endpoint["tension_x_n"], endpoint["tension_y_n"]])
        records["payload_wrench"].append(endpoint["generalized_payload_wrench"].copy())
        records["signed_gap_m"].append(endpoint["signed_gap_m"].copy())
        records["smoothing_fraction"].append(np.mean([feature["smoothing_fraction"] for feature in step_features], axis=0))
        records["tire_raw_utilization"].append(np.max([feature["tire_raw_utilization_max"] for feature in step_features], axis=0))
        records["vehicle_yaw_rad"].append(vehicles[:, 2].copy())
        records["payload_yaw_rad"].append(payload[2])
        records["force_interval_mean_world_n"].append(interval["force_mean_world"].copy())
        records["force_interval_mean_body_n"].append(interval["force_mean_world"] @ rotation(payload[2]))
        records["force_interval_impulse_world_ns"].append(interval["force_impulse_world"].copy())
        records["internal_force_interval_mean_n"].append(interval["internal_force_mean"].copy())
        records["tension_proxy_interval_mean_n"].append(interval["tension_proxy_mean"].copy())
        records["contact_fraction"].append(interval["contact_fraction"].copy())
        records["smoothing_weight_mean"].append(interval["g_mean"].copy())
        records["event_counts16"].append(interval["event_counts16"].copy())
        if status != "PASS" or (name == "100m" and distance_m >= 100.0):
            break
    arrays = {key: np.asarray(value) for key, value in records.items()}
    force_norm = np.asarray(force_norm_2ms, dtype=float)
    jumps = np.abs(np.diff(force_norm, axis=0)) if len(force_norm) > 1 else np.zeros((1, 4))
    internal_norm = np.linalg.norm(arrays["internal_force_vector_n"], axis=1) if len(arrays["time_s"]) else np.zeros(1)
    peak_index = int(np.argmax(internal_norm)) if len(internal_norm) else 0
    summary = {
        "scenario": name,
        "factor": label,
        "law": law,
        "integrator": mode,
        "status": status,
        "duration_s": time_s,
        "distance_m": distance_m,
        "samples_20ms": int(len(arrays["time_s"])),
        "samples_2ms": int(len(force_norm)),
        "force_peak_n": np.max(force_norm, axis=0).tolist() if len(force_norm) else [0.0] * 4,
        "force_jump_p99_n": np.quantile(jumps, 0.99, axis=0).tolist(),
        "internal_force_peak_n": float(np.max(internal_norm)),
        "internal_force_vector_at_peak_n": arrays["internal_force_vector_n"][peak_index].tolist() if len(arrays["time_s"]) else [0.0] * 8,
        "tension_x_peak_n": float(np.max(arrays["tension_proxy_n"][:, 0])) if len(arrays["time_s"]) else 0.0,
        "tension_y_peak_n": float(np.max(arrays["tension_proxy_n"][:, 1])) if len(arrays["time_s"]) else 0.0,
        "payload_force_peak_n": float(np.max(np.linalg.norm(arrays["payload_wrench"][:, :2], axis=1))) if len(arrays["time_s"]) else 0.0,
        "payload_moment_peak_nm": float(np.max(np.abs(arrays["payload_wrench"][:, 2]))) if len(arrays["time_s"]) else 0.0,
        "smoothing_exposure": np.mean(arrays["smoothing_fraction"], axis=0).tolist() if len(arrays["time_s"]) else [0.0] * 4,
        "damping_ratio": (damping_integral / np.maximum(total_force_integral, 1e-12)).tolist(),
        "tire_raw_utilization_max": np.max(arrays["tire_raw_utilization"], axis=0).tolist() if len(arrays["time_s"]) else [0.0] * 4,
        "steering_clipped_fraction": steering_clip_count / max(steering_total_count, 1),
        "action_reaction_max_n": action_reaction_max,
        "internal_null_max": internal_null_max,
        "event_count": event_count,
        "runtime_s": time.perf_counter() - started,
        "finite": bool(all(np.all(np.isfinite(value)) for value in arrays.values())),
    }
    arrays["force_time_2ms"] = np.asarray(force_time_2ms)
    arrays["force_norm_2ms"] = force_norm
    arrays["initial_state30"] = initial_state
    return summary, arrays


def directional_checks(summaries: list[dict]) -> tuple[dict, dict]:
    if not summaries:
        return {}, {"status": "NOT_APPLICABLE_NO_DIRECTIONAL_RUNS", "cosine_matrix": [], "norms_n": []}
    vectors = np.asarray([summary["internal_force_vector_at_peak_n"] for summary in summaries], dtype=float)
    norms = np.linalg.norm(vectors, axis=1)
    cosine = np.eye(len(vectors))
    for i in range(len(vectors)):
        for j in range(len(vectors)):
            cosine[i, j] = float(np.dot(vectors[i], vectors[j]) / max(norms[i] * norms[j], 1e-12))
    checks = {
        "all_finite_pass": all(summary["status"] == "PASS" and summary["finite"] for summary in summaries),
        "internal_peak_ge_50n": all(summary["internal_force_peak_n"] >= 50.0 for summary in summaries),
        "tire_raw_utilization_le_0p9": all(max(summary["tire_raw_utilization_max"]) <= 0.9 for summary in summaries),
        "distinct_internal_modes": all(cosine[i, j] < 0.99 for i in range(len(vectors)) for j in range(i + 1, len(vectors))),
    }
    return checks, {"cosine_matrix": cosine.tolist(), "norms_n": norms.tolist()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--factor", choices=[factor[0] for factor in FACTORS])
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    summaries = []
    if args.scenario:
        selected_factors = [factor for factor in FACTORS if args.factor is None or factor[0] == args.factor]
        tasks = [(args.scenario, *factor) for factor in selected_factors]
    elif args.pilot:
        tasks = [(name, "R3-ES", "R3", "ES") for name in DIRECTIONAL]
    else:
        tasks = [(name, *factor) for name in SCENARIOS for factor in FACTORS]
    for name, label, law, mode in tasks:
        run_dir = output / name / label
        run_dir.mkdir(parents=True, exist_ok=True)
        summary, arrays = simulate(name, label, law, mode)
        summaries.append(summary)
        write_json(run_dir / "summary.json", summary)
        np.savez_compressed(run_dir / "timeseries.npz", **arrays)
    write_csv(output / "maneuver_summary.csv", summaries)
    directional = [summary for summary in summaries if summary["scenario"] in DIRECTIONAL and summary["factor"] == "R3-ES"]
    directional_gate, directional_diagnostic = directional_checks(directional)
    write_json(output / "directional_diagnosis.json", directional_diagnostic)
    general_checks = {
        "all_runs_finite_pass": all(summary["status"] == "PASS" and summary["finite"] for summary in summaries),
        "action_reaction": all(summary["action_reaction_max_n"] <= 1e-10 for summary in summaries),
        "internal_null": all(summary["internal_null_max"] <= 1e-8 * max(1.0, summary["internal_force_peak_n"]) for summary in summaries),
        "tire_raw_utilization_le_0p9": all(max(summary["tire_raw_utilization_max"]) <= 0.9 for summary in summaries),
    }
    if not args.pilot:
        general_checks["all_100m_runs_complete"] = all(summary["distance_m"] >= 100.0 for summary in summaries if summary["scenario"] == "100m")
    checks = {**general_checks, **directional_gate}
    passed = all(checks.values())
    complete = {
        "stage": f"N4_{args.scenario.upper()}_REPAIR" if args.scenario else ("N4_PILOT" if args.pilot else "N4_FULL"),
        "passed": passed,
        "run_count": len(summaries),
        "checks": checks,
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        low = [summary["scenario"] for summary in directional if summary["internal_force_peak_n"] < 50.0]
        saturated = [summary["scenario"] for summary in directional if max(summary["tire_raw_utilization_max"]) > 0.9]
        complete["repair_code"] = "DIRECTIONAL_LOW_RESPONSE" if low and not saturated else "N4_MANEUVER_GATE"
        complete["low_response_modes"] = low
        complete["saturated_modes"] = saturated
        complete["next_action"] = "Increase only the low-response directional amplitude by 25% when unsaturated, then rerun the four directional pilot."
    write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data_manifest import array_sha256, canonical_json, canonical_params, params_sha256
from scenarios import ScenarioSpec, command_for


CONTROL_SUBSTEPS = 10


def resolved_params(seed: int, protocol: dict):
    from four_vehicle_common import ModelParams

    rng = np.random.default_rng(int(seed))
    config = protocol["k2"]
    base = ModelParams()
    payload_scale = rng.uniform(*map(float, config["payload_mass_scale"]))
    connector_low, connector_high = map(float, config["connector_scale"])
    return replace(
        base,
        vehicle=replace(base.vehicle, mu=float(rng.uniform(*map(float, config["mu"])))),
        payload=replace(base.payload, mass_kg=float(base.payload.mass_kg * payload_scale)),
        connector=replace(
            base.connector,
            stiffness_npm=float(base.connector.stiffness_npm * rng.uniform(connector_low, connector_high)),
            damping_nspm=float(base.connector.damping_nspm * rng.uniform(connector_low, connector_high)),
            free_play_m=float(base.connector.free_play_m * rng.uniform(connector_low, connector_high)),
        ),
    )


def initial_speed(seed: int, protocol: dict) -> float:
    rng = np.random.default_rng(int(seed) + 100_003)
    return float(rng.uniform(*map(float, protocol["k2"]["initial_speed_mps"])))


def run_complete_control_interval(stepper: Callable[[int], object]) -> list[object]:
    """Execute every plant substep; distance termination is checked only after this returns."""
    return [stepper(index) for index in range(CONTROL_SUBSTEPS)]


def simulate_trajectory(
    spec: ScenarioSpec,
    law: str,
    seed: int,
    params: object,
    protocol: dict,
) -> tuple[dict, dict[str, np.ndarray]]:
    from event_substep import EventSubstepConfig, advance_outer_step
    from four_vehicle_common import connector_diagnostics, initialize_state, rotation, split_state
    from steering_allocator import allocate_controls
    from step_features import aggregate_control_interval, aggregate_step_audit

    config = protocol["k2"]
    control_dt = float(config["model_step_s"])
    plant_dt = float(config["plant_step_s"])
    if abs(control_dt / plant_dt - CONTROL_SUBSTEPS) > 1.0e-12:
        raise ValueError("K2 requires exactly ten 2 ms plant steps per 20 ms model step")
    event_config = EventSubstepConfig()
    state = initialize_state(params, initial_speed(seed, protocol))
    initial_state30 = state.copy()
    time_s = 0.0
    distance_m = 0.0
    previous_position = state[24:26].copy()
    time_at_30_s: float | None = None
    deceleration_state: tuple[float, float] | None = None
    crossing: dict | None = None
    records = {key: [] for key in (
        "time_s",
        "distance_m",
        "state30",
        "control4x2",
        "command_phase",
        "base_acceleration_mps2",
        "virtual_front_deg",
        "virtual_rear_deg",
        "force_payload_body_n",
        "force_direction_body_rad",
        "force_active_mask",
        "internal_force_vector_n",
        "tension_proxy_n",
        "payload_wrench",
        "signed_gap_m",
        "smoothing_fraction",
        "tire_raw_utilization",
        "force_interval_mean_world_n",
        "force_interval_mean_body_n",
        "force_interval_impulse_world_ns",
        "internal_force_interval_mean_n",
        "tension_proxy_interval_mean_n",
        "contact_fraction",
        "smoothing_weight_mean",
        "event_counts16",
        "control_interval_duration_s",
    )}
    started = time.perf_counter()
    status = "PASS"
    action_reaction_max_n = 0.0
    internal_null_max_n = 0.0
    internal_force_peak_n = 0.0
    icr_residual_max_mps = 0.0
    tire_raw_utilization_max = 0.0
    force_peak_n = 0.0
    rated_force_exceeded = False
    ultimate_force_exceeded = False
    steering_clip_count = 0
    steering_total_count = 0
    event_count = 0
    control_interval_index = 0
    duration_intervals = None if spec.duration_s is None else int(round(spec.duration_s / control_dt))

    while True:
        if duration_intervals is not None and control_interval_index >= duration_intervals:
            break
        if spec.distance_target_m is not None and crossing is not None:
            break
        if spec.distance_target_m is not None and time_s >= 80.0:
            status = "TIME_CAP_BEFORE_DISTANCE_TARGET"
            break
        _, payload = split_state(state)
        if spec.scenario == "D2" and distance_m >= 30.0 and time_at_30_s is None:
            time_at_30_s = time_s
        if (
            spec.scenario == "D2"
            and time_at_30_s is not None
            and time_s - time_at_30_s >= 10.0
            and deceleration_state is None
        ):
            deceleration_state = (float(payload[3]), distance_m)
        command = command_for(spec, time_s, distance_m, time_at_30_s, deceleration_state)
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
        steering_clip_count += int(
            np.sum(np.asarray(allocation["steering_clipped"], dtype=bool) | post_offset_clipped)
        )
        steering_total_count += 4
        controls[:, 1] = np.clip(controls[:, 1], -steering_limit, steering_limit)
        icr_residual_max_mps = max(
            icr_residual_max_mps, float(allocation["max_normal_velocity_residual_mps"])
        )

        def plant_step(substep_index: int):
            nonlocal state, time_s, distance_m, previous_position, crossing
            nonlocal action_reaction_max_n, internal_null_max_n, internal_force_peak_n
            nonlocal tire_raw_utilization_max, force_peak_n, rated_force_exceeded, ultimate_force_exceeded, event_count
            state, audit = advance_outer_step(state, controls, law, params, plant_dt, "ES", event_config)
            if audit["status"] != "PASS":
                raise RuntimeError(f"event integrator failed: {audit['status']}")
            feature = aggregate_step_audit(state, controls, audit)
            time_s += plant_dt
            position = state[24:26]
            distance_m += float(np.linalg.norm(position - previous_position))
            previous_position = position.copy()
            diag = audit["endpoint_diagnostics"]
            action_reaction_max_n = max(
                action_reaction_max_n,
                float(np.max(np.linalg.norm(diag["action_reaction_residual_n"], axis=1))),
            )
            internal_null_max_n = max(internal_null_max_n, float(np.linalg.norm(diag["internal_null_residual"])))
            internal_force_peak_n = max(internal_force_peak_n, float(diag["internal_force_norm_n"]))
            force_peak_n = max(force_peak_n, float(np.max(diag["force_norm_n"])))
            rated_force_exceeded = rated_force_exceeded or bool(np.any(diag["rated_force_exceeded"]))
            ultimate_force_exceeded = ultimate_force_exceeded or bool(np.any(diag["ultimate_force_exceeded"]))
            tire_raw_utilization_max = max(
                tire_raw_utilization_max,
                float(np.max([segment.get("tire_raw_utilization", np.zeros(4)) for segment in audit["interval_segments"]])),
            )
            event_count += len(audit["events"])
            if (
                spec.distance_target_m is not None
                and crossing is None
                and distance_m >= float(spec.distance_target_m)
            ):
                crossing = {
                    "control_interval_index": control_interval_index,
                    "substep_in_interval": substep_index + 1,
                    "time_s": time_s,
                    "distance_m": distance_m,
                }
            return feature

        step_features = run_complete_control_interval(plant_step)
        interval = aggregate_control_interval(step_features, expected_duration_s=control_dt)
        endpoint = connector_diagnostics(state, params, law)
        _, payload = split_state(state)
        records["time_s"].append(time_s)
        records["distance_m"].append(distance_m)
        records["state30"].append(state.copy())
        records["control4x2"].append(controls.copy())
        records["command_phase"].append(command.phase)
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
        records["smoothing_fraction"].append(interval["smoothing_fraction"].copy())
        records["tire_raw_utilization"].append(interval["tire_raw_utilization_max"].copy())
        records["force_interval_mean_world_n"].append(interval["force_mean_world"].copy())
        records["force_interval_mean_body_n"].append(interval["force_mean_world"] @ rotation(payload[2]))
        records["force_interval_impulse_world_ns"].append(interval["force_impulse_world"].copy())
        records["internal_force_interval_mean_n"].append(interval["internal_force_mean"].copy())
        records["tension_proxy_interval_mean_n"].append(interval["tension_proxy_mean"].copy())
        records["contact_fraction"].append(interval["contact_fraction"].copy())
        records["smoothing_weight_mean"].append(interval["g_mean"].copy())
        records["event_counts16"].append(interval["event_counts16"].copy())
        records["control_interval_duration_s"].append(control_dt)
        control_interval_index += 1

    arrays = {key: np.asarray(value) for key, value in records.items()}
    arrays["initial_state30"] = initial_state30
    finite = bool(all(np.all(np.isfinite(value)) for key, value in arrays.items() if key != "command_phase"))
    if not finite:
        status = "NONFINITE"
    if spec.distance_target_m is not None and crossing is None and status == "PASS":
        status = "DISTANCE_TARGET_NOT_REACHED"
    summary = {
        "status": status,
        "scenario": spec.scenario,
        "direction": spec.direction,
        "law": law,
        "seed": int(seed),
        "sample_count": int(len(arrays["time_s"])),
        "duration_s": float(time_s),
        "distance_m": float(distance_m),
        "distance_target_m": spec.distance_target_m,
        "distance_overshoot_m": (
            float(max(distance_m - float(spec.distance_target_m), 0.0))
            if spec.distance_target_m is not None
            else None
        ),
        "first_distance_crossing": crossing,
        "finite": finite,
        "event_count": int(event_count),
        "force_peak_n": force_peak_n,
        "rated_force_exceeded": rated_force_exceeded,
        "ultimate_force_exceeded": ultimate_force_exceeded,
        "tire_raw_utilization_max": tire_raw_utilization_max,
        "action_reaction_max_n": action_reaction_max_n,
        "internal_null_max_n": internal_null_max_n,
        "internal_force_peak_n": internal_force_peak_n,
        "icr_residual_max_mps": icr_residual_max_mps,
        "steering_clipped_fraction": steering_clip_count / max(steering_total_count, 1),
        "runtime_s": time.perf_counter() - started,
        "trajectory_array_sha256": array_sha256(arrays),
        "control_sha256": array_sha256({"control4x2": arrays["control4x2"]}),
        "initial_state_sha256": array_sha256({"initial_state30": initial_state30}),
        "params_sha256": params_sha256(params),
        "params_json": canonical_json(canonical_params(params)),
    }
    return summary, arrays


def save_raw(path: Path, arrays: dict[str, np.ndarray], summary: dict, params: object) -> None:
    meta_path = path.with_suffix(".meta.json")
    if path.exists() or meta_path.exists():
        raise FileExistsError(f"refuse to overwrite existing raw trajectory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        **arrays,
        params_json=np.asarray(canonical_json(canonical_params(params))),
        params_sha256=np.asarray(params_sha256(params)),
    )
    meta = dict(summary)
    meta["raw_path"] = str(path)
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )

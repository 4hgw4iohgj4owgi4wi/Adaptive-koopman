"""T6-T7 ablation and applicability scans for the 100 m maneuver."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from four_vehicle_coupled import ModelParams, aggregate_diagnostics, initialize_state, rk4_step, split_state
from steering_allocator import AllocationConfig, allocate_controls


def direct_controls(accel: float, front_deg: float, rear_deg: float) -> np.ndarray:
    u = np.zeros((4, 2), dtype=float)
    u[:, 0] = accel
    u[:2, 1] = np.deg2rad(front_deg)
    u[2:, 1] = np.deg2rad(rear_deg)
    return u


def run_case(
    name: str,
    params: ModelParams,
    allocation_mode: str = "full",
    steering_scale: float = 1.0,
    dt: float = 0.002,
    max_time_s: float = 60.0,
) -> dict:
    state = initialize_state(params, speed_mps=2.0)
    t = 0.0
    distance = 0.0
    turn_start = None
    decel = None
    peak_force = 0.0
    peak_system_yaw = 0.0
    peak_vehicle_yaw = 0.0
    peak_tire = 0.0
    peak_q_fr = 0.0
    peak_q_lr = 0.0
    max_icr_residual = 0.0
    max_internal_residual = 0.0
    stage_fy = {"step_positive": [], "step_negative": []}
    stage_distance = {}

    configs = {
        "full": AllocationConfig(),
        "feedforward_only": AllocationConfig(heading_gain=0.0, speed_gain=0.0),
        "heading_only": AllocationConfig(speed_gain=0.0),
        "speed_only": AllocationConfig(heading_gain=0.0),
    }

    while distance < 100.0 and t < max_time_s:
        vehicles, payload = split_state(state)
        payload_speed = float(np.linalg.norm(payload[3:5]))
        if distance < 30.0:
            stage = "accelerate"
            accel, front, rear = 0.5, 0.0, 0.0
        else:
            if turn_start is None:
                turn_start = t
            elapsed = t - turn_start
            if elapsed < 5.0:
                stage = "step_positive"
                accel, front, rear = 0.0, 4.0 * steering_scale, -2.0 * steering_scale
            elif elapsed < 10.0:
                stage = "step_negative"
                accel, front, rear = 0.0, -4.0 * steering_scale, 2.0 * steering_scale
            else:
                stage = "decelerate"
                front, rear = 0.0, 0.0
                if decel is None:
                    remaining = max(100.0 - distance, 0.5)
                    decel = float(np.clip(-payload_speed**2 / (2.0 * remaining), -2.0, -0.1))
                accel = decel
        stage_distance.setdefault(stage, [distance, distance])
        stage_distance[stage][1] = distance

        if allocation_mode == "direct_copy":
            controls = direct_controls(accel, front, rear)
            allocation = {"normal_velocity_residual_mps": np.full(4, np.nan)}
        else:
            controls, allocation = allocate_controls(
                state,
                accel,
                front,
                rear,
                params,
                config=configs[allocation_mode],
            )
            residual = np.asarray(allocation["normal_velocity_residual_mps"], dtype=float)
            max_icr_residual = max(max_icr_residual, float(np.max(np.abs(residual))))

        diag = aggregate_diagnostics(state, controls, params)
        conn = diag["connectors"]
        peak_force = max(peak_force, float(np.max(conn["force_norm_n"])))
        peak_system_yaw = max(peak_system_yaw, abs(float(diag["system_yaw_rate_radps"])))
        peak_vehicle_yaw = max(peak_vehicle_yaw, float(np.max(np.abs(vehicles[:, 5]))))
        peak_tire = max(peak_tire, float(np.max(diag["tire_utilization"])))
        peak_q_fr = max(peak_q_fr, float(diag["q_front_rear_n"]))
        peak_q_lr = max(peak_q_lr, float(diag["q_left_right_n"]))
        max_internal_residual = max(
            max_internal_residual,
            float(np.linalg.norm(diag["internal_force_residual_n"])),
        )
        if stage in stage_fy:
            stage_fy[stage].append(float(np.sum(conn["force_payload_body_n"][:, 1])))

        next_state = rk4_step(state, controls, dt, params)
        _, next_payload = split_state(next_state)
        next_speed = float(np.linalg.norm(next_payload[3:5]))
        distance += 0.5 * (payload_speed + next_speed) * dt
        state = next_state
        t += dt
        if not np.all(np.isfinite(state)):
            break

    _, payload = split_state(state)
    positive_mean = float(np.mean(stage_fy["step_positive"])) if stage_fy["step_positive"] else np.nan
    negative_mean = float(np.mean(stage_fy["step_negative"])) if stage_fy["step_negative"] else np.nan
    return {
        "name": name,
        "allocation_mode": allocation_mode,
        "steering_scale": steering_scale,
        "completed": bool(distance >= 99.9),
        "finite": bool(np.all(np.isfinite(state))),
        "time_s": t,
        "distance_m": distance,
        "final_speed_mps": float(np.linalg.norm(payload[3:5])),
        "peak_connector_force_n": peak_force,
        "peak_system_yaw_rate_radps": peak_system_yaw,
        "peak_vehicle_yaw_rate_radps": peak_vehicle_yaw,
        "peak_tire_utilization": peak_tire,
        "peak_q_front_rear_n": peak_q_fr,
        "peak_q_left_right_n": peak_q_lr,
        "positive_step_mean_fy_n": positive_mean,
        "negative_step_mean_fy_n": negative_mean,
        "opposite_step_fy_sign": bool(positive_mean * negative_mean < 0.0),
        "max_icr_normal_residual_mps": max_icr_residual,
        "max_internal_force_residual_n": max_internal_residual,
        "reference_rated_exceeded": bool(peak_force >= params.connector.rated_force_n),
        "reference_ultimate_exceeded": bool(peak_force >= params.connector.ultimate_force_n),
        "stage_distance_m": stage_distance,
        "parameters": {
            "stiffness_npm": params.connector.stiffness_npm,
            "damping_nspm": params.connector.damping_nspm,
            "free_play_m": params.connector.free_play_m,
            "payload_mass_kg": params.payload.mass_kg,
            "vehicle_anchor_body_m": params.vehicle_anchor_body_m,
        },
    }


def build_cases() -> list[tuple[str, ModelParams, str, float]]:
    base = ModelParams()
    cases = [
        ("full", base, "full", 1.0),
        ("feedforward_only", base, "feedforward_only", 1.0),
        ("heading_only", base, "heading_only", 1.0),
        ("speed_only", base, "speed_only", 1.0),
        ("direct_copy_negative_control", base, "direct_copy", 1.0),
        ("k_half", replace(base, connector=replace(base.connector, stiffness_npm=15000.0)), "full", 1.0),
        ("k_double", replace(base, connector=replace(base.connector, stiffness_npm=60000.0)), "full", 1.0),
        ("c_half", replace(base, connector=replace(base.connector, damping_nspm=1750.0)), "full", 1.0),
        ("c_double", replace(base, connector=replace(base.connector, damping_nspm=7000.0)), "full", 1.0),
        ("gap_half", replace(base, connector=replace(base.connector, free_play_m=0.001)), "full", 1.0),
        ("gap_large", replace(base, connector=replace(base.connector, free_play_m=0.005)), "full", 1.0),
        ("payload_half", replace(base, payload=replace(base.payload, mass_kg=1000.0)), "full", 1.0),
        ("payload_1p5", replace(base, payload=replace(base.payload, mass_kg=3000.0)), "full", 1.0),
    ]
    anchors = np.asarray(base.vehicle_anchor_body_m, dtype=float)
    for scale in (0.0, 0.5, 1.5):
        cases.append((f"anchor_{scale:g}", replace(base, vehicle_anchor_body_m=tuple(map(tuple, anchors * scale))), "full", 1.0))
    for angle_scale in (0.125, 0.25, 0.5):
        cases.append((f"steer_{4.0*angle_scale:g}deg", base, "full", angle_scale))
    return cases


def plot(cases: list[dict], output: Path) -> None:
    names = [c["name"] for c in cases]
    force = [c["peak_connector_force_n"] / 1000.0 for c in cases]
    yaw = [c["peak_system_yaw_rate_radps"] for c in cases]
    distance = [min(c["distance_m"], 110.0) for c in cases]
    x = np.arange(len(cases))
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    axes[0].bar(x, force); axes[0].axhline(12.0, color="red", linestyle="--", label="reference rated")
    axes[0].set_ylabel("Peak connector [kN]"); axes[0].legend(); axes[0].grid(True, axis="y", alpha=0.3)
    axes[1].bar(x, yaw); axes[1].set_ylabel("Peak system yaw [rad/s]"); axes[1].grid(True, axis="y", alpha=0.3)
    axes[2].bar(x, distance); axes[2].axhline(100.0, color="black", linestyle="--")
    axes[2].set_ylabel("Distance [m]"); axes[2].set_xticks(x, names, rotation=55, ha="right")
    axes[2].grid(True, axis="y", alpha=0.3)
    fig.suptitle("100 m allocation ablation and parameter applicability scan")
    fig.tight_layout(); fig.savefig(output / "compare.png", dpi=180); plt.close(fig)


def main() -> None:
    output = Path(__file__).resolve().parent / "scan"
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name, params, mode, scale in build_cases():
        result = run_case(name, params, mode, scale)
        results.append(result)
        print(name, result["completed"], f"distance={result['distance_m']:.3f}", f"force={result['peak_connector_force_n']:.1f}")
    full = next(item for item in results if item["name"] == "full")
    acceptance = {
        "full_completed": full["completed"],
        "full_force_below_reference_rated": not full["reference_rated_exceeded"],
        "full_direction_reversal": full["opposite_step_fy_sign"],
        "full_internal_force_closure": full["max_internal_force_residual_n"] <= 1.0e-9,
    }
    report = {
        "passed": all(acceptance.values()),
        "acceptance": acceptance,
        "negative_control_expected_to_fail": "direct_copy_negative_control",
        "cases": results,
    }
    (output / "scan.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    plot(results, output)
    print(json.dumps({"passed": report["passed"], "acceptance": acceptance}, indent=2))


if __name__ == "__main__":
    main()

"""Generate labelled coupled-plant trajectories for Koopman K2.

The generator keeps the accepted common-ICR allocator and 30-state physical
plant.  Splits are assigned by whole trajectory before any model fitting.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "revision_2026" / "model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from four_vehicle_coupled import (  # noqa: E402
    ConnectorParams,
    ModelParams,
    PayloadParams,
    VehicleParams,
    aggregate_diagnostics,
    connector_diagnostics,
    initialize_state,
    rk4_step,
    rotation,
    split_state,
)
from steering_allocator import AllocationConfig, allocate_controls  # noqa: E402


CONTROL_DT = 0.02
PLANT_DT = 0.002
SUBSTEPS = int(round(CONTROL_DT / PLANT_DT))
BASE_SCENARIOS = (
    "staged_100m",
    "single_lane_change",
    "hairpin",
    "connector_directional",
    "network_excitation",
)
NAMES = ("FL", "FR", "RL", "RR")


def json_default(value: Any):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return str(value)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def split_for(traj_id: int) -> str:
    slot = int(traj_id) % 20
    if slot <= 13:
        return "train"
    if slot <= 16:
        return "validation"
    return "test"


def smooth_step(t: float, begin: float, end: float) -> float:
    if t <= begin:
        return 0.0
    if t >= end:
        return 1.0
    x = (t - begin) / max(end - begin, 1.0e-12)
    return float(x * x * (3.0 - 2.0 * x))


def parameter_sample(rng: np.random.Generator, external: bool) -> tuple[ModelParams, dict[str, float]]:
    if not external:
        mass_scale = float(rng.uniform(0.97, 1.03))
        stiffness_scale = float(rng.uniform(0.92, 1.08))
        damping_scale = float(rng.uniform(0.92, 1.08))
        free_play_scale = float(rng.uniform(0.92, 1.08))
        mu_scale = float(rng.uniform(0.96, 1.04))
    else:
        # External set is deliberately outside every in-distribution interval.
        mass_scale = float(rng.choice([0.82, 1.20]))
        stiffness_scale = float(rng.choice([0.68, 1.32]))
        damping_scale = float(rng.choice([0.62, 1.42]))
        free_play_scale = float(rng.choice([0.55, 1.75]))
        mu_scale = float(rng.choice([0.72, 1.12]))
    params = ModelParams(
        vehicle=replace(VehicleParams(), mu=VehicleParams().mu * mu_scale),
        payload=replace(PayloadParams(), mass_kg=PayloadParams().mass_kg * mass_scale),
        connector=replace(
            ConnectorParams(),
            stiffness_npm=ConnectorParams().stiffness_npm * stiffness_scale,
            damping_nspm=ConnectorParams().damping_nspm * damping_scale,
            free_play_m=ConnectorParams().free_play_m * free_play_scale,
        ),
    )
    scales = {
        "payload_mass_scale": mass_scale,
        "connector_stiffness_scale": stiffness_scale,
        "connector_damping_scale": damping_scale,
        "connector_free_play_scale": free_play_scale,
        "vehicle_mu_scale": mu_scale,
    }
    return params, scales


def target_speed_accel(speed: float, target: float, feedforward: float = 0.0) -> float:
    return float(np.clip(0.62 * (target - speed) + feedforward, -1.4, 1.2))


def nominal_command(
    scenario: str,
    t: float,
    distance: float,
    payload_speed: float,
    phase: float,
    sign: float,
    staged_turn_start: float | None,
) -> tuple[float, float, float]:
    if scenario == "staged_100m":
        if distance < 30.0:
            return 0.50 + 0.04 * math.sin(0.45 * t + phase), 0.0, 0.0
        tau = t - float(staged_turn_start if staged_turn_start is not None else t)
        if tau < 5.0:
            return target_speed_accel(payload_speed, 4.0), 4.0 * sign, -2.0 * sign
        if tau < 10.0:
            return target_speed_accel(payload_speed, 4.0), -4.0 * sign, 2.0 * sign
        return target_speed_accel(payload_speed, 0.7, feedforward=-0.15), 0.0, 0.0

    if scenario == "single_lane_change":
        accel = target_speed_accel(payload_speed, 2.8, 0.05 * math.sin(0.6 * t + phase))
        if 4.0 <= t < 8.0:
            angle = 3.0 * sign * math.sin(math.pi * (t - 4.0) / 4.0)
        elif 8.0 <= t < 12.0:
            angle = -3.0 * sign * math.sin(math.pi * (t - 8.0) / 4.0)
        else:
            angle = 0.0
        return accel, angle, -0.5 * angle

    if scenario == "hairpin":
        accel = target_speed_accel(payload_speed, 1.15, 0.025 * math.sin(0.35 * t + phase))
        up = smooth_step(t, 4.0, 7.0)
        down = 1.0 - smooth_step(t, 39.0, 43.0)
        gate = up * down
        return accel, 10.0 * sign * gate, -7.0 * sign * gate

    if scenario == "connector_directional":
        accel = target_speed_accel(payload_speed, 2.2, 0.12 * math.sin(0.8 * t + phase))
        angle = 1.3 * sign * math.sin(0.42 * t + phase)
        if 7.0 < t < 12.0:
            angle += 1.2 * sign
        return accel, angle, -0.55 * angle

    if scenario == "network_excitation":
        accel = target_speed_accel(payload_speed, 2.5, 0.08 * math.sin(0.55 * t + phase))
        if 3.0 <= t < 8.0:
            angle = 3.2 * sign * math.sin(math.pi * (t - 3.0) / 5.0)
        elif 9.0 <= t < 14.0:
            angle = -3.2 * sign * math.sin(math.pi * (t - 9.0) / 5.0)
        else:
            angle = 0.0
        return accel, angle, -0.5 * angle

    raise KeyError(scenario)


def equivalent_team_input(accel: float, front_deg: float, rear_deg: float, params: ModelParams) -> np.ndarray:
    curvature = (math.tan(math.radians(front_deg)) - math.tan(math.radians(rear_deg))) / params.payload.length_m
    wheelbase = params.vehicle.lf_m + params.vehicle.lr_m
    equivalent_steer = math.atan(wheelbase * curvature)
    return np.array([accel, equivalent_steer], dtype=float)


def feature_rows(state: np.ndarray, force_prev: np.ndarray | None, dt: float, params: ModelParams) -> dict[str, np.ndarray]:
    vehicles, payload = split_state(state)
    conn = connector_diagnostics(state, params)
    rp = rotation(payload[2])
    displacement_body = np.asarray(conn["displacement_world_m"], dtype=float) @ rp
    payload_anchor_velocity = np.empty((4, 2), dtype=float)
    vehicle_anchor_velocity = np.empty((4, 2), dtype=float)
    payload_center_velocity = rp @ payload[3:5]
    for i in range(4):
        payload_arm = rp @ params.payload_anchor_body_m[i]
        payload_anchor_velocity[i] = payload_center_velocity + payload[5] * np.array(
            [-payload_arm[1], payload_arm[0]]
        )
        rv = rotation(vehicles[i, 2])
        vehicle_arm = rv @ np.asarray(params.vehicle_anchor_body_m[i], dtype=float)
        vehicle_anchor_velocity[i] = rv @ vehicles[i, 3:5] + vehicles[i, 5] * np.array(
            [-vehicle_arm[1], vehicle_arm[0]]
        )
    rel_velocity_body = (vehicle_anchor_velocity - payload_anchor_velocity) @ rp
    force_body = np.asarray(conn["force_payload_body_n"], dtype=float)
    force_rate = np.zeros_like(force_body) if force_prev is None else (force_body - force_prev) / dt
    q_fr = 0.5 * ((force_body[0, 0] + force_body[1, 0]) - (force_body[2, 0] + force_body[3, 0]))
    q_lr = 0.5 * ((force_body[0, 1] + force_body[2, 1]) - (force_body[1, 1] + force_body[3, 1]))
    yaw_mean = math.atan2(float(np.mean(np.sin(vehicles[:, 2]))), float(np.mean(np.cos(vehicles[:, 2]))))
    aggregate_vehicle = np.array(
        [
            float(np.mean(vehicles[:, 0])),
            float(np.mean(vehicles[:, 1])),
            yaw_mean,
            float(np.mean(vehicles[:, 3])),
            float(np.mean(vehicles[:, 4])),
            float(np.mean(vehicles[:, 5])),
        ],
        dtype=float,
    )
    s1 = np.r_[payload, aggregate_vehicle]
    s2 = np.asarray(state, dtype=float).copy()
    s3 = np.r_[s2, displacement_body.reshape(-1), rel_velocity_body.reshape(-1)]
    force_output = np.r_[force_body.reshape(-1), q_fr, q_lr, force_rate.reshape(-1)]
    s4 = np.r_[s3, force_output]
    return {
        "s1_team": s1,
        "s2_four": s2,
        "s3_deform": s3,
        "s4_force_in": s4,
        "force_output": force_output,
        "force_body": force_body,
        "force_rate": force_rate,
        "q": np.array([q_fr, q_lr], dtype=float),
        "displacement_body": displacement_body,
        "relative_velocity_body": rel_velocity_body,
    }


def scenario_duration(scenario: str) -> float:
    return {
        # Hard ceiling only.  The trajectory exits as soon as the integrated
        # payload travel reaches 100 m; slower parameter draws must not be
        # silently accepted as a "100 m" experiment.
        "staged_100m": 90.0,
        "single_lane_change": 22.0,
        "hairpin": 44.0,
        "connector_directional": 20.0,
        "network_excitation": 22.0,
    }[scenario]


def simulate(scenario: str, traj_id: int, seed: int, external: bool) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    rng = np.random.default_rng(seed)
    params, scales = parameter_sample(rng, external=external)
    phase = float(rng.uniform(0.0, 2.0 * math.pi))
    sign = float(rng.choice([-1.0, 1.0]))
    initial_speed = {
        "staged_100m": 2.0,
        "single_lane_change": 2.0,
        "hairpin": 1.0,
        "connector_directional": 1.8,
        "network_excitation": 1.9,
    }[scenario] * float(rng.uniform(0.96, 1.04))
    state = initialize_state(params, speed_mps=initial_speed)
    vehicles, payload = split_state(state)
    vehicles[:, 3] += rng.normal(0.0, 0.015, size=4)
    vehicles[:, 4] += rng.normal(0.0, 0.004, size=4)
    state[:24] = vehicles.reshape(-1)

    alloc_cfg = AllocationConfig(max_steering_deg=15.0)
    max_steps = int(round(scenario_duration(scenario) / CONTROL_DT))
    staged_turn_start = None
    distance = 0.0
    nominal_history: list[tuple[float, float, float]] = []
    last_delivered: tuple[float, float, float] | None = None
    aoi = 0
    state_rows: dict[str, list[np.ndarray]] = {
        "s1_team": [],
        "s2_four": [],
        "s3_deform": [],
        "s4_force_in": [],
        "force_output": [],
        "force_body": [],
        "force_rate": [],
        "q": [],
        "displacement_body": [],
        "relative_velocity_body": [],
    }
    applied_controls: list[np.ndarray] = []
    commanded_controls: list[np.ndarray] = []
    u_team: list[np.ndarray] = []
    u_alloc: list[np.ndarray] = []
    network_rows: list[np.ndarray] = []
    icr_residual: list[float] = []
    force_prev: np.ndarray | None = None
    max_force = 0.0
    max_opening = 0.0
    max_tire = 0.0
    rated_steps = 0
    ultimate_steps = 0

    for k in range(max_steps):
        t = k * CONTROL_DT
        vehicles, payload = split_state(state)
        payload_speed = float(np.linalg.norm(payload[3:5]))
        if scenario == "staged_100m" and distance >= 30.0 and staged_turn_start is None:
            staged_turn_start = t
        nominal = nominal_command(scenario, t, distance, payload_speed, phase, sign, staged_turn_start)
        nominal_history.append(nominal)
        drop = 0
        delay = 0
        if scenario == "network_excitation":
            delay = int(rng.integers(1, 4))
            drop = int(rng.random() < 0.10 or (8.0 <= t < 8.6))
            if drop and last_delivered is not None:
                delivered = last_delivered
                aoi += 1
            else:
                delivered = nominal_history[max(0, len(nominal_history) - 1 - delay)]
                last_delivered = delivered
                aoi = delay
        else:
            delivered = nominal
            last_delivered = delivered
            aoi = 0
        accel, front_deg, rear_deg = delivered
        controls, allocation = allocate_controls(state, accel, front_deg, rear_deg, params, alloc_cfg)
        cmd_controls, _ = allocate_controls(state, nominal[0], nominal[1], nominal[2], params, alloc_cfg)
        if scenario == "connector_directional":
            extra_a = (0.16 + 0.02 * math.sin(0.17 * t + phase)) * math.sin(1.05 * t + phase)
            extra_d = math.radians(0.28) * math.sin(0.83 * t + 0.5 * phase)
            controls[:, 0] += extra_a * np.array([1.0, -1.0, -1.0, 1.0])
            controls[:, 1] += extra_d * np.array([1.0, -1.0, 1.0, -1.0])
            controls[:, 1] = np.clip(controls[:, 1], -math.radians(15.0), math.radians(15.0))

        obs = feature_rows(state, force_prev, CONTROL_DT, params)
        for key in state_rows:
            state_rows[key].append(obs[key])
        force_prev = obs["force_body"].copy()
        applied_controls.append(controls.copy())
        commanded_controls.append(cmd_controls.copy())
        u_team.append(equivalent_team_input(accel, front_deg, rear_deg, params))
        u_alloc.append(
            np.array(
                [
                    math.radians(front_deg),
                    math.radians(rear_deg),
                    float(allocation["yaw_rate_radps"]),
                    float(np.nan_to_num(allocation["icr_payload_body_m"][0], nan=0.0, posinf=0.0, neginf=0.0)),
                    float(np.nan_to_num(allocation["icr_payload_body_m"][1], nan=0.0, posinf=0.0, neginf=0.0)),
                ]
            )
        )
        network_rows.append(np.array([drop, delay, aoi, 1.0 - min(aoi / 10.0, 1.0)], dtype=float))
        icr_residual.append(float(np.max(np.abs(allocation["normal_velocity_residual_mps"]))))
        full_diag = aggregate_diagnostics(state, controls, params)
        force_norm = np.asarray(full_diag["connectors"]["force_norm_n"], dtype=float)
        max_force = max(max_force, float(np.max(force_norm)))
        max_opening = max(max_opening, float(np.max(np.abs(obs["q"]))))
        max_tire = max(max_tire, float(np.max(full_diag["tire_utilization"])))
        rated_steps += int(np.any(force_norm >= params.connector.rated_force_n))
        ultimate_steps += int(np.any(force_norm >= params.connector.ultimate_force_n))

        previous_speed = payload_speed
        for _ in range(SUBSTEPS):
            state = rk4_step(state, controls, PLANT_DT, params)
        _, next_payload = split_state(state)
        next_speed = float(np.linalg.norm(next_payload[3:5]))
        distance += 0.5 * (previous_speed + next_speed) * CONTROL_DT
        if not np.all(np.isfinite(state)):
            raise FloatingPointError(f"non-finite state in {scenario}/{traj_id} at step {k}")
        if scenario == "staged_100m" and distance >= 100.0:
            break

    final_obs = feature_rows(state, force_prev, CONTROL_DT, params)
    for key in state_rows:
        state_rows[key].append(final_obs[key])
    arrays = {key: np.asarray(value, dtype=np.float32) for key, value in state_rows.items()}
    arrays.update(
        {
            "u1_four": np.asarray(applied_controls, dtype=np.float32).reshape(-1, 8),
            "u2_commanded": np.asarray(commanded_controls, dtype=np.float32).reshape(-1, 8),
            "u0_team": np.asarray(u_team, dtype=np.float32),
            "u3_alloc": np.column_stack(
                [np.asarray(applied_controls, dtype=np.float32).reshape(-1, 8), np.asarray(u_alloc, dtype=np.float32)]
            ),
            "network": np.asarray(network_rows, dtype=np.float32),
            "icr_residual": np.asarray(icr_residual, dtype=np.float32),
            "time_s": np.arange(len(applied_controls) + 1, dtype=np.float32) * CONTROL_DT,
        }
    )
    metadata = {
        "scenario": scenario,
        "traj_id": int(traj_id),
        "seed": int(seed),
        "split": "external" if external else split_for(traj_id),
        "external": bool(external),
        "network_trace_id": f"{scenario}_seed_{seed}" if scenario == "network_excitation" else "clean",
        "steps": int(len(applied_controls)),
        "duration_s": float(len(applied_controls) * CONTROL_DT),
        "distance_m": float(distance),
        "distance_gate_passed": bool(scenario != "staged_100m" or distance >= 100.0),
        "control_dt_s": CONTROL_DT,
        "plant_dt_s": PLANT_DT,
        "substeps": SUBSTEPS,
        "initial_speed_mps": float(initial_speed),
        "turn_sign": sign,
        "parameter_scales": scales,
        "params": {
            "vehicle": asdict(params.vehicle),
            "payload": asdict(params.payload),
            "connector": asdict(params.connector),
        },
        "max_connector_force_n": max_force,
        "max_opening_n": max_opening,
        "max_tire_utilization": max_tire,
        "rated_exceeded_steps": rated_steps,
        "ultimate_exceeded_steps": ultimate_steps,
        "icr_residual_peak_mps": float(np.max(arrays["icr_residual"])) if arrays["icr_residual"].size else 0.0,
        "finite": bool(all(np.all(np.isfinite(v)) for v in arrays.values())),
    }
    return arrays, metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-scenario", type=int, default=20)
    parser.add_argument("--external", type=int, default=20)
    parser.add_argument("--tag", default="full")
    args = parser.parse_args()

    out = Path(__file__).resolve().parent / "k2" / f"data_{args.tag}"
    traj_dir = out / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    jobs: list[tuple[str, int, bool]] = []
    for scenario in BASE_SCENARIOS:
        jobs.extend((scenario, traj_id, False) for traj_id in range(args.per_scenario))
    for ext_id in range(args.external):
        jobs.append((BASE_SCENARIOS[ext_id % len(BASE_SCENARIOS)], ext_id, True))

    for job_index, (scenario, traj_id, external) in enumerate(jobs):
        seed = 52000 + BASE_SCENARIOS.index(scenario) * 1000 + traj_id + (9000 if external else 0)
        key = f"{'external' if external else split_for(traj_id)}_{scenario}_{traj_id:03d}"
        path = traj_dir / f"{key}.npz"
        try:
            arrays, metadata = simulate(scenario, traj_id, seed, external)
            np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
            metadata["file"] = str(path.relative_to(out))
            metadata["sha256"] = sha256(path)
            manifest.append(metadata)
            print(
                f"[{job_index + 1}/{len(jobs)}] {key} steps={metadata['steps']} "
                f"force={metadata['max_connector_force_n']:.1f}N opening={metadata['max_opening_n']:.1f}N",
                flush=True,
            )
            if (
                not metadata["finite"]
                or not metadata["distance_gate_passed"]
                or (not external and metadata["ultimate_exceeded_steps"] > 0)
            ):
                failures.append(metadata)
                break
        except Exception as exc:
            failures.append({"key": key, "error": repr(exc)})
            print(f"FAILED {key}: {exc!r}", flush=True)
            break

    fieldnames = sorted({key for row in manifest for key in row if key not in {"params", "parameter_scales"}})
    with (out / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest:
            writer.writerow({key: row.get(key) for key in fieldnames})
    summary = {
        "stage": "K2.0_coupled_dataset",
        "tag": args.tag,
        "planned_jobs": len(jobs),
        "completed_jobs": len(manifest),
        "failures": failures,
        "accepted": bool(len(manifest) == len(jobs) and not failures),
        "split_counts": {
            split: sum(1 for row in manifest if row["split"] == split)
            for split in ("train", "validation", "test", "external")
        },
        "scenario_counts": {scenario: sum(1 for row in manifest if row["scenario"] == scenario) for scenario in BASE_SCENARIOS},
        "max_connector_force_n": max((row["max_connector_force_n"] for row in manifest), default=math.nan),
        "max_opening_n": max((row["max_opening_n"] for row in manifest), default=math.nan),
        "max_icr_residual_mps": max((row["icr_residual_peak_mps"] for row in manifest), default=math.nan),
        "contract": {
            "S1_team_dim": 12,
            "S2_four_dim": 30,
            "S3_deform_dim": 46,
            "S4_force_in_dim": 64,
            "force_output_dim": 18,
            "U0_team_dim": 2,
            "U1_four_dim": 8,
            "U2_commanded_dim": 8,
            "U3_alloc_dim": 13,
            "force_output_order": ["Fx/Fy for FL,FR,RL,RR", "Q_FR", "Q_LR", "causal dFx/dt,dFy/dt for FL,FR,RL,RR"],
            "network_order": ["drop", "delay_steps", "AoI_steps", "quality"],
        },
    }
    write_json(out / "manifest.json", {"summary": summary, "trajectories": manifest})
    write_json(out / "split.json", {
        "frozen_before_training": True,
        "assignment": "within every base scenario traj_id modulo 20: 0-13 train, 14-16 validation, 17-19 test",
        "external": "separate out-of-range parameter trajectories; never used for normalization or tuning",
        "window_rule": "windows may not cross trajectory or split boundaries",
    })
    if failures:
        lines = [
            "# K2数据生成停止",
            "",
            "生成过程中出现数值非有限、100 m工况未跑满或基础分布连接力超过15 kN，已停止后续训练。",
            "",
            f"失败记录：`{json.dumps(failures, ensure_ascii=False, default=json_default)}`",
            "",
            "解决顺序：先复核对应场景命令、初始扰动和参数范围；不得通过删除异常轨迹或放宽15 kN门掩盖问题。",
        ]
        (out / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        raise SystemExit(2)
    print(json.dumps(summary, ensure_ascii=False, default=json_default), flush=True)


if __name__ == "__main__":
    main()

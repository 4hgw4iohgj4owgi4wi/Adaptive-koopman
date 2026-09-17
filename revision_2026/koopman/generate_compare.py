"""Generate only the preregistered E9 and one-shot confirmation trajectories.

This file imports the accepted coupled plant and feature contract from
``generate_k2.py``.  It does not modify the original 120-trajectory dataset.
Generation is resumable per trajectory and every completed file is hashed
before the progress manifest is updated.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import generate_k2 as base  # noqa: E402


DT = base.CONTROL_DT
SUBSTEPS = base.SUBSTEPS
PLANT_DT = base.PLANT_DT
PHYSICAL = ("E0", "E1", "E2", "E3", "E4", "E5", "E6")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=base.json_default) + "\n", encoding="utf-8")


def smooth_gate(t: float, begin: float, full: float, leave: float, end: float) -> float:
    return base.smooth_step(t, begin, full) * (1.0 - base.smooth_step(t, leave, end))


def physical_command(scene: str, t: float, speed: float, phase: float, sign: float) -> tuple[float, float, float]:
    """Return longitudinal acceleration and front/rear payload steering commands."""
    if scene == "E0":
        return base.target_speed_accel(speed, 2.5), 0.0, 0.0
    if scene == "E1":
        if t < 6.0:
            return base.target_speed_accel(speed, 4.0, 0.35), 0.0, 0.0
        if t < 14.0:
            return base.target_speed_accel(speed, 4.0), 0.0, 0.0
        return base.target_speed_accel(speed, 0.8, -0.30), 0.0, 0.0
    if scene == "E2":
        gate = smooth_gate(t, 3.0, 5.0, 17.0, 20.0)
        angle = 6.0 * sign * gate
        return base.target_speed_accel(speed, 2.0), angle, -0.65 * angle
    if scene == "E3":
        if 4.0 <= t < 9.0:
            angle = 5.0 * sign
        elif 9.0 <= t < 14.0:
            angle = -5.0 * sign
        else:
            angle = 0.0
        return base.target_speed_accel(speed, 2.5), angle, -0.55 * angle
    if scene == "E4":
        return base.nominal_command("single_lane_change", t, 0.0, speed, phase, sign, None)
    if scene == "E5":
        return base.nominal_command("hairpin", t, 0.0, speed, phase, sign, None)
    if scene == "E6":
        return base.nominal_command("connector_directional", t, 0.0, speed, phase, sign, None)
    raise KeyError(scene)


def duration(scene: str) -> float:
    return {"E0": 16.0, "E1": 22.0, "E2": 22.0, "E3": 19.0, "E4": 22.0, "E5": 44.0, "E6": 20.0, "E9": 24.0}[scene]


def e9_excitation(t: float, phase: float, scales: dict[str, np.ndarray]) -> tuple[float, float, float, np.ndarray]:
    # Frequencies are fixed before data generation.  The alternating sign term
    # is a deterministic PRBS-like component; amplitudes come only from the
    # original 70 train trajectories and are recorded in config.json.
    w = np.array([0.17, 0.43, 0.91, 1.37], dtype=float)
    s = np.sign(np.sin(2.0 * math.pi * np.array([0.13, 0.19, 0.29, 0.37]) * t + phase))
    amp = np.asarray(scales["longitudinal_amplitude"], dtype=float)
    modal = amp * (0.70 * np.sin(2.0 * math.pi * w * t + phase + np.arange(4)) + 0.30 * s)
    common, fr, lr, diag = modal
    accel = float(common)
    diff = (
        fr * np.array([1.0, 1.0, -1.0, -1.0])
        + lr * np.array([1.0, -1.0, 1.0, -1.0])
        + diag * np.array([1.0, -1.0, -1.0, 1.0])
    )
    steer_amp = float(scales["steering_amplitude_rad"])
    steer_rad = steer_amp * (0.75 * math.sin(2.0 * math.pi * 0.23 * t + phase) + 0.25 * math.sin(2.0 * math.pi * 0.71 * t))
    front = math.degrees(steer_rad)
    rear = -0.60 * front
    return accel, front, rear, diff


def deliver_network(
    nominal_history: list[tuple[float, float, float]],
    last: tuple[float, float, float] | None,
    t: float,
    rng: np.random.Generator,
    profile: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float], int, int, int]:
    nominal = nominal_history[-1]
    delay = 0
    drop = 0
    if profile == "delay":
        delay = int(rng.integers(3, 9))
    elif profile == "dropout":
        delay = int(rng.integers(0, 4))
        drop = int(rng.random() < 0.25)
    elif profile == "burst":
        delay = int(rng.integers(1, 6))
        drop = int((6.0 <= t < 7.5) or (13.0 <= t < 14.0) or rng.random() < 0.08)
    elif profile == "dos":
        delay = int(rng.integers(2, 7))
        drop = int(7.0 <= t < 11.0)
    if drop and last is not None:
        delivered = last
        aoi = 1
        # Consecutive AoI is reconstructed by the caller from the previous row.
    else:
        delivered = nominal_history[max(0, len(nominal_history) - 1 - delay)]
        last = delivered
        aoi = delay
    return delivered, last if last is not None else delivered, drop, delay, aoi


def simulate(job: dict[str, Any], e9_scales: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    seed = int(job["seed"])
    rng = np.random.default_rng(seed)
    parameter_external = bool(job.get("parameter_external", False))
    params, parameter_scales = base.parameter_sample(rng, external=parameter_external)
    phase = float(rng.uniform(0.0, 2.0 * math.pi))
    sign = float(rng.choice([-1.0, 1.0]))
    scene = str(job["physical_scene"])
    initial_base = {"E0": 2.4, "E1": 1.0, "E2": 1.8, "E3": 2.2, "E4": 2.0, "E5": 1.0, "E6": 1.8, "E9": 2.0}[scene]
    state = base.initialize_state(params, speed_mps=initial_base * float(rng.uniform(0.96, 1.04)))
    vehicles, _ = base.split_state(state)
    vehicles[:, 3] += rng.normal(0.0, 0.015, size=4)
    vehicles[:, 4] += rng.normal(0.0, 0.004, size=4)
    state[:24] = vehicles.reshape(-1)

    alloc_cfg = base.AllocationConfig(max_steering_deg=15.0)
    keys = (
        "s1_team", "s2_four", "s3_deform", "s4_force_in", "force_output", "force_body",
        "force_rate", "q", "displacement_body", "relative_velocity_body",
    )
    state_rows: dict[str, list[np.ndarray]] = {key: [] for key in keys}
    applied: list[np.ndarray] = []
    commanded: list[np.ndarray] = []
    team: list[np.ndarray] = []
    alloc_rows: list[np.ndarray] = []
    network_rows: list[np.ndarray] = []
    icr_rows: list[float] = []
    nominal_history: list[tuple[float, float, float]] = []
    last_delivered: tuple[float, float, float] | None = None
    consecutive_aoi = 0
    force_prev: np.ndarray | None = None
    max_force = max_opening = max_tire = max_icr = 0.0
    rated_steps = ultimate_steps = 0
    profile = str(job.get("network_profile", "clean"))

    for k in range(int(round(duration(scene) / DT))):
        t = k * DT
        _, payload = base.split_state(state)
        speed = float(np.linalg.norm(payload[3:5]))
        diff = np.zeros(4, dtype=float)
        if scene == "E9":
            accel, front_deg, rear_deg, diff = e9_excitation(t, phase, e9_scales)
            accel += base.target_speed_accel(speed, 2.2)
        else:
            accel, front_deg, rear_deg = physical_command(scene, t, speed, phase, sign)
        nominal = (float(accel), float(front_deg), float(rear_deg))
        nominal_history.append(nominal)
        if profile == "clean":
            delivered = nominal
            last_delivered = delivered
            drop = delay = consecutive_aoi = 0
        else:
            delivered, last_delivered, drop, delay, local_aoi = deliver_network(
                nominal_history, last_delivered, t, rng, profile
            )
            consecutive_aoi = consecutive_aoi + 1 if drop else local_aoi
        controls, allocation = base.allocate_controls(state, *delivered, params, alloc_cfg)
        cmd_controls, _ = base.allocate_controls(state, *nominal, params, alloc_cfg)
        if scene == "E6":
            extra_a = (0.16 + 0.02 * math.sin(0.17 * t + phase)) * math.sin(1.05 * t + phase)
            extra_d = math.radians(0.28) * math.sin(0.83 * t + 0.5 * phase)
            controls[:, 0] += extra_a * np.array([1.0, -1.0, -1.0, 1.0])
            controls[:, 1] += extra_d * np.array([1.0, -1.0, 1.0, -1.0])
        if scene == "E9":
            controls[:, 0] += diff
        controls[:, 0] = np.clip(controls[:, 0], -1.4, 1.2)
        controls[:, 1] = np.clip(controls[:, 1], -math.radians(15.0), math.radians(15.0))

        obs = base.feature_rows(state, force_prev, DT, params)
        for key in keys:
            state_rows[key].append(obs[key])
        force_prev = obs["force_body"].copy()
        applied.append(controls.copy())
        commanded.append(cmd_controls.copy())
        team.append(base.equivalent_team_input(*delivered, params))
        alloc_rows.append(np.r_[
            controls.reshape(-1), math.radians(delivered[1]), math.radians(delivered[2]),
            float(allocation["yaw_rate_radps"]),
            np.nan_to_num(allocation["icr_payload_body_m"], nan=0.0, posinf=0.0, neginf=0.0),
        ])
        network_rows.append(np.array([drop, delay, consecutive_aoi, 1.0 - min(consecutive_aoi / 10.0, 1.0)]))
        icr = float(np.max(np.abs(allocation["normal_velocity_residual_mps"])))
        icr_rows.append(icr)
        max_icr = max(max_icr, icr)
        diag = base.aggregate_diagnostics(state, controls, params)
        force_norm = np.asarray(diag["connectors"]["force_norm_n"], dtype=float)
        max_force = max(max_force, float(force_norm.max()))
        max_opening = max(max_opening, float(np.max(np.abs(obs["q"]))))
        max_tire = max(max_tire, float(np.max(diag["tire_utilization"])))
        rated_steps += int(np.any(force_norm >= params.connector.rated_force_n))
        ultimate_steps += int(np.any(force_norm >= params.connector.ultimate_force_n))
        for _ in range(SUBSTEPS):
            state = base.rk4_step(state, controls, PLANT_DT, params)
        if not np.all(np.isfinite(state)):
            raise FloatingPointError(f"non-finite state at step {k}")
        if ultimate_steps:
            raise RuntimeError(f"ultimate connector force exceeded at step {k}")
        if max_icr > 1.0e-8:
            raise RuntimeError(f"common-ICR residual gate failed: {max_icr}")

    final_obs = base.feature_rows(state, force_prev, DT, params)
    for key in keys:
        state_rows[key].append(final_obs[key])
    arrays = {key: np.asarray(value, dtype=np.float32) for key, value in state_rows.items()}
    arrays.update({
        "u1_four": np.asarray(applied, dtype=np.float32).reshape(-1, 8),
        "u2_commanded": np.asarray(commanded, dtype=np.float32).reshape(-1, 8),
        "u0_team": np.asarray(team, dtype=np.float32),
        "u3_alloc": np.asarray(alloc_rows, dtype=np.float32),
        "network": np.asarray(network_rows, dtype=np.float32),
        "icr_residual": np.asarray(icr_rows, dtype=np.float32),
        "time_s": np.arange(len(applied) + 1, dtype=np.float32) * DT,
    })
    metadata = {
        **job,
        "steps": len(applied),
        "duration_s": len(applied) * DT,
        "control_dt_s": DT,
        "plant_dt_s": PLANT_DT,
        "parameter_scales": parameter_scales,
        "params": {"vehicle": asdict(params.vehicle), "payload": asdict(params.payload), "connector": asdict(params.connector)},
        "max_connector_force_n": max_force,
        "max_opening_n": max_opening,
        "max_tire_utilization": max_tire,
        "rated_exceeded_steps": rated_steps,
        "ultimate_exceeded_steps": ultimate_steps,
        "icr_residual_peak_mps": max_icr,
        "finite": bool(all(np.all(np.isfinite(value)) for value in arrays.values())),
    }
    return arrays, metadata


def train_scales(data_dir: Path) -> dict[str, Any]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    controls = []
    for row in manifest["trajectories"]:
        if row["split"] != "train":
            continue
        path = data_dir / row["file"]
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as source:
            controls.append(np.asarray(source["u1_four"], dtype=float))
    u = np.concatenate(controls)
    a = u[:, 0::2]
    d = u[:, 1::2]
    modes = np.column_stack([
        a.mean(1), (a[:, :2].mean(1) - a[:, 2:].mean(1)) / 2.0,
        (a[:, [0, 2]].mean(1) - a[:, [1, 3]].mean(1)) / 2.0,
        (a[:, 0] - a[:, 1] - a[:, 2] + a[:, 3]) / 4.0,
    ])
    nonzero = lambda v: np.abs(v)[np.abs(v) > 1.0e-8]
    q = [0.50, 0.80, 0.95]
    longitudinal = np.array([np.quantile(nonzero(modes[:, i]), q[(i + 1) % 3]) for i in range(4)])
    steer_mode = (d[:, 0] + d[:, 1] - d[:, 2] - d[:, 3]) / 4.0
    steering = float(np.quantile(nonzero(steer_mode), 0.80))
    # Keep deterministic multisine superposition within the already observed
    # train envelope.  This scales rather than invents a new acceptance limit.
    longitudinal = np.minimum(longitudinal, np.array([0.35, 0.18, 0.18, 0.16]))
    steering = min(steering, math.radians(5.0))
    return {
        "longitudinal_amplitude": longitudinal.tolist(),
        "steering_amplitude_rad": steering,
        "source_quantiles": q,
        "source": "original 70 train trajectories only",
    }


def jobs_for(kind: str) -> list[dict[str, Any]]:
    if kind == "e9":
        roles = ["train"] * 14 + ["validation"] * 3 + ["test"] * 3 + ["external"] * 4
        return [{
            "scenario": "E9", "physical_scene": "E9", "traj_id": i, "seed": 83000 + i,
            "split": roles[i], "external": roles[i] == "external", "parameter_external": roles[i] == "external",
            "network_profile": "clean", "network_trace_id": "clean",
        } for i in range(24)]
    internal_counts = [("E0", 14), ("E1", 14), ("E2", 14), ("E4", 14), ("E5", 14), ("E3", 15), ("E6", 15)]
    jobs: list[dict[str, Any]] = []
    seed = 84000
    for scene, count in internal_counts:
        for _ in range(count):
            jobs.append({
                "scenario": scene, "physical_scene": scene, "traj_id": seed - 84000, "seed": seed,
                "split": "confirm_internal", "external": False, "parameter_external": False,
                "network_profile": "clean", "network_trace_id": "clean",
            })
            seed += 1
    for seed in range(84100, 84120):
        scene = PHYSICAL[(seed - 84100) % len(PHYSICAL)]
        jobs.append({
            "scenario": "E7", "physical_scene": scene, "traj_id": seed - 84000, "seed": seed,
            "split": "confirm_external", "external": True, "parameter_external": True,
            "network_profile": "clean", "network_trace_id": "clean",
        })
    profiles = ("delay", "dropout", "burst", "dos")
    for seed in range(84120, 84140):
        scene = PHYSICAL[(seed - 84120) % len(PHYSICAL)]
        profile = profiles[(seed - 84120) % len(profiles)]
        jobs.append({
            "scenario": "E8", "physical_scene": scene, "traj_id": seed - 84000, "seed": seed,
            "split": "confirm_external", "external": True, "parameter_external": False,
            "network_profile": profile, "network_trace_id": f"confirm_{profile}_{seed}",
        })
    assert len(jobs) == 140 and seed == 84139
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("e9", "confirm"), required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    traj_dir = out / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    scales = train_scales(args.data.resolve())
    jobs = jobs_for(args.kind)
    pre = {
        "kind": args.kind,
        "status": "frozen_before_generation",
        "generator_sha256": sha256(Path(__file__)),
        "base_generator_sha256": sha256(HERE / "generate_k2.py"),
        "seed_list": [row["seed"] for row in jobs],
        "jobs": jobs,
        "e9_train_derived_scales": scales,
    }
    pre_path = out / "manifest_pre.json"
    if pre_path.exists():
        old = json.loads(pre_path.read_text(encoding="utf-8"))
        if old != pre:
            raise RuntimeError("pre-generation manifest differs; refusing to mutate a frozen dataset")
    else:
        write_json(pre_path, pre)

    completed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        name = f"{job['split']}_{job['scenario']}_{job['seed']}.npz"
        path = traj_dir / name
        try:
            if path.exists():
                with np.load(path, allow_pickle=False) as source:
                    metadata = json.loads(str(source["metadata_json"].item()))
                if int(metadata["seed"]) != int(job["seed"]):
                    raise RuntimeError(f"resume metadata mismatch: {path}")
            else:
                arrays, metadata = simulate(job, scales)
                np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
            metadata["file"] = str(path.relative_to(out))
            metadata["sha256"] = sha256(path)
            completed.append(metadata)
            write_json(out / "manifest_progress.json", {"completed": completed, "failures": failures})
            print(f"[{index + 1}/{len(jobs)}] {name} force={metadata['max_connector_force_n']:.1f}N", flush=True)
        except Exception as exc:
            failures.append({"job": job, "error": repr(exc)})
            write_json(out / "manifest_progress.json", {"completed": completed, "failures": failures})
            (out / "stop.md").write_text(
                "# 数据生成停止\n\n" + repr(failures[-1]) + "\n\n不得删除失败轨迹；先检查命令包络、ICR与物理门。\n",
                encoding="utf-8",
            )
            raise
    summary = {
        "kind": args.kind, "accepted": not failures and len(completed) == len(jobs),
        "planned": len(jobs), "completed": len(completed),
        "split_counts": {s: sum(row["split"] == s for row in completed) for s in sorted({row["split"] for row in completed})},
        "scenario_counts": {s: sum(row["scenario"] == s for row in completed) for s in sorted({row["scenario"] for row in completed})},
        "max_connector_force_n": max(row["max_connector_force_n"] for row in completed),
        "max_icr_residual_mps": max(row["icr_residual_peak_mps"] for row in completed),
    }
    write_json(out / "manifest.json", {"summary": summary, "trajectories": completed, "pre_sha256": sha256(pre_path)})
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

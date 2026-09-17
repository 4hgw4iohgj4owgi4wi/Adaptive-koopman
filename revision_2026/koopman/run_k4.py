"""K4.0--K4.1 evidence freeze and fixed S4/S5 sensor-stress gates.

This script deliberately stops before K4.2 training.  It verifies the frozen
K2/K3 evidence, exactly reproduces the saved fixed-linear baselines, and then
evaluates the force-input channel with rolling-origin, teacher-free 20-step
predictions.  No confirmation trajectories are generated or read.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HORIZON = 20
BOOTSTRAP = 2000
GATE_PRESSURES = ("P0-clean", "P3-aoi1", "P4-drop10", "P6-single0.5s")
PRESSURES = (
    "P0-clean",
    "P1-noise2",
    "P2-bias2",
    "P3-aoi1",
    "P3-aoi2",
    "P3-aoi4",
    "P4-drop10",
    "P4-drop30",
    "P5-ge",
    "P6-single0.5s",
    "P6-single1s",
    "P6-single2s",
    "P7-dos0.5s",
    "P7-dos1s",
    "P7-dos2s",
)
SPLITS = ("validation", "test", "external")
SPLIT_LABEL = {"validation": "validation", "test": "dev_test_old", "external": "dev_external_old"}


def json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def stable_seed(base: int, *parts: Any) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    word = int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")
    return int((base + word) % (2**32 - 1))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        metadata = json.loads(str(source["metadata_json"].item()))
        model = dict(metadata)
        for key in ("x_mean", "x_std", "u_mean", "u_std", "transition", "decode_full", "decode_force"):
            model[key] = np.asarray(source[key], dtype=np.float64)
    return model


def relative_change(candidate: float, baseline: float) -> float:
    return (candidate - baseline) / max(abs(baseline), 1.0e-12)


def composite(metrics: dict[str, float]) -> float:
    return float(np.mean([metrics["state"], metrics["connector"], metrics["opening"]]))


def force_block(points: np.ndarray, previous: np.ndarray, dt: float) -> np.ndarray:
    q_fr = 0.5 * ((points[0, 0] + points[1, 0]) - (points[2, 0] + points[3, 0]))
    q_lr = 0.5 * ((points[0, 1] + points[2, 1]) - (points[1, 1] + points[3, 1]))
    rate = (points - previous) / dt
    return np.r_[points.reshape(-1), q_fr, q_lr, rate.reshape(-1)]


CONFIG: dict[str, Any] = {
    "stage": "K4.0-K4.1",
    "created_before_results": True,
    "confirmation_policy": "do not generate or read confirm trajectories before G42",
    "data_roles": {
        "train": 70,
        "validation": 15,
        "dev_test_old": 15,
        "dev_external_old": 20,
        "confirm_internal_preregistered_not_generated": 100,
        "confirm_external_preregistered_not_generated": 40,
    },
    "horizon": HORIZON,
    "origin_stride": HORIZON,
    "pressure_scope": "only four point-force messages; S3 physical observations remain current",
    "pressure_seeds": {"validation": 74601, "test": 74602, "external": 74603},
    "noise_scale_of_train_std": 0.02,
    "bias_scale_of_train_std": 0.02,
    "ge": {
        "p_good_to_bad": 0.02,
        "p_bad_to_good": 0.25,
        "delivery_good": 0.99,
        "delivery_bad": 0.10,
    },
    "outage_start_fraction": 0.40,
    "single_point_rule": "(trajectory id + trace seed) modulo 4",
    "supervisor_grid": {
        "tau_steps": [1.0, 2.0, 4.0],
        "cutout": [0.35, 0.60],
        "recover": [0.70, 0.90],
        "recover_consecutive_steps": [1, 5],
        "imputer": ["zoh", "impute"],
    },
    "supervisor_selection": {
        "dataset": "validation only",
        "pressures": list(GATE_PRESSURES),
        "objective": "lowest mean state/connector/opening composite; ties by fewer switches then canonical JSON",
    },
    "g41": {
        "clean_s4_composite_improvement_min": 0.10,
        "light_pressure_each_metric_degradation_max": 0.05,
        "paired_ci_upper_max": 0.0,
        "minimum_switch_interval_steps": 5,
        "maximum_switch_rate_hz": 0.5,
        "bootstrap": BOOTSTRAP,
        "bootstrap_seeds": {"connector": 74501, "opening": 74502},
    },
    "k42_preregistered_training": {
        "factor_seeds": {"A": 74411, "B": 74412, "force_decoder": 74413},
        "ranks": [2, 4, 8],
        "relative_projection_limits": [0.005, 0.01, 0.02],
        "model_seeds": [74201, 74202, 74203, 74204, 74205],
        "optimizer": "AdamW",
        "learning_rate": 5.0e-4,
        "weight_decay": 0.0,
        "batch": 256,
        "epochs": 80,
        "gradient_clip": 1.0,
        "patience": 10,
        "min_delta": 1.0e-5,
        "lambda_anchor": 1.0e-3,
        "lambda_force_rate": 1.0e-2,
        "window_stride": 20,
    },
}


@dataclass
class Trace:
    received: np.ndarray
    mask: np.ndarray
    aoi: np.ndarray


def make_trace(
    true_points: np.ndarray,
    pressure: str,
    train_force_std: np.ndarray,
    dt: float,
    seed: int,
    trajectory_id: int,
) -> Trace:
    count = true_points.shape[0]
    rng = np.random.default_rng(seed)
    received = true_points.copy()
    mask = np.ones((count, 4), dtype=bool)
    aoi = np.zeros((count, 4), dtype=np.int64)

    if pressure == "P0-clean":
        return Trace(received, mask, aoi)
    if pressure == "P1-noise2":
        scale = CONFIG["noise_scale_of_train_std"] * train_force_std.reshape(4, 2)
        received += rng.normal(size=received.shape) * scale[None, :, :]
        return Trace(received, mask, aoi)
    if pressure == "P2-bias2":
        scale = CONFIG["bias_scale_of_train_std"] * train_force_std.reshape(4, 2)
        received += rng.choice(np.array([-1.0, 1.0]), size=(4, 2))[None, :, :] * scale[None, :, :]
        return Trace(received, mask, aoi)
    if pressure.startswith("P3-aoi"):
        delay = int(pressure.removeprefix("P3-aoi"))
        received[:] = np.nan
        mask[:] = False
        for step in range(delay, count):
            received[step] = true_points[step - delay]
            mask[step] = True
            aoi[step] = delay
        return Trace(received, mask, aoi)

    delivery = np.ones((count, 4), dtype=bool)
    if pressure.startswith("P4-drop"):
        percent = int(pressure.removeprefix("P4-drop"))
        delivery = rng.random((count, 4)) >= percent / 100.0
    elif pressure == "P5-ge":
        cfg = CONFIG["ge"]
        bad = np.zeros(4, dtype=bool)
        for step in range(count):
            to_bad = (~bad) & (rng.random(4) < cfg["p_good_to_bad"])
            to_good = bad & (rng.random(4) < cfg["p_bad_to_good"])
            bad = (bad | to_bad) & (~to_good)
            probability = np.where(bad, cfg["delivery_bad"], cfg["delivery_good"])
            delivery[step] = rng.random(4) < probability
    elif pressure.startswith("P6-single") or pressure.startswith("P7-dos"):
        duration_text = pressure.split("single", 1)[1] if pressure.startswith("P6-single") else pressure.split("dos", 1)[1]
        duration = float(duration_text.removesuffix("s"))
        start = min(int(round(count * CONFIG["outage_start_fraction"])), max(count - 1, 0))
        length = max(1, int(round(duration / dt)))
        stop = min(start + length, count)
        if pressure.startswith("P6-single"):
            point = int((trajectory_id + seed) % 4)
            delivery[start:stop, point] = False
        else:
            delivery[start:stop, :] = False
    else:
        raise KeyError(pressure)

    received[:] = np.nan
    mask[:] = delivery
    last_good = np.full(4, -1, dtype=int)
    for step in range(count):
        for point in range(4):
            if delivery[step, point]:
                received[step, point] = true_points[step, point]
                last_good[point] = step
                aoi[step, point] = 0
            else:
                aoi[step, point] = step - last_good[point] if last_good[point] >= 0 else step + 1
    return Trace(received, mask, aoi)


def one_step_s5_force(row: dict[str, Any], model: dict[str, Any], linear: Any, force_mean: np.ndarray, force_std: np.ndarray) -> np.ndarray:
    arrays = row["arrays"]
    state = arrays[model["state_key"]]
    controls = arrays[model["input_key"]]
    output = np.zeros_like(arrays["force_output"])
    output[0] = arrays["force_output"][0]
    for step in range(controls.shape[0]):
        xn = ((state[step] - model["x_mean"]) / model["x_std"])[None, :]
        z = linear.basis(xn, model["kind"])[0]
        un = (controls[step] - model["u_mean"]) / model["u_std"]
        z_next = np.concatenate([z, un]) @ model["transition"]
        output[step + 1] = z_next @ model["decode_force"] * force_std + force_mean
    return output


def processed_s4_state(
    row: dict[str, Any],
    trace: Trace,
    mode: str,
    s5_force_prediction: np.ndarray,
) -> np.ndarray:
    arrays = row["arrays"]
    true_points = arrays["force_output"][:, :8].reshape(-1, 4, 2)
    dt = float(row["meta"]["control_dt_s"])
    result = np.empty_like(arrays["s4_force_in"])
    result[:, :46] = arrays["s3_deform"]
    previous = np.zeros((4, 2), dtype=float)
    last_valid = np.zeros((4, 2), dtype=float)
    have_valid = np.zeros(4, dtype=bool)
    for step in range(true_points.shape[0]):
        points = np.empty((4, 2), dtype=float)
        for point in range(4):
            if trace.mask[step, point]:
                points[point] = trace.received[step, point]
                last_valid[point] = points[point]
                have_valid[point] = True
            elif mode == "zero":
                points[point] = 0.0
            elif mode == "zoh":
                points[point] = last_valid[point] if have_valid[point] else 0.0
            elif mode == "impute":
                points[point] = s5_force_prediction[step, 2 * point : 2 * point + 2]
            else:
                raise KeyError(mode)
        rate_reference = points if step == 0 else previous
        result[step, 46:] = force_block(points, rate_reference, dt)
        previous = points.copy()
    return result


def supervisor_choice(trace: Trace, cfg: dict[str, Any]) -> tuple[np.ndarray, dict[str, int]]:
    reliability = np.min(trace.mask.astype(float) * np.exp(-trace.aoi / float(cfg["tau_steps"])), axis=1)
    use_s4 = np.zeros(reliability.size, dtype=bool)
    active = bool(reliability[0] >= cfg["recover"])
    consecutive = 0
    switches = 0
    recoveries = 0
    cutouts = 0
    last_switch = -10**9
    min_interval = 10**9
    for step, value in enumerate(reliability):
        before = active
        if active:
            if value < cfg["cutout"]:
                active = False
                consecutive = 0
                cutouts += 1
        else:
            if value >= cfg["recover"]:
                consecutive += 1
                if consecutive >= int(cfg["recover_consecutive_steps"]):
                    active = True
                    consecutive = 0
                    recoveries += 1
            else:
                consecutive = 0
        if active != before:
            switches += 1
            min_interval = min(min_interval, step - last_switch)
            last_switch = step
        use_s4[step] = active
    return use_s4, {
        "switches": int(switches),
        "cutouts": int(cutouts),
        "recoveries": int(recoveries),
        "min_switch_interval_steps": int(min_interval if switches >= 2 else -1),
    }


def rollout_errors(
    row: dict[str, Any],
    origins: np.ndarray,
    use_s4: np.ndarray,
    s4_state: np.ndarray,
    s4_model: dict[str, Any],
    s5_model: dict[str, Any],
    linear: Any,
    common_norm: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    arrays = row["arrays"]
    count = origins.size
    error = {name: np.full((count, HORIZON), np.nan, dtype=float) for name in ("state", "connector", "opening")}
    for select_s4, model in ((True, s4_model), (False, s5_model)):
        group = np.flatnonzero(use_s4 == select_s4)
        if group.size == 0:
            continue
        starts = origins[group]
        source_state = s4_state if select_s4 else arrays["s3_deform"]
        xn = (source_state[starts] - model["x_mean"]) / model["x_std"]
        z = linear.basis(xn, model["kind"])
        for horizon in range(1, HORIZON + 1):
            controls = arrays["u1_four"][starts + horizon - 1]
            un = (controls - model["u_mean"]) / model["u_std"]
            z = np.concatenate([z, un], axis=1) @ model["transition"]
            pred_state = z @ model["decode_full"]
            pred_force = z @ model["decode_force"]
            target_state = (arrays["s2_four"][starts + horizon] - common_norm["s2_mean"]) / common_norm["s2_std"]
            target_force = (arrays["force_output"][starts + horizon] - common_norm["force_mean"]) / common_norm["force_std"]
            error["state"][group, horizon - 1] = np.mean((pred_state - target_state) ** 2, axis=1)
            error["connector"][group, horizon - 1] = np.mean((pred_force[:, :8] - target_force[:, :8]) ** 2, axis=1)
            error["opening"][group, horizon - 1] = np.mean((pred_force[:, 8:10] - target_force[:, 8:10]) ** 2, axis=1)
    if not all(np.all(np.isfinite(value)) for value in error.values()):
        raise RuntimeError("non-finite rolling-origin error")
    return error


def evaluate_policy(
    rows: list[dict[str, Any]],
    split: str,
    pressure: str,
    strategy: str,
    models: dict[str, dict[str, Any]],
    linear: Any,
    common_norm: dict[str, np.ndarray],
    supervisor: dict[str, Any] | None = None,
    timeline: bool = False,
) -> dict[str, Any]:
    horizon_pieces = {name: [] for name in ("state", "connector", "opening")}
    per_trajectory: dict[str, dict[str, Any]] = {}
    total_switch = {"switches": 0, "cutouts": 0, "recoveries": 0}
    total_duration_s = 0.0
    min_switch_interval = 10**9
    timeline_value: dict[str, Any] | None = None
    base_seed = int(CONFIG["pressure_seeds"][split])
    train_force_std = common_norm["force_std"][:8]

    for row in rows:
        meta = row["meta"]
        if meta["split"] != split:
            continue
        arrays = row["arrays"]
        trace_seed = stable_seed(base_seed, pressure, meta["scenario"], meta["traj_id"], int(meta["external"]))
        true_points = arrays["force_output"][:, :8].reshape(-1, 4, 2)
        trace = make_trace(true_points, pressure, train_force_std, float(meta["control_dt_s"]), trace_seed, int(meta["traj_id"]))
        s5_prediction = one_step_s5_force(row, models["s5"], linear, common_norm["force_mean"], common_norm["force_std"])

        if strategy == "W3-S5":
            imputer = "zoh"
            choose = np.zeros(trace.mask.shape[0], dtype=bool)
            switch_stats = {"switches": 0, "cutouts": 0, "recoveries": 0, "min_switch_interval_steps": -1}
        elif strategy == "W4-supervisor":
            if supervisor is None:
                raise RuntimeError("W4 requires supervisor config")
            imputer = str(supervisor["imputer"])
            choose, switch_stats = supervisor_choice(trace, supervisor)
        else:
            imputer = {"W0-zero": "zero", "W1-zoh": "zoh", "W2-impute": "impute"}[strategy]
            choose = np.ones(trace.mask.shape[0], dtype=bool)
            switch_stats = {"switches": 0, "cutouts": 0, "recoveries": 0, "min_switch_interval_steps": -1}

        s4_state = processed_s4_state(row, trace, imputer, s5_prediction)
        steps = arrays["u1_four"].shape[0]
        total_duration_s += steps * float(meta["control_dt_s"])
        origins = np.arange(0, steps - HORIZON + 1, HORIZON, dtype=int)
        errors = rollout_errors(row, origins, choose[origins], s4_state, models["s4"], models["s5"], linear, common_norm)
        for name, value in errors.items():
            horizon_pieces[name].append(value)
        key = f"{meta['scenario']}|{meta['traj_id']}|{int(meta['external'])}"
        per_trajectory[key] = {
            name: float(math.sqrt(np.mean(value[:, 9:]))) for name, value in errors.items()
        }
        per_trajectory[key]["scenario"] = meta["scenario"]
        for name in ("switches", "cutouts", "recoveries"):
            total_switch[name] += int(switch_stats[name])
        if switch_stats["min_switch_interval_steps"] >= 0:
            min_switch_interval = min(min_switch_interval, switch_stats["min_switch_interval_steps"])

        if timeline and timeline_value is None:
            timeline_value = {
                "time_s": (np.arange(trace.mask.shape[0]) * float(meta["control_dt_s"])).tolist(),
                "mask": trace.mask.astype(int).tolist(),
                "aoi": trace.aoi.tolist(),
                "reliability": np.min(
                    trace.mask.astype(float) * np.exp(-trace.aoi / float((supervisor or {"tau_steps": 1.0})["tau_steps"])), axis=1
                ).tolist(),
                "use_s4": choose.astype(int).tolist(),
                "origin_time_s": (origins * float(meta["control_dt_s"])).tolist(),
                "origin_composite": np.sqrt(
                    np.mean(np.stack([errors[name][:, 9:] for name in ("state", "connector", "opening")]), axis=(0, 2))
                ).tolist(),
                "trajectory": key,
            }

    merged = {name: np.concatenate(values, axis=0) for name, values in horizon_pieces.items()}
    horizon = {name: np.sqrt(np.mean(value, axis=0)) for name, value in merged.items()}
    h10 = {name: float(math.sqrt(np.mean(value[:, 9:]))) for name, value in merged.items()}
    result = {
        "split": SPLIT_LABEL[split],
        "pressure": pressure,
        "strategy": strategy,
        "finite": bool(all(np.all(np.isfinite(value)) for value in merged.values())),
        "horizon_nrmse": horizon,
        "h10_20_nrmse": h10,
        "composite": composite(h10),
        "per_trajectory_h10_20": per_trajectory,
        "rollout_origins": int(merged["state"].shape[0]),
        "switching": {
            **total_switch,
            "min_switch_interval_steps": int(min_switch_interval if min_switch_interval < 10**9 else -1),
            "total_duration_s": total_duration_s,
            "switch_rate_hz": total_switch["switches"] / max(total_duration_s, 1.0e-12),
        },
    }
    if timeline_value is not None:
        result["timeline"] = timeline_value
    return result


def supervisor_grid() -> list[dict[str, Any]]:
    grid = CONFIG["supervisor_grid"]
    values = []
    for tau in grid["tau_steps"]:
        for cutout in grid["cutout"]:
            for recover in grid["recover"]:
                if recover <= cutout:
                    continue
                for consecutive in grid["recover_consecutive_steps"]:
                    for imputer in grid["imputer"]:
                        values.append(
                            {
                                "tau_steps": float(tau),
                                "cutout": float(cutout),
                                "recover": float(recover),
                                "recover_consecutive_steps": int(consecutive),
                                "imputer": str(imputer),
                            }
                        )
    return values


def select_supervisor(
    rows: list[dict[str, Any]], models: dict[str, dict[str, Any]], linear: Any, common_norm: dict[str, np.ndarray]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    search = []
    for cfg in supervisor_grid():
        cells = [evaluate_policy(rows, "validation", pressure, "W4-supervisor", models, linear, common_norm, cfg) for pressure in GATE_PRESSURES]
        score = float(np.mean([cell["composite"] for cell in cells]))
        switches = int(sum(cell["switching"]["switches"] for cell in cells))
        search.append({"config": cfg, "score": score, "switches": switches, "cells": cells})
    search.sort(key=lambda row: (row["score"], row["switches"], json.dumps(row["config"], sort_keys=True)))
    return dict(search[0]["config"]), search


def paired_ci(
    candidate: dict[str, Any], baseline: dict[str, Any], metric: str, seed: int
) -> dict[str, Any]:
    a = candidate["per_trajectory_h10_20"]
    b = baseline["per_trajectory_h10_20"]
    keys = sorted(set(a) & set(b))
    ratio = np.asarray([(a[key][metric] - b[key][metric]) / max(b[key][metric], 1.0e-12) for key in keys])
    rng = np.random.default_rng(seed)
    boot = ratio[rng.integers(0, len(ratio), size=(BOOTSTRAP, len(ratio)))].mean(axis=1)
    return {
        "n": len(keys),
        "mean_relative_difference": float(np.mean(ratio)),
        "ci95": np.quantile(boot, [0.025, 0.975]),
        "bootstrap_seed": seed,
    }


def aggregate_gate_cells(cells: Iterable[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, dict[str, Any]] = {}
    for cell in cells:
        for key, value in cell["per_trajectory_h10_20"].items():
            merged[f"{cell['pressure']}|{key}"] = value
    return {"per_trajectory_h10_20": merged}


def plot_sensor(results: dict[str, Any], path: Path) -> None:
    labels = list(PRESSURES)
    methods = ("W0-zero", "W1-zoh", "W2-impute", "W3-S5", "W4-supervisor")
    fig, ax = plt.subplots(figsize=(15, 6))
    for method in methods:
        values = [results["validation"][pressure][method]["composite"] for pressure in labels]
        ax.plot(range(len(labels)), values, marker="o", linewidth=1.5, label=method)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_ylabel("10–20 step composite NRMSE")
    ax.set_title("K4.1 fixed S4 force-channel stress; validation only")
    ax.grid(True, alpha=0.25)
    ax.legend(ncol=3)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_timeline(timeline: dict[str, Any], path: Path) -> None:
    t = np.asarray(timeline["time_s"])
    mask = np.asarray(timeline["mask"])
    aoi = np.asarray(timeline["aoi"])
    reliability = np.asarray(timeline["reliability"])
    use_s4 = np.asarray(timeline["use_s4"])
    origin_t = np.asarray(timeline["origin_time_s"])
    origin_error = np.asarray(timeline["origin_composite"])
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(t, mask + np.arange(4)[None, :] * 1.2)
    axes[0].set_ylabel("mask + offset")
    axes[1].plot(t, aoi)
    axes[1].set_ylabel("AoI [steps]")
    axes[2].plot(t, reliability, label="reliability")
    axes[2].step(t, use_s4, where="post", label="use S4")
    axes[2].set_ylabel("supervisor")
    axes[2].legend()
    axes[3].plot(origin_t, origin_error, color="tab:red")
    axes[3].set_ylabel("origin NRMSE")
    axes[3].set_xlabel("time [s]")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.suptitle(f"K4.1 supervisor timeline: {timeline['trajectory']}")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def freeze_evidence(root: Path, koopman_dir: Path, out: Path, linear: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_dir = koopman_dir / "k2" / "data_full"
    manifest, rows = linear.load_data(data_dir)
    confirm_path = koopman_dir / "k3" / "confirm_preregistered.json"
    confirm = json.loads(confirm_path.read_text(encoding="utf-8"))
    required = [
        root / "koopman.md",
        koopman_dir / "k4.md",
        koopman_dir / "run_k4.py",
        koopman_dir / "train_k4.py",
        koopman_dir / "generate_k2.py",
        koopman_dir / "linear.py",
        koopman_dir / "experts.py",
        data_dir / "manifest.json",
        data_dir / "split.json",
        koopman_dir / "k2" / "linear" / "results.json",
        koopman_dir / "k2" / "linear" / "models" / "S3-U1-raw.npz",
        koopman_dir / "k2" / "linear" / "models" / "S3-U1-lifted.npz",
        koopman_dir / "k2" / "linear" / "models" / "S4-force-in-U1-lifted.npz",
        koopman_dir / "k2" / "experts" / "results.json",
        koopman_dir / "k2" / "experts" / "stop.md",
        koopman_dir / "k3" / "config.json",
        koopman_dir / "k3" / "freeze.json",
        koopman_dir / "k3" / "g30.json",
        koopman_dir / "k3" / "g31.json",
        koopman_dir / "k3" / "development" / "A_results.json",
        koopman_dir / "k3" / "stop.md",
        koopman_dir / "k3" / "solutions.md",
        confirm_path,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    hashes = {str(path.relative_to(root)): sha256(path) for path in required if path.is_file()}
    split_counts: dict[str, int] = {}
    identities = set()
    files = set()
    for row in manifest["trajectories"]:
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
        identities.add((row["scenario"], int(row["traj_id"]), bool(row["external"])))
        files.add(row["file"].lower())
    confirm_files = list((koopman_dir / "k3").glob("confirm/**/*.npz")) + list(out.glob("confirm/**/*.npz"))
    internal = sum(row["set"] == "confirm_internal" for row in confirm["rows"])
    external = sum(row["set"] == "confirm_external" for row in confirm["rows"])
    expected_splits = {"train": 70, "validation": 15, "test": 15, "external": 20}
    checks = {
        "required_files_present": not missing,
        "manifest_accepted": bool(manifest["summary"]["accepted"]),
        "split_counts_exact": split_counts == expected_splits,
        "unique_trajectory_identity": len(identities) == 120,
        "unique_trajectory_files": len(files) == 120,
        "confirm_flag_false": confirm.get("generated") is False,
        "confirm_preregistered_counts": (internal, external) == (100, 40),
        "confirm_trajectory_files_absent": len(confirm_files) == 0,
    }
    initial_hashes = dict(hashes)
    second_hashes = {str(path.relative_to(root)): sha256(path) for path in required if path.is_file()}
    checks["second_read_hashes_equal"] = initial_hashes == second_hashes
    g40_pass = all(checks.values())
    freeze = {
        "stage": "K4.0",
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python": sys.version,
        "config": CONFIG,
        "config_sha256": hashlib.sha256(
            (json.dumps(CONFIG, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        ).hexdigest().upper(),
        "evidence_hashes": hashes,
        "trajectory_hashes_verified_by_linear_loader": len(rows),
        "data_roles": {
            "train": 70,
            "validation": 15,
            "test_mapped_to": "dev_test_old",
            "external_mapped_to": "dev_external_old",
        },
        "confirm": {
            "generated": False,
            "internal_preregistered": internal,
            "external_preregistered": external,
            "trajectory_files_found": len(confirm_files),
            "viewed": False,
        },
        "missing": missing,
        "checks": checks,
        "G40_pass": g40_pass,
    }
    write_json(out / "config.json", CONFIG)
    write_json(out / "freeze.json", freeze)
    reread = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    if reread["evidence_hashes"] != hashes or reread["checks"] != checks:
        raise RuntimeError("freeze second-read mismatch")
    if not g40_pass:
        raise RuntimeError(f"G40 failed: {checks}; missing={missing}")
    return freeze, rows


def exact_baselines(koopman_dir: Path, out: Path, rows: list[dict[str, Any]], linear: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, np.ndarray]]:
    model_dir = koopman_dir / "k2" / "linear" / "models"
    models = {
        "raw": load_model(model_dir / "S3-U1-raw.npz"),
        "s5": load_model(model_dir / "S3-U1-lifted.npz"),
        "s4": load_model(model_dir / "S4-force-in-U1-lifted.npz"),
    }
    common_norm = {
        "s2_mean": linear.moments(rows, "s2_four", states=True)[0],
        "s2_std": linear.moments(rows, "s2_four", states=True)[1],
        "force_mean": linear.moments(rows, "force_output", states=True)[0],
        "force_std": linear.moments(rows, "force_output", states=True)[1],
    }
    old = json.loads((koopman_dir / "k2" / "linear" / "results.json").read_text(encoding="utf-8"))
    old_lookup = {"raw": old["k21"]["S3-U1-raw"], "s5": old["k22"]["S3-deform"], "s4": old["k22"]["S4-force-in"]}
    evaluations: dict[str, Any] = {}
    differences = []
    for name, model in models.items():
        evaluations[name] = {}
        for split in SPLITS:
            result = linear.evaluate_model(model, rows, split, common_norm)
            evaluations[name][SPLIT_LABEL[split]] = result
            if split in ("test", "external"):
                expected = old_lookup[name][split]
                for metric in linear.METRICS:
                    differences.extend(np.abs(np.asarray(result["horizon_nrmse"][metric]) - np.asarray(expected["horizon_nrmse"][metric])).tolist())
                    differences.append(abs(result["h10_20_nrmse"][metric] - expected["h10_20_nrmse"][metric]))
    maximum = float(max(differences, default=0.0))
    result = {
        "stage": "K4.1_fixed_recalculation",
        "maximum_absolute_metric_difference_from_K2": maximum,
        "tolerance": 1.0e-10,
        "pass": maximum <= 1.0e-10,
        "evaluations": evaluations,
    }
    write_json(out / "development" / "fixed_recalculation.json", result)
    if not result["pass"]:
        raise RuntimeError(f"fixed baseline reproduction failed: {maximum}")
    return result, models, common_norm


def run_stress(out: Path, rows: list[dict[str, Any]], models: dict[str, dict[str, Any]], linear: Any, common_norm: dict[str, np.ndarray]) -> dict[str, Any]:
    selected, search = select_supervisor(rows, models, linear, common_norm)
    write_json(out / "development" / "supervisor_search.json", {"selected": selected, "search": search})
    results: dict[str, Any] = {}
    for split in SPLITS:
        label = SPLIT_LABEL[split]
        results[label] = {}
        for pressure in PRESSURES:
            results[label][pressure] = {}
            for strategy in ("W0-zero", "W1-zoh", "W2-impute", "W3-S5", "W4-supervisor"):
                need_timeline = split == "validation" and pressure == "P7-dos2s" and strategy == "W4-supervisor"
                results[label][pressure][strategy] = evaluate_policy(
                    rows, split, pressure, strategy, models, linear, common_norm, selected if strategy == "W4-supervisor" else None, need_timeline
                )

    validation = results["validation"]
    clean_s4 = validation["P0-clean"]["W1-zoh"]
    clean_s5 = validation["P0-clean"]["W3-S5"]
    clean_improvement = (clean_s5["composite"] - clean_s4["composite"]) / clean_s5["composite"]
    light_details: dict[str, Any] = {}
    light_pass = True
    for pressure in GATE_PRESSURES[1:]:
        candidate = validation[pressure]["W4-supervisor"]
        baseline = validation[pressure]["W3-S5"]
        degradation = {
            metric: relative_change(candidate["h10_20_nrmse"][metric], baseline["h10_20_nrmse"][metric])
            for metric in ("state", "connector", "opening")
        }
        light_details[pressure] = degradation
        light_pass = light_pass and all(value <= CONFIG["g41"]["light_pressure_each_metric_degradation_max"] for value in degradation.values())

    candidate_aggregate = aggregate_gate_cells(validation[pressure]["W4-supervisor"] for pressure in GATE_PRESSURES)
    baseline_aggregate = aggregate_gate_cells(validation[pressure]["W3-S5"] for pressure in GATE_PRESSURES)
    paired = {
        metric: paired_ci(candidate_aggregate, baseline_aggregate, metric, CONFIG["g41"]["bootstrap_seeds"][metric])
        for metric in ("connector", "opening")
    }
    force_ci_pass = any(value["ci95"][1] < CONFIG["g41"]["paired_ci_upper_max"] for value in paired.values())
    switching_details: dict[str, Any] = {}
    switching_pass = True
    for pressure in GATE_PRESSURES[1:]:
        switching = validation[pressure]["W4-supervisor"]["switching"]
        interval = int(switching["min_switch_interval_steps"])
        interval_pass = interval < 0 or interval >= CONFIG["g41"]["minimum_switch_interval_steps"]
        rate_pass = switching["switch_rate_hz"] <= CONFIG["g41"]["maximum_switch_rate_hz"]
        switching_details[pressure] = {
            **switching,
            "minimum_interval_pass": interval_pass,
            "switch_rate_pass": rate_pass,
        }
        switching_pass = switching_pass and interval_pass and rate_pass
    g41_checks = {
        "clean_s4_composite_improvement_at_least_10pct": clean_improvement >= CONFIG["g41"]["clean_s4_composite_improvement_min"],
        "selected_supervisor_light_pressure_each_metric_within_5pct": bool(light_pass),
        "connector_or_opening_paired_ci_upper_below_zero": bool(force_ci_pass),
        "supervisor_no_high_frequency_switching": bool(switching_pass),
        "all_rollouts_finite": bool(
            all(cell[strategy]["finite"] for split in results.values() for cell in split.values() for strategy in cell)
        ),
        "confirm_not_generated_or_viewed": True,
    }
    g41_pass = all(g41_checks.values())
    gate = {
        "stage": "K4.1",
        "selected_supervisor": selected,
        "clean_s4_composite": clean_s4["composite"],
        "clean_s5_composite": clean_s5["composite"],
        "clean_s4_relative_improvement": clean_improvement,
        "light_pressure_relative_degradation_vs_s5": light_details,
        "paired_gate_cells": paired,
        "switching_gate_cells": switching_details,
        "checks": g41_checks,
        "G41_pass": g41_pass,
        "selected_contract_for_K4_2": "S4+S5-supervisor" if g41_pass else "S5-operational",
        "confirm_generated": False,
        "confirm_viewed": False,
    }
    payload = {"gate": gate, "results": results}
    write_json(out / "development" / "sensor_stress.json", payload)
    plot_sensor(results, out / "development" / "sensor_stress.png")
    timeline = results["validation"]["P7-dos2s"]["W4-supervisor"]["timeline"]
    write_json(out / "development" / "switch_timeline.json", timeline)
    plot_timeline(timeline, out / "development" / "switch_timeline.png")
    return payload


def write_report(out: Path, freeze: dict[str, Any], baselines: dict[str, Any], stress: dict[str, Any], elapsed: float) -> None:
    gate = stress["gate"]
    report = [
        "# K4.0–K4.1执行报告",
        "",
        f"- G40：`{'PASS' if freeze['G40_pass'] else 'FAIL'}`；120条K2轨迹hash已复核。",
        f"- confirm：预注册100 internal + 40 external；生成文件=`0`，查看=`false`。",
        f"- fixed复算最大绝对差：`{baselines['maximum_absolute_metric_difference_from_K2']:.3e}`（门限`1e-10`）。",
        f"- validation clean S4/S5综合NRMSE：`{gate['clean_s4_composite']:.8f}/{gate['clean_s5_composite']:.8f}`。",
        f"- clean S4相对改善：`{100*gate['clean_s4_relative_improvement']:.2f}%`。",
        f"- G41：`{'PASS' if gate['G41_pass'] else 'FAIL'}`；K4.2合同=`{gate['selected_contract_for_K4_2']}`。",
        f"- 总运行时间：`{elapsed:.2f} s`。",
        "",
        "## G41逐项",
        "",
    ]
    report.extend(f"- {key}: `{value}`" for key, value in gate["checks"].items())
    report.extend(
        [
            "",
            "## 边界",
            "",
            "本阶段只验证fixed S4显式力输入通道与S5降级合同；没有训练M2/M3，没有生成确认集，也没有接入闭环。旧test/external仍是development证据。",
            "",
        ]
    )
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")


def append_work_log(root: Path, out: Path, freeze: dict[str, Any], baselines: dict[str, Any], stress: dict[str, Any]) -> None:
    gate = stress["gate"]
    files = [
        root / "koopman.md",
        root / "koopman" / "k4.md",
        root / "koopman" / "run_k4.py",
        out / "config.json",
        out / "freeze.json",
        out / "development" / "fixed_recalculation.json",
        out / "development" / "supervisor_search.json",
        out / "development" / "sensor_stress.json",
        out / "development" / "sensor_stress.png",
        out / "development" / "switch_timeline.json",
        out / "development" / "switch_timeline.png",
        out / "report.md",
    ]
    hash_lines = [f"  - `{path.relative_to(root)}` = `{sha256(path)}`" for path in files]
    entry = [
        "",
        "### W0037｜修正G41切换漏判并回退S5合同",
        "",
        "- 修正原因：首次自动结果把G41标为通过，但脚本只记录切换次数，漏掉了计划中“不能通过高频切换换误差”的布尔裁决；该结论不可接受。",
        "- 协议澄清：轻压力下最短驻留固定为至少5个控制周期、总切换率不超过0.5 Hz；因为已看到首次结果，本轮不再重调W4网格，违反即保守回退S5。",
        f"- G40=`{freeze['G40_pass']}`：120条轨迹hash、70/15/15/20角色、K2/K3证据和140条confirm预注册行通过二次只读核验；confirm轨迹文件=0，未查看confirm。",
        f"- fixed复算：M0/M1/M1F相对K2已保存1–20步指标最大绝对差=`{baselines['maximum_absolute_metric_difference_from_K2']:.3e}`，门限=`1e-10`。",
        f"- validation clean S4/S5综合NRMSE=`{gate['clean_s4_composite']:.8f}/{gate['clean_s5_composite']:.8f}`，S4相对改善=`{100*gate['clean_s4_relative_improvement']:.2f}%`。",
        f"- G41=`{gate['G41_pass']}`；K4.2唯一合同=`{gate['selected_contract_for_K4_2']}`。具体轻压力差值、paired CI和切换率见`koopman/k4/development/sensor_stress.json`。",
        "- 本轮没有生成confirm、没有训练M2/M3、没有接入MPC/DoS闭环；旧test/external只标记为dev_test_old/dev_external_old。",
        "- SHA256：",
        *hash_lines,
        "",
    ]
    log = root / "work_log.md"
    with log.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("all", "freeze", "sensor"), default="all")
    args = parser.parse_args()
    koopman_dir = Path(__file__).resolve().parent
    root = koopman_dir.parent
    out = koopman_dir / "k4"
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    linear = load_module(koopman_dir / "linear.py", "k4_linear")
    freeze, rows = freeze_evidence(root, koopman_dir, out, linear)
    if args.stage == "freeze":
        print(json.dumps({"G40_pass": True, "freeze": str(out / "freeze.json")}, ensure_ascii=False))
        return 0
    baselines, models, common_norm = exact_baselines(koopman_dir, out, rows, linear)
    stress = run_stress(out, rows, models, linear, common_norm)
    elapsed = time.perf_counter() - started
    write_report(out, freeze, baselines, stress, elapsed)
    append_work_log(root, out, freeze, baselines, stress)
    print(
        json.dumps(
            {
                "G40_pass": freeze["G40_pass"],
                "fixed_recalculation_pass": baselines["pass"],
                "G41_pass": stress["gate"]["G41_pass"],
                "selected_contract_for_K4_2": stress["gate"]["selected_contract_for_K4_2"],
                "confirm_generated": False,
                "elapsed_seconds": elapsed,
                "report": str(out / "report.md"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

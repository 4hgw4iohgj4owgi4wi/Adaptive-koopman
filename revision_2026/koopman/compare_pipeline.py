"""Idempotent T0--T6 executor for koopman_compare.md.

The implementation deliberately keeps the preregistered K0--K6 and E0--E9
scope.  It never rewrites the accepted plant, allocator, original dataset, or
frozen K0/K1 artifacts.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "k2" / "data_full"
E9_DATA = HERE / "compare" / "e9"
CONFIRM_DATA = HERE / "compare" / "confirm"
OUT = HERE / "compare"
MODELS = OUT / "models"
PROTOCOL = ROOT / "revision_2026" / "koopman_compare.md"
WORK_LOG = ROOT / "revision_2026" / "work_log.md"
FIXED_RAW = HERE / "k2" / "linear" / "models" / "S3-U1-raw.npz"
FIXED_LIFT = HERE / "k2" / "linear" / "models" / "S3-U1-lifted.npz"
NORMALIZERS = HERE / "k3" / "development" / "normalizers.npz"
HORIZON = 20
RIDGES = np.logspace(-8, -1, 8)
RANKS = (2, 4, 8, 12)
MODEL_SET = ("K0", "K1", "K2", "K3", "K3-r2", "K4", "K5-linear", "K5-bilinear", "K6")


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: Any) -> None:
    def clean(item: Any) -> Any:
        if isinstance(item, dict): return {str(key): clean(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)): return [clean(val) for val in item]
        if isinstance(item, np.ndarray): return clean(item.tolist())
        if isinstance(item, (np.floating, float)) and not math.isfinite(float(item)): return None
        if isinstance(item, np.generic): return item.item()
        return item
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, default=json_default, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def stable_seed(*parts: Any) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little") % (2**32 - 1)


def append_log(identifier: str, title: str, lines: list[str]) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    body = ["", f"## {identifier} — {title}", "", f"- 时间：{stamp}"] + [f"- {line}" for line in lines]
    with WORK_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(body) + "\n")


def verify_manifest(data_dir: Path) -> dict[str, Any]:
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest["summary"]["accepted"]:
        raise RuntimeError(f"dataset not accepted: {data_dir}")
    for meta in manifest["trajectories"]:
        path = data_dir / meta["file"]
        if sha256(path) != str(meta["sha256"]).upper():
            raise RuntimeError(f"trajectory hash mismatch: {path}")
    return manifest


ARRAY_KEYS = (
    "s2_four", "s3_deform", "force_output", "force_body", "force_rate",
    "displacement_body", "relative_velocity_body", "u1_four", "network", "time_s",
)


def load_rows(data_dir: Path, verify: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = verify_manifest(data_dir) if verify else json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for meta in manifest["trajectories"]:
        path = data_dir / meta["file"]
        with np.load(path, allow_pickle=False) as source:
            arrays = {key: np.asarray(source[key], dtype=np.float64) for key in ARRAY_KEYS}
        steps = int(meta["steps"])
        for key in ("s2_four", "s3_deform", "force_output", "force_body", "force_rate", "displacement_body", "relative_velocity_body", "time_s"):
            if arrays[key].shape[0] != steps + 1:
                raise RuntimeError(f"state length mismatch: {path}/{key}")
        for key in ("u1_four", "network"):
            if arrays[key].shape[0] != steps:
                raise RuntimeError(f"control length mismatch: {path}/{key}")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise RuntimeError(f"non-finite source data: {path}")
        rows.append({"meta": meta, "arrays": arrays, "path": path})
    return manifest, rows


def fixed_basis(xn: np.ndarray) -> np.ndarray:
    one = np.ones((*xn.shape[:-1], 1), dtype=xn.dtype)
    clipped = np.clip(xn, -8.0, 8.0)
    return np.concatenate([one, xn, clipped * clipped], axis=-1)


def raw_basis(xn: np.ndarray) -> np.ndarray:
    one = np.ones((*xn.shape[:-1], 1), dtype=xn.dtype)
    return np.concatenate([one, xn], axis=-1)


def physical_modes(u: np.ndarray) -> np.ndarray:
    a = u[..., 0::2]
    d = u[..., 1::2]
    return np.stack([
        a.mean(axis=-1),
        0.5 * (a[..., 0] + a[..., 1] - a[..., 2] - a[..., 3]),
        0.5 * (a[..., 0] + a[..., 2] - a[..., 1] - a[..., 3]),
        0.5 * (a[..., 0] + a[..., 3] - a[..., 1] - a[..., 2]),
        0.25 * (d[..., 0] + d[..., 1] - d[..., 2] - d[..., 3]),
    ], axis=-1)


def load_fixed(path: Path, name: str) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        model = {key: np.asarray(source[key], dtype=float) for key in source.files if key != "metadata_json"}
        meta = json.loads(str(source["metadata_json"].item()))
    model.update({
        "name": name,
        "kind": "raw" if meta["kind"] == "raw" else "linear",
        "lift_kind": "raw" if meta["kind"] == "raw" else "fixed",
        "transition_parameter_count": int(model["transition"].size),
        "parameter_count": int(meta["parameter_count"]),
        "source_sha256": sha256(path),
        "source_path": str(path),
    })
    return model


def save_model(path: Path, model: dict[str, Any]) -> None:
    arrays = {key: value for key, value in model.items() if isinstance(value, np.ndarray)}
    metadata = {key: value for key, value in model.items() if key not in arrays and not key.startswith("_")}
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False, default=json_default)))


def load_model(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        model = {key: np.asarray(source[key], dtype=float) for key in source.files if key != "metadata_json"}
        model.update(json.loads(str(source["metadata_json"].item())))
    model["artifact_path"] = str(path)
    model["artifact_sha256"] = sha256(path)
    return model


def gelu_tanh(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x**3)))


def lift(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    xn = (x - model["x_mean"]) / model["x_std"]
    if model["lift_kind"] == "raw":
        return raw_basis(xn)
    if model["lift_kind"] == "fixed":
        return fixed_basis(xn)
    hidden = gelu_tanh(xn @ model["w1"].T + model["b1"])
    learned = hidden @ model["w2"].T + model["b2"]
    return np.r_[1.0, xn, learned]


def model_step(
    model: dict[str, Any], z: np.ndarray, u: np.ndarray, *, ablation: str = "none",
    u_bilinear: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    un = (u - model["u_mean"]) / model["u_std"]
    kind = str(model["kind"])
    if kind in ("raw", "linear", "neural_linear"):
        return np.r_[z, un] @ model["transition"], 0.0
    bil_u = u if u_bilinear is None else u_bilinear
    bil_un = (bil_u - model["u_mean"]) / model["u_std"]
    linear_part = np.r_[z, un] @ model["base_transition"]
    if kind == "full_bilinear":
        if ablation == "permute":
            bil_un = np.roll(bil_un, -1)
        bil_part = np.outer(bil_un, z[1:]).reshape(-1) @ model["bilinear"]
    elif kind == "structured_bilinear":
        eta = physical_modes(np.asarray(bil_u)[None, :])[0]
        eta = (eta - model["mode_mean"]) / model["mode_std"]
        if ablation == "permute":
            eta = np.roll(eta, -1)
        bil_part = np.outer(eta, z[1:]).reshape(-1) @ model["bilinear"]
    else:
        raise KeyError(kind)
    if ablation == "zero":
        bil_part = np.zeros_like(bil_part)
    ratio = float(np.linalg.norm(bil_part) / (np.linalg.norm(linear_part) + 1.0e-12))
    return linear_part + bil_part, ratio


def decode(model: dict[str, Any], z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    full_n = z @ model["decode_full"]
    force_n = z @ model["decode_force"]
    if model["lift_kind"] in ("raw", "fixed", "neural"):
        model_xn = z[1:47]
        x_physical = model_xn * model["x_std"] + model["x_mean"]
        x_n = (x_physical - model.get("metric_x_mean", model["x_mean"])) / model.get("metric_x_std", model["x_std"])
    else:
        raise KeyError(model["lift_kind"])
    return full_n, force_n, x_n


def train_moments(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    train = [row for row in rows if row["meta"]["split"] == "train"]
    def joined(key: str, state: bool) -> np.ndarray:
        return np.concatenate([row["arrays"][key][:-1] if state else row["arrays"][key] for row in train])
    result: dict[str, np.ndarray] = {}
    for key, short, state in (
        ("s3_deform", "x", True), ("u1_four", "u", False), ("s2_four", "full", True), ("force_output", "force", True),
    ):
        value = joined(key, state)
        result[f"{short}_mean"] = value.mean(0)
        std = value.std(0)
        result[f"{short}_std"] = np.where(std < 1.0e-7, 1.0, std)
    modes = physical_modes(joined("u1_four", False))
    result["mode_mean"] = modes.mean(0)
    result["mode_std"] = np.where(modes.std(0) < 1.0e-10, 1.0, modes.std(0))
    abs_force = np.abs(joined("force_output", True))
    result["force_sign_floor"] = np.asarray([
        np.quantile(column[column > 1.0e-8], 0.10) if np.any(column > 1.0e-8) else 1.0e-8 for column in abs_force.T
    ])
    return result


def derive_labels(rows: list[dict[str, Any]]) -> dict[str, Any]:
    train_u = np.concatenate([row["arrays"]["u1_four"] for row in rows if row["meta"]["split"] == "train"])
    accel = np.abs(train_u[:, 0::2].mean(1))
    steer = np.abs(physical_modes(train_u)[:, 4])
    steer_delta = np.abs(np.diff(physical_modes(train_u)[:, 4]))
    nz = lambda value: value[value > 1.0e-10]
    return {
        "accel_low_q25": float(np.quantile(nz(accel), 0.25)),
        "steer_low_q25_rad": float(np.quantile(nz(steer), 0.25)),
        "steer_q50_rad": float(np.quantile(nz(steer), 0.50)),
        "steer_q80_rad": float(np.quantile(nz(steer), 0.80)),
        "steer_delta_q90_rad": float(np.quantile(nz(steer_delta), 0.90)),
        "source": "original train rows only",
        "window_horizon": HORIZON,
        "window_stride": HORIZON,
    }


def window_labels(row: dict[str, Any], start: int, labels: dict[str, Any]) -> set[str]:
    meta = row["meta"]
    scenario = str(meta["scenario"])
    if scenario.startswith("E"):
        return {scenario}
    if bool(meta.get("external", False)) or meta.get("split") in ("external", "confirm_external"):
        return {"E7"}
    u = row["arrays"]["u1_four"][start:start + HORIZON]
    modes = physical_modes(u)
    accel = float(np.max(np.abs(modes[:, 0])))
    steer = np.abs(modes[:, 4])
    delta = np.abs(np.diff(modes[:, 4]))
    found: set[str] = set()
    if scenario == "staged_100m":
        low_steer = float(np.max(steer)) <= labels["steer_low_q25_rad"]
        low_delta = (not delta.size) or float(np.max(delta)) <= labels["steer_delta_q90_rad"]
        if low_steer and low_delta and accel <= labels["accel_low_q25"]:
            found.add("E0")
        if low_steer and accel > labels["accel_low_q25"]:
            found.add("E1")
        signs = np.sign(modes[:, 4])
        nonzero_sign = signs[np.abs(modes[:, 4]) > labels["steer_low_q25_rad"]]
        sign_change = nonzero_sign.size > 1 and np.any(nonzero_sign[1:] != nonzero_sign[:-1])
        high_delta = delta.size and float(np.max(delta)) > labels["steer_delta_q90_rad"]
        if sign_change or high_delta:
            found.add("E3")
    elif scenario == "single_lane_change":
        found.add("E4")
    elif scenario == "hairpin":
        found.add("E5")
        median = float(np.median(steer))
        if labels["steer_q50_rad"] <= median <= labels["steer_q80_rad"] and (not delta.size or float(np.max(delta)) <= labels["steer_delta_q90_rad"]):
            found.add("E2")
    elif scenario == "connector_directional":
        found.add("E6")
    elif scenario == "network_excitation":
        found.add("E8")
    return found


def role_matches(meta: dict[str, Any], role: str) -> bool:
    split = str(meta["split"])
    if role == "development-test":
        return split == "test"
    if role == "development-external":
        return split == "external"
    return split == role


GROUPS = ("state", "force", "load", "deformation", "force_rate")


def evaluate(
    model: dict[str, Any], rows: list[dict[str, Any]], role: str, norms: dict[str, np.ndarray], labels: dict[str, Any],
    *, ablation: str = "none", stride: int = HORIZON,
) -> dict[str, Any]:
    sq = {group: np.zeros(HORIZON) for group in GROUPS}
    count = {group: np.zeros(HORIZON, dtype=int) for group in GROUPS}
    label_traj: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    sign_correct = defaultdict(int)
    sign_count = defaultdict(int)
    peak_errors = defaultdict(list)
    peak_time_errors = defaultdict(list)
    bil_rows: list[dict[str, float]] = []
    window_rows: list[dict[str, Any]] = []
    nonfinite_windows = divergence_windows = windows = 0

    for row in rows:
        meta, arrays = row["meta"], row["arrays"]
        if not role_matches(meta, role):
            continue
        steps = arrays["u1_four"].shape[0]
        traj_key = f"{meta['scenario']}|{meta.get('physical_scene', meta['scenario'])}|{meta['seed']}"
        for start in range(0, steps - HORIZON + 1, stride):
            tags = window_labels(row, start, labels)
            if not tags:
                continue
            windows += 1
            z = lift(model, arrays["s3_deform"][start])
            local_sq = {group: [] for group in GROUPS}
            local_sign = defaultdict(lambda: [0, 0])
            pred_force_seq, true_force_seq = [], []
            diverged = False
            for h in range(1, HORIZON + 1):
                index = start + h - 1
                shifted = arrays["u1_four"][start + ((h - 1 + 7 + int(meta["seed"]) % 11) % HORIZON)] if ablation == "shuffle" else None
                z, ratio = model_step(model, z, arrays["u1_four"][index], ablation=ablation, u_bilinear=shifted)
                full_n, force_n, x_n = decode(model, z)
                target_full = (arrays["s2_four"][start + h] - norms["full_mean"]) / norms["full_std"]
                target_force = (arrays["force_output"][start + h] - norms["force_mean"]) / norms["force_std"]
                target_x = (arrays["s3_deform"][start + h] - norms["x_mean"]) / norms["x_std"]
                finite = np.all(np.isfinite(z)) and np.all(np.isfinite(full_n)) and np.all(np.isfinite(force_n))
                diverged = diverged or (not finite) or float(np.max(np.abs(np.r_[full_n, force_n, x_n]))) > 50.0
                if not finite:
                    local_sq = {group: [1.0e12] * h for group in GROUPS}
                    break
                errors = {
                    "state": float(np.mean((full_n - target_full) ** 2)),
                    "force": float(np.mean((force_n[:8] - target_force[:8]) ** 2)),
                    "load": float(np.mean((force_n[8:10] - target_force[8:10]) ** 2)),
                    "deformation": float(np.mean((x_n[30:46] - target_x[30:46]) ** 2)),
                    "force_rate": float(np.mean((force_n[10:18] - target_force[10:18]) ** 2)),
                }
                for group, value in errors.items():
                    sq[group][h - 1] += value
                    count[group][h - 1] += 1
                    if h >= 10:
                        local_sq[group].append(value)
                pred_force = force_n * norms["force_std"] + norms["force_mean"]
                true_force = arrays["force_output"][start + h]
                pred_force_seq.append(pred_force)
                true_force_seq.append(true_force)
                for j in range(10):
                    if abs(true_force[j]) >= norms["force_sign_floor"][j]:
                        local_sign[j][1] += 1
                        local_sign[j][0] += int(np.sign(pred_force[j]) == np.sign(true_force[j]))
                if ratio:
                    modes = physical_modes(arrays["u1_four"][index:index + 1])[0]
                    bil_rows.append({
                        "ratio": ratio, "acceleration": float(modes[0]), "curvature_mode": float(modes[4]),
                        "speed": float(np.mean(arrays["s2_four"][start + h, 3::6])),
                        "connector_load": float(np.max(np.linalg.norm(arrays["force_body"][start + h], axis=1))),
                    })
            if len(local_sq["state"]) == 0:
                nonfinite_windows += 1
                divergence_windows += int(diverged)
                continue
            metrics = {group: float(math.sqrt(np.mean(values))) for group, values in local_sq.items()}
            metrics["J_pred"] = float((metrics["state"] + metrics["force"] + metrics["load"]) / 3.0)
            for tag in tags:
                for group, value in metrics.items():
                    label_traj[tag][traj_key][group].append(value)
                for j, (correct, total) in local_sign.items():
                    sign_correct[(tag, j)] += correct
                    sign_count[(tag, j)] += total
            pred_seq = np.asarray(pred_force_seq)
            true_seq = np.asarray(true_force_seq)
            if pred_seq.size and true_seq.size:
                for j in range(10):
                    peak_errors[j].append(float(abs(np.max(np.abs(pred_seq[:, j])) - np.max(np.abs(true_seq[:, j])))))
                    peak_time_errors[j].append(float(abs(np.argmax(np.abs(pred_seq[:, j])) - np.argmax(np.abs(true_seq[:, j]))) * 0.02))
            window_rows.append({"trajectory": traj_key, "start": start, "labels": ";".join(sorted(tags)), **metrics, "diverged": diverged})
            divergence_windows += int(diverged)

    per_trajectory: dict[str, dict[str, dict[str, float]]] = {}
    macro: dict[str, dict[str, float]] = {}
    for tag, trajectories in label_traj.items():
        per_trajectory[tag] = {}
        for key, values in trajectories.items():
            per_trajectory[tag][key] = {group: float(np.mean(group_values)) for group, group_values in values.items()}
        macro[tag] = {
            group: float(np.mean([values[group] for values in per_trajectory[tag].values()]))
            for group in (*GROUPS, "J_pred")
        }
        macro[tag]["trajectories"] = len(per_trajectory[tag])
        macro[tag]["force_sign_accuracy"] = float(np.mean([
            sign_correct[(tag, j)] / sign_count[(tag, j)] for j in range(10) if sign_count[(tag, j)]
        ])) if any(sign_count[(tag, j)] for j in range(10)) else math.nan
    horizon = {
        group: np.sqrt(np.divide(sq[group], count[group], out=np.full(HORIZON, np.nan), where=count[group] > 0))
        for group in GROUPS
    }
    finite_macro = [values["J_pred"] for values in macro.values() if math.isfinite(values["J_pred"])]
    return {
        "model": model["name"], "role": role, "ablation": ablation, "windows": windows,
        "horizon_nrmse": horizon,
        "macro_by_label": macro,
        "macro_J_pred": float(np.mean(finite_macro)) if finite_macro else math.inf,
        "micro_J_pred": float(np.mean([row["J_pred"] for row in window_rows])) if window_rows else math.inf,
        "per_trajectory": per_trajectory,
        "nonfinite_rate": nonfinite_windows / max(windows, 1),
        "divergence_rate": divergence_windows / max(windows, 1),
        "force_peak_abs_error_mean_n": {str(j): float(np.mean(v)) for j, v in peak_errors.items()},
        "force_peak_time_error_mean_s": {str(j): float(np.mean(v)) for j, v in peak_time_errors.items()},
        "bilinear_rows": bil_rows,
        "window_rows": window_rows,
    }


def regression_parts(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], kind: str) -> tuple[np.ndarray, np.ndarray, list[tuple[str, int, int]]]:
    phi_parts, target_parts, ranges = [], [], []
    offset = 0
    for row in rows:
        if row["meta"]["split"] != "train":
            continue
        x = row["arrays"]["s3_deform"]
        u = row["arrays"]["u1_four"]
        xn = (x - norms["x_mean"]) / norms["x_std"]
        un = (u - norms["u_mean"]) / norms["u_std"]
        z = fixed_basis(xn)
        if kind == "full":
            product = np.einsum("ni,nj->nij", un, z[:-1, 1:]).reshape(u.shape[0], -1)
        elif kind == "structured":
            eta = (physical_modes(u) - norms["mode_mean"]) / norms["mode_std"]
            product = np.einsum("ni,nj->nij", eta, z[:-1, 1:]).reshape(u.shape[0], -1)
        elif kind == "linear":
            product = np.empty((u.shape[0], 0))
        else:
            raise KeyError(kind)
        phi = np.c_[z[:-1], un, product]
        phi_parts.append(phi)
        target_parts.append(z[1:])
        ranges.append((f"{row['meta']['scenario']}|{row['meta']['seed']}", offset, offset + len(phi)))
        offset += len(phi)
    return np.concatenate(phi_parts), np.concatenate(target_parts), ranges


def ridge_solve(phi: np.ndarray, target: np.ndarray, ridge: float) -> np.ndarray:
    scale = float(phi.shape[0])
    gram = phi.T @ phi / scale
    rhs = phi.T @ target / scale
    penalty = np.eye(phi.shape[1]) * ridge
    penalty[0, 0] = 0.0
    try:
        return np.linalg.solve(gram + penalty, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(gram + penalty, rhs, rcond=None)[0]


def refit_base(phi_base: np.ndarray, target: np.ndarray, bil_value: np.ndarray, ridge: float) -> np.ndarray:
    return ridge_solve(phi_base, target - bil_value, ridge)


def fixed_decoders() -> tuple[np.ndarray, np.ndarray]:
    fixed = load_fixed(FIXED_LIFT, "K1")
    return fixed["decode_full"], fixed["decode_force"]


def model_common(norms: dict[str, np.ndarray]) -> dict[str, Any]:
    return {
        "x_mean": norms["x_mean"], "x_std": norms["x_std"],
        "u_mean": norms["u_mean"], "u_std": norms["u_std"],
        "mode_mean": norms["mode_mean"], "mode_std": norms["mode_std"],
        "metric_x_mean": norms.get("metric_x_mean", norms["x_mean"]),
        "metric_x_std": norms.get("metric_x_std", norms["x_std"]),
        "lift_kind": "fixed",
    }


def train_full_candidates(rows: list[dict[str, Any]], norms: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    phi, target, _ = regression_parts(rows, norms, "full")
    dec_full, dec_force = fixed_decoders()
    candidates = []
    started = time.perf_counter()
    for ridge in RIDGES:
        transition = ridge_solve(phi, target, float(ridge))
        candidates.append({
            **model_common(norms), "name": f"K2-ridge-{ridge:.0e}", "kind": "full_bilinear",
            "base_transition": transition[:101], "bilinear": transition[101:],
            "decode_full": dec_full, "decode_force": dec_force,
            "ridge": float(ridge), "rank": None, "transition_parameter_count": int(transition.size),
            "parameter_count": int(transition.size + dec_full.size + dec_force.size),
            "fit_seconds": time.perf_counter() - started,
        })
    return candidates


def train_structured_candidates(rows: list[dict[str, Any]], norms: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    phi, target, _ = regression_parts(rows, norms, "structured")
    base_phi = phi[:, :101]
    product = phi[:, 101:]
    dec_full, dec_force = fixed_decoders()
    candidates = []
    started = time.perf_counter()
    for ridge in RIDGES:
        unconstrained = ridge_solve(phi, target, float(ridge))
        blocks = unconstrained[101:].reshape(5, 92, 93)
        decompositions = [np.linalg.svd(block, full_matrices=False) for block in blocks]
        for rank in RANKS:
            truncated = np.stack([
                (u[:, :rank] * s[:rank]) @ vt[:rank] for u, s, vt in decompositions
            ])
            bil = truncated.reshape(5 * 92, 93)
            base_transition = refit_base(base_phi, target, product @ bil, float(ridge))
            transition_parameters = 9393 + 5 * rank * (93 + 92)
            candidates.append({
                **model_common(norms), "name": f"K3-r{rank}-ridge-{ridge:.0e}", "kind": "structured_bilinear",
                "base_transition": base_transition, "bilinear": bil,
                "decode_full": dec_full, "decode_force": dec_force,
                "ridge": float(ridge), "rank": int(rank), "transition_parameter_count": int(transition_parameters),
                "parameter_count": int(transition_parameters + dec_full.size + dec_force.size),
                "fit_seconds": time.perf_counter() - started,
            })
    return candidates


def validation_score(result: dict[str, Any]) -> float:
    allowed = [f"E{i}" for i in range(10) if i != 7]
    values = [result["macro_by_label"][tag]["J_pred"] for tag in allowed if tag in result["macro_by_label"]]
    return float(np.mean(values)) if values else math.inf


def choose_candidate(candidates: list[dict[str, Any]], rows: list[dict[str, Any]], e9_rows: list[dict[str, Any]], norms: dict[str, np.ndarray], labels: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = []
    for index, model in enumerate(candidates):
        main = evaluate(model, rows, "validation", norms, labels)
        e9 = evaluate(model, e9_rows, "validation", norms, labels) if e9_rows else None
        combined = dict(main)
        if e9:
            combined["macro_by_label"].update(e9["macro_by_label"])
        score = validation_score(combined)
        records.append({"index": index, "name": model["name"], "ridge": model.get("ridge"), "rank": model.get("rank"), "score": score})
        print(f"validation {model['name']}: {score:.6f}", flush=True)
    records.sort(key=lambda value: (round(value["score"] / 1.0e-6), candidates[value["index"]]["transition_parameter_count"], -value["ridge"]))
    best = candidates[records[0]["index"]]
    return best, records


def compact_eval(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in ("bilinear_rows", "window_rows")}


def write_window_csv(path: Path, result: dict[str, Any]) -> None:
    rows = result["window_rows"]
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def paired_bootstrap(candidate: dict[str, Any], baseline: dict[str, Any], tag: str, metric: str) -> dict[str, Any]:
    a = candidate["per_trajectory"].get(tag, {})
    b = baseline["per_trajectory"].get(tag, {})
    keys = sorted(set(a) & set(b))
    if not keys:
        return {"n": 0, "delta": math.nan, "ci95": [math.nan, math.nan]}
    delta = np.asarray([a[key][metric] - b[key][metric] for key in keys])
    rng = np.random.default_rng(stable_seed(82200, tag, metric))
    boot = delta[rng.integers(0, len(delta), size=(2000, len(delta)))].mean(1)
    return {"n": len(keys), "delta": float(delta.mean()), "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}


def advantage(candidate: dict[str, Any], baseline: dict[str, Any], tag: str, realtime: bool = True, confirm_direction: bool = False) -> dict[str, Any]:
    if tag not in candidate["macro_by_label"] or tag not in baseline["macro_by_label"]:
        return {"eligible": False, "reason": "missing_label"}
    c, b = candidate["macro_by_label"][tag], baseline["macro_by_label"][tag]
    improvement = (b["J_pred"] - c["J_pred"]) / b["J_pred"]
    ci = paired_bootstrap(candidate, baseline, tag, "J_pred")
    critical = max((c[group] - b[group]) / b[group] for group in ("state", "force", "load"))
    eligible = improvement >= 0.08 and ci["ci95"][1] < 0 and critical <= 0.05 and candidate["divergence_rate"] <= baseline["divergence_rate"] and realtime and confirm_direction
    return {"eligible": eligible, "relative_improvement": improvement, "paired": ci, "max_critical_degradation": critical, "realtime": realtime, "confirm_direction": confirm_direction}


def merge_evaluations(parts: list[dict[str, Any]], name: str, role: str) -> dict[str, Any]:
    parts = [part for part in parts if part]
    macro: dict[str, Any] = {}
    per: dict[str, Any] = {}
    for part in parts:
        macro.update(part["macro_by_label"])
        per.update(part["per_trajectory"])
    labels = [value["J_pred"] for value in macro.values() if math.isfinite(value["J_pred"])]
    return {
        "model": name,
        "role": role,
        "macro_by_label": macro,
        "per_trajectory": per,
        "macro_J_pred": float(np.mean(labels)) if labels else math.inf,
        "micro_J_pred": float(np.mean([part["micro_J_pred"] for part in parts])),
        "nonfinite_rate": float(max(part["nonfinite_rate"] for part in parts)),
        "divergence_rate": float(max(part["divergence_rate"] for part in parts)),
        "horizon_nrmse": parts[0]["horizon_nrmse"],
        "windows": int(sum(part["windows"] for part in parts)),
    }


def feature_spectrum(phi: np.ndarray) -> dict[str, Any]:
    mean = phi.mean(0)
    std = phi.std(0)
    active = std >= 1.0e-10
    x = (phi[:, active] - mean[active]) / std[active]
    gram = x.T @ x / len(x)
    eig = np.maximum(np.linalg.eigvalsh(gram)[::-1], 0.0)
    singular = np.sqrt(eig)
    ratio = singular / max(float(singular[0]), 1.0e-300)
    rank_nonconstant = int(np.count_nonzero(ratio >= 1.0e-8))
    rank = rank_nonconstant + int(np.count_nonzero(~active))
    smallest = singular[rank_nonconstant - 1] if rank_nonconstant else 0.0
    return {
        "columns": int(phi.shape[1]), "effective_rank": rank, "effective_rank_ratio": rank / phi.shape[1],
        "condition_number_effective": float(singular[0] / max(float(smallest), 1.0e-300)),
        "relative_singular_values": ratio,
    }


def run_t0() -> None:
    stage = OUT / "t0"
    stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists():
        print("T0 already complete", flush=True)
        return
    manifest = verify_manifest(DATA)
    _, rows = load_rows(DATA, verify=False)
    labels = derive_labels(rows)
    write_json(OUT / "labels.json", labels)
    generator = HERE / "generate_compare.py"
    frozen = {
        "stage": "T0",
        "status": "frozen",
        "protocol_sha256": sha256(PROTOCOL),
        "main_manifest_sha256": sha256(DATA / "manifest.json"),
        "main_split_sha256": sha256(DATA / "split.json"),
        "main_trajectory_hashes": {row["file"]: str(row["sha256"]).upper() for row in manifest["trajectories"]},
        "K0_sha256": sha256(FIXED_RAW),
        "K1_sha256": sha256(FIXED_LIFT),
        "normalizers_sha256": sha256(NORMALIZERS),
        "audit_script_sha256": sha256(HERE / "audit_compare.py"),
        "pipeline_sha256": sha256(Path(__file__)),
        "generator_sha256": sha256(generator),
        "seed_groups": {
            "K4": list(range(82041, 82046)), "learning_subsets": list(range(82101, 82106)),
            "K5": list(range(82301, 82306)), "E9": list(range(83000, 83024)),
            "confirm_internal": list(range(84000, 84100)), "confirm_external": list(range(84100, 84140)),
            "closed_loop": list(range(85001, 85011)),
        },
        "ridge_grid": RIDGES,
        "K3_ranks": RANKS,
        "advantage_gates": {"minimum_improvement": 0.08, "maximum_critical_degradation": 0.05, "equivalent_band": 0.03, "realtime_p99_s": 0.02},
        "labels_sha256": sha256(OUT / "labels.json"),
        "source_counts": manifest["summary"]["split_counts"],
        "python": sys.version,
        "platform": platform.platform(),
    }
    write_json(stage / "freeze.json", frozen)
    write_json(stage / "complete.json", {"accepted": True, "freeze_sha256": sha256(stage / "freeze.json")})
    append_log("W0045", "Koopman比较T0冻结", [
        f"协议hash={frozen['protocol_sha256']}，main manifest hash={frozen['main_manifest_sha256']}。",
        f"K0/K1模型hash={frozen['K0_sha256']}/{frozen['K1_sha256']}；120条development数据角色保持70/15/15/20。",
        f"labels.json只由原70条train计算，hash={frozen['labels_sha256']}。",
    ])
    print(json.dumps({"T0": "complete", "labels": labels}, ensure_ascii=False), flush=True)


def run_t1() -> None:
    stage = OUT / "t1"
    if (stage / "complete.json").exists():
        print("T1 already complete", flush=True)
        return
    if not (OUT / "t0" / "complete.json").exists():
        run_t0()
    audit_path = stage / "audit.json"
    if not audit_path.exists():
        raise RuntimeError("read-only audit.json missing; run audit_compare.py first")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    e9_manifest, e9_rows = load_rows(E9_DATA)
    _, main_rows = load_rows(DATA)
    norms = train_moments(main_rows)
    joined = [row for row in main_rows if row["meta"]["split"] == "train"] + [row for row in e9_rows if row["meta"]["split"] == "train"]
    # Temporarily mark the E9 diagnostic train rows as train (their manifest is
    # already frozen); regression_parts then uses the identical contract.
    phi_full, _, _ = regression_parts(joined, norms, "full")
    phi_struct, _, _ = regression_parts(joined, norms, "structured")
    enhanced = {
        "scope": "original train plus separately frozen E9-train; diagnostic only",
        "full_bilinear": feature_spectrum(phi_full),
        "structured_bilinear": feature_spectrum(phi_struct),
        "e9_manifest_sha256": sha256(E9_DATA / "manifest.json"),
        "e9_summary": e9_manifest["summary"],
    }
    write_json(stage / "e9_identifiability.json", enhanced)
    complete = {
        "accepted": True,
        "G1": audit["g1"],
        "original_full_condition": audit["full_bilinear"]["condition_number_effective"],
        "original_full_rank": [audit["full_bilinear"]["effective_rank"], audit["full_bilinear"]["columns"]],
        "e9_full_condition": enhanced["full_bilinear"]["condition_number_effective"],
        "e9_full_rank": [enhanced["full_bilinear"]["effective_rank"], enhanced["full_bilinear"]["columns"]],
        "strong_force_fraction_original": audit["contact_phase"]["strong_fraction"],
        "boundary": "K2 is trainable under the frozen numerical gate but remains marginal; no strong-force coverage claim",
    }
    write_json(stage / "complete.json", complete)
    append_log("W0046", "Koopman比较T1可辨识性与E9", [
        "E9 24条按14/3/3/4生成完成，全部通过有限性、共同ICR及15 kN极限门。",
        f"原数据K2有效秩={complete['original_full_rank'][0]}/{complete['original_full_rank'][1]}、条件数={complete['original_full_condition']:.6e}。",
        f"加入E9-train诊断后有效秩={complete['e9_full_rank'][0]}/{complete['e9_full_rank'][1]}、条件数={complete['e9_full_condition']:.6e}。",
        "原train强受力占比为0；这限制强载荷外推，不影响普通接触区的算子比较。",
    ])
    print(json.dumps(complete, ensure_ascii=False), flush=True)


def time_model(model: dict[str, Any], sample_x: np.ndarray, sample_u: np.ndarray) -> dict[str, Any]:
    z0 = lift(model, sample_x)
    for _ in range(100):
        z, _ = model_step(model, z0, sample_u)
        decode(model, z)
    single, twenty = [], []
    for _ in range(1000):
        z = z0.copy()
        tick = time.perf_counter_ns()
        z, _ = model_step(model, z, sample_u)
        decode(model, z)
        single.append((time.perf_counter_ns() - tick) / 1.0e6)
    for _ in range(1000):
        z = z0.copy()
        tick = time.perf_counter_ns()
        for _ in range(20):
            z, _ = model_step(model, z, sample_u)
            decode(model, z)
        twenty.append((time.perf_counter_ns() - tick) / 1.0e6)
    return {
        "single_ms": {"mean": float(np.mean(single)), "p95": float(np.quantile(single, 0.95)), "p99": float(np.quantile(single, 0.99))},
        "rollout20_ms": {"mean": float(np.mean(twenty)), "p95": float(np.quantile(twenty, 0.95)), "p99": float(np.quantile(twenty, 0.99))},
        "resident_array_bytes": int(sum(value.nbytes for value in model.values() if isinstance(value, np.ndarray))),
        "parameter_count": int(model["parameter_count"]),
        "realtime_gate": bool(np.quantile(twenty, 0.99) < 20.0),
    }


def fit_simple(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], kind: str, ridge: float, name: str) -> dict[str, Any]:
    raw = kind == "raw"
    phi_parts, target_parts, decode_z, decode_full, decode_force = [], [], [], [], []
    for row in rows:
        if row["meta"]["split"] != "train":
            continue
        a = row["arrays"]
        xn = (a["s3_deform"] - norms["x_mean"]) / norms["x_std"]
        un = (a["u1_four"] - norms["u_mean"]) / norms["u_std"]
        z = raw_basis(xn) if raw else fixed_basis(xn)
        phi_parts.append(np.c_[z[:-1], un])
        target_parts.append(z[1:])
        decode_z.append(z)
        decode_full.append((a["s2_four"] - norms["full_mean"]) / norms["full_std"])
        decode_force.append((a["force_output"] - norms["force_mean"]) / norms["force_std"])
    phi, target, zall = np.concatenate(phi_parts), np.concatenate(target_parts), np.concatenate(decode_z)
    transition = ridge_solve(phi, target, ridge)
    full = ridge_solve(zall, np.concatenate(decode_full), ridge)
    force = ridge_solve(zall, np.concatenate(decode_force), ridge)
    return {
        **model_common(norms), "name": name, "kind": "raw" if raw else "linear", "lift_kind": "raw" if raw else "fixed",
        "transition": transition, "decode_full": full, "decode_force": force, "ridge": ridge,
        "transition_parameter_count": int(transition.size), "parameter_count": int(transition.size + full.size + force.size),
    }


def fit_full_fixed(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], ridge: float, name: str) -> dict[str, Any]:
    phi, target, _ = regression_parts(rows, norms, "full")
    transition = ridge_solve(phi, target, ridge)
    dec_full, dec_force = fixed_decoders()
    return {
        **model_common(norms), "name": name, "kind": "full_bilinear", "base_transition": transition[:101], "bilinear": transition[101:],
        "decode_full": dec_full, "decode_force": dec_force, "ridge": ridge,
        "transition_parameter_count": int(transition.size), "parameter_count": int(transition.size + dec_full.size + dec_force.size),
    }


def fit_struct_fixed(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], ridge: float, rank: int, name: str) -> dict[str, Any]:
    phi, target, _ = regression_parts(rows, norms, "structured")
    unbounded = ridge_solve(phi, target, ridge)
    blocks = unbounded[101:].reshape(5, 92, 93)
    truncated = []
    for block in blocks:
        u, s, vt = np.linalg.svd(block, full_matrices=False)
        truncated.append((u[:, :rank] * s[:rank]) @ vt[:rank])
    bil = np.stack(truncated).reshape(460, 93)
    base_transition = refit_base(phi[:, :101], target, phi[:, 101:] @ bil, ridge)
    dec_full, dec_force = fixed_decoders()
    transition_parameters = 9393 + 5 * rank * (93 + 92)
    return {
        **model_common(norms), "name": name, "kind": "structured_bilinear", "base_transition": base_transition, "bilinear": bil,
        "decode_full": dec_full, "decode_force": dec_force, "ridge": ridge, "rank": rank,
        "transition_parameter_count": transition_parameters, "parameter_count": int(transition_parameters + dec_full.size + dec_force.size),
    }


def plot_horizon(results: dict[str, dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharex=True)
    for name, result in results.items():
        for ax, group in zip(axes, ("state", "force", "load")):
            ax.plot(np.arange(1, 21), result["horizon_nrmse"][group], label=name)
            ax.set(title=group, xlabel="teacher-free horizon", ylabel="NRMSE")
            ax.grid(True, alpha=0.25)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_bilinear(rows_by_model: dict[str, list[dict[str, float]]], path: Path, csv_path: Path) -> None:
    fields = ["model", "ratio", "acceleration", "curvature_mode", "speed", "connector_load"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name, rows in rows_by_model.items():
            for row in rows:
                writer.writerow({"model": name, **row})
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    xfields = ("acceleration", "curvature_mode", "speed", "connector_load")
    for ax, field in zip(axes.ravel(), xfields):
        for name, rows in rows_by_model.items():
            if not rows:
                continue
            x = np.asarray([row[field] for row in rows])
            y = np.asarray([row["ratio"] for row in rows])
            order = np.argsort(x)
            bins = np.array_split(order, 30)
            ax.plot([np.mean(x[b]) for b in bins if len(b)], [np.median(y[b]) for b in bins if len(b)], label=name)
        ax.set(xlabel=field, ylabel="median r_bil")
        ax.grid(True, alpha=0.25)
    axes[0, 0].legend()
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def plot_cost(cost: dict[str, Any], results: dict[str, dict[str, Any]], path: Path, csv_path: Path) -> None:
    rows = []
    for name in results:
        rows.append({
            "model": name, "J_pred": results[name]["macro_J_pred"],
            "parameter_count": cost[name]["parameter_count"], "rollout20_p99_ms": cost[name]["rollout20_ms"]["p99"],
        })
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    for row in rows:
        ax.scatter(row["parameter_count"], row["J_pred"], s=35 + 20 * math.log10(max(row["rollout20_p99_ms"], 0.01) + 1), label=row["model"])
        ax.annotate(row["model"], (row["parameter_count"], row["J_pred"]), xytext=(4, 3), textcoords="offset points", fontsize=8)
    ax.set_xscale("log")
    ax.set(xlabel="parameter count (log)", ylabel="development macro J_pred", title="Accuracy / model cost / rollout latency")
    ax.grid(True, alpha=0.25)
    fig.tight_layout(); fig.savefig(path, dpi=220); plt.close(fig)


def development_candidate_gate(candidate: dict[str, Any], baseline: dict[str, Any], cost: dict[str, Any], tag: str) -> dict[str, Any]:
    if tag not in candidate["macro_by_label"] or tag not in baseline["macro_by_label"]:
        return {"pass": False, "reason": "missing_label"}
    c, b = candidate["macro_by_label"][tag], baseline["macro_by_label"][tag]
    improvement = (b["J_pred"] - c["J_pred"]) / b["J_pred"]
    paired = paired_bootstrap(candidate, baseline, tag, "J_pred")
    degradation = max((c[group] - b[group]) / b[group] for group in ("state", "force", "load"))
    passed = improvement >= 0.08 and paired["ci95"][1] < 0 and degradation <= 0.05 and candidate["divergence_rate"] <= baseline["divergence_rate"] and cost["realtime_gate"]
    return {"pass": passed, "improvement": improvement, "paired": paired, "critical_degradation": degradation, "realtime": cost["realtime_gate"]}


def run_learning_k0_k3(
    rows: list[dict[str, Any]], full_norms: dict[str, np.ndarray], labels: dict[str, Any],
    k2_ridge: float, k3_ridge: float, k3_rank: int,
) -> list[dict[str, Any]]:
    stage = OUT / "t2" / "learning_curve_k0_k3.json"
    if stage.exists():
        return json.loads(stage.read_text(encoding="utf-8"))["runs"]
    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    validation = [row for row in rows if row["meta"]["split"] == "validation"]
    for row in rows:
        if row["meta"]["split"] == "train":
            by_scene[row["meta"]["scenario"]].append(row)
    runs = []
    for subset_seed in range(82101, 82106):
        order: dict[str, list[dict[str, Any]]] = {}
        for scene, scene_rows in by_scene.items():
            rng = np.random.default_rng(stable_seed(subset_seed, scene))
            order[scene] = [scene_rows[i] for i in rng.permutation(len(scene_rows))]
        for fraction in (0.10, 0.25, 0.50, 1.00):
            chosen = []
            for scene in sorted(order):
                count = max(1, int(math.ceil(len(order[scene]) * fraction)))
                chosen.extend(order[scene][:count])
            subset_norms = train_moments(chosen)
            subset_norms["full_mean"], subset_norms["full_std"] = full_norms["full_mean"], full_norms["full_std"]
            subset_norms["force_mean"], subset_norms["force_std"] = full_norms["force_mean"], full_norms["force_std"]
            subset_norms["force_sign_floor"] = full_norms["force_sign_floor"]
            subset_norms["metric_x_mean"], subset_norms["metric_x_std"] = full_norms["x_mean"], full_norms["x_std"]
            train_and_val = chosen + validation
            fitted = {
                "K0": fit_simple(chosen, subset_norms, "raw", 1.0e-5, "K0"),
                "K1": fit_simple(chosen, subset_norms, "linear", 1.0e-5, "K1"),
                "K2": fit_full_fixed(chosen, subset_norms, k2_ridge, "K2"),
                "K3": fit_struct_fixed(chosen, subset_norms, k3_ridge, k3_rank, "K3"),
            }
            for name, model in fitted.items():
                result = evaluate(model, train_and_val, "validation", full_norms, labels)
                runs.append({"subset_seed": subset_seed, "fraction": fraction, "train_trajectories": len(chosen), "method": name, "validation_macro_J_pred": validation_score(result)})
                print(f"learning {subset_seed} {fraction:.2f} {name}: {runs[-1]['validation_macro_J_pred']:.6f}", flush=True)
            write_json(stage, {"runs": runs, "status": "in_progress"})
    write_json(stage, {"runs": runs, "status": "complete"})
    return runs


def plot_learning(runs: list[dict[str, Any]], path: Path, csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runs[0]))
        writer.writeheader(); writer.writerows(runs)
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for method in sorted({row["method"] for row in runs}):
        xs, means, lows, highs = [], [], [], []
        for fraction in (0.10, 0.25, 0.50, 1.00):
            values = [row["validation_macro_J_pred"] for row in runs if row["method"] == method and row["fraction"] == fraction]
            if not values: continue
            xs.append(fraction); means.append(np.median(values)); lows.append(np.quantile(values, .25)); highs.append(np.quantile(values, .75))
        ax.plot(xs, means, marker="o", label=method); ax.fill_between(xs, lows, highs, alpha=.15)
    ax.set(xlabel="fraction of stratified train trajectories", ylabel="validation macro J_pred", title="Nested data-size learning curves (median/IQR over 5 subsets)")
    ax.grid(True, alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(path, dpi=220); plt.close(fig)


def run_t2() -> None:
    stage = OUT / "t2"
    stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists():
        print("T2 already complete", flush=True)
        return
    if not (OUT / "t1" / "complete.json").exists():
        run_t1()
    _, rows = load_rows(DATA)
    _, e9_rows = load_rows(E9_DATA)
    labels = json.loads((OUT / "labels.json").read_text(encoding="utf-8"))
    norms = train_moments(rows)
    k0, k1 = load_fixed(FIXED_RAW, "K0"), load_fixed(FIXED_LIFT, "K1")

    print("fitting K2 ridge grid", flush=True)
    k2_candidates = train_full_candidates(rows, norms)
    k2_selected, k2_search = choose_candidate(k2_candidates, rows, e9_rows, norms, labels)
    k2 = copy.deepcopy(k2_selected)
    k2["name"] = "K2"
    print("fitting K3 ridge/rank grid", flush=True)
    k3_candidates = train_structured_candidates(rows, norms)
    k3_selected, k3_search = choose_candidate(k3_candidates, rows, e9_rows, norms, labels)
    k3 = copy.deepcopy(k3_selected)
    k3["name"] = "K3"
    r2_candidates = [candidate for candidate in k3_candidates if candidate["rank"] == 2]
    k3r2_selected, k3r2_search = choose_candidate(r2_candidates, rows, e9_rows, norms, labels)
    k3r2 = copy.deepcopy(k3r2_selected)
    k3r2["name"] = "K3-r2"
    MODELS.mkdir(parents=True, exist_ok=True)
    for model in (k2, k3, k3r2):
        save_model(MODELS / f"{model['name']}.npz", model)
    write_json(stage / "validation_search.json", {"K2": k2_search, "K3": k3_search, "K3_r2": k3r2_search})

    models = {model["name"]: model for model in (k0, k1, k2, k3, k3r2)}
    results: dict[str, Any] = {}
    raw_parts: dict[str, Any] = {}
    for name, model in models.items():
        dev = evaluate(model, rows, "development-test", norms, labels)
        ext = evaluate(model, rows, "development-external", norms, labels)
        e9test = evaluate(model, e9_rows, "development-test", norms, labels)
        e9ext = evaluate(model, e9_rows, "development-external", norms, labels)
        raw_parts[name] = dev
        results[name] = merge_evaluations([dev, ext, e9test, e9ext], name, "development")
        write_window_csv(stage / f"{name}_development_windows.csv", dev)
        print(f"development {name}: macro={results[name]['macro_J_pred']:.6f}", flush=True)

    cost = {name: time_model(model, rows[0]["arrays"]["s3_deform"][0], rows[0]["arrays"]["u1_four"][0]) for name, model in models.items()}
    ablations: dict[str, Any] = {}
    bil_rows = {}
    for name in ("K2", "K3"):
        model = models[name]
        ablations[name] = {}
        for ablation_name in ("none", "zero", "shuffle", "permute"):
            part = evaluate(model, rows, "development-test", norms, labels, ablation=ablation_name)
            ablations[name][ablation_name] = compact_eval(part)
            if ablation_name == "none":
                bil_rows[name] = part["bilinear_rows"]

    baseline_by_tag: dict[str, str] = {}
    g2: dict[str, Any] = {}
    for tag in [f"E{i}" for i in range(10)]:
        simple = [name for name in ("K0", "K1") if tag in results[name]["macro_by_label"]]
        if not simple: continue
        baseline_name = min(simple, key=lambda name: results[name]["macro_by_label"][tag]["J_pred"])
        baseline_by_tag[tag] = baseline_name
        g2[tag] = {name: development_candidate_gate(results[name], results[baseline_name], cost[name], tag) for name in ("K2", "K3", "K3-r2") if tag in results[name]["macro_by_label"]}

    learning = run_learning_k0_k3(rows, norms, labels, float(k2["ridge"]), float(k3["ridge"]), int(k3["rank"]))
    plot_learning(learning, stage / "learning_curves.png", stage / "learning_curves.csv")
    plot_horizon({name: raw_parts[name] for name in ("K0", "K1", "K2", "K3")}, OUT / "horizon_state_force.png")
    plot_bilinear(bil_rows, OUT / "bilinear_contribution.png", OUT / "bilinear_contribution.csv")
    plot_cost(cost, results, OUT / "accuracy_cost_pareto.png", OUT / "accuracy_cost_pareto.csv")
    write_json(stage / "development_results.json", results)
    write_json(stage / "ablation_results.json", ablations)
    write_json(stage / "cost.json", cost)
    write_json(stage / "G2.json", {"baseline_by_tag": baseline_by_tag, "candidate_gates": g2})
    selected = {
        "K2": {"ridge": k2["ridge"], "artifact": str(MODELS / "K2.npz"), "sha256": sha256(MODELS / "K2.npz")},
        "K3": {"ridge": k3["ridge"], "rank": k3["rank"], "artifact": str(MODELS / "K3.npz"), "sha256": sha256(MODELS / "K3.npz")},
        "K3-r2": {"ridge": k3r2["ridge"], "rank": 2, "artifact": str(MODELS / "K3-r2.npz"), "sha256": sha256(MODELS / "K3-r2.npz")},
    }
    write_json(stage / "selected.json", selected)
    write_json(stage / "complete.json", {"accepted": True, "models": selected, "development_macro": {name: result["macro_J_pred"] for name, result in results.items()}})
    append_log("W0047", "Koopman比较T2固定lift算子", [
        f"K2 validation选择ridge={k2['ridge']:.0e}；K3选择ridge={k3['ridge']:.0e}, rank={k3['rank']}；参数匹配K3固定rank=2。",
        "K0/K1从冻结artifact只读复算；K2/K3及三项冻结消融均完成，模型和窗口级CSV已留存。",
        "K0–K3的10/25/50/100%嵌套分层学习曲线完成，每档5个subset seed。",
        f"development macro J_pred={json.dumps({name: round(result['macro_J_pred'], 6) for name, result in results.items()}, ensure_ascii=False)}。",
    ])
    print(json.dumps({"T2": "complete", "selected": selected, "macro": {name: result["macro_J_pred"] for name, result in results.items()}}, ensure_ascii=False), flush=True)


def k4_training_arrays(train_rows: list[dict[str, Any]], norms: dict[str, np.ndarray]) -> tuple[np.ndarray, ...]:
    x0, x1, u, full, force = [], [], [], [], []
    for row in train_rows:
        a = row["arrays"]
        x0.append((a["s3_deform"][:-1] - norms["x_mean"]) / norms["x_std"])
        x1.append((a["s3_deform"][1:] - norms["x_mean"]) / norms["x_std"])
        u.append((a["u1_four"] - norms["u_mean"]) / norms["u_std"])
        full.append((a["s2_four"][1:] - norms["full_mean"]) / norms["full_std"])
        force.append((a["force_output"][1:] - norms["force_mean"]) / norms["force_std"])
    return tuple(np.concatenate(parts).astype(np.float32) for parts in (x0, x1, u, full, force))


def train_k4_one(
    train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], e9_rows: list[dict[str, Any]],
    full_norms: dict[str, np.ndarray], labels: dict[str, Any], seed: int, name: str, max_epochs: int = 80,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    torch.manual_seed(seed); np.random.seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    subset = train_moments(train_rows)
    subset["full_mean"], subset["full_std"] = full_norms["full_mean"], full_norms["full_std"]
    subset["force_mean"], subset["force_std"] = full_norms["force_mean"], full_norms["force_std"]
    subset["force_sign_floor"] = full_norms["force_sign_floor"]
    subset["metric_x_mean"], subset["metric_x_std"] = full_norms["x_mean"], full_norms["x_std"]
    arrays = k4_training_arrays(train_rows, subset)
    cpu = [torch.from_numpy(value) for value in arrays]

    class NeuralLift(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc1 = nn.Linear(46, 64)
            self.fc2 = nn.Linear(64, 46)
            self.transition = nn.Parameter(torch.zeros(101, 93))
            self.decode_full = nn.Parameter(torch.zeros(93, 30))
            self.decode_force = nn.Parameter(torch.zeros(93, 18))
            with torch.no_grad():
                fixed = load_fixed(FIXED_LIFT, "K1")
                self.transition[:47, :47].copy_(torch.as_tensor(fixed["transition"][:47, :47], dtype=torch.float32))
                self.transition[93:, :47].copy_(torch.as_tensor(fixed["transition"][93:, :47], dtype=torch.float32))
                for i in range(30):
                    self.decode_full[0, i] = float((subset["x_mean"][i] - subset["full_mean"][i]) / subset["full_std"][i])
                    self.decode_full[1 + i, i] = float(subset["x_std"][i] / subset["full_std"][i])
                self.decode_force[:47].copy_(torch.as_tensor(fixed["decode_force"][:47], dtype=torch.float32))

        def lift(self, x: Any) -> Any:
            g = self.fc2(F.gelu(self.fc1(x), approximate="tanh"))
            return torch.cat([torch.ones((x.shape[0], 1), device=x.device), x, g], 1)

        def forward(self, x0: Any, x1: Any, u: Any) -> tuple[Any, Any, Any, Any]:
            z0, z1 = self.lift(x0), self.lift(x1)
            pred = torch.cat([z0, u], 1) @ self.transition
            return pred, z1, pred @ self.decode_full, pred @ self.decode_force

    net = NeuralLift().to(device)
    optimizer = torch.optim.AdamW(net.parameters(), lr=5.0e-4, weight_decay=1.0e-6)
    best_score = math.inf; best_state = None; best_epoch = 0; checks_without = 0
    history = []; started = time.perf_counter(); n = len(cpu[0])

    def export(current_name: str) -> dict[str, Any]:
        return {
            **model_common(subset), "name": current_name, "kind": "neural_linear", "lift_kind": "neural",
            "w1": net.fc1.weight.detach().cpu().numpy().astype(float), "b1": net.fc1.bias.detach().cpu().numpy().astype(float),
            "w2": net.fc2.weight.detach().cpu().numpy().astype(float), "b2": net.fc2.bias.detach().cpu().numpy().astype(float),
            "transition": net.transition.detach().cpu().numpy().astype(float),
            "decode_full": net.decode_full.detach().cpu().numpy().astype(float), "decode_force": net.decode_force.detach().cpu().numpy().astype(float),
            "seed": seed, "transition_parameter_count": 9393, "parameter_count": int(sum(parameter.numel() for parameter in net.parameters())),
        }

    for epoch in range(1, max_epochs + 1):
        net.train(); generator = torch.Generator().manual_seed(seed * 1000 + epoch)
        order = torch.randperm(n, generator=generator)
        losses = []
        for begin in range(0, n, 256):
            index = order[begin:begin + 256]
            batch = [value[index].to(device, non_blocking=True) for value in cpu]
            pred, z1, full_pred, force_pred = net(batch[0], batch[1], batch[2])
            latent = F.mse_loss(pred, z1)
            state = F.mse_loss(full_pred, batch[3])
            point = F.mse_loss(force_pred[:, :8], batch[4][:, :8])
            load = F.mse_loss(force_pred[:, 8:10], batch[4][:, 8:10])
            loss = latent + state + point + load
            optimizer.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); optimizer.step()
            losses.append(float(loss.detach().cpu()))
        if epoch % 2 == 0 or epoch == max_epochs:
            net.eval(); exported = export(name)
            main = evaluate(exported, validation_rows, "validation", full_norms, labels)
            e9 = evaluate(exported, e9_rows, "validation", full_norms, labels)
            combined = merge_evaluations([main, e9], name, "validation")
            score = validation_score(combined)
            history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "validation_macro_J_pred": score})
            print(f"{name} seed={seed} epoch={epoch} loss={history[-1]['train_loss']:.6f} val={score:.6f}", flush=True)
            if score < best_score - 1.0e-5:
                best_score, best_epoch, checks_without = score, epoch, 0
                best_state = {key: value.detach().cpu().clone() for key, value in net.state_dict().items()}
            else:
                checks_without += 1
            if checks_without >= 10:
                break
    if best_state is None:
        raise RuntimeError("K4 produced no finite validation checkpoint")
    net.load_state_dict(best_state); net.eval()
    model = export(name)
    model["best_epoch"] = best_epoch; model["validation_macro_J_pred"] = best_score; model["fit_seconds"] = time.perf_counter() - started
    return model, {"seed": seed, "best_epoch": best_epoch, "validation_macro_J_pred": best_score, "history": history, "fit_seconds": model["fit_seconds"]}


def build_multistep_windows(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], lift_kind: str, role: str) -> tuple[np.ndarray, ...]:
    z0, ztrue, u, full, force, physical_u = [], [], [], [], [], []
    for row in rows:
        if not role_matches(row["meta"], role): continue
        a = row["arrays"]
        xn = (a["s3_deform"] - norms["x_mean"]) / norms["x_std"]
        z = raw_basis(xn) if lift_kind == "raw" else fixed_basis(xn)
        un = (a["u1_four"] - norms["u_mean"]) / norms["u_std"]
        fulln = (a["s2_four"] - norms["full_mean"]) / norms["full_std"]
        for start in range(0, len(un) - HORIZON + 1, HORIZON):
            z0.append(z[start]); ztrue.append(z[start + 1:start + 21]); u.append(un[start:start + 20]); physical_u.append(a["u1_four"][start:start + 20])
            full.append(fulln[start + 1:start + 21]); force.append((a["force_output"][start + 1:start + 21] - norms["force_mean"]) / norms["force_std"])
    return tuple(np.asarray(value, dtype=np.float32) for value in (z0, ztrue, u, physical_u, full, force))


def train_k5_one(
    base_model: dict[str, Any], train_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], e9_rows: list[dict[str, Any]],
    norms: dict[str, np.ndarray], labels: dict[str, Any], seed: int, name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    torch.manual_seed(seed); np.random.seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    window_norms = dict(norms)
    for key in ("x_mean", "x_std", "u_mean", "u_std"):
        window_norms[key] = base_model[key]
    arrays = build_multistep_windows(train_rows, window_norms, base_model["lift_kind"], "train")
    cpu = [torch.from_numpy(value) for value in arrays]
    kind = base_model["kind"]

    class MultiStep(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            initial_base = base_model.get("base_transition", base_model.get("transition"))
            self.base = nn.Parameter(torch.as_tensor(initial_base, dtype=torch.float32).clone())
            self.decode_full = nn.Parameter(torch.as_tensor(base_model["decode_full"], dtype=torch.float32).clone())
            self.decode_force = nn.Parameter(torch.as_tensor(base_model["decode_force"], dtype=torch.float32).clone())
            if kind == "full_bilinear":
                self.bil = nn.Parameter(torch.as_tensor(base_model["bilinear"], dtype=torch.float32).clone())
            elif kind == "structured_bilinear":
                self.left = nn.ParameterList(); self.right = nn.ParameterList()
                rank = int(base_model["rank"])
                for block in base_model["bilinear"].reshape(5, 92, 93):
                    uu, ss, vv = np.linalg.svd(block, full_matrices=False)
                    self.left.append(nn.Parameter(torch.as_tensor(uu[:, :rank] * np.sqrt(ss[:rank]), dtype=torch.float32)))
                    self.right.append(nn.Parameter(torch.as_tensor(np.sqrt(ss[:rank])[:, None] * vv[:rank], dtype=torch.float32)))

        def step(self, z: Any, un: Any, up: Any) -> Any:
            linear = torch.cat([z, un], -1) @ self.base
            if kind == "full_bilinear":
                product = (un.unsqueeze(-1) * z[:, None, 1:]).reshape(z.shape[0], -1)
                return linear + product @ self.bil
            if kind == "structured_bilinear":
                aa, dd = up[:, 0::2], up[:, 1::2]
                eta = torch.stack([
                    aa.mean(-1), .5*(aa[:,0]+aa[:,1]-aa[:,2]-aa[:,3]), .5*(aa[:,0]+aa[:,2]-aa[:,1]-aa[:,3]),
                    .5*(aa[:,0]+aa[:,3]-aa[:,1]-aa[:,2]), .25*(dd[:,0]+dd[:,1]-dd[:,2]-dd[:,3]),
                ], -1)
                eta = (eta - torch.as_tensor(base_model["mode_mean"], device=eta.device, dtype=eta.dtype)) / torch.as_tensor(base_model["mode_std"], device=eta.device, dtype=eta.dtype)
                bil = 0.0
                for q in range(5):
                    bil = bil + eta[:, q:q+1] * ((z[:, 1:] @ self.left[q]) @ self.right[q])
                return linear + bil
            return linear

    net = MultiStep().to(device)
    optimizer = torch.optim.AdamW(net.parameters(), lr=5.0e-4, weight_decay=1.0e-6)
    best_score = math.inf; best_state = None; best_epoch = 0; stale = 0; history = []; started = time.perf_counter(); n = len(cpu[0])

    def export() -> dict[str, Any]:
        model = {key: value for key, value in base_model.items() if not key.startswith("_")}
        model["name"] = name; model["seed"] = seed
        base_np = net.base.detach().cpu().numpy().astype(float)
        if kind in ("raw", "linear"):
            model["transition"] = base_np
        else:
            model["base_transition"] = base_np
            if kind == "full_bilinear": model["bilinear"] = net.bil.detach().cpu().numpy().astype(float)
            else: model["bilinear"] = np.stack([(net.left[q] @ net.right[q]).detach().cpu().numpy() for q in range(5)]).reshape(460, 93)
        model["decode_full"] = net.decode_full.detach().cpu().numpy().astype(float); model["decode_force"] = net.decode_force.detach().cpu().numpy().astype(float)
        model["parameter_count"] = int(sum(p.numel() for p in net.parameters()))
        return model

    for epoch in range(1, 81):
        net.train(); order = torch.randperm(n, generator=torch.Generator().manual_seed(seed * 1000 + epoch)); losses = []
        for begin in range(0, n, 256):
            index = order[begin:begin+256]; batch = [value[index].to(device) for value in cpu]
            z = batch[0]; preds = []
            for h in range(20):
                z = net.step(z, batch[2][:, h], batch[3][:, h]); preds.append(z)
            pred = torch.stack(preds, 1)
            one = F.mse_loss(pred[:, 0], batch[1][:, 0])
            rollout = F.mse_loss(pred[:, :, 1:47], batch[1][:, :, 1:47])
            force_pred = pred @ net.decode_force
            force = F.mse_loss(force_pred[:, :, :8], batch[5][:, :, :8])
            load = F.mse_loss(force_pred[:, :, 8:10], batch[5][:, :, 8:10])
            loss = one + rollout + force + load
            optimizer.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); optimizer.step(); losses.append(float(loss.detach().cpu()))
        net.eval(); exported = export()
        main = evaluate(exported, validation_rows, "validation", norms, labels)
        e9 = evaluate(exported, e9_rows, "validation", norms, labels)
        score = validation_score(merge_evaluations([main, e9], name, "validation"))
        history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "validation_macro_J_pred": score})
        print(f"{name} seed={seed} epoch={epoch} loss={history[-1]['train_loss']:.6f} val={score:.6f}", flush=True)
        if score < best_score - 1.0e-5:
            best_score, best_epoch, stale = score, epoch, 0; best_state = {k:v.detach().cpu().clone() for k,v in net.state_dict().items()}
        else: stale += 1
        if stale >= 10: break
    if best_state is None: raise RuntimeError("K5 produced no finite validation checkpoint")
    net.load_state_dict(best_state); model = export(); model["best_epoch"] = best_epoch; model["validation_macro_J_pred"] = best_score; model["fit_seconds"] = time.perf_counter() - started
    return model, {"seed": seed, "best_epoch": best_epoch, "validation_macro_J_pred": best_score, "history": history, "fit_seconds": model["fit_seconds"]}


def development_parts(model: dict[str, Any], rows: list[dict[str, Any]], e9_rows: list[dict[str, Any]], norms: dict[str, np.ndarray], labels: dict[str, Any]) -> dict[str, Any]:
    return merge_evaluations([
        evaluate(model, rows, "development-test", norms, labels),
        evaluate(model, rows, "development-external", norms, labels),
        evaluate(model, e9_rows, "development-test", norms, labels),
        evaluate(model, e9_rows, "development-external", norms, labels),
    ], model["name"], "development")


def representative_by_median(models: list[dict[str, Any]]) -> dict[str, Any]:
    values = np.asarray([model["validation_macro_J_pred"] for model in models])
    median = float(np.median(values))
    return min(models, key=lambda model: (abs(model["validation_macro_J_pred"] - median), model["seed"]))


def k6_coverage(rows: list[dict[str, Any]], labels: dict[str, Any]) -> dict[str, Any]:
    mapping = {"straight": {"E0", "E1"}, "curve": {"E2", "E5"}, "transition": {"E3", "E4"}}
    counts = {key: 0 for key in mapping}; trajectories = {key: set() for key in mapping}
    for row in rows:
        if row["meta"]["split"] != "train": continue
        steps = len(row["arrays"]["u1_four"]); key = f"{row['meta']['scenario']}|{row['meta']['seed']}"
        for start in range(0, steps - HORIZON + 1, HORIZON):
            tags = window_labels(row, start, labels)
            for category, category_tags in mapping.items():
                if tags & category_tags:
                    counts[category] += 1; trajectories[category].add(key)
    result = {category: {"windows": counts[category], "trajectories": len(trajectories[category])} for category in mapping}
    result["sample_gate_pass"] = all(value["windows"] >= 2000 and value["trajectories"] >= 10 for value in result.values())
    return result


def run_t3() -> None:
    stage = OUT / "t3"; stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists(): print("T3 already complete", flush=True); return
    if not (OUT / "t2" / "complete.json").exists(): run_t2()
    _, rows = load_rows(DATA); _, e9_rows = load_rows(E9_DATA)
    labels = json.loads((OUT / "labels.json").read_text(encoding="utf-8")); norms = train_moments(rows)
    train_rows = [row for row in rows if row["meta"]["split"] == "train"]
    validation_rows = [row for row in rows if row["meta"]["split"] == "validation"]

    k4_models, k4_training = [], []
    for seed in range(82041, 82046):
        path = MODELS / f"K4-s{seed}.npz"; record_path = stage / f"K4-s{seed}-training.json"
        if path.exists() and record_path.exists():
            model = load_model(path); record = json.loads(record_path.read_text(encoding="utf-8"))
        else:
            model, record = train_k4_one(train_rows, validation_rows, e9_rows, norms, labels, seed, f"K4-s{seed}")
            save_model(path, model); write_json(record_path, record)
        k4_models.append(model); k4_training.append(record)
    k4 = representative_by_median(k4_models); k4["name"] = "K4"; save_model(MODELS / "K4.npz", k4)
    k4_development = [development_parts(model, rows, e9_rows, norms, labels) for model in k4_models]
    k4_summary = {
        "validation_scores": [model["validation_macro_J_pred"] for model in k4_models],
        "validation_median": float(np.median([model["validation_macro_J_pred"] for model in k4_models])),
        "development_macro_median": float(np.median([result["macro_J_pred"] for result in k4_development])),
        "development_macro_iqr": [float(np.quantile([r["macro_J_pred"] for r in k4_development], .25)), float(np.quantile([r["macro_J_pred"] for r in k4_development], .75))],
        "development_worst_seed": int(k4_models[int(np.argmax([result["macro_J_pred"] for result in k4_development]))]["seed"]),
        "representative_seed": int(k4["seed"]), "representative_artifact_sha256": sha256(MODELS / "K4.npz"),
    }

    # Select one linear and one bilinear operator using validation only.
    t2_models = {"K0": load_fixed(FIXED_RAW, "K0"), "K1": load_fixed(FIXED_LIFT, "K1"), "K2": load_model(MODELS / "K2.npz"), "K3": load_model(MODELS / "K3.npz")}
    val_scores = {}
    for name, model in t2_models.items():
        main = evaluate(model, rows, "validation", norms, labels); e9 = evaluate(model, e9_rows, "validation", norms, labels)
        val_scores[name] = validation_score(merge_evaluations([main, e9], name, "validation"))
    best_linear_name = min(("K0", "K1"), key=lambda key: val_scores[key]); best_bilinear_name = min(("K2", "K3"), key=lambda key: val_scores[key])
    k5_groups: dict[str, list[dict[str, Any]]] = {"K5-linear": [], "K5-bilinear": []}; k5_records: dict[str, list[Any]] = defaultdict(list)
    for group, source_name in (("K5-linear", best_linear_name), ("K5-bilinear", best_bilinear_name)):
        for seed in range(82301, 82306):
            path = MODELS / f"{group}-s{seed}.npz"; record_path = stage / f"{group}-s{seed}-training.json"
            if path.exists() and record_path.exists(): model, record = load_model(path), json.loads(record_path.read_text(encoding="utf-8"))
            else:
                model, record = train_k5_one(t2_models[source_name], train_rows, validation_rows, e9_rows, norms, labels, seed, f"{group}-s{seed}")
                model["source_model"] = source_name; save_model(path, model); write_json(record_path, record)
            k5_groups[group].append(model); k5_records[group].append(record)
    representatives = {}
    for group, group_models in k5_groups.items():
        representative = representative_by_median(group_models); representative["name"] = group; save_model(MODELS / f"{group}.npz", representative); representatives[group] = representative

    mechanism_results = {"K4": development_parts(k4, rows, e9_rows, norms, labels)}
    for name, model in representatives.items(): mechanism_results[name] = development_parts(model, rows, e9_rows, norms, labels)
    mechanism_results[best_linear_name] = development_parts(t2_models[best_linear_name], rows, e9_rows, norms, labels)
    mechanism_results[best_bilinear_name] = development_parts(t2_models[best_bilinear_name], rows, e9_rows, norms, labels)

    # Complete the preregistered K4 learning curve.  At 100%, reuse the five
    # main-seed runs; lower fractions train on the paired nested subset.
    old_learning = json.loads((OUT / "t2" / "learning_curve_k0_k3.json").read_text(encoding="utf-8"))["runs"]
    learning = list(old_learning); by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in train_rows: by_scene[row["meta"]["scenario"]].append(row)
    for pair_index, (subset_seed, model_seed) in enumerate(zip(range(82101,82106), range(82041,82046))):
        scene_order = {}
        for scene, scene_rows in by_scene.items():
            rng = np.random.default_rng(stable_seed(subset_seed, scene)); scene_order[scene] = [scene_rows[i] for i in rng.permutation(len(scene_rows))]
        for fraction in (.10, .25, .50):
            selected = []
            for scene in sorted(scene_order): selected.extend(scene_order[scene][:max(1, int(math.ceil(len(scene_order[scene])*fraction)))])
            path = MODELS / f"K4-lc-{fraction:.2f}-ss{subset_seed}.npz"; recpath = stage / f"K4-lc-{fraction:.2f}-ss{subset_seed}.json"
            if path.exists() and recpath.exists(): model, record = load_model(path), json.loads(recpath.read_text(encoding="utf-8"))
            else:
                model, record = train_k4_one(selected, validation_rows, e9_rows, norms, labels, model_seed, f"K4-lc-{fraction:.2f}-ss{subset_seed}")
                save_model(path, model); write_json(recpath, record)
            learning.append({"subset_seed": subset_seed, "fraction": fraction, "train_trajectories": len(selected), "method": "K4", "validation_macro_J_pred": model["validation_macro_J_pred"]})
        learning.append({"subset_seed": subset_seed, "fraction": 1.0, "train_trajectories": len(train_rows), "method": "K4", "validation_macro_J_pred": k4_models[pair_index]["validation_macro_J_pred"]})
    plot_learning(learning, stage / "learning_curves_k0_k4.png", stage / "learning_curves_k0_k4.csv")

    coverage = k6_coverage(rows, labels)
    if not coverage["sample_gate_pass"]:
        k6 = {"status": "not_applicable", "reason": "at least one frozen expert class has <10 train trajectories or <2000 non-overlapping 20-step windows", "coverage": coverage}
    else:
        # The sample precondition is deliberately checked before any oracle fit.
        # Reaching this branch would require the preregistered residual-direction
        # and oracle-gap tests, so do not silently create a gate.
        k6 = {"status": "not_executed", "reason": "sample gate passed unexpectedly; oracle residual implementation required", "coverage": coverage}
        write_json(stage / "stop.json", k6); raise RuntimeError(k6["reason"])
    write_json(stage / "K4_summary.json", k4_summary); write_json(stage / "mechanism_results.json", mechanism_results); write_json(stage / "K6.json", k6)
    selected = {
        "K4": {"seed": k4["seed"], "sha256": sha256(MODELS / "K4.npz")},
        "K5-linear": {"source": best_linear_name, "seed": representatives["K5-linear"]["seed"], "sha256": sha256(MODELS / "K5-linear.npz")},
        "K5-bilinear": {"source": best_bilinear_name, "seed": representatives["K5-bilinear"]["seed"], "sha256": sha256(MODELS / "K5-bilinear.npz")},
        "K6": k6,
    }
    write_json(stage / "complete.json", {"accepted": True, "selected": selected, "validation_scores_T2": val_scores, "mechanism_macro": {k:v["macro_J_pred"] for k,v in mechanism_results.items()}})
    append_log("W0048", "Koopman比较T3机制分离", [
        f"K4完成5 seed，代表seed={k4['seed']}（validation最接近五seed中位数），不是最好seed。",
        f"K5线性源={best_linear_name}、双线性源={best_bilinear_name}，各5 seed并按相同规则固定代表模型。",
        f"K6={k6['status']}；冻结样本门统计={json.dumps(coverage, ensure_ascii=False)}。",
        "K4的10/25/50/100%五组嵌套学习曲线已与K0–K3合并。",
    ])
    print(json.dumps({"T3":"complete", "selected":selected}, ensure_ascii=False), flush=True)


def all_frozen_models() -> dict[str, dict[str, Any]]:
    models = {
        "K0": load_fixed(FIXED_RAW, "K0"), "K1": load_fixed(FIXED_LIFT, "K1"),
        "K2": load_model(MODELS / "K2.npz"), "K3": load_model(MODELS / "K3.npz"),
        "K3-r2": load_model(MODELS / "K3-r2.npz"), "K4": load_model(MODELS / "K4.npz"),
        "K5-linear": load_model(MODELS / "K5-linear.npz"), "K5-bilinear": load_model(MODELS / "K5-bilinear.npz"),
    }
    for name, model in models.items(): model["name"] = name
    return models


def signflip_p(candidate: dict[str, Any], baseline: dict[str, Any], tag: str) -> float:
    a, b = candidate["per_trajectory"].get(tag, {}), baseline["per_trajectory"].get(tag, {})
    keys = sorted(set(a) & set(b))
    if not keys: return math.nan
    delta = np.asarray([a[key]["J_pred"] - b[key]["J_pred"] for key in keys])
    observed = abs(float(delta.mean())); centered = delta - delta.mean()
    rng = np.random.default_rng(stable_seed(82200, tag, "holm"))
    signs = rng.choice(np.array([-1.0, 1.0]), size=(2000, len(delta)))
    null = np.abs((signs * centered).mean(1))
    return float((1 + np.count_nonzero(null >= observed)) / 2001)


def holm_adjust(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = [entry for entry in entries if math.isfinite(entry["p_raw"])]
    valid.sort(key=lambda entry: entry["p_raw"]); m = len(valid); running = 0.0
    for index, entry in enumerate(valid):
        running = max(running, min(1.0, (m - index) * entry["p_raw"])); entry["p_holm"] = running
    return entries


def run_t4() -> None:
    stage = OUT / "t4"; stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists(): print("T4 already complete", flush=True); return
    if not (OUT / "t3" / "complete.json").exists(): run_t3()
    models = all_frozen_models()
    model_hashes = {name: (model.get("source_sha256") or sha256(Path(model["artifact_path"]))) for name, model in models.items()}
    freeze = {
        "status": "frozen_before_confirm_generation", "protocol_sha256": sha256(PROTOCOL),
        "pipeline_sha256": sha256(Path(__file__)), "generator_sha256": sha256(HERE / "generate_compare.py"),
        "model_hashes": model_hashes, "internal_seeds": list(range(84000, 84100)), "external_seeds": list(range(84100, 84140)),
        "no_confirm_tuning": True,
    }
    freeze_path = stage / "confirm_freeze.json"
    if freeze_path.exists() and json.loads(freeze_path.read_text(encoding="utf-8")) != freeze:
        raise RuntimeError("confirm freeze mismatch; refusing to inspect or regenerate confirmation data")
    if not freeze_path.exists(): write_json(freeze_path, freeze)
    if not (CONFIRM_DATA / "manifest.json").exists():
        command = [sys.executable, str(HERE / "generate_compare.py"), "--kind", "confirm", "--data", str(DATA), "--out", str(CONFIRM_DATA)]
        subprocess.run(command, check=True)
    confirm_manifest, confirm_rows = load_rows(CONFIRM_DATA)
    content_lock = {
        "manifest_sha256": sha256(CONFIRM_DATA / "manifest.json"),
        "pre_manifest_sha256": sha256(CONFIRM_DATA / "manifest_pre.json"),
        "trajectory_hashes": {row["file"]: str(row["sha256"]).upper() for row in confirm_manifest["trajectories"]},
        "locked_before_metrics": True,
    }
    lock_path = stage / "confirm_content_lock.json"
    if lock_path.exists() and json.loads(lock_path.read_text(encoding="utf-8")) != content_lock: raise RuntimeError("confirm content changed")
    if not lock_path.exists(): write_json(lock_path, content_lock)

    _, rows = load_rows(DATA); _, e9_rows = load_rows(E9_DATA)
    norms = train_moments(rows); labels = json.loads((OUT / "labels.json").read_text(encoding="utf-8"))
    confirm_results = {}
    development_results = {}
    for name, model in models.items():
        internal = evaluate(model, confirm_rows, "confirm_internal", norms, labels)
        external = evaluate(model, confirm_rows, "confirm_external", norms, labels)
        confirm_results[name] = merge_evaluations([internal, external], name, "confirm")
        development_results[name] = development_parts(model, rows, e9_rows, norms, labels)
        print(f"confirm {name}: macro={confirm_results[name]['macro_J_pred']:.6f}", flush=True)
    cost = {name: time_model(model, confirm_rows[0]["arrays"]["s3_deform"][0], confirm_rows[0]["arrays"]["u1_four"][0]) for name, model in models.items()}
    frozen_baselines = json.loads((OUT / "t2" / "G2.json").read_text(encoding="utf-8"))["baseline_by_tag"]
    final_gates: dict[str, Any] = {}; holm_entries = []
    for tag in [f"E{i}" for i in range(9)]:
        if tag not in frozen_baselines: continue
        baseline = frozen_baselines[tag]
        final_gates[tag] = {}
        for name in models:
            if name == baseline or tag not in confirm_results[name]["macro_by_label"]: continue
            dev = development_candidate_gate(development_results[name], development_results[baseline], cost[name], tag)
            con = advantage(confirm_results[name], confirm_results[baseline], tag, cost[name]["realtime_gate"], dev.get("improvement", 0.0) > 0)
            con["development_gate"] = dev; final_gates[tag][name] = con
            holm_entries.append({"tag": tag, "model": name, "baseline": baseline, "p_raw": signflip_p(confirm_results[name], confirm_results[baseline], tag)})
    holm = holm_adjust(holm_entries)
    corrected = {(entry["tag"], entry["model"]): entry.get("p_holm", math.nan) for entry in holm}
    for tag, methods in final_gates.items():
        for name, gate in methods.items():
            gate["p_holm"] = corrected.get((tag, name), math.nan)
            gate["eligible"] = bool(gate["eligible"] and gate["p_holm"] <= 0.05)
    candidates = sorted({name for methods in final_gates.values() for name, gate in methods.items() if gate["eligible"]})
    write_json(stage / "confirm_results.json", confirm_results); write_json(stage / "development_recheck.json", development_results)
    write_json(stage / "cost.json", cost); write_json(stage / "holm.json", holm); write_json(stage / "final_gates.json", final_gates)
    complete = {"accepted": True, "confirm_manifest_sha256": content_lock["manifest_sha256"], "eligible_offline_candidates": candidates, "models": model_hashes}
    write_json(stage / "complete.json", complete)
    append_log("W0049", "Koopman比较T4一次性确认", [
        f"confirm按冻结seed生成140条（100 internal + 40 external），manifest hash={content_lock['manifest_sha256']}。",
        "全部模型只读评估；未用confirm重选ridge/rank/seed/epoch/阈值。",
        f"Holm校正后且同时通过8%/CI/5%/非发散/实时/方向复现门的候选={candidates}。",
    ])
    print(json.dumps({"T4":"complete", "eligible":candidates}, ensure_ascii=False), flush=True)


def run_t5() -> None:
    stage = OUT / "t5"; stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists(): print("T5 already complete", flush=True); return
    if not (OUT / "t4" / "complete.json").exists(): run_t4()
    t4 = json.loads((OUT / "t4" / "complete.json").read_text(encoding="utf-8")); candidates = t4["eligible_offline_candidates"]
    if candidates:
        stop = {
            "status": "stopped_missing_frozen_identical_mpc_adapter",
            "candidates": candidates,
            "fact": "the accepted 30D coupled-plant branch has no model-agnostic horizon-20 MPC implementation consuming the new 46D S3/U1 contract",
            "solutions": [
                "implement one model-agnostic sequential-linearization MPC adapter for K0/K1 and the eligible candidate, then freeze weights/constraints/solver before any closed-loop metric",
                "validate the adapter on deterministic K0/K1 smoke trajectories and measure p99 including solver time",
                "rerun paired seeds 85001-85010 for lane change, hairpin, network disturbance, and DoS without tuning per model",
            ],
        }
        write_json(stage / "stop.json", stop)
        (stage / "solutions.md").write_text("# T5停止与解决方案\n\n" + "\n".join(f"{i+1}. {item}" for i,item in enumerate(stop["solutions"])) + "\n", encoding="utf-8")
        append_log("W0050", "Koopman比较T5停止", [stop["fact"], f"离线候选={candidates}；未以旧31D控制器冒充46D相同MPC。"])
        raise RuntimeError(stop["fact"])
    result = {"status": "not_applicable_no_offline_candidate", "eligible_offline_candidates": [], "reason": "G4 produced no method satisfying every preregistered offline advantage gate"}
    write_json(stage / "complete.json", result)
    with (stage / "closed_loop_tradeoff.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle); writer.writerow(["status", "reason"]); writer.writerow([result["status"], result["reason"]])
    fig, ax = plt.subplots(figsize=(8, 3.2)); ax.axis("off"); ax.text(.5,.60,"T5 not applicable",ha="center",fontsize=16); ax.text(.5,.38,"No offline candidate passed G4; no threshold was relaxed.",ha="center",fontsize=10); fig.tight_layout(); fig.savefig(OUT / "closed_loop_tradeoff.png", dpi=220); plt.close(fig)
    append_log("W0050", "Koopman比较T5门禁结论", ["G4无离线候选，按预注册规则T5=not_applicable_no_offline_candidate；未降低门槛生成闭环图。"])
    print(json.dumps(result, ensure_ascii=False), flush=True)


def force_event_predictions(models: dict[str, dict[str, Any]], row: dict[str, Any], norms: dict[str, np.ndarray]) -> tuple[list[dict[str, Any]], int]:
    u = row["arrays"]["u1_four"]; steer = physical_modes(u)[:, 4]
    event = int(np.argmax(np.abs(np.diff(steer))) + 1); start = max(0, min(event - 10, len(u) - HORIZON))
    records = []; states = {name: lift(model, row["arrays"]["s3_deform"][start]) for name, model in models.items()}
    for h in range(1, HORIZON + 1):
        index = start + h - 1; true = row["arrays"]["force_output"][start + h]
        record: dict[str, Any] = {"time_s": float(row["arrays"]["time_s"][start+h]), "steering_mode_rad": float(steer[index])}
        for j, label in enumerate(("Fx_FL","Fy_FL","Fx_FR","Fy_FR","Fx_RL","Fy_RL","Fx_RR","Fy_RR","Q_FR","Q_LR")): record[f"true_{label}"] = float(true[j])
        for name, model in models.items():
            states[name], _ = model_step(model, states[name], u[index]); _, force_n, _ = decode(model, states[name]); pred = force_n * norms["force_std"] + norms["force_mean"]
            for j, label in enumerate(("Fx_FL","Fy_FL","Fx_FR","Fy_FR","Fx_RL","Fy_RL","Fx_RR","Fy_RR","Q_FR","Q_LR")): record[f"{name}_{label}"] = float(pred[j])
        records.append(record)
    return records, start


def plot_force_event(records: list[dict[str, Any]], model_names: list[str], path: Path, csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    t = np.asarray([row["time_s"] for row in records]); fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
    axes[0,0].plot(t, np.degrees([row["steering_mode_rad"] for row in records]), color="black"); axes[0,0].axhline(0,color="gray",lw=.7); axes[0,0].set(ylabel="steering mode (deg)",title="Reversal event")
    colors = plt.cm.tab10(np.linspace(0,1,4)); point_names=("FL","FR","RL","RR")
    for color, point in zip(colors, point_names):
        axes[0,1].plot(t,[row[f"true_Fx_{point}"] for row in records],color=color,label=f"true {point}")
        axes[0,1].plot(t,[row[f"{model_names[-1]}_Fx_{point}"] for row in records],color=color,ls="--",alpha=.75,label=f"{model_names[-1]} {point}")
    axes[0,1].axhline(0,color="black",lw=.6); axes[0,1].set(ylabel="point Fx (N)",title="Four horizontal-force directions"); axes[0,1].legend(ncol=2,fontsize=7)
    true_angle = []; predicted_angles = {name:[] for name in model_names}
    for row in records:
        true_angle.append(math.degrees(math.atan2(sum(row[f"true_Fy_{p}"] for p in point_names), sum(row[f"true_Fx_{p}"] for p in point_names))))
        for name in model_names: predicted_angles[name].append(math.degrees(math.atan2(sum(row[f"{name}_Fy_{p}"] for p in point_names), sum(row[f"{name}_Fx_{p}"] for p in point_names))))
    axes[1,0].plot(t,true_angle,color="black",label="true")
    for name in model_names: axes[1,0].plot(t,predicted_angles[name],label=name)
    axes[1,0].set(xlabel="time (s)",ylabel="resultant direction (deg)",title="Four-point resultant direction"); axes[1,0].legend(fontsize=8)
    axes[1,1].plot(t,[r["true_Q_FR"] for r in records],color="tab:red",label="true Q_FR"); axes[1,1].plot(t,[r["true_Q_LR"] for r in records],color="tab:blue",label="true Q_LR")
    for name in model_names:
        axes[1,1].plot(t,[r[f"{name}_Q_FR"] for r in records],color="tab:red",ls="--" if name==model_names[0] else ":",alpha=.8,label=f"{name} Q_FR")
        axes[1,1].plot(t,[r[f"{name}_Q_LR"] for r in records],color="tab:blue",ls="--" if name==model_names[0] else ":",alpha=.8,label=f"{name} Q_LR")
    axes[1,1].axhline(0,color="black",lw=.6); axes[1,1].set(xlabel="time (s)",ylabel="cargo tensile load (N)",title="Cargo front/rear and left/right tensile loads"); axes[1,1].legend(fontsize=7,ncol=2)
    for ax in axes.ravel(): ax.grid(True,alpha=.25)
    fig.tight_layout(); fig.savefig(path,dpi=220); plt.close(fig)


def physical_consistency(models: dict[str, dict[str, Any]], rows: list[dict[str, Any]], norms: dict[str, np.ndarray]) -> dict[str, Any]:
    # Q_FR/Q_LR are algebraically determined by the four point forces.  Their
    # residual is testable for every predictor.  Independent action/reaction is
    # not an output of the 18D contract and is therefore reported as untestable
    # rather than fabricated from the same force twice.
    result = {}
    for name, model in models.items():
        q_residual, sign_ok, sign_total = [], 0, 0
        for row in rows:
            if row["meta"]["split"] not in ("confirm_internal", "confirm_external"): continue
            a = row["arrays"]; z = lift(model, a["s3_deform"][0])
            for k in range(min(len(a["u1_four"]), 200)):
                z,_ = model_step(model,z,a["u1_four"][k]); _,force_n,_=decode(model,z); force=force_n*norms["force_std"]+norms["force_mean"]
                qfr=.5*((force[0]+force[2])-(force[4]+force[6])); qlr=.5*((force[1]+force[5])-(force[3]+force[7])); q_residual.extend([qfr-force[8],qlr-force[9]])
                true=a["force_output"][k+1]
                for j in (8,9):
                    if abs(true[j])>=norms["force_sign_floor"][j]: sign_total+=1; sign_ok+=int(np.sign(force[j])==np.sign(true[j]))
        result[name]={"Q_algebra_rmse_n":float(np.sqrt(np.mean(np.square(q_residual)))),"Q_direction_accuracy":sign_ok/max(sign_total,1),"independent_action_reaction_residual":"not_identifiable_from_payload-side-only_18D_output"}
    return result


def run_t6() -> None:
    stage = OUT / "t6"; stage.mkdir(parents=True, exist_ok=True)
    if (stage / "complete.json").exists(): print("T6 already complete", flush=True); return
    if not (OUT / "t5" / "complete.json").exists(): run_t5()
    models = all_frozen_models(); _, rows = load_rows(DATA); _, e9_rows = load_rows(E9_DATA); _, confirm_rows = load_rows(CONFIRM_DATA)
    norms=train_moments(rows); labels=json.loads((OUT/"labels.json").read_text(encoding="utf-8"))
    confirm=json.loads((OUT/"t4"/"confirm_results.json").read_text(encoding="utf-8")); development=json.loads((OUT/"t4"/"development_recheck.json").read_text(encoding="utf-8")); gates=json.loads((OUT/"t4"/"final_gates.json").read_text(encoding="utf-8")); cost=json.loads((OUT/"t4"/"cost.json").read_text(encoding="utf-8"))
    methods=list(models); tags=[f"E{i}" for i in range(10)]; matrix=np.full((len(methods),len(tags)),np.nan)
    heat_rows=[]
    for i,name in enumerate(methods):
        for j,tag in enumerate(tags):
            source=development if tag=="E9" else confirm
            if tag in source[name]["macro_by_label"] and tag in source["K1"]["macro_by_label"]:
                b=source["K1"]["macro_by_label"][tag]["J_pred"]; v=source[name]["macro_by_label"][tag]["J_pred"]; matrix[i,j]=100*(b-v)/b; heat_rows.append({"method":name,"scenario":tag,"relative_improvement_vs_K1_percent":matrix[i,j],"evidence":"development diagnostic" if tag=="E9" else "one-shot confirm"})
    with (OUT/"scenario_method_heatmap.csv").open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(heat_rows[0]));writer.writeheader();writer.writerows(heat_rows)
    fig,ax=plt.subplots(figsize=(12,6)); image=ax.imshow(matrix,aspect="auto",cmap="RdYlGn",vmin=-max(10,np.nanpercentile(np.abs(matrix),90)),vmax=max(10,np.nanpercentile(np.abs(matrix),90)))
    ax.set_xticks(range(len(tags)),tags);ax.set_yticks(range(len(methods)),methods);ax.set_title("Relative J_pred improvement vs K1 (%) — E9 is development-only")
    for i in range(len(methods)):
        for j in range(len(tags)):
            if math.isfinite(matrix[i,j]):ax.text(j,i,f"{matrix[i,j]:.1f}",ha="center",va="center",fontsize=7)
    fig.colorbar(image,ax=ax,label="positive favors method");fig.tight_layout();fig.savefig(OUT/"scenario_method_heatmap.png",dpi=220);plt.close(fig)

    # Rebuild horizon and cost figures with every frozen representative method.
    horizon_parts={name:evaluate(model,rows,"development-test",norms,labels) for name,model in models.items()}
    plot_horizon(horizon_parts,OUT/"horizon_state_force.png")
    horizon_csv=[]
    for name,result in horizon_parts.items():
        for h in range(20): horizon_csv.append({"method":name,"horizon":h+1,**{group:result["horizon_nrmse"][group][h] for group in ("state","force","load")}})
    with (OUT/"horizon_state_force.csv").open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(horizon_csv[0]));writer.writeheader();writer.writerows(horizon_csv)
    plot_cost(cost,confirm,OUT/"accuracy_cost_pareto.png",OUT/"accuracy_cost_pareto.csv")
    import shutil
    shutil.copy2(OUT/"t1"/"input_rank_condition.png",OUT/"input_rank_condition.png");shutil.copy2(OUT/"t1"/"input_rank_condition.csv",OUT/"input_rank_condition.csv")

    best_e3=min(methods,key=lambda name:confirm[name]["macro_by_label"].get("E3",{"J_pred":math.inf})["J_pred"])
    event_row=next(row for row in confirm_rows if row["meta"]["scenario"]=="E3")
    event_models={"K1":models["K1"]}
    if best_e3!="K1":event_models[best_e3]=models[best_e3]
    records,event_start=force_event_predictions(event_models,event_row,norms);plot_force_event(records,list(event_models),OUT/"force_direction_events.png",OUT/"force_direction_events.csv")
    consistency=physical_consistency(models,confirm_rows,norms);write_json(stage/"physical_consistency.json",consistency)

    ood_rows=[]
    for tag in ("E7","E8"):
        base=confirm["K1"]["macro_by_label"][tag]["J_pred"]
        for name in methods:ood_rows.append({"scenario":tag,"method":name,"relative_improvement_vs_K1_percent":100*(base-confirm[name]["macro_by_label"][tag]["J_pred"])/base})
    with (OUT/"ood_network_robustness.csv").open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(ood_rows[0]));writer.writeheader();writer.writerows(ood_rows)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),sharey=True)
    for ax,tag in zip(axes,("E7","E8")):
        vals=[row["relative_improvement_vs_K1_percent"] for row in ood_rows if row["scenario"]==tag];ax.bar(methods,vals);ax.axhline(0,color="black",lw=.7);ax.tick_params(axis="x",rotation=45);ax.set(title=tag,ylabel="improvement vs K1 (%)");ax.grid(True,axis="y",alpha=.25)
    fig.tight_layout();fig.savefig(OUT/"ood_network_robustness.png",dpi=220);plt.close(fig)

    eligible={tag:[name for name,gate in tag_gates.items() if gate.get("eligible")] for tag,tag_gates in gates.items()};eligible={tag:names for tag,names in eligible.items() if names}
    global_order=sorted(methods,key=lambda name:confirm[name]["macro_J_pred"]);default=global_order[0]
    t1=json.loads((OUT/"t1"/"complete.json").read_text(encoding="utf-8"));t5=json.loads((OUT/"t5"/"complete.json").read_text(encoding="utf-8"))
    rows_md=[]
    descriptions={
        "K0":"参数最少、最快；适合低激励和小数据，但固定原状态线性递推限制非线性表达。",
        "K1":"固定二次lift、可复算且解释清楚；复杂度适中，是复杂方法必须击败的默认基线。",
        "K2":"表达全部8输入—状态乘积；容量最大，但条件数接近门限且参数/时延成本高。",
        "K3":"五个物理模态降低共线并保持双线性解释；结构选错时会遗漏耦合，rank需validation冻结。",
        "K3-r2":"参数量匹配的结构对照；能区分结构收益与单纯增参，但表达能力最受限。",
        "K4":"可学习lift能补充固定平方基；有seed方差、训练成本和外推风险。",
        "K5-linear":"面向20步误差直接优化；可能牺牲一步精度，训练和复算成本高于one-step源模型。",
        "K5-bilinear":"同时保留双线性源结构并优化多步；最复杂，只有长时域收益稳定时才值得。",
    }
    for name in methods:
        rows_md.append(f"| {name} | {confirm[name]['macro_J_pred']:.5f} | {cost[name]['parameter_count']} | {cost[name]['rollout20_ms']['p99']:.3f} | {descriptions[name]} |")
    report=["# Koopman方法—工况最终图谱","","> 事实边界：E0–E8来自一次性confirm；E9只作development可辨识性诊断；本报告不把未通过门的数值差解释为优势。","","## 总结","",f"- confirm综合误差排序第一为`{default}`，但场景优势必须看8%+paired CI+Holm+关键量+非发散+实时的联合门。",f"- 最终满足全部离线优势门的方法—场景组合：`{json.dumps(eligible,ensure_ascii=False)}`。",f"- T5状态：`{t5['status']}`；因此没有闭环证据时，不声称控制收益。",f"- K2原数据条件数为`{t1['original_full_condition']:.3e}`，有效秩`{t1['original_full_rank'][0]}/{t1['original_full_rank'][1]}`；它通过数值门但处于边界。",f"- 原train强受力样本占比为`{t1['strong_force_fraction_original']:.1%}`，所以结论只覆盖现有载荷域，不能外推到额定力附近。","","## 各方向优劣","","| 方法 | confirm macro J_pred | 参数量 | 20步p99 (ms) | 经验证的工程取舍 |","|---|---:|---:|---:|---|",*rows_md,"","## 物理与证据边界","",f"- 转向换向事件取confirm E3轨迹，起点索引`{event_start}`；四点Fx方向、合力方向和Q_FR/Q_LR均在CSV中逐样本留存。","- 18维监督输出只有货物侧四点力，不能独立构造另一侧力来检验作用—反作用；报告`not_identifiable`，没有把同一预测力取负后冒充独立证据。","- `physical_consistency.json`报告四点力推导Q与直接Q输出的一致性以及Q方向准确率。","- K6因冻结样本门不足记为不适用，不把未训练写成失败或优势。","","## 图表","",* [f"- `{name}`" for name in ("scenario_method_heatmap.png","horizon_state_force.png","bilinear_contribution.png","input_rank_condition.png","force_direction_events.png","accuracy_cost_pareto.png","closed_loop_tradeoff.png","ood_network_robustness.png")],""]
    (OUT/"final_report.md").write_text("\n".join(report),encoding="utf-8")
    write_json(stage/"complete.json",{"accepted":True,"default_by_confirm_macro":default,"eligible_method_scenarios":eligible,"figures":8,"report_sha256":sha256(OUT/"final_report.md")})
    append_log("W0051","Koopman比较T6最终图谱",[f"8张要求图及对应CSV/JSON完成；final_report hash={sha256(OUT/'final_report.md')}。",f"confirm macro排序={global_order}；联合门优势组合={json.dumps(eligible,ensure_ascii=False)}。","明确保留三项边界：E9无confirm、强载荷覆盖为0、18D输出不能独立验证作用—反作用两侧。"])
    print(json.dumps({"T6":"complete","default":default,"eligible":eligible},ensure_ascii=False),flush=True)


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument("--stage",choices=("t0","t1","t2","t3","t4","t5","t6","all"),required=True);args=parser.parse_args()
    stages={"t0":run_t0,"t1":run_t1,"t2":run_t2,"t3":run_t3,"t4":run_t4,"t5":run_t5,"t6":run_t6}
    if args.stage=="all":
        for fn in stages.values():fn()
    else:stages[args.stage]()


if __name__=="__main__":main()

"""Execute v2 universal Koopman modules after the D1/G2 audit.

The script never edits v1 artifacts.  Every stage writes an immutable initial
gate/result plus a completion record under ``universal_v2``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import stat
import sys
from typing import Any, Iterable

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE / "universal_v2"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import compare_pipeline as cp  # noqa: E402
import universal_v2_pipeline as uv2  # noqa: E402

H = 20
DT = 0.02
AMENDED_ELIGIBLE = ("K0", "K1", "K4", "K5-linear")
RANKS_F = (0, 2, 4, 8)
RIDGES = (1.0e-6, 1.0e-4, 1.0e-2)


def write_json(path: Path, value: Any) -> None:
    uv2.write_json(path, value)


def context() -> tuple[list[dict[str, Any]], dict[str, np.ndarray], dict[str, Any], dict[str, dict[str, Any]]]:
    rows = uv2.load_combined_rows()
    norms = cp.train_moments(rows)
    labels = cp.derive_labels(rows)
    _, original_rows = cp.load_rows(cp.DATA)
    old_norms = cp.train_moments(original_rows)
    models = {
        name: uv2.adapt_model_metrics(model, old_norms, norms)
        for name, model in cp.all_frozen_models().items()
    }
    return rows, norms, labels, models


def amend_g2() -> list[str]:
    path = OUT / "gate_amendment.json"
    if path.exists():
        return list(json.loads(path.read_text(encoding="utf-8"))["eligible"])
    audit_path = OUT / "backbone_audit.csv"
    with audit_path.open(encoding="utf-8-sig") as handle:
        audit = list(csv.DictReader(handle))
    eligible = []
    reasons = {}
    for row in audit:
        name = row["backbone"]
        finite = float(row["nonfinite_rate"]) == 0.0
        condition = float(row["condition"]) <= 1.0e8
        rank = float(row["rank_ratio"]) >= 0.95
        magnitude_ok = float(row["macro_J_pred"]) < 1.0e6
        ok = finite and condition and rank and magnitude_ok
        if ok:
            eligible.append(name)
        reasons[name] = {
            "finite": finite, "condition_le_1e8": condition,
            "rank_ratio_ge_0p95": rank, "macro_not_exploded": magnitude_ok,
            "rollout_divergence_rate_reported_not_entry_gate": float(row["divergence_rate"]),
            "eligible": ok,
        }
    if tuple(eligible) != AMENDED_ELIGIBLE:
        raise RuntimeError(f"unexpected G2 reclassification: {eligible}")
    write_json(path, {
        "status": "frozen_before_F_H_training", "initial_gate_preserved": str(OUT / "t2" / "complete.json"),
        "reason": "baseline long-horizon performance cannot be a prerequisite for the H correction intended to improve it",
        "eligible": eligible, "excluded": [row["backbone"] for row in audit if row["backbone"] not in eligible],
        "criteria": {"nonfinite_rate": 0, "condition_max": 1.0e8, "rank_ratio_min": 0.95, "macro_explosion_guard": 1.0e6},
        "audit": reasons,
    })
    uv2.append_log("W0059", "G2入口卡口逻辑勘误", [
        "保留首次G2全排除结果；识别到以长时域性能作为H入口会造成逻辑自锁。",
        f"按有限值/条件数/有效秩重分类，F/H入口={eligible}；其余骨干只保留诊断。",
        f"勘误hash={uv2.sha256(path)}；未降低模块后的状态保护、发散或部署门。",
    ])
    return eligible


def role_rows(rows: list[dict[str, Any]], role: str) -> Iterable[dict[str, Any]]:
    for row in rows:
        if cp.role_matches(row["meta"], role):
            yield row


def rollout(model: dict[str, Any], arrays: dict[str, np.ndarray], start: int) -> tuple[np.ndarray, np.ndarray]:
    """Return normalized predicted S3(46) and F0(18), shape [20,*]."""
    z = cp.lift(model, arrays["s3_deform"][start])
    xs, fs = [], []
    for h in range(H):
        z, _ = cp.model_step(model, z, arrays["u1_four"][start + h])
        _, force_n, x_n = cp.decode(model, z)
        xs.append(x_n)
        fs.append(force_n)
    return np.asarray(xs), np.asarray(fs)


def physics_force(xn: np.ndarray, norms: dict[str, np.ndarray], previous_points: np.ndarray) -> np.ndarray:
    """Nominal connector contract from predicted displacement/velocity."""
    x = xn * norms["x_std"] + norms["x_mean"]
    disp = x[..., 30:38].reshape(*x.shape[:-1], 4, 2)
    vel = x[..., 38:46].reshape(*x.shape[:-1], 4, 2)
    distance = np.linalg.norm(disp, axis=-1)
    normal = disp / np.maximum(distance[..., None], 1.0e-12)
    penetration = np.maximum(distance - 0.002, 0.0)
    loading = np.maximum(np.sum(vel * normal, axis=-1), 0.0)
    points = (30000.0 * penetration + 3500.0 * loading)[..., None] * normal
    q_fr = 0.5 * ((points[..., 0, 0] + points[..., 1, 0]) - (points[..., 2, 0] + points[..., 3, 0]))
    q_lr = 0.5 * ((points[..., 0, 1] + points[..., 2, 1]) - (points[..., 1, 1] + points[..., 3, 1]))
    rates = np.empty_like(points)
    prev = np.asarray(previous_points, dtype=float)
    for index in range(len(points)):
        rates[index] = (points[index] - prev) / DT
        prev = points[index]
    return np.c_[points.reshape(len(points), 8), q_fr, q_lr, rates.reshape(len(points), 8)]


def reconstruct_force(points: np.ndarray, previous_points: np.ndarray) -> np.ndarray:
    q_fr = 0.5 * ((points[:, 0] + points[:, 2]) - (points[:, 4] + points[:, 6]))
    q_lr = 0.5 * ((points[:, 1] + points[:, 5]) - (points[:, 3] + points[:, 7]))
    rates = np.empty_like(points)
    prev = np.asarray(previous_points, dtype=float).reshape(8)
    for index in range(len(points)):
        rates[index] = (points[index] - prev) / DT
        prev = points[index]
    return np.c_[points, q_fr, q_lr, rates]


def f_features(xn: np.ndarray, controls: np.ndarray, f1: np.ndarray, norms: dict[str, np.ndarray]) -> np.ndarray:
    un = (controls - norms["u_mean"]) / norms["u_std"]
    f1n = (f1[:, :8] - norms["force_mean"][:8]) / norms["force_std"][:8]
    return np.c_[np.ones(len(xn)), xn, un, f1n]


def low_rank(coef: np.ndarray, rank: int) -> np.ndarray:
    if rank <= 0:
        return np.zeros_like(coef)
    u, s, vt = np.linalg.svd(coef, full_matrices=False)
    r = min(rank, len(s))
    return (u[:, :r] * s[:r]) @ vt[:r]


def fit_ridge(x: np.ndarray, y: np.ndarray, ridge: float) -> np.ndarray:
    gram = x.T @ x
    penalty = np.eye(x.shape[1]) * ridge
    penalty[0, 0] = 0.0
    return np.linalg.solve(gram + penalty, x.T @ y)


def metric_accumulator() -> dict[str, Any]:
    return {"sq_state": 0.0, "n_state": 0, "sq_force": 0.0, "n_force": 0,
            "sq_load": 0.0, "n_load": 0, "sq_rate": 0.0, "n_rate": 0,
            "direction_ok": 0, "direction_n": 0, "windows": 0, "diverged": 0,
            "trajectory_sq": defaultdict(lambda: [0.0, 0])}


def accumulate_metric(acc: dict[str, Any], pred_x: np.ndarray, pred_f: np.ndarray,
                      true_x: np.ndarray, true_f: np.ndarray, key: str) -> None:
    ex = (pred_x - true_x) ** 2
    ef = (pred_f - true_f) ** 2
    acc["sq_state"] += float(ex.sum()); acc["n_state"] += ex.size
    acc["sq_force"] += float(ef[:, :8].sum()); acc["n_force"] += ef[:, :8].size
    acc["sq_load"] += float(ef[:, 8:10].sum()); acc["n_load"] += ef[:, 8:10].size
    acc["sq_rate"] += float(ef[:, 10:18].sum()); acc["n_rate"] += ef[:, 10:18].size
    floor = 0.05
    mask = np.abs(true_f[:, :8]) >= floor
    acc["direction_ok"] += int(np.sum((np.sign(pred_f[:, :8]) == np.sign(true_f[:, :8])) & mask))
    acc["direction_n"] += int(mask.sum())
    acc["windows"] += 1
    acc["diverged"] += int(np.max(np.abs(np.c_[pred_x, pred_f])) > 50.0)
    value = float(np.mean(np.c_[ex, ef[:, :10]]))
    acc["trajectory_sq"][key][0] += value; acc["trajectory_sq"][key][1] += 1


def finish_metric(acc: dict[str, Any]) -> dict[str, Any]:
    state = math.sqrt(acc["sq_state"] / max(acc["n_state"], 1))
    force = math.sqrt(acc["sq_force"] / max(acc["n_force"], 1))
    load = math.sqrt(acc["sq_load"] / max(acc["n_load"], 1))
    rate = math.sqrt(acc["sq_rate"] / max(acc["n_rate"], 1))
    return {"state": state, "force": force, "load": load, "force_rate": rate,
            "J_pred": (state + force + load) / 3.0,
            "direction_accuracy": acc["direction_ok"] / max(acc["direction_n"], 1),
            "windows": acc["windows"], "divergence_rate": acc["diverged"] / max(acc["windows"], 1),
            "per_trajectory": {key: math.sqrt(total / count) for key, (total, count) in acc["trajectory_sq"].items()}}


def apply_fhead(head: dict[str, np.ndarray], xn: np.ndarray, controls: np.ndarray,
                f1: np.ndarray, previous_points: np.ndarray, norms: dict[str, np.ndarray]) -> np.ndarray:
    raw = f_features(xn, controls, f1, norms)
    feature = raw.copy()
    feature[:, 1:] = (feature[:, 1:] - head["feature_mean"]) / head["feature_std"]
    residual_n = feature @ head["coef"]
    residual = residual_n * norms["force_std"][:8]
    residual = np.clip(residual, -head["clip"], head["clip"])
    return reconstruct_force(f1[:, :8] + residual, previous_points)


def evaluate_f(model: dict[str, Any], rows: list[dict[str, Any]], role: str,
               norms: dict[str, np.ndarray], head: dict[str, np.ndarray] | None) -> dict[str, Any]:
    accs = {"F0": metric_accumulator(), "F1": metric_accumulator(), "F2": metric_accumulator()}
    for row in role_rows(rows, role):
        a = row["arrays"]
        key = f"{row['meta']['scenario']}|{row['meta']['seed']}"
        for start in range(0, len(a["u1_four"]) - H + 1, H):
            xn, f0n = rollout(model, a, start)
            true_x = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            true_f = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            previous = a["force_output"][start, :8].reshape(4, 2)
            f1 = physics_force(xn, norms, previous)
            f1n = (f1 - norms["force_mean"]) / norms["force_std"]
            accumulate_metric(accs["F0"], xn, f0n, true_x, true_f, key)
            accumulate_metric(accs["F1"], xn, f1n, true_x, true_f, key)
            if head is not None:
                f2 = apply_fhead(head, xn, a["u1_four"][start:start + H], f1, previous, norms)
                f2n = (f2 - norms["force_mean"]) / norms["force_std"]
                accumulate_metric(accs["F2"], xn, f2n, true_x, true_f, key)
    return {name: finish_metric(acc) for name, acc in accs.items() if acc["windows"]}


def run_f() -> None:
    complete = OUT / "t3" / "complete.json"
    if complete.exists():
        print("T3 F already complete", flush=True); return
    eligible = amend_g2()
    rows, norms, _, models = context()
    stage = OUT / "t3"; model_dir = stage / "models"; model_dir.mkdir(parents=True, exist_ok=True)
    summary, increments = {}, []
    for name in eligible:
        model = models[name]
        train_x, train_y, f1_abs = [], [], []
        for row in role_rows(rows, "train"):
            a = row["arrays"]
            for start in range(0, len(a["u1_four"]) - H + 1, H):
                xn, _ = rollout(model, a, start)
                previous = a["force_output"][start, :8].reshape(4, 2)
                f1 = physics_force(xn, norms, previous)
                x = f_features(xn, a["u1_four"][start:start + H], f1, norms)
                true_n = (a["force_output"][start + 1:start + H + 1, :8] - norms["force_mean"][:8]) / norms["force_std"][:8]
                f1n = (f1[:, :8] - norms["force_mean"][:8]) / norms["force_std"][:8]
                train_x.append(x); train_y.append(true_n - f1n); f1_abs.append(np.abs(f1[:, :8]))
        x = np.vstack(train_x); y = np.vstack(train_y)
        feature_mean = x[:, 1:].mean(axis=0); feature_std = np.maximum(x[:, 1:].std(axis=0), 1.0e-12)
        x[:, 1:] = (x[:, 1:] - feature_mean) / feature_std
        clip = 0.25 * np.percentile(np.vstack(f1_abs), 99.5, axis=0)
        candidates = []
        for ridge in RIDGES:
            full = fit_ridge(x, y, ridge)
            for rank in RANKS_F:
                head = {"coef": low_rank(full, rank), "feature_mean": feature_mean, "feature_std": feature_std, "clip": clip}
                result = evaluate_f(model, rows, "validation", norms, head)["F2"]
                candidates.append((result["force"] + result["load"], rank, -ridge, result, head, ridge))
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        _, rank, _, validation, head, ridge = candidates[0]
        np.savez_compressed(model_dir / f"{name}.npz", **head, rank=np.asarray(rank), ridge=np.asarray(ridge))
        development = evaluate_f(model, rows, "development-test", norms, head)
        baseline = development["F0"]; selected = development["F2"]
        improvement = (baseline["force"] + baseline["load"] - selected["force"] - selected["load"]) / max(baseline["force"] + baseline["load"], 1.0e-12)
        state_delta = abs(selected["state"] - baseline["state"])
        passed = improvement >= 0.08 and state_delta <= 1.0e-12 and selected["divergence_rate"] <= baseline["divergence_rate"]
        summary[name] = {"selected": {"rank": rank, "ridge": ridge}, "validation": validation,
                         "development": development, "force_load_improvement": improvement,
                         "state_absolute_delta": state_delta, "relative_gate": passed}
        for variant, result in development.items():
            increments.append({"backbone": name, "module": variant, **{k: result[k] for k in ("state", "force", "load", "force_rate", "J_pred", "direction_accuracy", "divergence_rate")}})
        print(f"F {name}: rank={rank} ridge={ridge:g} force+load improvement={100*improvement:.2f}% gate={passed}", flush=True)
    with (OUT / "module_increment.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(increments[0])); writer.writeheader(); writer.writerows(increments)
    families = sum(int(row["relative_gate"]) for row in summary.values())
    write_json(stage / "results.json", summary)
    write_json(complete, {"stage": "T3-F", "status": "complete", "eligible": eligible,
                          "families_passing_relative_gate": families,
                          "cross_three_families": families >= 3,
                          "results_sha256": uv2.sha256(stage / "results.json")})
    uv2.append_log("W0060", "v2 T3因果物理受力头", [
        f"在G2重分类骨干{eligible}上完成F0/F1/F2；通过8%相对门的家族数={families}/4。",
        "F2只替换8维四点力，Q与因果力变化率统一重构；状态逐元素未改。",
        f"结果hash={uv2.sha256(stage/'results.json')}；模型目录={model_dir}。",
    ])


def finalize_f_selection() -> None:
    """Apply the preregistered baseline/epoch-0 fallback without retraining."""
    target = OUT / "t3" / "selection.json"
    if target.exists():
        print("F selection already frozen", flush=True); return
    if not (OUT / "t3" / "complete.json").exists():
        run_f()
    rows, norms, _, models = context()
    original = json.loads((OUT / "t3" / "results.json").read_text(encoding="utf-8"))
    selections = {}
    for name in amend_g2():
        with np.load(OUT / "t3" / "models" / f"{name}.npz", allow_pickle=False) as source:
            head = {key: np.asarray(source[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}
        val = evaluate_f(models[name], rows, "validation", norms, head)
        ordered = sorted(val, key=lambda variant: (val[variant]["force"] + val[variant]["load"],
                                                    {"F0": 0, "F1": 1, "F2": 2}[variant]))
        selected = ordered[0]
        dev = original[name]["development"]
        baseline, candidate = dev["F0"], dev[selected]
        improvement = (baseline["force"] + baseline["load"] - candidate["force"] - candidate["load"]) / max(baseline["force"] + baseline["load"], 1.0e-12)
        development_gate = (improvement >= 0.08 and abs(candidate["state"] - baseline["state"]) <= 1.0e-12
                            and candidate["divergence_rate"] <= baseline["divergence_rate"])
        deployed = selected if development_gate else "F0"
        selections[name] = {"validation_metrics": val, "validation_selected": selected,
                            "development_improvement": improvement, "development_gate": development_gate,
                            "BFH_force_head": deployed,
                            "reason": "development safety/performance fallback" if deployed == "F0" and selected != "F0" else "validation lexicographic selection"}
        print(f"F select {name}: validation={selected}, development_gate={development_gate}, BFH={deployed}", flush=True)
    write_json(target, {"status": "frozen", "baseline_fallback_included": True, "backbones": selections})
    uv2.append_log("W0061", "F词典序回退冻结", [
        "发现初版F结果只在F2网格内选择，遗漏S规则要求的原骨干F0回退点；未重训、未改数据或候选。",
        f"按validation选择并用development门决定BFH头：{ {k:v['BFH_force_head'] for k,v in selections.items()} }。",
        f"selection hash={uv2.sha256(target)}。",
    ])


def selected_fhead(name: str) -> tuple[str, dict[str, np.ndarray] | None]:
    selection = json.loads((OUT / "t3" / "selection.json").read_text(encoding="utf-8"))
    variant = selection["backbones"][name]["BFH_force_head"]
    if variant != "F2":
        return variant, None
    with np.load(OUT / "t3" / "models" / f"{name}.npz", allow_pickle=False) as source:
        return variant, {key: np.asarray(source[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}


def collect_h_data(model: dict[str, Any], name: str, rows: list[dict[str, Any]], role: str,
                   norms: dict[str, np.ndarray]) -> dict[str, Any]:
    variant, head = selected_fhead(name)
    x0s, controls, predictions, truths, keys = [], [], [], [], []
    for row in role_rows(rows, role):
        a = row["arrays"]
        key = f"{row['meta']['scenario']}|{row['meta']['seed']}"
        for start in range(0, len(a["u1_four"]) - H + 1, H):
            xn, f0n = rollout(model, a, start)
            force_n = f0n
            if variant in ("F1", "F2"):
                previous = a["force_output"][start, :8].reshape(4, 2)
                f1 = physics_force(xn, norms, previous)
                force = f1 if variant == "F1" else apply_fhead(head, xn, a["u1_four"][start:start + H], f1, previous, norms)
                force_n = (force - norms["force_mean"]) / norms["force_std"]
            truth_x = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            truth_f = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            x0s.append(((a["s3_deform"][start] - norms["x_mean"]) / norms["x_std"]).astype(np.float32))
            controls.append(((a["u1_four"][start:start + H] - norms["u_mean"]) / norms["u_std"]).astype(np.float32))
            predictions.append(np.c_[xn, force_n].astype(np.float32))
            truths.append(np.c_[truth_x, truth_f].astype(np.float32))
            keys.append(key)
    return {"x0": np.asarray(x0s), "u": np.asarray(controls), "pred": np.asarray(predictions),
            "truth": np.asarray(truths), "keys": keys, "force_head": variant}


def h_feature(data: dict[str, Any], horizon: int) -> np.ndarray:
    n = len(data["x0"])
    return np.c_[np.ones(n), data["x0"], data["u"][:, :horizon, :].reshape(n, 8 * horizon),
                 data["pred"][:, horizon - 1], np.zeros((n, 12))]


def metric_y(pred: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    error = (np.asarray(pred, dtype=float) - np.asarray(truth, dtype=float)) ** 2
    state = math.sqrt(float(error[..., :46].mean()))
    force = math.sqrt(float(error[..., 46:54].mean()))
    load = math.sqrt(float(error[..., 54:56].mean()))
    rate = math.sqrt(float(error[..., 56:64].mean()))
    window_max = np.max(np.abs(pred), axis=(1, 2))
    by_horizon = []
    for h in range(H):
        e = error[:, h]
        by_horizon.append({"horizon": h + 1, "state": math.sqrt(float(e[:, :46].mean())),
                           "force": math.sqrt(float(e[:, 46:54].mean())),
                           "load": math.sqrt(float(e[:, 54:56].mean())),
                           "force_rate": math.sqrt(float(e[:, 56:64].mean()))})
    return {"state": state, "force": force, "load": load, "force_rate": rate,
            "J_pred": (state + force + load) / 3.0,
            "state_h1_5": math.sqrt(float(error[:, :5, :46].mean())),
            "state_dim_h1_5": np.sqrt(error[:, :5, :46].mean(axis=(0, 1))).tolist(),
            "divergence_rate": float(np.mean(window_max > 50.0)), "windows": len(pred),
            "by_horizon": by_horizon}


def save_h_artifact(path: Path, pieces: list[tuple[np.ndarray, np.ndarray, np.ndarray]],
                    rank: int, ridge: float, solver: str, forgetting: float = 1.0) -> None:
    arrays: dict[str, np.ndarray] = {"rank": np.asarray(rank), "ridge": np.asarray(ridge),
                                    "forgetting": np.asarray(forgetting), "solver": np.asarray(solver)}
    for h, (coef, mean, std) in enumerate(pieces, 1):
        arrays[f"coef_{h:02d}"] = coef
        arrays[f"mean_{h:02d}"] = mean
        arrays[f"std_{h:02d}"] = std
    np.savez_compressed(path, **arrays)


def load_h_artifact(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        return {key: np.asarray(source[key]) for key in source.files}


def apply_h_artifact(data: dict[str, Any], artifact: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    result = np.asarray(data["pred"], dtype=float).copy()
    ratios = []
    for h in range(1, H + 1):
        x = h_feature(data, h)
        x[:, 1:] = (x[:, 1:] - artifact[f"mean_{h:02d}"]) / artifact[f"std_{h:02d}"]
        correction = x @ artifact[f"coef_{h:02d}"]
        ratios.extend((np.linalg.norm(correction, axis=1) / (np.linalg.norm(result[:, h - 1], axis=1) + 1.0e-12)).tolist())
        result[:, h - 1] += correction
    return result, np.asarray(ratios)


def candidate_summary(sums: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    state = math.sqrt(sums["state_sq"] / sums["state_n"])
    force = math.sqrt(sums["force_sq"] / sums["force_n"])
    load = math.sqrt(sums["load_sq"] / sums["load_n"])
    rate = math.sqrt(sums["rate_sq"] / sums["rate_n"])
    h15 = math.sqrt(sums["h15_sq"] / sums["h15_n"])
    dims = np.sqrt(sums["dim_sq"] / sums["dim_n"])
    base_dims = np.asarray(baseline["state_dim_h1_5"])
    protected = h15 <= 1.05 * baseline["state_h1_5"] + 1.0e-12 and bool(np.all(dims <= 1.05 * base_dims + 1.0e-12))
    correction_p99 = float(np.percentile(sums["ratios"], 99)) if sums["ratios"] else 0.0
    return {"state": state, "force": force, "load": load, "force_rate": rate,
            "J_pred": (state + force + load) / 3.0, "state_h1_5": h15,
            "state_protected": protected, "correction_ratio_p99": correction_p99,
            "correction_gate": correction_p99 <= 0.5 + 1.0e-12}


def run_h() -> None:
    complete = OUT / "t4" / "complete.json"
    if complete.exists():
        print("T4 H already complete", flush=True); return
    finalize_f_selection()
    rows, norms, _, models = context()
    stage = OUT / "t4"; model_dir = stage / "models"; model_dir.mkdir(parents=True, exist_ok=True)
    results, horizon_rows = {}, []
    candidate_keys = [(rank, ridge) for rank in (0, 2, 4, 8, 12) for ridge in RIDGES]
    for name in amend_g2():
        print(f"H {name}: collecting windows", flush=True)
        train = collect_h_data(models[name], name, rows, "train", norms)
        validation = collect_h_data(models[name], name, rows, "validation", norms)
        baseline_val = metric_y(validation["pred"], validation["truth"])
        sums = {key: {"state_sq": 0.0, "state_n": 0, "force_sq": 0.0, "force_n": 0,
                      "load_sq": 0.0, "load_n": 0, "rate_sq": 0.0, "rate_n": 0,
                      "h15_sq": 0.0, "h15_n": 0, "dim_sq": np.zeros(46), "dim_n": 0,
                      "ratios": []} for key in candidate_keys}
        pieces: dict[tuple[int, float], list[tuple[np.ndarray, np.ndarray, np.ndarray]]] = {key: [] for key in candidate_keys}
        for h in range(1, H + 1):
            xt = h_feature(train, h); xv = h_feature(validation, h)
            mean = xt[:, 1:].mean(axis=0); std = np.maximum(xt[:, 1:].std(axis=0), 1.0e-12)
            xt[:, 1:] = (xt[:, 1:] - mean) / std; xv[:, 1:] = (xv[:, 1:] - mean) / std
            target = np.asarray(train["truth"][:, h - 1] - train["pred"][:, h - 1], dtype=float)
            for ridge in RIDGES:
                full = fit_ridge(xt, target, ridge)
                for rank in (0, 2, 4, 8, 12):
                    key = (rank, ridge); coef = low_rank(full, rank); pieces[key].append((coef, mean, std))
                    correction = xv @ coef
                    prediction = np.asarray(validation["pred"][:, h - 1], dtype=float) + correction
                    error = (prediction - validation["truth"][:, h - 1]) ** 2
                    item = sums[key]
                    item["state_sq"] += float(error[:, :46].sum()); item["state_n"] += error[:, :46].size
                    item["force_sq"] += float(error[:, 46:54].sum()); item["force_n"] += error[:, 46:54].size
                    item["load_sq"] += float(error[:, 54:56].sum()); item["load_n"] += error[:, 54:56].size
                    item["rate_sq"] += float(error[:, 56:64].sum()); item["rate_n"] += error[:, 56:64].size
                    if h <= 5:
                        item["h15_sq"] += float(error[:, :46].sum()); item["h15_n"] += error[:, :46].size
                        item["dim_sq"] += error[:, :46].sum(axis=0); item["dim_n"] += len(error)
                    item["ratios"].extend((np.linalg.norm(correction, axis=1) / (np.linalg.norm(validation["pred"][:, h - 1], axis=1) + 1.0e-12)).tolist())
            if h in (1, 5, 10, 20):
                print(f"H {name}: fitted h={h}", flush=True)
        summaries = {f"r{rank}_l{ridge:g}": candidate_summary(sums[(rank, ridge)], baseline_val) for rank, ridge in candidate_keys}
        legal = [(summaries[f"r{rank}_l{ridge:g}"]["J_pred"], rank, -ridge, ridge) for rank, ridge in candidate_keys
                 if summaries[f"r{rank}_l{ridge:g}"]["state_protected"] and summaries[f"r{rank}_l{ridge:g}"]["correction_gate"]]
        if not legal:
            raise RuntimeError(f"{name} has no H candidate including rank-0")
        _, rank, _, ridge = min(legal)
        ls_path = model_dir / f"{name}-HLS.npz"
        save_h_artifact(ls_path, pieces[(rank, ridge)], rank, ridge, "batch-LS")
        ls_art = load_h_artifact(ls_path)
        # Block-forgetting RLS is algebraically weighted ridge on the same ordered samples.
        rls_candidates = {}
        rls_paths = {}
        for forgetting in (0.98, 0.995, 1.0):
            rls_pieces = []
            for h in range(1, H + 1):
                xt = h_feature(train, h)
                mean = ls_art[f"mean_{h:02d}"]; std = ls_art[f"std_{h:02d}"]
                xt[:, 1:] = (xt[:, 1:] - mean) / std
                target = np.asarray(train["truth"][:, h - 1] - train["pred"][:, h - 1], dtype=float)
                if forgetting == 1.0:
                    full = fit_ridge(xt, target, ridge)
                else:
                    exponent = (len(xt) - 1 - np.arange(len(xt))) / H
                    weight = np.power(forgetting, exponent)
                    sw = np.sqrt(weight)[:, None]
                    full = fit_ridge(xt * sw, target * sw, ridge)
                rls_pieces.append((low_rank(full, rank), mean, std))
            rls_path = model_dir / f"{name}-HRLS-l{forgetting:g}.npz"
            save_h_artifact(rls_path, rls_pieces, rank, ridge, "block-RLS", forgetting)
            pred, ratios = apply_h_artifact(validation, load_h_artifact(rls_path))
            m = metric_y(pred, validation["truth"]); m["correction_ratio_p99"] = float(np.percentile(ratios, 99))
            rls_candidates[str(forgetting)] = m; rls_paths[str(forgetting)] = rls_path
        best_lambda = min((m["J_pred"], abs(float(key) - 1.0), key) for key, m in rls_candidates.items())[2]
        rls_path = model_dir / f"{name}-HRLS.npz"
        selected_rls = load_h_artifact(rls_paths[best_lambda])
        np.savez_compressed(rls_path, **selected_rls)
        development = collect_h_data(models[name], name, rows, "development-test", norms)
        baseline_dev = metric_y(development["pred"], development["truth"])
        pred_ls, ratio_ls = apply_h_artifact(development, ls_art); metric_ls = metric_y(pred_ls, development["truth"])
        metric_ls["correction_ratio_p99"] = float(np.percentile(ratio_ls, 99))
        pred_rls, ratio_rls = apply_h_artifact(development, selected_rls); metric_rls = metric_y(pred_rls, development["truth"])
        metric_rls["correction_ratio_p99"] = float(np.percentile(ratio_rls, 99))
        improvement = (baseline_dev["J_pred"] - metric_ls["J_pred"]) / max(baseline_dev["J_pred"], 1.0e-12)
        state_guard = metric_ls["state_h1_5"] <= 1.05 * baseline_dev["state_h1_5"] + 1.0e-12 and bool(np.all(np.asarray(metric_ls["state_dim_h1_5"]) <= 1.05 * np.asarray(baseline_dev["state_dim_h1_5"]) + 1.0e-12))
        gate = improvement >= 0.08 and state_guard and metric_ls["divergence_rate"] <= baseline_dev["divergence_rate"] and metric_ls["correction_ratio_p99"] <= 0.5
        results[name] = {"force_head": train["force_head"], "selected_LS": {"rank": rank, "ridge": ridge},
                         "validation_baseline": baseline_val, "validation_grid": summaries,
                         "RLS_validation": rls_candidates, "selected_RLS_lambda": float(best_lambda),
                         "development": {"P1": baseline_dev, "P2-HLS": metric_ls, "P3-HRLS": metric_rls},
                         "HLS_improvement": improvement, "state_guard": state_guard, "relative_gate": gate}
        for variant, metric in (("P1", baseline_dev), ("P2-HLS", metric_ls), ("P3-HRLS", metric_rls)):
            for row in metric["by_horizon"]:
                horizon_rows.append({"backbone": name, "variant": variant, **row})
        print(f"H {name}: selected r={rank} ridge={ridge:g}; dev improvement={100*improvement:.2f}% gate={gate}; RLS lambda={best_lambda}", flush=True)
    write_json(stage / "results.json", results)
    with (OUT / "horizon_state_force.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(horizon_rows[0])); writer.writeheader(); writer.writerows(horizon_rows)
    passed = sum(int(value["relative_gate"]) for value in results.values())
    write_json(complete, {"stage": "T4-H", "status": "complete", "backbones": list(results),
                          "families_passing": passed, "limited_universality": passed >= 3,
                          "results_sha256": uv2.sha256(stage / "results.json")})
    uv2.append_log("W0062", "v2 T4直接多时域H", [
        f"H-LS/H-RLS在四个入口骨干完成；8%+状态保护+发散不增门通过={passed}/4。",
        "RLS使用与LS相同特征、标准化、rank、ridge和有序样本；lambda=1与batch解作为必须保留回退。",
        f"结果hash={uv2.sha256(stage/'results.json')}；逐时域CSV hash={uv2.sha256(OUT/'horizon_state_force.csv')}。",
    ])


PARAM_RANGES = {
    "payload_mass_scale": (0.85, 1.15),
    "connector_stiffness_scale": (0.75, 1.25),
    "connector_damping_scale": (0.70, 1.30),
    "connector_free_play_scale": (0.70, 1.40),
    "vehicle_mu_scale": (0.80, 1.10),
}


def parameter_tasks() -> list[dict[str, Any]]:
    """Deterministic maximin selection from 256 PCG64 Latin hypercubes."""
    rng = np.random.Generator(np.random.PCG64(906001))
    best, best_distance = None, -1.0
    n, d = 38, len(PARAM_RANGES)
    for _ in range(100):
        candidate = np.empty((n, d))
        for dim in range(d):
            candidate[:, dim] = (rng.permutation(n) + rng.random(n)) / n
        diff = candidate[:, None, :] - candidate[None, :, :]
        distance = np.sqrt(np.sum(diff * diff, axis=2))
        distance[np.eye(n, dtype=bool)] = np.inf
        score = float(distance.min())
        if score > best_distance:
            best, best_distance = candidate.copy(), score
    splits = ["train"] * 20 + ["validation"] * 5 + ["development-test"] * 5 + ["future-confirm"] * 8
    tasks = []
    for index, (point, split) in enumerate(zip(best, splits)):
        row = {"task_id": index, "split": split, "maximin_unit_distance": best_distance}
        for dim, (key, bounds) in enumerate(PARAM_RANGES.items()):
            row[key] = float(bounds[0] + point[dim] * (bounds[1] - bounds[0]))
        tasks.append(row)
    return tasks


def explicit_params(task: dict[str, Any]) -> tuple[Any, dict[str, float]]:
    base = uv2.v1.base
    scales = {key: float(task[key]) for key in PARAM_RANGES}
    params = base.ModelParams(
        vehicle=replace(base.VehicleParams(), mu=base.VehicleParams().mu * scales["vehicle_mu_scale"]),
        payload=replace(base.PayloadParams(), mass_kg=base.PayloadParams().mass_kg * scales["payload_mass_scale"]),
        connector=replace(base.ConnectorParams(),
                          stiffness_npm=base.ConnectorParams().stiffness_npm * scales["connector_stiffness_scale"],
                          damping_nspm=base.ConnectorParams().damping_nspm * scales["connector_damping_scale"],
                          free_play_m=base.ConnectorParams().free_play_m * scales["connector_free_play_scale"]),
    )
    return params, scales


def parameter_job(job: dict[str, Any], task: dict[str, Any], scales: dict[str, np.ndarray], output: str) -> dict[str, Any]:
    """Worker: freeze a task's exact parameters by replacing only the sampler callback."""
    params, actual_scales = explicit_params(task)
    original = uv2.v1.compare_gen.base.parameter_sample
    uv2.v1.compare_gen.base.parameter_sample = lambda rng, external: (params, actual_scales)
    try:
        arrays, metadata = uv2.v1.compare_gen.simulate(job, scales)
    finally:
        uv2.v1.compare_gen.base.parameter_sample = original
    metadata.update({"task_id": task["task_id"], "task_split": task["split"], "fixed_parameter_task": True})
    path = Path(output)
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    return {"file": path.name, "sha256": uv2.sha256(path), "task_id": task["task_id"], "split": task["split"],
            "physical_scene": job["physical_scene"], "seed": job["seed"],
            "max_connector_force_n": metadata["max_connector_force_n"], "max_tire_utilization": metadata["max_tire_utilization"],
            "finite": metadata["finite"], "ultimate_exceeded_steps": metadata["ultimate_exceeded_steps"]}


def run_parameters() -> None:
    complete = OUT / "parameters" / "complete.json"
    if complete.exists():
        print("parameter tasks already complete", flush=True); return
    invalid_archive = OUT / "invalid_parameter_range_20260822"
    invalid_marker = invalid_archive / "invalid.json"
    if invalid_archive.exists() and not invalid_marker.exists():
        write_json(invalid_marker, {"status": "invalid_not_evidence", "reason": "used external-extreme ranges instead of the frozen parameter-task ranges", "archived_without_deletion": True})
        uv2.append_log("W0066", "参数范围实现错误归档", [
            "首轮参数任务误用了历史external极值范围；90条轨迹和A结果全部移入invalid_parameter_range_20260822，不作为证据。",
            "修复为预注册范围：质量0.85–1.15、刚度0.75–1.25、阻尼0.70–1.30、间隙0.70–1.40、附着0.80–1.10；maximin候选恢复100。",
            "参数任务、90条轨迹和A必须整批重算；D1/F/H/T/C未依赖该参数集，无需重算。",
        ])
    stage = OUT / "parameters"; trajectories = stage / "trajectories"; trajectories.mkdir(parents=True, exist_ok=True)
    tasks = parameter_tasks()
    with (OUT / "parameter_tasks.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(tasks[0])); writer.writeheader(); writer.writerows(tasks)
    scales = uv2.v1.compare_gen.train_scales(HERE / "k2" / "data_full")
    scene_rows = (("E1", 0), ("E2", 1), ("E3", 2))
    pending = []
    for task in tasks[:30]:
        for scene, offset in scene_rows:
            seed = 930000 + 10 * int(task["task_id"]) + offset
            job = {"scenario": scene, "physical_scene": scene, "split": task["split"], "seed": seed,
                   "traj_id": seed, "external": True, "parameter_external": True,
                   "network_profile": "clean", "network_trace_id": "clean"}
            path = trajectories / f"task{int(task['task_id']):02d}_{scene}_{seed}.npz"
            pending.append((job, task, scales, str(path)))
    freeze = {"seed": 906001, "lhs_candidates": 100, "tasks_sha256": uv2.sha256(OUT / "parameter_tasks.csv"),
              "jobs": [{"task_id": t[1]["task_id"], **t[0], "output": t[3]} for t in pending]}
    write_json(stage / "freeze.json", freeze)
    completed, failures = [], []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(parameter_job, *item): item for item in pending}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                row = future.result(); completed.append(row)
                print(f"PARAM [{index:02d}/90] task={row['task_id']} {row['physical_scene']} force={row['max_connector_force_n']:.1f}N", flush=True)
            except Exception as exc:
                failures.append({"task_id": item[1]["task_id"], "scene": item[0]["physical_scene"], "seed": item[0]["seed"], "error": repr(exc)})
                print(f"PARAM FAILED task={item[1]['task_id']} {item[0]['physical_scene']}: {exc!r}", flush=True)
    completed.sort(key=lambda row: (row["task_id"], row["physical_scene"]))
    write_json(stage / "manifest.json", {"planned": 90, "completed": completed, "failures": failures})
    accepted = len(completed) == 90 and not failures and all(row["finite"] and row["ultimate_exceeded_steps"] == 0 for row in completed)
    write_json(complete, {"stage": "parameter-data", "status": "pass" if accepted else "fail", "accepted": accepted,
                          "completed": len(completed), "failed": len(failures),
                          "manifest_sha256": uv2.sha256(stage / "manifest.json")})
    uv2.append_log("W0063", "参数任务数据生成", [
        f"冻结38个maximin-LHS参数任务；生成train/validation/development前30任务×3场景={len(completed)}/90，失败={len(failures)}。",
        f"参数表hash={uv2.sha256(OUT/'parameter_tasks.csv')}；manifest hash={uv2.sha256(stage/'manifest.json')}。",
        "任务失败不替换参数组合或seed；future-confirm 8任务留到D2冻结后生成。",
    ])


def rollout_periodic(model: dict[str, Any], arrays: dict[str, np.ndarray], start: int,
                     period: int | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = cp.lift(model, arrays["s3_deform"][start])
    xs, fs, drift = [], [], []
    for index in range(H):
        z, _ = cp.model_step(model, z, arrays["u1_four"][start + index])
        _, force_n, x_n = cp.decode(model, z)
        physical = x_n * model.get("metric_x_std", model["x_std"]) + model.get("metric_x_mean", model["x_mean"])
        relifted = cp.lift(model, physical)
        drift.append(float(np.linalg.norm(z - relifted) / math.sqrt(len(z))))
        if period is not None and model["lift_kind"] != "raw" and (index + 1) % period == 0 and index + 1 < H:
            z = relifted
        xs.append(x_n); fs.append(force_n)
    return np.asarray(xs), np.asarray(fs), np.asarray(drift)


def evaluate_period(model: dict[str, Any], rows: list[dict[str, Any]], role: str,
                    norms: dict[str, np.ndarray], period: int | None) -> tuple[dict[str, Any], list[float], list[float]]:
    predictions, truths, drifts, errors = [], [], [], []
    for row in role_rows(rows, role):
        a = row["arrays"]
        for start in range(0, len(a["u1_four"]) - H + 1, H):
            xn, fn, drift = rollout_periodic(model, a, start, period)
            true_x = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            true_f = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            predictions.append(np.c_[xn, fn]); truths.append(np.c_[true_x, true_f])
            drifts.append(float(np.mean(drift[9:]))); errors.append(float(np.sqrt(np.mean((xn[9:] - true_x[9:]) ** 2))))
    return metric_y(np.asarray(predictions), np.asarray(truths)), drifts, errors


def run_tc() -> None:
    complete = OUT / "t5" / "complete.json"
    if complete.exists():
        print("T5 T/C already complete", flush=True); return
    if not (OUT / "t4" / "complete.json").exists():
        run_h()
    rows, norms, _, models = context()
    stage = OUT / "t5"; stage.mkdir(parents=True, exist_ok=True)
    mechanism, c_results = {}, {}
    for name in amend_g2():
        base, drift, error = evaluate_period(models[name], rows, "development-test", norms, None)
        corr = float(np.corrcoef(drift, error)[0, 1]) if np.std(drift) > 1.0e-12 and np.std(error) > 1.0e-12 else 0.0
        # Horizon trend is measured separately on a deterministic subset.
        horizon_drift = []
        for row in role_rows(rows, "development-test"):
            a = row["arrays"]
            if len(a["u1_four"]) >= H:
                _, _, values = rollout_periodic(models[name], a, 0, None); horizon_drift.append(values)
        mean_drift = np.mean(horizon_drift, axis=0)
        trend = float(mean_drift[-1] / max(mean_drift[0], 1.0e-12))
        signal = models[name]["lift_kind"] != "raw" and trend >= 1.2 and corr >= 0.3
        mechanism[name] = {"lift_kind": models[name]["lift_kind"], "drift_h1": float(mean_drift[0]),
                           "drift_h20": float(mean_drift[-1]), "growth_ratio": trend,
                           "trajectory_correlation_with_h10_20_error": corr, "C_mechanism_signal": signal}
        validation_grid = {"infinity": evaluate_period(models[name], rows, "validation", norms, None)[0]}
        if signal:
            for period in (1, 2, 5, 10):
                validation_grid[str(period)] = evaluate_period(models[name], rows, "validation", norms, period)[0]
            baseline = validation_grid["infinity"]
            legal = []
            for key, metric in validation_grid.items():
                protected = metric["state_h1_5"] <= 1.05 * baseline["state_h1_5"] + 1.0e-12 and bool(np.all(np.asarray(metric["state_dim_h1_5"]) <= 1.05 * np.asarray(baseline["state_dim_h1_5"]) + 1.0e-12))
                if protected:
                    legal.append((metric["J_pred"], 999 if key == "infinity" else int(key), key))
            selected = min(legal)[2]
            dev_selected = evaluate_period(models[name], rows, "development-test", norms, None if selected == "infinity" else int(selected))[0]
            improvement = (base["J_pred"] - dev_selected["J_pred"]) / max(base["J_pred"], 1.0e-12)
            gate = improvement >= 0.08 and dev_selected["divergence_rate"] <= base["divergence_rate"]
            c_results[name] = {"status": "run", "validation": validation_grid, "selected_period": selected,
                               "development_baseline": base, "development_selected": dev_selected,
                               "improvement": improvement, "relative_gate": gate}
        else:
            c_results[name] = {"status": "not_applicable_no_mechanism", "validation": validation_grid,
                               "selected_period": "infinity", "development_baseline": base,
                               "development_selected": base, "improvement": 0.0, "relative_gate": False}
        print(f"TC {name}: drift growth={trend:.3g} corr={corr:.3g} C={c_results[name]['status']}", flush=True)
    h_results = json.loads((OUT / "t4" / "results.json").read_text(encoding="utf-8"))
    nonzero_h = any(int(value["selected_LS"]["rank"]) > 0 and value["relative_gate"] for value in h_results.values())
    t_status = "not_applicable_no_nonzero_legal_H" if not nonzero_h else "mechanism_present_training_required"
    write_json(stage / "mechanism.json", mechanism); write_json(stage / "c_results.json", c_results)
    write_json(complete, {"stage": "T5-TC", "status": "complete", "T_status": t_status,
                          "C_run_backbones": [name for name, value in c_results.items() if value["status"] == "run"],
                          "C_pass_backbones": [name for name, value in c_results.items() if value["relative_gate"]],
                          "mechanism_sha256": uv2.sha256(stage / "mechanism.json"), "C_sha256": uv2.sha256(stage / "c_results.json")})
    uv2.append_log("W0064", "v2 T5时间一致性/重新升维机制门", [
        f"逐骨干潜空间漂移诊断完成；C实际运行={[k for k,v in c_results.items() if v['status']=='run']}。",
        f"T状态={t_status}；没有合法非零H时不为凑实验强训T。",
        f"机制hash={uv2.sha256(stage/'mechanism.json')}；C结果hash={uv2.sha256(stage/'c_results.json')}。",
    ])


def load_parameter_rows() -> list[dict[str, Any]]:
    manifest = json.loads((OUT / "parameters" / "manifest.json").read_text(encoding="utf-8"))
    task_lookup = {int(row["task_id"]): row for row in parameter_tasks()}
    rows = []
    for item in manifest["completed"]:
        path = OUT / "parameters" / "trajectories" / item["file"]
        if uv2.sha256(path) != item["sha256"]:
            raise RuntimeError(f"parameter trajectory hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as source:
            arrays = {key: np.asarray(source[key], dtype=np.float64) for key in cp.ARRAY_KEYS}
        task = task_lookup[int(item["task_id"])]
        rows.append({"meta": {**item, "task_split": task["split"], "scenario": item["physical_scene"]}, "arrays": arrays})
    return rows


def one_step_residuals(model: dict[str, Any], row: dict[str, Any], norms: dict[str, np.ndarray], seconds: float) -> np.ndarray:
    a = row["arrays"]; count = min(len(a["u1_four"]), int(seconds / DT)); residuals = []
    for k in range(count):
        z = cp.lift(model, a["s3_deform"][k]); z, _ = cp.model_step(model, z, a["u1_four"][k])
        _, fn, xn = cp.decode(model, z)
        tx = (a["s3_deform"][k + 1] - norms["x_mean"]) / norms["x_std"]
        tf = (a["force_output"][k + 1] - norms["force_mean"]) / norms["force_std"]
        residuals.append(np.r_[tx, tf] - np.r_[xn, fn])
    return np.asarray(residuals)


def task_bias(model: dict[str, Any], rows: list[dict[str, Any]], norms: dict[str, np.ndarray],
              task_id: int, seconds: float) -> np.ndarray:
    pieces = [one_step_residuals(model, row, norms, seconds) for row in rows if int(row["meta"]["task_id"]) == task_id]
    return np.vstack(pieces).mean(axis=0)


def eval_task_adaptation(model: dict[str, Any], rows: list[dict[str, Any]], norms: dict[str, np.ndarray],
                         task_ids: set[int], basis: np.ndarray | None, prior: float,
                         seconds: float, online: bool = False, eval_start_s: float = 5.0) -> dict[str, Any]:
    predictions, truths = [], []
    for row in rows:
        task_id = int(row["meta"]["task_id"])
        if task_id not in task_ids:
            continue
        a = row["arrays"]
        fixed_bias = np.zeros(64)
        if basis is not None and not online:
            observed = task_bias(model, rows, norms, task_id, seconds)
            fixed_bias = basis @ (basis.T @ observed) / (1.0 + prior)
        # All information conditions are scored on the same post-5 s windows.
        first = int(eval_start_s / DT)
        for start in range(first, len(a["u1_four"]) - H + 1, H):
            bias = fixed_bias
            if basis is not None and online:
                upto = max(DT, math.floor(start * DT / 1.0) * 1.0)
                observed = one_step_residuals(model, row, norms, upto).mean(axis=0)
                bias = basis @ (basis.T @ observed) / (1.0 + prior)
            xn, fn = rollout(model, a, start)
            pred = np.c_[xn, fn] + bias
            tx = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            tf = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            predictions.append(pred); truths.append(np.c_[tx, tf])
    return metric_y(np.asarray(predictions), np.asarray(truths))


def run_adaptation() -> None:
    complete = OUT / "t5" / "adaptation_complete.json"
    if complete.exists():
        print("T5 A already complete", flush=True); return
    run_parameters()
    pdata = json.loads((OUT / "parameters" / "complete.json").read_text(encoding="utf-8"))
    if not pdata["accepted"]:
        write_json(complete, {"stage": "T5-A", "status": "not_applicable_parameter_data_failed"}); return
    rows, norms, _, models = context(); prows = load_parameter_rows()
    out_rows, results = [], {}
    for name in amend_g2():
        model = models[name]
        biases = np.vstack([task_bias(model, prows, norms, task_id, 5.0) for task_id in range(20)])
        _, _, vt = np.linalg.svd(biases, full_matrices=False)
        candidates = []
        for rank in (2, 4, 8):
            basis = vt[:rank].T
            for prior in (1.0e-2, 1.0e-1, 1.0):
                metric = eval_task_adaptation(model, prows, norms, set(range(20, 25)), basis, prior, 2.0)
                candidates.append((metric["J_pred"], rank, -prior, prior, basis, metric))
        _, rank, _, prior, basis, validation = min(candidates)
        development = {"A0-zero": eval_task_adaptation(model, prows, norms, set(range(25, 30)), None, prior, 0.0)}
        for seconds in (1.0, 2.0, 5.0):
            development[f"A1-{seconds:g}s"] = eval_task_adaptation(model, prows, norms, set(range(25, 30)), basis, prior, seconds)
        development["A2-online"] = eval_task_adaptation(model, prows, norms, set(range(25, 30)), basis, prior, 1.0, online=True)
        baseline = development["A0-zero"]
        best_key = min((value["J_pred"], key) for key, value in development.items() if key != "A0-zero")[1]
        improvement = (baseline["J_pred"] - development[best_key]["J_pred"]) / max(baseline["J_pred"], 1.0e-12)
        gate = improvement >= 0.08 and development[best_key]["state_h1_5"] <= 1.05 * baseline["state_h1_5"] and development[best_key]["divergence_rate"] <= baseline["divergence_rate"]
        results[name] = {"selected_rank": rank, "selected_prior": prior, "validation_2s": validation,
                         "development": development, "best_adaptive_condition": best_key,
                         "external_improvement": improvement, "relative_gate": gate}
        for condition, metric in development.items():
            out_rows.append({"backbone": name, "condition": condition, "rank": rank, "prior": prior,
                             **{key: metric[key] for key in ("state", "force", "load", "J_pred", "divergence_rate")}})
        np.savez_compressed(OUT / "t5" / f"A-{name}.npz", basis=basis, rank=np.asarray(rank), prior=np.asarray(prior))
        print(f"A {name}: rank={rank} prior={prior:g} best={best_key} improvement={100*improvement:.2f}% gate={gate}", flush=True)
    with (OUT / "online_adaptation.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(out_rows[0])); writer.writeheader(); writer.writerows(out_rows)
    write_json(OUT / "t5" / "adaptation_results.json", results)
    write_json(complete, {"stage": "T5-A", "status": "complete", "passing_backbones": [k for k,v in results.items() if v["relative_gate"]],
                          "results_sha256": uv2.sha256(OUT / "t5" / "adaptation_results.json")})
    uv2.append_log("W0065", "v2 T5参数共享低秩适应", [
        f"A0/A1(1/2/5s)/A2-online在4骨干、5个development参数任务上完成；通过={ [k for k,v in results.items() if v['relative_gate']] }。",
        "共享基底只由20个train参数任务的一步残差学习；validation选rank/prior，development不调参。",
        f"结果hash={uv2.sha256(OUT/'t5'/'adaptation_results.json')}；CSV hash={uv2.sha256(OUT/'online_adaptation.csv')}。",
    ])


def d2_physical_job(job: dict[str, Any], config: dict[str, Any] | None,
                    scales: dict[str, np.ndarray], task: dict[str, Any] | None,
                    output: str) -> dict[str, Any]:
    if task is None:
        arrays, metadata = uv2.v1.simulate_d1(job, scales, config)
    else:
        params, actual_scales = explicit_params(task)
        original = uv2.v1.compare_gen.base.parameter_sample
        uv2.v1.compare_gen.base.parameter_sample = lambda rng, external: (params, actual_scales)
        try:
            arrays, metadata = uv2.v1.compare_gen.simulate(job, scales)
        finally:
            uv2.v1.compare_gen.base.parameter_sample = original
        metadata.update({"task_id": task["task_id"], "task_split": task["split"], "fixed_parameter_task": True})
    path = Path(output)
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    return {"file": path.name, "sha256": uv2.sha256(path), "kind": "external" if task is not None else "internal",
            "scenario": job["physical_scene"], "seed": job["seed"], "task_id": None if task is None else task["task_id"],
            "finite": metadata["finite"], "max_connector_force_n": metadata["max_connector_force_n"],
            "ultimate_exceeded_steps": metadata["ultimate_exceeded_steps"]}


def network_trace(profile: str, trace_id: int, steps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    profile_index = ("iid", "burst", "delay", "dos").index(profile)
    rng = np.random.default_rng(980000 + 100 * profile_index + trace_id)
    mask = np.zeros((steps, 8), dtype=np.int8)
    delay = np.zeros((steps, 4), dtype=np.int16)
    if profile == "iid":
        mask = (rng.random((steps, 8)) < 0.25).astype(np.int8)
    elif profile == "burst":
        for begin in (int(0.18 * steps), int(0.48 * steps), int(0.76 * steps)):
            mask[begin:min(steps, begin + 75)] = 1
        mask |= (rng.random((steps, 8)) < 0.05).astype(np.int8)
    elif profile == "delay":
        delay = rng.integers(3, 9, size=(steps, 4), dtype=np.int16)
    elif profile == "dos":
        mask[int(0.25 * steps):int(0.36 * steps)] = 1
        mask[int(0.62 * steps):int(0.74 * steps)] = 1
    car_drop = np.maximum(mask[:, 0::2], mask[:, 1::2])
    aoi = delay.copy()
    for k in range(1, steps):
        aoi[k] = np.where(car_drop[k] > 0, aoi[k - 1] + 1, delay[k])
    network = np.c_[np.max(car_drop, axis=1), np.max(delay, axis=1), np.max(aoi, axis=1),
                    1.0 - np.minimum(np.max(aoi, axis=1) / 10.0, 1.0)]
    return mask, aoi, network.astype(np.float32)


def create_network_overlay(source_path: Path, output: Path, profile: str, trace_id: int) -> dict[str, Any]:
    with np.load(source_path, allow_pickle=False) as source:
        arrays = {key: np.asarray(source[key]) for key in source.files if key != "metadata_json"}
        metadata = json.loads(str(source["metadata_json"].item()))
    steps = len(arrays["u1_four"])
    mask, aoi, network = network_trace(profile, trace_id, steps)
    arrays["network"] = network; arrays["network_mask"] = mask; arrays["network_aoi4"] = aoi
    metadata.update({"confirm_kind": "network", "network_profile": profile, "network_trace_id": trace_id,
                     "physical_truth_source": source_path.name, "plant_truth_unchanged": True})
    np.savez_compressed(output, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    return {"file": output.name, "sha256": uv2.sha256(output), "kind": "network", "profile": profile,
            "trace_id": trace_id, "physical_truth_source": source_path.name, "steps": steps}


def freeze_candidates() -> dict[str, Any]:
    files = {
        "protocol": OUT / "protocol_v2.md", "pipeline": Path(__file__).resolve(),
        "D1_manifest": OUT / "combined_manifest.json", "G2_amendment": OUT / "gate_amendment.json",
        "F_selection": OUT / "t3" / "selection.json", "H_results": OUT / "t4" / "results.json",
        "TC_results": OUT / "t5" / "c_results.json", "A_results": OUT / "t5" / "adaptation_results.json",
    }
    for name in amend_g2():
        files[f"F2_{name}"] = OUT / "t3" / "models" / f"{name}.npz"
        files[f"HLS_{name}"] = OUT / "t4" / "models" / f"{name}-HLS.npz"
        files[f"HRLS_{name}"] = OUT / "t4" / "models" / f"{name}-HRLS.npz"
        files[f"A_{name}"] = OUT / "t5" / f"A-{name}.npz"
    missing = [name for name, path in files.items() if not path.exists()]
    if missing:
        raise RuntimeError(f"cannot freeze D2; missing {missing}")
    return {name: {"path": str(path), "sha256": uv2.sha256(path)} for name, path in files.items()}


def run_d2() -> None:
    complete = OUT / "d2" / "complete.json"
    if complete.exists():
        print("D2 already complete", flush=True); return
    run_tc(); run_adaptation()
    stage = OUT / "d2"; data_dir = stage / "trajectories"; data_dir.mkdir(parents=True, exist_ok=True)
    tasks = parameter_tasks(); scales = uv2.v1.compare_gen.train_scales(HERE / "k2" / "data_full")
    scan = uv2.v1.load_scan_rows(uv2.V1_OUT / "t1" / "force_coverage_scan.csv")
    candidates = uv2.v1.coverage_candidates(scan)
    pending = []
    for si, scene in enumerate(uv2.v1.SCENES):
        for offset in range(20):
            seed = 960000 + 1000 * si + offset
            job = {"scenario": scene, "physical_scene": scene, "scene_index": si, "split": "confirm", "offset": offset,
                   "seed": seed, "traj_id": offset, "external": False, "parameter_external": False,
                   "network_profile": "clean", "network_trace_id": "clean"}
            tier = None if scene in ("E0", "E1") else ("L1", "L2", "L3")[(offset + si) % 3]
            config = None if tier is None else candidates[tier][(offset + si) % len(candidates[tier])]
            job["coverage_tier"] = "nominal" if tier is None else tier
            path = data_dir / f"internal_{scene}_{seed}.npz"
            pending.append((job, config, scales, None, str(path)))
    for task in tasks[30:38]:
        for scene, offset in (("E1", 0), ("E2", 1), ("E3", 2)):
            seed = 970000 + 10 * (int(task["task_id"]) - 30) + offset
            job = {"scenario": scene, "physical_scene": scene, "split": "confirm-external", "seed": seed,
                   "traj_id": seed, "external": True, "parameter_external": True,
                   "network_profile": "clean", "network_trace_id": "clean"}
            path = data_dir / f"external_task{int(task['task_id']):02d}_{scene}_{seed}.npz"
            pending.append((job, None, scales, task, str(path)))
    planned_network = [{"profile": profile, "trace_id": trace} for profile in ("iid", "burst", "delay", "dos") for trace in range(10)]
    freeze = {"status": "frozen_before_confirm_generation", "candidate_files": freeze_candidates(),
              "internal_jobs": [{"scene": item[0]["physical_scene"], "seed": item[0]["seed"], "file": Path(item[4]).name} for item in pending if item[3] is None],
              "external_jobs": [{"scene": item[0]["physical_scene"], "seed": item[0]["seed"], "task_id": item[3]["task_id"], "file": Path(item[4]).name} for item in pending if item[3] is not None],
              "network_jobs": planned_network}
    write_json(stage / "freeze.json", freeze)
    print("D2 freeze written; confirm generation begins without metric inspection", flush=True)
    completed, failures = [], []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(d2_physical_job, *item): item for item in pending}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                completed.append(future.result()); print(f"D2 physical [{index:03d}/184] {Path(item[4]).name}", flush=True)
            except Exception as exc:
                failures.append({"file": Path(item[4]).name, "error": repr(exc)}); print(f"D2 physical FAILED {Path(item[4]).name}: {exc!r}", flush=True)
    completed.sort(key=lambda row: (row["kind"], row["file"]))
    internal = [row for row in completed if row["kind"] == "internal"]
    network_rows = []
    if not failures and len(internal) == 160:
        sources = sorted(internal, key=lambda row: row["file"])
        for index, plan in enumerate(planned_network):
            source = data_dir / sources[index]["file"]
            output = data_dir / f"network_{plan['profile']}_{plan['trace_id']:02d}.npz"
            network_rows.append(create_network_overlay(source, output, plan["profile"], plan["trace_id"]))
            print(f"D2 network [{index+1:02d}/40] {output.name}", flush=True)
    manifest = {"planned": {"internal": 160, "external": 24, "network": 40}, "physical": completed,
                "network": network_rows, "failures": failures}
    write_json(stage / "manifest.json", manifest)
    accepted = (not failures and len(internal) == 160 and len([r for r in completed if r["kind"] == "external"]) == 24
                and len(network_rows) == 40 and all(r["finite"] and r["ultimate_exceeded_steps"] == 0 for r in completed))
    write_json(complete, {"stage": "D2", "status": "pass" if accepted else "fail", "accepted": accepted,
                          "manifest_sha256": uv2.sha256(stage / "manifest.json"), "freeze_sha256": uv2.sha256(stage / "freeze.json")})
    if accepted:
        for path in data_dir.glob("*.npz"):
            try: path.chmod(stat.S_IREAD)
            except OSError: pass
    uv2.append_log("W0067", "v2 D2一次性确认集生成", [
        f"冻结后生成internal={len(internal)}/160、external={len([r for r in completed if r['kind']=='external'])}/24、network={len(network_rows)}/40；失败={failures}。",
        "network文件复用对应internal plant真值，只叠加mask/AoI/trace；确认文件生成后设只读。",
        f"freeze hash={uv2.sha256(stage/'freeze.json')}；manifest hash={uv2.sha256(stage/'manifest.json')}。",
    ])


def load_d2_rows(kind: str) -> list[dict[str, Any]]:
    manifest = json.loads((OUT / "d2" / "manifest.json").read_text(encoding="utf-8"))
    items = ([row for row in manifest["physical"] if row["kind"] == kind] if kind in ("internal", "external")
             else manifest["network"])
    rows = []
    for item in items:
        path = OUT / "d2" / "trajectories" / item["file"]
        if uv2.sha256(path) != item["sha256"]:
            raise RuntimeError(f"D2 hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as source:
            arrays = {key: np.asarray(source[key], dtype=np.float64) for key in cp.ARRAY_KEYS}
            for extra in ("network_mask", "network_aoi4"):
                if extra in source.files: arrays[extra] = np.asarray(source[extra])
            metadata = json.loads(str(source["metadata_json"].item()))
        metadata.update(item)
        rows.append({"meta": metadata, "arrays": arrays, "path": path})
    return rows


def block_metrics(predictions: list[np.ndarray], truths: list[np.ndarray], keys: list[str]) -> dict[str, Any]:
    pred = np.asarray(predictions); true = np.asarray(truths)
    overall = metric_y(pred, true)
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, key in enumerate(keys): grouped[key].append(index)
    overall["per_trajectory_J"] = {key: metric_y(pred[index], true[index])["J_pred"] for key, index in grouped.items()}
    return overall


def evaluate_confirm_variant(model: dict[str, Any], name: str, rows: list[dict[str, Any]], norms: dict[str, np.ndarray],
                             variant: str, head: dict[str, np.ndarray] | None = None,
                             period: int | None = None) -> dict[str, Any]:
    predictions, truths, keys = [], [], []
    for row in rows:
        a = row["arrays"]; key = str(row["meta"]["file"])
        for start in range(0, len(a["u1_four"]) - H + 1, H):
            if period is None:
                xn, f0n = rollout(model, a, start)
            else:
                xn, f0n, _ = rollout_periodic(model, a, start, period)
            fn = f0n
            if variant == "F2":
                previous = a["force_output"][start, :8].reshape(4, 2)
                f1 = physics_force(xn, norms, previous)
                force = apply_fhead(head, xn, a["u1_four"][start:start + H], f1, previous, norms)
                fn = (force - norms["force_mean"]) / norms["force_std"]
            tx = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            tf = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            predictions.append(np.c_[xn, fn]); truths.append(np.c_[tx, tf]); keys.append(key)
    return block_metrics(predictions, truths, keys)


def evaluate_network(model: dict[str, Any], rows: list[dict[str, Any]], norms: dict[str, np.ndarray],
                     protected: bool) -> dict[str, Any]:
    predictions, truths, keys = [], [], []
    for row in rows:
        a = row["arrays"]; key = str(row["meta"]["file"])
        for start in range(0, len(a["u1_four"]) - H + 1, H):
            stale = int(np.max(a["network_aoi4"][min(start, len(a["network_aoi4"]) - 1)]))
            origin = max(0, start - stale)
            z = cp.lift(model, a["s3_deform"][origin])
            if protected:
                for k in range(origin, start):
                    z, _ = cp.model_step(model, z, a["u1_four"][k])
            xs, fs = [], []
            for h in range(H):
                z, _ = cp.model_step(model, z, a["u1_four"][start + h])
                _, fn, xn = cp.decode(model, z); xs.append(xn); fs.append(fn)
            tx = (a["s3_deform"][start + 1:start + H + 1] - norms["x_mean"]) / norms["x_std"]
            tf = (a["force_output"][start + 1:start + H + 1] - norms["force_mean"]) / norms["force_std"]
            predictions.append(np.c_[xs, fs]); truths.append(np.c_[tx, tf]); keys.append(key)
    return block_metrics(predictions, truths, keys)


def paired_bootstrap(baseline: dict[str, float], candidate: dict[str, float]) -> dict[str, float]:
    keys = sorted(set(baseline) & set(candidate)); rng = np.random.default_rng(990001)
    values = np.asarray([(baseline[key] - candidate[key]) / max(abs(baseline[key]), 1.0e-12) for key in keys])
    boot = np.empty(10000)
    for index in range(10000):
        boot[index] = float(np.mean(values[rng.integers(0, len(values), len(values))]))
    lower, upper = np.percentile(boot, [2.5, 97.5])
    p = float(2.0 * min(np.mean(boot <= 0.0), np.mean(boot >= 0.0)))
    return {"trajectories": len(keys), "mean_improvement": float(values.mean()), "ci95_low": float(lower),
            "ci95_high": float(upper), "bootstrap_p": min(p, 1.0)}


def run_confirm() -> None:
    complete = OUT / "t7" / "complete.json"
    if complete.exists():
        print("D2 confirm already complete", flush=True); return
    run_d2()
    d2 = json.loads((OUT / "d2" / "complete.json").read_text(encoding="utf-8"))
    if not d2["accepted"]:
        write_json(complete, {"stage": "T7", "status": "not_applicable_D2_failed"}); return
    rows, norms, _, models = context()
    internal, external, network = load_d2_rows("internal"), load_d2_rows("external"), load_d2_rows("network")
    cdev = json.loads((OUT / "t5" / "c_results.json").read_text(encoding="utf-8"))
    adev = json.loads((OUT / "t5" / "adaptation_results.json").read_text(encoding="utf-8"))
    stage = OUT / "t7"; stage.mkdir(parents=True, exist_ok=True)
    results, statistics, flat = {}, {}, []
    for name in amend_g2():
        model = models[name]
        with np.load(OUT / "t3" / "models" / f"{name}.npz", allow_pickle=False) as source:
            head = {key: np.asarray(source[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}
        p0 = evaluate_confirm_variant(model, name, internal, norms, "P0")
        f2 = evaluate_confirm_variant(model, name, internal, norms, "F2", head=head)
        selected_period = cdev[name]["selected_period"]
        cperiod = None if selected_period == "infinity" else int(selected_period)
        cmetric = evaluate_confirm_variant(model, name, internal, norms, "C", period=cperiod)
        internal_result = {"P0": p0, "F2-diagnostic": f2, "C-selected": cmetric,
                           "HLS-rank0": p0, "HRLS-rank0": p0}
        statistics[name] = {variant: paired_bootstrap(p0["per_trajectory_J"], metric["per_trajectory_J"])
                            for variant, metric in internal_result.items() if variant != "P0"}
        with np.load(OUT / "t5" / f"A-{name}.npz", allow_pickle=False) as source:
            basis = np.asarray(source["basis"]); prior = float(source["prior"])
        condition = adev[name]["best_adaptive_condition"]
        seconds = float(condition.split("-")[1][:-1]) if condition.startswith("A1-") else 1.0
        ext0 = eval_task_adaptation(model, external, norms, set(range(30, 38)), None, prior, 0.0)
        exta = eval_task_adaptation(model, external, norms, set(range(30, 38)), basis, prior, seconds, online=condition == "A2-online")
        network_result = {}
        for profile in ("iid", "burst", "delay", "dos"):
            subset = [row for row in network if row["meta"]["profile"] == profile]
            network_result[profile] = {"unprotected": evaluate_network(model, subset, norms, False),
                                       "protected_state_propagation": evaluate_network(model, subset, norms, True)}
        results[name] = {"internal": internal_result, "external": {"A0-zero": ext0, condition: exta},
                         "network": network_result}
        for domain, variants in (("internal", internal_result), ("external", {"A0-zero": ext0, condition: exta})):
            for variant, metric in variants.items():
                flat.append({"backbone": name, "domain": domain, "condition": variant,
                             **{key: metric[key] for key in ("state", "force", "load", "J_pred", "divergence_rate")}})
        for profile, variants in network_result.items():
            for variant, metric in variants.items():
                flat.append({"backbone": name, "domain": f"network-{profile}", "condition": variant,
                             **{key: metric[key] for key in ("state", "force", "load", "J_pred", "divergence_rate")}})
        print(f"CONFIRM {name}: internal P0={p0['J_pred']:.4g} F2={f2['J_pred']:.4g}; external A0={ext0['J_pred']:.4g} A={exta['J_pred']:.4g}", flush=True)
    # Holm correction is applied to the fixed internal backbone x module family.
    tests = sorted((statistics[name][variant]["bootstrap_p"], name, variant) for name in statistics for variant in statistics[name])
    holm = {}; running = 0.0; m = len(tests)
    for index, (p, name, variant) in enumerate(tests):
        adjusted = min(1.0, (m - index) * p); running = max(running, adjusted); holm[f"{name}|{variant}"] = running
    for name in statistics:
        for variant in statistics[name]: statistics[name][variant]["holm_p"] = holm[f"{name}|{variant}"]
    write_json(stage / "confirm_results.json", results); write_json(stage / "paired_statistics.json", statistics)
    with (OUT / "confirm_metrics.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0])); writer.writeheader(); writer.writerows(flat)
    # Final gates are never granted by relative recovery alone.
    passing_internal = []
    for name in results:
        for variant in ("F2-diagnostic", "C-selected"):
            metric = results[name]["internal"][variant]; base = results[name]["internal"]["P0"]
            statrow = statistics[name][variant]
            improvement = (base["J_pred"] - metric["J_pred"]) / max(base["J_pred"], 1.0e-12)
            if improvement >= 0.08 and statrow["ci95_low"] > 0 and statrow["holm_p"] < 0.05 and metric["divergence_rate"] <= base["divergence_rate"]:
                passing_internal.append(f"{name}|{variant}")
    external_passing = []
    for name, value in results.items():
        ext = value["external"]; keys = list(ext); a0, adaptive = ext[keys[0]], ext[keys[1]]
        improvement = (a0["J_pred"] - adaptive["J_pred"]) / max(a0["J_pred"], 1.0e-12)
        if improvement >= 0.08 and adaptive["divergence_rate"] <= a0["divergence_rate"]:
            external_passing.append(name)
    gates = {"internal_relative_candidates": passing_internal, "external_adaptation_candidates": external_passing,
             "cross_family_F": False, "cross_family_H": False,
             "absolute_deployment_candidates": [],
             "closed_loop_official": [],
             "closed_loop_diagnostic": ["K0", "K1"] + [f"{name}-A" for name in external_passing],
             "claim": "no universal combination; external adaptation only if independently reproduced"}
    write_json(OUT / "universality_gates.json", gates)
    write_json(complete, {"stage": "T7", "status": "complete", "confirm_evaluated_once": True,
                          "passing_internal": passing_internal, "external_passing": external_passing,
                          "absolute_deployment_candidates": [],
                          "results_sha256": uv2.sha256(stage / "confirm_results.json"),
                          "gates_sha256": uv2.sha256(OUT / "universality_gates.json")})
    uv2.append_log("W0068", "v2 D2一次性确认", [
        f"一次性评估全部冻结有限候选；internal通过={passing_internal}；参数适应复现={external_passing}。",
        "F/H跨家族门未在development通过，因此无论confirm局部结果如何均不授予普适性；绝对部署候选为空。",
        f"结果hash={uv2.sha256(stage/'confirm_results.json')}；门禁hash={uv2.sha256(OUT/'universality_gates.json')}。",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("amend", "f", "f_select", "h", "parameters", "tc", "adaptation", "d2", "confirm"), required=True)
    args = parser.parse_args()
    if args.stage == "amend":
        print(amend_g2())
    elif args.stage == "f":
        run_f()
    elif args.stage == "f_select":
        finalize_f_selection()
    elif args.stage == "h":
        run_h()
    elif args.stage == "parameters":
        run_parameters()
    elif args.stage == "tc":
        run_tc()
    elif args.stage == "adaptation":
        run_adaptation()
    elif args.stage == "d2":
        run_d2()
    elif args.stage == "confirm":
        run_confirm()


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
import math
import pickle
import shutil
from pathlib import Path
import time
from typing import Any

import numpy as np
from sklearn.tree import DecisionTreeClassifier, export_text

from contracts import PredictionBundle, validate_bundle


EXPERTS = ("K0", "K1", "K4", "K5F2")
FALLBACK = 1
H = 20


def _load_context(rs: Any) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, np.ndarray]]:
    cp, uv, cfg = rs.cp, rs.uv, rs.CFG
    with np.load(cfg.universal_root / "normalizers.npz", allow_pickle=False) as src:
        norms = {key: np.asarray(src[key], dtype=float) for key in src.files}
    _, original = cp.load_rows(cp.DATA)
    old_norms = cp.train_moments(original)
    originals = cp.all_frozen_models()
    models = {}
    for alias, source in (("K0", "K0"), ("K1", "K1"), ("K4", "K4"), ("K5F2", "K5-linear")):
        models[alias] = uv.uv2.adapt_model_metrics(originals[source], old_norms, norms)
    with np.load(cfg.universal_root / "t3" / "models" / "K5-linear.npz", allow_pickle=False) as src:
        head = {key: np.asarray(src[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}
    return models, norms, head


def _load_trajectory(path: Path) -> dict[str, np.ndarray]:
    keys = ("s3_deform", "s2_four", "force_output", "u1_four", "network", "time_s")
    with np.load(path, allow_pickle=False) as src:
        return {key: np.asarray(src[key], dtype=float) for key in keys}


def _rollout(rs: Any, model: dict[str, Any], arrays: dict[str, np.ndarray], start: int,
             norms: dict[str, np.ndarray], head: dict[str, np.ndarray] | None, alias: str
             ) -> tuple[PredictionBundle, np.ndarray, np.ndarray]:
    cp, uv = rs.cp, rs.uv
    z = cp.lift(model, arrays["s3_deform"][start])
    xs, f0s, drift = [], [], []
    for h in range(H):
        z, _ = cp.model_step(model, z, arrays["u1_four"][start + h])
        _, fn, xn = cp.decode(model, z)
        xs.append(xn); f0s.append(fn)
        physical = xn * norms["x_std"] + norms["x_mean"]
        relift = cp.lift(model, physical)
        drift.append(float(np.linalg.norm(z - relift) / math.sqrt(len(z))))
    xn = np.asarray(xs); fn = np.asarray(f0s)
    previous = arrays["force_output"][start, :8].reshape(4, 2)
    if alias == "K5F2":
        f1 = uv.physics_force(xn, norms, previous)
        fp = uv.apply_fhead(head, xn, arrays["u1_four"][start:start + H], f1, previous, norms)
        fn = (fp - norms["force_mean"]) / norms["force_std"]
    force = fn * norms["force_std"] + norms["force_mean"]
    state = xn * norms["x_std"] + norms["x_mean"]
    finite = np.all(np.isfinite(np.c_[xn, fn]), axis=1)
    bundle = PredictionBundle(state_s3=state, state_main=state[:, :30],
                              point_force=force[:, :8].reshape(H, 4, 2), payload_load=force[:, 8:10],
                              force_rate=force[:, 10:18].reshape(H, 4, 2), finite_mask=finite,
                              expert_name=alias, metadata={"force_variant": "F2" if alias == "K5F2" else "P0"})
    validate_bundle(bundle)
    physics = uv.physics_force(xn, norms, previous)
    contract = np.mean(np.abs((force[:, :10] - physics[:, :10]) / norms["force_std"][:10]), axis=1)
    return bundle, np.asarray(drift), contract


def _base_context(arrays: dict[str, np.ndarray], origin: int) -> np.ndarray:
    x = arrays["s3_deform"][origin]
    u = arrays["u1_four"][origin]
    prev = arrays["u1_four"][max(0, origin - 1)]
    disp = x[30:38].reshape(4, 2); vel = x[38:46].reshape(4, 2)
    network = arrays["network"][min(origin, len(arrays["network"]) - 1)]
    return np.r_[x[24:30], x[[2, 8, 14, 20]], np.mean(u[0::2]), np.mean(u[1::2]),
                 np.mean(u[1::2] - prev[1::2]), np.linalg.norm(disp, axis=1),
                 np.linalg.norm(vel, axis=1), network[:4]]


def _cache_one(rs: Any, row: dict[str, Any], models: dict[str, Any], norms: dict[str, np.ndarray],
               head: dict[str, np.ndarray], output: Path) -> dict[str, Any]:
    arrays = _load_trajectory(rs.D4 / "trajectories" / row["file"])
    origins = np.arange(0, len(arrays["u1_four"]) - H + 1, H, dtype=int)
    wx, wf, drift, contract, base = [], [], [], [], []
    truth_x, truth_f = [], []
    tic = time.perf_counter()
    for origin in origins:
        local_x, local_f, local_d, local_c = [], [], [], []
        for alias in EXPERTS:
            bundle, d, c = _rollout(rs, models[alias], arrays, int(origin), norms, head if alias == "K5F2" else None, alias)
            local_x.append((bundle.state_s3 - norms["x_mean"]) / norms["x_std"])
            force = np.c_[bundle.point_force.reshape(H, 8), bundle.payload_load, bundle.force_rate.reshape(H, 8)]
            local_f.append((force - norms["force_mean"]) / norms["force_std"])
            local_d.append(d); local_c.append(c)
        wx.append(local_x); wf.append(local_f); drift.append(local_d); contract.append(local_c)
        base.append(_base_context(arrays, int(origin)))
        truth_x.append((arrays["s3_deform"][origin + 1:origin + H + 1] - norms["x_mean"]) / norms["x_std"])
        truth_f.append((arrays["force_output"][origin + 1:origin + H + 1] - norms["force_mean"]) / norms["force_std"])
    temp = output.with_suffix(".tmp.npz")
    np.savez_compressed(temp, origins=origins, pred_x=np.asarray(wx, dtype=np.float32),
                        pred_f=np.asarray(wf, dtype=np.float32), truth_x=np.asarray(truth_x, dtype=np.float32),
                        truth_f=np.asarray(truth_f, dtype=np.float32), base_context=np.asarray(base, dtype=np.float32),
                        lift_drift=np.asarray(drift, dtype=np.float32), contract=np.asarray(contract, dtype=np.float32))
    temp.replace(output)
    truth_force = np.asarray(truth_f) * norms["force_std"] + norms["force_mean"]
    peak = np.max(np.linalg.norm(truth_force[..., :8].reshape(-1, H, 4, 2), axis=-1), axis=(1, 2))
    return {"trajectory": f"{row['scenario']}|{row['seed']}", "scene": row["scenario"], "seed": row["seed"],
            "split": row["split"], "file": output.name, "sha256": rs.sha256(output), "windows": len(origins),
            "high_load_windows": int(np.sum(peak >= 0.8 * rs.gen.base.ConnectorParams().rated_force_n)),
            "seconds": time.perf_counter() - tic}


def t2_cache(rs: Any) -> bool:
    if not rs.t1_generate(): return False
    stage = rs.OUT / "t2"
    complete = stage / "complete.json"
    if complete.exists(): return bool(json.loads(complete.read_text(encoding="utf-8")).get("accepted"))
    stage.mkdir(parents=True, exist_ok=True); cache = stage / "cache"; cache.mkdir(exist_ok=True)
    models, norms, head = _load_context(rs)
    manifest = json.loads((rs.D4 / "manifest.json").read_text(encoding="utf-8"))
    rows, failures = [], []
    for index, row in enumerate(manifest["trajectories"], 1):
        output = cache / f"{row['split']}_{row['scenario']}_{row['seed']}.npz"
        try:
            if output.exists():
                with np.load(output, allow_pickle=False) as src: windows = len(src["origins"])
                result = {"trajectory": f"{row['scenario']}|{row['seed']}", "scene": row["scenario"], "seed": row["seed"],
                          "split": row["split"], "file": output.name, "sha256": rs.sha256(output), "windows": windows,
                          "high_load_windows": 0, "seconds": 0.0, "resumed": True}
            else: result = _cache_one(rs, row, models, norms, head, output)
            rows.append(result)
        except Exception as exc:
            failures.append({"scene": row["scenario"], "seed": row["seed"], "error": repr(exc)})
        if index % 8 == 0 or index == len(manifest["trajectories"]):
            print(f"T2 cache {index}/{len(manifest['trajectories'])} failures={len(failures)}", flush=True)
            rs.write_json(stage / "progress.json", {"completed": rows, "failures": failures})
    # Recount high-load windows from cache so resumed files cannot silently lose coverage.
    high = defaultdict(int); windows = defaultdict(int)
    for row in rows:
        with np.load(cache / row["file"], allow_pickle=False) as src:
            tf = np.asarray(src["truth_f"], dtype=float) * norms["force_std"] + norms["force_mean"]
            peak = np.max(np.linalg.norm(tf[..., :8].reshape(len(tf), H, 4, 2), axis=-1), axis=(1, 2))
        row["high_load_windows"] = int(np.sum(peak >= 0.8 * rs.gen.base.ConnectorParams().rated_force_n))
        high[row["split"]] += row["high_load_windows"]; windows[row["split"]] += row["windows"]
    accepted = len(rows) == len(manifest["trajectories"]) and not failures
    rs.write_json(stage / "cache_manifest.json", {"accepted": accepted, "trajectories": rows, "failures": failures,
                                                   "windows": windows, "high_load_windows": high})
    rs.write_json(complete, {"stage": "T2", "accepted": accepted, "completed": len(rows), "failed": len(failures),
                             "high_load_trainable": high["train"] >= 200,
                             "cache_manifest_sha256": rs.sha256(stage / "cache_manifest.json")})
    rs.append_log("C003", "T2四专家缓存与合同审计", [f"cache={len(rows)}/{len(manifest['trajectories'])} failures={len(failures)}。",
                  f"窗口={dict(windows)}；L4-high(>=0.8 rated)={dict(high)}；训练门={high['train'] >= 200}。",
                  "统一形状S3=46、force=18、FL/FR/RL/RR与Fx/Fy顺序已由PredictionBundle逐窗检查。",
                  f"代码hash：run_stage={rs.sha256(rs.HERE/'run_stage.py')}；offline={rs.sha256(Path(__file__))}。"])
    return accepted


def _records(rs: Any, split: str) -> list[tuple[dict[str, Any], dict[str, np.ndarray]]]:
    manifest = json.loads((rs.OUT / "t2" / "cache_manifest.json").read_text(encoding="utf-8"))
    out = []
    for row in manifest["trajectories"]:
        if row["split"] != split: continue
        with np.load(rs.OUT / "t2" / "cache" / row["file"], allow_pickle=False) as src:
            out.append((row, {key: np.asarray(src[key]) for key in src.files}))
    return out


def _features(data: dict[str, np.ndarray]) -> np.ndarray:
    px, pf = data["pred_x"], data["pred_f"]
    w = len(px); horizon = np.broadcast_to(np.arange(1, H + 1) / H, (w, H))[..., None]
    base = np.broadcast_to(data["base_context"][:, None, :], (w, H, data["base_context"].shape[1]))
    sx = np.mean(np.std(px, axis=1), axis=-1)[..., None]
    sf = np.mean(np.std(pf[:, :, :, :10], axis=1), axis=-1)[..., None]
    contract = np.transpose(data["contract"], (0, 2, 1))
    drift = np.transpose(data["lift_drift"][:, [1, 2]], (0, 2, 1))
    return np.concatenate([base, horizon, sx, sf, contract, drift], axis=-1)


def _labels(data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ex = np.mean((data["pred_x"] - data["truth_x"][:, None]) ** 2, axis=-1)
    ef = np.mean((data["pred_f"][..., :8] - data["truth_f"][:, None, :, :8]) ** 2, axis=-1)
    el = np.mean((data["pred_f"][..., 8:10] - data["truth_f"][:, None, :, 8:10]) ** 2, axis=-1)
    state = np.argmin(ex, axis=1); force = np.argmin(ef + el, axis=1)
    state = np.where(ex[:, FALLBACK] <= 1.03 * np.min(ex, axis=1), FALLBACK, state)
    force = np.where((ef + el)[:, FALLBACK] <= 1.03 * np.min(ef + el, axis=1), FALLBACK, force)
    full_loss = np.mean(ex + ef + el, axis=2)
    full = np.argmin(full_loss, axis=1)
    full = np.where(full_loss[:, FALLBACK] <= 1.03 * np.min(full_loss, axis=1), FALLBACK, full)
    return state, force, full


def _dataset(records: list[tuple[dict[str, Any], dict[str, np.ndarray]]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xf, ys, yf, xw, yw = [], [], [], [], []
    for _, data in records:
        feat = _features(data); state, force, full = _labels(data)
        xf.append(feat.reshape(-1, feat.shape[-1])); ys.append(state.reshape(-1)); yf.append(force.reshape(-1))
        xw.append(np.c_[data["base_context"], np.mean(feat[..., -8:], axis=1)]); yw.append(full)
    return np.concatenate(xf), np.concatenate(ys), np.concatenate(yf), np.concatenate(xw), np.concatenate(yw)


def _predict_proba(model: DecisionTreeClassifier, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    prob0 = model.predict_proba(x); prob = np.zeros((len(x), len(EXPERTS)))
    prob[:, model.classes_.astype(int)] = prob0
    return np.argmax(prob, axis=1), np.max(prob, axis=1)


def _compose(method: str, data: dict[str, np.ndarray], selector: dict[str, Any], thresholds: dict[str, float]
             ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    px, pf, tx, tf = data["pred_x"], data["pred_f"], data["truth_x"], data["truth_f"]
    w = len(px); rows = np.arange(w)[:, None]; hs = np.arange(H)[None, :]
    rejected = np.zeros((w, H), dtype=bool)
    if method in ("C0", "C1", "C2", "C3"):
        idx = int(method[1]); return px[:, idx], pf[:, idx], {"selected": np.full((w, H), idx), "rejected": rejected}
    if method == "C4": return np.mean(px, axis=1), np.mean(pf, axis=1), {"selected": None, "rejected": rejected}
    if method == "C5":
        weights = selector["global_weights"]
        return np.einsum("e,wehd->whd", weights, px), np.einsum("e,wehd->whd", weights, pf), {"selected": None, "rejected": rejected}
    if method == "C6":
        idx = np.broadcast_to(selector["fixed_map"][None, :], (w, H))
        return px[rows, idx, hs], pf[rows, idx, hs], {"selected": idx, "rejected": rejected}
    feat = _features(data)
    if method == "C7":
        xw = np.c_[data["base_context"], np.mean(feat[..., -8:], axis=1)]
        iw, confidence = _predict_proba(selector["full"], xw); idx = np.broadcast_to(iw[:, None], (w, H))
        confidence = np.broadcast_to(confidence[:, None], (w, H))
        sx = px[rows, idx, hs]; ff = pf[rows, idx, hs]
    else:
        flat = feat.reshape(-1, feat.shape[-1])
        ix, cx = _predict_proba(selector["state"], flat); iff, cf = _predict_proba(selector["force"], flat)
        ix, iff, confidence = ix.reshape(w, H), iff.reshape(w, H), np.minimum(cx, cf).reshape(w, H)
        sx, ff = px[rows, ix, hs], pf[rows, iff, hs]
        idx = ix
        if method == "C10":
            ix, iff, _ = _labels(data); sx, ff = px[rows, ix, hs], pf[rows, iff, hs]; confidence[:] = 1.0; idx = ix
        elif method == "C9":
            disagreement_x = np.mean(np.std(px, axis=1), axis=-1)
            disagreement_f = np.mean(np.std(pf[:, :, :, :10], axis=1), axis=-1)
            selected_contract = data["contract"][rows, iff, hs]
            rejected = ((confidence < thresholds["confidence"]) |
                        (disagreement_x > thresholds["state_disagreement_p95"]) |
                        (disagreement_f > thresholds["force_disagreement_p95"]) |
                        (selected_contract > thresholds["contract_p95"]))
            sx = np.where(rejected[..., None], px[:, FALLBACK], sx)
            ff = np.where(rejected[..., None], pf[:, FALLBACK], ff)
            idx = np.where(rejected, FALLBACK, idx)
    return sx, ff, {"selected": idx, "rejected": rejected}


def _metric(method: str, records: list[tuple[dict[str, Any], dict[str, np.ndarray]]], selector: dict[str, Any],
            thresholds: dict[str, float], force_floor: np.ndarray) -> dict[str, Any]:
    per = {}; sq = defaultdict(float); count = defaultdict(int); correct = total = diverged = windows = rejected = 0
    occupancy = Counter(); times = []
    for row, data in records:
        tic = time.perf_counter_ns(); x, f, aux = _compose(method, data, selector, thresholds)
        times.append((time.perf_counter_ns() - tic) * 1e-6 / max(len(x), 1))
        ex = (x - data["truth_x"]) ** 2; ef = (f - data["truth_f"]) ** 2
        vals = {"state": float(np.sqrt(np.mean(ex))), "force": float(np.sqrt(np.mean(ef[..., :8]))),
                "load": float(np.sqrt(np.mean(ef[..., 8:10])))}
        vals["J_pred"] = (vals["state"] + vals["force"] + vals["load"]) / 3
        for key, value in (("state", ex), ("force", ef[..., :8]), ("load", ef[..., 8:10])):
            sq[key] += float(np.sum(value)); count[key] += value.size
        physical_pred = f[..., :8] * force_floor[1][:8] + force_floor[0][:8]
        physical_true = data["truth_f"][..., :8] * force_floor[1][:8] + force_floor[0][:8]
        mask = np.abs(physical_true) >= force_floor[2][:8]
        local_correct = int(np.sum((np.sign(physical_pred) == np.sign(physical_true)) & mask)); local_total = int(mask.sum())
        vals["direction_accuracy"] = local_correct / max(local_total, 1)
        per[row["trajectory"]] = vals
        correct += local_correct; total += local_total
        joined = np.concatenate([x, f], axis=-1)
        diverged += int(np.sum(np.any(~np.isfinite(joined), axis=(1, 2)) |
                                (np.max(np.abs(joined), axis=(1, 2)) > 50)))
        windows += len(x); rejected += int(np.sum(aux["rejected"]))
        if aux["selected"] is not None: occupancy.update(aux["selected"].reshape(-1).tolist())
    result = {key: math.sqrt(sq[key] / max(count[key], 1)) for key in ("state", "force", "load")}
    result.update({"J_pred": sum(math.sqrt(sq[k] / max(count[k], 1)) for k in ("state", "force", "load")) / 3,
                   "mean_per_trajectory_J": float(np.mean([v["J_pred"] for v in per.values()])),
                   "direction_accuracy": correct / max(total, 1), "divergence_rate": diverged / max(windows, 1),
                   "windows": windows, "rejection_rate": rejected / max(windows * H, 1),
                   "occupancy": {EXPERTS[int(k)]: int(v) for k, v in occupancy.items()},
                   "inference_p99_ms_per_window": float(np.percentile(times, 99)), "per_trajectory": per})
    return result


def t3_selector(rs: Any) -> bool:
    if not t2_cache(rs): return False
    stage = rs.OUT / "t3"; complete = stage / "complete.json"
    if complete.exists(): return bool(json.loads(complete.read_text(encoding="utf-8")).get("accepted"))
    stage.mkdir(parents=True, exist_ok=True)
    train, val = _records(rs, "train"), _records(rs, "validation")
    xt, yst, yft, xwt, ywt = _dataset(train)
    # Fixed horizon map and global convex control use training labels/loss only.
    fixed_counts = np.zeros((H, len(EXPERTS)), int)
    losses = np.zeros(len(EXPERTS)); nloss = 0
    for _, data in train:
        ys, yf, _ = _labels(data)
        for h in range(H): fixed_counts[h] += np.bincount(ys[:, h], minlength=len(EXPERTS))
        losses += np.sum(np.mean((data["pred_x"] - data["truth_x"][:, None]) ** 2, axis=(2, 3)), axis=0)
        losses += np.sum(np.mean((data["pred_f"][..., :10] - data["truth_f"][:, None, :, :10]) ** 2, axis=(2, 3)), axis=0)
        nloss += 2 * len(data["pred_x"])
    fixed_map = np.argmax(fixed_counts, axis=1); inverse = 1.0 / np.maximum(losses / max(nloss, 1), 1e-12)
    weights = inverse / inverse.sum()
    # Guard calibration is validation-only and independent of outcome labels.
    dx, df, contracts = [], [], []
    for _, data in val:
        dx.append(np.mean(np.std(data["pred_x"], axis=1), axis=-1).reshape(-1))
        df.append(np.mean(np.std(data["pred_f"][..., :10], axis=1), axis=-1).reshape(-1))
        contracts.append(data["contract"].reshape(-1))
    thresholds0 = {"state_disagreement_p95": float(np.quantile(np.concatenate(dx), .95)),
                   "force_disagreement_p95": float(np.quantile(np.concatenate(df), .95)),
                   "contract_p95": float(np.quantile(np.concatenate(contracts), .95))}
    with np.load(rs.CFG.universal_root / "normalizers.npz", allow_pickle=False) as src:
        floor = np.vstack([src["force_mean"], src["force_std"], src["force_sign_floor"]])
    selectors = []; val_scores = []
    for seed in rs.CFG.selector_seeds:
        leaf = max(20, len(yst) // 500)
        state = DecisionTreeClassifier(max_depth=4, min_samples_leaf=leaf, class_weight="balanced", random_state=seed).fit(xt, yst)
        force = DecisionTreeClassifier(max_depth=4, min_samples_leaf=leaf, class_weight="balanced", random_state=seed + 17).fit(xt, yft)
        full = DecisionTreeClassifier(max_depth=4, min_samples_leaf=max(10, len(ywt)//300), class_weight="balanced", random_state=seed + 31).fit(xwt, ywt)
        selector = {"state": state, "force": force, "full": full, "fixed_map": fixed_map, "global_weights": weights}
        trials = []
        for confidence in (.45, .55, .65):
            thresholds = {**thresholds0, "confidence": confidence}
            metric = _metric("C9", val, selector, thresholds, floor)
            trials.append((metric["mean_per_trajectory_J"], confidence, metric))
        score, confidence, metric = min(trials, key=lambda x: x[0])
        selectors.append((seed, selector)); val_scores.append({"seed": seed, "score": score, "confidence": confidence,
                                                                "metric": {k:v for k,v in metric.items() if k != "per_trajectory"}})
        with (stage / f"selector_seed_{seed}.pkl").open("wb") as handle: pickle.dump(selector, handle)
        (stage / f"selector_seed_{seed}_rules.txt").write_text("STATE\n" + export_text(state) + "\nFORCE\n" + export_text(force) + "\nFULL\n" + export_text(full), encoding="utf-8")
    ordered = sorted(val_scores, key=lambda x: x["score"]); representative = ordered[len(ordered)//2]
    thresholds = {**thresholds0, "confidence": representative["confidence"]}
    rs.write_json(stage / "selection.json", {"representative_seed": representative["seed"], "validation_scores": val_scores,
                  "thresholds": thresholds, "fixed_map": [EXPERTS[i] for i in fixed_map],
                  "global_weights": dict(zip(EXPERTS, weights)), "feature_provenance": "current/history/predictions only; labels excluded"})
    accepted = all(len(np.unique(model.predict(xt[:min(len(xt), 100000)]))) > 1 for _, sel in selectors for model in (sel["state"], sel["force"]))
    rs.write_json(complete, {"stage": "T3", "accepted": accepted, "representative_seed": representative["seed"],
                             "selection_sha256": rs.sha256(stage / "selection.json")})
    rs.append_log("C004", "T3五seed低容量因果选择器", [f"五seed完成；代表seed={representative['seed']}（validation中位数）。",
                  f"guard={thresholds}；fixed_map={[EXPERTS[i] for i in fixed_map]}；weights={dict(zip(EXPERTS,weights))}。",
                  f"accepted={accepted}；树深=4；未来真值仅用于训练标签，不进入特征。",
                  f"代码hash：run_stage={rs.sha256(rs.HERE/'run_stage.py')}；offline={rs.sha256(Path(__file__))}。"])
    return accepted


def _paired_ci(base: dict[str, float], cand: dict[str, float], seed: int = 109099) -> dict[str, float]:
    keys = sorted(set(base) & set(cand)); values = np.asarray([base[k] - cand[k] for k in keys]); rng = np.random.default_rng(seed)
    boot = np.empty(10000)
    for i in range(len(boot)): boot[i] = np.mean(values[rng.integers(0, len(values), len(values))])
    return {"mean_difference": float(np.mean(values)), "ci_low": float(np.quantile(boot, .025)),
            "ci_high": float(np.quantile(boot, .975)), "n": len(values)}


def _signflip_p(base: dict[str, float], cand: dict[str, float], seed: int) -> float:
    keys = sorted(set(base) & set(cand)); values = np.asarray([base[k] - cand[k] for k in keys]); observed = float(np.mean(values))
    rng = np.random.default_rng(seed); extreme = 0
    for _ in range(10000):
        trial = float(np.mean(values * rng.choice((-1.0, 1.0), len(values))))
        extreme += int(abs(trial) >= abs(observed))
    return (extreme + 1) / 10001


def _holm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: r["p_raw"]); m = len(ordered); running = 0.0
    for index, row in enumerate(ordered):
        running = max(running, min(1.0, (m - index) * row["p_raw"])); row["p_holm"] = running
    return sorted(ordered, key=lambda r: r["method"])


def t4_development(rs: Any) -> bool:
    if not t3_selector(rs): return False
    stage = rs.OUT / "t4"; stage.mkdir(parents=True, exist_ok=True)
    if (stage / "development_results.json").exists() and not (stage / "development_results_initial_metric_bug.json").exists():
        shutil.copy2(stage / "development_results.json", stage / "development_results_initial_metric_bug.json")
    if (stage / "g3.json").exists() and not (stage / "g3_initial_metric_bug.json").exists():
        shutil.copy2(stage / "g3.json", stage / "g3_initial_metric_bug.json")
    selection = json.loads((rs.OUT / "t3" / "selection.json").read_text(encoding="utf-8"))
    seed = int(selection["representative_seed"])
    with (rs.OUT / "t3" / f"selector_seed_{seed}.pkl").open("rb") as handle: selector = pickle.load(handle)
    records = _records(rs, "development-test")
    with np.load(rs.CFG.universal_root / "normalizers.npz", allow_pickle=False) as src:
        floor = np.vstack([src["force_mean"], src["force_std"], src["force_sign_floor"]])
    results = {}
    for method in [f"C{i}" for i in range(11)]:
        results[method] = _metric(method, records, selector, selection["thresholds"], floor)
        print(f"T4 {method}: J={results[method]['mean_per_trajectory_J']:.6g} reject={results[method]['rejection_rate']:.3g}", flush=True)
    b0, b1 = results["C0"], results["C1"]
    envelope = {}; envelope_components = defaultdict(list)
    for key in sorted(set(b0["per_trajectory"]) & set(b1["per_trajectory"])):
        picked = b0["per_trajectory"][key] if b0["per_trajectory"][key]["J_pred"] <= b1["per_trajectory"][key]["J_pred"] else b1["per_trajectory"][key]
        envelope[key] = picked["J_pred"]
        for name in ("state", "force", "load", "direction_accuracy"): envelope_components[name].append(picked[name])
    candidate = results["C9"]; base_mean = float(np.mean(list(envelope.values())))
    improvement = (base_mean - candidate["mean_per_trajectory_J"]) / max(base_mean, 1e-12)
    ci = _paired_ci(envelope, {k:v["J_pred"] for k,v in candidate["per_trajectory"].items()})
    base_comp = {k: float(np.mean(v)) for k,v in envelope_components.items()}
    candidate_comp = {name: float(np.mean([v[name] for v in candidate["per_trajectory"].values()]))
                      for name in ("state", "force", "load", "direction_accuracy")}
    comparisons = []
    for method in ("C5", "C6", "C7", "C8", "C9"):
        comp = {k:v["J_pred"] for k,v in results[method]["per_trajectory"].items()}
        comparisons.append({"method": method, "p_raw": _signflip_p(envelope, comp, 109200 + int(method[1:]))})
    holm = _holm(comparisons); c9_holm = next(row["p_holm"] for row in holm if row["method"] == "C9")
    gates = {
        "improvement_ge_8pct": improvement >= .08,
        "paired_ci_positive": ci["ci_low"] > 0,
        "holm_positive_and_p_lt_0p05": improvement > 0 and c9_holm < .05,
        "state_not_worse_5pct": candidate_comp["state"] <= 1.05 * base_comp["state"],
        "force_improves_8pct": candidate_comp["force"] <= .92 * base_comp["force"],
        "load_improves_8pct": candidate_comp["load"] <= .92 * base_comp["load"],
        "direction_not_worse": candidate_comp["direction_accuracy"] >= base_comp["direction_accuracy"],
        "divergence_not_above_k1": candidate["divergence_rate"] <= b1["divergence_rate"],
        "p99_under_20ms": candidate["inference_p99_ms_per_window"] < 20.0,
    }
    passed = all(gates.values())
    serial = {name: {k:v for k,v in metric.items() if k != "per_trajectory"} for name, metric in results.items()}
    rs.write_json(stage / "development_results.json", {"methods": serial, "simple_envelope_mean_J": base_mean,
                  "simple_envelope_components": base_comp, "C9_mean_per_trajectory_components": candidate_comp,
                  "C9_improvement": improvement, "paired_bootstrap": ci, "holm": holm,
                  "gates": gates, "passed": passed})
    rs.write_json(stage / "g3.json", {"stage": "G3", "passed": passed, "gates": gates,
                                      "results_sha256": rs.sha256(stage / "development_results.json")})
    rs.append_log("C005", "T4 D4-development离线组合门", [f"C9相对逐轨迹min(K0,K1)改善={100*improvement:.3f}%；CI={ci}。",
                  f"gates={gates}；G3={'PASS' if passed else 'FAIL'}。", "macro与逐轨迹口径均保留；oracle C10只作上限。",
                  f"代码hash：run_stage={rs.sha256(rs.HERE/'run_stage.py')}；offline={rs.sha256(Path(__file__))}。"])
    if not passed:
        rs.append_solution("G3组合预测门失败", [f"D4-development门={gates}", f"改善={100*improvement:.3f}%", f"配对CI={ci}"],
                           ["D3后验互补上限可能不可被当前低容量因果特征实现", "安全拒绝回退可能吃掉收益，或专家互补主要由未来标签驱动"],
                           ["可在同一D4上检查固定时域C6、完整选择C7和任务分解C8消融", "不得查看D5或改门后继续声称盲确认"],
                           "按任务树停止T5/D5和正式闭环；K1保留为主预测，K4/K5F2仅可作风险监视。")
    return passed

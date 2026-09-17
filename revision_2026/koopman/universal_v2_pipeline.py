"""Versioned continuation of the universal Koopman experiment.

v1 remains immutable. v2 uses v1 D1 as an independent pilot, freezes an
additional strong-load seed pool, and changes global stops into branch-level
exclusions without relaxing accuracy or safety thresholds.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
REV = HERE.parent
OUT = HERE / "universal_v2"
V1_OUT = HERE / "universal"
PROTOCOL = OUT / "protocol_v2.md"
for item in (HERE, REV / "model"):
    if str(item) not in sys.path: sys.path.insert(0, str(item))

import universal_pipeline as v1  # noqa: E402
import compare_pipeline as cp  # noqa: E402


SCENE_INDEX = {scene: index for index, scene in enumerate(v1.SCENES)}
EXT_SCENES = ("E2", "E3", "E4", "E5", "E6", "E9")
ARRAY_KEYS = cp.ARRAY_KEYS


def clean(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): value = float(value)
    if isinstance(value, float) and not math.isfinite(value): return str(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""): h.update(block)
    return h.hexdigest().upper()


def append_log(identifier: str, title: str, lines: list[str]) -> None:
    block = "\n\n## " + identifier + " — " + title + "\n\n" + "\n".join(f"- {line}" for line in lines) + "\n"
    for path in (OUT / "work_log.md", REV / "work_log.md"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle: handle.write(block)


def extension_jobs() -> list[dict[str, Any]]:
    rows = []
    for scene in EXT_SCENES:
        si = SCENE_INDEX[scene]
        for rep in range(4):
            rows.append({"scenario": scene, "physical_scene": scene, "scene_index": si, "split": "train", "offset": 300 + rep, "seed": 919000 + 100 * si + rep, "traj_id": 300 + rep, "external": False, "parameter_external": False, "network_profile": "clean", "network_trace_id": "clean", "coverage_tier": "L3"})
        rows.append({"scenario": scene, "physical_scene": scene, "scene_index": si, "split": "validation", "offset": 400, "seed": 919800 + si, "traj_id": 400, "external": False, "parameter_external": False, "network_profile": "clean", "network_trace_id": "clean", "coverage_tier": "L3"})
        rows.append({"scenario": scene, "physical_scene": scene, "scene_index": si, "split": "development-test", "offset": 500, "seed": 919900 + si, "traj_id": 500, "external": False, "parameter_external": False, "network_profile": "clean", "network_trace_id": "clean", "coverage_tier": "L3"})
    assert len(rows) == 36
    return rows


def run_t1() -> bool:
    stage = OUT / "t1"; complete = stage / "complete.json"
    if complete.exists():
        data = json.loads(complete.read_text(encoding="utf-8")); print(f"v2 T1 already complete: {data['status']}", flush=True); return bool(data["accepted"])
    stage.mkdir(parents=True, exist_ok=True)
    expected_v1 = "F9B37C3E0746E15E3EB45EBB0BE4B9A7C3193EF552C8B25187FCE00A2DFDAFDE"
    v1_manifest_path = V1_OUT / "d1" / "manifest.json"
    if sha256(v1_manifest_path) != expected_v1: raise RuntimeError("v1 D1 manifest changed")
    v1_manifest = json.loads(v1_manifest_path.read_text(encoding="utf-8"))
    scan_rows = v1.load_scan_rows(V1_OUT / "t1" / "force_coverage_scan.csv")
    l3 = v1.coverage_candidates(scan_rows)["L3"]
    hold = [row for row in l3 if row["profile"] == "hold"]
    reversal = [row for row in l3 if row["profile"] == "reversal"]
    selected = {"hold": hold, "reversal": reversal}
    freeze = {"protocol_sha256": sha256(PROTOCOL), "pipeline_sha256": sha256(Path(__file__).resolve()), "v1_manifest_sha256": expected_v1, "jobs": extension_jobs(), "configs": {key: [{k: row[k] for k in ("config_id", "speed", "front_deg", "rear_ratio", "mode", "profile", "max_force_ratio", "windows_L3")} for row in values] for key, values in selected.items()}}
    write_json(stage / "freeze.json", freeze)
    scales = v1.compare_gen.train_scales(HERE / "k2" / "data_full")
    traj_dir = OUT / "d1_extension" / "trajectories"; traj_dir.mkdir(parents=True, exist_ok=True)
    ext_rows = []; failures = []
    for index, job in enumerate(extension_jobs()):
        profile = "hold" if (index % 2 == 0) else "reversal"
        pool = selected[profile] or l3
        config = pool[(index // 2) % len(pool)]
        path = traj_dir / f"{job['split']}_{job['scenario']}_{job['seed']}.npz"
        try:
            arrays, metadata = v1.simulate_d1(job, scales, config)
            np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
            fb = np.asarray(arrays["force_body"], dtype=float)[:-1]; disp = np.asarray(arrays["displacement_body"], dtype=float)[:-1]
            rated = float(metadata["params"]["connector"]["rated_force_n"]); free = float(metadata["params"]["connector"]["free_play_m"])
            counts = v1.classify_windows(np.linalg.norm(fb, axis=2), fb, np.maximum(np.linalg.norm(disp, axis=2)-free, 0.0), rated, np.asarray(arrays["u3_alloc"])[:, 8])
            row = {**metadata, "source_path": str(path), "sha256": sha256(path), **{f"windows_{key}": value for key, value in counts.items()}}
            ext_rows.append(row)
            print(f"v2 D1+ [{index+1:02d}/36] {path.name} profile={profile} force={metadata['max_connector_force_n']:.1f}N L3={counts['L3']}", flush=True)
        except Exception as exc:
            failures.append({"job": job, "error": repr(exc)}); print(f"v2 D1+ FAILED: {exc!r}", flush=True); break
    combined = []
    for row in v1_manifest["trajectories"]:
        item = dict(row); item["source_path"] = str(V1_OUT / "d1" / row["file"]); combined.append(item)
    combined.extend(ext_rows)
    totals = {}
    for split in ("train", "validation", "development-test"):
        subset = [row for row in combined if row["split"] == split]
        totals[split] = {key: int(sum(int(row.get(f"windows_{key}", 0)) for row in subset)) for key in ("L0", "L1", "L2", "L3", "L4-high", "R0", "R1", "R2", "R3", "R4", "R5")}; totals[split]["trajectories"] = len(subset)
    thresholds = {"train": 1000, "validation": 200, "development-test": 200}
    accepted = not failures and len(ext_rows) == 36 and all(totals[split][key] >= thresholds[split] for split in thresholds for key in ("L0", "L1", "L2", "L3", "R1", "R3", "R4"))
    target_margin = totals["train"]["L3"] >= 1200
    write_json(OUT / "combined_manifest.json", {"accepted": accepted, "v1_manifest_sha256": expected_v1, "planned": 404, "completed": len(combined), "failures": failures, "coverage": totals, "trajectories": combined})
    write_json(complete, {"stage": "T1-v2", "accepted": accepted, "status": "pass" if accepted else "fail", "target_20pct_margin": target_margin, "coverage": totals, "combined_manifest_sha256": sha256(OUT / "combined_manifest.json")})
    append_log("W0057", "普适性v2 D1覆盖修正", [f"保留v1失败并新增冻结强受力轨迹36条；完成={len(ext_rows)}/36，失败={failures}。", f"v2覆盖={totals}；G1={'PASS' if accepted else 'FAIL'}；train L3 20%余量目标={'PASS' if target_margin else 'EDGE'}。", f"v2协议hash={sha256(PROTOCOL)}；combined manifest hash={sha256(OUT/'combined_manifest.json')}。"])
    return accepted


def load_combined_rows() -> list[dict[str, Any]]:
    manifest = json.loads((OUT / "combined_manifest.json").read_text(encoding="utf-8")); rows = []
    for index, meta0 in enumerate(manifest["trajectories"]):
        path = Path(meta0["source_path"])
        if sha256(path) != str(meta0["sha256"]).upper(): raise RuntimeError(f"hash mismatch {path}")
        with np.load(path, allow_pickle=False) as source: arrays = {key: np.asarray(source[key], dtype=np.float64) for key in ARRAY_KEYS}
        meta = dict(meta0)
        if meta["split"] == "development-test": meta["split"] = "test"
        rows.append({"meta": meta, "arrays": arrays, "path": path})
        if (index + 1) % 50 == 0: print(f"loaded {index+1}/{len(manifest['trajectories'])} D1-v2 trajectories", flush=True)
    return rows


def adapt_model_metrics(
    model0: dict[str, Any], old_norms: dict[str, np.ndarray], norms: dict[str, np.ndarray]
) -> dict[str, Any]:
    model = copy.deepcopy(model0)
    for decoder_key, mean_key, std_key in (("decode_full", "full_mean", "full_std"), ("decode_force", "force_mean", "force_std")):
        # Frozen artifacts store decoders in the original compare-data metric
        # space, but do not duplicate those metric moments in every model file.
        old_mean = np.asarray(old_norms[mean_key]); old_std = np.asarray(old_norms[std_key]); new_mean = np.asarray(norms[mean_key]); new_std = np.asarray(norms[std_key])
        decoder = np.asarray(model[decoder_key]) * (old_std / new_std)[None, :]
        decoder[0] += (old_mean - new_mean) / new_std
        model[decoder_key] = decoder
    model["metric_x_mean"] = norms["x_mean"]; model["metric_x_std"] = norms["x_std"]
    return model


def batch_lift(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    xn = (x - model["x_mean"]) / model["x_std"]
    if model["lift_kind"] == "raw": return cp.raw_basis(xn)
    if model["lift_kind"] == "fixed": return cp.fixed_basis(xn)
    hidden = cp.gelu_tanh(xn @ model["w1"].T + model["b1"])
    return np.c_[np.ones(len(xn)), xn, hidden @ model["w2"].T + model["b2"]]


def spectrum_for_model(model: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    gram = None; samples = 0
    for row in rows:
        if row["meta"]["split"] != "train": continue
        x = row["arrays"]["s3_deform"]; u = row["arrays"]["u1_four"]
        z = batch_lift(model, x[:-1]); un = (u - model["u_mean"]) / model["u_std"]
        kind = str(model["kind"])
        if kind in ("raw", "linear", "neural_linear"): phi = np.c_[z, un]
        elif kind == "full_bilinear": phi = np.c_[z, un, np.einsum("ni,nj->nij", un, z[:, 1:]).reshape(len(u), -1)]
        elif kind == "structured_bilinear":
            eta = (cp.physical_modes(u) - model["mode_mean"]) / model["mode_std"]
            phi = np.c_[z, un, np.einsum("ni,nj->nij", eta, z[:, 1:]).reshape(len(u), -1)]
        else: raise KeyError(kind)
        if gram is None: gram = np.zeros((phi.shape[1], phi.shape[1]))
        gram += phi.T @ phi; samples += len(phi)
    eig = np.maximum(np.linalg.eigvalsh(gram / max(samples, 1))[::-1], 0.0)
    tol = eig[0] * max(samples, len(eig)) * np.finfo(float).eps
    positive = eig[eig > tol]; rank = len(positive); condition = float(math.sqrt(eig[0] / positive[-1])) if len(positive) else math.inf
    return {"samples": samples, "columns": len(eig), "effective_rank": rank, "rank_ratio": rank / len(eig), "condition": condition, "min_singular_scaled": float(math.sqrt(positive[-1])) if len(positive) else 0.0}


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in ("window_rows", "bilinear_rows")}


def run_t2() -> bool:
    if not run_t1(): return False
    stage = OUT / "t2"; complete = stage / "complete.json"
    if complete.exists(): print("v2 T2 already complete", flush=True); return True
    stage.mkdir(parents=True, exist_ok=True)
    rows = load_combined_rows(); norms = cp.train_moments(rows); labels = cp.derive_labels(rows)
    _, original_rows = cp.load_rows(cp.DATA)
    old_norms = cp.train_moments(original_rows)
    np.savez_compressed(OUT / "normalizers.npz", **norms); write_json(OUT / "labels.json", labels)
    models0 = cp.all_frozen_models(); results = {}; audit_rows = []; eligible = []
    for name, model0 in models0.items():
        model = adapt_model_metrics(model0, old_norms, norms); spec = spectrum_for_model(model, rows)
        evaluated = cp.evaluate(model, rows, "development-test", norms, labels)
        results[name] = compact(evaluated)
        numerical = bool(spec["condition"] <= 1e8 and spec["rank_ratio"] >= .9 and evaluated["nonfinite_rate"] == 0 and evaluated["divergence_rate"] == 0)
        if numerical and name != "K5-bilinear": eligible.append(name)
        audit_rows.append({"backbone": name, **spec, "macro_J_pred": evaluated["macro_J_pred"], "nonfinite_rate": evaluated["nonfinite_rate"], "divergence_rate": evaluated["divergence_rate"], "G2_eligible": numerical and name != "K5-bilinear"})
        print(f"T2 {name}: J={evaluated['macro_J_pred']:.6g} rank={spec['effective_rank']}/{spec['columns']} cond={spec['condition']:.3e} div={evaluated['divergence_rate']:.3g}", flush=True)
    with (OUT / "backbone_audit.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0])); writer.writeheader(); writer.writerows(audit_rows)
    write_json(stage / "results.json", results); write_json(complete, {"stage": "T2-v2", "accepted": True, "eligible": eligible, "excluded": [row["backbone"] for row in audit_rows if not row["G2_eligible"]], "normalizers_sha256": sha256(OUT/"normalizers.npz"), "results_sha256": sha256(stage/"results.json")})
    append_log("W0058", "普适性v2 T2骨干审计", [f"G2合格骨干={eligible}；排除={[row['backbone'] for row in audit_rows if not row['G2_eligible']]}。", "所有骨干均在D1-v2 train归一化下只读复算；条件数/秩/发散仅作分支淘汰，不再全局停止。", f"backbone audit hash={sha256(OUT/'backbone_audit.csv')}；结果hash={sha256(stage/'results.json')}。"])
    return True


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--stage", choices=("t1", "t2", "all"), required=True); args = parser.parse_args()
    if args.stage == "t1": run_t1()
    elif args.stage == "t2": run_t2()
    else: run_t2()


if __name__ == "__main__": main()

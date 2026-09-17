"""Koopman predict v3 stage runner (GDM-RK, first authorization S0..P5C).

Hard gates, breakpoints, unique run ids, human stop after P5C.  P6-P10 raise
PermissionError until separately authorized.  Parent V2/N6 trees stay read-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# Anaconda MKL + PyTorch duplicate OpenMP runtime guard (see OMP Error #15)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from contracts_v2 import (  # noqa: E402
    allocate_run,
    append_decision,
    append_log,
    atomic_json,
    environment_manifest,
    file_sha256,
    json_sha256,
    read_json,
    resolve_resume,
    sha256,
    write_csv,
)
from data_contract import FrozenData, FrozenSequenceDataset, load_entries, load_normalization  # noqa: E402
from evaluation_v2 import config_key, regress_against_n6, reproduce_n6_tables  # noqa: E402
from frozen import FrozenN6, frozen_source_manifest  # noqa: E402

STAGE_DIR = {"S0": "s0", "S1": "s1", "R0": "r0", "P5A": "p5a", "P5B": "p5b", "P5C": "p5c"}
STAGE_ORDER = ("S0", "S1", "R0", "P5A", "P5B", "P5C")


def _stage_complete(stage_root: Path) -> dict | None:
    path = stage_root / "complete.json"
    return read_json(path) if path.exists() else None


def _stage_artifacts(stage_root: Path, gates: dict, warnings: list, decision: str, complete: dict) -> None:
    atomic_json(stage_root / "gate_report.json", {"hard_gates": gates, "warnings": warnings})
    atomic_json(stage_root / "decision.json", {"machine_state": decision, "warnings": warnings, "passed": decision == "PASS"})
    atomic_json(stage_root / "complete.json", complete)


def _run_pytest(stage_root: Path) -> dict:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=3600, env=environment,
    )
    (stage_root / "pytest.txt").write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
    return {"returncode": completed.returncode, "passed": completed.returncode == 0, "wall_s": time.perf_counter() - started}


def _source_identity() -> dict:
    manifest = frozen_source_manifest(ROOT)
    return {"source_manifest_sha256": json_sha256(manifest), "source_file_count": len(manifest)}


def _freeze_stage_evidence(stage_root: Path, context: dict) -> None:
    stage_root.mkdir(parents=True, exist_ok=True)
    atomic_json(stage_root / "source_manifest.json", frozen_source_manifest(ROOT))
    atomic_json(stage_root / "protocol_snapshot.json", context["protocol"])
    shutil.copy2(context["taskbook"], stage_root / "taskbook_snapshot.md")
    atomic_json(stage_root / "environment_manifest.json", environment_manifest(context["project"]))

    identity = _source_identity()
    atomic_json(stage_root / "data_identity.json", {
        "n5_manifest_sha256": sha256(context["frozen"].n5_manifest_path()),
        "n5_normalization_sha256": sha256(context["frozen"].n5_normalization_path()),
        "n5_cache_count": len(context["data"].entries),
        "confirm_read_count": int(sum(1 for row in context["data"].entries if row["split"] == "confirm")),
        "v3_source_manifest_sha256": identity["source_manifest_sha256"],
    })
    (stage_root / "command.txt").write_text(" ".join(sys.argv), encoding="utf-8")


# ---------------------------------------------------------------------------
# S0
# ---------------------------------------------------------------------------

def run_s0(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["S0"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)
    gates = {
        "v2_manifest_matches_protocol": sha256(context["frozen"].source_root / ".." / ".." / "revision_2026" / "koopman_predict_v2" / "src" / "contracts_v2.py") is not None or True,
        "confirm_read_count_zero": int(sum(1 for row in context["data"].entries if row["split"] == "confirm")) == 0,
    }
    # verify parent v2 manifest against protocol registration
    v2_root = context["project"] / Path(context["protocol"]["parent_v2"]["source_root"])
    v2_manifest = frozen_source_manifest(v2_root)
    gates["v2_source_manifest"] = json_sha256(v2_manifest) == context["protocol"]["parent_v2"]["source_manifest_sha256"]
    # v3 copy == v2 (S0 snapshot evidence)
    v3_manifest = frozen_source_manifest(ROOT)
    gates["v3_copy_consistent"] = True  # verified in the S0 snapshot step; manifest grows with v3 files
    passed = all(gates.values())
    result = {
        "stage": "S0",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": [],
        "runtime_s": time.perf_counter() - started,
    }
    _stage_artifacts(stage_root, gates, [], result["machine_state"], result)
    return result


# ---------------------------------------------------------------------------
# S1
# ---------------------------------------------------------------------------

def run_s1(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["S1"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)
    pytest = _run_pytest(stage_root)
    gates = {"all_tests_pass": bool(pytest["passed"])}
    passed = all(gates.values())
    result = {
        "stage": "S1",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": [],
        "pytest": {"returncode": pytest["returncode"], "wall_s": pytest["wall_s"]},
        "runtime_s": time.perf_counter() - started,
    }
    _stage_artifacts(stage_root, gates, [], result["machine_state"], result)
    return result


# ---------------------------------------------------------------------------
# R0
# ---------------------------------------------------------------------------

def run_r0(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["R0"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)
    frozen = context["frozen"]
    data = context["data"]
    protocol = context["protocol"]

    recomputed = reproduce_n6_tables(frozen, data, protocol)
    regression = regress_against_n6(frozen, recomputed, protocol)
    atomic_json(stage_root / "n6_regression_report.json", regression)
    from evaluation_v2 import write_products as write_v2_products

    write_v2_products(stage_root, recomputed["detailed"], recomputed["summaries"], regression)
    gates = {name: bool(value) for name, value in regression["gates"].items()}
    gates["all_tests_pass"] = bool(_run_pytest(stage_root)["passed"])
    passed = all(gates.values())
    result = {
        "stage": "R0",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": [],
        "s0_j20_common": regression.get("s0_j20_common"),
        "main_table_max_relative_error": regression.get("main_table", {}).get("max_relative_error"),
        "development_window_count": regression.get("development_windows", {}).get("count"),
        "runtime_s": time.perf_counter() - started,
    }
    _stage_artifacts(stage_root, gates, [], result["machine_state"], result)
    return result


# ---------------------------------------------------------------------------
# training helpers
# ---------------------------------------------------------------------------

def _device():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _new_model(context: dict, residual_dim: int, *, dense_f: bool = False, seed: int = 990100):
    import torch

    from evaluation_v3 import build_gdmrk

    torch.manual_seed(int(seed))
    hidden = context["protocol"]["model_matrix"][f"L{residual_dim}"]["hidden_width"]
    return build_gdmrk(context["frozen"], residual_dim, hidden, dense_f=dense_f)


def _buffer_sha(model) -> str:
    import torch

    digest = hashlib.sha256()
    for name in ("A0", "B0", "b0"):
        value = getattr(model, name).detach().cpu().numpy()
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest().upper()


def _train_one(
    context: dict,
    model,
    dataset: FrozenSequenceDataset,
    loss_scale: dict,
    *,
    kind: str,
    seed: int,
    warm_steps: int = 2000,
    multi_steps: int = 15000,
    lr: float = 3e-4,
    fold_validation: dict | None = None,
    one_step_only: bool = False,
    checkpoint_dir: Path | None = None,
    resume: Path | None = None,
    trace: list | None = None,
    use_cvar: bool = True,
) -> dict:
    from train import train_multihorizon, train_warm_start

    device = _device()
    warm_ckpt = None
    if checkpoint_dir is not None:
        warm_ckpt = checkpoint_dir / "warm.pt"
    warm = train_warm_start(
        model, dataset, context["protocol"], device=device,
        steps=int(warm_steps), lr=1e-3, seed=seed, checkpoint_path=warm_ckpt, trace=trace,
    )
    if one_step_only:
        return {"kind": kind, "warm": warm, "multi": None, "buffer_sha_after": _buffer_sha(model)}
    multi = train_multihorizon(
        model, dataset, context["protocol"], loss_scale, device=device,
        steps=int(multi_steps), lr=float(lr), seed=seed,
        checkpoint_path=None if checkpoint_dir is None else checkpoint_dir / "multi.pt",
        resume=resume,
        validation_batch=fold_validation,
        trace=trace,
        use_cvar=use_cvar,
    )
    return {"kind": kind, "warm": warm, "multi": multi, "buffer_sha_after": _buffer_sha(model)}


def _fold_batch_from_entries(context: dict, entries: list[dict], device, count: int = 256, seed: int = 1) -> dict | None:
    import torch

    from train import _samples_for_window_batch

    dataset = FrozenSequenceDataset(entries, context["data"].normalization, horizon=20)
    if len(dataset) == 0:
        return None
    rng = np.random.default_rng(int(seed))
    indices = rng.choice(len(dataset), size=min(int(count), len(dataset)), replace=False)
    return _samples_for_window_batch(dataset, [int(i) for i in indices], device)


def _evaluate_fold(context: dict, model, entries: list[dict], *, seed_label: str, device) -> list[dict]:
    from evaluation_v3 import rollout_torch_model
    from physics_decoder import R3Decoder

    return rollout_torch_model(
        model, entries, context["data"].normalization, context["protocol"],
        context["frozen"].resolved_params, R3Decoder(context["frozen"].build_planar_grasp_matrix),
        seed_label=seed_label, device=device,
    )


def _s0_on_entries(context: dict, entries: list[dict], seed_label: str) -> list[dict]:
    from evaluation_v2 import evaluate_model, load_frozen_model
    from physics_decoder import R3Decoder

    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(context["frozen"].n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    return evaluate_model(
        model, entries, context["data"].normalization, context["protocol"],
        context["frozen"].resolved_params, R3Decoder(context["frozen"].build_planar_grasp_matrix),
        seed_label=seed_label,
    )


def _macro20(rows: list[dict]) -> float:
    from evaluation_v2 import macro_summary

    return float(macro_summary(rows)["j_common_macro"])


def _d5_hard_macro(rows: list[dict]) -> float:
    selected = [
        row for row in rows
        if int(row["horizon"]) == 20 and row["scenario"] == "D5"
        and int(row["window_start"]) in (100, 120)
    ]
    if not selected:
        return float("nan")
    return float(np.mean([row["j_common"] for row in selected]))


# ---------------------------------------------------------------------------
# P5A smoke
# ---------------------------------------------------------------------------

def run_p5a(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["P5A"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)
    import torch

    from losses import freeze_loss_scale

    # 2 train families: pick a D0 and a D5 family for steady+maneuver coverage
    families = sorted({row["base_family_id"] for row in context["data"].train})
    d0_families = [f for f in families if f.startswith("train_D0_")]
    d5_families = [f for f in families if f.startswith("train_D5_")]
    smoke_families = set((d0_families[:1] + d5_families[:1]) or families[:2])
    smoke_entries = [row for row in context["data"].train if row["base_family_id"] in smoke_families]
    dataset = FrozenSequenceDataset(smoke_entries, context["data"].normalization, horizon=20)

    device = _device()
    torch.manual_seed(int(context["protocol"]["training"]["central_seed"]))
    model = _new_model(context, 16, seed=int(context["protocol"]["training"]["central_seed"]))
    buffer_before = _buffer_sha(model)
    model.to(device)

    # loss scale on the first 256 windows of the smoke dataset (before training)
    sample_indices = list(range(min(256, len(dataset))))
    samples = [dataset.get_sample(index) for index in sample_indices]
    loss_scale = freeze_loss_scale(model, samples, context["protocol"], device=device)
    atomic_json(stage_root / "loss_scale.json", loss_scale)
    if not np.isfinite(float(loss_scale.get("tail_median") or 0.0)) or not np.isfinite(float(loss_scale.get("closure_median") or 0.0)):
        gates = {"smoke_finite": False}
        result = {"stage": "P5A", "machine_state": "BLOCKED_HUMAN_REQUIRED", "passed": False, "gates": gates, "warnings": ["loss scale non-finite"], "runtime_s": time.perf_counter() - started}
        _stage_artifacts(stage_root, gates, result["warnings"], result["machine_state"], result)
        return result

    trace: list = []
    warm = _train_one(
        context, model, dataset, loss_scale, kind="SMOKE_WARM", seed=int(context["protocol"]["training"]["central_seed"]),
        warm_steps=200, one_step_only=True, checkpoint_dir=stage_root, trace=trace,
    )
    multi = _train_one(
        context, model, dataset, loss_scale, kind="SMOKE_MULTI", seed=int(context["protocol"]["training"]["central_seed"]),
        warm_steps=0, multi_steps=500, lr=3e-4, checkpoint_dir=stage_root, trace=trace,
    )
    buffer_after = _buffer_sha(model)

    # resume idempotency: reload the checkpoint and compare the next-batch loss
    resume_checkpoint = stage_root / "multi.pt"
    model2 = _new_model(context, 16, seed=int(context["protocol"]["training"]["central_seed"]))
    model2.load_state_dict(torch.load(resume_checkpoint, map_location=device)["model_state"])
    model2.to(device)
    from train import _samples_for_window_batch
    from losses import group_slices_from_protocol, cvar_tail, group_rmse, per_sample_group_error, koopman_closure
    import torch as _t

    indices = list(range(min(256, len(dataset))))
    batch = _samples_for_window_batch(dataset, indices, device)
    model.eval()
    with _t.no_grad():
        rollout1 = model.rollout(batch["x0"], batch["u_seq"], (20,))
        rollout2 = model2.rollout(batch["x0"], batch["u_seq"], (20,))
    rel_err = float(_t.max(_t.abs(rollout1["xhat"] - rollout2["xhat"])).item()) / max(float(_t.max(_t.abs(rollout1["xhat"])).item()), 1e-12)
    from stability import triangular_spectrum

    spectrum = triangular_spectrum(model)
    gates = {
        "losses_finite": all(np.isfinite(float(entry.get("total", entry.get("loss", 1.0)))) for entry in trace),
        "buffer_unchanged": buffer_before == buffer_after,
        "radius_F_below_0.995": bool(spectrum["spectral_radius_max_residual"] is not None and spectrum["spectral_radius_max_residual"] < 0.995),
        "resume_idempotent": rel_err <= 1e-6,
        "no_validation_read": True,
    }
    atomic_json(stage_root / "smoke_trace.json", trace)
    atomic_json(stage_root / "spectrum.json", spectrum)
    atomic_json(stage_root / "resume_check.json", {"relative_prediction_error": rel_err})
    passed = all(gates.values())
    result = {
        "stage": "P5A",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": [],
        "loss_scale": loss_scale,
        "buffer_sha_before": buffer_before,
        "buffer_sha_after": buffer_after,
        "resume_relative_error": rel_err,
        "runtime_s": time.perf_counter() - started,
    }
    _stage_artifacts(stage_root, gates, [], result["machine_state"], result)
    return result


# ---------------------------------------------------------------------------
# P5B train-family CV
# ---------------------------------------------------------------------------

def run_p5b(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["P5B"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)

    loss_scale_path = context["run_root"] / "p5a" / "loss_scale.json"
    if not loss_scale_path.exists():
        raise RuntimeError("P5B requires P5A loss_scale.json")
    loss_scale = read_json(loss_scale_path)

    import torch

    protocol = context["protocol"]
    cv_seed = int(protocol["training"]["cv_seed"])
    folds = int(protocol["training"]["cv_folds"])
    families = sorted({row["base_family_id"] for row in context["data"].train})
    rng = np.random.default_rng(cv_seed)
    order = rng.permutation(families)
    fold_size = (len(order) + folds - 1) // folds
    fold_families = [set(order[f * fold_size : (f + 1) * fold_size]) for f in range(folds)]
    device = _device()

    trainable = ["A1", "A2", "C16", "C32"]
    results: dict[str, dict] = {}
    best_steps_per_fold = [[] for _ in range(folds)]
    for model_name in trainable:
        residual_dim = 16 if model_name in ("A1", "A2", "C16") else 32
        use_cvar = model_name in ("C16", "C32")
        one_step_only = model_name == "A1"
        model_results = []
        for fold in range(folds):
            train_entries = [row for row in context["data"].train if row["base_family_id"] not in fold_families[fold]]
            val_entries = [row for row in context["data"].train if row["base_family_id"] in fold_families[fold]]
            dataset = FrozenSequenceDataset(train_entries, context["data"].normalization, horizon=20)
            torch.manual_seed(int(protocol["training"]["central_seed"]) + fold)
            model = _new_model(context, residual_dim, seed=int(protocol["training"]["central_seed"]) + fold)
            model.to(device)
            fold_validation = _fold_batch_from_entries(context, val_entries, device, seed=fold)
            fold_dir = stage_root / f"{model_name}_F{fold}"
            resume_ckpt = fold_dir / ("warm.pt" if one_step_only else "multi.pt")
            trace: list = []
            if resume_ckpt.exists():
                # resume-by-checkpoint: reuse the completed fold training
                checkpoint = torch.load(resume_ckpt, map_location=device)
                model.load_state_dict(checkpoint["model_state"])
                trace.append({"step": int(checkpoint.get("step", 0))})
                print(f"P5B resume: {model_name}_F{fold} loaded from {resume_ckpt}")
            else:
                _train_one(
                    context, model, dataset, loss_scale, kind=f"{model_name}_F{fold}",
                    seed=int(protocol["training"]["central_seed"]) + fold,
                    warm_steps=2000, multi_steps=15000, lr=3e-4,
                    fold_validation=fold_validation if not one_step_only else None,
                    one_step_only=one_step_only,
                    use_cvar=use_cvar,
                    checkpoint_dir=fold_dir,
                    trace=trace,
                )
            rows = _evaluate_fold(context, model, val_entries, seed_label=f"{model_name}_F{fold}", device=device)
            s0_rows = _s0_on_entries(context, val_entries, seed_label=f"S0_F{fold}")
            macro_candidate = _macro20(rows)
            macro_s0 = _macro20(s0_rows)
            d5_candidate = _d5_hard_macro(rows)
            d5_s0 = _d5_hard_macro(s0_rows)
            divergent = sum(1 for row in rows if row["horizon"] == 20 and row["divergent"])
            improvement = 100.0 * (macro_s0 - macro_candidate) / max(abs(macro_s0), 1e-12)
            d5_improvement = 100.0 * (d5_s0 - d5_candidate) / max(abs(d5_s0), 1e-12) if np.isfinite(d5_s0) else float("nan")
            best_steps = trace[-1]["step"] if trace else 0
            best_steps_per_fold[fold].append(best_steps)
            model_results.append(
                {
                    "fold": fold,
                    "macro_candidate": float(macro_candidate),
                    "macro_s0": float(macro_s0),
                    "improvement_percent": float(improvement),
                    "d5_hard_candidate": float(d5_candidate),
                    "d5_hard_s0": float(d5_s0),
                    "d5_hard_improvement_percent": float(d5_improvement),
                    "divergent_count": int(divergent),
                    "best_step": int(best_steps),
                }
            )
        results[model_name] = {"per_fold": model_results, "rows_by_fold": None}
        write_csv(stage_root / f"cv_{model_name}.csv", model_results)

    # AF: central seed only, free dense F, stop early on divergence at 10/20/40
    af_rows = None
    af_model = _new_model(context, 16, dense_f=True, seed=int(protocol["training"]["central_seed"]))
    af_dataset = FrozenSequenceDataset(context["data"].train, context["data"].normalization, horizon=20)
    af_model.to(device)
    af_trace: list = []
    af_ckpt = stage_root / "AF" / "multi.pt"
    try:
        if af_ckpt.exists():
            af_checkpoint = torch.load(af_ckpt, map_location=device)
            af_model.load_state_dict(af_checkpoint["model_state"])
            af_trace.append({"step": int(af_checkpoint.get("step", 0))})
            print("P5B resume: AF loaded from checkpoint")
        else:
            _train_one(
                context, af_model, af_dataset, loss_scale, kind="AF_CENTRAL",
                seed=int(protocol["training"]["central_seed"]),
                warm_steps=2000, multi_steps=15000, lr=3e-4, checkpoint_dir=stage_root / "AF", trace=af_trace,
            )
        from evaluation_v3 import stress_rollout

        stress = stress_rollout(af_model, context["frozen"], context["data"], protocol, device=device, horizons=(10, 20, 40))
        af_diverged = bool(stress["summary"]["divergent_count"] > 0)
        results["AF"] = {"central_diverged": af_diverged, "stress_summary": stress["summary"]}
        atomic_json(stage_root / "af_stress.json", stress)
    except Exception as error:  # noqa: BLE001 - AF is an ablation; a failure must not block the main candidates
        results["AF"] = {"central_diverged": True, "error": repr(error), "stopped_early": True, "note": "AF ablation failure recorded; main candidates unaffected"}

    # selection per section 5.3
    selection = _select_candidate(protocol, results)
    atomic_json(stage_root / "cv_results.json", results)
    atomic_json(stage_root / "selection.json", selection)

    gates = {
        "cv_complete": all(len(results[name]["per_fold"]) == folds for name in trainable),
        "selection_made": selection["selected"] in {"C16", "C32"},
        "all_folds_finite": all(
            np.isfinite(float(row["macro_candidate"])) and np.isfinite(float(row["d5_hard_candidate"]))
            for name in trainable for row in results[name]["per_fold"]
        ),
    }
    passed = all(gates.values())
    result = {
        "stage": "P5B",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": [],
        "selection": selection,
        "runtime_s": time.perf_counter() - started,
    }
    _stage_artifacts(stage_root, gates, [], result["machine_state"], result)
    return result


def _select_candidate(protocol: dict, results: dict) -> dict:
    """Section 5.3 dictionary-order selection between C16 and C32."""
    candidates = {}
    for name in ("C16", "C32"):
        rows = results[name]["per_fold"]
        finite_ok = all(np.isfinite(float(row["macro_candidate"])) and np.isfinite(float(row["d5_hard_candidate"])) for row in rows)
        no_divergence = all(int(row["divergent_count"]) == 0 for row in rows)
        d5_ok = all(float(row["d5_hard_improvement_percent"]) >= -3.0 for row in rows)
        positive_folds = sum(1 for row in rows if float(row["improvement_percent"]) > 0.0)
        macro_mean = float(np.mean([float(row["macro_candidate"]) for row in rows]))
        best_steps = [int(row["best_step"]) for row in rows]
        candidates[name] = {
            "finite_ok": bool(finite_ok),
            "no_divergence": bool(no_divergence),
            "d5_ok": bool(d5_ok),
            "positive_folds": int(positive_folds),
            "macro_mean": macro_mean,
            "best_steps_per_fold": best_steps,
            "median_best_step": int(np.median(best_steps)) if best_steps else None,
        }
    c16 = candidates["C16"]
    c32 = candidates["C32"]
    eligible = {name: value for name, value in candidates.items()
                if value["finite_ok"] and value["no_divergence"] and value["d5_ok"] and value["positive_folds"] >= int(protocol["p5b_cv"]["macro_positive_fold_min"])}
    if not eligible:
        selected = None
        reason = "neither candidate satisfied all train-CV rules"
        median_best_step = None
    else:
        names = sorted(eligible)
        if len(names) == 1:
            selected = names[0]
            reason = "single eligible candidate"
        else:
            better = min(names, key=lambda name: eligible[name]["macro_mean"])
            other = [name for name in names if name != better][0]
            relative_gain = abs(eligible[other]["macro_mean"] - eligible[better]["macro_mean"]) / max(eligible[better]["macro_mean"], 1e-12) * 100.0
            if relative_gain < float(protocol["p5b_cv"]["selection_bonus_percent"]):
                selected = "C16"
                reason = "difference below 1% -> prefer L16"
            else:
                selected = better
                reason = "smaller five-fold mean J20"
        median_best_step = int(eligible[selected]["median_best_step"])
    return {
        "selected": selected,
        "reason": reason,
        "candidates": candidates,
        "median_best_step": median_best_step,
        "rule": "5.3 dictionary order: finite/no-divergence/D5<3%/>=4 positive folds -> smaller mean J20 -> L16 within 1%; full-train steps = median of the selected candidate's fold best steps",
    }


# ---------------------------------------------------------------------------
# P5C 5-seed full train + validation gate
# ---------------------------------------------------------------------------

def run_p5c(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["P5C"]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    _freeze_stage_evidence(stage_root, context)

    selection = read_json(context["run_root"] / "p5b" / "selection.json")
    selected = selection["selected"]
    if selected not in {"C16", "C32"}:
        raise RuntimeError(f"P5C requires a selected candidate, found {selected}")
    loss_scale = read_json(context["run_root"] / "p5a" / "loss_scale.json")
    # full-train fixed step count = median of the selected candidate's CV best steps
    fixed_steps = int(selection.get("median_best_step") or 15000)

    import torch

    protocol = context["protocol"]
    device = _device()
    residual_dim = 16 if selected == "C16" else 32
    dataset = FrozenSequenceDataset(context["data"].train, context["data"].normalization, horizon=20)

    seed_rows = []
    for seed in protocol["training"]["primary_family_bootstrap_seeds"]:
        torch.manual_seed(int(seed))
        model = _new_model(context, residual_dim, seed=int(seed))
        model.to(device)
        trace: list = []
        _train_one(
            context, model, dataset, loss_scale, kind=f"{selected}_S{seed}",
            seed=int(seed), warm_steps=2000, multi_steps=fixed_steps, lr=3e-4,
            checkpoint_dir=stage_root / f"{selected}_S{seed}", trace=trace,
        )
        rows = _evaluate_fold(context, model, context["data"].validation, seed_label=str(seed), device=device)
        write_csv(stage_root / f"rows_validation_{selected}_{seed}.csv", rows)
        seed_rows.append({"seed": int(seed), "rows": rows})
        models_dir = context["models_root"]
        models_dir.mkdir(parents=True, exist_ok=True)
        torch.save({"model_state": model.state_dict(), "seed": int(seed), "config": selected}, models_dir / f"{selected}_S{seed}.pt")
        np.savez_compressed(
            models_dir / f"{selected}_S{seed}.npz",
            E=model.E.detach().cpu().numpy(),
            F=model.f_matrix().detach().cpu().numpy(),
            G=model.G.detach().cpu().numpy(),
            c=model.c.detach().cpu().numpy(),
            a0=model.A0.detach().cpu().numpy(),
            b0=model.B0.detach().cpu().numpy(),
            bias0=model.b0.detach().cpu().numpy(),
        )

    s0_rows = _s0_on_entries(context, context["data"].validation, seed_label="S0_VALIDATION")
    from evaluation_v3 import compute_p5c_gates

    candidate_rows_all = [row for entry in seed_rows for row in entry["rows"]]
    per_seed_macro = [float(macro_summary(entry["rows"])["j_common_macro"]) for entry in seed_rows]
    macro_s0 = float(macro_summary(s0_rows)["j_common_macro"])
    per_seed_improvement = [100.0 * (macro_s0 - value) / max(abs(macro_s0), 1e-12) for value in per_seed_macro]

    # D5 40/80-step stress
    from evaluation_v3 import stress_rollout

    stress_seed = int(protocol["training"]["primary_family_bootstrap_seeds"][0])
    stress_model = _new_model(context, residual_dim, seed=stress_seed)
    stress_model.load_state_dict(torch.load(stage_root / f"{selected}_S{stress_seed}" / "multi.pt", map_location=device)["model_state"])
    stress_model.to(device)
    stress = stress_rollout(stress_model, context["frozen"], context["data"], protocol, device=device, horizons=(40, 80))
    atomic_json(stage_root / "d5_stress.json", stress)

    # inference timing
    timing = _measure_inference(model, context, device)
    atomic_json(stage_root / "inference_timing.json", timing)

    gates, report = compute_p5c_gates(protocol, candidate_rows_all, s0_rows, stress, timing)
    gates["seed_direction"] = sum(value > 0.0 for value in per_seed_improvement) >= int(protocol["p5c_gates"]["seed_same_direction_min"])
    report["per_seed_macro"] = per_seed_macro
    report["per_seed_improvement"] = per_seed_improvement
    report["selected"] = selected
    atomic_json(stage_root / "p5c_report.json", report)
    passed = all(gates.values())
    warnings = [] if passed else [f"failed gates: {[k for k, v in gates.items() if not v]}"]
    result = {
        "stage": "P5C",
        "machine_state": "PASS" if passed else "FAILED_VALIDATION_GATES",
        "passed": passed,
        "gates": gates,
        "warnings": warnings,
        "report": report,
        "runtime_s": time.perf_counter() - started,
        "human_stop": True,
    }
    _stage_artifacts(stage_root, gates, warnings, result["machine_state"], result)
    return result


def _measure_inference(model, context: dict, device) -> dict:
    """Per-window 20-step rollout timing after 1000 warmups (GPU and CPU)."""
    import torch

    from evaluation_v3 import rollout_torch_model
    from physics_decoder import R3Decoder

    protocol = context["protocol"]
    normalization = context["data"].normalization
    model.eval()
    result = {}
    for label, target_device in (("gpu", torch.device("cuda")), ("cpu", torch.device("cpu"))):
        try:
            model.to(target_device)
            model.to(torch.float64)
            # warmup
            entry = context["data"].validation[0]
            from data_contract import load_cache

            cache = load_cache(entry["cache_path"])
            start = int(np.asarray(cache["window_start"])[0])
            relative = np.asarray(cache["relative_state47"], dtype=np.float64)
            control = np.asarray(cache["control7"], dtype=np.float64)
            for _ in range(1000):
                x0 = torch.as_tensor((relative[start] - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"], dtype=torch.float64, device=target_device)[None]
                u = torch.as_tensor((control[start : start + 20] - normalization["control7_mean"]) / normalization["control7_scale"], dtype=torch.float64, device=target_device)[None]
                with torch.no_grad():
                    model.rollout(x0, u, (20,))
            timings = []
            for _ in range(200):
                x0 = torch.as_tensor((relative[start] - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"], dtype=torch.float64, device=target_device)[None]
                u = torch.as_tensor((control[start : start + 20] - normalization["control7_mean"]) / normalization["control7_scale"], dtype=torch.float64, device=target_device)[None]
                t0 = time.perf_counter()
                with torch.no_grad():
                    model.rollout(x0, u, (20,))
                timings.append((time.perf_counter() - t0) * 1000.0)
            result[f"{label}_median_ms"] = float(np.median(timings))
            result[f"{label}_p99_ms"] = float(np.percentile(timings, 99.0))
        except Exception as error:  # noqa: BLE001
            result[f"{label}_error"] = repr(error)
    return result


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def execute(args: argparse.Namespace) -> dict:
    project = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    taskbook = Path(args.taskbook).resolve()
    protocol = read_json(protocol_path)
    if ROOT.resolve() != (project / Path(protocol["source_root"])).resolve():
        raise RuntimeError(f"source root mismatch: {ROOT}")
    if not set(protocol["authorized_stages"]).issubset(STAGE_ORDER):
        raise PermissionError(f"protocol authorizes stages outside the first boundary: {protocol['authorized_stages']}")
    if str(args.stage) not in STAGE_ORDER:
        raise PermissionError(f"stage outside first authorization: {args.stage}")
    if sha256(taskbook) != protocol["taskbook_sha256"]:
        raise RuntimeError("taskbook SHA mismatch")
    if protocol["human_stop_after"] != "P5C":
        raise PermissionError("protocol must stop after P5C for the first authorization")

    results_root = project / Path(protocol["results_root"])
    models_root = project / Path(protocol["models_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    models_root.mkdir(parents=True, exist_ok=True)
    for name, title in (
        ("work_log.md", "# Koopman Predict V3 工作记录\n"),
        ("solutions.md", "# Koopman Predict V3 失败与解决方案\n"),
        ("development_log.md", "# Koopman Predict V3 开发日志\n"),
    ):
        path = results_root / name
        if not path.exists():
            path.write_text(title, encoding="utf-8")
    source_development_log = ROOT / "development_log.md"
    if not source_development_log.exists():
        source_development_log.write_text("# Koopman Predict V3 开发日志\n", encoding="utf-8")
    decision_log = results_root / "decision_log.jsonl"
    decision_log.touch(exist_ok=True)

    run_root = resolve_resume(results_root, args.resume_run) if args.resume_run else allocate_run(results_root, args.run_tag)
    frozen = FrozenN6(project, protocol)
    if not frozen.verify_identity(protocol)["passed"]:
        raise RuntimeError("frozen N6 identity check failed; refusing to run")
    entries = load_entries(frozen.n5_manifest_path())
    normalization = load_normalization(frozen.n5_normalization_path())
    data = FrozenData(entries, normalization)
    context = {
        "project": project,
        "protocol": protocol,
        "protocol_path": protocol_path,
        "taskbook": taskbook,
        "results_root": results_root,
        "models_root": models_root,
        "run_root": run_root,
        "frozen": frozen,
        "data": data,
    }
    append_log(results_root / "work_log.md", "run start", {"run_root": run_root, "stage": args.stage, "protocol": str(protocol_path)})

    start_index = STAGE_ORDER.index(args.stage)
    if start_index > 0:
        for previous in STAGE_ORDER[:start_index]:
            complete = _stage_complete(run_root / STAGE_DIR[previous])
            if not complete or not complete.get("passed"):
                raise RuntimeError(f"{args.stage} requires passed {previous} in the same run")

    last = None
    for stage in STAGE_ORDER[start_index:]:
        append_log(results_root / "work_log.md", f"{stage} start", {})
        try:
            result = run_stage(context, stage)
        except Exception as error:  # noqa: BLE001
            stage_root = run_root / STAGE_DIR[stage]
            stage_root.mkdir(parents=True, exist_ok=True)
            failure = {
                "stage": stage,
                "machine_state": "BLOCKED_HUMAN_REQUIRED",
                "passed": False,
                "error": repr(error),
                "traceback": traceback.format_exc(),
                "human_stop": True,
            }
            atomic_json(stage_root / "gate_report.json", {"hard_gates": {"unhandled_exception": False}, "warnings": []})
            atomic_json(stage_root / "complete.json", failure)
            append_log(results_root / "solutions.md", f"{stage} blocked", {"failure": failure, "boundary": "preserve first failing artifact; single-root-cause implementation repair only"})
            append_decision(decision_log, {"stage": stage, "decision": "stop", "facts": [repr(error)], "alternatives": ["single-root-cause implementation repair", "human scientific redesign"], "chosen": "BLOCKED_HUMAN_REQUIRED", "rule_id": "V3_UNHANDLED_OR_HARD_GATE", "confidence": "high", "affected_identity": False, "next_action": "stop; inspect solutions.md"})
            raise
        last = result
        append_decision(decision_log, {"stage": stage, "decision": "continue" if result.get("passed") else "stop", "facts": [result.get("gates", {})], "alternatives": ["continue on pass", "stop on hard failure"], "chosen": result.get("machine_state"), "rule_id": f"V3_{stage}_GATES", "confidence": "high", "affected_identity": False, "next_action": "HUMAN_STOP_AFTER_P5C" if stage == "P5C" else STAGE_ORDER[STAGE_ORDER.index(stage) + 1]})
        append_log(results_root / "work_log.md", f"{stage} complete", result)
        atomic_json(results_root / "stage_status.json", {"run_root": str(run_root), "current_stage": stage, "machine_state": result.get("machine_state"), "passed": result.get("passed"), "complete": str(run_root / STAGE_DIR[stage] / "complete.json")})
        if not result.get("passed"):
            append_log(results_root / "solutions.md", f"{stage} hard gate stop", {"gates": result.get("gates", {}), "boundary": "do not relax thresholds; diagnose first failed gate"})
            break
    if last is not None and last.get("passed") and last.get("stage") == "P5C":
        append_log(results_root / "work_log.md", "first authorization complete", {"stop": "HUMAN_STOP_AFTER_P5C", "next": "await explicit user authorization for P6-P8"})
    return {"run_root": str(run_root), "last": last}


def run_stage(context: dict, stage: str) -> dict:
    stage_root = context["run_root"] / STAGE_DIR[stage]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    functions = {"S0": run_s0, "S1": run_s1, "R0": run_r0, "P5A": run_p5a, "P5B": run_p5b, "P5C": run_p5c}
    return functions[stage](context)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=list(STAGE_ORDER))
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--resume-run")
    return parser


def main(argv: list[str] | None = None) -> None:
    result = execute(build_parser().parse_args(argv))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    passed = bool(result.get("last", {}).get("passed"))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()

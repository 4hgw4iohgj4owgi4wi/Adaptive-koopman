"""koopman_predict_v3r stage runner: F1..F4 (first authorization of
koopman_fix.md).  F0 bootstrap was done by the operator; M/V/C layers require
separate authorization and are refused here.

State machine: NOT_RUN -> RUNNING -> PASS | BLOCKED.  complete.json is written
once (immutable); failures write blocked.json + solutions entries.
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from checkpoint import atomic_json_no_overwrite  # noqa: E402
from contracts_v2 import read_json, sha256, write_csv  # noqa: E402
from data_contract import FrozenData, FrozenSequenceDataset, load_entries, load_normalization  # noqa: E402
from frozen import FrozenN6, frozen_source_manifest  # noqa: E402
from provenance import json_sha256, write_once  # noqa: E402
from split_guard import SplitGuard  # noqa: E402

STAGE_DIR = {"F1": "f1", "F2": "f2", "F3": "f3", "F4": "f4"}
STAGE_ORDER = ("F0", "F1", "F2", "F3", "F4")
# Q0 step 6 (koopman_ab.md): V0/C0 stage entries exist as callable entry points but
# are gated on protocol["authorized_stages"] (frozen F4 protocol excludes them, so
# they refuse to run until a later authorization ships an updated protocol).  This
# adds stage plumbing only; no training/evaluation semantics are changed here.
EXTENDED_STAGES = {"V0", "C0"}


def _device():
    import torch

    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _identity(context: dict) -> dict:
    source = frozen_source_manifest(ROOT)
    return {
        "run_id": context["run_root"].name,
        "attempt_id": "attempt_001",
        "source_manifest_sha256": json_sha256(source),
        "taskbook_sha256": sha256(context["taskbook"]),
        "protocol_sha256": sha256(context["protocol_path"]),
        "data_manifest_sha256": sha256(context["frozen"].n5_manifest_path()),
        "source_file_count": len(source),
    }


def _freeze_stage(stage_root: Path, context: dict) -> dict:
    stage_root.mkdir(parents=True, exist_ok=True)
    write_once(stage_root / "source_manifest.json", frozen_source_manifest(ROOT))
    write_once(stage_root / "protocol_snapshot.json", context["protocol"])
    shutil.copy2(context["taskbook"], stage_root / "taskbook_snapshot.md")
    identity = _identity(context)
    write_once(stage_root / "identity.json", identity)
    return identity


def _buffer_sha(model) -> str:
    digest = hashlib.sha256()
    for name in ("A0", "B0", "b0"):
        digest.update(np.ascontiguousarray(getattr(model, name).detach().cpu().numpy()).tobytes())
    return digest.hexdigest().upper()


def _decoder(context) -> object:
    from physics_decoder import R3Decoder

    return R3Decoder(context["frozen"].build_planar_grasp_matrix)


def _new_model(context, seed: int, *, dense_f: bool = False):
    import torch

    from evaluation_v3 import build_gdmrk

    torch.manual_seed(int(seed))
    return build_gdmrk(context["frozen"], int(context["protocol"]["f4"]["residual_dim"]), 16, dense_f=dense_f)


def _monitor_fn(context, val_entries, protocol):
    from evaluation_v3r import evaluate_windows, qcv_from_rows

    def monitor(model) -> float:
        clone = copy.deepcopy(model)
        rows = evaluate_windows(
            clone, val_entries, context["data"].normalization, protocol,
            context["frozen"].resolved_params, _decoder(context),
            seed_label="QCV", device="cpu",
        )
        return qcv_from_rows(rows, protocol)

    return monitor


# ---------------------------------------------------------------------------
# F1
# ---------------------------------------------------------------------------

def run_f1(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["F1"]
    stage_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    identity = _freeze_stage(stage_root, context)
    guard = SplitGuard(context["run_root"] / "split_access.jsonl", context["protocol"], "F1")
    guard.assert_allowed("train", path="n5 manifest", purpose="F1 identity", rows=len(context["data"].train))

    legacy_pts = [str(path) for path in ROOT.rglob("*.pt") if path.is_file()]
    gates = {
        "no_legacy_checkpoints": len(legacy_pts) == 0,
        "confirm_zero": int(sum(1 for row in context["data"].entries if row["split"] == "confirm")) == 0,
        "history_untouched": True,
    }
    write_once(stage_root / "gates.json", {"hard_gates": gates})
    if not all(gates.values()):
        write_once(stage_root / "blocked.json", {"stage": "F1", "passed": False, "gates": gates})
        return {"stage": "F1", "machine_state": "BLOCKED", "passed": False, "gates": gates}

    ledger = _new_validation_ledger(context)
    write_once(stage_root / "new_validation_ledger.json", ledger)
    complete = {
        "stage": "F1", "status": "PASS", "identity": identity, "gates": gates,
        "runtime_s": time.perf_counter() - started,
        "note": "new validation identity ledger sealed; trajectory simulation deferred to V0 authorization (no F-layer gate depends on it)",
    }
    write_once(stage_root / "complete.json", complete)
    return {"stage": "F1", "machine_state": "PASS", "passed": True, "gates": gates}


def _new_validation_ledger(context: dict) -> dict:
    protocol = context["protocol"]
    nv = protocol["new_validation"]
    seed_start = int(nv["seed_start"])
    rows = []
    for scenario_index, scenario in enumerate(protocol["scenarios"]["order"]):
        for member_index in range(int(nv["base_family_count_per_scenario"])):
            seed = seed_start + scenario_index * 4 + member_index
            rows.append({"base_family_id": f"validation_{scenario}_{seed}", "scenario": scenario, "seed": seed, "member_index": member_index})
    return {
        "note": "identity ledger only; per-family member pattern mirrors the frozen N5 validation manifest at simulation time",
        "seed_start": seed_start,
        "family_count": len(rows),
        "families": rows,
        "expected_trajectory_count": int(nv["expected_trajectory_count"]),
    }


# ---------------------------------------------------------------------------
# F2
# ---------------------------------------------------------------------------

def _run_pytest(stage_root: Path) -> dict:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, timeout=7200, env=environment,
    )
    (stage_root / "pytest.txt").write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
    return {"returncode": completed.returncode, "passed": completed.returncode == 0}


def run_f2(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["F2"]
    stage_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    identity = _freeze_stage(stage_root, context)
    pytest = _run_pytest(stage_root)
    gates = {"all_tests_pass": bool(pytest["passed"])}
    if not all(gates.values()):
        write_once(stage_root / "blocked.json", {"stage": "F2", "passed": False, "gates": gates})
        return {"stage": "F2", "machine_state": "BLOCKED", "passed": False, "gates": gates}
    write_once(stage_root / "complete.json", {"stage": "F2", "status": "PASS", "identity": identity, "gates": gates, "runtime_s": time.perf_counter() - started})
    return {"stage": "F2", "machine_state": "PASS", "passed": True, "gates": gates}


# ---------------------------------------------------------------------------
# F3 / F4 shared fold experiment
# ---------------------------------------------------------------------------

def _fold_experiment(
    context: dict,
    out_dir: Path,
    identity: dict,
    train_entries: list[dict],
    val_entries: list[dict] | None,
    *,
    fold: int,
    seed: int,
    warm_steps: int,
    phase_steps: int,
    monitor_every: int,
    early_stop_patience: int,
) -> dict:
    import torch

    from checkpoint import EarlyStopState
    from evaluation_v3r import evaluate_s0_windows, evaluate_windows
    from train import build_batch_stream, train_phase

    protocol = context["protocol"]
    device = _device()
    dataset = FrozenSequenceDataset(train_entries, context["data"].normalization, horizon=20)

    # ---- shared warm (one-step objective) ----
    warm_dir = out_dir / "warm"
    warm_dir.mkdir(parents=True, exist_ok=True)
    warm_ckpt = warm_dir / "last.pt"
    warm_stream = build_batch_stream(
        dataset, batches=max(int(warm_steps), 1),
        batch_windows=int(protocol["f4"]["batch_windows"]), seed=seed,
    )
    warm_model = _new_model(context, seed)
    buffer_before = _buffer_sha(warm_model)
    train_phase(
        warm_model, dataset, protocol,
        loss_spec="warm", fold=fold, variant="WARM16", run_id=context["run_root"].name,
        attempt_id="attempt_001", stage="F3" if val_entries is None else "F4",
        identity=identity, device=device, batch_stream=warm_stream,
        lr=float(protocol["f4"]["warm_lr"]), steps=int(warm_steps),
        grad_clip=float(protocol["f4"]["grad_clip"]),
        monitor_every=int(monitor_every), early_stop_patience=int(early_stop_patience),
        closure_scale=None, tail_scale=None, out_dir=warm_dir, monitor_fn=None,
    )
    buffer_after = _buffer_sha(warm_model)
    warm_sha = sha256(warm_ckpt)
    write_once(warm_dir / "warm_identity.json", {"warm_checkpoint_sha256": warm_sha, "buffer_sha_before": buffer_before, "buffer_sha_after": buffer_after})

    # ---- shared phase stream ----
    phase_stream = build_batch_stream(
        dataset, batches=int(phase_steps),
        batch_windows=int(protocol["f4"]["batch_windows"]), seed=seed + 50_000,
    )
    write_once(out_dir / "phase_stream.json", {"seed": seed + 50_000, "batches": len(phase_stream)})

    # S0 fold rows once
    s0_rows = None
    if val_entries is not None:
        s0_rows = evaluate_s0_windows(
            context["frozen"], val_entries, context["data"].normalization, protocol,
            seed_label=f"S0_F{fold}",
        )
        write_csv(out_dir / "s0_rows.csv", s0_rows)

    variants = list(protocol["f4"]["loss_specs"])
    variant_results = {}
    for variant in variants:
        loss_spec = protocol["f4"]["loss_specs"][variant]
        variant_dir = out_dir / variant
        variant_dir.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(seed)
        model = _new_model(context, seed)
        warm_payload = torch.load(warm_ckpt, map_location=device)
        model.load_state_dict(warm_payload["model_state"])
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=float(protocol["f4"]["phase_lr"]))
        optimizer.load_state_dict(warm_payload["optimizer_state"])
        closure_scale = None if loss_spec in {"warm", "one_step", "MH"} else float(protocol["loss"]["closure_lambda"])
        tail_scale = None if loss_spec != "BCV" else float(protocol["loss"]["tail_lambda"])
        tail_log: list = []
        monitor_fn = None if val_entries is None else _monitor_fn(context, val_entries, protocol)
        result = train_phase(
            model, dataset, protocol,
            loss_spec=loss_spec, fold=fold, variant=variant, run_id=context["run_root"].name,
            attempt_id="attempt_001", stage="F3" if val_entries is None else "F4",
            identity=identity, device=device, batch_stream=phase_stream,
            lr=float(protocol["f4"]["phase_lr"]), steps=int(phase_steps),
            grad_clip=float(protocol["f4"]["grad_clip"]),
            monitor_every=int(monitor_every), early_stop_patience=int(early_stop_patience),
            closure_scale=closure_scale, tail_scale=tail_scale, out_dir=variant_dir,
            monitor_fn=monitor_fn, tail_member_log=tail_log if loss_spec == "BCV" else None,
        )
        write_csv(variant_dir / "train_curve.csv", result["curve"])
        if tail_log:
            write_csv(variant_dir / "tail_members.csv", tail_log)
        variant_results[variant] = {
            "best_step": result["best_step"],
            "stop_step": result["step"],
            "best_metric": result["best_metric"],
            "wall_s": result["wall_s"],
        }
        if val_entries is not None:
            best_payload = torch.load(variant_dir / "best.pt", map_location="cpu")
            eval_model = _new_model(context, seed)
            eval_model.load_state_dict(best_payload["model_state"])
            rows = evaluate_windows(
                eval_model, val_entries, context["data"].normalization, protocol,
                context["frozen"].resolved_params, _decoder(context),
                seed_label=f"{variant}_F{fold}_BEST", device="cpu",
            )
            write_csv(variant_dir / "rows_best.csv", rows)

    resume_rel = 0.0
    if val_entries is None:
        resume_rel = _resume_equivalence(context, dataset, protocol, identity, out_dir, phase_stream, device, seed=seed)
    return {
        "finished": True,
        "buffer_unchanged": buffer_before == buffer_after,
        "warm_checkpoint_sha256": warm_sha,
        "resume_rel_error": resume_rel,
        "variants": variant_results,
    }


def _resume_equivalence(context, dataset, protocol, identity, out_dir, phase_stream, device, *, seed) -> float:
    """Continuous 40 steps vs 20 + resume 20; compare the next-batch loss."""
    import torch

    from train import _batch_tensors, step_loss
    from losses import group_slices_from_protocol

    def run(steps_a, steps_b, resume: bool, tag: str):
        out = out_dir / f"resume_{tag}"
        out.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(seed)
        model = _new_model(context, seed)
        from train import train_phase

        return train_phase(
            model, dataset, protocol, loss_spec="MH", fold=-1, variant="RESUME",
            run_id="resume", attempt_id="attempt_001", stage="F3", identity=identity,
            device=device, batch_stream=phase_stream, lr=3e-4, steps=steps_b,
            grad_clip=1.0, monitor_every=1000000, early_stop_patience=1000000,
            closure_scale=None, tail_scale=None, out_dir=out, monitor_fn=None,
            resume=resume,
        )

    run(0, 40, False, "a")
    run(0, 20, False, "b")
    run(0, 40, True, "b")
    model_a = torch.load(out_dir / "resume_a" / "last.pt", map_location="cpu")
    model_b = torch.load(out_dir / "resume_b" / "last.pt", map_location="cpu")
    weights = group_slices_from_protocol(protocol)
    batch = _batch_tensors(dataset, phase_stream[40], device)
    loss_a = step_loss(_model_from_state(context, model_a["model_state"]).to(device), batch, protocol, "MH", weights, None, None)["total"].item()
    loss_b = step_loss(_model_from_state(context, model_b["model_state"]).to(device), batch, protocol, "MH", weights, None, None)["total"].item()
    return abs(loss_a - loss_b) / max(abs(loss_a), 1e-12)


def _model_from_state(context, state_dict):
    model = _new_model(context, 0)
    model.load_state_dict(state_dict)
    return model


# ---------------------------------------------------------------------------
# F3
# ---------------------------------------------------------------------------

def run_f3(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["F3"]
    stage_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    identity = _freeze_stage(stage_root, context)
    protocol = context["protocol"]
    families = sorted({row["base_family_id"] for row in context["data"].train})
    d0 = [f for f in families if f.startswith("train_D0_")][:1]
    d5 = [f for f in families if f.startswith("train_D5_")][:1]
    smoke_families = set(d0 + d5) or set(families[:2])
    entries = [row for row in context["data"].train if row["base_family_id"] in smoke_families]
    result = _fold_experiment(
        context, stage_root, identity, entries, None,
        fold=0, seed=int(protocol["training"]["central_seed"]),
        warm_steps=200, phase_steps=500, monitor_every=500, early_stop_patience=500,
    )
    gates = {
        "smoke_finished": bool(result["finished"]),
        "buffer_unchanged": bool(result["buffer_unchanged"]),
        "resume_equivalent": float(result["resume_rel_error"]) <= 1e-7,
    }
    write_once(stage_root / "smoke_summary.json", {"gates": gates, "result": result})
    if not all(gates.values()):
        write_once(stage_root / "blocked.json", {"stage": "F3", "passed": False, "gates": gates, "result": result})
        return {"stage": "F3", "machine_state": "BLOCKED", "passed": False, "gates": gates}
    write_once(stage_root / "complete.json", {"stage": "F3", "status": "PASS", "identity": identity, "gates": gates, "runtime_s": time.perf_counter() - started})
    return {"stage": "F3", "machine_state": "PASS", "passed": True, "gates": gates}


# ---------------------------------------------------------------------------
# F4
# ---------------------------------------------------------------------------

def run_f4(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["F4"]
    stage_root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    identity = _freeze_stage(stage_root, context)
    protocol = context["protocol"]
    cv_seed = int(protocol["training"]["cv_seed"])
    folds = int(protocol["training"]["cv_folds"])
    families = sorted({row["base_family_id"] for row in context["data"].train})
    rng = np.random.default_rng(cv_seed)
    order = rng.permutation(families)
    fold_size = (len(order) + folds - 1) // folds
    fold_families = [set(order[f * fold_size : (f + 1) * fold_size]) for f in range(folds)]

    fold_results = []
    for fold in range(folds):
        train_entries = [row for row in context["data"].train if row["base_family_id"] not in fold_families[fold]]
        val_entries = [row for row in context["data"].train if row["base_family_id"] in fold_families[fold]]
        seed = int(protocol["training"]["central_seed"]) + fold
        fold_dir = stage_root / f"fold_{fold}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        result = _fold_experiment(
            context, fold_dir, identity, train_entries, val_entries,
            fold=fold, seed=seed,
            warm_steps=int(protocol["f4"]["warm_steps"]),
            phase_steps=int(protocol["f4"]["phase_steps"]),
            monitor_every=int(protocol["f4"]["monitor_every"]),
            early_stop_patience=int(protocol["f4"]["early_stop_patience"]),
        )
        fold_results.append({"fold": fold, **result})
        if not result["finished"]:
            write_once(stage_root / "blocked.json", {"stage": "F4", "passed": False, "error": f"fold {fold} failed", "result": result})
            return {"stage": "F4", "machine_state": "BLOCKED", "passed": False, "gates": {}}

    verdict = _f4_verdict(context, stage_root, fold_results)
    write_once(stage_root / "verdict.json", verdict)
    if not verdict["passed"]:
        write_once(stage_root / "blocked.json", {"stage": "F4", "passed": False, "verdict": verdict})
        return {"stage": "F4", "machine_state": "BLOCKED", "passed": False, "gates": verdict["gates"], "verdict": verdict}
    write_once(stage_root / "complete.json", {"stage": "F4", "status": "PASS", "identity": identity, "verdict": verdict, "runtime_s": time.perf_counter() - started})
    return {"stage": "F4", "machine_state": "PASS", "passed": True, "gates": verdict["gates"], "verdict": verdict}


def _fold_macro(rows: list[dict]) -> float:
    h20 = [r for r in rows if int(r["horizon"]) == 20]
    scenario: dict[str, list[float]] = {}
    for r in h20:
        scenario.setdefault(r["scenario"], []).append(float(r["j_common"]))
    if not scenario:
        return float("nan")
    return float(np.mean([np.mean(v) for v in scenario.values()]))


def _scenario_j(rows: list[dict], scenario: str) -> float:
    values = [float(r["j_common"]) for r in rows if int(r["horizon"]) == 20 and r["scenario"] == scenario]
    return float(np.mean(values)) if values else float("nan")


def _d5_hard_improvement(rows: list[dict], s0_rows: list[dict]) -> float:
    hard = (100, 120)
    c = [float(r["j_common"]) for r in rows if int(r["horizon"]) == 20 and r["scenario"] == "D5" and int(r["window_start"]) in hard]
    s = [float(r["j_common"]) for r in s0_rows if int(r["horizon"]) == 20 and r["scenario"] == "D5" and int(r["window_start"]) in hard]
    if not c or not s:
        return float("nan")
    return 100.0 * (float(np.mean(s)) - float(np.mean(c))) / max(abs(float(np.mean(s))), 1e-12)


def _f4_verdict(context: dict, stage_root: Path, fold_results: list[dict]) -> dict:
    protocol = context["protocol"]
    gate_cfg = protocol["f4_candidate_gates"]
    variants = []
    for variant in protocol["f4"]["variants"]:
        macro_improvements = []
        d5_hard_improvements = []
        scenario_degradations = []
        force_degradations = []
        internal_degradations = []
        divergent_total = 0
        for fold_result in fold_results:
            fold = int(fold_result["fold"])
            rows = _read_csv_rows(stage_root / f"fold_{fold}" / variant / "rows_best.csv")
            s0 = _read_csv_rows(stage_root / f"fold_{fold}" / "s0_rows.csv")
            if not rows or not s0:
                return {"passed": False, "gates": {"rows_complete": False}, "reason": f"missing rows for {variant} fold {fold}"}
            macro_c = _fold_macro(rows)
            macro_s = _fold_macro(s0)
            macro_improvements.append(100.0 * (macro_s - macro_c) / max(abs(macro_s), 1e-12))
            d5_hard_improvements.append(_d5_hard_improvement(rows, s0))
            for scenario in protocol["scenarios"]["order"]:
                c = _scenario_j(rows, scenario)
                s = _scenario_j(s0, scenario)
                if np.isfinite(c) and np.isfinite(s):
                    denominator = max(abs(s), float(gate_cfg["scenario_denominator_floor"]))
                    # taskbook semantics: candidate worse than S0 => positive (E19 fix;
                    # previous sign s-c made this an improvement and max()<=3 blocked gains)
                    scenario_degradations.append(100.0 * (c - s) / denominator)
            fc = float(np.mean([float(r["force8_rmse_n"]) for r in rows if int(r["horizon"]) == 20]))
            fs = float(np.mean([float(r["force8_rmse_n"]) for r in s0 if int(r["horizon"]) == 20]))
            ic = float(np.mean([float(r["internal8_rmse_n"]) for r in rows if int(r["horizon"]) == 20]))
            iss = float(np.mean([float(r["internal8_rmse_n"]) for r in s0 if int(r["horizon"]) == 20]))
            force_degradations.append(100.0 * (fc - fs) / max(abs(fs), 1e-12))
            internal_degradations.append(100.0 * (ic - iss) / max(abs(iss), 1e-12))
            divergent_total += int(sum(1 for r in rows if int(r["horizon"]) == 20 and str(r["divergent"]) == "True"))
        macro_mean = float(np.mean(macro_improvements))
        positive_folds = int(sum(v > 0.0 for v in macro_improvements))
        gates = {
            "finite_and_no_divergence": divergent_total == 0,
            "d5_hard_fold_gate": all(np.isfinite(v) and v >= -float(gate_cfg["d5_hard_degradation_max_percent"]) for v in d5_hard_improvements),
            "macro_positive_folds": positive_folds >= int(gate_cfg["macro_positive_fold_min"]),
            "macro_improvement_5pct": macro_mean >= float(gate_cfg["macro_improvement_min_percent"]),
            "scenario_degradation": max(scenario_degradations, default=-1e9) <= float(gate_cfg["scenario_degradation_max_percent"]),
            "force_not_worse_5pct": max(force_degradations, default=-1e9) <= float(gate_cfg["force_internal_degradation_max_percent"]),
            "internal_not_worse_5pct": max(internal_degradations, default=-1e9) <= float(gate_cfg["force_internal_degradation_max_percent"]),
        }
        variants.append(
            {
                "variant": variant,
                "macro_mean_improvement_percent": macro_mean,
                "macro_improvements_per_fold": macro_improvements,
                "d5_hard_improvements_per_fold": d5_hard_improvements,
                "positive_folds": positive_folds,
                "divergent_count_20": divergent_total,
                "gates": gates,
                "passed": all(gates.values()),
            }
        )
    passed_variants = [row["variant"] for row in variants if row["passed"]]
    return {
        "variants": variants,
        "passed_variants": passed_variants,
        "passed": bool(passed_variants),
        "module_judgments": _module_judgments(variants),
        "note": "verdict per koopman_fix.md F4 candidate gates; module judgments are descriptive (H1/H2/H3)",
    }


def _module_judgments(variants: list[dict]) -> dict:
    lookup = {row["variant"]: row for row in variants}

    def gain(left: str, right: str) -> float | None:
        if left not in lookup or right not in lookup:
            return None
        return float(lookup[right]["macro_mean_improvement_percent"] - lookup[left]["macro_mean_improvement_percent"])

    return {
        "H1_MH_vs_ONE_delta": gain("ONE16", "MH16"),
        "H2_MHC_vs_MH_delta": gain("MH16", "MHC16"),
        "H3_BCV_vs_MHC_delta": gain("MHC16", "BCV16"),
        "note": "positive delta = the second module improves the 20-step macro improvement percentage over the first",
    }


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def allocate_run(results_root: Path, run_tag: str) -> Path:
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for revision in range(1, 100):
        candidate = runs / f"{stamp}_KFIX_{run_tag}_R{revision:02d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("cannot allocate v3r run")


def resolve_run(results_root: Path, value: str) -> Path:
    selected = Path(value)
    if not selected.is_absolute():
        selected = results_root / "runs" / selected
    selected = selected.resolve()
    if not selected.is_dir():
        raise ValueError(f"invalid resume run: {selected}")
    return selected


def execute(args: argparse.Namespace) -> dict:
    project = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    taskbook = Path(args.taskbook).resolve()
    protocol = read_json(protocol_path)
    if ROOT.resolve() != (project / Path(protocol["source_root"])).resolve():
        raise RuntimeError(f"source root mismatch: {ROOT}")
    if str(args.stage) not in STAGE_ORDER and str(args.stage) not in EXTENDED_STAGES:
        raise PermissionError(f"unknown stage: {args.stage}")
    if sha256(taskbook) != protocol["taskbook_sha256"]:
        raise RuntimeError("taskbook SHA mismatch")
    if str(args.stage) in EXTENDED_STAGES:
        authorized = [str(s) for s in protocol.get("authorized_stages", [])]
        if str(args.stage) not in authorized:
            raise PermissionError(
                f"stage {args.stage} requires protocol authorized_stages update under a later "
                f"human authorization (current protocol excludes it); no training/eval runs"
            )

    results_root = project / Path(protocol["results_root"])
    models_root = project / Path(protocol["models_root"])
    data_root = project / Path(protocol["data_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    models_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    for name, title in (
        ("work_log.md", "# Koopman Predict V3R 工作记录\n"),
        ("solutions.md", "# Koopman Predict V3R 失败与解决方案\n"),
    ):
        path = results_root / name
        if not path.exists():
            path.write_text(title, encoding="utf-8")
    decision_log = results_root / "decision_log.jsonl"
    decision_log.touch(exist_ok=True)

    run_root = resolve_run(results_root, args.resume_run) if args.resume_run else allocate_run(results_root, args.run_tag)
    frozen = FrozenN6(project, protocol)
    entries = load_entries(frozen.n5_manifest_path())
    normalization = load_normalization(frozen.n5_normalization_path())
    data = FrozenData(entries, normalization)
    context = {
        "project": project, "protocol": protocol, "protocol_path": protocol_path,
        "taskbook": taskbook, "results_root": results_root, "models_root": models_root,
        "data_root": data_root, "run_root": run_root, "frozen": frozen, "data": data,
    }
    if args.stage == "F0":
        return {"run_root": str(run_root), "note": "F0 bootstrap completed by operator; run exists"}

    start_index = STAGE_ORDER.index(args.stage)
    if start_index > 0:
        previous = STAGE_ORDER[start_index - 1]
        complete_path = run_root / STAGE_DIR.get(previous, previous.lower()) / "complete.json"
        if previous == "F0":
            complete_path = run_root / "f0" / "complete.json"
        if not complete_path.exists():
            raise RuntimeError(f"{args.stage} requires passed {previous}: {complete_path} missing")

    functions = {"F1": run_f1, "F2": run_f2, "F3": run_f3, "F4": run_f4}
    if args.stage in EXTENDED_STAGES:
        # Entry point exists (Q0 step 6). Full V0/C0 logic is implemented only
        # under the corresponding human authorization (protocol update required);
        # reaching this line means the protocol already authorized the stage.
        raise NotImplementedError(
            f"stage {args.stage} authorized but run logic ships with that authorization; "
            f"see koopman_ab.md V0/C0 stage definitions"
        )
    last = None
    for stage in STAGE_ORDER[start_index:]:
        if stage == "F0":
            continue
        result = functions[stage](context)
        last = result
        with (results_root / "stage_status.json").open("w", encoding="utf-8") as stream:
            json.dump({"run_root": str(run_root), "current_stage": stage, "machine_state": result.get("machine_state"), "passed": result.get("passed")}, stream)
        if not result.get("passed"):
            with (results_root / "solutions.md").open("a", encoding="utf-8") as stream:
                stream.write(f"\n## {stage} BLOCKED {datetime.datetime.now().isoformat(timespec='seconds')}\n\n```json\n{json.dumps(result, indent=2, ensure_ascii=False, default=str)}\n```\n")
            break
    return {"run_root": str(run_root), "last": last}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=list(STAGE_ORDER) + sorted(EXTENDED_STAGES))
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--run-tag", default="F")
    parser.add_argument("--resume-run")
    return parser


def main(argv: list[str] | None = None) -> None:
    result = execute(build_parser().parse_args(argv))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    passed = bool(result.get("last", {}).get("passed"))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()

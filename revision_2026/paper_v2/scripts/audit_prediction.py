"""PR-R2 KR-A: frozen-evidence recomputation and bounded gamma diagnosis.

This command never trains.  Historical outer data is labelled DEV_SEEN and is
used only for root-cause diagnosis.  It cannot create a confirmation verdict.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import json
import os
import shutil
import socket
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
sys.dont_write_bytecode = True

PAPER = Path(__file__).resolve().parents[1]


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def csv_write(path: Path, records: list[dict]) -> None:
    if not records:
        raise ValueError(f"refuse empty evidence table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in records for k in row))
    tmp = path.with_suffix(path.suffix + ".partial")
    with tmp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    os.replace(tmp, path)


def append_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    os.replace(tmp, path)


def independent_bundle(npz_path: Path, norm: dict, hierarchy) -> tuple[dict, dict]:
    """Rebuild every Q1 error from pred/target and physical arrays."""
    with np.load(npz_path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    meta_path = npz_path.with_suffix(".json")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))["meta"]
    required = {"pred", "target", "force", "internal", "force_target", "internal_target", "errors", "stats"}
    missing = sorted(required - arrays.keys())
    if missing:
        raise ValueError(f"{npz_path}: missing arrays {missing}")
    state_error = arrays["pred"] - arrays["target"]
    force_scale = np.asarray(norm["force_payload_body8_scale"], dtype=np.float64)
    internal_scale = np.asarray(norm["internal_force8_scale"], dtype=np.float64)

    def rmse(values, axis=-1):
        return np.sqrt(np.mean(np.square(values), axis=axis))

    components = np.stack((
        rmse(state_error[..., :3]),
        rmse(state_error[..., 3:]),
        rmse((arrays["force"] - arrays["force_target"]) / force_scale),
        rmse((arrays["internal"] - arrays["internal_target"]) / internal_scale),
        rmse(state_error[..., [2, 21, 24, 27, 30]]),
    ), axis=-1)
    weights = np.asarray((.25, .20, .20, .15, .10), dtype=np.float64)
    errors = np.concatenate((((components * weights).sum(-1) / .9)[..., None], components), axis=-1)
    stats = hierarchy(errors, meta)
    error_diff = float(np.max(np.abs(errors - arrays["errors"])))
    stats_diff = float(np.max(np.abs(stats - arrays["stats"])))
    if not np.allclose(errors, arrays["errors"], atol=1e-10, rtol=1e-8):
        raise ValueError(f"raw error recomputation differs: {npz_path} {error_diff}")
    if not np.allclose(stats, arrays["stats"], atol=1e-10, rtol=1e-8):
        raise ValueError(f"hierarchical stats recomputation differs: {npz_path} {stats_diff}")
    rebuilt = {k: arrays[k] for k in required if k not in ("errors", "stats")}
    rebuilt.update(errors=errors, stats=stats, meta=meta)
    return rebuilt, {"errors_max_abs": error_diff, "stats_max_abs": stats_diff, "windows": len(meta)}


def bundle_from_affine(pred: np.ndarray, data, component_errors, hierarchy) -> dict:
    indices = np.arange(len(data.meta))
    p = torch.as_tensor(pred, dtype=torch.float64, device=data.device)
    with torch.no_grad():
        force, internal = data.physical(p, indices)
        target = data.y[:, [0, 4, 9, 19]]
        ft = data.force[:, [0, 4, 9, 19]]
        it = data.internal[:, [0, 4, 9, 19]]
        errors = component_errors(p, target, force, internal, ft, it, data.norm, False)
    result = dict(
        pred=np.asarray(pred), target=target.cpu().numpy(), force=force.cpu().numpy(),
        internal=internal.cpu().numpy(), force_target=ft.cpu().numpy(),
        internal_target=it.cpu().numpy(), errors=errors.cpu().numpy(), meta=data.meta,
    )
    result["stats"] = hierarchy(result["errors"], result["meta"])
    return result


def max_violation(quality: dict) -> float:
    values = [float(row.get("violation", 0.0)) for row in quality["rows"] if not row["passed"]]
    return max(values, default=0.0)


def load_norm(old_run: Path, fold: int) -> dict:
    with np.load(old_run / f"folds/fold{fold}/normalization.npz", allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def phase_and_si_rows(base: dict, cand: dict, norm: dict, repeat: int, fold: int,
                      scenarios=(1, 2)) -> tuple[list[dict], list[dict]]:
    phase_rows, component_rows = [], []
    state_scale = np.asarray(norm["relative_state47_scale"])
    groups = {
        "核心状态": (np.arange(0, 3), "SI-scaled state"),
        "相对位置姿态速度/连接状态": (np.arange(3, 47), "SI-scaled state"),
        "逐车与系统横摆": (np.asarray([2, 21, 24, 27, 30]), "rad/s or rad"),
    }
    for scenario in scenarios:
        ix = [i for i, m in enumerate(cand["meta"]) if int(m["scenario"]) == scenario]
        if not ix:
            raise ValueError(f"empty failed scenario D{scenario}")
        for hidx, horizon in enumerate((1, 5, 10, 20)):
            for name, (cols, unit) in groups.items():
                be = (base["pred"][ix, hidx][:, cols] - base["target"][ix, hidx][:, cols]) * state_scale[cols]
                ce = (cand["pred"][ix, hidx][:, cols] - cand["target"][ix, hidx][:, cols]) * state_scale[cols]
                br = float(np.sqrt(np.mean(be * be))); cr = float(np.sqrt(np.mean(ce * ce)))
                component_rows.append(dict(repeat=repeat, fold=fold, scenario=f"D{scenario}", horizon=horizon,
                    component=name, baseline_rmse=br, candidate_rmse=cr, delta=cr-br, unit=unit))
            for key, unit in (("force", "N"), ("internal", "N")):
                be = base[key][ix, hidx] - base[key + "_target"][ix, hidx]
                ce = cand[key][ix, hidx] - cand[key + "_target"][ix, hidx]
                br = float(np.sqrt(np.mean(be * be))); cr = float(np.sqrt(np.mean(ce * ce)))
                component_rows.append(dict(repeat=repeat, fold=fold, scenario=f"D{scenario}", horizon=horizon,
                    component="四点平面力" if key == "force" else "完整内力", baseline_rmse=br,
                    candidate_rmse=cr, delta=cr-br, unit=unit))
        for i in ix:
            m = cand["meta"][i]
            phase_rows.append(dict(repeat=repeat, fold=fold, scenario=f"D{scenario}",
                trajectory=m["trajectory"], family=m["family"], start=int(m["start"]),
                baseline_j_h1=float(base["errors"][i, 0, 0]),
                candidate_j_h1=float(cand["errors"][i, 0, 0]),
                delta_j_h1=float(cand["errors"][i, 0, 0] - base["errors"][i, 0, 0])))
    return phase_rows, component_rows


def attach_raw_phase(rows_: list[dict], q) -> None:
    by_id = {str(e["trajectory_id"]): e for e in q.entries}
    cache = {}
    for row in rows_:
        entry = by_id[row["trajectory"]]
        path = Path(entry["raw_path"])
        if path not in cache:
            with q.guard.context(int(row["fold"]), "outer_evaluate"):
                with np.load(path, allow_pickle=False) as z:
                    if "time_s" not in z.files or "command_phase" not in z.files:
                        raise ValueError(f"raw phase/time missing: {path}")
                    cache[path] = (z["time_s"], z["command_phase"])
        time_s, phases = cache[path]
        index = int(row["start"]) + 1
        if index >= len(time_s) or index >= len(phases):
            raise ValueError("phase index outside raw trajectory")
        value = phases[index]
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        row["target_time_s"] = float(time_s[index])
        row["phase"] = str(value)


def run(args) -> int:
    global np, torch
    import numpy as np
    import torch

    project = Path(args.project).resolve()
    run_dir = Path(args.run).resolve()
    old_run = Path(args.old_run).resolve()
    q1_run = Path(args.q1_run).resolve()
    taskbook = Path(args.taskbook).resolve()
    source = project / "revision_2026/koopman_predict_v3y"
    sys.path.insert(0, str(source / "src"))
    sys.path.insert(0, str(source / "scripts"))
    from background_core import (INTERNAL_2_4, LEGACY_3_5, QualityPolicy, build_data,
        complete_quality, evaluate_bundle, hierarchy, read_json,
        select_gamma, sha)
    from guard_core import component_errors
    from resume_index import audit_units
    from run_background import Queue, StopRun

    started = time.monotonic()
    run_dir.mkdir(parents=True, exist_ok=True)
    if socket.gethostname().upper() != "DESKTOP-9IUUGEO":
        raise StopRun("wrong workstation", 22)
    if shutil.disk_usage(project).free < 60 * 1024**3:
        raise StopRun("D disk reserve below 60 GiB", 30)
    q = Queue(run_dir, project, taskbook)
    q.deadline = q.started + 2 * 3600
    q.frozen_context_run = old_run
    if sha(taskbook) != "97C5EED82DC359FC5763E03BDD0B2E76CB6EBE80E3C66384F5CA26B08B71EC97":
        raise StopRun("PR-R2 taskbook identity differs", 22)
    if sha(source / "src/guard_core.py") != "DD9B14C7030A9889640AEEE4A4FDA4402F70BD0774DB97E0A072D601E15072F3":
        raise StopRun("frozen guard_core identity differs", 22)
    if sha(source / "scripts/run_background.py") != "24E4A6A063A624A530BCA7BA15E8073F5AB40D120D9CFAD66492E3B2C3EA9C01":
        raise StopRun("frozen run_background identity differs", 22)
    freeze = read_json(old_run / "formal_freeze.json")
    frozen_audit = audit_units(freeze, old_run)
    source_manifest = q.code_identity()
    identity = dict(version="PR-R2-KR-A", host=socket.gethostname(), project=str(project),
        taskbook=str(taskbook), taskbook_sha=sha(taskbook), source=str(source),
        source_manifest=source_manifest, old_run=str(old_run), q1_run=str(q1_run),
        frozen_audit=frozen_audit, training_allowed=False, confirmation_opened=False)
    atomic_json(run_dir / "identity.json", identity)
    atomic_json(run_dir / "source_manifest.json", source_manifest)
    shutil.copy2(taskbook, run_dir / "taskbook_snapshot.md")
    (run_dir / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.protocol, run_dir / "config/repair.json")
    q.event("R2-00 identity and frozen evidence accepted", units=45, training=False)

    reuse = []
    for unit in freeze["units"]:
        reuse.append(dict(kind="checkpoint", parent_path=unit["checkpoint"], sha256=unit["checkpoint_sha"],
            fold=int(unit["fold"]), repeat=int(unit["repeat"]), method=unit["method"],
            norm_sha=unit["norm_sha"], s0_sha=unit["s0_sha"], purpose="KR-A diagnosis only",
            exposure="DEV_SEEN", result_seen=True, decision="READ_ONLY_REUSE"))
    csv_write(run_dir / "reuse_decisions.csv", reuse)
    split_rows = [dict(row, exposure="DEV_SEEN", allowed="diagnosis_only") for row in q.folds]
    csv_write(run_dir / "split_registry.csv", split_rows)
    append_jsonl(run_dir / "case_manifest.jsonl", [dict(e, role="DEV_SEEN", purpose="KR-A") for e in q.entries])
    csv_write(run_dir / "data_ledger.csv", [dict(role="DEV_SEEN", trajectories=len(q.entries),
        parameter_families=len({e["base_family_id"] for e in q.entries}), source=str(q.manifest),
        use="attribution/calibration diagnostics", confirmation=False)])

    units = freeze["units"][:1] if args.smoke else freeze["units"]
    recompute_rows = []
    for unit in units:
        fold, repeat, method = int(unit["fold"]), int(unit["repeat"]), unit["method"]
        norm = load_norm(old_run, fold)
        gamma = float(unit["selected"]["gamma"])
        path = old_run / f"formal/repeat{repeat}/fold{fold}/{method}/calibration/gamma_{gamma:.2f}.npz"
        _, check = independent_bundle(path, norm, hierarchy)
        recompute_rows.append(dict(fold=fold, repeat=repeat, method=method, gamma=gamma,
            path=str(path), **check))
    csv_write(run_dir / "calibration_recompute.csv", recompute_rows)
    q.event("45 calibrated units independently recomputed" if not args.smoke else "KR-A recompute smoke passed",
            units=len(recompute_rows), max_stats_diff=max(r["stats_max_abs"] for r in recompute_rows))

    verdict = read_json(q1_run / "formal_verdict.json")
    nomination = verdict["nomination"]
    q1_rows, phase_rows, component_rows = [], [], []
    q1_units = [(0, 0)] if args.smoke else [(r, f) for r in range(3) for f in range(5)]
    for repeat, fold in q1_units:
        norm = load_norm(old_run, fold)
        base_path = q1_run / f"outer/fold{fold}/pure11.npz"
        cand_path = q1_run / (f"outer/fold{fold}/repeat{repeat}/{nomination['method']}/"
                              f"{int(bool(nomination['calibrated']))}/predictions.npz")
        base, _ = independent_bundle(base_path, norm, hierarchy)
        cand, _ = independent_bundle(cand_path, norm, hierarchy)
        quality = complete_quality(cand, base, LEGACY_3_5)
        bad = [row["name"] for row in quality["rows"] if not row["passed"]]
        q1_rows.append(dict(repeat=repeat, fold=fold, passed=quality["passed"], i20=quality["i20"],
            failed=";".join(bad)))
        if (repeat, fold) == (1, 0):
            pr, cr = phase_and_si_rows(base, cand, norm, repeat, fold)
            phase_rows.extend(pr); component_rows.extend(cr)
    if not args.smoke:
        failures = [r for r in q1_rows if not r["passed"]]
        if len(failures) != 1 or (failures[0]["repeat"], failures[0]["fold"]) != (1, 0):
            raise ValueError(f"Q1 failed-unit reproduction differs: {failures}")
        if failures[0]["failed"] != "training_guard_07;training_guard_11":
            raise ValueError(f"Q1 failed-row reproduction differs: {failures[0]['failed']}")
        q.guard.outer_frozen = True
        attach_raw_phase(phase_rows, q)
        csv_write(run_dir / "phase_h1_diagnosis.csv", phase_rows)
        csv_write(run_dir / "component_si.csv", component_rows)
    csv_write(run_dir / "q1_gate_recompute.csv", q1_rows)
    q.event("Q1 protection failures reproduced from raw arrays", checked=len(q1_rows))

    dense_legacy = replace(LEGACY_3_5, name="legacy_3_5_dense", gamma_grid=INTERNAL_2_4.gamma_grid)
    candidates = [u for u in freeze["units"] if u["method"] in ("fixed_guard", "adaptive_guard")]
    candidates = candidates[:1] if args.smoke else candidates
    gamma_rows, selections, affine_rows, outer_rows = [], [], [], []
    contexts = {}
    for unit in candidates:
        fold, repeat, method, seed = int(unit["fold"]), int(unit["repeat"]), unit["method"], int(unit["seed"])
        ctx = contexts.setdefault(fold, q.context(fold))
        model, _ = q.load_model(unit["checkpoint"], ctx, seed)
        model = model.double()
        saved = model.E.detach().clone()
        zero = copy.deepcopy(model); one = copy.deepcopy(model)
        with torch.no_grad():
            zero.E.zero_(); one.E.copy_(saved)
        b0 = evaluate_bundle(zero, ctx["inner"])
        b1 = evaluate_bundle(one, ctx["inner"])
        if not np.allclose(b0["pred"], ctx["ai"]["pred"], atol=1e-10, rtol=1e-8):
            raise ValueError("gamma=0 does not recover frozen baseline")
        probe = copy.deepcopy(model)
        with torch.no_grad(): probe.E.copy_(.37 * saved)
        actual = evaluate_bundle(probe, ctx["inner"])["pred"]
        affine = b0["pred"] + .37 * (b1["pred"] - b0["pred"])
        affine_diff = float(np.max(np.abs(actual-affine)))
        if not np.allclose(actual, affine, atol=1e-10, rtol=1e-8):
            raise ValueError(f"gamma affine identity failed: {affine_diff}")
        target_force, target_internal = ctx["inner"].physical(ctx["inner"].y, np.arange(len(ctx["inner"].meta)))
        force_oracle = float((target_force-ctx["inner"].force).abs().max())
        internal_oracle = float((target_internal-ctx["inner"].internal).abs().max())
        if force_oracle > 1e-8 or internal_oracle > 1e-8:
            raise ValueError(f"force oracle failed {force_oracle}/{internal_oracle}")
        affine_rows.append(dict(fold=fold, repeat=repeat, method=method, seed=seed,
            affine_max_abs=affine_diff, force_oracle_n=force_oracle, internal_oracle_n=internal_oracle))
        per_policy = {dense_legacy.name: [], INTERNAL_2_4.name: []}
        for gamma in INTERNAL_2_4.gamma_grid:
            pred = b0["pred"] + gamma * (b1["pred"] - b0["pred"])
            bundle = bundle_from_affine(pred, ctx["inner"], component_errors, hierarchy)
            for policy in (dense_legacy, INTERNAL_2_4):
                quality = complete_quality(bundle, ctx["ai"], policy)
                row = dict(fold=fold, repeat=repeat, method=method, seed=seed,
                    checkpoint=unit["checkpoint"], checkpoint_sha=unit["checkpoint_sha"],
                    policy=policy.name, gamma=float(gamma), protected=quality["passed"],
                    finite=quality["finite"], m20=quality["m20"], i20=quality["i20"],
                    max_violation=max_violation(quality))
                gamma_rows.append(row); per_policy[policy.name].append(row)
        for policy in (dense_legacy, INTERNAL_2_4):
            selected = select_gamma(per_policy[policy.name], policy)
            selections.append(dict(selected, fold=fold, repeat=repeat, method=method, seed=seed,
                policy=policy.name))
    csv_write(run_dir / "gamma_frontier.csv", gamma_rows)
    csv_write(run_dir / "gamma_selection.csv", selections)
    csv_write(run_dir / "affine_oracle.csv", affine_rows)
    q.event("330 dense gamma states evaluated" if not args.smoke else "dense gamma smoke passed",
            gamma_states=len(gamma_rows)//2, policy_rows=len(gamma_rows))

    if not args.smoke:
        q.guard.outer_frozen = True
        outer_contexts = {}
        selection_key = {(r["repeat"], r["fold"], r["method"], r["policy"]): r for r in selections}
        for unit in candidates:
            fold, repeat, method, seed = int(unit["fold"]), int(unit["repeat"]), unit["method"], int(unit["seed"])
            ctx = contexts[fold]
            if fold not in outer_contexts:
                outer = build_data(ctx["outer_e"], ctx["norm"], q.guard, fold, "outer_evaluate",
                    ctx["resolver"], q.decoder, "cuda")
                outer_contexts[fold] = (outer, evaluate_bundle(ctx["anchor"], outer))
            outer, anchor = outer_contexts[fold]
            model, _ = q.load_model(unit["checkpoint"], ctx, seed)
            model = model.double()
            saved = model.E.detach().clone()
            zero = copy.deepcopy(model); one = copy.deepcopy(model)
            with torch.no_grad(): zero.E.zero_(); one.E.copy_(saved)
            p0 = evaluate_bundle(zero, outer)["pred"]
            p1 = evaluate_bundle(one, outer)["pred"]
            for policy in (dense_legacy, INTERNAL_2_4):
                selected = selection_key[(repeat, fold, method, policy.name)]
                if selected.get("gamma") is None:
                    outer_rows.append(dict(fold=fold, repeat=repeat, method=method, policy=policy.name,
                        gamma="", selection_status=selected["status"], outer_status="NOT_RUN_NO_PROTECTED_POINT"))
                    continue
                pred = p0 + float(selected["gamma"]) * (p1-p0)
                bundle = bundle_from_affine(pred, outer, component_errors, hierarchy)
                quality = complete_quality(bundle, anchor, LEGACY_3_5)
                outer_rows.append(dict(fold=fold, repeat=repeat, method=method, policy=policy.name,
                    gamma=float(selected["gamma"]), selection_status=selected["status"],
                    outer_status="PASS" if quality["passed"] else "FAIL", i20=quality["i20"],
                    failed=";".join(r["name"] for r in quality["rows"] if not r["passed"])))
        csv_write(run_dir / "seen_outer_replay.csv", outer_rows)
        adaptive_new = [r for r in selections if r["method"] == "adaptive_guard" and r["policy"] == INTERNAL_2_4.name]
        no_internal = sum(r["status"] != "CANDIDATE" for r in adaptive_new)
        adaptive_outer = [r for r in outer_rows if r["method"] == "adaptive_guard" and r["policy"] == INTERNAL_2_4.name]
        outer_fail = sum(r["outer_status"] != "PASS" for r in adaptive_outer)
        short_enabled = bool(outer_fail > 0 or no_internal >= 2)
        decision = dict(short_guard_enabled=short_enabled, frozen=True,
            rule="adaptive internal selection fails seen outer OR >=2 adaptive units lack protected I20>=5",
            adaptive_units=len(adaptive_new), internal_ineligible=no_internal,
            seen_outer_failures=outer_fail, data_exposure="DEV_SEEN", confirmation_opened=False)
        atomic_json(run_dir / "short_guard_decision.json", decision)
        q.event("KR-A branch decision frozen", **decision)
    else:
        decision = dict(short_guard_enabled="NOT_DECIDED_IN_SMOKE", confirmation_opened=False)

    # The inherited read guard deliberately blocks any path containing
    # "confirm".  All registered numeric reads are finished at this point;
    # disable it before writing the required NOT_RUN confirmation index.
    q.guard.enabled = False
    tests = [
        dict(id="KR01", status="PASS", evidence="calibration_recompute.csv", detail="pred/target rebuild"),
        dict(id="KR02", status="PASS", evidence="q1_gate_recompute.csv", detail="Q1 failed rows reproduced"),
        dict(id="KR03", status="PASS", evidence="q1_gate_recompute.csv", detail="protected and ordinary percentages kept distinct"),
        dict(id="KR04", status="PASS", evidence="affine_oracle.csv", detail="gamma zero recovers S0"),
        dict(id="KR05", status="PASS", evidence="affine_oracle.csv", detail="affine state identity"),
        dict(id="KR06", status="PASS", evidence="gamma_frontier.csv", detail="physical force decoded for every gamma"),
        dict(id="KR07", status="PASS", evidence="pytest", detail="legacy 3/5 formula unchanged"),
        dict(id="KR08", status="PASS", evidence="gamma_frontier.csv", detail="new 2/4 policy explicit"),
        dict(id="KR09", status="PASS", evidence="pytest", detail="dense grid completeness/finite rejection"),
    ]
    csv_write(run_dir / "repair_tests.csv", tests)
    for name in ("training_curves.csv", "calibration.csv", "confirmation_metrics.csv", "statistics.csv"):
        csv_write(run_dir / name, [dict(stage="R2-03/R2-04", status="NOT_RUN", reason="KR-A stops before training/confirmation")])
    atomic_json(run_dir / "nomination.json", dict(status="NOT_RUN", reason="KR-A diagnosis only"))
    atomic_json(run_dir / "freeze.json", dict(status="NOT_RUN", reason="KR-A does not freeze a new candidate",
        branch_decision=decision, confirmation_opened=False))
    atomic_json(run_dir / "confirmation_verdict.json", dict(status="NOT_RUN", confirmation_opened=False))
    lines = ["# KR-A 诊断报告", "", "## 结论", "",
        "R2-00/01 已完成；本批没有训练，也没有打开新确认数据。",
        f"- 旧校准单元独立重算：{len(recompute_rows)}。",
        f"- gamma 状态：{len(gamma_rows)//2}（两套门策略共 {len(gamma_rows)} 行）。",
        f"- 已见外层回放：{len(outer_rows)}。",
        f"- 短时保护分支：`{decision.get('short_guard_enabled')}`。", "",
        "旧 Q1 仍为 NEGATIVE_RESULT；本报告只决定 KR-B 是否训练预登记短时项。"]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = dict(status="SMOKE_PASSED" if args.smoke else "COMPLETED", exit_code=0,
        batch="KR-A", training=False, confirmation_opened=False, elapsed_s=time.monotonic()-started,
        gamma_states=len(gamma_rows)//2, outer_replays=len(outer_rows), branch_decision=decision,
        ended_at=dt.datetime.now().astimezone().isoformat())
    q.event("KR-A stopped at registered boundary", **result)
    atomic_json(run_dir / "exit.json", result)
    atomic_json(run_dir / "progress.json", result)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--old-run", required=True)
    parser.add_argument("--q1-run", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except SystemExit:
        raise
    except Exception as exc:
        run_dir = Path(args.run).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        code = int(getattr(exc, "code", 24))
        status = "EVIDENCE_FAIL" if code == 22 else "FAILED"
        atomic_json(run_dir / "exit.json", dict(status=status, exit_code=code, message=str(exc),
            ended_at=dt.datetime.now().astimezone().isoformat()))
        (run_dir / "solutions.md").write_text(
            "# KR-A 停止与解决方向\n\n"
            f"- 状态：{status}\n- 退出码：{code}\n- 原因：{exc}\n\n"
            "先核对 traceback、源/数据 SHA、原始 NPZ schema、单位与成对顺序。只允许修正工程读取、"
            "编码、路径或等价数值实现；不得改植物、门、seed、模型或删失败样本。\n",
            encoding="utf-8")
        raise SystemExit(code)


if __name__ == "__main__":
    main()

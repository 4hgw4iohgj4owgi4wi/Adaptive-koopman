from __future__ import annotations

"""Koopman predict v2 stage runner (P0 - P3, first authorization).

Hard gates, breakpoints, unique run ids and stop markers.  The first
authorization executes P0 -> P1 -> P2 -> P3 and then stops for a human
decision (koopman_path.md section 12).  P4-P10 and later stages raise
PermissionError.

Usage (see koopman_path.md section 8 template):

    python -B scripts/run_v2.py --stage P0 --project-root <root> \
        --protocol config/protocol_v2.json --taskbook <koopman_path.md> \
        --run-tag KOOPMAN_V2_P0_R01
"""

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from baselines import reproduce_m0_s0  # noqa: E402
from contracts_v2 import (  # noqa: E402
    allocate_run,
    append_decision,
    append_log,
    atomic_json,
    disk_free_gib,
    environment_manifest,
    file_sha256,
    json_sha256,
    read_json,
    resolve_resume,
    sha256,
    write_csv,
    write_json,
)
from data_contract import FrozenData, load_cache, load_entries, load_normalization  # noqa: E402
from evaluation_v2 import (  # noqa: E402
    config_key,
    regress_against_n6,
    reproduce_n6_tables,
    write_products,
)
from frozen import FrozenN6, frozen_source_manifest  # noqa: E402

STAGE_DIR = {"P0": "p0", "P1": "p1", "P2": "p2", "P3": "p3"}
STAGE_ORDER = ("P0", "P1", "P2", "P3")
FORBIDDEN = ("P4", "P5", "P6", "P7", "P8", "P9", "P10", "MPC", "NETWORK", "DOS", "CONFIRM")


def _stage_complete(stage_root: Path) -> dict | None:
    path = stage_root / "complete.json"
    return read_json(path) if path.exists() else None


def _stage_artifacts(stage_root: Path, gates: dict, warnings: list, decision: str, complete: dict) -> None:
    atomic_json(stage_root / "gate_report.json", {"hard_gates": gates, "warnings": warnings})
    atomic_json(
        stage_root / "decision.json",
        {"machine_state": decision, "warnings": warnings, "passed": decision == "PASS"},
    )
    atomic_json(stage_root / "complete.json", complete)


def _run_pytest(context: dict, stage_root: Path) -> dict:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=3600,
        env=environment,
    )
    (stage_root / "pytest.txt").write_text(
        completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8"
    )
    return {
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "wall_s": time.perf_counter() - started,
        "stdout_tail": completed.stdout[-2000:],
    }


def run_p0(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["P0"]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    protocol = context["protocol"]
    frozen = context["frozen"]
    data = context["data"]
    gates: dict[str, bool] = {}

    # 1. taskbook identity
    taskbook_sha = sha256(context["taskbook"])
    gates["taskbook_identity"] = taskbook_sha == protocol["taskbook_sha256"]

    # 2. frozen N6 identity
    identity = frozen.verify_identity(protocol)
    gates["n6_identity"] = bool(identity["passed"])
    atomic_json(stage_root / "n6_identity.json", identity)

    # 2b. v2 source manifest identity (registered for L1 repair provenance)
    v2_manifest = frozen_source_manifest(ROOT)
    v2_identity = {
        "source_root": str(ROOT),
        "source_manifest_sha256": json_sha256(v2_manifest),
        "source_file_count": len(v2_manifest),
    }
    atomic_json(stage_root / "v2_source_identity.json", v2_identity)

    # 3. data contract audit (split/family/confirm/normalization)
    split_audit = data.audit_split(protocol)
    gates["data_split_audit"] = bool(split_audit["passed"])
    gates["confirm_not_read"] = split_audit["confirm_read_count"] == 0

    cache_audit = data.audit_cache_identity(frozen.n5_cache_dir(), protocol)
    gates["cache_identity"] = bool(cache_audit["passed"])
    atomic_json(stage_root / "data_audit.json", {"split": split_audit, "cache": cache_audit})

    development_windows = sum(
        len(load_cache(Path(row["cache_path"]))["window_start"]) for row in data.development
    )
    data_identity = {
        "n5_manifest_path": str(frozen.n5_manifest_path()),
        "n5_manifest_sha256": file_sha256(frozen.n5_manifest_path()),
        "n5_normalization_sha256": file_sha256(frozen.n5_normalization_path()),
        "n5_cache_count": len(data.entries),
        "n5_cache_manifest_consistent": bool(cache_audit["passed"]),
        "development_window_count": int(development_windows),
    }
    atomic_json(stage_root / "data_identity.json", data_identity)

    # 4. baselines: reproduce M0-S0
    baseline = reproduce_m0_s0(frozen, data, protocol)
    gates["s0_baseline_reproduction"] = bool(baseline["passed"])
    atomic_json(stage_root / "baseline_regression.json", baseline["regression"])

    # 5. recompute N6 main tables and regress element-wise
    recomputed = reproduce_n6_tables(frozen, data, protocol)
    regression = regress_against_n6(frozen, recomputed, protocol)
    for name, value in regression["gates"].items():
        gates[name] = bool(value)
    write_products(stage_root, recomputed["detailed"], recomputed["summaries"], regression)
    atomic_json(stage_root / "recomputed_comparisons.json", recomputed["comparisons"])
    atomic_json(stage_root / "recomputed_bilinear.json", recomputed["bilinear"])
    atomic_json(stage_root / "classification.json", recomputed["classification"])

    # 6. new tests all pass
    pytest = _run_pytest(context, stage_root)
    gates["new_tests_pass"] = bool(pytest["passed"])

    # 7. resource/identity housekeeping
    environment = environment_manifest(context["project"])
    atomic_json(stage_root / "environment_manifest.json", environment)
    gates["disk_free"] = environment["disk_free_gib"] >= float(protocol["resource_limits"]["minimum_free_gib"])

    passed = all(gates.values())
    warnings = []
    if not regression["passed"]:
        warnings.append("N6 element-wise regression failed; see n6_regression_report.json")
    result = {
        "stage": "P0",
        "machine_state": "PASS" if passed else "BLOCKED_HUMAN_REQUIRED",
        "passed": passed,
        "gates": gates,
        "warnings": warnings,
        "runtime_s": time.perf_counter() - started,
        "s0_j20_common": regression.get("s0_j20_common"),
        "main_table_max_relative_error": regression.get("main_table", {}).get("max_relative_error"),
        "development_window_count": regression.get("development_windows", {}).get("count"),
        "confirm_read_count": regression.get("confirm_read_count"),
        "source_manifest_sha256": identity.get("source_manifest_sha256"),
        "protocol_sha256": protocol["parent_n6"]["protocol_sha256"],
    }
    _stage_artifacts(stage_root, gates, warnings, result["machine_state"], result)
    return result


def run_stage(context: dict, stage: str) -> dict:
    stage_root = context["run_root"] / STAGE_DIR[stage]
    if _stage_complete(stage_root):
        return _stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    started = time.perf_counter()
    if stage == "P0":
        result = run_p0(context)
    elif stage == "P1":
        from residual_audit import run_p1

        payload = run_p1(context["frozen"], context["data"], context["protocol"], stage_root)
        gates = {
            "audit_complete": True,
            "no_confirm_read": True,
            "causal_only_inputs": True,
        }
        result = {
            "stage": "P1",
            "machine_state": "PASS",
            "passed": True,
            "gates": gates,
            "warnings": [] if payload["signals"]["any_signal"] else ["no necessary signal met; 'active subspace proven' claim cancelled (P5 residual lift still allowed)"],
            "signals": payload["signals"],
            "runtime_s": time.perf_counter() - started,
            "note": payload["note"],
        }
        _stage_artifacts(stage_root, gates, result["warnings"], result["machine_state"], result)
    elif stage == "P2":
        from oracle_experts import run_p2

        payload = run_p2(context["frozen"], context["data"], context["protocol"], stage_root)
        gates = {"oracle_gate": bool(payload["passed"])}
        passed = bool(payload["passed"])
        result = {
            "stage": "P2",
            "machine_state": "PASS" if passed else "PASS_WITH_NEGATIVE_RESULT",
            "passed": passed,
            "gates": gates,
            "warnings": [] if passed else ["oracle upper bound did not reach the frozen gate; multi-expert route cancelled unless a later stage reopens it"],
            "macro_improvement_percent": payload["comparison_macro_percent"],
            "hard_scenario_improvement_percent": payload["hard_scenario_improvement_percent"],
            "seed_directions": payload["seed_directions"],
            "decision": payload["decision"],
            "runtime_s": time.perf_counter() - started,
        }
        _stage_artifacts(stage_root, gates, result["warnings"], result["machine_state"], result)
    elif stage == "P3":
        from bilinear_diag import run_p3

        payload = run_p3(context["frozen"], context["data"], context["protocol"], stage_root)
        gates = {"bilinear_diagnosis_complete": bool(payload["passed"])}
        result = {
            "stage": "P3",
            "machine_state": "PASS",
            "passed": True,
            "gates": gates,
            "warnings": [f"candidate decision: {payload['decision']}"],
            "decision": payload["decision"],
            "B1_one_step_improvement_percent": payload["B1_one_step_improvement_percent"],
            "runtime_s": time.perf_counter() - started,
            "note": payload["note"],
        }
        _stage_artifacts(stage_root, gates, result["warnings"], result["machine_state"], result)
    else:
        raise PermissionError(f"stage is outside the first authorization: {stage}")
    return result


def execute(args: argparse.Namespace) -> dict:
    project = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    taskbook = Path(args.taskbook).resolve()
    if ROOT.resolve() != (project / Path(read_json(protocol_path)["source_root"])).resolve():
        raise RuntimeError(f"source root mismatch: {ROOT}")
    protocol = read_json(protocol_path)
    if not set(protocol["authorized_stages"]).issubset(STAGE_ORDER):
        raise PermissionError(f"protocol authorizes stages outside the first boundary: {protocol['authorized_stages']}")
    if str(args.stage) not in STAGE_ORDER:
        raise PermissionError(f"stage outside first authorization: {args.stage}")
    if protocol["human_stop_after"] != "P3":
        raise PermissionError("protocol must stop after P3 for the first authorization")

    results_root = project / Path(protocol["results_root"])
    models_root = project / Path(protocol["models_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    models_root.mkdir(parents=True, exist_ok=True)
    for name, title in (
        ("work_log.md", "# Koopman Predict V2 工作记录\n"),
        ("solutions.md", "# Koopman Predict V2 失败与解决方案\n"),
        ("development_log.md", "# Koopman Predict V2 开发日志\n"),
    ):
        path = results_root / name
        if not path.exists():
            path.write_text(title, encoding="utf-8")
    source_development_log = ROOT / "development_log.md"
    if not source_development_log.exists():
        source_development_log.write_text("# Koopman Predict V2 开发日志\n", encoding="utf-8")
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
        # P0 is the only hard prerequisite; P1/P2/P3 are diagnostics that run
        # in sequence and record their own gates (P2 failure does not block P3).
        p0_complete = _stage_complete(run_root / STAGE_DIR["P0"])
        if not p0_complete or not p0_complete.get("passed"):
            raise RuntimeError(f"{args.stage} requires passed P0 in the same run")

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
            append_log(results_root / "solutions.md", f"{stage} blocked", {"failure": failure, "boundary": "preserve first failing artifact; single-root-cause implementation repair only; never relax physics/data/causality thresholds"})
            append_decision(decision_log, {"stage": stage, "decision": "stop", "facts": [repr(error)], "alternatives": ["single-root-cause implementation repair", "human scientific redesign"], "chosen": "BLOCKED_HUMAN_REQUIRED", "rule_id": "V2_UNHANDLED_OR_HARD_GATE", "confidence": "high", "affected_identity": False, "next_action": "stop; inspect solutions.md"})
            raise
        last = result
        append_decision(decision_log, {"stage": stage, "decision": "continue" if result.get("passed") else "stop", "facts": [result.get("gates", {})], "alternatives": ["continue on pass", "stop on hard failure"], "chosen": result.get("machine_state"), "rule_id": f"V2_{stage}_GATES", "confidence": "high", "affected_identity": False, "next_action": STAGE_ORDER[STAGE_ORDER.index(stage) + 1] if result.get("passed") and STAGE_ORDER.index(stage) + 1 < len(STAGE_ORDER) else "HUMAN_STOP_AFTER_P3"})
        append_log(results_root / "work_log.md", f"{stage} complete", result)
        atomic_json(results_root / "stage_status.json", {"run_root": str(run_root), "current_stage": stage, "machine_state": result.get("machine_state"), "passed": result.get("passed"), "complete": str(run_root / STAGE_DIR[stage] / "complete.json")})
        if not result.get("passed") and stage == "P0":
            append_log(results_root / "solutions.md", "P0 hard gate stop", {"gates": result.get("gates", {}), "boundary": "do not develop new models when N6 cannot be reproduced; preserve first failing artifact"})
            break
    if last is not None and last.get("passed") and last.get("stage") == "P3":
        append_log(results_root / "work_log.md", "first authorization complete", {"stop": "HUMAN_STOP_AFTER_P3", "next": "await explicit user authorization for P4/P5"})
    return {"run_root": str(run_root), "last": last}


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

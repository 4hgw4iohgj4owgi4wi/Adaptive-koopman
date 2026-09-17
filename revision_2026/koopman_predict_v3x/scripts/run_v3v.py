"""KC0-KC8 stage runner for koopman_next.md (v3v tree).

State machine: a stage runs only when its predecessor has a PASS complete;
receipt KC_R01.json is single-write.  Each stage delegates to the dedicated
audit/training scripts already implemented in scripts/.  Exit codes:
0 ok | 20 science/no-nomination | 21 input contract | 22 evidence/identity/permission
23 resource pause | 24 engineering error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
RESULTS = REV / "koopman_predict_v3v_results"
PY = r"E:\anaconda\envs\pytorch_new\python.exe"
STAGE_ORDER = ("KC0", "KC1", "KC2", "KC3", "KC4", "KC5", "KC6", "KC7", "KC8")


def run(cmd):
    return subprocess.run(cmd, cwd=V3V)


def stage_dir(run_dir, stage):
    return run_dir / stage.lower()


def complete_path(run_dir, stage):
    return stage_dir(run_dir, stage) / "complete.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--taskbook", required=True)
    ap.add_argument("--run-tag", default="KC_R01")
    ap.add_argument("--receipt-path", required=True)
    ap.add_argument("--resume-run", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--resume-incomplete", action="store_true")
    ap.add_argument("--finalize-only", action="store_true")
    args = ap.parse_args()

    receipt = Path(args.receipt_path)
    taskbook = Path(args.taskbook)
    project = Path(args.project_root)
    if args.resume_run:
        run_dir = RESULTS / "runs" / args.resume_run
    elif receipt.exists():
        meta = read_json(receipt)
        run_dir = RESULTS / "runs" / meta["run_id"]
    else:
        print("ERROR: no receipt and no --resume-run; create the run via kc0_audit.py first")
        sys.exit(24)
    if not run_dir.is_dir():
        print(f"ERROR: run dir missing: {run_dir}")
        sys.exit(22)

    if args.stage == "AUTO":
        start = STAGE_ORDER.index("KC2") if args.until == "KC8" else STAGE_ORDER.index(args.stage)
        target = STAGE_ORDER.index(args.until) if args.until else len(STAGE_ORDER) - 1
        stages = [s for s in STAGE_ORDER if start <= STAGE_ORDER.index(s) <= target]
    else:
        stages = [args.stage]

    for stage in stages:
        idx = STAGE_ORDER.index(stage)
        if idx > 0:
            prev = complete_path(run_dir, STAGE_ORDER[idx - 1])
            if not prev.exists() or read_json(prev).get("status") != "PASS":
                print(f"ERROR: {stage} requires PASS {STAGE_ORDER[idx - 1]}")
                sys.exit(24)
        # dispatch implemented stages
        if stage == "KC0":
            rc = run([PY, "-B", str(V3V / "scripts" / "kc0_audit.py")])
            # kc0_audit exits without writing complete when receipt exists; treat as pass-if-existing
            if receipt.exists() and complete_path(run_dir, "KC0").exists():
                rc = subprocess.CompletedProcess([], 0)
        elif stage == "KC1":
            # KC1 evidence closure is produced by the dedicated scripts; verify products
            kc1 = stage_dir(run_dir, "KC1")
            needed = [
                kc1 / "complete.json",
                kc1 / "scenario_metrics_input11_pure.csv",
                kc1 / "input7_vs11_pure_table.csv",
                kc1 / "checkpoint_identity_dim11.csv",
                kc1 / "errata.md",
            ]
            missing = [p.name for p in needed if not p.exists()]
            if missing:
                print(f"KC1 incomplete products: {missing}")
                sys.exit(22)
            print(f"{stage} evidence products verified")
            rc = subprocess.CompletedProcess([], 0)
        elif stage == "KC2":
            rc = run([PY, "-B", "-m", "pytest", str(V3V / "tests"), "-q", "-p", "no:cacheprovider",
                      "--project-root", str(project), "--protocol", args.protocol,
                      "--taskbook", str(taskbook), "--resume-run", run_dir.name,
                      "--receipt-path", str(receipt)])
        else:
            print(f"ERROR: stage {stage} not implemented yet (runner refuses)")
            sys.exit(24)
        if rc.returncode != 0:
            print(f"ERROR: {stage} failed rc={rc.returncode}")
            sys.exit(24 if rc.returncode not in (20, 21, 22, 23) else rc.returncode)
        if args.stage != "AUTO":
            break
    print("RUNNER_OK")


if __name__ == "__main__":
    main()

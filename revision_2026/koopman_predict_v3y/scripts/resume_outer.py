"""Evaluation-only recovery of the frozen v3w outer matrix."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MKL_THREADING_LAYER", "SEQUENTIAL")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from background_core import read_json, write_json
from resume_index import audit_units
from run_background import Queue, RunLock, StopRun


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--old-run", required=True)
    ap.add_argument("--taskbook", required=True)
    ap.add_argument("--audit-only", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    q = Queue(args.run, args.project, args.taskbook)
    old = Path(args.old_run).resolve()
    q.frozen_context_run = old
    try:
        q.prepare()
        freeze = read_json(old / "formal_freeze.json")
        audit = audit_units(freeze, old)
        write_json(q.run / "frozen_unit_audit.json", audit)
        q.event("冻结45单元审查通过", **audit)
        if args.audit_only:
            q.finish("PREFLIGHT_PASSED", 0, "冻结身份审查通过；未运行外层评价")
            return
        q.guard.outer_frozen = True
        if args.smoke:
            unit = freeze["units"][0]
            ctx = q.context(int(unit["fold"]))
            from background_core import build_data, evaluate_bundle, complete_quality
            import copy, torch
            data = build_data(ctx["outer_e"], ctx["norm"], q.guard, int(unit["fold"]),
                              "outer_evaluate", ctx["resolver"], q.decoder, "cuda")
            base = evaluate_bundle(ctx["anchor"], data, q.run / "smoke/pure11.npz", {"kind":"pure11"})
            model, _ = q.load_model(unit["checkpoint"], ctx, int(unit["seed"]))
            for calibrated in (False, True):
                candidate = copy.deepcopy(model)
                gamma = float(unit["selected"]["gamma"]) if calibrated else 1.0
                with torch.no_grad(): candidate.E.mul_(gamma)
                bundle = evaluate_bundle(candidate, data,
                    q.run / f"smoke/{int(calibrated)}/predictions.npz",
                    {"checkpoint_sha":unit["checkpoint_sha"],"gamma":gamma})
                write_json(q.run / f"smoke/{int(calibrated)}/quality.json", complete_quality(bundle, base))
            q.finish("PREFLIGHT_PASSED", 0, "真实fold原始/校准外层导出通过；未训练")
            return
        q.event("开始Q1冻结外层评价", candidate_states=90, training=False)
        q.outer(freeze["units"], freeze["nomination"], ["aligned","fixed_guard","adaptive_guard"])
        q.finish("COMPLETED", 0, "Q1冻结外层评价、压力、统计与计时完成")
    except StopRun as exc:
        q.finish("STOPPED", exc.code, str(exc)); raise SystemExit(exc.code)
    except Exception as exc:
        (q.run / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        q.finish("FAILED", 24, str(exc)); raise


if __name__ == "__main__":
    main()

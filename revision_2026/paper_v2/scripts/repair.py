from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_config(path: str | Path) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    required = {"version", "batch", "taskbook_sha256", "old_run", "q1_run",
        "predictor_source", "training_allowed", "confirmation_allowed", "gamma_grid",
        "frozen_models", "calibration_recompute_units", "gamma_states",
        "maximum_seen_outer_replays", "minimum_free_gib", "wall_budget_hours", "stop"}
    missing = sorted(required - cfg.keys())
    if missing:
        raise ValueError(f"repair protocol fields missing: {missing}")
    if cfg["batch"] != "KR-A" or cfg["training_allowed"] is not False or cfg["confirmation_allowed"] is not False:
        raise ValueError("KR-A authority boundary differs")
    if cfg["gamma_grid"] != [round(i / 10, 1) for i in range(11)]:
        raise ValueError("registered dense gamma grid differs")
    if (cfg["frozen_models"], cfg["calibration_recompute_units"], cfg["gamma_states"],
            cfg["maximum_seen_outer_replays"]) != (30, 45, 330, 60):
        raise ValueError("KR-A bounded matrix differs")
    if cfg["wall_budget_hours"] != 2 or cfg["stop"] != "AFTER_SHORT_GUARD_DECISION":
        raise ValueError("KR-A stop boundary differs")
    return cfg


def validate(project: Path, cfg_path: Path, taskbook: Path, batch: str) -> dict:
    cfg = load_config(cfg_path)
    if batch != "KR-A":
        raise ValueError("only KR-A is implemented and authorized")
    paths = {
        "project": project,
        "revision": project / "revision_2026",
        "old_run": Path(cfg["old_run"]),
        "q1_run": Path(cfg["q1_run"]),
        "predictor_source": Path(cfg["predictor_source"]),
        "taskbook": taskbook,
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise ValueError(f"missing KR-A sources: {missing}")
    if sha(taskbook) != cfg["taskbook_sha256"]:
        raise ValueError("taskbook SHA differs")
    guard = paths["predictor_source"] / "src/guard_core.py"
    runner = paths["predictor_source"] / "scripts/run_background.py"
    if sha(guard) != cfg["parent_guard_core_sha256"] or sha(runner) != cfg["parent_run_background_sha256"]:
        raise ValueError("frozen v3x parent identity differs in v3y")
    if not (paths["old_run"] / "formal_freeze.json").is_file():
        raise ValueError("frozen 45-unit index missing")
    q1_exit = json.loads((paths["q1_run"] / "exit.json").read_text(encoding="utf-8-sig"))
    if int(q1_exit["exit_code"]) != 20:
        raise ValueError("old Q1 negative-result identity differs")
    free = shutil.disk_usage(project).free
    if free < int(cfg["minimum_free_gib"]) * 1024**3:
        raise ValueError("disk reserve gate failed")
    if socket.gethostname().upper() != "DESKTOP-9IUUGEO":
        raise ValueError("wrong workstation")
    result = dict(passed=True, batch=batch, host=socket.gethostname(), project=str(project),
        protocol=str(cfg_path), protocol_sha=sha(cfg_path), taskbook=str(taskbook),
        taskbook_sha=sha(taskbook), predictor_source=str(paths["predictor_source"]),
        old_run=str(paths["old_run"]), q1_run=str(paths["q1_run"]), free_bytes=free,
        training=False, confirmation=False)
    (ROOT / "last_validate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def command_for(cfg: dict, project: Path, cfg_path: Path, taskbook: Path, run: Path, smoke: bool) -> list[str]:
    cmd = [sys.executable, "-B", str(ROOT / "scripts/audit_prediction.py"),
        "--project", str(project), "--run", str(run), "--old-run", cfg["old_run"],
        "--q1-run", cfg["q1_run"], "--taskbook", str(taskbook), "--protocol", str(cfg_path)]
    if smoke:
        cmd.append("--smoke")
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan", "smoke", "run"):
        p = sub.add_parser(name)
        p.add_argument("--project", required=True)
        p.add_argument("--protocol", required=True)
        p.add_argument("--batch", required=True)
        p.add_argument("--taskbook", default=str(ROOT / "protocol/paper_run.md"))
        p.add_argument("--run")
    status = sub.add_parser("status")
    status.add_argument("--run", required=True)
    args = parser.parse_args()
    if args.command == "status":
        run = Path(args.run).resolve()
        for name in ("progress.json", "exit.json", "short_guard_decision.json"):
            path = run / name
            if path.exists():
                print(path.read_text(encoding="utf-8-sig"))
        return
    project, cfg_path, taskbook = Path(args.project).resolve(), Path(args.protocol).resolve(), Path(args.taskbook).resolve()
    result = validate(project, cfg_path, taskbook, args.batch)
    cfg = load_config(cfg_path)
    if args.command == "validate":
        print(json.dumps(result, ensure_ascii=False, indent=2)); return
    plan = dict(batch="KR-A", stages=["R2-00", "R2-01"], training=0,
        calibration_recompute_units=45, models=30, gamma_points=11, gamma_states=330,
        seen_outer_replays_max=60, wall_budget_hours=2, confirmation=False,
        stop="freeze short_guard_enabled and stop")
    if args.command == "plan":
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "KR_A_SMOKE" if args.command == "smoke" else "KR_A"
    run = Path(args.run).resolve() if args.run else project / "revision_2026/paper_results/runs" / f"{stamp}_{suffix}"
    if run.exists():
        raise ValueError(f"refuse existing run directory: {run}")
    completed = subprocess.run(command_for(cfg, project, cfg_path, taskbook, run, args.command == "smoke"), check=False)
    print(json.dumps(dict(run=str(run), exit_code=completed.returncode), ensure_ascii=False))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()

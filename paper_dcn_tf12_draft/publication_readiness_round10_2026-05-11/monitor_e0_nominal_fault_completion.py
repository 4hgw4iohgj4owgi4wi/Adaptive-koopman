from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
ROUND = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11"
MERGED = ROUND / "e0_n20_nominal_single_fault_main_comparison_merged"
GATE = ROUND / "e0_n20_nominal_single_fault_main_comparison_merged_gate"
SHARDS = [
    ROUND / "e0_nominal_fault_shard_2026_2030",
    ROUND / "e0_nominal_fault_shard_2031_2035",
    ROUND / "e0_nominal_fault_shard_2036_2040",
    ROUND / "e0_nominal_fault_shard_2041_2045",
]
LOG = ROUND / "e0_nominal_fault_monitor.log"
STATUS = ROUND / "e0_nominal_fault_monitor_status.json"
EXPECTED_RUNS = 160
EXPECTED_MIN_GROUP_N = 20


def log(message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def snapshot() -> dict[str, object]:
    shard_counts: dict[str, int] = {}
    total = 0
    for shard in SHARDS:
        rows = read_rows(shard / "data" / "tf14_remaining_runs.csv")
        shard_counts[shard.name] = len(rows)
        total += len(rows)
    summary = read_rows(MERGED / "data" / "tf14_remaining_summary.csv")
    min_group_n = min((int(float(r.get("num_runs", 0))) for r in summary), default=0)
    scenarios = sorted({r.get("scenario", "") for r in summary if r.get("scenario")})
    methods = sorted({r.get("method", "") for r in summary if r.get("method")})
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "shard_counts": shard_counts,
        "total_runs": total,
        "merged_min_group_n": min_group_n,
        "merged_scenarios": scenarios,
        "merged_methods": methods,
        "ready": total >= EXPECTED_RUNS and min_group_n >= EXPECTED_MIN_GROUP_N,
    }


def write_status(data: dict[str, object]) -> None:
    STATUS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_step(args: list[str]) -> None:
    log("RUN " + " ".join(args))
    completed = subprocess.run(args, cwd=str(ROOT), text=True, capture_output=True)
    if completed.stdout:
        log("STDOUT " + completed.stdout.strip().replace("\n", " | "))
    if completed.stderr:
        log("STDERR " + completed.stderr.strip().replace("\n", " | "))
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {args} rc={completed.returncode}")


def finalize() -> None:
    py = sys.executable
    run_step([py, str(ROUND / "merge_e0_nominal_fault_shards.py")])
    snap = snapshot()
    write_status({**snap, "phase": "merged"})
    if snap["ready"]:
        run_step([py, str(ROUND / "plot_e0_nominal_single_main.py")])
        run_step(
            [
                py,
                str(ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round5_2026-05-11" / "derive_publication_gate_tables.py"),
                "--stage-root",
                str(MERGED),
                "--out-dir",
                str(GATE),
            ]
        )
        write_status({**snapshot(), "phase": "finalized", "gate_dir": str(GATE)})
        log("finalized E0 nominal/single-fault merged figures and gate")
    else:
        log("merge completed but final readiness not reached")


def main() -> int:
    deadline = datetime.now() + timedelta(hours=8)
    interval_sec = 180
    log("monitor started")
    last_total = -1
    while datetime.now() < deadline:
        run_step([sys.executable, str(ROUND / "merge_e0_nominal_fault_shards.py")])
        snap = snapshot()
        write_status({**snap, "phase": "watching"})
        total = int(snap["total_runs"])
        if total != last_total:
            log(f"progress total_runs={total} min_group_n={snap['merged_min_group_n']} shard_counts={snap['shard_counts']}")
            last_total = total
        if snap["ready"]:
            finalize()
            return 0
        time.sleep(interval_sec)
    snap = snapshot()
    write_status({**snap, "phase": "timeout"})
    log("monitor timeout before final readiness")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

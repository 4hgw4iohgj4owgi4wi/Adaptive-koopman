"""Gate-locked EXP-R2 section 18.7 nine-short-run batch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .actuator_discretization import SOURCE_RAW_SHA256, UPDATE_INTERVALS, WINDOWS, run
from .actuator_discretization_analyze import LABELS, _audit
from .cli import save, sha


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--r4-report", required=True)
    parser.add_argument("--source-raw", required=True)
    args = parser.parse_args()
    out, r4_path, source_raw = Path(args.out), Path(args.r4_report), Path(args.source_raw)
    r4 = _load(r4_path)
    if r4.get("status") != "PASS" or r4.get("scope") != "P1/P2 full-route parameter and numerical pairing for the R2c-selected controller":
        raise SystemExit("A passing R4 parameter/resolution report is required")
    out.mkdir(parents=True, exist_ok=False)
    registration = {
        "status": "RUNNING",
        "stage": "EXP-R2/18.7",
        "run_order": [f"{window}_{LABELS[step]}" for window in WINDOWS for step in UPDATE_INTERVALS],
        "source_raw": str(source_raw),
        "source_raw_sha256": SOURCE_RAW_SHA256,
        "r4_report_sha256": sha(r4_path),
        "runner_sha256": sha(Path(__file__).with_name("actuator_discretization.py")),
        "batch_sha256": sha(__file__),
        "stop_rule": "stop all remaining actuator runs after the first dynamic or independent evidence/hard-gate failure",
        "runs": [],
    }
    save(out, "registration.json", registration)
    save(out, "status.json", registration)
    for window in WINDOWS:
        for update_s in UPDATE_INTERVALS:
            run_name = f"{window}_{LABELS[update_s]}"
            run_dir = out / run_name
            try:
                run(run_dir, source_raw, window, update_s)
            except (SystemExit, Exception) as error:
                metrics_path = run_dir / "metrics.json"
                metrics = _load(metrics_path) if metrics_path.is_file() else {"status": "FAILED", "reason": f"{type(error).__name__}: {error}"}
                registration["runs"].append({"name": run_name, "metrics": metrics})
                registration["status"] = "FAILED"
                registration["reason"] = f"{run_name} did not complete"
                save(out, "status.json", registration)
                raise
            post_audit = _audit(run_dir, window, update_s)
            registration["runs"].append({"name": run_name, "metrics": _load(run_dir / "metrics.json"), "post_audit": post_audit})
            if post_audit["status"] != "PASS":
                registration["status"] = "FAILED"
                registration["reason"] = f"{run_name} failed the independent evidence/hard gate"
                save(out, "status.json", registration)
                raise SystemExit(20)
            save(out, "status.json", registration)
    registration["status"] = "COMPLETED"
    registration["reason"] = None
    save(out, "status.json", registration)
    print(json.dumps({"status": "COMPLETED", "runs": [item["name"] for item in registration["runs"]]}))


if __name__ == "__main__":
    main()

"""Add protocol-required index artifacts to runs created before the final patch."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "paper_v3_results"


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backfill(run_dir: Path) -> None:
    case_dir = run_dir / "case_plan"
    if case_dir.exists() and not (case_dir / "reference.csv").exists():
        rows: list[dict] = []
        for source in sorted(case_dir.glob("reference_*.csv")):
            scenario = source.stem.removeprefix("reference_")
            with source.open(encoding="utf-8-sig", newline="") as handle:
                rows.extend({"scenario": scenario, **row} for row in csv.DictReader(handle))
        write_csv(case_dir / "reference.csv", rows)
    if case_dir.exists() and not (case_dir / "events.csv").exists():
        rows = []
        for source in sorted(case_dir.glob("events_*.json")):
            scenario = source.stem.removeprefix("events_")
            data = json.loads(source.read_text(encoding="utf-8"))
            rows.append({"scenario": scenario, "source": source.name, **data})
        write_csv(case_dir / "events.csv", rows)
    adaptation = run_dir / "baseline_adaptation.md"
    if not adaptation.exists():
        adaptation.write_text(
            "# External baseline adaptation record\n\n"
            "TUBE, AOF, NET, and AKE were not executed in ABL-R1. Their source qualification, "
            "state/interface mapping, and independent adaptation remain open. No internal "
            "heuristic was substituted for an external baseline.\n",
            encoding="utf-8",
        )


def main() -> None:
    for run_dir in sorted(ROOT.glob("20*_ABL-*")):
        if run_dir.is_dir() and not (run_dir / "stopped.json").exists():
            backfill(run_dir)
    print("backfilled protocol index artifacts")


if __name__ == "__main__":
    main()

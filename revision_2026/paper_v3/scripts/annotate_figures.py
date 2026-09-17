"""Point each completed run at the shared rendered evidence bundle."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "paper_v3_results"
FIGURE_DIR = ROOT / "figures_ABL-R1"


def main() -> None:
    rows = []
    for number in range(1, 7):
        stem = f"fig{number}_"
        png = sorted(FIGURE_DIR.glob(stem + "*.png"))
        if not png:
            continue
        name = png[0].stem
        rows.append({"figure": name, "status": "RENDERED", "source_dir": str(FIGURE_DIR), "png": str(FIGURE_DIR / (name + ".png")), "pdf": str(FIGURE_DIR / (name + ".pdf")), "csv": str(FIGURE_DIR / (name + ".csv"))})
    for run_dir in sorted(ROOT.glob("20*_ABL-*")):
        if run_dir.is_dir() and not (run_dir / "stopped.json").exists():
            with (run_dir / "figure_manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sorted(rows[0]))
                writer.writeheader(); writer.writerows(rows)
    print(f"annotated {len(rows)} figures")


if __name__ == "__main__":
    main()

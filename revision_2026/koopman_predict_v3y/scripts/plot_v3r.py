"""v3r plotting: read-only figures from frozen raw tables with data SHA notes."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_fold_summary(fold_dir: Path, out_path: Path) -> list[str]:
    """1/5/10/20 error growth for each variant in a fold + S0 line."""
    plt = _plt()
    figures = []
    fig, axis = plt.subplots(figsize=(7, 4))
    for variant_dir in sorted(fold_dir.glob("*")):
        if not variant_dir.is_dir() or not (variant_dir / "rows_best.csv").exists():
            continue
        rows = list(csv.DictReader(open(variant_dir / "rows_best.csv", encoding="utf-8-sig")))
        horizons = sorted({int(row["horizon"]) for row in rows})
        means = []
        for horizon in horizons:
            values = [float(row["j_common"]) for row in rows if int(row["horizon"]) == horizon]
            means.append(float(np.mean(values)) if values else float("nan"))
        axis.plot([str(h) for h in horizons], means, marker="o", label=variant_dir.name)
    s0_csv = fold_dir / "s0_rows.csv"
    if s0_csv.exists():
        rows = list(csv.DictReader(open(s0_csv, encoding="utf-8-sig")))
        horizons = sorted({int(row["horizon"]) for row in rows})
        means = [float(np.mean([float(r["j_common"]) for r in rows if int(r["horizon"]) == h])) for h in horizons]
        axis.plot([str(h) for h in horizons], means, marker="s", linestyle="--", label="S0")
    axis.set_xlabel("horizon")
    axis.set_ylabel("J_common macro (lower better)")
    axis.set_title(f"Fold error growth ({fold_dir.name})")
    axis.legend()
    fig.tight_layout()
    path = out_path / f"fold_{fold_dir.name}_error_growth.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))
    return figures


def plot_d5_hard_windows(fold_dir: Path, out_path: Path) -> list[str]:
    plt = _plt()
    figures = []
    for variant_dir in sorted(fold_dir.glob("*")):
        rows_csv = variant_dir / "rows_best.csv"
        if not variant_dir.is_dir() or not rows_csv.exists():
            continue
        rows = [r for r in csv.DictReader(open(rows_csv, encoding="utf-8-sig")) if r["scenario"] == "D5" and int(r["horizon"]) == 20]
        if not rows:
            continue
        starts = sorted({int(r["window_start"]) for r in rows})
        fig, axis = plt.subplots(figsize=(7, 4))
        for start in starts:
            values = [float(r["j_common"]) for r in rows if int(r["window_start"]) == start]
            axis.bar(str(start), np.mean(values))
        axis.set_xlabel("D5 window_start")
        axis.set_ylabel("J20 mean")
        axis.set_title(f"D5 windows ({variant_dir.name})")
        fig.tight_layout()
        path = out_path / f"fold_{fold_dir.name}_{variant_dir.name}_d5.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(str(path))
    return figures


def plot_all(f4_root: Path, out_root: Path) -> None:
    for fold_dir in sorted(f4_root.glob("fold_*")):
        plot_fold_summary(fold_dir, out_root)
        plot_d5_hard_windows(fold_dir, out_root)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--f4-root", required=True)
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args()
    plot_all(Path(args.f4_root), Path(args.out_root))

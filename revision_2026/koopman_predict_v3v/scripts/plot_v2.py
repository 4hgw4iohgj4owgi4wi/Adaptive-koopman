from __future__ import annotations

"""v2 plotting: main tables, worst trajectories, oracle/permutation/stability
summary figures.  Every figure keeps its source CSV and the generating script
in the run directory; a figure manifest records SHA256 for each artifact."""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts_v2 import file_sha256  # noqa: E402


def _matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_p0(stage_root: Path, model_summary_csv: Path) -> list[str]:
    plt = _matplotlib()
    rows = list(csv.DictReader(open(model_summary_csv, encoding="utf-8-sig")))
    figures = []
    labels = []
    values = []
    for row in sorted(rows, key=lambda item: item["config_key"]):
        labels.append(row["config_key"].replace("M0_FIXED_LINEAR|", "M0|").replace("M1_LOWRANK_BILINEAR|", "M1|"))
        values.append(float(row["j_common_macro"]))
    fig, axis = plt.subplots(figsize=(12, 5))
    axis.bar(np.arange(len(labels)), values, color="#3b82f6")
    axis.set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
    axis.set_ylabel("20-step macro J_common")
    axis.set_title("V2 recomputed N6 model/interface matrix (lower is better)")
    fig.tight_layout()
    path = stage_root / "p0_model_matrix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))
    return figures


def plot_p1(stage_root: Path, by_regime_csv: Path, permutation_csv: Path) -> list[str]:
    plt = _matplotlib()
    figures = []
    rows = list(csv.DictReader(open(by_regime_csv, encoding="utf-8-sig")))
    horizon_rows = [row for row in rows if row["horizon"] == "20"]
    scenarios = sorted({row["scenario"] for row in horizon_rows})
    scenario_means = {
        scenario: float(np.mean([float(row["j_common"]) for row in horizon_rows if row["scenario"] == scenario]))
        for scenario in scenarios
    }
    fig, axis = plt.subplots(figsize=(10, 4))
    axis.bar(list(scenario_means), list(scenario_means.values()), color="#f59e0b")
    axis.set_ylabel("20-step J_common (S0)")
    axis.set_title("P1: S0 J20 by scenario (worst: D7/D9/D10)")
    fig.tight_layout()
    path = stage_root / "p1_scenario_j20.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    perm_rows = list(csv.DictReader(open(permutation_csv, encoding="utf-8-sig")))
    if perm_rows:
        labels = [row["group"] for row in perm_rows]
        degradation = [float(row["j20_degradation_percent"]) for row in perm_rows]
        fig, axis = plt.subplots(figsize=(8, 4))
        axis.bar(labels, degradation, color="#ef4444")
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_ylabel("J20 degradation after group permutation (%)")
        axis.set_title("P1: causal group permutation cost (S0)")
        fig.tight_layout()
        path = stage_root / "p1_causal_permutation.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(str(path))
    return figures


def plot_p2(stage_root: Path, comparison_json: Path) -> list[str]:
    plt = _matplotlib()
    comparison = json.loads(Path(comparison_json).read_text(encoding="utf-8"))
    scenarios = comparison["scenario_improvement_percent"]
    fig, axis = plt.subplots(figsize=(10, 4))
    axis.bar(list(scenarios), list(scenarios.values()), color="#10b981")
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_ylabel("20-step J_common improvement vs S0 (%)")
    axis.set_title("P2: oracle expert upper bound by scenario")
    fig.tight_layout()
    path = stage_root / "p2_oracle_by_scenario.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_p3(stage_root: Path, diagnosis_json: Path) -> list[str]:
    plt = _matplotlib()
    diagnosis = json.loads(Path(diagnosis_json).read_text(encoding="utf-8"))
    figures = []
    b1_choices = diagnosis.get("B1", {}).get("ridge_choices", [])
    if b1_choices:
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.plot([float(row["ridge"]) for row in b1_choices], [float(row["j20_macro"]) for row in b1_choices], marker="o")
        axis.set_xscale("log")
        axis.set_xlabel("ridge")
        axis.set_ylabel("validation J20 macro")
        axis.set_title("P3: full bilinear ridge sweep (B1)")
        fig.tight_layout()
        path = stage_root / "p3_b1_ridge_sweep.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(str(path))
    growth = diagnosis.get("B1", {}).get("mechanism", {}).get("error_growth", {})
    if growth:
        horizons = sorted(growth, key=int)
        candidate = [growth[h]["candidate"] for h in horizons]
        s0 = [growth[h]["s0"] for h in horizons]
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.plot(horizons, candidate, marker="o", label="B1 full bilinear")
        axis.plot(horizons, s0, marker="s", label="S0")
        axis.set_xlabel("horizon")
        axis.set_ylabel("J_common macro")
        axis.set_title("P3: error growth 1->5->10->20")
        axis.legend()
        fig.tight_layout()
        path = stage_root / "p3_error_growth.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        figures.append(str(path))
    return figures


def write_figure_manifest(stage_root: Path, figures: list[str]) -> None:
    manifest = {"script": "scripts/plot_v2.py", "figures": []}
    for figure in figures:
        path = Path(figure)
        manifest["figures"].append({"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size})
    (stage_root / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def plot_all(run_root: Path) -> None:
    p0 = run_root / "p0"
    p1 = run_root / "p1"
    p2 = run_root / "p2"
    p3 = run_root / "p3"
    figures = []
    if (p0 / "model_summary_v2.csv").exists():
        figures += plot_p0(p0, p0 / "model_summary_v2.csv")
    if (p1 / "residual_by_regime.csv").exists():
        figures += plot_p1(p1, p1 / "residual_by_regime.csv", p1 / "causal_permutation.csv")
    if (p2 / "comparison.json").exists():
        figures += plot_p2(p2, p2 / "comparison.json")
    if (p3 / "diagnosis.json").exists():
        figures += plot_p3(p3, p3 / "diagnosis.json")
    for stage in ("p0", "p1", "p2", "p3"):
        stage_dir = run_root / stage
        if stage_dir.exists():
            write_figure_manifest(stage_dir, [f for f in figures if stage in f])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    plot_all(Path(args.run_root))

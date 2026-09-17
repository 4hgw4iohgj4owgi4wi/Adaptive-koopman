"""v3 plotting: error growth, scenario heatmap, D5 transition, forces,
damped-mode evidence, stress rollouts and seed distributions."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

# Anaconda MKL + PyTorch duplicate OpenMP runtime guard
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts_v2 import file_sha256  # noqa: E402


def _matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_error_growth(stage_root: Path, csv_paths: list[tuple[str, Path]]) -> list[str]:
    plt = _matplotlib()
    fig, axis = plt.subplots(figsize=(7, 4))
    for label, path in csv_paths:
        if not path.exists():
            continue
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        horizons = sorted({int(row["horizon"]) for row in rows})
        values = [np.mean([float(row["j_common"]) for row in rows if int(row["horizon"]) == h]) for h in horizons]
        axis.plot([str(h) for h in horizons], values, marker="o", label=label)
    axis.set_xlabel("horizon")
    axis.set_ylabel("J_common macro")
    axis.set_title("Error growth 1/5/10/20")
    axis.legend()
    fig.tight_layout()
    path = stage_root / "error_growth.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_scenario_heatmap(stage_root: Path, candidate_csv: Path, s0_csv: Path) -> list[str]:
    plt = _matplotlib()
    if not candidate_csv.exists() or not s0_csv.exists():
        return []
    candidate = list(csv.DictReader(open(candidate_csv, encoding="utf-8-sig")))
    s0 = list(csv.DictReader(open(s0_csv, encoding="utf-8-sig")))
    scenarios = sorted({row["scenario"] for row in candidate if int(row["horizon"]) == 20})
    improvements = []
    labels = []
    for scenario in scenarios:
        cand = np.mean([float(row["j_common"]) for row in candidate if int(row["horizon"]) == 20 and row["scenario"] == scenario])
        base = np.mean([float(row["j_common"]) for row in s0 if int(row["horizon"]) == 20 and row["scenario"] == scenario])
        improvements.append(100.0 * (base - cand) / max(abs(base), 1e-12))
        labels.append(scenario)
    fig, axis = plt.subplots(figsize=(10, 3))
    colors = ["#10b981" if value >= 0 else "#ef4444" for value in improvements]
    axis.bar(labels, improvements, color=colors)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_ylabel("J20 improvement vs S0 (%)")
    axis.set_title("D0-D11 improvement heatmap")
    fig.tight_layout()
    path = stage_root / "scenario_heatmap.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_d5_transition(stage_root: Path, rows_csv: Path) -> list[str]:
    plt = _matplotlib()
    if not rows_csv.exists():
        return []
    rows = list(csv.DictReader(open(rows_csv, encoding="utf-8-sig")))
    d5 = [row for row in rows if row["scenario"] == "D5" and int(row["horizon"]) == 20]
    if not d5:
        return []
    starts = sorted({int(row["window_start"]) for row in d5})
    means = [np.mean([float(row["j_common"]) for row in d5 if int(row["window_start"]) == start]) for start in starts]
    fig, axis = plt.subplots(figsize=(7, 4))
    axis.bar([str(start) for start in starts], means, color="#f59e0b")
    axis.set_xlabel("window_start (2.0-2.4 s is 100/120)")
    axis.set_ylabel("J20 mean")
    axis.set_title("D5 transition windows")
    fig.tight_layout()
    path = stage_root / "d5_transition.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_force_internal(stage_root: Path, rows_csv: Path) -> list[str]:
    plt = _matplotlib()
    if not rows_csv.exists():
        return []
    rows = list(csv.DictReader(open(rows_csv, encoding="utf-8-sig")))
    force = [float(row["force8_rmse_n"]) for row in rows if int(row["horizon"]) == 20]
    internal = [float(row["internal8_rmse_n"]) for row in rows if int(row["horizon"]) == 20]
    if not force:
        return []
    fig, axis = plt.subplots(figsize=(7, 4))
    axis.boxplot([force, internal], labels=["force8", "internal8"])
    axis.set_ylabel("RMSE (N)")
    axis.set_title("Force and internal-force 20-step RMSE distribution")
    fig.tight_layout()
    path = stage_root / "force_internal.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_modes(stage_root: Path, spectrum_json: Path) -> list[str]:
    plt = _matplotlib()
    if not spectrum_json.exists():
        return []
    spectrum = json.loads(Path(spectrum_json).read_text(encoding="utf-8"))
    radii = spectrum.get("per_pair_radius")
    if not radii:
        return []
    fig, axis = plt.subplots(figsize=(7, 4))
    axis.plot(np.arange(1, len(radii) + 1), radii, marker="o")
    axis.axhline(0.995, color="red", linestyle="--", label="0.995 bound")
    axis.set_xlabel("mode pair")
    axis.set_ylabel("radius r_j")
    axis.set_title("Damped-mode radii")
    axis.legend()
    fig.tight_layout()
    path = stage_root / "damped_modes.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def plot_stress(stage_root: Path, stress_json: Path) -> list[str]:
    plt = _matplotlib()
    if not stress_json.exists():
        return []
    stress = json.loads(Path(stress_json).read_text(encoding="utf-8"))
    rows = stress.get("rows", [])
    if not rows:
        return []
    fig, axis = plt.subplots(figsize=(7, 4))
    for horizon in sorted({row["horizon"] for row in rows}):
        values = [row["state47_rmse_si"] for row in rows if row["horizon"] == horizon]
        axis.hist(values, bins=20, alpha=0.5, label=f"{horizon} steps")
    axis.set_xlabel("state47 RMSE (SI)")
    axis.set_title("D5 40/80-step stress rollout")
    axis.legend()
    fig.tight_layout()
    path = stage_root / "d5_stress.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def write_figure_manifest(stage_root: Path, figures: list[str]) -> None:
    manifest = {"script": "scripts/plot_v3.py", "figures": []}
    for figure in figures:
        path = Path(figure)
        manifest["figures"].append({"path": str(path), "sha256": file_sha256(path), "bytes": path.stat().st_size})
    (stage_root / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def plot_all(run_root: Path) -> None:
    figures = []
    p5c = run_root / "p5c"
    p5b = run_root / "p5b"
    if p5b.exists():
        for model in ("C16", "C32"):
            csv_path = p5b / f"cv_{model}.csv"
            if csv_path.exists():
                figures += plot_error_growth(p5b, [(model, csv_path)])
    if p5c.exists():
        candidates = sorted(p5c.glob("rows_validation_*_*.csv"))
        s0 = p5c / "s0_rows_validation.csv"
        if candidates:
            combined = p5c / "rows_validation_combined.csv"
            if not combined.exists():
                with open(combined, "w", newline="", encoding="utf-8-sig") as out:
                    first = True
                    for path in candidates:
                        with open(path, encoding="utf-8-sig") as source:
                            content = source.read()
                            if not first:
                                content = "\n".join(content.splitlines()[1:]) + "\n"
                            out.write(content)
                            first = False
            figures += plot_error_growth(p5c, [("GDM-RK", combined)])
            figures += plot_scenario_heatmap(p5c, combined, s0) if s0.exists() else []
            figures += plot_d5_transition(p5c, combined)
            figures += plot_force_internal(p5c, combined)
        figures += plot_modes(p5c, p5c / "d5_stress.json" if (p5c / "d5_stress.json").exists() else run_root / "p5a" / "spectrum.json")
        figures += plot_stress(p5c, p5c / "d5_stress.json")
    for stage in ("s0", "s1", "r0", "p5a", "p5b", "p5c"):
        stage_dir = run_root / stage
        if stage_dir.exists():
            write_figure_manifest(stage_dir, [f for f in figures if stage in f])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    args = parser.parse_args()
    plot_all(Path(args.run_root))

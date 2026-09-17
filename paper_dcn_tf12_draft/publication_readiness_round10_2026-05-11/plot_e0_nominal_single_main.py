from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
STAGE = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11" / "e0_n20_nominal_single_fault_main_comparison_merged"
SUMMARY = STAGE / "data" / "tf14_remaining_summary.csv"
FIG_DIR = STAGE / "figures"


SCENARIOS = ["sine_nominal_clean", "sine_single_fault_v2"]
SCENARIO_LABELS = {
    "sine_nominal_clean": "nominal clean",
    "sine_single_fault_v2": "single fault",
}
METHODS = ["baseline", "tf14_main", "tf14_phase_role", "zoh_consensus_surrogate"]
LABELS = {
    "baseline": "AKE-M",
    "tf14_main": "TF14-main",
    "tf14_phase_role": "TF14-full",
    "zoh_consensus_surrogate": "ZOH",
}
COLORS = {
    "baseline": "#6C757D",
    "tf14_main": "#D55E00",
    "tf14_phase_role": "#009E73",
    "zoh_consensus_surrogate": "#222222",
}


def read_rows() -> list[dict[str, str]]:
    with SUMMARY.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def f(row: dict[str, str] | None, key: str) -> float:
    if row is None:
        return float("nan")
    try:
        return float(row.get(key, "nan"))
    except Exception:
        return float("nan")


def save(fig: plt.Figure, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ["png", "pdf", "svg"]:
        fig.savefig(FIG_DIR / f"{name}.{ext}", dpi=220, bbox_inches="tight")


def main() -> None:
    rows = read_rows()
    by_key = {(r["scenario"], r["method"]): r for r in rows}

    panels = [
        ("rmse_lat_mean_mean", "lateral RMSE [m]"),
        ("rmse_long_mean_mean", "longitudinal RMSE [m]"),
        ("connection_max_utilization_mean", "connection max utilization"),
        ("success_mean", "success rate"),
        ("certificate_ok_ratio_mean", "certificate ok ratio"),
        ("force_norm_peak_mean", "force peak [N]"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    x = np.arange(len(SCENARIOS))
    width = 0.18
    for ax, (metric, title) in zip(axes.ravel(), panels):
        for j, method in enumerate(METHODS):
            vals = [f(by_key.get((scenario, method)), metric) for scenario in SCENARIOS]
            offset = (j - (len(METHODS) - 1) / 2.0) * width
            ax.bar(x + offset, vals, width=width, color=COLORS[method], label=LABELS[method])
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_LABELS[s] for s in SCENARIOS], rotation=10)
        ax.set_title(title, fontsize=12)
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend(loc="best", fontsize=8)
    fig.suptitle("E0 nominal and single-fault main comparison (paired n=20 when complete)", fontsize=15)
    save(fig, "R0_nominal_single_main_comparison_summary")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    metrics = [
        ("rmse_lat_mean_mean", "lat RMSE"),
        ("rmse_long_mean_mean", "long RMSE"),
        ("connection_max_utilization_mean", "conn util"),
        ("force_norm_peak_mean", "force peak"),
    ]
    for ax, scenario in zip(axes, SCENARIOS):
        baseline = by_key.get((scenario, "baseline"))
        full = by_key.get((scenario, "tf14_phase_role"))
        deltas = []
        for key, _label in metrics:
            b = f(baseline, key)
            v = f(full, key)
            deltas.append((v - b) / abs(b) * 100 if b and np.isfinite(b) else np.nan)
        colors = ["#009E73" if v <= 0 else "#B00020" for v in deltas]
        ax.bar([label for _key, label in metrics], deltas, color=colors)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(SCENARIO_LABELS[scenario])
        ax.set_ylabel("TF14-full vs AKE-M [%]")
        ax.tick_params(axis="x", rotation=12)
        ax.grid(axis="y", alpha=0.25)
        for i, v in enumerate(deltas):
            if np.isfinite(v):
                ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    save(fig, "R0_nominal_single_relative_change")
    plt.close(fig)
    print(FIG_DIR)


if __name__ == "__main__":
    main()

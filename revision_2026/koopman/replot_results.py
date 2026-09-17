"""Presentation-only replot from frozen CSV results.

No metrics, models, gates, or CSV values are modified.  Extreme failed-model
values are clipped or isolated so that the successful-model comparisons remain
visible; exact values stay in the accompanying CSV files.
"""

from pathlib import Path
import csv
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman\compare")


def read(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def heatmap():
    rows = read("scenario_method_heatmap.csv")
    methods = list(dict.fromkeys(row["method"] for row in rows))
    scenarios = list(dict.fromkeys(row["scenario"] for row in rows))
    exact = np.full((len(methods), len(scenarios)), np.nan)
    for row in rows:
        exact[methods.index(row["method"]), scenarios.index(row["scenario"])] = float(row["relative_improvement_vs_K1_percent"])
    shown = np.clip(exact, -100, 100)
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    image = ax.imshow(shown, aspect="auto", cmap="RdYlGn", vmin=-100, vmax=100)
    ax.set_xticks(range(len(scenarios)), scenarios); ax.set_yticks(range(len(methods)), methods)
    ax.set_title("Relative J_pred improvement vs K1 (%) — display clipped at ±100; E9 development-only")
    for i in range(len(methods)):
        for j in range(len(scenarios)):
            value = exact[i, j]
            if not math.isfinite(value): continue
            label = "NUM FAIL" if abs(value) > 1000 else f"{value:.1f}"
            color = "white" if abs(shown[i, j]) > 60 else "black"
            ax.text(j, i, label, ha="center", va="center", fontsize=7, color=color)
    fig.colorbar(image, ax=ax, label="positive favors method; exact values in CSV")
    fig.tight_layout(); fig.savefig(ROOT / "scenario_method_heatmap.png", dpi=220); plt.close(fig)


def horizon():
    rows = read("horizon_state_force.csv")
    methods = list(dict.fromkeys(row["method"] for row in rows))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.7), sharex=True)
    for method in methods:
        values = sorted((row for row in rows if row["method"] == method), key=lambda row: int(row["horizon"]))
        for ax, metric in zip(axes, ("state", "force", "load")):
            y = np.asarray([max(float(row[metric]), 1.0e-6) for row in values])
            ax.plot([int(row["horizon"]) for row in values], y, label=method, lw=1.5)
            ax.set_yscale("log"); ax.set(title=metric, xlabel="teacher-free horizon", ylabel="NRMSE (log scale)")
            ax.grid(True, which="both", alpha=.22)
    axes[0].legend(fontsize=7, ncol=2)
    fig.suptitle("Horizon errors; log scale retains the K5-bilinear numerical-failure curve without hiding other methods")
    fig.tight_layout(); fig.savefig(ROOT / "horizon_state_force.png", dpi=220); plt.close(fig)


def pareto():
    rows = read("accuracy_cost_pareto.csv")
    fig, ax = plt.subplots(figsize=(8.2, 5.5))
    for row in rows:
        x = float(row["parameter_count"]); y = max(float(row["J_pred"]), 1.0e-8); latency = float(row["rollout20_p99_ms"])
        marker = "x" if row["model"] == "K5-bilinear" else "o"
        ax.scatter(x, y, s=65, marker=marker)
        ax.annotate(row["model"], (x, y), xytext=(4, 3), textcoords="offset points", fontsize=8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set(xlabel="parameter count (log)", ylabel="confirm macro J_pred (log)", title="Accuracy / model cost / rollout latency (exact values in CSV)")
    ax.grid(True, which="both", alpha=.25); fig.tight_layout(); fig.savefig(ROOT / "accuracy_cost_pareto.png", dpi=220); plt.close(fig)


def ood():
    rows = read("ood_network_robustness.csv")
    methods = [method for method in dict.fromkeys(row["method"] for row in rows) if method != "K5-bilinear"]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), sharey=True)
    for ax, scenario in zip(axes, ("E7", "E8")):
        lookup = {row["method"]: float(row["relative_improvement_vs_K1_percent"]) for row in rows if row["scenario"] == scenario}
        values = [lookup[method] for method in methods]
        colors = ["tab:green" if value >= 0 else "tab:orange" for value in values]
        ax.bar(methods, values, color=colors); ax.axhline(0, color="black", lw=.7)
        ax.tick_params(axis="x", rotation=40); ax.set(title=scenario, ylabel="improvement vs K1 (%)")
        ax.grid(True, axis="y", alpha=.25)
        ax.text(.98, .04, "K5-bilinear: numerical failure\n(exact value in CSV)", transform=ax.transAxes, ha="right", va="bottom", color="darkred", fontsize=8)
    fig.suptitle("Out-of-distribution and network robustness; failed K5-bilinear isolated for readability")
    fig.tight_layout(); fig.savefig(ROOT / "ood_network_robustness.png", dpi=220); plt.close(fig)


def learning():
    path = ROOT / "t3" / "learning_curves_k0_k4.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    methods = list(dict.fromkeys(row["method"] for row in rows))
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    for method in methods:
        xs, medians, lows, highs = [], [], [], []
        for fraction in (.10, .25, .50, 1.00):
            values = [float(row["validation_macro_J_pred"]) for row in rows if row["method"] == method and abs(float(row["fraction"]) - fraction) < 1e-8]
            if not values: continue
            xs.append(fraction); medians.append(np.median(values)); lows.append(np.quantile(values,.25)); highs.append(np.quantile(values,.75))
        ax.plot(xs, medians, marker="o", label=method); ax.fill_between(xs, lows, highs, alpha=.13)
    ax.set_yscale("log"); ax.set(xlabel="fraction of stratified train trajectories", ylabel="validation macro J_pred (log)", title="Nested data-size learning curves (median/IQR over 5 subsets)")
    ax.grid(True, which="both", alpha=.23); ax.legend(); fig.tight_layout(); fig.savefig(ROOT / "t3" / "learning_curves_k0_k4.png", dpi=220); plt.close(fig)


if __name__ == "__main__":
    heatmap(); horizon(); pareto(); ood(); learning()
    print("replotted 5 presentation-limited figures from frozen CSVs")

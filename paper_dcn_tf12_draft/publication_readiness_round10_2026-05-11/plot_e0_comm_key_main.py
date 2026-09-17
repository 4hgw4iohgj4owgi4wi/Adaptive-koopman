from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
STAGE = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11" / "e0_n20_comm_noise_key_main_comparison_merged"
SUMMARY = STAGE / "data" / "tf14_remaining_summary.csv"
FIG_DIR = STAGE / "figures"


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


def f(row: dict[str, str], key: str) -> float:
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
    methods = ["baseline", "tf14_main", "tf14_phase_role", "zoh_consensus_surrogate"]
    by_method = {r["method"]: r for r in rows}

    fig, axes = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    panels = [
        ("rmse_lat_mean_mean", "lateral RMSE [m]"),
        ("rmse_long_mean_mean", "longitudinal RMSE [m]"),
        ("connection_max_utilization_mean", "connection max utilization"),
        ("success_mean", "success rate"),
        ("certificate_ok_ratio_mean", "certificate ok ratio"),
        ("force_norm_peak_mean", "force peak [N]"),
    ]
    for ax, (key, title) in zip(axes.ravel(), panels):
        vals = [f(by_method[m], key) for m in methods]
        ax.bar([LABELS[m] for m in methods], vals, color=[COLORS[m] for m in methods])
        ax.set_title(title, fontsize=12)
        ax.tick_params(axis="x", rotation=18, labelsize=9)
        ax.tick_params(axis="y", labelsize=9)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("E0 high-communication-noise main comparison (paired n=20)", fontsize=15)
    save(fig, "R0_comm_key_main_comparison_summary")
    plt.close(fig)

    baseline = by_method["baseline"]
    full = by_method["tf14_phase_role"]
    metrics = [
        ("rmse_lat_mean_mean", "lat RMSE"),
        ("rmse_long_mean_mean", "long RMSE"),
        ("connection_max_utilization_mean", "conn util"),
        ("force_norm_peak_mean", "force peak"),
    ]
    deltas = []
    for key, _label in metrics:
        b = f(baseline, key)
        v = f(full, key)
        deltas.append((v - b) / abs(b) * 100 if b else 0.0)
    fig, ax = plt.subplots(figsize=(7, 3.8))
    colors = ["#009E73" if v <= 0 else "#B00020" for v in deltas]
    ax.bar([label for _key, label in metrics], deltas, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("TF14-full vs AKE-M [%]")
    ax.set_title("E0 high-communication-noise relative change (negative is lower)")
    ax.grid(axis="y", alpha=0.25)
    for i, v in enumerate(deltas):
        ax.text(i, v, f"{v:.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    save(fig, "R0_comm_key_relative_change")
    plt.close(fig)

    print(FIG_DIR)


if __name__ == "__main__":
    main()

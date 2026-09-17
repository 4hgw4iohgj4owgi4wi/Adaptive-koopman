from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
STAGE = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11" / "e2_n20_mixed_fault_ablation_merged"
SUMMARY = STAGE / "data" / "tf14_remaining_summary.csv"
FIG_DIR = STAGE / "figures"


LABELS = {
    "full_tf14": "TF14-full",
    "no_bilinear": "no bilinear",
    "no_stable_projection": "no stable proj.",
    "no_online_adapt": "no online adapt",
    "no_comm_aware": "no comm-aware",
    "no_delay_compensation": "no delay comp.",
    "no_fdi": "no FDI",
    "no_ftc_switching": "no FTC switch",
    "no_phase_role": "no phase-role",
    "no_realtime_scheduler": "no RT scheduler",
    "no_ppc_progress_guard": "no PPC/progress",
    "zoh_consensus_surrogate": "ZOH surrogate",
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
    by_method = {r["method"]: r for r in rows}
    full = by_method["full_tf14"]
    methods = [
        "no_bilinear",
        "no_stable_projection",
        "no_online_adapt",
        "no_comm_aware",
        "no_delay_compensation",
        "no_fdi",
        "no_ftc_switching",
        "no_phase_role",
        "no_realtime_scheduler",
        "no_ppc_progress_guard",
        "zoh_consensus_surrogate",
    ]
    metrics = [
        ("rmse_lat_mean_mean", "lat RMSE", "rel"),
        ("rmse_long_mean_mean", "long RMSE", "rel"),
        ("connection_max_utilization_mean", "conn util", "rel"),
        ("force_norm_peak_mean", "force peak", "rel"),
        ("success_mean", "success loss", "loss"),
    ]
    mat = []
    for method in methods:
        row = by_method[method]
        vals = []
        for key, _label, mode in metrics:
            base = f(full, key)
            val = f(row, key)
            if mode == "loss":
                vals.append(base - val)
            elif base == 0 or base != base or val != val:
                vals.append(np.nan)
            else:
                vals.append((val - base) / abs(base))
        mat.append(vals)
    arr = np.array(mat, dtype=float)

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    vmax = np.nanmax(np.abs(arr[:, :4]))
    vmax = max(vmax, 1.0)
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels([m[1] for m in metrics], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels([LABELS[m] for m in methods])
    ax.set_title("E2 module ablation, positive = worse than TF14-full (n=20)")
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            value = arr[i, j]
            if value != value:
                txt = "-"
            elif metrics[j][2] == "loss":
                txt = f"{value:.2f}"
            else:
                txt = f"{value*100:.0f}%"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    save(fig, "R2_round10_module_ablation_heatmap")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    plot_methods = ["full_tf14", "no_comm_aware", "no_ppc_progress_guard", "zoh_consensus_surrogate"]
    colors = ["#009E73", "#E69F00", "#B00020", "#222222"]
    for ax, key, title in [
        (axes[0], "rmse_long_mean_mean", "longitudinal RMSE"),
        (axes[1], "connection_max_utilization_mean", "connection max utilization"),
        (axes[2], "success_mean", "success rate"),
    ]:
        vals = [f(by_method[m], key) for m in plot_methods]
        ax.bar([LABELS[m] for m in plot_methods], vals, color=colors)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("E2 representative module effects (mixed fault/noise, n=20)")
    save(fig, "R2_round10_key_module_effects")
    plt.close(fig)

    print(FIG_DIR)


if __name__ == "__main__":
    main()

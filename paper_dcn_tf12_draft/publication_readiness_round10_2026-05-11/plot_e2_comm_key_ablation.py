from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
STAGE = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11" / "e2_n20_comm_noise_key_ablation_merged"
SUMMARY = STAGE / "data" / "tf14_remaining_summary.csv"
FIG_DIR = STAGE / "figures"


LABELS = {
    "full_tf14": "TF14-full",
    "no_comm_aware": "no comm-aware",
    "no_delay_compensation": "no delay comp.",
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


def rel_delta(value: float, base: float) -> float:
    if base == 0 or base != base or value != value:
        return np.nan
    return (value - base) / abs(base)


def main() -> None:
    rows = read_rows()
    by_method = {r["method"]: r for r in rows}
    methods = ["full_tf14", "no_comm_aware", "no_delay_compensation", "zoh_consensus_surrogate"]
    full = by_method["full_tf14"]

    metrics = [
        ("rmse_lat_mean_mean", "lat RMSE", "rel"),
        ("rmse_long_mean_mean", "long RMSE", "rel"),
        ("connection_max_utilization_mean", "conn util", "rel"),
        ("certificate_ok_ratio_mean", "cert loss", "loss_from_one"),
        ("success_mean", "success loss", "loss"),
    ]
    arr = []
    for method in methods:
        row = by_method[method]
        vals = []
        for key, _label, mode in metrics:
            val = f(row, key)
            base = f(full, key)
            if method == "full_tf14":
                vals.append(0.0)
            elif mode == "rel":
                vals.append(rel_delta(val, base))
            elif mode == "loss_from_one":
                vals.append(base - val)
            else:
                vals.append(base - val)
        arr.append(vals)
    arr_np = np.array(arr, dtype=float)

    fig, ax = plt.subplots(figsize=(7.8, 3.8))
    vmax = np.nanmax(np.abs(arr_np[:, :3]))
    vmax = max(vmax, 1.0)
    im = ax.imshow(arr_np, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels([m[1] for m in metrics], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels([LABELS[m] for m in methods])
    ax.set_title("E2 communication-key ablation, positive = worse than TF14-full (n=20)")
    for i in range(arr_np.shape[0]):
        for j in range(arr_np.shape[1]):
            value = arr_np[i, j]
            if value != value:
                txt = "-"
            elif metrics[j][2] == "rel":
                txt = f"{value*100:.0f}%"
            else:
                txt = f"{value:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)
    save(fig, "R2_comm_key_ablation_heatmap")
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(13, 3.5))
    colors = ["#009E73", "#E69F00", "#17BECF", "#222222"]
    bar_metrics = [
        ("rmse_long_mean_mean", "longitudinal RMSE"),
        ("connection_max_utilization_mean", "connection utilization"),
        ("certificate_ok_ratio_mean", "certificate ok ratio"),
        ("success_mean", "success rate"),
    ]
    for ax, (key, title) in zip(axes, bar_metrics):
        vals = [f(by_method[m], key) for m in methods]
        ax.bar([LABELS[m] for m in methods], vals, color=colors)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("E2 high-communication-noise key ablation (n=20)")
    save(fig, "R2_comm_key_effects")
    plt.close(fig)

    print(FIG_DIR)


if __name__ == "__main__":
    main()

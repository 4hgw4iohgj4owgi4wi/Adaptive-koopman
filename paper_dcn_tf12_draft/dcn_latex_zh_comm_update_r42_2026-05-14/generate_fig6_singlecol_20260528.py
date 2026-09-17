from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LATEX_DIR = Path(__file__).resolve().parent
DATA_CSV = (
    ROOT
    / "paper_dcn_tf12_draft"
    / "hairpin_5mps_global_tune_base_20260513"
    / "data"
    / "diagnostics"
    / "E8_HAIRPIN_5MPS"
    / "seed_2026"
    / "hairpin_pressure_v5p0_tf14_full"
    / "control_spread.csv"
)
FIG_DIR = LATEX_DIR / "figures"
OUT_STEM = "fig_nrkdcc_comm_mechanism_singlecol_20260528"


def _series(df: pd.DataFrame, name: str, default: float = 0.0) -> np.ndarray:
    if name not in df:
        return np.full(len(df), default, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").fillna(default).to_numpy(dtype=float)


def _legend(ax: plt.Axes, ncol: int = 2) -> None:
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.24),
        ncol=ncol,
        fontsize=5.9,
        frameon=True,
        facecolor="white",
        edgecolor="#B7C3D0",
        framealpha=0.95,
        borderpad=0.25,
        handlelength=1.6,
        columnspacing=0.8,
    )


def _style(ax: plt.Axes) -> None:
    ax.grid(True, color="#D9E2EC", linewidth=0.5, alpha=0.75)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8AA0B6")
    ax.spines["bottom"].set_color("#8AA0B6")
    ax.tick_params(labelsize=6.2, colors="#334E68", width=0.45, length=2.5)


def main() -> None:
    if not DATA_CSV.exists():
        raise FileNotFoundError(DATA_CSV)

    df = pd.read_csv(DATA_CSV)
    t = np.arange(len(df), dtype=float) * 0.02

    delay = _series(df, "comm_mean_delay_steps")
    loss = _series(df, "comm_loss_ratio")
    quality = _series(df, "comm_quality_global", 1.0)
    tighten = _series(df, "comm_tighten_frac")
    consensus = _series(df, "comm_consensus_blend_mean")
    delta_spread = _series(df, "delta_spread")
    ax_spread = _series(df, "ax_spread")
    lateral_priority = _series(df, "critical_lateral_priority_active")
    speed_cap = _series(df, "high_curvature_team_speed_cap_active")
    fault = _series(df, "fault_active")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.titlesize": 7.2,
            "axes.labelsize": 6.5,
        }
    )

    fig, axes = plt.subplots(4, 1, figsize=(3.45, 6.25), dpi=260, sharex=True)
    colors = {
        "blue": "#2F6FBB",
        "red": "#C15B3D",
        "green": "#2E8B57",
        "orange": "#D9822B",
        "purple": "#7B61A8",
        "gray": "#5E6C84",
    }

    axes[0].plot(t, delay, color=colors["blue"], lw=1.05, label="mean delay")
    axes[0].plot(t, loss, color=colors["red"], lw=1.05, label="packet loss")
    axes[0].set_ylabel("steps / ratio")
    _legend(axes[0], ncol=2)

    axes[1].plot(t, quality, color=colors["green"], lw=1.05, label="link quality")
    axes[1].plot(t, tighten, color=colors["orange"], lw=1.05, label="constraint tightening")
    axes[1].plot(t, consensus, color=colors["purple"], lw=1.0, label="consensus blend")
    axes[1].set_ylabel("ratio")
    axes[1].set_ylim(-0.05, 1.05)
    _legend(axes[1], ncol=2)

    axes[2].plot(t, delta_spread, color=colors["blue"], lw=1.05, label=r"$\delta$ spread")
    axes[2].plot(t, ax_spread, color=colors["orange"], lw=1.05, label=r"$a_x$ spread")
    axes[2].set_ylabel("input range")
    _legend(axes[2], ncol=2)

    axes[3].step(t, lateral_priority, where="post", color=colors["purple"], lw=1.0, label="lateral priority")
    axes[3].step(t, speed_cap, where="post", color=colors["green"], lw=1.0, label="speed cap")
    axes[3].step(t, fault, where="post", color=colors["red"], lw=0.95, label="fault flag")
    axes[3].set_ylabel("active")
    axes[3].set_ylim(-0.08, 1.08)
    _legend(axes[3], ncol=3)

    for ax in axes:
        _style(ax)
        ax.set_xlim(t[0], t[-1])
    axes[-1].set_xlabel("time [s]", fontsize=6.5)

    fig.subplots_adjust(left=0.155, right=0.985, top=0.965, bottom=0.075, hspace=0.72)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = FIG_DIR / f"{OUT_STEM}.pdf"
    out_png = FIG_DIR / f"{OUT_STEM}.png"
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    summary = {
        "source": str(DATA_CSV),
        "rows": int(len(df)),
        "comm_quality_min": float(np.nanmin(quality)),
        "comm_delay_max": float(np.nanmax(delay)),
        "packet_loss_max": float(np.nanmax(loss)),
        "tightening_max": float(np.nanmax(tighten)),
        "output_pdf": str(out_pdf),
        "output_png": str(out_png),
    }
    (FIG_DIR / f"{OUT_STEM}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

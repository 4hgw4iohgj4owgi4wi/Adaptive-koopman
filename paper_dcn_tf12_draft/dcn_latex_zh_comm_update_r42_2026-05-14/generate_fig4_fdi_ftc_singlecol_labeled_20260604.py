from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LATEX_DIR = Path(__file__).resolve().parent
DATA_DIR = (
    ROOT
    / "tf14_remaining_experiments_20260509"
    / "data"
    / "diagnostics"
    / "E0"
    / "seed_2026"
    / "dlc_mixed_fault_noise_tf14_phase_role"
)
FIG_DIR = LATEX_DIR / "figures"
OUT_STEM = "fig_nrkdcc_fdi_ftc_timeline_singlecol_labeled_20260604"
DT = 0.02


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _as_float(df: pd.DataFrame, name: str, default: float = 0.0) -> np.ndarray:
    if name not in df:
        return np.full(len(df), default, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").fillna(default).to_numpy(dtype=float)


def _as_bool_series(values: pd.Series) -> np.ndarray:
    return values.astype(str).str.lower().isin(["1", "true", "yes", "y"]).to_numpy(dtype=float)


def _style(ax: plt.Axes, *, zero: bool = False) -> None:
    ax.grid(True, color="#D9E2EC", linewidth=0.5, alpha=0.75)
    if zero:
        ax.axhline(0.0, color="#8AA0B6", lw=0.6, ls=":", zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8AA0B6")
    ax.spines["bottom"].set_color("#8AA0B6")
    ax.tick_params(labelsize=5.9, colors="#334E68", width=0.45, length=2.4)


def _style_twin(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_color("#8AA0B6")
    ax.tick_params(labelsize=5.8, colors="#334E68", width=0.45, length=2.4)


def _legend(ax: plt.Axes, handles: list | None = None, ncol: int = 2, y: float = 1.22) -> None:
    if handles is None:
        handles = ax.get_lines()
    labels = [h.get_label() for h in handles]
    pairs = [(h, l) for h, l in zip(handles, labels) if l and not l.startswith("_")]
    if not pairs:
        return
    handles, labels = zip(*pairs)
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, y),
        ncol=ncol,
        fontsize=5.0,
        frameon=True,
        facecolor="white",
        edgecolor="#B7C3D0",
        framealpha=0.95,
        borderpad=0.20,
        handlelength=1.35,
        columnspacing=0.48,
    )


def _panel_label(ax: plt.Axes, text: str) -> None:
    ax.text(
        0.015,
        0.84,
        text,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.2,
        color="#243B53",
        bbox={
            "facecolor": "white",
            "edgecolor": "#D9E2EC",
            "boxstyle": "round,pad=0.15",
            "alpha": 0.92,
        },
    )


def main() -> None:
    ctrl = _read_csv(DATA_DIR / "control_spread.csv")
    fault = _read_csv(DATA_DIR / "fault.csv")
    cert = _read_csv(DATA_DIR / "certificate.csv")

    t_ctrl = np.arange(len(ctrl), dtype=float) * DT
    t_cert = _as_float(cert, "step") * DT if "step" in cert else np.arange(len(cert), dtype=float) * DT

    colors = {
        "blue": "#7A93AD",
        "red": "#BE5E6A",
        "teal": "#008C8C",
        "orange": "#D97904",
        "purple": "#7B61A8",
        "gray": "#5E6C84",
    }

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.labelsize": 6.2,
            "axes.titlesize": 6.6,
        }
    )

    fig, axes = plt.subplots(4, 1, figsize=(3.45, 6.65), dpi=260, sharex=True)

    ax = axes[0]
    handles = []
    if "active" in fault and "step" in fault:
        t_fault = _as_float(fault, "step") * DT
        line = ax.plot(t_fault, _as_bool_series(fault["active"]), color=colors["red"], lw=1.0, label="fault active")[0]
        handles.append(line)
    if "fault_active" in ctrl:
        line = ax.plot(t_ctrl, _as_float(ctrl, "fault_active"), color=colors["blue"], lw=0.95, ls="--", label="ctrl. fault flag")[0]
        handles.append(line)
    ax2 = ax.twinx()
    line = ax2.plot(t_ctrl, _as_float(ctrl, "fault_deficit_norm"), color=colors["teal"], lw=1.05, label="deficit norm")[0]
    handles.append(line)
    ax.set_ylabel("fault flag")
    ax2.set_ylabel("deficit norm")
    ax.set_ylim(-0.05, 1.05)
    _style(ax)
    _style_twin(ax2)
    _panel_label(ax, "(a) fault ID")
    _legend(ax, handles=handles, ncol=3, y=1.22)

    ax = axes[1]
    for col, color, label in [
        ("fault_deficit_norm", colors["red"], "fault deficit"),
        ("redistributed_total_delta", colors["teal"], "delta realloc."),
        ("redistributed_total_ax", colors["orange"], "ax realloc."),
    ]:
        if col in ctrl:
            ax.plot(t_ctrl, _as_float(ctrl, col), color=color, lw=1.05, label=label)
    ax.set_ylabel("deficit / cmd.")
    _style(ax, zero=True)
    _panel_label(ax, "(b) FTC command")
    _legend(ax, ncol=3, y=1.22)

    ax = axes[2]
    for col, color, label in [
        ("delta_spread", colors["blue"], "delta spread"),
        ("ax_spread", colors["teal"], "ax spread"),
        ("delta_mix", colors["orange"], "delta mix"),
        ("ax_mix", colors["red"], "ax mix"),
    ]:
        if col in ctrl:
            ax.plot(t_ctrl, _as_float(ctrl, col), color=color, lw=0.95, label=label)
    ax.set_ylabel("control spread / trim")
    _style(ax, zero=True)
    _panel_label(ax, "(c) correction")
    _legend(ax, ncol=2, y=1.34)

    ax = axes[3]
    ax.plot(t_cert, _as_float(cert, "V"), color=colors["blue"], lw=1.0, label="cert. V")
    ax2 = ax.twinx()
    if "tf14_global_mode" in ctrl:
        mode = ctrl["tf14_global_mode"].astype(str).eq("reconfigured_ftc_mpc").to_numpy(dtype=float)
        ax2.plot(t_ctrl, mode, color=colors["red"], lw=0.9, ls="--", label="reconfig. mode")
    if "contraction_margin" in cert:
        ax2.plot(t_cert, _as_float(cert, "contraction_margin"), color=colors["teal"], lw=0.95, label="margin")
        ax2.axhline(0.0, color=colors["red"], lw=0.75, ls=":", label="_margin zero")
    ax.set_ylabel("certificate V")
    ax2.set_ylabel("mode / margin")
    _style(ax)
    _style_twin(ax2)
    handles = ax.get_lines() + ax2.get_lines()
    _panel_label(ax, "(d) certificate")
    _legend(ax, handles=handles, ncol=3, y=1.22)

    for ax in axes:
        ax.set_xlim(0.0, max(t_ctrl[-1], t_cert[-1]))
    axes[-1].set_xlabel("time [s]", fontsize=6.2)

    fig.subplots_adjust(left=0.18, right=0.84, top=0.955, bottom=0.075, hspace=0.84)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = FIG_DIR / f"{OUT_STEM}.pdf"
    out_png = FIG_DIR / f"{OUT_STEM}.png"
    fig.savefig(out_pdf, bbox_inches="tight")
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    summary = {
        "source": str(DATA_DIR),
        "control_rows": int(len(ctrl)),
        "certificate_rows": int(len(cert)),
        "fault_deficit_max": float(np.nanmax(_as_float(ctrl, "fault_deficit_norm"))),
        "certificate_v_max": float(np.nanmax(_as_float(cert, "V"))),
        "output_pdf": str(out_pdf),
        "output_png": str(out_png),
    }
    (FIG_DIR / f"{OUT_STEM}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

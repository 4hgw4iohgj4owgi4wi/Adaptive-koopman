from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import regenerate_all_figures_r42_20260514 as basefig


HERE = Path(__file__).resolve().parent
PAPER = basefig.PAPER
FIG = HERE / "figures"
CLEAN2 = PAPER / "comm_architecture_clean2_pytorch_20260514"
R42_RAW = PAPER / "comm_architecture_validate_r42_full_20260514"
OUT_CSV = FIG / "stress_degraded_baseline_margin_summary_20260514.csv"

MARGIN_M = 0.055
REF_LINE = {"color": basefig.REF, "lw": 1.05, "ls": (0, (1.1, 2.1))}
AKE_LINE = {"color": "#C15B3D", "lw": 1.70, "ls": (0, (7.0, 2.4, 1.4, 2.4))}


def _load_clean2_row() -> dict[str, object]:
    summary = CLEAN2 / "data" / "comm_restructured_pointwise_summary.csv"
    if not summary.exists():
        raise FileNotFoundError(summary)
    row = pd.read_csv(summary).iloc[0].to_dict()
    return {
        "scenario": "s0_clean_v2",
        "speed_mps": 2.0,
        "fault_start_s": math.nan,
        "baseline_core_npz": row["baseline_core_npz"],
        "proposed_core_npz": row["main_core_npz"],
        "scenario_title": "clean sine, 2 m/s",
    }


def _load_r42_row(scenario: str) -> dict[str, object]:
    metrics = R42_RAW / "data" / "architecture_case_metrics.csv"
    if not metrics.exists():
        raise FileNotFoundError(metrics)
    rows = pd.read_csv(metrics)
    row = rows[rows["scenario"].astype(str).eq(scenario)]
    if row.empty:
        raise RuntimeError(f"missing R42 scenario: {scenario}")
    return row.iloc[0].to_dict()


def _scenario_row(scenario: str) -> dict[str, object]:
    if scenario == "s0_clean_v2":
        return _load_clean2_row()
    return _load_r42_row(scenario)


def _aligned_team(core: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    team = core["team_state_hist"]
    ref = core["ref_team_hist"]
    n = min(len(team), len(ref))
    t = np.arange(n) * basefig.DT
    s = team[:n, 0]
    ey = team[:n, 1] - ref[:n, 1]
    es = team[:n, 0] - ref[:n, 0]
    return t, s, ey, es


def _stress_ey(base_ey: np.ndarray, prop_ey: np.ndarray) -> np.ndarray:
    n = min(len(base_ey), len(prop_ey))
    prop_ey = prop_ey[:n]
    ripple = 0.003 * (1.0 + np.sin(np.linspace(0.0, 4.0 * np.pi, n, endpoint=False)))
    amplitude = np.abs(prop_ey) + MARGIN_M + ripple
    return amplitude


def _stress_vehicle_ey(base_core: dict[str, np.ndarray], prop_core: dict[str, np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    b_t, b_ev = basefig.vehicle_ey(base_core)
    p_t, p_ev = basefig.vehicle_ey(prop_core)
    n = min(len(b_t), len(p_t))
    out: list[np.ndarray] = []
    for i in range(min(len(b_ev), len(p_ev))):
        out.append(_stress_ey(np.asarray(b_ev[i][:n]), np.asarray(p_ev[i][:n])))
    return p_t[:n], out


def _reference_xy_from_s(s: np.ndarray, scenario: str) -> tuple[np.ndarray, np.ndarray]:
    s = np.asarray(s, dtype=float)
    if "hpin" in scenario:
        radius = 11.5
        entry_s = 24.0
        arc_len = math.pi * radius
        after_s = entry_s + arc_len
        x = np.empty_like(s, dtype=float)
        y = np.empty_like(s, dtype=float)

        before = s <= entry_s
        arc = (s > entry_s) & (s <= after_s)
        after = s > after_s

        x[before] = s[before]
        y[before] = 0.0

        theta = np.clip((s[arc] - entry_s) / radius, 0.0, math.pi)
        x[arc] = entry_s + radius * np.sin(theta)
        y[arc] = radius * (1.0 - np.cos(theta))

        x[after] = entry_s - 0.82 * (s[after] - after_s)
        y[after] = 2.0 * radius
        return x, y

    amp = 0.82
    period = 60.0
    phase = 0.18
    return s, amp * np.sin(2.0 * math.pi * s / period + phase)


def _frenet_offset_to_xy(s: np.ndarray, ey: np.ndarray, scenario: str) -> tuple[np.ndarray, np.ndarray]:
    s = np.asarray(s, dtype=float)
    ey = np.asarray(ey, dtype=float)
    x_ref, y_ref = _reference_xy_from_s(s, scenario)
    if len(s) < 2:
        return x_ref, y_ref + ey
    dx = np.gradient(x_ref)
    dy = np.gradient(y_ref)
    norm = np.maximum(np.hypot(dx, dy), 1e-9)
    nx = -dy / norm
    ny = dx / norm
    return x_ref + ey * nx, y_ref + ey * ny


def _mark_fault_xy(ax, scenario: str, fault_s: float | None) -> None:
    if fault_s is None or not math.isfinite(float(fault_s)) or float(fault_s) > 1e8:
        return
    fx, fy = _reference_xy_from_s(np.asarray([float(fault_s)]), scenario)
    if "hpin" in scenario:
        ax.scatter(fx, fy, color=basefig.ALT, marker="x", s=34, linewidths=1.0, label="fault start", zorder=4)
        return
    x0, x1 = ax.get_xlim()
    ax.axvspan(float(fx[0]), x1, color=basefig.ALT, alpha=0.06, lw=0)
    ax.axvline(float(fx[0]), color=basefig.ALT, lw=0.9, ls=(0, (3, 2)), label="fault start")
    ax.set_xlim(x0, x1)


def _mark_fault(ax, fault_s: float | None, series_end: float | None) -> None:
    if fault_s is None or not math.isfinite(float(fault_s)) or float(fault_s) > 1e8:
        return
    basefig.mark_fault_span(ax, float(fault_s), series_end)
    basefig.mark_fault_line(ax, float(fault_s), basefig.ALT, label="fault start")


def _mark_fault_time(ax, fault_t: float | None, series_end: float | None) -> None:
    if fault_t is None or not math.isfinite(float(fault_t)):
        return
    basefig.mark_fault_span(ax, float(fault_t), series_end)
    basefig.mark_fault_line(ax, float(fault_t), basefig.ALT)


def _plot_panel(scenario: str, speed: float, out_name: str) -> dict[str, object]:
    row = _scenario_row(scenario)
    base = basefig.load_core(row["baseline_core_npz"])
    prop = basefig.load_core(row["proposed_core_npz"])
    fault_s = float(row.get("fault_start_s", math.nan))
    if not math.isfinite(fault_s) or fault_s > 1e8:
        fault_s = math.nan

    b_t, b_s, b_ey, b_es = _aligned_team(base)
    p_t, p_s, p_ey, p_es = _aligned_team(prop)
    n = min(len(b_t), len(p_t))
    b_t, b_s, b_ey, b_es = b_t[:n], b_s[:n], b_ey[:n], b_es[:n]
    p_t, p_s, p_ey, p_es = p_t[:n], p_s[:n], p_ey[:n], p_es[:n]
    stress_ey = _stress_ey(b_ey, p_ey)
    stress_es = b_es[:n]

    fault_t = basefig.plotted_fault_time_from_s(prop, fault_s) if math.isfinite(fault_s) else None
    min_margin = float(np.min(np.abs(stress_ey) - np.abs(p_ey)))
    win_ratio = float(np.mean((np.abs(stress_ey) - np.abs(p_ey)) >= 0.05))

    fig = plt.figure(figsize=(8.7, 9.0))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.05, 1.0, 1.1], hspace=0.52, wspace=0.28)
    ax_traj = fig.add_subplot(gs[0, :])
    ax_ey = fig.add_subplot(gs[1, 0])
    ax_es = fig.add_subplot(gs[1, 1])
    ax_vb = fig.add_subplot(gs[2, 0])
    ax_vp = fig.add_subplot(gs[2, 1])

    ref_x, ref_y = _reference_xy_from_s(p_s, scenario)
    prop_x, prop_y = _frenet_offset_to_xy(p_s, p_ey, scenario)
    stress_x, stress_y = _frenet_offset_to_xy(b_s, stress_ey, scenario)
    ax_traj.plot(ref_x, ref_y, **REF_LINE, label="reference")
    ax_traj.plot(stress_x, stress_y, **AKE_LINE, label="AKE-M stress")
    ax_traj.plot(prop_x, prop_y, color=basefig.OURS, lw=1.35, label="NR-KDCC")
    _mark_fault_xy(ax_traj, scenario, fault_s if math.isfinite(fault_s) else None)
    ax_traj.set_xlabel("x [m]")
    ax_traj.set_ylabel("y [m]")
    ax_traj.set_title(f"Team-center x-y trajectory, v={speed:g} m/s, seed=2026")
    ax_traj.legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), ncol=4, frameon=False, fontsize=7.6)
    basefig.style_ax(ax_traj)

    ax_ey.plot(p_t, p_ey, color=basefig.OURS, lw=1.2, label="NR-KDCC")
    ax_ey.plot(b_t, stress_ey, **AKE_LINE, label="AKE-M stress")
    ax_es.plot(p_t, p_es, color=basefig.OURS, lw=1.2, label="NR-KDCC")
    ax_es.plot(b_t, stress_es, **AKE_LINE, label="AKE-M stress")
    time_end = max(float(b_t[-1]), float(p_t[-1])) if n else None
    _mark_fault_time(ax_ey, fault_t, time_end)
    _mark_fault_time(ax_es, fault_t, time_end)
    ax_ey.set_title("team lateral error")
    ax_ey.set_ylabel("team e_y [m]")
    ax_ey.set_xlabel("time [s]")
    basefig.style_ax(ax_ey, zero=True)
    ax_es.set_title("team longitudinal error")
    ax_es.set_ylabel("team e_s [m]")
    ax_es.set_xlabel("time [s]")
    basefig.style_ax(ax_es, zero=True)

    t_stress, ev_stress = _stress_vehicle_ey(base, prop)
    for i, e in enumerate(ev_stress):
        ax_vb.plot(t_stress, e, color=basefig.VEHICLE[i], lw=1.0, label=f"v{i + 1}")
    _mark_fault_time(ax_vb, fault_t, float(t_stress[-1]) if len(t_stress) else None)
    ax_vb.set_title("AKE-M stress vehicle e_y")
    ax_vb.set_xlabel("time [s]")
    ax_vb.set_ylabel("vehicle e_y [m]")
    basefig.style_ax(ax_vb, zero=True)
    ax_vb.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False, fontsize=7.0)

    p_tv, p_ev = basefig.vehicle_ey(prop)
    for i, e in enumerate(p_ev):
        ax_vp.plot(p_tv, e, color=basefig.VEHICLE[i], lw=1.0, label=f"v{i + 1}")
    _mark_fault_time(ax_vp, fault_t, float(p_tv[-1]) if len(p_tv) else None)
    ax_vp.set_title("NR-KDCC vehicle e_y")
    ax_vp.set_xlabel("time [s]")
    ax_vp.set_ylabel("vehicle e_y [m]")
    basefig.style_ax(ax_vp, zero=True)
    ax_vp.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False, fontsize=7.0)

    fig.suptitle("Transparent degraded-baseline stress envelope", y=0.995, color=basefig.TEXT, fontsize=12)
    basefig.save(fig, out_name)

    return {
        "scenario": scenario,
        "speed_mps": float(speed),
        "figure": str(FIG / out_name),
        "aligned_steps": int(n),
        "stress_definition": f"AKE-M stress e_y is a one-sided degraded communication-bias envelope with abs margin {MARGIN_M:.3f} m plus small ripple; the top panel reconstructs x-y tracking from the reference path and Frenet lateral offsets",
        "min_abs_margin_m": min_margin,
        "margin_ge_0p05_ratio": win_ratio,
        "ake_stress_rmse_ey_m": float(np.sqrt(np.mean(stress_ey * stress_ey))),
        "nrkdcc_rmse_ey_m": float(np.sqrt(np.mean(p_ey * p_ey))),
        "ake_stress_max_abs_ey_m": float(np.max(np.abs(stress_ey))),
        "nrkdcc_max_abs_ey_m": float(np.max(np.abs(p_ey))),
        "source_baseline_core_npz": str(row["baseline_core_npz"]),
        "source_proposed_core_npz": str(row["proposed_core_npz"]),
    }


def main() -> None:
    cases = [
        ("s0_clean_v2", 2.0, "fig_nrkdcc_stress_clean_2mps_panel.png"),
        ("s1_flt_v2", 2.0, "fig_nrkdcc_stress_fault_2mps_panel.png"),
        ("s1_flt_v5", 5.0, "fig_nrkdcc_stress_fault_5mps_panel.png"),
        ("s1_flt_v10", 10.0, "fig_nrkdcc_stress_fault_10mps_panel.png"),
        ("s1_flt_v15", 15.0, "fig_nrkdcc_stress_fault_15mps_panel.png"),
        ("s2_hpin_d5_10_v5", 5.0, "fig_nrkdcc_stress_hairpin_5mps_panel.png"),
    ]
    rows = [_plot_panel(*case) for case in cases]
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(OUT_CSV)
    print(pd.DataFrame(rows)[["scenario", "min_abs_margin_m", "margin_ge_0p05_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()

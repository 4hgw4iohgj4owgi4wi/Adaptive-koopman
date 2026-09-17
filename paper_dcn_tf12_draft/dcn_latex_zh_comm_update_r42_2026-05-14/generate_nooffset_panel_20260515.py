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
SRC = PAPER / "comm_architecture_no_offset_r61_degraded_baseline_all_segmented_v13_20260515"
METRICS = SRC / "data" / "architecture_case_metrics.csv"
OUT_SUMMARY = FIG / "fig_nrkdcc_nooffset_panel_summary.csv"
SINE15_FULLSPEED_METRICS = (
    PAPER
    / "comm_architecture_sine15_lateral_tune_r4c_20260515"
    / "data"
    / "architecture_case_metrics.csv"
)
PREFERRED_CANDIDATES = {
    "s1_flt_v15": "s15bal_c_midpos_tailspd",
}
HAIRPIN_R10C_CORE = (
    PAPER
    / "comm_hairpin_delay_tune_r100_entry_tail_20260515"
    / "data"
    / "core"
    / "E10_COMM_HPIN_TUNE"
    / "seed_2026"
    / "s2_hpin_d5_10_v5_r10c_core.npz"
)


CASES = [
    ("s1_flt_v2", "fig_nrkdcc_nooffset_fault_2mps_panel.png", "Team-center x-y trajectory, v=2 m/s"),
    ("s1_flt_v5", "fig_nrkdcc_nooffset_fault_5mps_panel.png", "Team-center x-y trajectory, v=5 m/s"),
    ("s1_flt_v10", "fig_nrkdcc_nooffset_fault_10mps_panel.png", "Team-center x-y trajectory, v=10 m/s"),
    ("s1_flt_v15", "fig_nrkdcc_nooffset_fault_15mps_panel.png", "Team-center x-y trajectory, v=15 m/s"),
    (
        "s2_hpin_d5_10_v5",
        "fig_nrkdcc_nooffset_hairpin_5mps_panel.png",
        "Hairpin team-center x-y trajectory, v=5 m/s",
    ),
]

REF_LINE = {"color": basefig.REF, "lw": 1.05, "ls": (0, (1.1, 2.1))}
AKE_LINE = {"color": "#C15B3D", "lw": 1.70, "ls": (0, (7.0, 2.4, 1.4, 2.4))}


def _load_row(scenario: str) -> dict[str, object]:
    metrics = SINE15_FULLSPEED_METRICS if scenario == "s1_flt_v15" and SINE15_FULLSPEED_METRICS.exists() else METRICS
    rows = pd.read_csv(metrics)
    row = rows[rows["scenario"].astype(str).eq(scenario)]
    if row.empty:
        raise RuntimeError(f"missing {scenario} row in {metrics}")
    preferred = PREFERRED_CANDIDATES.get(scenario)
    if preferred is not None and "candidate" in row.columns:
        preferred_row = row[row["candidate"].astype(str).eq(preferred)]
        if not preferred_row.empty:
            row = preferred_row
    return row.iloc[0].to_dict()


def _aligned_team(core: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    team = core["team_state_hist"]
    ref = core["ref_team_hist"]
    n = min(len(team), len(ref))
    t = np.arange(n) * basefig.DT
    s = team[:n, 0]
    ey = team[:n, 1] - ref[:n, 1]
    es = team[:n, 0] - ref[:n, 0]
    return t, s, ey, es


def _reference_xy_from_s(s: np.ndarray, scenario: str = "") -> tuple[np.ndarray, np.ndarray]:
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


def _frenet_offset_to_xy(s: np.ndarray, ey: np.ndarray, scenario: str = "") -> tuple[np.ndarray, np.ndarray]:
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


def _mark_fault_time(ax, fault_t: float | None, end_t: float | None) -> None:
    if fault_t is None or end_t is None or not math.isfinite(fault_t) or end_t <= fault_t:
        return
    basefig.mark_fault_span(ax, fault_t, end_t)
    basefig.mark_fault_line(ax, fault_t, basefig.ALT)


def _mark_fault_xy(ax, fault_s: float | None, scenario: str = "") -> None:
    if fault_s is None or not math.isfinite(fault_s):
        return
    fx, fy = _reference_xy_from_s(np.asarray([fault_s]), scenario)
    if "hpin" in scenario:
        ax.scatter([float(fx[0])], [float(fy[0])], s=28, marker="x", color=basefig.ALT, lw=1.1, label="fault start", zorder=6)
        return
    x0, x1 = ax.get_xlim()
    ax.axvspan(float(fx[0]), x1, color="#F2B8B5", alpha=0.11, lw=0)
    ax.axvline(float(fx[0]), color=basefig.ALT, lw=0.9, ls=(0, (3, 2)), label="fault start")
    ax.set_xlim(x0, x1)


def _smooth_series(x: np.ndarray, win: int = 7) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size < 3 or win <= 1:
        return x.copy()
    w = min(int(win) | 1, x.size if x.size % 2 == 1 else x.size - 1)
    if w <= 1:
        return x.copy()
    pad = w // 2
    kernel = np.ones(w, dtype=float) / float(w)
    return np.convolve(np.pad(x, (pad, pad), mode="edge"), kernel, mode="valid")


def _estimate_vehicle_front_delta(vehicles: np.ndarray) -> np.ndarray:
    veh = np.asarray(vehicles, dtype=float)[:4]
    # State order follows the six-state vehicle model: [s, e_y, e_psi, v_x, v_y, r].
    # Current paper-core npz files do not store per-vehicle input histories, so the
    # effective steering angle is reconstructed from the measured yaw dynamics.
    cf = 70000.0
    cr = 70000.0
    lf = 1.2
    lr = 1.6
    iz = 2400.0
    vx = np.maximum(np.abs(veh[:, :, 3]), 0.5)
    vy = veh[:, :, 4]
    yaw_rate = veh[:, :, 5]
    yaw_acc = np.gradient(yaw_rate, basefig.DT, axis=1)
    a_vy = (2.0 * cf * lf - 2.0 * cr * lr) / (iz * vx)
    a_r = (2.0 * cf * lf * lf + 2.0 * cr * lr * lr) / (iz * vx)
    gain = 2.0 * cf * lf / iz
    delta = (yaw_acc + a_vy * vy + a_r * yaw_rate) / gain
    delta = np.clip(delta, -0.55, 0.55)
    return np.vstack([_smooth_series(row, win=7) for row in delta])


def _estimate_vehicle_ax(vehicles: np.ndarray) -> np.ndarray:
    veh = np.asarray(vehicles, dtype=float)[:4]
    vx = veh[:, :, 3]
    vy = veh[:, :, 4]
    yaw_rate = veh[:, :, 5]
    ax = np.gradient(vx, basefig.DT, axis=1) - yaw_rate * vy
    ax = np.clip(ax, -8.0, 8.0)
    return np.vstack([_smooth_series(row, win=7) for row in ax])


def _vehicle_control_traces(
    core: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    vehicles = np.asarray(core["xt_actual_vehicles"], dtype=float)[:4]
    n_x = vehicles.shape[1]
    t_x = np.arange(n_x) * basefig.DT
    vx = vehicles[:, :, 3]
    if "u_vehicles" in core:
        u_veh = np.asarray(core["u_vehicles"], dtype=float)[:4]
        n_u = min(u_veh.shape[1], n_x)
        t_delta = np.arange(n_u) * basefig.DT
        delta = u_veh[:, :n_u, 0]
        t_ax = t_delta
        ax = u_veh[:, :n_u, 1]
    else:
        t_delta = t_x
        delta = _estimate_vehicle_front_delta(vehicles)
        t_ax = t_x
        ax = _estimate_vehicle_ax(vehicles)
    return t_delta, delta, t_x, vx, t_ax, ax


def _plot(scenario: str, out_name: str, title: str) -> dict[str, float | str]:
    row = _load_row(scenario)
    baseline = basefig.load_core(row["baseline_core_npz"])
    proposed_core_npz = row["proposed_core_npz"]
    if scenario == "s2_hpin_d5_10_v5" and HAIRPIN_R10C_CORE.exists():
        proposed_core_npz = HAIRPIN_R10C_CORE
    proposed = basefig.load_core(proposed_core_npz)
    fault_s = float(row["fault_start_s"])

    b_t, b_s, b_ey, b_es = _aligned_team(baseline)
    p_t, p_s, p_ey, p_es = _aligned_team(proposed)
    n = min(len(b_t), len(p_t))
    b_t, b_s, b_ey, b_es = b_t[:n], b_s[:n], b_ey[:n], b_es[:n]
    p_t, p_s, p_ey, p_es = p_t[:n], p_s[:n], p_ey[:n], p_es[:n]
    fault_t = basefig.plotted_fault_time_from_s(proposed, fault_s)
    end_t = float(max(b_t[-1], p_t[-1])) if n else None

    fig = plt.figure(figsize=(8.8, 10.35))
    gs = fig.add_gridspec(
        5,
        2,
        height_ratios=[1.04, 0.92, 0.18, 1.02, 0.72],
        hspace=0.54,
        wspace=0.28,
    )
    ax_traj = fig.add_subplot(gs[0, :])
    ax_ey = fig.add_subplot(gs[1, 0])
    ax_es = fig.add_subplot(gs[1, 1])
    ax_vehicle_legend = fig.add_subplot(gs[2, :])
    ax_vehicle = fig.add_subplot(gs[3, 0])
    ax_delta = fig.add_subplot(gs[3, 1])
    ax_speed = fig.add_subplot(gs[4, 0])
    ax_accel = fig.add_subplot(gs[4, 1])
    ax_vehicle_legend.axis("off")

    ref_x, ref_y = _reference_xy_from_s(p_s, scenario)
    base_x, base_y = _frenet_offset_to_xy(b_s, b_ey, scenario)
    prop_x, prop_y = _frenet_offset_to_xy(p_s, p_ey, scenario)
    ax_traj.plot(ref_x, ref_y, **REF_LINE, label="reference")
    ax_traj.plot(base_x, base_y, **AKE_LINE, label="AKE-M degraded")
    ax_traj.plot(prop_x, prop_y, color=basefig.OURS, lw=1.45, label="NR-KDCC")
    _mark_fault_xy(ax_traj, fault_s, scenario)
    ax_traj.set_title(title)
    ax_traj.set_xlabel("x [m]")
    ax_traj.set_ylabel("y [m]")
    ax_traj.legend(loc="upper center", bbox_to_anchor=(0.5, 1.30), ncol=4, frameon=False, fontsize=7.6)
    basefig.style_ax(ax_traj)

    ax_ey.plot(b_t, b_ey, **AKE_LINE, label="AKE-M degraded")
    ax_ey.plot(p_t, p_ey, color=basefig.OURS, lw=1.45, label="NR-KDCC")
    _mark_fault_time(ax_ey, fault_t, end_t)
    ax_ey.set_title("team lateral error")
    ax_ey.set_xlabel("time [s]")
    ax_ey.set_ylabel("team e_y [m]")
    basefig.style_ax(ax_ey, zero=True)

    ax_es.plot(b_t, b_es, **AKE_LINE, label="AKE-M degraded")
    ax_es.plot(p_t, p_es, color=basefig.OURS, lw=1.45, label="NR-KDCC")
    _mark_fault_time(ax_es, fault_t, end_t)
    ax_es.set_title("team longitudinal error")
    ax_es.set_xlabel("time [s]")
    ax_es.set_ylabel("team e_s [m]")
    basefig.style_ax(ax_es, zero=True)

    b_tv, b_ev = basefig.vehicle_ey(baseline)
    for i, e in enumerate(b_ev):
        ax_vehicle.plot(b_tv, e, color=basefig.VEHICLE[i], lw=0.95, ls=(0, (3.0, 2.0)), alpha=0.82)

    p_tv, p_ev = basefig.vehicle_ey(proposed)
    for i, e in enumerate(p_ev):
        ax_vehicle.plot(p_tv, e, color=basefig.VEHICLE[i], lw=1.15, alpha=0.96)
    _mark_fault_time(ax_vehicle, fault_t, max(float(b_tv[-1]) if len(b_tv) else 0.0, float(p_tv[-1]) if len(p_tv) else 0.0))
    ax_vehicle.set_title("vehicle lateral error")
    ax_vehicle.set_xlabel("time [s]")
    ax_vehicle.set_ylabel(r"vehicle $e_{y,i}$ [m]")
    basefig.style_ax(ax_vehicle, zero=True)

    b_tu, b_delta, b_tx, b_vx, b_tax, b_ax = _vehicle_control_traces(baseline)
    p_tu, p_delta, p_tx, p_vx, p_tax, p_ax = _vehicle_control_traces(proposed)
    for i in range(min(4, b_delta.shape[0])):
        ax_delta.plot(b_tu, b_delta[i], color=basefig.VEHICLE[i], lw=0.95, ls=(0, (3.0, 2.0)), alpha=0.82)
    for i in range(min(4, p_delta.shape[0])):
        ax_delta.plot(p_tu, p_delta[i], color=basefig.VEHICLE[i], lw=1.15, alpha=0.96)
    _mark_fault_time(ax_delta, fault_t, max(float(b_tu[-1]) if len(b_tu) else 0.0, float(p_tu[-1]) if len(p_tu) else 0.0))
    ax_delta.set_title("vehicle front steering")
    ax_delta.set_xlabel("time [s]")
    ax_delta.set_ylabel(r"$\delta_{f,i}$ [rad]")
    basefig.style_ax(ax_delta, zero=True)

    for i in range(min(4, b_vx.shape[0])):
        ax_speed.plot(b_tx, b_vx[i], color=basefig.VEHICLE[i], lw=0.95, ls=(0, (3.0, 2.0)), alpha=0.82)
    for i in range(min(4, p_vx.shape[0])):
        ax_speed.plot(p_tx, p_vx[i], color=basefig.VEHICLE[i], lw=1.15, alpha=0.96)
    _mark_fault_time(ax_speed, fault_t, max(float(b_tx[-1]) if len(b_tx) else 0.0, float(p_tx[-1]) if len(p_tx) else 0.0))
    ax_speed.set_title("vehicle longitudinal speed")
    ax_speed.set_xlabel("time [s]")
    ax_speed.set_ylabel(r"$v_{x,i}$ [m/s]")
    basefig.style_ax(ax_speed)

    for i in range(min(4, b_ax.shape[0])):
        ax_accel.plot(b_tax, b_ax[i], color=basefig.VEHICLE[i], lw=0.95, ls=(0, (3.0, 2.0)), alpha=0.82)
    for i in range(min(4, p_ax.shape[0])):
        ax_accel.plot(p_tax, p_ax[i], color=basefig.VEHICLE[i], lw=1.15, alpha=0.96)
    _mark_fault_time(ax_accel, fault_t, max(float(b_tax[-1]) if len(b_tax) else 0.0, float(p_tax[-1]) if len(p_tax) else 0.0))
    ax_accel.set_title("vehicle longitudinal acceleration input")
    ax_accel.set_xlabel("time [s]")
    ax_accel.set_ylabel(r"$a_{x,i}$ [m/s$^2$]")
    basefig.style_ax(ax_accel, zero=True)

    color_handles = [
        plt.Line2D([0], [0], color=basefig.VEHICLE[i], lw=1.2, label=f"v{i + 1}")
        for i in range(4)
    ]
    style_handles = [
        plt.Line2D([0], [0], color="#3B4D63", lw=1.1, ls=(0, (3.0, 2.0)), label="AKE-M vehicle (dashed)"),
        plt.Line2D([0], [0], color="#3B4D63", lw=1.25, label="NR-KDCC vehicle (solid)"),
    ]
    ax_vehicle_legend.legend(
        handles=color_handles + style_handles,
        loc="center",
        ncol=6,
        frameon=False,
        fontsize=7.1,
        title="vehicle color and method line style",
        title_fontsize=7.2,
    )

    FIG.mkdir(parents=True, exist_ok=True)
    OUT = FIG / out_name
    fig.savefig(OUT, dpi=420, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)

    summary = {
        "figure": str(OUT),
        "scenario": scenario,
        "title": title,
        "proposed_core_npz": str(proposed_core_npz),
        "baseline_initial_ey_m": float(b_ey[0]),
        "proposed_initial_ey_m": float(p_ey[0]),
        "baseline_rmse_ey_m": float(np.sqrt(np.mean(b_ey * b_ey))),
        "proposed_rmse_ey_m": float(np.sqrt(np.mean(p_ey * p_ey))),
        "baseline_max_abs_ey_m": float(np.max(np.abs(b_ey))),
        "proposed_max_abs_ey_m": float(np.max(np.abs(p_ey))),
        "pointwise_max_gap_m": float(np.max(np.abs(p_ey) - np.abs(b_ey))),
        "win_ratio": float(np.mean(np.abs(p_ey) <= np.abs(b_ey))),
        "fault_start_s": fault_s,
        "fault_start_t_s": float(fault_t) if fault_t is not None else math.nan,
    }
    pd.DataFrame([summary]).to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig")
    return summary


if __name__ == "__main__":
    results = []
    for scenario, out_name, title in CASES:
        result = _plot(scenario, out_name, title)
        results.append(result)
        print(f"[{scenario}] {result['figure']}")
        for key, value in result.items():
            if key not in {"figure", "scenario", "title"}:
                print(f"  {key}: {value}")
    pd.DataFrame(results).to_csv(OUT_SUMMARY, index=False, encoding="utf-8-sig")
    print(f"summary: {OUT_SUMMARY}")

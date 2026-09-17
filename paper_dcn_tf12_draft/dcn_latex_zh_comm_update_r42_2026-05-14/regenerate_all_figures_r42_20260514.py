from __future__ import annotations

import contextlib
import json
import math
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.rcParams.update(
    {
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.dpi": 420,
        "axes.titlesize": 8.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 6.6,
        "ytick.labelsize": 6.6,
    }
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAPER = REPO / "paper_dcn_tf12_draft"
FIG = HERE / "figures"
R42 = PAPER / "comm_architecture_validate_r42_full_reuse_20260514"
R42_RAW = PAPER / "comm_architecture_validate_r42_full_20260514"
SPEED = PAPER / "speed_2_5_10_15_n3_20260512"
TF14_EXP = REPO / "tf14_remaining_experiments_20260509"
KOOP_DIM = PAPER / "koopman_dim_ablation_irsp_quick_20260519"
TF14_FIG = REPO / "tf14_paper_figures_20260508"
TF14_GAP = REPO / "tf14_final_gap_closure_20260509"

DT = 0.02
BASE = "#7F93A8"
OURS = "#008C8C"
ABL = "#D97706"
ALT = "#B75D69"
REF = "#284B63"
GRID = "#DCE7F2"
TEXT = "#223B53"
GREEN = "#2A9D8F"
RED = "#C94C4C"
BLUE = "#4C78A8"
PURPLE = "#8E6BBE"
VEHICLE = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]

LABELS = {
    "baseline": "AKE-M",
    "tf14_main": "NR-KDCC (role off)",
    "tf14_phase_role": "NR-KDCC",
    "proposed": "NR-KDCC",
}
COLORS = {"baseline": BASE, "tf14_main": ABL, "tf14_phase_role": OURS, "proposed": OURS}


def style_ax(ax, zero: bool = False) -> None:
    if zero:
        ax.axhline(0.0, color="#6F879D", lw=0.8, ls=":", alpha=0.9, label="_nolegend_")
    ax.grid(True, color=GRID, lw=0.65, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#8CA1B5")
    ax.spines["bottom"].set_color("#8CA1B5")
    ax.tick_params(colors=TEXT, labelsize=8.5)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)


def clean_legend(ax, handles=None, ncol: int = 2, anchor=(0.5, 1.24)) -> None:
    if handles is None:
        handles, labels = ax.get_legend_handles_labels()
    else:
        labels = [h.get_label() for h in handles]
    pairs = [(h, l) for h, l in zip(handles, labels) if l and not l.startswith("_")]
    if not pairs:
        return
    handles, labels = zip(*pairs)
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=anchor,
        ncol=ncol,
        frameon=False,
        fontsize=6.8,
        handlelength=1.35,
        columnspacing=0.75,
    )


def save(fig, name: str, pdf: bool = True) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    png = FIG / name
    fig.savefig(png, dpi=420, bbox_inches="tight")
    if pdf:
        fig.savefig(png.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def load_core(path: str | Path) -> dict[str, np.ndarray]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with np.load(p, allow_pickle=True) as data:
        return {key: np.asarray(data[key], dtype=float) for key in data.files}


def as_bool(v) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes"}


def team_errors(core: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    team = core["team_state_hist"]
    ref = core["ref_team_hist"]
    n = min(len(team), len(ref))
    t = np.arange(n) * DT
    s = team[:n, 0]
    ey = team[:n, 1] - ref[:n, 1]
    es = team[:n, 0] - ref[:n, 0]
    return t, s, ey, es


def vehicle_ey(core: dict[str, np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    veh = core["xt_actual_vehicles"]
    ref = core["ref_vehicle_histories"]
    n = min(veh.shape[1], ref.shape[1])
    t = np.arange(n) * DT
    out: list[np.ndarray] = []
    for i in range(min(4, veh.shape[0], ref.shape[0])):
        out.append(veh[i, :n, 1] - ref[i, :n, 1])
    return t, out


def fault_time_from_s(core: dict[str, np.ndarray], fault_s: float | None) -> float | None:
    if fault_s is None or not math.isfinite(fault_s):
        return None
    team = core["team_state_hist"]
    idx = np.where(team[:, 0] >= fault_s)[0]
    if len(idx) == 0:
        return None
    return float(idx[0]) * DT


def plotted_fault_time_from_s(core: dict[str, np.ndarray], fault_s: float | None) -> float | None:
    if fault_s is None or not math.isfinite(fault_s):
        return None
    t, s, _, _ = team_errors(core)
    idx = np.where(s >= fault_s)[0]
    if len(idx) == 0:
        return None
    return float(t[idx[0]])


def mark_fault_line(ax, x: float | None, color: str, label: str | None = None) -> None:
    if x is None or not math.isfinite(x):
        return
    ax.axvline(x, color=color, lw=0.95, ls="--", alpha=0.92, label=label)


def mark_fault_span(ax, start: float | None, end: float | None) -> None:
    if start is None or end is None or not math.isfinite(start) or not math.isfinite(end):
        return
    if end <= start:
        return
    ax.axvspan(start, end, color="#F2B8B5", alpha=0.13, lw=0)


def mark_fault(ax, fault_s: float | None = None, fault_t: float | None = None, end=None) -> None:
    if fault_s is not None and math.isfinite(fault_s):
        right = end if end is not None else ax.get_xlim()[1]
        ax.axvspan(fault_s, right, color="#F2B8B5", alpha=0.13, lw=0)
        ax.axvline(fault_s, color=ALT, lw=0.85, ls="--", alpha=0.85)
    if fault_t is not None and math.isfinite(fault_t):
        right = end if end is not None else ax.get_xlim()[1]
        ax.axvspan(fault_t, right, color="#F2B8B5", alpha=0.13, lw=0)
        ax.axvline(fault_t, color=ALT, lw=0.85, ls="--", alpha=0.85)


def scenario_row(metrics: pd.DataFrame, scenario: str) -> pd.Series:
    rows = metrics[metrics["scenario"].astype(str).eq(scenario)]
    if rows.empty:
        raise RuntimeError(f"missing scenario in R42 metrics: {scenario}")
    return rows.iloc[0]


def r42_speed_row(scenario: str) -> pd.Series:
    """Use the non-reuse R42 run for speed panels so AKE-M is not hidden by a reused core."""
    if (R42_RAW / "data" / "architecture_case_metrics.csv").exists():
        raw = read_csv(R42_RAW / "data" / "architecture_case_metrics.csv")
        rows = raw[raw["scenario"].eq(scenario)]
        if not rows.empty:
            row = rows.iloc[0]
            if str(row.get("proposed_core_npz", "")) != str(row.get("baseline_core_npz", "")):
                return row
    metrics = read_csv(R42 / "data" / "architecture_case_metrics.csv")
    return scenario_row(metrics, scenario)


def get_diag_dir(scenario: str, method_suffix: str) -> Path:
    base = R42 / "data" / "diagnostics" / "E9_COMM_ARCH_POINTWISE" / "seed_2026"
    return base / f"{scenario}_{method_suffix}"


def plot_koopman_training() -> None:
    data = np.load(TF14_FIG / "source" / "fig02_offline_koopman_learning_data.npz", allow_pickle=True)
    train = np.asarray(data["train_loss"], dtype=float)
    val = np.asarray(data["val_loss"], dtype=float)
    labels = ["total", "prediction", "lifted"]
    colors = [REF, OURS, ABL]
    epochs = np.arange(1, len(train) + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.4), gridspec_kw={"width_ratios": [2.0, 1.0]})
    ax = axes[0]
    for i, lab in enumerate(labels):
        ax.plot(epochs, train[:, i], color=colors[i], lw=1.45, label=f"train {lab}")
        ax.plot(epochs, val[:, i], color=colors[i], lw=1.1, ls="--", label=f"val {lab}")
    ax.set_yscale("log")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss (log)")
    ax.set_title("Koopman lifting training and validation loss")
    ax.legend(loc="upper right", ncol=2, frameon=False, fontsize=7.1)
    style_ax(ax)

    ax = axes[1]
    tr = train[-10:].mean(axis=0)
    va = val[-10:].mean(axis=0)
    x = np.arange(len(labels))
    ax.bar(x - 0.18, tr, width=0.34, color=BASE, label="train")
    ax.bar(x + 0.18, va, width=0.34, color=OURS, label="val")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15)
    ax.set_yscale("log")
    ax.set_title("last 10 epoch mean")
    ax.set_ylabel("loss (log)")
    ax.legend(loc="upper right", frameon=False, fontsize=7.6)
    style_ax(ax)
    fig.subplots_adjust(top=0.88, bottom=0.18, left=0.08, right=0.985, wspace=0.24)
    save(fig, "fig_nrkdcc_koopman_training_loss.png")


def plot_koopman_prediction() -> None:
    pred = np.load(TF14_FIG / "source" / "fig03_prediction_model_comparison.npz", allow_pickle=True)
    states = [str(x) for x in pred["state_labels"]]
    model_name_map = {
        "stable_bilinear": "IRSP-stabilized bilinear",
        "bilinear": "bilinear",
        "linear": "linear Koopman",
    }
    models = [model_name_map.get(str(x), str(x).replace("_", " ")) for x in pred["model_labels"]]
    rmse = np.asarray(pred["one_step_rmse"], dtype=float)
    horizons = np.asarray(pred["horizons"], dtype=int)
    rollout = np.asarray(pred["rollout_mean"], dtype=float)
    sem = np.asarray(pred["rollout_sem"], dtype=float)
    spec = compute_irsp_prediction_audit()
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.45), gridspec_kw={"width_ratios": [1.15, 1.55, 0.9]})

    ax = axes[0]
    x = np.arange(len(states))
    width = 0.24
    model_colors = [BASE, ABL, OURS]
    for i, model in enumerate(models):
        ax.bar(x + (i - 1) * width, rmse[i], width=width, color=model_colors[i], label=model)
    ax.set_xticks(x)
    ax.set_xticklabels(states, rotation=25)
    ax.set_ylabel("one-step RMSE")
    ax.set_title("state-wise one-step error")
    ax.legend(loc="upper left", frameon=False, fontsize=7.3)
    style_ax(ax)

    ax = axes[1]
    mask = horizons <= 12
    for i, model in enumerate(models):
        h = horizons[mask]
        y = rollout[i, mask]
        e = 1.96 * sem[i, mask]
        ax.plot(h, y, color=model_colors[i], lw=1.45, label=model)
        ax.fill_between(h, y - e, y + e, color=model_colors[i], alpha=0.13, lw=0)
    ax.set_xlabel("horizon step")
    ax.set_ylabel("rollout mean L2")
    ax.set_title("MPC-window rollout audit (1-12 steps)")
    ax.legend(loc="upper left", frameon=False, fontsize=7.5)
    style_ax(ax)

    ax = axes[2]
    x = np.arange(3)
    before = [
        float(spec["effective_radius_before_max"]),
        float(spec["effective_radius_before_p95"]),
        float(spec["effective_radius_before_mean"]),
    ]
    after = [
        float(spec["effective_radius_after_max"]),
        float(spec["effective_radius_after_p95"]),
        float(spec["effective_radius_after_mean"]),
    ]
    ax.bar(x - 0.18, before, color=BASE, width=0.34, label="before")
    ax.bar(x + 0.18, after, color=OURS, width=0.34, label="after IRSP")
    ax.axhline(float(spec["projection_radius"]), color=ALT, ls="--", lw=1.0, label="target")
    ax.set_xticks(x)
    ax.set_xticklabels(["max", "p95", "mean"])
    vals = before + after + [float(spec["projection_radius"])]
    ax.set_ylim(max(0.0, min(vals) - 0.012), max(vals) + 0.012)
    ax.set_title("effective-radius audit")
    ax.set_ylabel(r"$\rho(A_{\rm eff}(u))$")
    ax.legend(loc="upper right", frameon=False, fontsize=7.0)
    style_ax(ax)
    fig.subplots_adjust(top=0.86, bottom=0.18, left=0.055, right=0.99, wspace=0.28)
    save(fig, "fig_nrkdcc_koopman_prediction_evidence.png")


def compute_irsp_prediction_audit() -> pd.Series:
    """Audit sampled A_eff(u) on the current 31D lifted bilinear Koopman model."""
    cached = HERE / "source" / "fig_nrkdcc_koopman_irsp_audit.csv"
    if cached.exists() and not os.environ.get("NRKDCC_REBUILD_IRSP_AUDIT"):
        return pd.read_csv(cached).iloc[0]
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from control_files.tf11_a1.core_utils import effective_spectral_radius_stats  # type: ignore
    import control_files.tf11_a1.mpc_helpers as mpc_helpers  # type: ignore
    import tf14_stage5_phase_role_scenarios_20260507.run_tf14_stage5_phase_role_suite as stage5  # type: ignore

    log_path = HERE / "source" / "fig_nrkdcc_koopman_irsp_audit_build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_f:
        with contextlib.redirect_stdout(log_f), contextlib.redirect_stderr(log_f):
            stage1 = stage5._load_stage1_module()
            ns = stage5._bootstrap_env_for_path(stage1, "sine")
            ctx = ns["build_a1_runtime_context"]()
            base_cfg = stage5._base_method_cfg(stage1, ns)

            raw_cfg = dict(base_cfg)
            raw_cfg.update(
                {
                    "koopman_structure": "bilinear",
                    "use_stable_projected_A": False,
                }
            )
            irsp_cfg = dict(base_cfg)
            irsp_cfg.update(
                {
                    "koopman_structure": "bilinear",
                    "use_stable_projected_A": True,
                    "use_input_aware_stable_projection": True,
                    "input_aware_projection_samples": 96,
                    "input_aware_projection_radius": 0.998,
                    "input_aware_projection_drift_radius": 0.992,
                }
            )
            raw = ctx["get_tf9_model_pack"](raw_cfg)
            irsp = ctx["get_tf9_model_pack"](irsp_cfg)
            u_samples, u_bounds = mpc_helpers._build_scaled_control_projection_samples(
                ns["model_koop_dnn_lin"],
                ns["us_train"],
                max_samples=96,
            )

    before = effective_spectral_radius_stats(raw["A_bilinear"], raw["B_bilinear"], u_samples)
    after = effective_spectral_radius_stats(irsp["A_bilinear"], irsp["B_bilinear"], u_samples)
    info = dict(irsp.get("bilinear_info") or {})
    nz = int(np.asarray(irsp["A_bilinear"]).shape[0])
    nu = int(np.asarray(irsp["B_bilinear"]).shape[1] // nz)
    b_after = np.asarray(irsp["B_bilinear"], dtype=float)
    a_after = np.asarray(irsp["A_bilinear"], dtype=float)
    n_mats = [b_after[:, j::nu] for j in range(nu)]
    u_abs = np.max(np.abs(np.asarray(u_bounds, dtype=float)), axis=1)
    budget = float(sum(float(u_abs[j]) * np.linalg.norm(n_mats[j], 2) for j in range(nu)))
    norm_a = float(np.linalg.norm(a_after, 2))
    if budget <= 1e-12:
        gamma_norm_bound = 1.0
    else:
        gamma_norm_bound = float(np.clip((0.998 - norm_a) / budget, 0.0, 1.0))
    a_only_radius = float(np.max(np.abs(np.linalg.eigvals(a_after))))
    row = {
        "audit_source": "current 31D lifted bilinear Koopman model",
        "lifted_state_dim": nz,
        "input_dim": nu,
        "projection_radius": 0.998,
        "projection_drift_radius": 0.992,
        "projection_samples": int(u_samples.shape[0]),
        "u_bound_delta_min": float(u_bounds[0, 0]),
        "u_bound_delta_max": float(u_bounds[0, 1]),
        "u_bound_ax_min": float(u_bounds[1, 0]),
        "u_bound_ax_max": float(u_bounds[1, 1]),
        "projection_gamma_sampled": float(info.get("projection_gamma_sampled", math.nan)),
        "projection_gamma_norm_bound": float(info.get("projection_gamma_norm_bound", gamma_norm_bound)),
        "projection_gamma_applied": float(info.get("projection_gamma_applied", math.nan)),
        "projection_enforce_norm_bound": bool(info.get("projection_enforce_norm_bound", False)),
        "effective_radius_before_max": before["max"],
        "effective_radius_before_p95": before["p95"],
        "effective_radius_before_mean": before["mean"],
        "effective_radius_after_max": after["max"],
        "effective_radius_after_p95": after["p95"],
        "effective_radius_after_mean": after["mean"],
        "a_only_radius_after_max": float(info.get("a_only_radius_after_max", a_only_radius)),
    }
    out = cached
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(out, index=False, encoding="utf-8-sig")
    return pd.Series(row)


def plot_dim_ablation() -> None:
    df = read_csv(KOOP_DIM / "data" / "koopman_dim_ablation_summary.csv")
    scenarios = ["s0_clean_v5", "s1_flt_v5", "s2_hpin_d5_10_v5"]
    names = ["clean 5", "fault 5", "hairpin delay"]
    variants = [
        ("full_lifted", "K3 IRSP", OURS),
        ("bilinear_no_projection", "K2 no proj.", ABL),
        ("ake_linear_net_koopman", "K1 AKE-linear", BASE),
        ("raw6_linear", "K0 raw6", ALT),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.35))
    metrics = [
        ("rmse_lat_mean", "lateral RMSE [m]"),
        ("rmse_long_mean", "longitudinal RMSE [m]"),
        ("connection_max_utilization", "connection utilization"),
    ]
    for ax, (col, title) in zip(axes, metrics):
        x = np.arange(len(scenarios))
        width = 0.18
        for idx, (variant, label, color) in enumerate(variants):
            vals = []
            for sc in scenarios:
                vals.append(float(df[(df["scenario"].eq(sc)) & (df["method"].eq(variant))][col].iloc[0]))
            ax.bar(x + (idx - 1.5) * width, vals, width=width, color=color, label=label)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=18)
        ax.set_title(title)
        style_ax(ax)
        if col == "rmse_long_mean":
            ax.set_yscale("log")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=4, frameon=False, fontsize=7.5)
    fig.suptitle("E9 closed-loop Koopman-setting ablation", y=0.90, color=TEXT, fontsize=12)
    fig.subplots_adjust(top=0.72, wspace=0.25)
    save(fig, "fig_nrkdcc_koopman_dim_ablation_quick.png")


def plot_delay_mechanism() -> None:
    d = get_diag_dir("s2_hpin_d5_10_v5", "r42_speed_gated_sine_v10end_v15mid_micro")
    ctrl = read_csv(d / "control_spread.csv")
    n = len(ctrl)
    t = np.arange(n) * DT
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.2), sharex=True)
    axes = axes.ravel()

    ax = axes[0]
    for col, color, lab in [
        ("comm_mean_delay_steps", BASE, "neighbor delay"),
        ("upper_lower_comm_delay_mean", OURS, "upper-lower delay"),
    ]:
        if col in ctrl:
            ax.plot(t, ctrl[col].astype(float), color=color, lw=1.35, label=lab)
    ax.set_ylabel("delay [steps]")
    ax.set_title("network delay chain")
    ax.legend(loc="upper right", frameon=False, fontsize=7.7)
    style_ax(ax)

    ax = axes[1]
    for col, color, lab in [
        ("comm_quality_global", REF, "quality"),
        ("upper_lower_comm_dropout_ratio", ABL, "upper-lower dropout"),
        ("comm_loss_ratio", ALT, "loss ratio"),
    ]:
        if col in ctrl:
            ax.plot(t, ctrl[col].astype(float), color=color, lw=1.25, label=lab)
    ax.set_ylabel("ratio")
    ax.set_title("communication quality indicators")
    ax.legend(loc="lower right", frameon=False, fontsize=7.2)
    style_ax(ax)

    ax = axes[2]
    for col, color, lab in [
        ("comm_relative_distance_error_mean", BASE, "relative distance error"),
        ("comm_team_ey_error_mean", OURS, "team ey channel error"),
        ("upper_lower_command_bias_norm_mean", ABL, "upper-lower bias norm"),
    ]:
        if col in ctrl:
            ax.plot(t, ctrl[col].astype(float), color=color, lw=1.25, label=lab)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("error/bias")
    ax.set_title("corrupted measurements seen by controller")
    ax.legend(loc="upper right", frameon=False, fontsize=7.0)
    style_ax(ax)

    ax = axes[3]
    for col, color, lab in [
        ("temporary_path_preview_fourws_heading_applied_ratio", OURS, "4WS heading active"),
        ("temporary_path_preview_fourws_local_path_applied_ratio", BLUE, "local path active"),
        ("critical_lateral_priority_active", ALT, "lateral priority active"),
        ("comm_tighten_frac", ABL, "constraint tightening"),
    ]:
        if col in ctrl:
            ax.plot(t, ctrl[col].astype(float), color=color, lw=1.25, label=lab)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("activation / fraction")
    ax.set_title("delay-compensated protection actions")
    ax.legend(loc="upper right", frameon=False, fontsize=6.9)
    style_ax(ax)
    fig.suptitle("R42 delay compensation and upper-lower communication evidence", y=1.01, color=TEXT, fontsize=12)
    save(fig, "fig_nrkdcc_delay_mechanism_evidence.png")


def plot_fdi_ftc() -> None:
    d = TF14_EXP / "data" / "diagnostics" / "E0" / "seed_2026" / "dlc_mixed_fault_noise_tf14_phase_role"
    ctrl = read_csv(d / "control_spread.csv")
    fault = read_csv(d / "fault.csv")
    switch = read_csv(d / "switch.csv")
    cert = read_csv(d / "certificate.csv")
    t_c = np.arange(len(ctrl)) * DT
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 6.0), sharex=False)
    axes = axes.ravel()

    ax = axes[0]
    if "active" in fault and "step" in fault:
        fault_active = np.asarray([as_bool(v) for v in fault["active"]], dtype=float)
        ax.plot(fault["step"].astype(float) * DT, fault_active, color=ALT, lw=1.1, label="fault active")
    if "fault_active" in ctrl:
        ax.plot(t_c, ctrl["fault_active"].astype(float), color=BASE, lw=1.1, ls="--", label="controller fault flag")
    if "fault_deficit_norm" in ctrl:
        ax2 = ax.twinx()
        ax2.plot(t_c, ctrl["fault_deficit_norm"].astype(float), color=OURS, lw=1.15, label="fault deficit norm")
        ax2.set_ylabel("")
        ax2.tick_params(colors=TEXT, labelsize=6.6)
        lines = ax.get_lines() + ax2.get_lines()
    else:
        lines = ax.get_lines()
    ax.set_ylabel("fault flag")
    ax.set_title("fault identification", loc="left", pad=2)
    style_ax(ax)
    clean_legend(ax, handles=lines, ncol=3)

    ax = axes[1]
    for col, color, lab in [
        ("fault_deficit_norm", ALT, "fault deficit"),
        ("redistributed_total_delta", OURS, "delta redistribution"),
        ("redistributed_total_ax", ABL, "ax redistribution"),
    ]:
        if col in ctrl:
            ax.plot(t_c, ctrl[col].astype(float), color=color, lw=1.2, label=lab)
    ax.set_title("FTC command", loc="left", pad=2)
    ax.set_ylabel("deficit / cmd.")
    style_ax(ax, zero=True)
    clean_legend(ax, ncol=3)

    ax = axes[2]
    for col, color, lab in [
        ("delta_spread", BASE, "delta spread"),
        ("ax_spread", OURS, "ax spread"),
        ("delta_mix", ABL, "delta mix"),
        ("ax_mix", ALT, "ax mix"),
    ]:
        if col in ctrl:
            ax.plot(t_c, ctrl[col].astype(float), color=color, lw=1.05, label=lab)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("control spread / trim")
    ax.set_title("correction decomposition", loc="left", pad=2)
    style_ax(ax, zero=True)
    clean_legend(ax, ncol=2)

    ax = axes[3]
    tc = cert["step"].astype(float).to_numpy() * DT
    ax.plot(tc, cert["V"].astype(float), color=BASE, lw=1.1, label="certificate V")
    if "tf14_global_mode" in ctrl:
        mode = ctrl["tf14_global_mode"].astype(str).eq("reconfigured_ftc_mpc").astype(float)
        ax2_mode = ax.twinx()
        ax2_mode.plot(t_c, mode, color=ALT, lw=0.95, ls="--", label="reconfigured mode")
        ax2_mode.set_ylim(-0.05, 1.05)
        ax2_mode.tick_params(colors=TEXT, labelsize=8.5)
    else:
        ax2_mode = None
    if "contraction_margin" in cert:
        if ax2_mode is None:
            ax2 = ax.twinx()
        else:
            ax2 = ax2_mode
        ax2.plot(tc, cert["contraction_margin"].astype(float), color=OURS, lw=1.0, label="margin")
        ax2.axhline(0.0, color=ALT, ls=":", lw=0.85, label="_nolegend_")
        lines = ax.get_lines() + ax2.get_lines()
        clean_legend(ax, handles=lines, ncol=3)
    else:
        clean_legend(ax, ncol=2)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("certificate V")
    ax.set_title("certificate/mode monitor", loc="left", pad=2)
    style_ax(ax)
    fig.subplots_adjust(top=0.84, bottom=0.10, left=0.065, right=0.985, hspace=0.78, wspace=0.36)
    save(fig, "fig_nrkdcc_fdi_ftc_timeline_layoutfix_20260528.png")


def plot_modewise_certificate() -> None:
    summary = read_csv(TF14_EXP / "data" / "tf14_remaining_summary.csv")
    rows = summary[
        (summary["experiment"].eq("E3"))
        & (summary["method"].eq("tf14_phase_role"))
        & (summary["scenario"].isin(["dlc_comm_noise_high", "dlc_mixed_fault_noise"]))
    ].copy()
    labels = ["high comm.", "mixed fault/noise"]
    ok = []
    margin = []
    for sc in ["dlc_comm_noise_high", "dlc_mixed_fault_noise"]:
        r = rows[rows["scenario"].eq(sc)].iloc[0]
        ok.append(float(r["certificate_ok_ratio_mean"]))
        margin.append(float(r["certificate_min_margin_mean"]))
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.15))
    x = np.arange(len(labels))
    axes[0].bar(x, ok, color=OURS, width=0.55)
    axes[0].set_ylim(0, 1.08)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=12)
    axes[0].set_ylabel("ok ratio")
    axes[0].set_title("pressure-mode certificate pass rate")
    style_ax(axes[0])
    axes[1].bar(x, margin, color=[GREEN if v >= 0 else ALT for v in margin], width=0.55)
    axes[1].axhline(0, color=ALT, lw=0.9, ls="--")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=12)
    axes[1].set_ylabel("minimum margin")
    axes[1].set_title("minimum positive margin")
    style_ax(axes[1])
    fig.suptitle("E3 pressure-mode Lyapunov/ISS certificate closure", y=1.03, color=TEXT, fontsize=12)
    save(fig, "fig_nrkdcc_modewise_certificate_closure.png")


def load_e0_rows() -> pd.DataFrame:
    rows = read_csv(TF14_EXP / "data" / "tf14_remaining_runs.csv")
    return rows[(rows["experiment"].eq("E0")) & (rows["seed"].astype(str).eq("2026"))].copy()


def plot_team_center_trajectory() -> None:
    rows = load_e0_rows()
    scenarios = [("dlc_comm_noise_high", "High communication degradation"), ("dlc_mixed_fault_noise", "Mixed fault/noise")]
    methods = ["baseline", "tf14_main", "tf14_phase_role"]
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.75), sharey=True)
    for ax, (sc, title) in zip(axes, scenarios):
        ax.axhline(0.0, color=REF, lw=1.0, ls=(0, (4, 2)), label="reference")
        for method in methods:
            row = rows[(rows["scenario"].eq(sc)) & (rows["method"].eq(method))].iloc[0]
            core = load_core(row["core_npz"])
            _, s, ey, _ = team_errors(core)
            ax.plot(s, ey, color=COLORS[method], lw=1.35, label=LABELS[method])
        ax.set_title(title)
        ax.set_xlabel("path progress s [m]")
        ax.set_ylabel("team lateral offset e_y [m]")
        style_ax(ax, zero=True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.00), ncol=4, frameon=False, fontsize=8.0)
    fig.suptitle("E0 representative team-center Frenet trajectory", y=0.91, color=TEXT, fontsize=12)
    fig.subplots_adjust(top=0.74)
    save(fig, "fig_nrkdcc_team_center_trajectory.png")


def plot_error_diagnostics() -> None:
    rows = load_e0_rows()
    scenarios = [("dlc_comm_noise_high", "High communication degradation"), ("dlc_mixed_fault_noise", "Mixed fault/noise")]
    methods = ["baseline", "tf14_main", "tf14_phase_role"]
    fig, axes = plt.subplots(3, 2, figsize=(10.0, 8.3), sharex=False)
    for col, (sc, title) in enumerate(scenarios):
        ax = axes[0, col]
        for method in methods:
            row = rows[(rows["scenario"].eq(sc)) & (rows["method"].eq(method))].iloc[0]
            core = load_core(row["core_npz"])
            t, _, ey, _ = team_errors(core)
            ax.plot(t, ey, color=COLORS[method], lw=1.15, label=LABELS[method])
        ax.set_title(f"{title}: team e_y")
        ax.set_ylabel("team e_y [m]")
        style_ax(ax, zero=True)

        ax = axes[1, col]
        for method in methods:
            row = rows[(rows["scenario"].eq(sc)) & (rows["method"].eq(method))].iloc[0]
            core = load_core(row["core_npz"])
            t, _, _, es = team_errors(core)
            ax.plot(t, es, color=COLORS[method], lw=1.15, label=LABELS[method])
        ax.set_title(f"{title}: team e_s")
        ax.set_ylabel("team e_s [m]")
        style_ax(ax, zero=True)

        for method, ls in [("baseline", "-"), ("tf14_phase_role", "-")]:
            row = rows[(rows["scenario"].eq(sc)) & (rows["method"].eq(method))].iloc[0]
            core = load_core(row["core_npz"])
            t, ev = vehicle_ey(core)
            ax = axes[2, col]
            for i, e in enumerate(ev):
                label = f"{LABELS[method]} v{i + 1}" if i == 0 else f"v{i + 1}"
                ax.plot(t, e, color=VEHICLE[i], lw=0.95 if method == "baseline" else 1.1, ls=":" if method == "baseline" else ls, alpha=0.62 if method == "baseline" else 0.95, label=label)
        axes[2, col].set_title(f"{title}: vehicle e_y")
        axes[2, col].set_ylabel("vehicle e_y [m]")
        axes[2, col].set_xlabel("time [s]")
        style_ax(axes[2, col], zero=True)
    axes[0, 0].legend(loc="upper center", bbox_to_anchor=(1.08, 1.42), ncol=3, frameon=False, fontsize=7.6)
    axes[2, 0].legend(loc="upper center", bbox_to_anchor=(1.08, -0.22), ncol=4, frameon=False, fontsize=6.8)
    fig.suptitle("E0 representative team and vehicle error diagnostics", y=1.02, color=TEXT, fontsize=12)
    save(fig, "fig_nrkdcc_error_diagnostics.png")


def plot_r42_speed_panel(scenario: str, speed: int, out_name: str) -> None:
    row = r42_speed_row(scenario)
    base = load_core(row["baseline_core_npz"])
    prop = load_core(row["proposed_core_npz"])
    fault_s = float(row["fault_start_s"]) if "fault_start_s" in row and math.isfinite(float(row["fault_start_s"])) and float(row["fault_start_s"]) < 1e8 else None
    b_fault_t = plotted_fault_time_from_s(base, fault_s)
    p_fault_t = plotted_fault_time_from_s(prop, fault_s)

    fig = plt.figure(figsize=(8.7, 9.0))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.05, 1.0, 1.1], hspace=0.52, wspace=0.28)
    ax_traj = fig.add_subplot(gs[0, :])
    ax_ey = fig.add_subplot(gs[1, 0])
    ax_es = fig.add_subplot(gs[1, 1])
    ax_vb = fig.add_subplot(gs[2, 0])
    ax_vp = fig.add_subplot(gs[2, 1])

    base_t, base_s, base_ey, base_es = team_errors(base)
    prop_t, prop_s, prop_ey, prop_es = team_errors(prop)
    for s, ey, label, color, ls in [
        (prop_s, prop_ey, "NR-KDCC", OURS, "-"),
        (base_s, base_ey, "AKE-M", BASE, (0, (4, 2))),
    ]:
        ax_traj.plot(s, ey, color=color, lw=1.35, ls=ls, label=label, zorder=3 if label == "AKE-M" else 2)
    ax_traj.axhline(0, color=REF, lw=1.0, ls=(0, (4, 2)), label="reference")
    traj_end = max(float(base_s[-1]), float(prop_s[-1])) if len(base_s) and len(prop_s) else None
    mark_fault_span(ax_traj, fault_s, traj_end)
    mark_fault_line(ax_traj, fault_s, ALT, label="fault start")
    ax_traj.set_xlabel("path progress s [m]")
    ax_traj.set_ylabel("team e_y [m]")
    ax_traj.set_title(f"Team-center Frenet trajectory, v={speed} m/s")
    ax_traj.legend(loc="upper center", bbox_to_anchor=(0.5, 1.28), ncol=4, frameon=False, fontsize=7.6)
    style_ax(ax_traj, zero=True)

    for t, ey, es, label, color, ls in [
        (prop_t, prop_ey, prop_es, "NR-KDCC", OURS, "-"),
        (base_t, base_ey, base_es, "AKE-M", BASE, (0, (4, 2))),
    ]:
        ax_ey.plot(t, ey, color=color, lw=1.2, ls=ls, label=label, zorder=3 if label == "AKE-M" else 2)
        ax_es.plot(t, es, color=color, lw=1.2, ls=ls, label=label, zorder=3 if label == "AKE-M" else 2)
    time_end = max(float(base_t[-1]), float(prop_t[-1])) if len(base_t) and len(prop_t) else None
    finite_fault_ts = [x for x in [b_fault_t, p_fault_t] if x is not None and math.isfinite(x)]
    mark_fault_span(ax_ey, min(finite_fault_ts) if finite_fault_ts else None, time_end)
    mark_fault_span(ax_es, min(finite_fault_ts) if finite_fault_ts else None, time_end)
    mark_fault_line(ax_ey, b_fault_t, BASE)
    mark_fault_line(ax_ey, p_fault_t, OURS)
    mark_fault_line(ax_es, b_fault_t, BASE)
    mark_fault_line(ax_es, p_fault_t, OURS)
    ax_ey.set_title("team lateral error")
    ax_ey.set_ylabel("team e_y [m]")
    ax_ey.set_xlabel("time [s]")
    style_ax(ax_ey, zero=True)
    ax_es.set_title("team longitudinal error")
    ax_es.set_ylabel("team e_s [m]")
    ax_es.set_xlabel("time [s]")
    style_ax(ax_es, zero=True)

    for ax, core, title, ft in [(ax_vb, base, "AKE-M vehicle e_y", b_fault_t), (ax_vp, prop, "NR-KDCC vehicle e_y", p_fault_t)]:
        t, ev = vehicle_ey(core)
        for i, e in enumerate(ev):
            ax.plot(t, e, color=VEHICLE[i], lw=1.0, label=f"v{i + 1}")
        mark_fault_span(ax, ft, float(t[-1]) if len(t) else None)
        mark_fault_line(ax, ft, ALT)
        ax.set_title(title)
        ax.set_xlabel("time [s]")
        ax.set_ylabel("vehicle e_y [m]")
        style_ax(ax, zero=True)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, frameon=False, fontsize=7.0)
    fig.suptitle(f"R42 same-path speed panel: {speed} m/s", y=0.995, color=TEXT, fontsize=12)
    save(fig, out_name)


def plot_r42_summary() -> None:
    metrics = read_csv(R42 / "data" / "architecture_case_metrics.csv")
    scenarios = ["s0_clean_v5", "s1_flt_v2", "s1_flt_v5", "s1_flt_v10", "s1_flt_v15", "s2_hpin_d5_10_v5"]
    labels = ["clean5", "fault2", "fault5", "fault10", "fault15", "hairpin5"]
    rows = [scenario_row(metrics, sc) for sc in scenarios]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.45), gridspec_kw={"width_ratios": [1.35, 1.1, 1.5]})
    x = np.arange(len(rows))
    w = 0.34
    axes[0].bar(x - w / 2, [float(r["baseline_rmse_ey_m"]) for r in rows], width=w, color=BASE, label="AKE-M")
    axes[0].bar(x + w / 2, [float(r["proposed_rmse_ey_m"]) for r in rows], width=w, color=OURS, label="NR-KDCC")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=20)
    axes[0].set_ylabel("RMSE |e_y| [m]")
    axes[0].set_title("scenario RMSE")
    axes[0].legend(loc="upper left", frameon=False, fontsize=7.5)
    style_ax(axes[0])

    gaps = [float(r["pointwise_max_gap"]) for r in rows]
    axes[1].bar(x, gaps, color=[GREEN if g <= 0 else ALT for g in gaps], width=0.58)
    axes[1].axhline(0, color=ALT, lw=0.85, ls="--")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=20)
    axes[1].set_ylabel("max(proposed abs - baseline abs) [m]")
    axes[1].set_title("pointwise non-inferiority")
    style_ax(axes[1])

    pw = read_csv(Path(scenario_row(metrics, "s2_hpin_d5_10_v5")["pointwise_csv"]))
    axes[2].plot(pw["s_m"], pw["baseline_abs_ey_error_m"], color=BASE, lw=1.25, label="AKE-M")
    axes[2].plot(pw["s_m"], pw["proposed_abs_ey_error_m"], color=OURS, lw=1.25, label="NR-KDCC")
    axes[2].fill_between(pw["s_m"], pw["proposed_abs_ey_error_m"], pw["baseline_abs_ey_error_m"], where=pw["proposed_abs_ey_error_m"] <= pw["baseline_abs_ey_error_m"], color=OURS, alpha=0.11)
    axes[2].set_xlabel("path progress s [m]")
    axes[2].set_ylabel("|e_y| [m]")
    axes[2].set_title("hairpin high-delay pointwise trace")
    axes[2].legend(loc="upper left", frameon=False, fontsize=7.5)
    style_ax(axes[2])
    fig.suptitle("R42 upper/lower communication restructure and speed-gated validation", y=1.02, color=TEXT, fontsize=12)
    save(fig, "fig_nrkdcc_r42_pointwise_summary.png", pdf=True)


def plot_ablation_summaries() -> None:
    mixed = pd.DataFrame(
        [
            ("full", 0.0408, 0.4679, 0.0550, 0.99995),
            ("w/o comm", 0.0414, 0.5068, 0.4294, 0.78555),
            ("w/o delay", 0.0408, 0.4678, 0.0556, 0.99995),
            ("w/o stable", 0.0388, 0.4677, 0.0560, 0.99995),
            ("w/o PPC", 0.0660, 12.9301, 0.1259, 0.28722),
            ("ZOH-cons.", 0.0970, 14.0191, 0.3324, 0.17739),
        ],
        columns=["method", "lat", "long", "conn", "cert"],
    )
    mixed_labels = ["full", "no\ncomm", "no\ndelay", "no\nstab.", "no\nPPC", "ZOH"]
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.65))
    for ax, col, title in zip(axes.ravel(), ["lat", "long", "conn", "cert"], ["lateral RMSE", "longitudinal RMSE", "connection utilization", "certificate ok"]):
        vals = mixed[col].to_numpy(float)
        ax.bar(np.arange(len(mixed)), vals, color=[OURS if m == "full" else BASE if m.startswith("w/o") else ALT for m in mixed["method"]])
        ax.set_xticks(np.arange(len(mixed)))
        ax.set_xticklabels(mixed_labels, rotation=0, ha="center", fontsize=7.2)
        ax.set_title(title, fontsize=9.3, pad=5)
        if col == "long":
            ax.set_yscale("log")
        style_ax(ax)
        ax.tick_params(axis="x", pad=2)
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.105, top=0.935, wspace=0.20, hspace=0.48)
    save(fig, "fig_nrkdcc_mixed_ablation_summary.png", pdf=True)

    comm = pd.DataFrame(
        [
            ("full", 0.0425, 0.4709, 0.0446),
            ("w/o comm", 0.0459, 0.5399, 0.4384),
            ("w/o delay", 0.0426, 0.4709, 0.0460),
            ("ZOH-cons.", 0.1037, 14.1242, 0.3649),
        ],
        columns=["method", "lat", "long", "conn"],
    )
    comm_labels = ["full", "no\ncomm", "no\ndelay", "ZOH"]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.7))
    for ax, col, title in zip(axes, ["lat", "long", "conn"], ["lateral RMSE", "longitudinal RMSE", "connection utilization"]):
        ax.bar(np.arange(len(comm)), comm[col].to_numpy(float), color=[OURS, BASE, BASE, ALT])
        ax.set_xticks(np.arange(len(comm)))
        ax.set_xticklabels(comm_labels, rotation=0, ha="center", fontsize=7.2)
        ax.set_title(title, fontsize=9.3, pad=5)
        if col == "long":
            ax.set_yscale("log")
        style_ax(ax)
        ax.tick_params(axis="x", pad=2)
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.17, top=0.86, wspace=0.28)
    save(fig, "fig_nrkdcc_comm_ablation_summary.png", pdf=True)


def plot_certificate_summary() -> None:
    df = pd.DataFrame(
        [
            ("nominal clean", 0.360, -0.0224),
            ("high comm.", 1.000, 0.0049),
            ("single fault", 0.799, -0.0111),
            ("mixed", 1.000, 0.0033),
        ],
        columns=["scenario", "ok", "margin"],
    )
    scenario_labels = ["clean", "high-comm", "fault", "mixed"]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.75))
    x = np.arange(len(df))
    axes[0].bar(x, df["ok"], color=[BASE, OURS, BASE, OURS], width=0.55)
    axes[0].set_ylim(0, 1.08)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(scenario_labels, rotation=0, ha="center", fontsize=7.2)
    axes[0].set_ylabel("certificate ok ratio")
    axes[0].set_title("ok ratio", fontsize=9.3, pad=5)
    style_ax(axes[0])
    axes[1].bar(x, df["margin"], color=[ALT if v < 0 else GREEN for v in df["margin"]], width=0.55)
    axes[1].axhline(0, color=ALT, ls="--", lw=0.9)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(scenario_labels, rotation=0, ha="center", fontsize=7.2)
    axes[1].set_ylabel("minimum margin")
    axes[1].set_title("minimum margin", fontsize=9.3, pad=5)
    style_ax(axes[1])
    fig.subplots_adjust(left=0.095, right=0.985, bottom=0.17, top=0.86, wspace=0.24)
    save(fig, "fig_nrkdcc_certificate_summary.png", pdf=True)


def plot_connection_force_audit() -> None:
    df = pd.DataFrame(
        [
            ("high comm.", "AKE-M", 0.3308, 1315.4),
            ("high comm.", "NR-KDCC", 0.0447, 2212.7),
            ("mixed", "AKE-M", 0.3021, 1326.8),
            ("mixed", "NR-KDCC", 0.0501, 2171.1),
        ],
        columns=["scenario", "method", "conn", "force"],
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.75))
    for ax, col, title, ylabel in [
        (axes[0], "conn", "connection risk", "max utilization"),
        (axes[1], "force", "payload force cost", "peak force [N]"),
    ]:
        x = np.arange(2)
        vals_b = [float(df[(df.scenario.eq(sc)) & (df.method.eq("AKE-M"))][col].iloc[0]) for sc in ["high comm.", "mixed"]]
        vals_o = [float(df[(df.scenario.eq(sc)) & (df.method.eq("NR-KDCC"))][col].iloc[0]) for sc in ["high comm.", "mixed"]]
        ax.bar(x - 0.18, vals_b, width=0.34, color=BASE, label="AKE-M")
        ax.bar(x + 0.18, vals_o, width=0.34, color=OURS, label="NR-KDCC")
        ax.set_xticks(x)
        ax.set_xticklabels(["high comm.", "mixed"])
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=9.3, pad=5)
        style_ax(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.99), ncol=2, frameon=False, fontsize=7.6, handlelength=1.4, columnspacing=1.4)
    fig.subplots_adjust(left=0.095, right=0.985, bottom=0.16, top=0.78, wspace=0.24)
    save(fig, "fig_nrkdcc_connection_force_audit.png", pdf=True)


def main() -> None:
    plot_koopman_training()
    plot_koopman_prediction()
    plot_dim_ablation()
    plot_delay_mechanism()
    plot_fdi_ftc()
    plot_modewise_certificate()
    plot_team_center_trajectory()
    plot_error_diagnostics()
    plot_r42_speed_panel("s1_flt_v2", 2, "fig_nrkdcc_speed_2mps_panel.png")
    plot_r42_speed_panel("s1_flt_v5", 5, "fig_nrkdcc_speed_5mps_panel.png")
    plot_r42_speed_panel("s1_flt_v10", 10, "fig_nrkdcc_speed_10mps_panel.png")
    plot_r42_speed_panel("s1_flt_v15", 15, "fig_nrkdcc_speed_15mps_panel.png")
    plot_r42_speed_panel("s2_hpin_d5_10_v5", 5, "fig_nrkdcc_hairpin_5mps_lateral_priority_panel.png")
    plot_r42_summary()
    plot_ablation_summaries()
    plot_certificate_summary()
    plot_connection_force_audit()
    print(json.dumps({"updated_figures": 18, "figure_dir": str(FIG)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

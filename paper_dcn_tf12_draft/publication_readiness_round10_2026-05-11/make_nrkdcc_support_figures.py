from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
STAGE5_DATA = ROOT / "tf14_stage5_phase_role_scenarios_20260507" / "data"
TF13_DATA = ROOT / "paper_dcn_tf12_draft" / "data_tf13"
ROUND10 = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11"
GAP_CLOSURE = ROOT / "tf14_final_gap_closure_20260509"
REMAINING = ROOT / "tf14_remaining_experiments_20260509"
OUT = Path(__file__).resolve().parent / "nrkdcc_support_figures"
FIG_DIR = OUT / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "ink": "#243B53",
    "axis": "#5E7184",
    "grid": "#E6EDF5",
    "ref": "#4F6478",
    "baseline": "#7B8794",
    "nr_worole": "#D97732",
    "nrkdcc": "#008C8C",
    "event": "#B6465F",
    "shade": "#F4C7D4",
    "v0": "#2F80ED",
    "v1": "#D97732",
    "v2": "#008C8C",
    "v3": "#C879A8",
}

METHODS = {
    "baseline": ("AKE-M", COLORS["baseline"]),
    "tf14_main": ("NR-KDCC w/o role schedule", COLORS["nr_worole"]),
    "tf14_phase_role": ("NR-KDCC", COLORS["nrkdcc"]),
}

SCENARIOS = {
    "sine_comm_noise_high": "High communication degradation",
    "sine_mixed_fault_noise": "Mixed fault/noise",
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.edgecolor": COLORS["axis"],
        "axes.labelcolor": COLORS["ink"],
        "axes.titlecolor": COLORS["ink"],
        "xtick.color": COLORS["ink"],
        "ytick.color": COLORS["ink"],
        "text.color": COLORS["ink"],
        "axes.linewidth": 0.9,
        "axes.unicode_minus": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def _load_npz(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as z:
        return {k: np.asarray(z[k]) for k in z.files}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _to_float(value: object, default: float = np.nan) -> float:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        out = float(text)
        return out if np.isfinite(out) else default
    except Exception:
        return default


def _load_stage5_core(scenario: str, method: str) -> Dict[str, np.ndarray]:
    path = STAGE5_DATA / f"{scenario}_{method}_core_arrays.npz"
    if not path.exists():
        raise FileNotFoundError(path)
    return _load_npz(path)


def _load_sine_reference() -> Tuple[np.ndarray, np.ndarray]:
    ref_path = TF13_DATA / "tf13_scenario_sine_team_center_traj.npz"
    if ref_path.exists():
        data = _load_npz(ref_path)
        return np.asarray(data["x_ref"], dtype=float), np.asarray(data["y_ref"], dtype=float)
    x = np.linspace(0.0, 60.0, 1001)
    y = 0.85 * np.exp(-0.5 * ((x - 18.0) / 5.0) ** 2) - 0.85 * np.exp(-0.5 * ((x - 42.0) / 5.0) ** 2)
    return x, y


def _global_from_sine_state(state: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x_ref, y_ref = _load_sine_reference()
    s = np.clip(np.asarray(state[:, 0], dtype=float), float(x_ref[0]), float(x_ref[-1]))
    y0 = np.interp(s, x_ref, y_ref)
    return s, y0 + np.asarray(state[:, 1], dtype=float)


def _team_series(scenario: str, method: str) -> Dict[str, np.ndarray]:
    data = _load_stage5_core(scenario, method)
    team = np.asarray(data["team_state_hist"], dtype=float)
    ref = np.asarray(data["ref_team_hist"], dtype=float)
    n = min(team.shape[0], ref.shape[0])
    x, y = _global_from_sine_state(team[:n])
    xr, yr = _global_from_sine_state(ref[:n])
    return {
        "t": np.arange(n, dtype=float) * 0.02,
        "x": x,
        "y": y,
        "x_ref": xr,
        "y_ref": yr,
        "ey": team[:n, 1] - ref[:n, 1],
        "es": team[:n, 0] - ref[:n, 0],
    }


def _vehicle_errors(scenario: str, method: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    data = _load_stage5_core(scenario, method)
    actual = np.asarray(data["xt_actual_vehicles"], dtype=float)
    ref = np.asarray(data["ref_vehicle_histories"], dtype=float)
    n = min(actual.shape[1], ref.shape[1])
    t = np.arange(n, dtype=float) * 0.02
    ey = actual[:, :n, 1] - ref[:, :n, 1]
    es = actual[:, :n, 0] - ref[:, :n, 0]
    return t, ey, es


def _style(ax: plt.Axes) -> None:
    ax.grid(True, color=COLORS["grid"], linewidth=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["axis"])
    ax.spines["bottom"].set_color(COLORS["axis"])


def _save(fig: plt.Figure, name: str, *, rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)) -> None:
    fig.tight_layout(rect=rect)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(FIG_DIR / f"{name}.{ext}", dpi=600 if ext == "png" else None, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _top_legend(fig: plt.Figure, handles, labels, *, ncol: int) -> None:
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.015),
        ncol=ncol,
        frameon=False,
        handlelength=2.6,
        columnspacing=1.15,
        handletextpad=0.45,
        borderaxespad=0.0,
    )


def figure_team_center_trajectory() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.55), sharey=True)
    x_ref, y_ref = _load_sine_reference()
    for ax, (scenario, title) in zip(axes, SCENARIOS.items()):
        ax.plot(x_ref, y_ref, color=COLORS["ref"], linestyle=(0, (4, 2)), linewidth=1.25, label="reference")
        for method, (label, color) in METHODS.items():
            series = _team_series(scenario, method)
            ax.plot(series["x"], series["y"], color=color, linewidth=1.45, label=label)
        ax.set_title(title)
        ax.set_xlabel(r"$x$ [m]")
        _style(ax)
    axes[0].set_ylabel(r"$y$ [m]")
    handles, labels = axes[0].get_legend_handles_labels()
    _top_legend(fig, handles, labels, ncol=4)
    _save(fig, "fig_nrkdcc_team_center_trajectory", rect=(0.0, 0.0, 1.0, 0.88))


def figure_team_center_errors() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.5), sharex="col")
    for col, (scenario, title) in enumerate(SCENARIOS.items()):
        for method, (label, color) in METHODS.items():
            series = _team_series(scenario, method)
            axes[0, col].plot(series["t"], series["ey"], color=color, linewidth=1.15, label=label)
            axes[1, col].plot(series["t"], series["es"], color=color, linewidth=1.15, label=label)
        axes[0, col].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        axes[1, col].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        axes[0, col].set_title(title)
        axes[1, col].set_xlabel("time [s]")
        _style(axes[0, col])
        _style(axes[1, col])
    axes[0, 0].set_ylabel(r"team $e_y$ [m]")
    axes[1, 0].set_ylabel(r"team $e_s$ [m]")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    _top_legend(fig, handles, labels, ncol=3)
    _save(fig, "fig_nrkdcc_team_center_errors", rect=(0.0, 0.0, 1.0, 0.91))


def figure_vehicle_lateral_errors() -> None:
    scenario = "sine_mixed_fault_noise"
    fig, axes = plt.subplots(2, 1, figsize=(3.55, 4.35), sharex=True, sharey=True)
    vehicle_colors = [COLORS[f"v{i}"] for i in range(4)]
    for ax, method, title in [
        (axes[0], "baseline", "AKE-M per-vehicle lateral error"),
        (axes[1], "tf14_phase_role", "NR-KDCC per-vehicle lateral error"),
    ]:
        t, ey, _ = _vehicle_errors(scenario, method)
        for i in range(min(4, ey.shape[0])):
            ax.plot(t, ey[i], color=vehicle_colors[i], linewidth=1.0, label=f"V{i}")
        ax.axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        ax.axvspan(5.0, min(float(t[-1]), 20.0), color=COLORS["shade"], alpha=0.16, zorder=0)
        ax.axvline(5.0, color=COLORS["event"], linestyle=(0, (4, 2)), linewidth=1.0)
        ax.set_title(title)
        _style(ax)
    axes[0].set_ylabel(r"vehicle $e_y$ [m]")
    axes[1].set_ylabel(r"vehicle $e_y$ [m]")
    axes[1].set_xlabel("time [s]")
    handles, labels = axes[1].get_legend_handles_labels()
    _top_legend(fig, handles, labels, ncol=4)
    _save(fig, "fig_nrkdcc_vehicle_lateral_errors", rect=(0.0, 0.0, 1.0, 0.90))


def figure_error_diagnostics() -> None:
    fig = plt.figure(figsize=(7.2, 6.45))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.95], hspace=0.72, wspace=0.24)
    axes = np.array([[fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])],
                     [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])],
                     [fig.add_subplot(gs[2, 0]), fig.add_subplot(gs[2, 1])]], dtype=object)

    for col, (scenario, title) in enumerate(SCENARIOS.items()):
        for method, (label, color) in METHODS.items():
            series = _team_series(scenario, method)
            axes[0, col].plot(series["t"], series["ey"], color=color, linewidth=1.1, label=label)
            axes[1, col].plot(series["t"], series["es"], color=color, linewidth=1.1, label=label)
        axes[0, col].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        axes[1, col].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        axes[0, col].set_title(title)
        _style(axes[0, col])
        _style(axes[1, col])
    axes[0, 0].set_ylabel(r"team $e_y$ [m]")
    axes[1, 0].set_ylabel(r"team $e_s$ [m]")

    scenario = "sine_mixed_fault_noise"
    vehicle_colors = [COLORS[f"v{i}"] for i in range(4)]
    vehicle_handles = []
    for ax, method, title in [
        (axes[2, 0], "baseline", r"AKE-M vehicle $e_y$"),
        (axes[2, 1], "tf14_phase_role", r"NR-KDCC vehicle $e_y$"),
    ]:
        t, ey, _ = _vehicle_errors(scenario, method)
        for i in range(min(4, ey.shape[0])):
            line, = ax.plot(t, ey[i], color=vehicle_colors[i], linewidth=0.95, label=f"V{i}")
            if len(vehicle_handles) < 4:
                vehicle_handles.append(line)
        ax.axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
        ax.axvspan(5.0, min(float(t[-1]), 20.0), color=COLORS["shade"], alpha=0.14, zorder=0)
        ax.axvline(5.0, color=COLORS["event"], linestyle=(0, (4, 2)), linewidth=0.9)
        ax.set_title(title, pad=10)
        ax.set_xlabel("time [s]")
        _style(ax)
    axes[2, 0].set_ylabel(r"vehicle $e_y$ [m]")

    method_handles, method_labels = axes[0, 0].get_legend_handles_labels()
    _top_legend(fig, method_handles, method_labels, ncol=3)
    fig.legend(
        vehicle_handles,
        [f"V{i}" for i in range(len(vehicle_handles))],
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.006),
        ncol=4,
        handlelength=1.8,
        columnspacing=1.2,
        handletextpad=0.35,
    )
    _save(fig, "fig_nrkdcc_error_diagnostics", rect=(0.0, 0.08, 1.0, 0.93))


def figure_mixed_ablation_summary() -> None:
    labels = ["full\nNR-KDCC", "w/o\ncomm-aware", "w/o\ndelay", "w/o\nstable proj.", "w/o\nPPC guard", "ZOH"]
    lat = np.array([0.0408, 0.0414, 0.0408, 0.0388, 0.0660, 0.0970])
    long = np.array([0.4679, 0.5068, 0.4678, 0.4677, 12.9301, 14.0191])
    conn = np.array([0.0550, 0.4294, 0.0556, 0.0560, 0.1259, 0.3324])
    ok = np.array([0.99995, 0.78555, 0.99995, 0.99995, 0.28722, 0.17739])
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.2))
    panels = [
        (lat, "lateral RMSE [m]", 0.11),
        (long, "longitudinal RMSE [m]", 15.0),
        (conn, "connection max utilization", 0.48),
        (ok, "certificate ok ratio", 1.05),
    ]
    for ax, (vals, title, ymax) in zip(axes.flat, panels):
        colors = [COLORS["nrkdcc"]] + [COLORS["nr_worole"]] * 4 + [COLORS["event"]]
        ax.bar(x, vals, color=colors, width=0.68)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=22, ha="right")
        ax.set_ylim(0.0, ymax)
        _style(ax)
    _save(fig, "fig_nrkdcc_mixed_ablation_summary")


def figure_comm_ablation_summary() -> None:
    labels = ["full\nNR-KDCC", "w/o\ncomm-aware", "w/o\ndelay", "ZOH"]
    lat = np.array([0.0425, 0.0459, 0.0426, 0.1037])
    long = np.array([0.4709, 0.5399, 0.4709, 14.1242])
    conn = np.array([0.0446, 0.4384, 0.0460, 0.3649])
    success = np.array([1.0, 1.0, 1.0, 0.0])
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.0))
    panels = [
        (lat, "lateral RMSE [m]", 0.12),
        (long, "longitudinal RMSE [m]", 15.0),
        (conn, "connection max utilization", 0.50),
        (success, "full-path success rate", 1.05),
    ]
    for ax, (vals, title, ymax) in zip(axes.flat, panels):
        colors = [COLORS["nrkdcc"], COLORS["event"], COLORS["nr_worole"], COLORS["baseline"]]
        ax.bar(x, vals, color=colors, width=0.64)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=18, ha="right")
        ax.set_ylim(0.0, ymax)
        _style(ax)
    _save(fig, "fig_nrkdcc_comm_ablation_summary")


def figure_certificate_summary() -> None:
    labels = ["nominal\nclean", "high comm.\nnoise", "single\nfault", "mixed\nfault/noise"]
    ok = np.array([0.360, 1.000, 0.799, 1.000])
    margin = np.array([-0.0224, 0.0049, -0.0111, 0.0033])
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    axes[0].bar(x, ok, color=[COLORS["baseline"], COLORS["nrkdcc"], COLORS["nr_worole"], COLORS["nrkdcc"]], width=0.64)
    axes[0].set_title("certificate ok ratio")
    axes[0].set_ylim(0.0, 1.05)
    axes[1].bar(x, margin, color=[COLORS["event"] if v < 0 else COLORS["nrkdcc"] for v in margin], width=0.64)
    axes[1].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
    axes[1].set_title("minimum certificate margin")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=18, ha="right")
        _style(ax)
    _save(fig, "fig_nrkdcc_certificate_summary")


def figure_connection_force_audit() -> None:
    groups = ["high comm.", "mixed"]
    methods = ["AKE-M", "NR-KDCC"]
    conn = np.array([[0.3308, 0.0447], [0.3021, 0.0501]])
    force = np.array([[1315.4, 2212.7], [1326.8, 2171.1]])
    x = np.arange(len(groups))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    for ax, vals, title, ylabel in [
        (axes[0], conn, "connection max utilization", "ratio"),
        (axes[1], force, "payload force peak", "force metric"),
    ]:
        ax.bar(x - width / 2, vals[:, 0], width=width, color=COLORS["baseline"], label=methods[0])
        ax.bar(x + width / 2, vals[:, 1], width=width, color=COLORS["nrkdcc"], label=methods[1])
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(groups)
        _style(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    _top_legend(fig, handles, labels, ncol=2)
    _save(fig, "fig_nrkdcc_connection_force_audit", rect=(0.0, 0.0, 1.0, 0.86))


def figure_koopman_prediction_evidence() -> None:
    rows = _read_csv(GAP_CLOSURE / "source" / "E1_koopman_prediction_validation.csv")
    models = ["linear", "bilinear", "stable_bilinear"]
    labels = {"linear": "linear", "bilinear": "bilinear", "stable_bilinear": "stable bilinear"}
    colors = {"linear": COLORS["baseline"], "bilinear": COLORS["nr_worole"], "stable_bilinear": COLORS["nrkdcc"]}

    states = ["s", "e_y", "e_psi", "v_x", "v_y", "r"]
    one_step = {
        model: [
            _to_float(next((r.get("one_step_rmse") for r in rows if r.get("model") == model and r.get("state") == state), ""))
            for state in states
        ]
        for model in models
    }
    all_horizons = sorted({_to_float(r.get("horizon")) for r in rows if str(r.get("horizon", "")).strip()}, key=float)
    horizons = [h for h in all_horizons if h <= 12]

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55))
    x = np.arange(len(states))
    width = 0.24
    for j, model in enumerate(models):
        axes[0].bar(x + (j - 1) * width, one_step[model], width=width, color=colors[model], label=labels[model])
    axes[0].set_title("one-step prediction RMSE")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(states, rotation=25, ha="right")
    axes[0].set_ylabel("RMSE")
    _style(axes[0])

    for model in models:
        ys = []
        sem = []
        for h in horizons:
            row = next((r for r in rows if r.get("model") == model and _to_float(r.get("horizon")) == h), None)
            ys.append(_to_float(row.get("rollout_mean_l2") if row else ""))
            sem.append(_to_float(row.get("rollout_sem_l2") if row else ""))
        axes[1].plot(horizons, ys, color=colors[model], linewidth=1.25, marker="o", markersize=2.2, label=labels[model])
        lower = np.maximum(np.asarray(ys) - 1.96 * np.asarray(sem), 0.0)
        upper = np.asarray(ys) + 1.96 * np.asarray(sem)
        axes[1].fill_between(horizons, lower, upper, color=colors[model], alpha=0.10, linewidth=0)
    axes[1].axvline(12, color=COLORS["event"], linestyle=(0, (4, 2)), linewidth=0.9)
    axes[1].set_title("control-window rollout")
    axes[1].set_xlabel("horizon step")
    axes[1].set_ylabel("mean L2 error, 95% CI")
    _style(axes[1])

    spectral = next((r for r in rows if str(r.get("spectral_radius_before", "")).strip()), None)
    before = _to_float(spectral.get("spectral_radius_before") if spectral else "")
    after = _to_float(spectral.get("spectral_radius_after") if spectral else "")
    axes[2].bar([0, 1], [before, after], color=[COLORS["event"], COLORS["nrkdcc"]], width=0.56)
    axes[2].axhline(1.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
    axes[2].set_xticks([0, 1])
    axes[2].set_xticklabels(["before\nprojection", "after\nprojection"])
    axes[2].set_title("spectral projection audit")
    axes[2].set_ylim(min(0.992, np.nanmin([before, after]) - 0.004), max(1.010, np.nanmax([before, after]) + 0.004))
    _style(axes[2])

    handles, legend_labels = axes[0].get_legend_handles_labels()
    _top_legend(fig, handles, legend_labels, ncol=3)
    _save(fig, "fig_nrkdcc_koopman_prediction_evidence", rect=(0.0, 0.0, 1.0, 0.86))


def figure_koopman_training_loss() -> None:
    loss_path = TF13_DATA / "tf13_fig02_loss_curve_data.npz"
    data = _load_npz(loss_path)
    train = np.asarray(data["train_hist"], dtype=float)
    val = np.asarray(data["val_hist"], dtype=float)
    epochs = np.arange(train.shape[0], dtype=int)
    loss_names = ["total", "prediction", "lifted"]
    styles = ["-", "--", ":"]

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.65))
    for idx, (name, style) in enumerate(zip(loss_names, styles)):
        axes[0].semilogy(epochs, train[:, idx], linestyle=style, color=COLORS["nr_worole"], linewidth=1.2, label=f"train {name}")
        axes[0].semilogy(epochs, val[:, idx], linestyle=style, color=COLORS["nrkdcc"], linewidth=1.2, label=f"val {name}")
    axes[0].set_title("Koopman lifting-network loss")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("loss")
    _style(axes[0])

    x = np.arange(len(loss_names))
    width = 0.34
    final_train = train[-10:].mean(axis=0)
    final_val = val[-10:].mean(axis=0)
    axes[1].bar(x - width / 2, final_train, width=width, color=COLORS["nr_worole"], label="train, last-10 mean")
    axes[1].bar(x + width / 2, final_val, width=width, color=COLORS["nrkdcc"], label="val, last-10 mean")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(loss_names, rotation=15, ha="right")
    axes[1].set_title("final convergence gap")
    axes[1].set_ylabel("loss")
    _style(axes[1])

    handles, legend_labels = axes[0].get_legend_handles_labels()
    _top_legend(fig, handles, legend_labels, ncol=3)
    _save(fig, "fig_nrkdcc_koopman_training_loss", rect=(0.0, 0.0, 1.0, 0.82))


def figure_delay_mechanism_evidence() -> None:
    diag_dir = REMAINING / "data" / "diagnostics" / "E0" / "seed_2026" / "dlc_mixed_fault_noise_tf14_phase_role"
    comm_rows = _read_csv(diag_dir / "comm.csv")
    t = np.asarray([_to_float(r.get("step"), 0.0) * 0.02 for r in comm_rows], dtype=float)
    delay = np.asarray([_to_float(r.get("mean_delay_steps")) for r in comm_rows], dtype=float)
    loss = np.asarray([_to_float(r.get("loss_ratio")) for r in comm_rows], dtype=float)
    tighten = np.asarray([_to_float(r.get("tighten_frac")) for r in comm_rows], dtype=float)
    quality = np.asarray([_to_float(r.get("quality_global")) for r in comm_rows], dtype=float)

    summary_rows = _read_csv(ROUND10 / "e2_n20_comm_noise_key_ablation_merged" / "data" / "tf14_remaining_summary.csv")
    method_rows = {r.get("method"): r for r in summary_rows if r.get("scenario") == "sine_comm_noise_high"}
    metrics = [
        ("lat RMSE", "rmse_lat_mean_mean"),
        ("long RMSE", "rmse_long_mean_mean"),
        ("conn util.", "connection_max_utilization_mean"),
        ("cert ok", "certificate_ok_ratio_mean"),
    ]
    full = method_rows.get("full_tf14", {})
    no_delay = method_rows.get("no_delay_compensation", {})

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    axes[0].plot(t, delay, color=COLORS["nr_worole"], linewidth=1.0, label="mean delay [steps]")
    axes[0].plot(t, loss, color=COLORS["event"], linewidth=1.0, label="loss ratio")
    axes[0].plot(t, tighten, color=COLORS["nrkdcc"], linewidth=1.0, label="constraint tightening")
    axes[0].plot(t, quality, color=COLORS["baseline"], linewidth=0.9, label="link quality")
    axes[0].set_title("online network-quality trace")
    axes[0].set_xlabel("time [s]")
    axes[0].set_ylabel("trace value")
    _style(axes[0])

    x = np.arange(len(metrics))
    width = 0.34
    full_vals = np.asarray([_to_float(full.get(field)) for _, field in metrics], dtype=float)
    no_delay_vals = np.asarray([_to_float(no_delay.get(field)) for _, field in metrics], dtype=float)
    axes[1].bar(x - width / 2, full_vals, width=width, color=COLORS["nrkdcc"], label="full NR-KDCC")
    axes[1].bar(x + width / 2, no_delay_vals, width=width, color=COLORS["nr_worole"], label="w/o delay")
    axes[1].set_title("paired n=20 delay-ablation boundary")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([name for name, _ in metrics], rotation=20, ha="right")
    axes[1].set_yscale("symlog", linthresh=0.2)
    _style(axes[1])

    handles0, labels0 = axes[0].get_legend_handles_labels()
    handles1, labels1 = axes[1].get_legend_handles_labels()
    fig.legend(handles0 + handles1, labels0 + labels1, loc="upper center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False, handlelength=2.0, columnspacing=1.0)
    _save(fig, "fig_nrkdcc_delay_mechanism_evidence", rect=(0.0, 0.0, 1.0, 0.82))


def figure_fdi_ftc_timeline() -> None:
    diag_dir = REMAINING / "data" / "diagnostics" / "E0" / "seed_2026" / "dlc_mixed_fault_noise_tf14_phase_role"
    fault_rows = _read_csv(diag_dir / "fault.csv")
    switch_rows = _read_csv(diag_dir / "switch.csv")
    cert_rows = _read_csv(diag_dir / "certificate.csv")
    n = min(len(fault_rows), len(switch_rows), len(cert_rows))
    t = np.asarray([_to_float(fault_rows[i].get("step"), 0.0) * 0.02 for i in range(n)], dtype=float)
    active = np.asarray([1.0 if str(fault_rows[i].get("active")).lower() == "true" else 0.0 for i in range(n)], dtype=float)
    deficit = np.asarray([_to_float(fault_rows[i].get("deficit_norm"), 0.0) for i in range(n)], dtype=float)
    confidence = np.asarray([_to_float(fault_rows[i].get("diagnosed_confidence"), 0.0) for i in range(n)], dtype=float)
    mode = np.asarray([0.0 if switch_rows[i].get("global_mode") == "nominal_koopman_mpc" else 1.0 for i in range(n)], dtype=float)
    red_ax = np.asarray([_to_float(switch_rows[i].get("redistributed_total_ax"), 0.0) for i in range(n)], dtype=float)
    red_delta = np.asarray([_to_float(switch_rows[i].get("redistributed_total_delta"), 0.0) for i in range(n)], dtype=float)
    margin = np.asarray([_to_float(cert_rows[i].get("contraction_margin")) for i in range(n)], dtype=float)
    margin[~np.isfinite(margin)] = np.nan

    fault_start = t[np.argmax(active > 0.5)] if np.any(active > 0.5) else np.nan
    diagnosis_idx = next((i for i in range(n) if fault_rows[i].get("diagnosed_mode") not in {"", "nominal", None}), None)
    switch_idx = next((i for i in range(n) if switch_rows[i].get("global_mode") != "nominal_koopman_mpc"), None)
    diagnosis_t = t[diagnosis_idx] if diagnosis_idx is not None else np.nan
    switch_t = t[switch_idx] if switch_idx is not None else np.nan

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 4.8), sharex=True)
    axes[0].plot(t, deficit, color=COLORS["event"], linewidth=1.0, label="fault deficit norm")
    axes[0].plot(t, confidence, color=COLORS["nrkdcc"], linewidth=1.0, label="diagnosis confidence")
    axes[0].fill_between(t, 0.0, active * max(0.2, np.nanmax(deficit)), color=COLORS["shade"], alpha=0.18, label="injected fault active")
    axes[0].set_ylabel("FDI signal")
    axes[0].set_title("FDI detection and FTC switching timeline")

    axes[1].step(t, mode, where="post", color=COLORS["nrkdcc"], linewidth=1.15, label="FTC mode")
    axes[1].plot(t, red_ax, color=COLORS["nr_worole"], linewidth=1.0, label="redistributed $a_x$")
    axes[1].plot(t, red_delta, color=COLORS["baseline"], linewidth=1.0, label="redistributed $\\delta$")
    axes[1].set_yticks([0, 1])
    axes[1].set_yticklabels(["nominal", "FTC"])
    axes[1].set_ylabel("switch/redist.")

    axes[2].plot(t, margin, color=COLORS["nrkdcc"], linewidth=0.95, label="certificate margin")
    axes[2].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
    axes[2].set_ylabel("margin")
    axes[2].set_xlabel("time [s]")

    for ax in axes:
        for event_t, text, color in [
            (fault_start, "fault", COLORS["event"]),
            (diagnosis_t, "FDI", COLORS["nr_worole"]),
            (switch_t, "FTC", COLORS["nrkdcc"]),
        ]:
            if np.isfinite(event_t):
                ax.axvline(event_t, color=color, linestyle=(0, (4, 2)), linewidth=0.9)
        _style(ax)
    handles, labels = [], []
    for ax in axes:
        h, l = ax.get_legend_handles_labels()
        handles += h
        labels += l
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.018), ncol=4, frameon=False, handlelength=2.0, columnspacing=0.9)
    _save(fig, "fig_nrkdcc_fdi_ftc_timeline", rect=(0.0, 0.0, 1.0, 0.89))


def figure_modewise_certificate_closure() -> None:
    rows = _read_csv(GAP_CLOSURE / "source" / "E3_certificate_mode_margin_stats.csv")
    labels = []
    ok_vals = []
    margins = []
    bounds = []
    for row in rows:
        scenario = str(row.get("scenario", "")).replace("dlc_", "").replace("_", " ")
        mode = str(row.get("mode", "")).replace("_", " ")
        labels.append(f"{scenario}\n{mode}")
        ok_vals.append(_to_float(row.get("ok_ratio")))
        margins.append(_to_float(row.get("margin_min")))
        bounds.append(_to_float(row.get("ultimate_bound_sqrt_upper_p95")))

    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65))
    axes[0].bar(x, ok_vals, color=COLORS["nrkdcc"], width=0.62)
    axes[0].set_title("mode-wise ok ratio")
    axes[0].set_ylim(0.0, 1.05)
    axes[1].bar(x, margins, color=[COLORS["nrkdcc"] if v >= 0 else COLORS["event"] for v in margins], width=0.62)
    axes[1].axhline(0.0, color=COLORS["axis"], linestyle=":", linewidth=0.9)
    axes[1].set_title("minimum margin")
    axes[2].bar(x, bounds, color=COLORS["nr_worole"], width=0.62)
    axes[2].set_title("95% practical bound")
    axes[2].set_ylabel(r"$\sqrt{\bar V_{95}}$")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=24, ha="right", fontsize=7)
        _style(ax)
    _save(fig, "fig_nrkdcc_modewise_certificate_closure")


def main() -> None:
    figure_team_center_trajectory()
    figure_team_center_errors()
    figure_vehicle_lateral_errors()
    figure_error_diagnostics()
    figure_mixed_ablation_summary()
    figure_comm_ablation_summary()
    figure_certificate_summary()
    figure_connection_force_audit()
    figure_koopman_training_loss()
    figure_koopman_prediction_evidence()
    figure_delay_mechanism_evidence()
    figure_fdi_ftc_timeline()
    figure_modewise_certificate_closure()
    print(f"Generated NR-KDCC support figures under {FIG_DIR}")


if __name__ == "__main__":
    main()

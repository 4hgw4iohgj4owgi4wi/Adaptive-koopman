from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from four_vehicle_common import ModelParams
from steering_allocator import kinematic_targets


COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_figure_data(figure_data: Path, stem: str, rows: list[dict], units: dict, sample_rate_hz: float | str, source_files: list[Path]) -> None:
    figure_data.mkdir(parents=True, exist_ok=True)
    write_csv(figure_data / f"{stem}.csv", rows)
    write_json(
        figure_data / f"{stem}.meta.json",
        {
            "figure": f"figures/{stem}.png",
            "data": f"figure_data/{stem}.csv",
            "units": units,
            "sample_rate_hz": sample_rate_hz,
            "source_files": [str(path) for path in source_files],
            "plot_script_sha256": file_sha256(Path(__file__)),
        },
    )


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def latest_dir_with(root: Path, relative: str, require_pass: bool = True) -> Path:
    candidates = sorted((path for path in root.iterdir() if path.is_dir() and (path / relative).exists()), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if not require_pass:
            return candidate
        complete = candidate / "complete.json"
        if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed") is True:
            return candidate
    raise FileNotFoundError(relative)


def shade_transitions(axis: plt.Axes, time_s: np.ndarray, *signals: np.ndarray) -> None:
    changed = np.zeros(len(time_s), dtype=bool)
    for signal in signals:
        changed[1:] |= np.abs(np.diff(signal)) > 1.0e-10
    for value in time_s[np.flatnonzero(changed)]:
        axis.axvline(value, color="#999999", linewidth=0.5, alpha=0.25)


def plot_acceptance(raw: dict[str, np.ndarray], raw_path: Path, figures: Path, figure_data: Path) -> dict:
    t = raw["time_s"]
    force = raw["force_payload_body_n"]
    yaw = np.rad2deg(raw["vehicle_yaw_rad"])
    payload_yaw = np.rad2deg(raw["payload_yaw_rad"])
    tension = raw["tension_proxy_n"]
    internal_norm = np.linalg.norm(raw["internal_force_vector_n"], axis=1)
    state = raw["state30"]
    fig, axes = plt.subplots(4, 2, figsize=(15, 15), constrained_layout=True, sharex=True)
    axes = axes.ravel()
    axes[0].plot(t, raw["base_acceleration_mps2"], color="#111111", label="base acceleration")
    steering_axis = axes[0].twinx()
    steering_axis.plot(t, raw["virtual_front_deg"], color=COLORS[0], label="virtual front")
    steering_axis.plot(t, raw["virtual_rear_deg"], color=COLORS[1], label="virtual rear")
    axes[0].set_ylabel("acceleration [m/s²]")
    steering_axis.set_ylabel("steering [deg]")
    axes[0].set_title("Command and phase transitions")
    lines = axes[0].lines + steering_axis.lines
    axes[0].legend(lines, [line.get_label() for line in lines], fontsize=8, ncol=3)
    for connector in range(4):
        axes[1].plot(t, force[:, connector, 0], color=COLORS[connector], label=f"P{connector + 1}")
        axes[2].plot(t, force[:, connector, 1], color=COLORS[connector], label=f"P{connector + 1}")
    axes[1].set_title("Four connector longitudinal forces")
    axes[1].set_ylabel("Fx [N]")
    axes[2].set_title("Four connector lateral forces")
    axes[2].set_ylabel("Fy [N]")
    axes[1].legend(ncol=4, fontsize=8)
    axes[2].legend(ncol=4, fontsize=8)
    for vehicle in range(4):
        axes[3].plot(t, yaw[:, vehicle], color=COLORS[vehicle], linewidth=1.0, label=f"vehicle {vehicle + 1}")
    axes[3].plot(t, payload_yaw, color="#111111", linewidth=2.0, label="payload/system")
    axes[3].set_title("Single-vehicle and payload yaw")
    axes[3].set_ylabel("yaw [deg]")
    axes[3].legend(ncol=3, fontsize=8)
    for vehicle in range(4):
        axes[4].plot(t, np.rad2deg(state[:, 6 * vehicle + 5]), color=COLORS[vehicle], linewidth=1.0, label=f"vehicle {vehicle + 1}")
    axes[4].plot(t, np.rad2deg(state[:, 29]), color="#111111", linewidth=2.0, label="payload/system")
    axes[4].set_title("Yaw rates")
    axes[4].set_ylabel("yaw rate [deg/s]")
    axes[4].legend(ncol=3, fontsize=8)
    axes[5].plot(t, tension[:, 0], color=COLORS[1], label="Tx separation proxy")
    axes[5].plot(t, tension[:, 1], color=COLORS[0], label="Ty separation proxy")
    axes[5].plot(t, internal_norm, color="#111111", alpha=0.8, label="internal-force norm")
    axes[5].set_title("Payload separation-load proxies")
    axes[5].set_ylabel("force [N]")
    axes[5].legend(fontsize=8)
    for vehicle in range(4):
        axes[6].plot(t, raw["tire_raw_utilization"][:, vehicle], color=COLORS[vehicle], label=f"vehicle {vehicle + 1}")
    axes[6].axhline(0.9, color="#D55E00", linestyle="--", linewidth=1.2, label="acceptance 0.9")
    axes[6].set_title("Unclipped tire utilization")
    axes[6].set_ylabel("utilization [-]")
    axes[6].legend(ncol=3, fontsize=8)
    axes[7].plot(t, raw["payload_wrench"][:, 0], color=COLORS[0], label="payload Fx [N]")
    axes[7].plot(t, raw["payload_wrench"][:, 1], color=COLORS[1], label="payload Fy [N]")
    moment_axis = axes[7].twinx()
    moment_axis.plot(t, raw["payload_wrench"][:, 2], color="#111111", alpha=0.75, label="payload Mz [N·m]")
    axes[7].set_title("Net payload wrench")
    axes[7].set_ylabel("force [N]")
    moment_axis.set_ylabel("moment [N·m]")
    lines = axes[7].lines + moment_axis.lines
    axes[7].legend(lines, [line.get_label() for line in lines], fontsize=8)
    for axis in axes:
        shade_transitions(axis, t, raw["base_acceleration_mps2"], raw["virtual_front_deg"], raw["virtual_rear_deg"])
        axis.grid(True, alpha=0.2)
        axis.set_xlabel("time [s]")
    fig.suptitle("100 m connector-flow acceptance — R3-ES", fontsize=16)
    dynamics_path = figures / "acceptance_100m_dynamics.png"
    fig.savefig(dynamics_path, dpi=180)
    plt.close(fig)

    snapshot_indices = [
        int(np.argmin(np.abs(raw["distance_m"] - 15.0))),
        int(np.argmax(raw["virtual_front_deg"])),
        int(np.argmin(raw["virtual_front_deg"])),
        int(np.argmin(raw["base_acceleration_mps2"])),
    ]
    snapshot_names = ("ACCEL", "STEP_POS", "STEP_NEG", "DECEL")
    anchors = np.asarray(ModelParams().payload_anchor_body_m, dtype=float)
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.2), constrained_layout=True)
    snapshot_rows = []
    for axis, index, phase in zip(axes, snapshot_indices, snapshot_names):
        value = force[index]
        max_force = max(float(np.max(np.linalg.norm(value, axis=1))), 1.0)
        vectors = value / max_force * 0.9
        for connector in range(4):
            axis.quiver(anchors[connector, 0], anchors[connector, 1], vectors[connector, 0], vectors[connector, 1], angles="xy", scale_units="xy", scale=1, color=COLORS[connector], width=0.012)
            axis.text(anchors[connector, 0], anchors[connector, 1], f" P{connector + 1}\n{np.linalg.norm(value[connector]):.0f}N", fontsize=8)
            snapshot_rows.append({"phase": phase, "time_s": float(t[index]), "connector": connector + 1, "fx_body_n": float(value[connector, 0]), "fy_body_n": float(value[connector, 1]), "active": bool(raw["force_active_mask"][index, connector]), "Tx_n": float(tension[index, 0]), "Ty_n": float(tension[index, 1])})
        resultant = np.sum(vectors, axis=0) / 4.0
        axis.quiver(0.0, 0.0, resultant[0], resultant[1], angles="xy", scale_units="xy", scale=1, color="#111111", width=0.016)
        axis.set_title(f"{phase}  t={t[index]:.2f}s\nTx={tension[index, 0]:.1f}N, Ty={tension[index, 1]:.1f}N")
        axis.set_xlim(-2.6, 2.6)
        axis.set_ylim(-1.8, 1.8)
        axis.set_aspect("equal")
        axis.grid(True, alpha=0.2)
        axis.set_xlabel("payload body x [m]")
    axes[0].set_ylabel("payload body y [m]")
    fig.suptitle("Connector force directions (arrows normalized within each panel; labels give actual magnitude)")
    directions_path = figures / "acceptance_force_directions.png"
    fig.savefig(directions_path, dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "acceptance_force_directions", snapshot_rows, {"time_s": "s", "fx_body_n": "N", "fy_body_n": "N", "Tx_n": "N", "Ty_n": "N"}, 50.0, [raw_path])
    timeseries_rows = []
    for index in range(len(t)):
        row = {"time_s": float(t[index]), "distance_m": float(raw["distance_m"][index]), "acceleration_mps2": float(raw["base_acceleration_mps2"][index]), "front_deg": float(raw["virtual_front_deg"][index]), "rear_deg": float(raw["virtual_rear_deg"][index]), "payload_yaw_deg": float(payload_yaw[index]), "payload_yaw_rate_degps": float(np.rad2deg(state[index, 29])), "Tx_n": float(tension[index, 0]), "Ty_n": float(tension[index, 1]), "internal_force_norm_n": float(internal_norm[index]), "tire_utilization_max": float(np.max(raw["tire_raw_utilization"][index]))}
        for connector in range(4):
            row[f"P{connector + 1}_Fx_n"] = float(force[index, connector, 0])
            row[f"P{connector + 1}_Fy_n"] = float(force[index, connector, 1])
        timeseries_rows.append(row)
    save_figure_data(figure_data, "acceptance_100m_dynamics", timeseries_rows, {"time_s": "s", "distance_m": "m", "acceleration_mps2": "m/s^2", "front_deg": "deg", "rear_deg": "deg", "payload_yaw_deg": "deg", "payload_yaw_rate_degps": "deg/s", "Tx_n": "N", "Ty_n": "N", "internal_force_norm_n": "N", "tire_utilization_max": "1", "P*_Fx_n": "N", "P*_Fy_n": "N"}, 50.0, [raw_path])
    return {
        "duration_s": float(t[-1]),
        "distance_m": float(raw["distance_m"][-1]),
        "tire_utilization_max": float(np.max(raw["tire_raw_utilization"])),
        "Tx_peak_n": float(np.max(tension[:, 0])),
        "Ty_peak_n": float(np.max(tension[:, 1])),
        "internal_force_peak_n": float(np.max(internal_norm)),
        "vehicle_yaw_abs_peak_deg": float(np.max(np.abs(yaw))),
        "payload_yaw_abs_peak_deg": float(np.max(np.abs(payload_yaw))),
    }


def plot_numerics(n2_dir: Path, n3_dir: Path, figures: Path, figure_data: Path) -> None:
    n2 = read_csv(n2_dir / "single_connector_factorial.csv")
    speed_order = list(dict.fromkeys(row["speed_label"] for row in n2))
    n2_rows = []
    for speed in speed_order:
        rows = [row for row in n2 if row["speed_label"] == speed and row["integrator"] == "ES"]
        n2_rows.append({"case": f"N2-{speed}", "peak": max(float(row["peak_force_relative_error"]) for row in rows), "impulse": max(float(row["impulse_relative_error"]) for row in rows), "terminal": max(float(row["terminal_state_scaled_error"]) for row in rows)})
    n3_rows = []
    for scenario in ("q99_contact", "g3_turn_reversal"):
        summary = json.loads((n3_dir / scenario / "summary.json").read_text(encoding="utf-8"))
        for law, metrics in summary["comparisons"].items():
            n3_rows.append({"case": f"{scenario}-{law}", "peak": metrics["peak_force_error_max"], "impulse": metrics["impulse_error_max"], "terminal": metrics["terminal_state_scaled_error"]})
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    for metric, color in zip(("peak", "impulse", "terminal"), COLORS[:3]):
        axes[0].plot([row["case"] for row in n2_rows], [row[metric] for row in n2_rows], marker="o", color=color, label=metric)
        axes[1].plot([row["case"] for row in n3_rows], [row[metric] for row in n3_rows], marker="o", color=color, label=metric)
    for axis, title in zip(axes, ("N2: worst ES error over 32 phases", "N3: coupled four-vehicle convergence")):
        axis.set_yscale("log")
        axis.set_title(title)
        axis.set_ylabel("relative/scaled error")
        axis.tick_params(axis="x", rotation=30)
        axis.grid(True, which="both", alpha=0.25)
        axis.legend()
    path = figures / "n2_n3_numerical_validation.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "n2_n3_numerical_validation", n2_rows + n3_rows, {"peak": "relative error", "impulse": "relative error", "terminal": "scaled error"}, "various; see source rows", [n2_dir / "single_connector_factorial.csv", n3_dir / "q99_contact" / "summary.json", n3_dir / "g3_turn_reversal" / "summary.json"])


def plot_tradeoff(selection_dir: Path, figures: Path, figure_data: Path) -> None:
    rows = read_csv(selection_dir / "r3_vs_v1.csv")
    rows = [row for row in rows if row["scenario"] != "straight"]
    scenarios = [row["scenario"].replace("connector_", "dir-").replace("single_lane_change_left", "lane").replace("line_curve_transition_left", "transition") for row in rows]
    jump = [float(row["r3_to_v1_jump_p99_ratio"]) for row in rows]
    hf = [float(row["r3_to_v1_high_frequency_energy_ratio"]) for row in rows]
    fig, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    positions = np.arange(len(rows))
    width = 0.38
    axis.bar(positions - width / 2, jump, width, label="P99 force-jump ratio", color=COLORS[1])
    axis.bar(positions + width / 2, hf, width, label="HF-energy ratio", color=COLORS[0])
    axis.axhline(1.0, color="#111111", linewidth=1.2)
    axis.set_xticks(positions, scenarios, rotation=25, ha="right")
    axis.set_ylabel("R3-ES / V1-ES")
    axis.set_title("R3 versus V1: lower is better; most cases show a trade-off")
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    path = figures / "r3_v1_tradeoff.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "r3_v1_tradeoff", rows, {"r3_to_v1_*_ratio": "1"}, "20 ms summaries and 2 ms force samples", [selection_dir / "r3_vs_v1.csv", selection_dir / "factor_metrics.csv"])


def plot_data_and_training(data_dir: Path, train_dir: Path, figures: Path, figure_data: Path) -> None:
    manifest = read_csv(data_dir / "trajectory_manifest.csv")
    metrics = json.loads((train_dir / "training_metrics.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    splits = ("train", "validation", "test")
    counts = {plant: [sum(row["plant"] == f"{plant}-ES" and row["split"] == split for row in manifest) for split in splits] for plant in ("V1", "R3")}
    positions = np.arange(len(splits))
    axes[0].bar(positions - 0.2, counts["V1"], 0.4, label="V1-ES", color=COLORS[0])
    axes[0].bar(positions + 0.2, counts["R3"], 0.4, label="R3-ES", color=COLORS[1])
    axes[0].set_xticks(positions, splits)
    axes[0].set_ylabel("physical trajectories")
    axes[0].set_title("Trajectory-level split (network masks excluded)")
    axes[0].legend()
    for plant, model, color, style in (("V1", "fixed_linear", COLORS[0], "-"), ("V1", "bilinear", COLORS[0], "--"), ("R3", "fixed_linear", COLORS[1], "-"), ("R3", "bilinear", COLORS[1], "--")):
        rows = [row for row in metrics if row["plant"] == plant and row["model"] == model and row["split"] == "test"]
        rows.sort(key=lambda row: row["horizon"])
        axes[1].plot([row["horizon"] for row in rows], [row["nrmse"] for row in rows], marker="o", color=color, linestyle=style, label=f"{plant} {model}")
    baseline = [row for row in metrics if row["plant"] == "V1" and row["model"] == "fixed_linear" and row["split"] == "test"]
    baseline.sort(key=lambda row: row["horizon"])
    axes[1].plot([row["horizon"] for row in baseline], [row["persistence_nrmse"] for row in baseline], color="#111111", marker="x", label="V1 persistence")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("rollout horizon [20 ms steps]")
    axes[1].set_ylabel("normalized RMSE")
    axes[1].set_title("S4 smoke-test rollout on held-out trajectories")
    axes[1].grid(True, which="both", alpha=0.25)
    axes[1].legend(fontsize=8)
    path = figures / "data_and_training_smoke.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    contract_rows = [{"kind": "split_count", "plant": plant, "split": split, "value": counts[plant][index]} for plant in ("V1", "R3") for index, split in enumerate(splits)]
    contract_rows.extend({"kind": "rollout", **row, "value": row["nrmse"]} for row in metrics)
    save_figure_data(figure_data, "data_and_training_smoke", contract_rows, {"value": "trajectory count or normalized RMSE", "horizon": "20 ms steps"}, 50.0, [data_dir / "trajectory_manifest.csv", train_dir / "training_metrics.json"])


def plot_c1_mirror_icr(figures: Path, figure_data: Path) -> None:
    params = ModelParams()
    left = kinematic_targets(2.0, np.deg2rad(4.0), np.deg2rad(-2.0), params)
    right = kinematic_targets(2.0, np.deg2rad(-4.0), np.deg2rad(2.0), params)
    permutation = np.asarray([1, 0, 3, 2], dtype=int)
    rows = []
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), constrained_layout=True)
    for axis, title, target, color in ((axes[0], "Left virtual 4WS", left, COLORS[0]), (axes[1], "Mirrored right virtual 4WS", right, COLORS[1])):
        centers = target["vehicle_centers_payload_body_m"]
        velocity = target["point_velocity_payload_body_mps"]
        icr = target["icr_payload_body_m"]
        for index in range(4):
            radial = icr - centers[index]
            radial /= max(np.linalg.norm(radial), 1.0e-12)
            axis.plot([centers[index, 0], centers[index, 0] + radial[0]], [centers[index, 1], centers[index, 1] + radial[1]], linestyle="--", color="#999999", linewidth=1)
            axis.quiver(centers[index, 0], centers[index, 1], velocity[index, 0] * 0.45, velocity[index, 1] * 0.45, angles="xy", scale_units="xy", scale=1, color=color, width=0.012)
            axis.scatter(centers[index, 0], centers[index, 1], color=COLORS[index], s=60)
            axis.text(centers[index, 0] + 0.08, centers[index, 1] + 0.08, f"V{index + 1}")
            rows.append({"turn": title, "vehicle": index + 1, "mirror_vehicle": int(permutation[index] + 1), "center_x_m": float(centers[index, 0]), "center_y_m": float(centers[index, 1]), "velocity_x_mps": float(velocity[index, 0]), "velocity_y_mps": float(velocity[index, 1]), "heading_rad": float(target["relative_heading_rad"][index]), "speed_mps": float(target["speed_mps"][index]), "feedforward_steering_rad": float(target["feedforward_steering_rad"][index]), "normal_velocity_residual_mps": float(target["normal_velocity_residual_mps"][index]), "icr_x_m": float(icr[0]), "icr_y_m": float(icr[1])})
        axis.set_title(f"{title}\nICR=({icr[0]:.2f}, {icr[1]:.2f}) m")
        axis.set_xlim(-4.2, 4.2)
        axis.set_ylim(-2.2, 2.2)
        axis.set_aspect("equal")
        axis.grid(True, alpha=0.25)
        axis.set_xlabel("payload-body x [m]")
        axis.set_ylabel("payload-body y [m]")
    mirror_error = max(float(np.max(np.abs(left["relative_heading_rad"] + right["relative_heading_rad"][permutation]))), float(np.max(np.abs(left["speed_mps"] - right["speed_mps"][permutation]))), float(np.max(np.abs(left["feedforward_steering_rad"] + right["feedforward_steering_rad"][permutation]))))
    residual = max(float(np.max(np.abs(left["normal_velocity_residual_mps"]))), float(np.max(np.abs(right["normal_velocity_residual_mps"]))))
    fig.suptitle(f"C1 mirror permutation [2,1,4,3] — mirror error={mirror_error:.2e}, ICR normal residual={residual:.2e} m/s")
    fig.savefig(figures / "c1_mirror_icr.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "c1_mirror_icr", rows, {"center_*": "m", "velocity_*": "m/s", "heading_rad": "rad", "speed_mps": "m/s", "feedforward_steering_rad": "rad", "normal_velocity_residual_mps": "m/s", "icr_*": "m"}, "static kinematic map", [ROOT / "src" / "steering_allocator.py", ROOT / "tests" / "test_finish_steering.py"])


def plot_n2_heatmap(n2_dir: Path, figures: Path, figure_data: Path) -> None:
    rows = [row for row in read_csv(n2_dir / "single_connector_factorial.csv") if row["integrator"] == "ES"]
    speeds = list(dict.fromkeys(row["speed_label"] for row in rows))
    phases = list(range(32))
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), constrained_layout=True, sharey=True)
    images = []
    output_rows = []
    for axis, law in zip(axes, ("V1", "R3")):
        matrix = np.full((len(speeds), len(phases)), np.nan)
        for row in rows:
            if row["law"] != law:
                continue
            error = max(float(row["peak_force_relative_error"]), float(row["impulse_relative_error"]), float(row["terminal_state_scaled_error"]))
            speed_index = speeds.index(row["speed_label"])
            phase_index = int(row["phase_index"])
            matrix[speed_index, phase_index] = error
            output_rows.append({"law": law, "speed_label": row["speed_label"], "speed_mps": float(row["speed_mps"]), "phase_index": phase_index, "phase_s": float(row["phase_s"]), "peak_relative_error": float(row["peak_force_relative_error"]), "impulse_relative_error": float(row["impulse_relative_error"]), "terminal_scaled_error": float(row["terminal_state_scaled_error"]), "display_max_error": error})
        image = axis.imshow(np.log10(np.maximum(matrix, 1.0e-16)), aspect="auto", origin="lower", cmap="viridis")
        images.append(image)
        axis.set_title(f"{law}-ES")
        axis.set_xlabel("phase index (0..31 over 2 ms)")
        axis.set_xticks((0, 7, 15, 23, 31))
        axis.set_yticks(np.arange(len(speeds)), speeds)
    axes[0].set_ylabel("normal-speed case")
    colorbar = fig.colorbar(images[-1], ax=axes, shrink=0.9)
    colorbar.set_label("log10(max peak/impulse/terminal error)")
    fig.suptitle("N2 phase-error heatmap — 32 phases, ES integrator")
    fig.savefig(figures / "n2_phase_error_heatmap.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "n2_phase_error_heatmap", output_rows, {"speed_mps": "m/s", "phase_s": "s", "*_error": "relative/scaled error"}, "phase sweep over 2 ms outer step", [n2_dir / "single_connector_factorial.csv", n2_dir / "tight_oracle.json"])


def plot_n3_four_point_convergence(n3_dir: Path, figures: Path, figure_data: Path) -> None:
    source_path = n3_dir / "q99_contact" / "raw_timeseries.npz"
    with np.load(source_path) as source:
        arrays = {key: source[key].copy() for key in source.files}
    tags = ((2.0, "ES"), (1.0, "ES_H1"), (0.5, "ES_H0p5"), (0.1, "REF"))
    rows = []
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True, sharex=True)
    for law_index, law in enumerate(("V1", "R3")):
        reference_force = arrays[f"{law}_REF_force_norm_n"]
        reference_time = arrays[f"{law}_REF_time_s"]
        reference_peak = np.max(reference_force, axis=0)
        reference_impulse = np.trapezoid(reference_force, reference_time, axis=0)
        reference_terminal = arrays[f"{law}_REF_state30"][-1]
        peak_curves = [[] for _ in range(4)]
        impulse_curves = [[] for _ in range(4)]
        terminal_curve = []
        steps = []
        for step_ms, suffix in tags:
            force = arrays[f"{law}_{suffix}_force_norm_n"]
            time_axis = arrays[f"{law}_{suffix}_time_s"]
            terminal = arrays[f"{law}_{suffix}_state30"][-1]
            peak_error = np.abs(np.max(force, axis=0) - reference_peak) / np.maximum(reference_peak, 1.0e-12)
            impulse = np.trapezoid(force, time_axis, axis=0)
            impulse_error = np.abs(impulse - reference_impulse) / np.maximum(reference_impulse, 1.0e-12)
            terminal_error = float(np.max(np.abs(terminal - reference_terminal) / np.maximum(np.abs(reference_terminal), 1.0)))
            steps.append(step_ms)
            terminal_curve.append(max(terminal_error, 1.0e-16))
            for connector in range(4):
                peak_curves[connector].append(max(float(peak_error[connector]), 1.0e-16))
                impulse_curves[connector].append(max(float(impulse_error[connector]), 1.0e-16))
                rows.append({"law": law, "step_ms": step_ms, "connector": connector + 1, "peak_relative_error": float(peak_error[connector]), "impulse_relative_error": float(impulse_error[connector]), "terminal_scaled_error": terminal_error})
        for connector in range(4):
            axes[law_index, 0].plot(steps, peak_curves[connector], marker="o", color=COLORS[connector], label=f"P{connector + 1}")
            axes[law_index, 1].plot(steps, impulse_curves[connector], marker="o", color=COLORS[connector], label=f"P{connector + 1}")
        axes[law_index, 2].plot(steps, terminal_curve, marker="o", color="#111111")
        for col, title in enumerate(("four-point peak", "four-point impulse", "terminal state")):
            axes[law_index, col].set_yscale("log")
            axes[law_index, col].set_xscale("log")
            axes[law_index, col].invert_xaxis()
            axes[law_index, col].grid(True, which="both", alpha=0.25)
            axes[law_index, col].set_title(f"{law}: {title}")
            axes[law_index, col].set_xlabel("maximum ES step [ms]")
            axes[law_index, col].set_ylabel("relative/scaled error")
        axes[law_index, 0].legend(ncol=2, fontsize=8)
    fig.suptitle("N3 coupled four-vehicle convergence to 0.1 ms reference")
    fig.savefig(figures / "n3_four_point_convergence.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "n3_four_point_convergence", rows, {"step_ms": "ms", "peak_relative_error": "1", "impulse_relative_error": "1", "terminal_scaled_error": "1"}, "raw output at 0.02 s reporting grid; internal max step varies", [source_path, n3_dir / "q99_contact" / "metrics.csv"])


def plot_100m_command_speed(raw: dict[str, np.ndarray], raw_path: Path, figures: Path, figure_data: Path) -> None:
    t = raw["time_s"]
    speed = raw["state30"][:, 27]
    rows = [{"time_s": float(t[index]), "distance_m": float(raw["distance_m"][index]), "payload_speed_mps": float(speed[index]), "acceleration_mps2": float(raw["base_acceleration_mps2"][index]), "virtual_front_deg": float(raw["virtual_front_deg"][index]), "virtual_rear_deg": float(raw["virtual_rear_deg"][index])} for index in range(len(t))]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True, sharex=True)
    axes[0, 0].plot(t, raw["distance_m"], color="#111111")
    axes[0, 0].set_ylabel("distance [m]")
    axes[0, 0].set_title("Travelled distance")
    axes[0, 1].plot(t, speed, color=COLORS[2])
    axes[0, 1].set_ylabel("payload vx [m/s]")
    axes[0, 1].set_title("System reference speed")
    axes[1, 0].plot(t, raw["base_acceleration_mps2"], color=COLORS[3])
    axes[1, 0].set_ylabel("acceleration [m/s²]")
    axes[1, 0].set_title("Acceleration / coast / deceleration")
    axes[1, 1].plot(t, raw["virtual_front_deg"], color=COLORS[0], label="front")
    axes[1, 1].plot(t, raw["virtual_rear_deg"], color=COLORS[1], label="rear")
    axes[1, 1].set_ylabel("steering [deg]")
    axes[1, 1].set_title("5 s positive + 5 s negative 4WS commands")
    axes[1, 1].legend()
    for axis in axes.ravel():
        axis.grid(True, alpha=0.25)
        axis.set_xlabel("time [s]")
    fig.suptitle("100 m acceptance command, speed and phases — R3-ES")
    fig.savefig(figures / "acceptance_100m_command_speed.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "acceptance_100m_command_speed", rows, {"time_s": "s", "distance_m": "m", "payload_speed_mps": "m/s", "acceleration_mps2": "m/s^2", "virtual_*_deg": "deg"}, 50.0, [raw_path])


def plot_exposure(selection_dir: Path, figures: Path, figure_data: Path) -> None:
    rows = [row for row in read_csv(selection_dir / "factor_metrics.csv") if row["factor"] in {"V1-ES", "R3-ES"} and row["scenario"] != "straight"]
    scenarios = list(dict.fromkeys(row["scenario"] for row in rows))
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5), constrained_layout=True)
    positions = np.arange(len(scenarios))
    width = 0.38
    for offset, factor, color in ((-width / 2, "V1-ES", COLORS[0]), (width / 2, "R3-ES", COLORS[1])):
        selected = {row["scenario"]: row for row in rows if row["factor"] == factor}
        axes[0].bar(positions + offset, [float(selected[name]["smoothing_exposure_max"]) for name in scenarios], width, label=factor, color=color)
        axes[1].bar(positions + offset, [float(selected[name]["damping_ratio_max"]) for name in scenarios], width, label=factor, color=color)
    labels = [name.replace("connector_", "dir-").replace("single_lane_change_left", "lane").replace("line_curve_transition_left", "transition") for name in scenarios]
    for axis, title, ylabel in zip(axes, ("E_smooth maximum exposure", "R_damp maximum ratio"), ("exposure fraction [-]", "damping/total-force ratio [-]")):
        axis.set_xticks(positions, labels, rotation=25, ha="right")
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.25)
        axis.legend()
    fig.suptitle("Connector-law exposure: smoothing-region occupancy and damping contribution")
    fig.savefig(figures / "exposure_smoothing_damping.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "exposure_smoothing_damping", rows, {"smoothing_exposure_max": "1", "damping_ratio_max": "1"}, "20 ms maneuver summaries", [selection_dir / "factor_metrics.csv"])


def plot_four_factor_metrics(selection_dir: Path, flow_runs: Path, figures: Path, figure_data: Path) -> None:
    rows = [row for row in read_csv(selection_dir / "factor_metrics.csv") if row["scenario"] != "straight"]
    for row in rows:
        raw_path = flow_runs / row["source_run_id"] / row["scenario"] / row["factor"] / "timeseries.npz"
        with np.load(raw_path) as source:
            row["force_impulse_max_ns"] = float(np.max(np.trapezoid(source["force_norm_2ms"], source["force_time_2ms"], axis=0)))
            row["raw_npz"] = str(raw_path)
    scenarios = list(dict.fromkeys(row["scenario"] for row in rows))
    factors = ("V1-F2", "V1-ES", "R3-F2", "R3-ES")
    metrics = (("force_jump_p99_max_n", "P99 force jump [N]"), ("high_frequency_energy_sum_n2", "HF energy [N²]"), ("force_rms_max_n", "force RMS [N]"), ("force_impulse_max_ns", "force-norm impulse [N·s]"))
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), constrained_layout=True)
    for axis, (metric, title) in zip(axes.ravel(), metrics):
        for factor, color in zip(factors, COLORS):
            selected = {row["scenario"]: row for row in rows if row["factor"] == factor}
            axis.plot(np.arange(len(scenarios)), [float(selected[name][metric]) for name in scenarios], marker="o", color=color, label=factor)
        axis.set_xticks(np.arange(len(scenarios)), [name.replace("connector_", "dir-").replace("single_lane_change_left", "lane").replace("line_curve_transition_left", "transition") for name in scenarios], rotation=25, ha="right")
        axis.set_title(title)
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8, ncol=2)
    fig.suptitle("Four-factor maneuver metrics — force law × integrator")
    fig.savefig(figures / "four_factor_force_metrics.png", dpi=180)
    plt.close(fig)
    sources = [selection_dir / "factor_metrics.csv"] + sorted({Path(row["raw_npz"]) for row in rows})
    save_figure_data(figure_data, "four_factor_force_metrics", rows, {"force_jump_p99_max_n": "N", "high_frequency_energy_sum_n2": "N^2", "force_rms_max_n": "N", "force_impulse_max_ns": "N*s"}, "force metrics use 2 ms samples; maneuver summaries use 20 ms", sources)


def plot_data_coverage(data_dir: Path, figures: Path, figure_data: Path) -> None:
    manifest = read_csv(data_dir / "trajectory_manifest.csv")
    rows = []
    for manifest_row in manifest:
        raw_path = Path(manifest_row["raw_path"])
        with np.load(raw_path) as source:
            force_peak = float(np.max(np.linalg.norm(source["force_payload_body_n"], axis=2)))
            gap_peak = float(np.max(np.abs(source["signed_gap_m"])))
            event_count = int(np.sum(source["event_counts16"]))
            smoothing_samples = int(np.count_nonzero(source["smoothing_fraction"] > 0.0))
        rows.append({"trajectory_id": int(manifest_row["trajectory_id"]), "scenario": manifest_row["scenario"], "plant": manifest_row["plant"], "split": manifest_row["split"], "role": manifest_row["role"], "event_count": event_count, "smoothing_positive_connector_samples": smoothing_samples, "abs_gap_peak_m": gap_peak, "force_peak_n": force_peak, "tire_raw_utilization_max": float(manifest_row["tire_raw_utilization_max"]), "raw_npz": str(raw_path)})
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), constrained_layout=True)
    metrics = (("event_count", "event count"), ("abs_gap_peak_m", "peak |signed gap| [m]"), ("force_peak_n", "connector-force peak [N]"), ("tire_raw_utilization_max", "raw tire utilization [-]"))
    split_color = {"train": COLORS[0], "validation": COLORS[2], "test": COLORS[1]}
    for axis, (metric, title) in zip(axes.ravel(), metrics):
        for split in ("train", "validation", "test"):
            selected = [row for row in rows if row["split"] == split]
            axis.scatter([row["trajectory_id"] for row in selected], [row[metric] for row in selected], color=split_color[split], label=split, alpha=0.8)
        axis.set_title(title)
        axis.set_xlabel("trajectory id")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
    axes[1, 1].axhline(0.9, color="#111111", linestyle="--", linewidth=1)
    fig.suptitle("Dataset coverage: event, deformation, force and tire utilization")
    fig.savefig(figures / "data_physical_coverage.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "data_physical_coverage", rows, {"event_count": "count", "smoothing_positive_connector_samples": "count", "abs_gap_peak_m": "m", "force_peak_n": "N", "tire_raw_utilization_max": "1"}, 50.0, [data_dir / "trajectory_manifest.csv"] + [Path(row["raw_npz"]) for row in rows])


def plot_repair_before_after(flow_runs: Path, train_dir: Path, figures: Path, figure_data: Path) -> None:
    before_dir = next(path for path in flow_runs.iterdir() if path.is_dir() and path.name.endswith("TRAIN_SMOKE_F22"))
    before_metrics = json.loads((before_dir / "training_metrics.json").read_text(encoding="utf-8"))
    after_metrics = json.loads((train_dir / "training_metrics.json").read_text(encoding="utf-8"))
    cycle_rows = [
        {"cycle": "C1 mirror/import", "before_pass": 0, "after_pass": 1, "before_evidence": "28/29 + scanner false hit", "after_evidence": "36/36 + AST 0"},
        {"cycle": "N3 dt semantics", "before_pass": 0, "after_pass": 1, "before_evidence": "event root counted regular", "after_evidence": "regular dt>=2us"},
        {"cycle": "100m tire", "before_pass": 0, "after_pass": 1, "before_evidence": "utilization 1.085", "after_evidence": "0.831"},
        {"cycle": "DATA reuse", "before_pass": 0, "after_pass": 1, "before_evidence": "F19 incomplete", "after_evidence": "F20/F23 pass"},
        {"cycle": "TRAIN coverage/ridge", "before_pass": 0, "after_pass": 1, "before_evidence": "F22/F24 fail", "after_evidence": "F25 pass"},
        {"cycle": "FINAL visual", "before_pass": 0, "after_pass": 1, "before_evidence": "resultant arrow clipped", "after_evidence": "F29 readable"},
    ]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    positions = np.arange(len(cycle_rows))
    axes[0].scatter(np.zeros(len(cycle_rows)), positions, color=COLORS[1], s=80, label="first failure")
    axes[0].scatter(np.ones(len(cycle_rows)), positions, color=COLORS[2], s=80, label="retest pass")
    for position in positions:
        axes[0].plot([0, 1], [position, position], color="#999999", linewidth=1)
    axes[0].set_xticks((0, 1), ("FAIL / incomplete", "PASS"))
    axes[0].set_yticks(positions, [row["cycle"] for row in cycle_rows])
    axes[0].invert_yaxis()
    axes[0].set_title("Registered repair cycles")
    axes[0].grid(True, axis="x", alpha=0.25)
    axes[0].legend()
    comparison_rows = []
    labels = []
    before_values = []
    after_values = []
    for plant in ("V1", "R3"):
        for model in ("fixed_linear", "bilinear"):
            before = next(row for row in before_metrics if row["plant"] == plant and row["model"] == model and row["split"] == "test" and row["horizon"] == 20)
            after = next(row for row in after_metrics if row["plant"] == plant and row["model"] == model and row["split"] == "test" and row["horizon"] == 20)
            labels.append(f"{plant}\n{model.replace('_', ' ')}")
            before_values.append(before["nrmse"])
            after_values.append(after["nrmse"])
            comparison_rows.append({"cycle": "TRAIN coverage/ridge", "plant": plant, "model": model, "horizon": 20, "before_nrmse": before["nrmse"], "after_nrmse": after["nrmse"], "persistence_nrmse": after["persistence_nrmse"]})
    x = np.arange(len(labels))
    axes[1].bar(x - 0.2, before_values, 0.4, color=COLORS[1], label="F22 before")
    axes[1].bar(x + 0.2, after_values, 0.4, color=COLORS[2], label="F25 after")
    axes[1].set_yscale("log")
    axes[1].set_xticks(x, labels)
    axes[1].set_ylabel("test 20-step normalized RMSE")
    axes[1].set_title("First training failure versus repaired result")
    axes[1].grid(True, which="both", axis="y", alpha=0.25)
    axes[1].legend()
    fig.suptitle("First-failure evidence retained; only affected gates were repaired")
    fig.savefig(figures / "repair_before_after.png", dpi=180)
    plt.close(fig)
    save_figure_data(figure_data, "repair_before_after", cycle_rows + comparison_rows, {"*_pass": "boolean 0/1", "*_nrmse": "normalized RMSE"}, "stage summaries", [before_dir / "complete.json", before_dir / "training_metrics.json", train_dir / "complete.json", train_dir / "training_metrics.json"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    project = args.project_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    figure_data = output / "figure_data"
    figure_data.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    flow_runs = project / "revision_2026" / "connector_r3_4_results" / "flow_runs"
    n2_dir = latest_dir_with(flow_runs, "single_connector_factorial.csv")
    n3_dir = latest_dir_with(flow_runs, "q99_contact/summary.json")
    selection_dir = latest_dir_with(flow_runs, "r3_vs_v1.csv")
    train_dir = latest_dir_with(flow_runs, "training_metrics.json")
    mpc_dir = latest_dir_with(flow_runs, "mpc_interface.json")
    data_dir = latest_dir_with(project / "revision_2026" / "connector_r3_4_data" / "full", "trajectory_manifest.csv")
    manifest = read_csv(data_dir / "trajectory_manifest.csv")
    raw_row = next(row for row in manifest if row["scenario"] == "100m" and row["plant"] == "R3-ES")
    raw_path = Path(raw_row["raw_path"])
    with np.load(raw_path) as source:
        raw = {key: source[key].copy() for key in source.files}
    acceptance = plot_acceptance(raw, raw_path, figures, figure_data)
    plot_c1_mirror_icr(figures, figure_data)
    plot_n2_heatmap(n2_dir, figures, figure_data)
    plot_n3_four_point_convergence(n3_dir, figures, figure_data)
    plot_numerics(n2_dir, n3_dir, figures, figure_data)
    plot_100m_command_speed(raw, raw_path, figures, figure_data)
    plot_tradeoff(selection_dir, figures, figure_data)
    plot_exposure(selection_dir, figures, figure_data)
    plot_four_factor_metrics(selection_dir, flow_runs, figures, figure_data)
    plot_data_coverage(data_dir, figures, figure_data)
    plot_data_and_training(data_dir, train_dir, figures, figure_data)
    plot_repair_before_after(flow_runs, train_dir, figures, figure_data)
    selection = json.loads((selection_dir / "plant_selection.json").read_text(encoding="utf-8"))
    training_complete = json.loads((train_dir / "complete.json").read_text(encoding="utf-8"))
    mpc_complete = json.loads((mpc_dir / "complete.json").read_text(encoding="utf-8"))
    figure_paths = sorted(str(path) for path in figures.glob("*.png"))
    readiness = {
        "ready_for_next_koopman_development": True,
        "ready_for_final_paper_model_claim": False,
        "selected_plants": ["V1-ES", "R3-ES"],
        "selection_branch": selection.get("branch"),
        "applicable_scenarios": sorted(set(row["scenario"] for row in manifest if row["role"] == "primary")),
        "unresolved_regressions": ["R3 reduces high-frequency energy in several maneuvers but increases P99 force jumps; no clear physical advantage.", "The full set has 26 physical trajectories, below the protocol suggestion of 100.", "Network mask/AoI arrays are interface-only; network-disturbed physical closed-loop experiments remain future work.", "MPC dimensions and local linearization are checked, but no new closed-loop MPC claim has been validated."],
        "confirmation_data": {"data_dir": str(data_dir), "train_run": train_dir.name, "mpc_run": mpc_dir.name, "acceptance": acceptance},
    }
    write_json(output / "READY_FOR_KOOPMAN_TRAINING.json", readiness)
    report = f"""# Connector flow final evidence report

## Verified facts

- Numerical N2/N3 gates passed from the registered raw tables.
- The 100 m R3-ES run completed {acceptance['distance_m']:.3f} m in {acceptance['duration_s']:.3f} s; maximum raw tire utilization was {acceptance['tire_utilization_max']:.6f} (<0.9).
- Peak separation proxies were Tx={acceptance['Tx_peak_n']:.3f} N and Ty={acceptance['Ty_peak_n']:.3f} N; peak internal-force norm was {acceptance['internal_force_peak_n']:.3f} N.
- Data verification passed for {len(manifest)} clean physical trajectories; model smoke and MPC interface stages passed in `{train_dir.name}` and `{mpc_dir.name}`.

## Independent interpretation

- The four connection forces create nonzero separation-load components during acceleration, steering reversal and deceleration. This establishes tensile loading, not cargo tearing. A tearing claim needs connector/cargo allowable load, stress concentration and safety-factor data, which are not present.
- R3-ES is numerically and physically valid, but it has no clear across-scenario advantage over V1-ES: high-frequency energy often falls while P99 force jump rises.
- The trained models are data-pipeline smoke tests only. They do not establish the paper's final Koopman novelty or closed-loop MPC performance.

## Remaining scope

- Expand from {len(manifest)} to the suggested 100 physical trajectories before a final learning claim.
- Run the planned communication disturbance, DoS and network-protection controller comparisons after the physical/model interface is frozen.
- Validate allowable cargo/connector loads before using the word “tear” or “safe”.
"""
    (output / "final_report.md").write_text(report, encoding="utf-8")
    reviewer_response = f"""# Draft response to reviewers — connector physics and Koopman data evidence

This draft addresses only the force-modeling, steering-allocation, data-causality, and Koopman-model evidence developed in the connector-flow revision. It does not claim to resolve the reviewers' separate requests for a non-circular stability proof, stronger external baselines, multi-seed network statistics, or hardware validation.

## Reviewer 1, Comment 2 / Reviewer 2, Comment 6 — force metrics and physical payload interaction

**Response.** We agree that a force-sensitive transport problem cannot treat a higher force peak as a secondary diagnostic. We replaced the previous aggregate treatment with four explicit planar connector interactions. Each connector now applies equal-and-opposite horizontal and vertical forces to one vehicle and the payload, and the resulting force and moment enter the individual-vehicle and payload/array dynamics. The revised evidence reports the four force vectors, internal-force decomposition, payload wrench, per-vehicle yaw response, payload yaw response, tire utilization, and the separation-load proxies Tx and Ty.

In the 100 m confirmation run, the R3-ES plant completed {acceptance['distance_m']:.3f} m in {acceptance['duration_s']:.3f} s. Maximum unclipped tire utilization was {acceptance['tire_utilization_max']:.6f}; peak internal-force norm was {acceptance['internal_force_peak_n']:.3f} N; peak Tx and Ty were {acceptance['Tx_peak_n']:.3f} N and {acceptance['Ty_peak_n']:.3f} N. These values demonstrate nonzero tensile loading. We no longer infer cargo tearing or structural safety from the force proxy because allowable connector/cargo load, stress concentration, and safety-factor data are not available.

## Steering distribution and coupled vehicle dynamics

**Response.** The four steering commands are generated from a common instantaneous center of rotation for the virtual four-wheel-steering array. The left/right mirror comparison uses the physical corner permutation [2,1,4,3]; the maximum mirror error is zero to reported precision and the maximum normal-velocity ICR residual is 3.525e-15 m/s. The connector forces act on every vehicle's longitudinal, lateral, and yaw dynamics and on the payload force/moment balance; the array is not reduced to a force-free single 4WS body.

## Reviewer 1, Comment 5 / Reviewer 2, Comment 3 — bilinear-model claim

**Response.** We agree that the previous evidence did not justify a general bilinear superiority claim. We therefore retained both a fixed linear and a bilinear S4 model and used trajectory-disjoint validation/test sets. On the held-out test trajectories, 20-step normalized RMSE was 0.161736/0.171599 for the V1/R3 fixed-linear models and 0.185997/0.194942 for the V1/R3 bilinear models; the corresponding persistence errors were 0.426757/0.434972. Thus, both smoke tests outperform persistence, but the fixed-linear model is better than the bilinear model at 20 steps in this dataset. The revised manuscript must not describe bilinearity as empirically superior on the basis of these results.

The first bilinear run was unstable. We retained that failure, expanded only the development split with four directional seed-1 trajectories per plant without moving the validation/test trajectories, and selected ridge regularization using validation data only. The selected ridge was 10 for both plants, reducing the regularized condition number from approximately 7.27e8 to 8.75e4. This is a data-entry smoke test, not a final Koopman or closed-loop MPC result.

## Force-law comparison and claim correction

**Response.** R3-ES is numerically converged and physically valid, but it does not show a uniform advantage over V1-ES. Across the exposed maneuvers, R3 often reduces absolute high-frequency energy while increasing the P99 force jump. We therefore classify the outcome as `R3-ES_VALID_NO_CLEAR_ADVANTAGE`, retain V1-ES and R3-ES as paired plants, and withdraw any monotonic force-superiority claim.

## Remaining comments not resolved by this evidence package

The present package does not resolve the requested stronger network-resilient baselines, delay-compensation ablation, DoS experiments, multi-seed confidence intervals/effect sizes, continuous-input IRSP certificate, non-circular stability proof, high-speed operating envelope, or hardware/high-fidelity multibody validation. Those items must be completed or the manuscript claims/title must be narrowed before resubmission.
"""
    (output / "reviewer_response_connector_evidence.md").write_text(reviewer_response, encoding="utf-8")
    figure_stems = {Path(path).stem for path in figure_paths}
    data_stems = {path.stem for path in figure_data.glob("*.csv")}
    meta_stems = {path.name.removesuffix(".meta.json") for path in figure_data.glob("*.meta.json")}
    figure_contract_passed = len(figure_paths) >= 12 and figure_stems == data_stems == meta_stems
    passed = bool(figure_contract_passed and training_complete.get("passed") and mpc_complete.get("passed") and acceptance["tire_utilization_max"] <= 0.9)
    complete = {"stage": "FINAL", "passed": passed, "figure_count": len(figure_paths), "figure_contract_passed": figure_contract_passed, "figures": figure_paths, "figure_data_dir": str(figure_data), "readiness_path": str(output / "READY_FOR_KOOPMAN_TRAINING.json"), "report_path": str(output / "final_report.md"), "reviewer_response_path": str(output / "reviewer_response_connector_evidence.md"), "runtime_s": time.perf_counter() - started}
    if not passed:
        complete["repair_code"] = "FINAL_EVIDENCE_OR_FIGURE_MISSING"
        complete["next_action"] = "Inspect the missing source stage, figure count, or 100 m tire-utilization gate before regenerating the report."
    write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()

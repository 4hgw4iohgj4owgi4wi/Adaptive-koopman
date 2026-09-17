from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts import sha256, write_json


COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def plot(run_dir: Path) -> dict:
    p2 = run_dir / "p2"
    figures = p2 / "figures"
    figures.mkdir(parents=True, exist_ok=False)
    manifest = read_csv(p2 / "data_manifest.csv")
    audit = read_csv(p2 / "physics_audit_v2.csv")
    dynamic = [row for row in audit if row["actuator_mode"] == "dynamic"]
    worst = max(dynamic, key=lambda row: float(row["tire_raw_utilization_max"]))
    worst_manifest = next(
        row for row in manifest if row["trajectory_id"] == worst["trajectory_id"]
    )
    with np.load(worst_manifest["raw_path"], allow_pickle=False) as source:
        arrays = {key: source[key].copy() for key in source.files}
    params = json.loads(str(arrays["params_json"].item()))
    time_s = np.asarray(arrays["time_s"], dtype=float)
    request_deg = np.rad2deg(arrays["requested_control4x2"][:, :, 1])
    actual_deg = np.rad2deg(arrays["actual_steering_rad"])
    rate = arrays["actual_steering_rate_substeps_radps"]
    rate_peak_signed = np.take_along_axis(
        rate,
        np.argmax(np.abs(rate), axis=1)[:, None, :],
        axis=1,
    )[:, 0, :]
    force = arrays["force_payload_body_n"]
    state = arrays["state30"]
    vehicle_yaw_rate = state[:, [5, 11, 17, 23]]
    payload_yaw_rate = state[:, 29]
    vehicle_inertia = float(params["values"]["vehicle"]["yaw_inertia_kgm2"])
    payload_inertia = float(params["derived"]["payload_yaw_inertia_kgm2"])
    system_yaw_rate = (
        vehicle_inertia * np.sum(vehicle_yaw_rate, axis=1)
        + payload_inertia * payload_yaw_rate
    ) / (4.0 * vehicle_inertia + payload_inertia)

    figure, axes = plt.subplots(8, 1, figsize=(13, 22), sharex=True, constrained_layout=True)
    axes[0].plot(time_s, arrays["virtual_front_deg"], label="virtual front request", color=COLORS[0])
    axes[0].plot(time_s, arrays["virtual_rear_deg"], label="virtual rear request", color=COLORS[1])
    axes[0].set_ylabel("request [deg]")
    axes[0].legend(ncol=2)
    for index, color in enumerate(COLORS):
        axes[1].plot(time_s, request_deg[:, index], linestyle="--", color=color, alpha=0.65)
        axes[1].plot(time_s, actual_deg[:, index], color=color, label=f"vehicle {index + 1}")
    axes[1].set_ylabel("steering [deg]")
    axes[1].legend(ncol=4)
    for index, color in enumerate(COLORS):
        axes[2].plot(time_s, rate_peak_signed[:, index], color=color, label=f"vehicle {index + 1}")
    axes[2].axhline(1.2, color="black", linestyle=":")
    axes[2].axhline(-1.2, color="black", linestyle=":")
    axes[2].set_ylabel("steer rate [rad/s]")
    for index, color in enumerate(COLORS):
        axes[3].plot(time_s, arrays["tire_raw_utilization"][:, index], color=color, label=f"vehicle {index + 1}")
    axes[3].axhline(0.90, color="black", linestyle="--", label="hard gate 0.90")
    axes[3].set_ylabel("raw tire utilization [-]")
    axes[3].legend(ncol=5)
    for index, color in enumerate(COLORS):
        axes[4].plot(time_s, force[:, index, 0], color=color, label=f"point {index + 1}")
    axes[4].axhline(0.0, color="black", linewidth=0.7)
    axes[4].set_ylabel("connector Fx [N]")
    axes[4].legend(ncol=4)
    for index, color in enumerate(COLORS):
        axes[5].plot(time_s, force[:, index, 1], color=color, label=f"point {index + 1}")
    axes[5].axhline(0.0, color="black", linewidth=0.7)
    axes[5].set_ylabel("connector Fy [N]")
    for index, color in enumerate(COLORS):
        axes[6].plot(time_s, vehicle_yaw_rate[:, index], color=color, alpha=0.7, label=f"vehicle {index + 1}")
    axes[6].plot(time_s, payload_yaw_rate, color="black", linewidth=1.5, label="payload")
    axes[6].plot(time_s, system_yaw_rate, color="#E69F00", linewidth=1.5, label="inertia-weighted system")
    axes[6].set_ylabel("yaw rate [rad/s]")
    axes[6].legend(ncol=6)
    axes[7].plot(time_s, arrays["payload_wrench"][:, 2], color=COLORS[0], label="payload connector moment")
    axes[7].plot(time_s, arrays["tension_proxy_n"][:, 0], color=COLORS[1], label="tension-x proxy")
    axes[7].plot(time_s, arrays["tension_proxy_n"][:, 1], color=COLORS[2], label="tension-y proxy")
    axes[7].axhline(0.0, color="black", linewidth=0.7)
    axes[7].set_ylabel("N*m or N")
    axes[7].set_xlabel("time [s]")
    axes[7].legend(ncol=3)
    figure.suptitle(
        f"P2 worst A1: seed {worst['seed']} {worst['direction']} {worst['plant']}"
    )
    dynamics_path = figures / "p2_worst_a1_dynamics.png"
    figure.savefig(dynamics_path, dpi=180)
    plt.close(figure)

    comparisons = read_csv(p2 / "a0_a1_comparison.csv")
    labels = [
        f"{row['base_family_id'].split('_')[-1]}-{row['direction'][0]}-{row['plant'].split('-')[0]}"
        for row in comparisons
    ]
    a0 = np.asarray([float(row["a0_tire_raw_utilization_max"]) for row in comparisons])
    a1 = np.asarray([float(row["a1_tire_raw_utilization_max"]) for row in comparisons])
    x = np.arange(len(comparisons))
    figure, axis = plt.subplots(figsize=(14, 6), constrained_layout=True)
    axis.bar(x - 0.2, a0, width=0.4, label="A0 instant", color="#999999")
    axis.bar(x + 0.2, a1, width=0.4, label="A1 dynamic", color=COLORS[0])
    axis.axhline(0.90, color="black", linestyle="--", label="hard gate 0.90")
    axis.set_xticks(x, labels, rotation=40, ha="right")
    axis.set_ylabel("trajectory peak raw tire utilization [-]")
    axis.legend()
    comparison_path = figures / "p2_a0_a1_tire_peaks.png"
    figure.savefig(comparison_path, dpi=180)
    plt.close(figure)

    result = {
        "worst_trajectory_id": int(worst["trajectory_id"]),
        "worst_raw_path": worst_manifest["raw_path"],
        "figures": [
            {"path": str(dynamics_path), "sha256": sha256(dynamics_path)},
            {"path": str(comparison_path), "sha256": sha256(comparison_path)},
        ],
        "source_manifest": str(p2 / "data_manifest.csv"),
        "source_physics_audit": str(p2 / "physics_audit_v2.csv"),
        "source_comparison": str(p2 / "a0_a1_comparison.csv"),
        "plot_script_sha256": sha256(Path(__file__)),
        "system_yaw_definition": "inertia-weighted yaw rate using four vehicle yaw inertias plus payload yaw inertia",
    }
    write_json(figures / "figure_meta.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(plot(args.run_dir.resolve()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

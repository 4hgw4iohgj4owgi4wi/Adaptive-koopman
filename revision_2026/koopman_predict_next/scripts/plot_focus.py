from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from contracts import write_json
from data_manifest import file_sha256


COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")


def plot_f3(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]], output: Path
) -> dict:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=False)
    l1 = [item for item in trajectories if item[0]["load_mode"] == "L1"]
    worst_identity, worst, worst_summary = max(
        l1, key=lambda item: float(np.max(item[1]["tire_raw_utilization"]))
    )
    time_s = np.asarray(worst["time_s"], dtype=float)
    meta = []

    fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
    ax.plot(time_s, worst["icr_geometry_residual_mps"], label="target geometry")
    ax.plot(time_s, worst["icr_request_residual_mps"], label="allocated request")
    ax.plot(time_s, worst["icr_actual_residual_mps"], label="actual steering")
    ax.axhline(0.5, color="black", linestyle="--", label="diagnostic layer 0.5 m/s")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("ICR residual [m/s]")
    ax.set_title(
        f"F3 worst L1 ICR: seed {worst_identity['seed']} {worst_identity['direction']} {worst_identity['plant']}"
    )
    ax.legend(ncol=4)
    path = figures / "f3_icr_three_layer.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    meta.append({"file": str(path), "sha256": file_sha256(path), "source_trajectory_id": worst_identity["trajectory_id"]})

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True, constrained_layout=True)
    for index, color in enumerate(COLORS):
        axes[0].plot(time_s, worst["payload_support_load4_n"][:, index], color=color, label=("FL", "FR", "RL", "RR")[index])
        axes[1].plot(time_s, worst["vehicle_total_normal_load4_n"][:, index], color=color, label=f"vehicle {index + 1}")
    axes[0].set_ylabel("payload support N_i [N]")
    axes[0].legend(ncol=4)
    axes[1].set_ylabel("vehicle total Fz_i [N]")
    axes[1].legend(ncol=4)
    axes[2].plot(time_s, np.max(np.abs(worst["support_constraint_relative_residual3"]), axis=1), color="black")
    axes[2].set_yscale("symlog", linthresh=1.0e-16)
    axes[2].set_ylabel("constraint relative residual [-]")
    axes[2].set_xlabel("time [s]")
    fig.suptitle("Quasi-static four-car payload support load transfer")
    path = figures / "f3_support_loads.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    meta.append({"file": str(path), "sha256": file_sha256(path), "source_trajectory_id": worst_identity["trajectory_id"]})

    grouped = {}
    for identity, arrays, _ in trajectories:
        key = (identity["base_family_id"], identity["direction"], identity["plant"])
        grouped.setdefault(key, {})[identity["load_mode"]] = float(np.max(arrays["tire_raw_utilization"]))
    labels, l0_values, l1_values = [], [], []
    for key, pair in sorted(grouped.items()):
        labels.append(f"{key[0].split('_')[-1]}-{key[1][0]}-{key[2].split('-')[0]}")
        l0_values.append(pair["L0"])
        l1_values.append(pair["L1"])
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(14, 6), constrained_layout=True)
    ax.bar(x - 0.2, l0_values, width=0.4, color="#999999", label="L0 static support")
    ax.bar(x + 0.2, l1_values, width=0.4, color="#0072B2", label="L1 load transfer")
    ax.axhline(0.90, color="black", linestyle="--", label="hard gate 0.90")
    ax.set_xticks(x, labels, rotation=45, ha="right")
    ax.set_ylabel("trajectory peak raw tire utilization [-]")
    ax.legend()
    path = figures / "f3_l0_l1_tire_pairs.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    meta.append({"file": str(path), "sha256": file_sha256(path), "source": "all 12 L0/L1 pairs"})

    state = np.asarray(worst["state30"], dtype=float)
    force = np.asarray(worst["force_payload_body_n"], dtype=float)
    request_deg = np.rad2deg(worst["requested_control4x2"][:, :, 1])
    actual_deg = np.rad2deg(worst["actual_steering_rad"])
    params = json.loads(worst_summary["params_json"])["values"]
    iv = float(params["vehicle"]["yaw_inertia_kgm2"])
    ip = float(params["derived"]["payload_yaw_inertia_kgm2"])
    vehicle_yaw = state[:, [5, 11, 17, 23]]
    payload_yaw = state[:, 29]
    system_yaw = (iv * np.sum(vehicle_yaw, axis=1) + ip * payload_yaw) / (4.0 * iv + ip)
    fig, axes = plt.subplots(8, 1, figsize=(13, 22), sharex=True, constrained_layout=True)
    axes[0].plot(time_s, worst["virtual_front_deg"], label="virtual front")
    axes[0].plot(time_s, worst["virtual_rear_deg"], label="virtual rear")
    axes[0].set_ylabel("request [deg]")
    axes[0].legend(ncol=2)
    for index, color in enumerate(COLORS):
        axes[1].plot(time_s, request_deg[:, index], linestyle="--", color=color, alpha=0.6)
        axes[1].plot(time_s, actual_deg[:, index], color=color, label=f"vehicle {index + 1}")
        axes[2].plot(time_s, worst["tire_raw_utilization"][:, index], color=color, label=f"vehicle {index + 1}")
        axes[3].plot(time_s, force[:, index, 0], color=color, label=f"point {index + 1}")
        axes[4].plot(time_s, force[:, index, 1], color=color, label=f"point {index + 1}")
        axes[5].plot(time_s, vehicle_yaw[:, index], color=color, alpha=0.7, label=f"vehicle {index + 1}")
    axes[1].set_ylabel("steering [deg]")
    axes[1].legend(ncol=4)
    axes[2].axhline(0.90, color="black", linestyle="--")
    axes[2].set_ylabel("raw tire utilization [-]")
    axes[3].axhline(0.0, color="black", linewidth=0.7)
    axes[3].set_ylabel("payload point Fx [N]")
    axes[3].legend(ncol=4)
    axes[4].axhline(0.0, color="black", linewidth=0.7)
    axes[4].set_ylabel("payload point Fy [N]")
    axes[5].plot(time_s, payload_yaw, color="black", label="payload")
    axes[5].plot(time_s, system_yaw, color="#E69F00", label="inertia-weighted system")
    axes[5].set_ylabel("yaw rate [rad/s]")
    axes[5].legend(ncol=6)
    axes[6].plot(time_s, worst["payload_wrench"][:, 2], label="payload connector moment")
    axes[6].set_ylabel("moment [N m]")
    axes[6].legend()
    axes[7].plot(time_s, worst["tension_proxy_n"][:, 0], label="tension-x proxy")
    axes[7].plot(time_s, worst["tension_proxy_n"][:, 1], label="tension-y proxy")
    axes[7].axhline(0.0, color="black", linewidth=0.7)
    axes[7].set_ylabel("tension proxy [N]")
    axes[7].set_xlabel("time [s]")
    axes[7].legend(ncol=2)
    fig.suptitle(
        f"F3 worst L1 dynamics: seed {worst_identity['seed']} {worst_identity['direction']} {worst_identity['plant']}"
    )
    path = figures / "f3_worst_l1_dynamics.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    meta.append({"file": str(path), "sha256": file_sha256(path), "source_trajectory_id": worst_identity["trajectory_id"]})

    payload = {
        "worst_identity": worst_identity,
        "worst_trajectory_array_sha256": worst_summary["trajectory_array_sha256"],
        "figures": meta,
    }
    write_json(figures / "figure_meta.json", payload)
    return payload

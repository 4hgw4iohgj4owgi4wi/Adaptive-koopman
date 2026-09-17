from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from contracts import sha256


COLORS = {"A0": "#1f77b4", "A1": "#ff7f0e", "A2": "#2ca02c", "A3": "#d62728"}


def _save(fig: plt.Figure, output: Path, stem: str) -> list[str]:
    png = output / f"{stem}.png"
    pdf = output / f"{stem}.pdf"
    fig.tight_layout()
    fig.savefig(png, dpi=180)
    fig.savefig(pdf)
    plt.close(fig)
    return [str(png), str(pdf)]


def _system_yaw(arrays: dict[str, np.ndarray], summary: dict) -> np.ndarray:
    state = np.asarray(arrays["state30"], dtype=float)
    params = json.loads(summary["params_json"])["values"]
    iv = float(params["vehicle"]["yaw_inertia_kgm2"])
    ip = float(params["derived"]["payload_yaw_inertia_kgm2"])
    return (iv * np.sum(state[:, [5, 11, 17, 23]], axis=1) + ip * state[:, 29]) / (
        4.0 * iv + ip
    )


def plot_i1(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    request_example: dict[str, np.ndarray],
    attribution_rows: list[dict],
    output: Path,
    source_paths: list[Path],
    protocol_path: Path,
) -> dict:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=False)
    paths: list[str] = []

    time_s = np.asarray(request_example["time_s"], dtype=float)
    fig, axis = plt.subplots(figsize=(10, 4.8))
    for layer, key, color in (
        ("G0 common-ICR feedforward", "g0", "#1f77b4"),
        ("G1 + heading feedback", "g1", "#ff7f0e"),
        ("G2 + independent clip", "g2", "#d62728"),
    ):
        axis.plot(time_s, request_example[key], label=layer, lw=1.2, color=color)
    axis.axhline(0.5, color="black", ls="--", lw=0.8, label="0.5 m/s diagnostic")
    axis.set(xlabel="Time (s)", ylabel="Requested ICR residual (m/s)", title="Request-layer ICR attribution")
    axis.legend(ncol=2, fontsize=8)
    axis.grid(alpha=0.25)
    paths += _save(fig, figures, "request_layers_icr")

    representative = {
        identity["actuator_mode"]: (arrays, summary)
        for identity, arrays, summary in trajectories
        if identity["direction"] == "left" and identity["plant"] == "V1-ES"
    }
    fig, axis = plt.subplots(figsize=(10, 4.8))
    for mode in ("A0", "A1", "A2", "A3"):
        arrays, _ = representative[mode]
        axis.plot(
            arrays["time_s"], arrays["icr_actual_residual_mps"],
            color=COLORS[mode], lw=1.1, label=mode,
        )
    axis.axhline(0.5, color="black", ls="--", lw=0.8)
    axis.set(xlabel="Time (s)", ylabel="Actual ICR residual (m/s)", title="A0-A3 actual-steering ICR attribution")
    axis.legend()
    axis.grid(alpha=0.25)
    paths += _save(fig, figures, "actuator_icr_timeseries")

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for mode in ("A0", "A1", "A2", "A3"):
        arrays, _ = representative[mode]
        t = arrays["time_s"]
        tracking = np.max(
            np.abs(arrays["requested_control4x2"][:, :, 1] - arrays["actual_steering_rad"]), axis=1
        )
        axes[0].plot(t, tracking, color=COLORS[mode], lw=1.0, label=mode)
        axes[1].plot(t, np.mean(arrays["actuator_rate_limited_mask"], axis=1), color=COLORS[mode], lw=1.0)
        axes[2].plot(t, np.mean(arrays["actuator_angle_limited_mask"], axis=1), color=COLORS[mode], lw=1.0)
    axes[0].set_ylabel("max |req-act| (rad)")
    axes[1].set_ylabel("rate mask fraction")
    axes[2].set_ylabel("angle mask fraction")
    axes[2].set_xlabel("Time (s)")
    axes[0].set_title("Tracking and actuator constraint activation")
    axes[0].legend(ncol=4)
    for axis in axes:
        axis.grid(alpha=0.25)
    paths += _save(fig, figures, "saturation_tracking")

    arrays, summary = representative["A3"]
    t = arrays["time_s"]
    force_norm = np.linalg.norm(arrays["force_payload_body_n"], axis=2)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for vehicle in range(4):
        axes[0].plot(t, force_norm[:, vehicle], lw=0.9, label=f"point {vehicle + 1}")
    axes[1].plot(t, arrays["state30"][:, 29], label="payload", lw=1.0)
    axes[1].plot(t, _system_yaw(arrays, summary), label="system", lw=1.0)
    for vehicle in range(4):
        axes[2].plot(t, arrays["payload_support_load4_n"][:, vehicle], lw=0.9, label=f"support {vehicle + 1}")
    axes[0].set(ylabel="Connector force (N)", title="A3 force, yaw and support response")
    axes[1].set_ylabel("Yaw rate (rad/s)")
    axes[2].set_ylabel("Support load (N)")
    axes[2].set_xlabel("Time (s)")
    axes[0].legend(ncol=4, fontsize=8)
    axes[1].legend()
    for axis in axes:
        axis.grid(alpha=0.25)
    paths += _save(fig, figures, "force_yaw_support_a3")

    impulse_norm = np.linalg.norm(arrays["force_interval_impulse_world_ns"], axis=2)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for vehicle in range(4):
        axes[0].plot(t, arrays["force_payload_body_n"][:, vehicle, 0], lw=0.85, label=f"point {vehicle + 1}")
        axes[1].plot(t, arrays["force_payload_body_n"][:, vehicle, 1], lw=0.85)
        axes[2].plot(t, impulse_norm[:, vehicle], lw=0.85)
    axes[0].set(ylabel="Horizontal force (N)", title="A3 four-point force components and interval impulse")
    axes[1].set_ylabel("Vertical force (N)")
    axes[2].set(ylabel="Impulse norm (N s)", xlabel="Time (s)")
    axes[0].legend(ncol=4, fontsize=8)
    for axis in axes:
        axis.axhline(0.0, color="black", lw=0.5)
        axis.grid(alpha=0.25)
    paths += _save(fig, figures, "force_components_impulse_a3")

    grouped = {mode: [] for mode in ("A0", "A1", "A2", "A3")}
    for row in attribution_rows:
        grouped[row["actuator_mode"]].append(float(row["actual_icr_p95_mps"]))
    means = [float(np.mean(grouped[mode])) for mode in grouped]
    fig, axis = plt.subplots(figsize=(7.5, 4.8))
    modes = list(grouped)
    axis.bar(modes, means, color=[COLORS[mode] for mode in modes])
    axis.set(ylabel="Mean trajectory P95 ICR residual (m/s)", title="A0-A3 paired attribution summary")
    axis.grid(axis="y", alpha=0.25)
    paths += _save(fig, figures, "actuator_attribution_summary")

    manifest = {
        "protocol_path": str(protocol_path),
        "protocol_sha256": sha256(protocol_path),
        "source_files": [
            {"path": str(path), "sha256": sha256(path)} for path in source_paths
        ],
        "figures": [
            {"path": path, "sha256": sha256(Path(path))} for path in paths
        ],
    }
    (figures / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return manifest

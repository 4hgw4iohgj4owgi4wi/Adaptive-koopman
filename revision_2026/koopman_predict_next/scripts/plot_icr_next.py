from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from contracts import sha256
from plot_icr_fix import COLORS, _save, _system_yaw, plot_i1


REQUIRED_N2_FIGURE_STEMS = (
    "steering_request_actual_a0_a3",
    "yaw_vehicle_payload_system",
    "force_components_a0_a3",
    "support_load_a0_a3",
    "array_stretch_internal_force",
)


def _payload_anchors(summary: dict) -> np.ndarray:
    values = json.loads(summary["params_json"])["values"]
    length = float(values["payload"]["length_m"])
    width = float(values["payload"]["width_m"])
    return np.asarray(
        [
            [0.5 * length, 0.5 * width],
            [0.5 * length, -0.5 * width],
            [-0.5 * length, 0.5 * width],
            [-0.5 * length, -0.5 * width],
        ]
    )


def plot_n2(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    request_example: dict[str, np.ndarray],
    attribution_rows: list[dict],
    output: Path,
    source_paths: list[Path],
    protocol_path: Path,
) -> dict:
    manifest = plot_i1(
        trajectories,
        request_example,
        attribution_rows,
        output,
        source_paths,
        protocol_path,
    )
    figures = output / "figures"
    new_paths: list[str] = []
    representative = {
        identity["actuator_mode"]: (identity, arrays, summary)
        for identity, arrays, summary in trajectories
        if identity["direction"] == "left" and identity["plant"] == "V1-ES"
    }

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for mode in ("A0", "A1", "A2", "A3"):
        _, arrays, _ = representative[mode]
        time_s = arrays["time_s"]
        axes[0].plot(
            time_s,
            np.max(arrays["tire_raw_utilization"], axis=1),
            color=COLORS[mode],
            lw=1.0,
            label=mode,
        )
        axes[1].plot(
            time_s,
            np.max(np.abs(arrays["actual_steering_rate_substeps_radps"]), axis=(1, 2)),
            color=COLORS[mode],
            lw=1.0,
        )
        axes[2].plot(
            time_s,
            arrays["icr_actual_residual_mps"],
            color=COLORS[mode],
            lw=1.0,
        )
    axes[0].axhline(0.90, color="black", ls="--", lw=0.8, label="deployment gate")
    axes[1].axhline(1.2, color="black", ls="--", lw=0.8)
    axes[0].set(ylabel="Raw tire utilization", title="D2 switch response: counterfactual versus deployment modes")
    axes[1].set_ylabel("Peak steering rate (rad/s)")
    axes[2].set(ylabel="Actual ICR residual (m/s)", xlabel="Time (s)")
    axes[0].legend(ncol=5, fontsize=8)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "switch_tire_rate_icr")

    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    for axis, mode in zip(axes, ("A0", "A1", "A2", "A3")):
        _, arrays, summary = representative[mode]
        time_s = arrays["time_s"]
        state = np.asarray(arrays["state30"], dtype=float)
        for vehicle, index in enumerate((5, 11, 17, 23), start=1):
            axis.plot(time_s, state[:, index], lw=0.65, alpha=0.8, label=f"vehicle {vehicle}")
        axis.plot(time_s, state[:, 29], color="black", lw=1.0, label="payload")
        axis.plot(time_s, _system_yaw(arrays, summary), color="red", lw=0.9, label="system")
        axis.set_ylabel(f"{mode}\nrad/s")
    axes[0].set_title("A0-A3 individual-vehicle, payload and inertia-weighted system yaw")
    axes[-1].set_xlabel("Time (s)")
    axes[0].legend(ncol=6, fontsize=7)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "yaw_vehicle_payload_system")

    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    for axis, mode in zip(axes, ("A0", "A1", "A2", "A3")):
        _, arrays, _ = representative[mode]
        time_s = arrays["time_s"]
        requested = np.asarray(arrays["requested_control4x2"], dtype=float)[:, :, 1]
        actual = np.asarray(arrays["actual_steering_rad"], dtype=float)
        for vehicle in range(4):
            color = plt.cm.tab10(vehicle)
            axis.plot(time_s, requested[:, vehicle], color=color, lw=0.55, alpha=0.55)
            axis.plot(time_s, actual[:, vehicle], color=color, lw=0.9, label=f"vehicle {vehicle + 1}")
        axis.set_ylabel(f"{mode}\nrad")
    axes[0].set_title("Requested (thin) and actual (thick) steering for A0-A3")
    axes[-1].set_xlabel("Time (s)")
    axes[0].legend(ncol=4, fontsize=7)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "steering_request_actual_a0_a3")

    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    for axis, mode in zip(axes, ("A0", "A1", "A2", "A3")):
        _, arrays, _ = representative[mode]
        time_s = arrays["time_s"]
        force = np.asarray(arrays["force_payload_body_n"], dtype=float)
        for point in range(4):
            color = plt.cm.tab10(point)
            axis.plot(time_s, force[:, point, 0], color=color, lw=0.8, label=f"P{point + 1} Fx")
            axis.plot(time_s, force[:, point, 1], color=color, lw=0.65, ls="--", label=f"P{point + 1} Fy")
        axis.set_ylabel(f"{mode}\nN")
        axis.axhline(0.0, color="black", lw=0.45)
    axes[0].set_title("A0-A3 four-point payload-body forces: longitudinal Fx and lateral Fy")
    axes[-1].set_xlabel("Time (s)")
    axes[0].legend(ncol=4, fontsize=6)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "force_components_a0_a3")

    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    for axis, mode in zip(axes, ("A0", "A1", "A2", "A3")):
        _, arrays, _ = representative[mode]
        time_s = arrays["time_s"]
        support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
        for point in range(4):
            axis.plot(time_s, support[:, point], lw=0.75, label=f"P{point + 1}")
        axis.set_ylabel(f"{mode}\nN")
    axes[0].set_title("A0-A3 four-point vertical payload support loads")
    axes[-1].set_xlabel("Time (s)")
    axes[0].legend(ncol=4, fontsize=7)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "support_load_a0_a3")

    worst = max(
        trajectories,
        key=lambda item: float(np.max(item[1]["icr_actual_residual_mps"])),
    )
    identity, arrays, summary = worst
    sample = int(np.argmax(arrays["icr_actual_residual_mps"]))
    force = np.asarray(arrays["force_payload_body_n"][sample], dtype=float)
    magnitude = np.linalg.norm(force, axis=1)
    unit = force / np.maximum(magnitude[:, None], 1.0e-12)
    anchors = _payload_anchors(summary)
    fig, axis = plt.subplots(figsize=(7.5, 5.5))
    axis.scatter(anchors[:, 0], anchors[:, 1], color="black")
    for index in range(4):
        axis.arrow(
            anchors[index, 0],
            anchors[index, 1],
            unit[index, 0],
            unit[index, 1],
            width=0.012,
            head_width=0.10,
            length_includes_head=True,
            color=plt.cm.tab10(index),
        )
        axis.text(
            anchors[index, 0] + 1.08 * unit[index, 0],
            anchors[index, 1] + 1.08 * unit[index, 1],
            f"P{index + 1}: {magnitude[index]:.1f} N",
            fontsize=8,
        )
    resultant = np.sum(force, axis=0)
    resultant_norm = float(np.linalg.norm(resultant))
    if resultant_norm > 1.0e-12:
        axis.arrow(0.0, 0.0, *(resultant / resultant_norm), width=0.018, head_width=0.12, color="red", length_includes_head=True)
    axis.set(
        xlabel="Payload longitudinal x (m)",
        ylabel="Payload lateral y (m)",
        title=(
            f"Four-point force directions at worst actual ICR\n"
            f"{identity['direction']} {identity['plant']} {identity['actuator_mode']}, "
            f"t={float(arrays['time_s'][sample]):.3f} s, resultant={resultant_norm:.1f} N"
        ),
        aspect="equal",
    )
    axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "force_direction_worst_icr")

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for mode in ("A0", "A1", "A2", "A3"):
        _, arrays, _ = representative[mode]
        t = arrays["time_s"]
        tension = np.asarray(arrays["tension_proxy_n"], dtype=float)
        axes[0].plot(t, tension[:, 0], color=COLORS[mode], lw=1.0, label=mode)
        axes[1].plot(t, tension[:, 1], color=COLORS[mode], lw=1.0)
        internal = np.linalg.norm(
            np.asarray(arrays["internal_force_vector_n"], dtype=float), axis=1
        )
        axes[2].plot(t, internal, color=COLORS[mode], lw=1.0)
    axes[0].set(ylabel="Front/rear stretch proxy (N)", title="Array internal stretch diagnostics")
    axes[1].set_ylabel("Left/right stretch proxy (N)")
    axes[2].set(ylabel="Full internal-force norm (N)", xlabel="Time (s)")
    axes[0].legend(ncol=4)
    for axis in axes:
        axis.grid(alpha=0.25)
    new_paths += _save(fig, figures, "array_stretch_internal_force")

    manifest["figures"].extend(
        {"path": path, "sha256": sha256(Path(path))} for path in new_paths
    )
    manifest["generator_files"] = [
        {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
        {
            "path": str((Path(__file__).resolve().parent / "plot_icr_fix.py")),
            "sha256": sha256(Path(__file__).resolve().parent / "plot_icr_fix.py"),
        },
    ]
    generated_names = {Path(item["path"]).stem for item in manifest["figures"]}
    missing_required = sorted(set(REQUIRED_N2_FIGURE_STEMS) - generated_names)
    if missing_required:
        raise RuntimeError(f"required N2 figures were not generated: {missing_required}")
    manifest["required_n2_figure_stems"] = list(REQUIRED_N2_FIGURE_STEMS)
    manifest["required_n2_figures_passed"] = True
    (figures / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return manifest

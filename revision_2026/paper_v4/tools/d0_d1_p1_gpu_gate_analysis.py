"""Read-only D0 GPU-entry audit and D1 P1 late-tracking analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), {str(value): index for index, value in enumerate(data["columns"])}


def validate_protocol(path: Path, expected_sha: str, paper: Path) -> dict:
    if sha(path) != expected_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "D0_D1_READ_ONLY_NO_GPU_OR_DYNAMICS_EXECUTION":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        source = paper / item["path"]
        if not source.is_file() or sha(source) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    return protocol


def finite_stats(value) -> dict:
    value = np.asarray(value, float)
    return {
        "rmse": float(np.sqrt(np.mean(np.square(value)))),
        "mean": float(np.mean(value)),
        "mean_absolute": float(np.mean(np.abs(value))),
        "maximum_absolute": float(np.max(np.abs(value))),
        "start": float(value[0]),
        "end": float(value[-1]),
    }


def slope(time, value) -> float:
    if len(time) < 2:
        return float("nan")
    return float(np.polyfit(np.asarray(time, float), np.asarray(value, float), 1)[0])


def correlation(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def save_figure(fig, output: Path, stem: str) -> list[str]:
    fig.tight_layout()
    files = [f"{stem}.png", f"{stem}.svg"]
    fig.savefig(output / files[0], dpi=240)
    fig.savefig(output / files[1])
    plt.close(fig)
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    protocol = validate_protocol(protocol_path, args.protocol_sha, paper)
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    gpu_line = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().splitlines()[0]
    gpu_values = [item.strip() for item in gpu_line.split(",")]
    prior_protocol = json.loads((paper / protocol["d0"]["prior_protocol"]).read_text(encoding="utf-8"))
    prior_failure = json.loads((paper / protocol["d0"]["prior_failure"]).read_text(encoding="utf-8"))
    prior_g0 = json.loads((paper / protocol["d0"]["prior_g0"]).read_text(encoding="utf-8"))
    source_identity = {}
    for item in prior_protocol["identity_files"]:
        if "/gpu_port/" in item["path"] or item["path"].endswith("gpu_g0_g2_qualify.py"):
            path = paper / item["path"]
            source_identity[item["path"]] = bool(path.is_file() and sha(path) == item["sha256"])
    current_taskbook_sha = sha(paper / "experiment.md")
    d0_checks = {
        "device_present_and_named_rtx5080": gpu_values[0] == "NVIDIA GeForce RTX 5080",
        "prior_g0_pass": prior_g0.get("status") == "PASS",
        "gpu_sources_match_v3": all(source_identity.values()),
        "newer_g1_report_present": (paper / "results/20260915_RTX5080_G0_G2_03/g1_physics.json").is_file(),
        "newer_g2_report_present": (paper / "results/20260915_RTX5080_G0_G2_03/g2_fd_qp.json").is_file(),
        "prior_protocol_matches_current_taskbook": any(
            item["path"] == "experiment.md" and item["sha256"] == current_taskbook_sha for item in prior_protocol["identity_files"]
        ),
    }
    d0 = {
        "status": "GPU_ENTRY_PRESENT_QUALIFICATION_PENDING",
        "device": {"name": gpu_values[0], "driver": gpu_values[1], "memory_total_mib": float(gpu_values[2]), "memory_used_mib": float(gpu_values[3]), "utilization_percent": float(gpu_values[4])},
        "prior_g0": prior_g0,
        "prior_failure_status": prior_failure.get("status"),
        "prior_failure_reason": prior_failure.get("reason"),
        "gpu_source_identity_against_v3": source_identity,
        "current_taskbook_sha256": current_taskbook_sha,
        "prior_protocol_taskbook_sha256": next(item["sha256"] for item in prior_protocol["identity_files"] if item["path"] == "experiment.md"),
        "checks": d0_checks,
        "decision": "D1_READ_ONLY_ALLOWED; GPU_G1_G2_AND_CLOSED_LOOP_BLOCKED",
    }
    (output / "d0_gpu_entry_audit.json").write_text(json.dumps(d0, indent=2), encoding="utf-8")
    labels = ["RTX5080", "G0", "source ID", "G1", "G2", "taskbook ID"]
    values = [d0_checks[key] for key in d0_checks]
    colors = ["#2ca02c" if value else "#d62728" for value in values]
    fig, axis = plt.subplots(figsize=(9.5, 4.8))
    axis.bar(np.arange(len(labels)), np.ones(len(labels)), color=colors)
    axis.set(xticks=np.arange(len(labels)), xticklabels=labels, yticks=[], ylim=(0, 1.15), title="D0 GPU entry and qualification coverage")
    for index, value in enumerate(values):
        axis.text(index, 0.5, "PASS" if value else "MISSING/STALE", ha="center", va="center", color="white", fontweight="bold", rotation=90 if index >= 3 else 0)
    axis.text(0.01, -0.18, "Green is verified local evidence; red does not mean GPU hardware failure.", transform=axis.transAxes)
    d0_figures = save_figure(fig, output, "d0_gpu_entry_coverage")

    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.references import build_hairpin

    run = paper / protocol["d1"]["run"]
    raw, c = archive(run / "raw.npz")
    sub, s = archive(run / "substeps.npz")
    solver = [json.loads(line) for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    route = build_hairpin()
    distance = raw[:, c["reference_distance_m"]]
    reference = np.column_stack([np.interp(distance, route["s_m"], route[key]) for key in ("x_m", "y_m", "heading_rad", "curvature_1pm")])
    dx = raw[:, c["x24"]] - reference[:, 0]
    dy = raw[:, c["x25"]] - reference[:, 1]
    cosine, sine = np.cos(reference[:, 2]), np.sin(reference[:, 2])
    longitudinal = cosine * dx + sine * dy
    lateral = -sine * dx + cosine * dy
    position = np.hypot(dx, dy)
    heading = np.rad2deg(np.arctan2(np.sin(raw[:, c["x26"]] - reference[:, 2]), np.cos(raw[:, c["x26"]] - reference[:, 2])))
    forward_speed = raw[:, c["x27"]] - 2.0
    lateral_speed = raw[:, c["x28"]]
    yaw_rate = raw[:, c["x29"]] - 2.0 * reference[:, 3]
    time = raw[:, c["time_s"]]
    request_steering = np.rad2deg(raw[:, [c[f"request_delta{i}"] for i in range(4)]])
    actual_steering = np.rad2deg(raw[:, [c[f"actual_delta{i}"] for i in range(4)]])
    request_accel = raw[:, [c[f"request_accel{i}"] for i in range(4)]]
    steering_lag = request_steering - actual_steering
    force = raw[:, [c[f"point_force_norm{i}"] for i in range(4)]]
    tire = raw[:, [c[f"tire_utilization{i}"] for i in range(4)]]
    support = raw[:, [c[f"support_load{i}"] for i in range(4)]]
    boundaries = np.asarray(route["boundaries_m"], float)
    segment_names = ["entry_straight", "entry_transition", "constant_curvature", "exit_transition", "exit_straight_observed"]
    segment_ranges = list(zip(boundaries[:-2], boundaries[1:-1])) + [(boundaries[-2], float(distance[-1]) + 1e-12)]
    segments = {}
    for name, (start, end) in zip(segment_names, segment_ranges):
        mask = (distance >= start) & (distance < end)
        if not np.any(mask):
            continue
        indices = np.flatnonzero(mask)
        segments[name] = {
            "distance_range_m": [float(distance[indices[0]]), float(distance[indices[-1]])],
            "time_range_s": [float(time[indices[0]]), float(time[indices[-1]])],
            "samples": int(len(indices)),
            "position_error_m": finite_stats(position[indices]),
            "longitudinal_error_m": finite_stats(longitudinal[indices]),
            "lateral_error_m": finite_stats(lateral[indices]),
            "heading_error_deg": finite_stats(heading[indices]),
            "forward_speed_error_mps": finite_stats(forward_speed[indices]),
            "position_error_absolute_slope_mps": slope(time[indices], np.abs(position[indices])),
            "request_steering_limit_fraction": float(np.mean(np.isclose(np.abs(request_steering[indices]), 15.0, atol=1e-9))),
            "maximum_request_actual_steering_gap_deg": float(np.max(np.abs(steering_lag[indices]))),
            "maximum_force_n": float(np.max(force[indices])),
            "maximum_tire_utilization": float(np.max(tire[indices])),
            "minimum_support_n": float(np.min(support[indices])),
        }
    exit_mask = distance >= boundaries[-2]
    exit_indices = np.flatnonzero(exit_mask)
    command_from_raw = np.column_stack([raw[:, c[f"request_accel{i}"]] for i in range(4)] + [raw[:, c[f"request_delta{i}"]] for i in range(4)])
    command_from_raw = np.column_stack(tuple(sum(([raw[:, c[f"request_accel{i}"]], raw[:, c[f"request_delta{i}"]]] for i in range(4)), [])))
    solver_first = np.asarray([item["first_control"] for item in solver[: len(raw)]], float)
    previous_u = np.vstack([np.zeros((1, 8)), solver_first[:-1]])
    d1 = {
        "status": "PASS_READ_ONLY_ANALYSIS_COMPLETE",
        "experiment_verdict": "FAIL_LATE_TRACKING_DIVERGENCE_USER_DESIGNATED",
        "scope": "accepted 0-44 s prefix only; future 3.58 s unobserved; no dynamics replay",
        "samples": {"raw": len(raw), "substeps": len(sub), "solver": len(solver), "closed_solver_prefix": len(raw), "orphan_solver": len(solver) - len(raw)},
        "overall": {
            "position_error_m": finite_stats(position),
            "longitudinal_error_m": finite_stats(longitudinal),
            "lateral_error_m": finite_stats(lateral),
            "heading_error_deg": finite_stats(heading),
            "forward_speed_error_mps": finite_stats(forward_speed),
            "lateral_speed_mps": finite_stats(lateral_speed),
            "yaw_rate_error_radps": finite_stats(yaw_rate),
        },
        "route_segments": segments,
        "late_exit_correlations_not_causal": {
            "position_error_vs_max_abs_request_steering": correlation(position[exit_indices], np.max(np.abs(request_steering[exit_indices]), axis=1)),
            "position_error_vs_max_abs_actual_steering": correlation(position[exit_indices], np.max(np.abs(actual_steering[exit_indices]), axis=1)),
            "position_error_vs_max_request_actual_gap": correlation(position[exit_indices], np.max(np.abs(steering_lag[exit_indices]), axis=1)),
            "position_error_vs_configuration_error": correlation(position[exit_indices], raw[exit_indices, c["max_e_g_m"]]),
        },
        "input_and_memory": {
            "maximum_requested_steering_deg": float(np.max(np.abs(request_steering))),
            "maximum_actual_steering_deg": float(np.max(np.abs(actual_steering))),
            "requested_steering_limit_fraction": float(np.mean(np.isclose(np.abs(request_steering), 15.0, atol=1e-9))),
            "maximum_request_actual_gap_deg": float(np.max(np.abs(steering_lag))),
            "raw_request_matches_solver_first_control_max_abs": float(np.max(np.abs(command_from_raw - solver_first))),
            "previous_u_reconstructable_for_accepted_prefix": bool(np.isfinite(previous_u).all() and len(previous_u) == len(raw)),
            "beta_memory_saved": False,
            "full_recovery_state_available": False,
        },
        "observed_physical_bounds": {
            "maximum_point_force_n": float(np.max(force)),
            "maximum_internal_force_n": float(np.max(raw[:, c["internal_force_norm_n"]])),
            "maximum_tire_utilization": float(np.max(tire)),
            "minimum_support_n": float(np.min(support)),
            "force_ultimate_15kn_not_reached": bool(np.max(force) <= 15000.0 + 1e-6),
            "tire_limit_not_reached": bool(np.max(tire) <= 1.0 + 1e-9),
            "support_nonnegative": bool(np.min(support) >= 0.0),
        },
        "missing_evidence": [
            "unobserved final 179 control ticks",
            "saved beta memory required for exact checkpoint continuation",
            "full horizon controls and numerical QP slacks; solver log stores hashes and first/last controls only",
            "a preregistered runtime late-tracking failure threshold in the original P1 protocol",
        ],
        "root_cause_boundary": "segment correlations and timing are diagnostic candidates only; they do not prove plant, predictor, or solver causality",
        "decision": "D1_COMPLETE; D2_CAN_DEFINE_CANDIDATE; D3_BLOCKED_BY_G1_G2_AND_INCOMPLETE_RECOVERY_STATE",
    }
    (output / "d1_p1_late_tracking.json").write_text(json.dumps(d1, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 9.2))
    axes[0, 0].plot(route["x_m"], route["y_m"], "k--", label="Full frozen reference")
    axes[0, 0].plot(raw[:, c["x24"]], raw[:, c["x25"]], label="Accepted P1 payload")
    axes[0, 0].scatter(raw[-1, c["x24"]], raw[-1, c["x25"]], color="red", s=30, label="Last observed point")
    axes[0, 0].set(xlabel="World X (m)", ylabel="World Y (m)", title="Observed 0-44 s; remaining route unobserved")
    axes[0, 0].axis("equal")
    axes[0, 1].plot(time, position, label="Position magnitude")
    axes[0, 1].plot(time, longitudinal, label="Longitudinal")
    axes[0, 1].plot(time, lateral, label="Lateral")
    axes[0, 1].set(xlabel="Time (s)", ylabel="Error (m)", title="Payload tracking decomposition")
    axes[1, 0].plot(time, heading, label="Heading error")
    axes[1, 0].set(xlabel="Time (s)", ylabel="Error (deg)", title="Payload heading error")
    axes[1, 1].plot(time, forward_speed, label="Forward speed error")
    axes[1, 1].plot(time, lateral_speed, label="Lateral speed")
    axes[1, 1].plot(time, yaw_rate, label="Yaw-rate error")
    axes[1, 1].set(xlabel="Time (s)", ylabel="m/s or rad/s", title="Payload velocity errors")
    for axis in axes.flat:
        axis.grid(alpha=0.2); axis.legend(fontsize=8)
    fig.suptitle("P1 2 ms accepted prefix — user-designated late tracking divergence\nOriginal execution interrupted; no values beyond 44 s")
    d1_tracking_figures = save_figure(fig, output, "d1_tracking_decomposition")

    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    axes[0, 0].plot(time, reference[:, 3], label="Reference curvature")
    axes[0, 0].set(xlabel="Time (s)", ylabel="Curvature (1/m)", title="Frozen route transition")
    for index in range(4):
        axes[0, 1].plot(time, request_steering[:, index], label=f"V{index+1} request")
        axes[1, 0].plot(time, actual_steering[:, index], label=f"V{index+1} actual")
        axes[1, 1].plot(time, steering_lag[:, index], label=f"V{index+1}")
        axes[2, 0].plot(time, request_accel[:, index], label=f"V{index+1}")
    axes[0, 1].axhline(15, color="red", ls=":"); axes[0, 1].axhline(-15, color="red", ls=":")
    axes[0, 1].set(xlabel="Time (s)", ylabel="Requested steering (deg)", title="Requested steering and registered limits")
    axes[1, 0].set(xlabel="Time (s)", ylabel="Actual steering (deg)", title="Actual steering")
    axes[1, 1].set(xlabel="Time (s)", ylabel="Request - actual (deg)", title="Steering actuator gap")
    axes[2, 0].set(xlabel="Time (s)", ylabel="Acceleration (m/s²)", title="Requested accelerations")
    axes[2, 1].plot(time, np.max(force, axis=1) / 15000.0, label="Force / 15 kN")
    axes[2, 1].plot(time, np.max(tire, axis=1), label="Tire utilization")
    axes[2, 1].plot(time, np.maximum(0.0, -np.min(support, axis=1)) / 10000.0, label="Negative support proxy")
    axes[2, 1].axhline(1.0, color="red", ls=":", label="Registered hard boundary")
    axes[2, 1].set(xlabel="Time (s)", ylabel="Normalized value (1)", title="Observed physical gates; not QP slack")
    for axis in axes.flat:
        axis.grid(alpha=0.2); axis.legend(fontsize=7, ncol=2)
    fig.suptitle("P1 accepted prefix — reference, inputs and observed constraints\nCorrelations are not causal evidence")
    d1_signal_figures = save_figure(fig, output, "d1_transition_inputs_constraints")

    source_files = [paper / item["path"] for item in protocol["identity_files"]] + [protocol_path]
    manifest = {
        "science_status": "P1_FAIL_LATE_TRACKING_DIVERGENCE_USER_DESIGNATED; D1_READ_ONLY_COMPLETE",
        "figure_status": "PENDING_VISUAL_QA",
        "figures": d0_figures + d1_tracking_figures + d1_signal_figures,
        "source_files": [{"path": str(path), "sha256": sha(path)} for path in source_files],
        "result_files": [
            {"path": "d0_gpu_entry_audit.json", "sha256": sha(output / "d0_gpu_entry_audit.json")},
            {"path": "d1_p1_late_tracking.json", "sha256": sha(output / "d1_p1_late_tracking.json")},
        ],
        "caption_boundary": "User-designated late tracking divergence; original execution externally interrupted; observed 0-44 s only; remaining interval unobserved.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# D0 GPU入口核对与D1 P1晚段分析\n\nD0只核对现成GPU入口和资格证据；D1只读取2200周期前缀并分解跟踪误差、参考过渡、输入和已观测物理门。没有运行GPU或动力学。相关性不作为根因证明，未观测179周期不补画。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS_D0_D1_READ_ONLY", "d0": d0["status"], "d1": d1["status"], "output": str(output)}))


if __name__ == "__main__":
    main()

"""Seal and visualize an externally interrupted POST-R3 R4 run."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--observed-pid", type=int, required=True)
    parser.add_argument("--observed-at", required=True)
    args = parser.parse_args()
    run, protocol_path, out = args.run.resolve(), args.protocol.resolve(), args.out.resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_INTERRUPTION_EVIDENCE")
    if out.parent != run:
        raise ValueError("INTERRUPTION_OUTPUT_MUST_BE_INSIDE_RUN")
    out.mkdir()

    required = [run / name for name in ("raw.npz", "substeps.npz", "solver.jsonl", "status.json", "launch.json")]
    if not all(path.is_file() for path in required) or (run / "metrics.json").exists():
        raise ValueError("NOT_AN_UNFINALIZED_CHECKPOINT_RUN")
    raw, c = archive(run / "raw.npz")
    sub, s = archive(run / "substeps.npz")
    solver = [json.loads(line) for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    launch = json.loads((run / "launch.json").read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected = int(np.ceil((protocol["run"]["route_length_m"] / protocol["run"]["speed_mps"]) / protocol["run"]["controller_step_s"]))
    accepted = len(raw)
    solver_only = len(solver) - accepted
    if status.get("status") != "RUNNING" or accepted != status.get("completed_ticks") or solver_only < 0:
        raise ValueError("CHECKPOINT_IDENTITY_INCONSISTENT")
    if accepted == 0 or not np.isfinite(raw).all() or not np.isfinite(sub).all():
        raise ValueError("NONFINITE_OR_EMPTY_ACCEPTED_EVIDENCE")

    force = np.column_stack([sub[:, s[f"force_peak{i}"]] for i in range(4)])
    tire = np.column_stack([sub[:, s[f"tire_utilization{i}"]] for i in range(4)])
    support = np.column_stack([sub[:, s[f"support_load{i}"]] for i in range(4)])
    request = np.column_stack([raw[:, c[f"request_delta{i}"]] for i in range(4)])
    actual = np.column_stack([raw[:, c[f"actual_delta{i}"]] for i in range(4)])
    accepted_solver = solver[:accepted]
    all_solver_pass = all(item.get("status") == "PASS" and item.get("validation", {}).get("status") == "PASS" for item in solver)
    last_solver_time = datetime.fromtimestamp((run / "solver.jsonl").stat().st_mtime).astimezone().isoformat()
    report = {
        "status": "EXTERNAL_PROCESS_TERMINATION_INCOMPLETE",
        "science_status": "INCOMPLETE_NOT_A_SCIENTIFIC_PASS_OR_FAIL",
        "reason": "PROCESS_ABSENT_WITH_RUNNING_CHECKPOINT_AND_EMPTY_STDERR",
        "run": run.name,
        "observed_pid": args.observed_pid,
        "observed_at": args.observed_at,
        "launch_time": launch.get("started_local"),
        "last_solver_file_time": last_solver_time,
        "expected_ticks": expected,
        "accepted_ticks": accepted,
        "remaining_ticks": expected - accepted,
        "solver_records": len(solver),
        "solver_only_orphan_records": solver_only,
        "accepted_time_s": float(raw[-1, c["time_s"]]),
        "accepted_reference_distance_m": float(raw[-1, c["reference_distance_m"]]),
        "accepted_substeps": len(sub),
        "stderr_bytes": (run.parents[1] / "logs" / f"{run.name}.stderr.log").stat().st_size,
        "accepted_segment_diagnostics": {
            "maximum_point_force_n": float(np.max(force)),
            "maximum_tire_utilization": float(np.max(tire)),
            "minimum_support_load_n": float(np.min(support)),
            "maximum_requested_steering_deg": float(np.max(np.abs(np.rad2deg(request)))),
            "maximum_actual_steering_deg": float(np.max(np.abs(np.rad2deg(actual)))),
            "maximum_solver_wall_s": float(max(item["wall_s"] for item in accepted_solver)),
            "all_solver_and_nonlinear_validation_pass_including_orphans": bool(all_solver_pass),
        },
        "integrity_checks": {
            "checkpoint_status_running": status.get("status") == "RUNNING",
            "raw_matches_checkpoint_count": accepted == status.get("completed_ticks"),
            "raw_columns_present": len(c) == raw.shape[1],
            "substep_columns_present": len(s) == sub.shape[1],
            "accepted_arrays_finite": bool(np.isfinite(raw).all() and np.isfinite(sub).all()),
            "solver_prefix_covers_accepted_ticks": len(solver) >= accepted,
            "solver_ticks_contiguous": [item.get("tick") for item in solver] == list(range(len(solver))),
            "all_solver_and_nonlinear_validation_pass": bool(all_solver_pass),
            "force_below_ultimate_stop": float(np.max(force)) <= 15000.0 + 1e-6,
            "tire_within_capability": float(np.max(tire)) <= 1.0 + 1e-9,
            "support_nonnegative": float(np.min(support)) >= 0.0,
            "steering_within_limit": float(np.max(np.abs(request))) <= np.deg2rad(15.0) + 1e-9 and float(np.max(np.abs(actual))) <= np.deg2rad(15.0) + 1e-9,
        },
        "recovery_decision": "DO_NOT_SPLICE; RETRY_FROM_INITIAL_STATE_WITH_NEW_RUN_ID_AND_DEDUCT_ELAPSED_BUDGET",
        "sources": [{"path": str(path), "sha256": sha(path)} for path in required + [run / "solver.jsonl", protocol_path]],
    }
    (out / "interruption_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from paper_v4_core.references import build_hairpin

    route = build_hairpin()
    distance = raw[:, c["reference_distance_m"]]
    reference = np.column_stack([np.interp(distance, route["s_m"], route[key]) for key in ("x_m", "y_m", "heading_rad")])
    position_error = np.linalg.norm(raw[:, [c["x24"], c["x25"]]] - reference[:, :2], axis=1)
    heading_error = np.rad2deg(np.arctan2(np.sin(raw[:, c["x26"]] - reference[:, 2]), np.cos(raw[:, c["x26"]] - reference[:, 2])))
    time, subtime = raw[:, c["time_s"]], sub[:, s["time_s"]]
    colors = ["#315a9c", "#d95f02", "#1b9e77", "#7570b3"]
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 12.0))
    axes[0, 0].plot(route["x_m"], route["y_m"], "k--", label="Frozen payload reference")
    axes[0, 0].plot(raw[:, c["x24"]], raw[:, c["x25"]], color="#111111", label="Accepted payload actual")
    for index, color in enumerate(colors):
        axes[0, 0].plot(raw[:, c[f"x{6 * index}"]], raw[:, c[f"x{6 * index + 1}"]], color=color, lw=0.8, label=f"Vehicle {index + 1}")
    axes[0, 0].set(title=f"Interrupted route: {accepted}/{expected} accepted ticks", xlabel="World X (m)", ylabel="World Y (m)")
    axes[0, 0].axis("equal")
    axes[0, 1].plot(time, position_error, label="Payload position error")
    axes[0, 1].plot(time, raw[:, c["max_e_g_m"]], label="Maximum configuration error")
    error_twin = axes[0, 1].twinx()
    error_twin.plot(time, heading_error, color="#d95f02", label="Payload heading error")
    axes[0, 1].set(title="Accepted tracking evidence", xlabel="Time (s)", ylabel="Position error (m)")
    error_twin.set_ylabel("Heading error (deg)")
    axes[1, 0].plot(subtime, np.max(force, axis=1), label="Maximum point-force norm", lw=0.7)
    axes[1, 0].plot(subtime, np.max(np.abs(np.column_stack([sub[:, s[f"force_body_x{i}"]] for i in range(4)])), axis=1), label="Maximum |body Fx|", lw=0.7)
    axes[1, 0].plot(subtime, np.max(np.abs(np.column_stack([sub[:, s[f"force_body_y{i}"]] for i in range(4)])), axis=1), label="Maximum |body Fy|", lw=0.7)
    axes[1, 0].plot(time, raw[:, c["internal_force_norm_n"]], label="Internal-force norm", lw=0.8)
    axes[1, 0].set(title="Unsmoothed accepted-step forces", xlabel="Time (s)", ylabel="Force (N)")
    for index, color in enumerate(colors):
        axes[1, 1].plot(time, np.rad2deg(request[:, index]), color=color, label=f"V{index + 1} requested")
        axes[1, 1].plot(time, np.rad2deg(actual[:, index]), color=color, ls="--", alpha=0.75, label=f"V{index + 1} actual")
    axes[1, 1].axhline(15.0, color="#d62728", ls=":")
    axes[1, 1].axhline(-15.0, color="#d62728", ls=":")
    axes[1, 1].set(title="Accepted steering", xlabel="Time (s)", ylabel="Steering angle (deg)")
    wall = np.asarray([item["wall_s"] for item in accepted_solver])
    axes[2, 0].plot(time, wall, label="Optimization wall time")
    axes[2, 0].axhline(5.0, color="#d62728", ls=":", label="Original 5 s budget")
    axes[2, 0].set(title=f"Offline computation; {solver_only} solver-only orphan records excluded", xlabel="Control tick time (s)", ylabel="Wall time (s)")
    constraint_twin = axes[2, 1].twinx()
    for index, color in enumerate(colors):
        axes[2, 1].plot(subtime, tire[:, index], color=color, label=f"V{index + 1} tire")
        constraint_twin.plot(subtime, support[:, index], color=color, ls="--", alpha=0.7, label=f"V{index + 1} support")
    axes[2, 1].set(title="Accepted tire utilization and support", xlabel="Time (s)", ylabel="Tire utilization (1)")
    constraint_twin.set_ylabel("Support load (N)")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(fontsize=7, ncol=2)
    h1, l1 = axes[0, 1].get_legend_handles_labels(); h2, l2 = error_twin.get_legend_handles_labels()
    axes[0, 1].legend(h1 + h2, l1 + l2, fontsize=7)
    h1, l1 = axes[2, 1].get_legend_handles_labels(); h2, l2 = constraint_twin.get_legend_handles_labels()
    axes[2, 1].legend(h1 + h2, l1 + l2, fontsize=7, ncol=2)
    fig.suptitle("POST-R3 R4 P1, 2 ms — externally interrupted incomplete run\nDiagnostic only; not a scientific pass or fail")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    stem = "r4_P1_2ms_interrupted_diagnostics"
    fig.savefig(out / f"{stem}.png", dpi=240)
    fig.savefig(out / f"{stem}.svg")
    plt.close(fig)

    manifest = {
        "run": run.name,
        "science_status": report["science_status"],
        "figure_status": "PENDING_VISUAL_QA",
        "accepted_ticks": accepted,
        "expected_ticks": expected,
        "excluded_solver_only_orphan_records": solver_only,
        "figure": {"files": [f"{stem}.png", f"{stem}.svg"], "units": "XY m; error m/deg; force N; steering deg; wall s; tire utilization 1; support N"},
        "source_report": {"path": str(out / "interruption_report.json"), "sha256": sha(out / "interruption_report.json")},
        "generator": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
    }
    (out / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "README.md").write_text("# R4-P1-2ms中断诊断\n\n仅显示2200个证据闭合的已接受周期；10条只有solver而缺少raw/substep闭合的记录不计为完成。该图不构成科学PASS或FAIL。\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "accepted_ticks": accepted, "orphan_solver_records": solver_only, "figure_manifest": str(out / "figure_manifest.json")}))


if __name__ == "__main__":
    main()

"""Required single-run figures for POST-R3 C1/R4."""
from __future__ import annotations

import argparse
import hashlib
import json
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
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    run, audit_path, protocol_path = args.run.resolve(), args.audit.resolve(), args.protocol.resolve()
    figures = run / "figures"
    figures.mkdir(exist_ok=False)
    raw, c = archive(run / "raw.npz")
    sub, s = archive(run / "substeps.npz")
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    solver = [json.loads(line) for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert metrics["status"] == "COMPLETED" and audit["status"] == "PASS" and len(raw) == len(solver) == 2379
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
    axes[0, 0].plot(raw[:, c["x24"]], raw[:, c["x25"]], color="#111111", label="Payload actual")
    for index, color in enumerate(colors):
        axes[0, 0].plot(raw[:, c[f"x{6 * index}"]], raw[:, c[f"x{6 * index + 1}"]], color=color, lw=0.8, label=f"Vehicle {index + 1}")
    axes[0, 0].set(title="Full registered route", xlabel="World X (m)", ylabel="World Y (m)")
    axes[0, 0].axis("equal")
    axes[0, 1].plot(time, position_error, label="Payload position error")
    axes[0, 1].plot(time, raw[:, c["max_e_g_m"]], label="Maximum configuration error")
    twin_error = axes[0, 1].twinx()
    twin_error.plot(time, heading_error, color="#d95f02", label="Payload heading error")
    axes[0, 1].set(title="Tracking and configuration errors", xlabel="Time (s)", ylabel="Position error (m)")
    twin_error.set_ylabel("Heading error (deg)")
    force_norm = np.max(np.column_stack([sub[:, s[f"force_peak{i}"]] for i in range(4)]), axis=1)
    force_x = np.max(np.abs(np.column_stack([sub[:, s[f"force_body_x{i}"]] for i in range(4)])), axis=1)
    force_y = np.max(np.abs(np.column_stack([sub[:, s[f"force_body_y{i}"]] for i in range(4)])), axis=1)
    axes[1, 0].plot(subtime, force_norm, label="Maximum point-force norm", lw=0.7)
    axes[1, 0].plot(subtime, force_x, label="Maximum |payload-body Fx|", lw=0.7)
    axes[1, 0].plot(subtime, force_y, label="Maximum |payload-body Fy|", lw=0.7)
    axes[1, 0].plot(time, raw[:, c["internal_force_norm_n"]], label="Internal-force norm", lw=0.8)
    axes[1, 0].set(title="Unsmoothed accepted-step forces", xlabel="Time (s)", ylabel="Force (N)")
    for index, color in enumerate(colors):
        axes[1, 1].plot(time, np.rad2deg(raw[:, c[f"request_delta{index}"]]), color=color, label=f"V{index + 1} requested")
        axes[1, 1].plot(time, np.rad2deg(raw[:, c[f"actual_delta{index}"]]), color=color, ls="--", alpha=0.75, label=f"V{index + 1} actual")
    axes[1, 1].axhline(15.0, color="#d62728", ls=":")
    axes[1, 1].axhline(-15.0, color="#d62728", ls=":")
    tv = audit["input_diagnostics"]["request_steering_total_variation_deg"]
    axes[1, 1].set(title=f"Requested/actual steering; request TV max {max(tv):.1f} deg", xlabel="Time (s)", ylabel="Steering angle (deg)")
    wall = np.asarray([row["wall_s"] for row in solver])
    axes[2, 0].plot(time, wall, label="Optimization wall time")
    axes[2, 0].axhline(5.0, color="#d62728", ls=":", label="Original 5 s budget")
    axes[2, 0].set(title=f"Offline computation; total {metrics['wall_s'] / 3600.0:.3f} h", xlabel="Control tick time (s)", ylabel="Wall time (s)")
    constraint = axes[2, 1]
    support_axis = constraint.twinx()
    for index, color in enumerate(colors):
        constraint.plot(time, raw[:, c[f"tire_utilization{index}"]], color=color, label=f"V{index + 1} tire")
        support_axis.plot(time, raw[:, c[f"support_load{index}"]], color=color, ls="--", alpha=0.7, label=f"V{index + 1} support")
    constraint.set(title="Tire utilization and payload support", xlabel="Time (s)", ylabel="Tire utilization (1)")
    support_axis.set_ylabel("Support load (N)")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        handles, labels = axis.get_legend_handles_labels()
        if handles:
            axis.legend(fontsize=7, ncol=2)
    handles, labels = axes[0, 1].get_legend_handles_labels()
    handles2, labels2 = twin_error.get_legend_handles_labels()
    axes[0, 1].legend(handles + handles2, labels + labels2, fontsize=7)
    handles, labels = constraint.get_legend_handles_labels()
    handles2, labels2 = support_axis.get_legend_handles_labels()
    constraint.legend(handles + handles2, labels + labels2, fontsize=7, ncol=2)
    parameter, step = metrics["parameter_id"], 1000.0 * metrics["maximum_plant_step_s"]
    fig.suptitle(f"Centralized Full-State Physical Model Predictive Control\nPOST-R3 R4 {parameter}; Plant Maximum Integration Step {step:g} ms; one deterministic simulation")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    stem = f"r4_{parameter}_{step:g}ms_diagnostics"
    fig.savefig(figures / f"{stem}.png", dpi=240)
    fig.savefig(figures / f"{stem}.svg")
    plt.close(fig)
    sources = [run / name for name in ("raw.npz", "substeps.npz", "solver.jsonl", "metrics.json")] + [audit_path, protocol_path]
    manifest = {
        "run": run.name,
        "candidate_id": metrics["candidate_id"],
        "parameter_id": parameter,
        "method_full_name": metrics["identity"],
        "information_boundary": "Centralized full simulation state; offline diagnostic upper bound.",
        "plant_maximum_integration_step_ms": step,
        "source_files": [{"path": str(path), "sha256": sha(path)} for path in sources],
        "generator": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        "figure": {"files": [f"{stem}.png", f"{stem}.svg"], "fields_units": "XY m; errors m/deg; force N; steering deg; wall s; tire utilization 1; support N", "caption": f"POST-R3 R4 {parameter}, {step:g} ms maximum plant integration step; centralized full-state offline diagnostic; one deterministic simulation; force components and peaks are unsmoothed."},
        "science_status": "PASS_SINGLE_RUN_PHYSICAL_AND_EVIDENCE_PARAMETER_CONVERGENCE_PENDING",
        "figure_status": "PENDING_VISUAL_QA",
        "expected_figure_contract": protocol["expected_figures"],
    }
    (figures / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (figures / "README.md").write_text(f"# POST-R3 R4 {parameter} 单条图表\n\n包含路线、误差、未平滑受力分量/范数/内力、请求与实际转角、约束和耗时。单条通过不等于该参数三步长数值门通过。\n", encoding="utf-8")
    print(json.dumps({"status": "FIGURES_CREATED", "manifest": str(figures / "figure_manifest.json")}))


if __name__ == "__main__":
    main()

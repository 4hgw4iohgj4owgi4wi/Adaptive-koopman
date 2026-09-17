"""Create the required per-run figures for an EXP-R4-C force-bearing window."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


METHOD_NAMES = {
    "EXP-R4B-serial-v1": "Centralized Full-State Physical Model Predictive Control (serial)",
    "EXP-R4B-parallel8-v1": "Centralized Full-State Physical Model Predictive Control (8-process)",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_npz(path: Path) -> tuple[np.ndarray, list[str]]:
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(x) for x in data["columns"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--suffix", default="")
    args = parser.parse_args()
    run = args.run.resolve()
    protocol = args.protocol.resolve()
    figures = run / "figures"
    figures.mkdir(exist_ok=True)

    raw, raw_columns = load_npz(run / "raw.npz")
    sub, sub_columns = load_npz(run / "substeps.npz")
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    solver = [json.loads(line) for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rc = {name: i for i, name in enumerate(raw_columns)}
    sc = {name: i for i, name in enumerate(sub_columns)}
    assert raw.shape == (50, 63), raw.shape
    assert sub.shape == (500, 22), sub.shape
    assert len(solver) == 50, len(solver)
    assert status["status"] == "COMPLETED"

    method = METHOD_NAMES.get(status["implementation_id"], status["implementation_id"])
    t = raw[:, rc["time_s"]]
    ts = sub[:, sc["time_s"]]
    colors = ["#315a9c", "#d95f02", "#1b9e77", "#7570b3"]
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 12.0))

    axes[0, 0].plot(raw[:, rc["x24"]], raw[:, rc["x25"]], color="#315a9c", lw=2)
    axes[0, 0].scatter(raw[0, rc["x24"]], raw[0, rc["x25"]], marker="o", color="#1b9e77", label="Window start")
    axes[0, 0].scatter(raw[-1, rc["x24"]], raw[-1, rc["x25"]], marker="x", color="#d95f02", label="Window end")
    axes[0, 0].set(title="Payload path (reference XY unavailable in run file)", xlabel="World X (m)", ylabel="World Y (m)")

    axes[0, 1].plot(t, 1000.0 * raw[:, rc["max_e_g_m"]], color="#d95f02")
    axes[0, 1].set(title="Maximum configuration error", xlabel="Interval end time (s)", ylabel="Error (mm)")

    for i, color in enumerate(colors):
        axes[1, 0].plot(t, raw[:, rc[f"point_force_norm{i}"]], color=color, lw=1.5, label=f"Connection {i + 1}, control")
        axes[1, 0].plot(ts, sub[:, sc[f"force_peak{i}"]], color=color, lw=.8, alpha=.55, label=f"Connection {i + 1}, 2 ms peak")
    axes[1, 0].set(title="Unsmoothed connection-force norms", xlabel="Time (s)", ylabel="Force (N)")

    for i, color in enumerate(colors):
        axes[1, 1].plot(t, np.rad2deg(raw[:, rc[f"request_delta{i}"]]), color=color, lw=1.5, label=f"Vehicle {i + 1} requested")
        axes[1, 1].plot(t, np.rad2deg(raw[:, rc[f"actual_delta{i}"]]), color=color, lw=1.0, ls="--", label=f"Vehicle {i + 1} actual")
    axes[1, 1].set(title="Requested and actual steering", xlabel="Interval end time (s)", ylabel="Steering angle (deg)")

    wall = np.asarray([row["wall_s"] for row in solver], dtype=float)
    axes[2, 0].plot(t, wall, color="#315a9c", label="Observed optimization wall time")
    axes[2, 0].axhline(5.0, color="#d62728", ls=":", label="Original 5 s offline budget")
    axes[2, 0].set(title=f"Optimization cost; total window {status['wall_s'] / 60:.2f} min", xlabel="Control tick time (s)", ylabel="Wall time (s)")

    ax = axes[2, 1]
    ax2 = ax.twinx()
    for i, color in enumerate(colors):
        ax.plot(t, raw[:, rc[f"tire_utilization{i}"]], color=color, label=f"Vehicle {i + 1} tire")
        ax2.plot(t, raw[:, rc[f"support_load{i}"]], color=color, ls="--", alpha=.75, label=f"Vehicle {i + 1} support")
    ax.set(title="Tire utilization and support load", xlabel="Interval end time (s)", ylabel="Tire utilization (1)")
    ax2.set_ylabel("Support load (N)")

    for panel in axes.flat:
        panel.grid(alpha=.2)
    for panel in (axes[0, 0], axes[1, 0], axes[1, 1]):
        panel.legend(fontsize=7, ncol=2)
    axes[2, 0].legend(fontsize=8)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, ncol=2)
    fig.suptitle(f"{method}\nForce-bearing window 26.66-27.66 s; one deterministic simulation; no confidence interval", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .955))
    stem = "force_window_diagnostics" + args.suffix
    fig.savefig(figures / f"{stem}.png", dpi=240)
    fig.savefig(figures / f"{stem}.svg")
    plt.close(fig)

    source_files = []
    for path in (run / "raw.npz", run / "substeps.npz", run / "solver.jsonl", run / "status.json", protocol):
        source_files.append({"path": str(path), "sha256": sha256(path)})
    script_path = Path(__file__).resolve()
    manifest = {
        "run": run.name,
        "candidate_id": status["candidate_id"],
        "implementation_id": status["implementation_id"],
        "method_full_name": method,
        "protocol": str(protocol),
        "protocol_sha256": sha256(protocol),
        "window_s": [status["start_s"], status["end_s"]],
        "sample_counts": {"control_cycles": int(raw.shape[0]), "plant_substeps": int(sub.shape[0]), "solver_records": len(solver)},
        "statistics": "One deterministic force-bearing window; raw, unsmoothed values; no confidence interval.",
        "source_files": source_files,
        "generator": {"path": str(script_path), "sha256": sha256(script_path)},
        "figures": [{
            "name": stem,
            "files": [f"{stem}.png", f"{stem}.svg"],
            "experiment_question": "Does this implementation complete the registered force-bearing window while retaining trajectory, error, force, input, constraint, and cost evidence?",
            "fields_and_units": "Payload X/Y (m); configuration error (mm); point-force norm (N); requested/actual steering (deg); optimization wall time (s); tire utilization (1); support load (N).",
            "caption": f"{method}, centralized full-state information boundary, registered 26.66-27.66 s force-bearing window, one deterministic simulation. Raw force peaks are unsmoothed. Status: COMPLETED; original 5 s offline optimization budget remains failed.",
        }],
        "science_status": "RUN_COMPLETED_SINGLE_IMPLEMENTATION_ONLY_COMPARISON_PENDING",
        "figure_status": "PENDING_VISUAL_QA",
        "postprocess_note": "When suffix is nonempty, the original image remains preserved and this manifest selects the corrected no-empty-legend rendering; simulation data are not recomputed.",
    }
    (figures / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (figures / "README.md").write_text(
        "# 有力窗口单条图表\n\n"
        f"- 运行：`{run.name}`\n"
        f"- 方法：{method}\n"
        "- 工况：事前登记的26.66—27.66 s有力窗口，单次确定性仿真。\n"
        "- 图：轨迹、构形误差、未平滑四点力、请求/实际转角、求解耗时、轮胎利用率和支承载荷。\n"
        "- 边界：该图只证明本条运行已完成；串并行等价性要等配对比较，5 s离线预算仍未通过。\n"
        f"- 重绘：`E:\\anaconda\\python.exe {script_path} --run {run} --protocol {protocol}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "FIGURES_CREATED", "figure_status": "PENDING_VISUAL_QA", "manifest": str(figures / "figure_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()

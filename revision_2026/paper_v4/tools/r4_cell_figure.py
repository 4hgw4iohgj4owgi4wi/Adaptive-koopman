"""Per-run six-panel figure for R4 dynamics runs, completed or interrupted.

Satisfies the task-book figure contract:
  section 25.3 - every run writes its own figures/ directory, with PNG and SVG, a
  machine-readable manifest and a Chinese README; failures and interruptions must
  produce a diagnostic figure over the accepted segment only, with the unobserved
  remainder marked rather than drawn.
  section 25.4 - an R4 step/parameter run must show the full XY reference against
  the actual four-vehicle and payload trajectories.
  line 2116 - every dynamics experiment must carry trajectory, error, force and
  constraint, input, and cost information.

Read-only: it never reruns dynamics and never overwrites an existing figures/ tree.
"""
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

SPEED = 2.0
POSITION_INDEX = (0, 1, 6, 7, 12, 13, 18, 19)
HEADING_INDEX = (2, 8, 14, 20)
EXIT_STRAIGHT_START_M = 71.12831551628262


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--script-sha", default=None)
    parser.add_argument("--question", default=None)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[1]
    run = (paper / args.run).resolve()
    if not (run / "raw.npz").is_file():
        raise ValueError("RAW_MISSING")
    figures = run / "figures"
    if figures.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_FIGURES")

    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.references import build_hairpin

    raw, columns = load(run / "raw.npz")
    index = {name: position for position, name in enumerate(columns)}
    sub, sub_columns = load(run / "substeps.npz")
    sub_index = {name: position for position, name in enumerate(sub_columns)}
    route = build_hairpin()

    metrics_path = run / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else None
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    interruption_path = run / "interruption.json"
    interruption = json.loads(interruption_path.read_text(encoding="utf-8")) if interruption_path.is_file() else None

    # An interrupted run has no metrics.json, and its status.json is only the last
    # checkpoint record, which carries no plant step.  Falling back to a default
    # would silently mislabel the figure (it did: a 1 ms run was labelled 2 ms), so
    # the step is looked up in the protocol that names this run's output, and stays
    # unknown rather than guessed if no protocol matches.
    step_ms = None
    if metrics:
        step_ms = float(metrics["maximum_plant_step_s"]) * 1000.0
    else:
        for protocol_path in sorted((paper / "protocol").glob("*.json")):
            try:
                candidate = json.loads(protocol_path.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            declared = candidate.get("run", {}).get("output") if isinstance(candidate.get("run"), dict) else None
            if declared and (paper / declared).resolve() == run:
                step_ms = float(candidate["run"]["plant_max_step_ms"])
                break
    step_label = f"{step_ms:g} ms" if step_ms is not None else "UNKNOWN (no metrics and no matching protocol)"

    complete = bool(metrics and metrics.get("status") == "COMPLETED")
    ticks = raw.shape[0]
    # Expected ticks come from the run's own record: metrics for a finished run, the
    # last checkpoint's total for an interrupted one.  Hard-coding 2379 (as the first
    # version did) would misreport every 30-tick G3 window run.
    if metrics:
        expected = int(metrics.get("expected_iterations", ticks))
    else:
        expected = int(status.get("total_ticks", ticks))
    window_mode = bool(metrics and int(metrics.get("start_tick", 0)) > 0 and expected < 2379)
    window_name = (metrics or {}).get("window_name")
    step_ms = (metrics or status).get("maximum_plant_step_s", 0.002) * 1000.0
    time = raw[:, index["time_s"]]
    distance = raw[:, index["reference_distance_m"]]

    # --- error series, D1 convention -------------------------------------------------
    reference = np.column_stack([np.interp(distance, route["s_m"], route[key]) for key in ("x_m", "y_m", "heading_rad")])
    dx = raw[:, index["x24"]] - reference[:, 0]
    dy = raw[:, index["x25"]] - reference[:, 1]
    cosine, sine = np.cos(reference[:, 2]), np.sin(reference[:, 2])
    longitudinal = cosine * dx + sine * dy
    lateral = -sine * dx + cosine * dy
    position_error = np.hypot(dx, dy)
    heading_error_deg = np.rad2deg(np.arctan2(np.sin(raw[:, index["x26"]] - reference[:, 2]), np.cos(raw[:, index["x26"]] - reference[:, 2])))

    # Raw columns are interval-endpoint values; the frozen metrics take the peak over
    # all accepted substeps.  Both are reported, and the peak used in titles comes from
    # the substeps so that the figure and metrics.json agree.
    forces_endpoint = raw[:, [index[f"point_force_norm{i}"] for i in range(4)]]
    internal = raw[:, index["internal_force_norm_n"]]
    if sub.shape[0]:
        substep_peak = sub[:, [sub_index[f"force_peak{i}"] for i in range(4)]]
        forces = np.vstack([forces_endpoint, substep_peak])
        substep_peak_value = float(substep_peak.max())
    else:
        forces = forces_endpoint
        substep_peak_value = float(forces_endpoint.max())
    tire = raw[:, [index[f"tire_utilization{i}"] for i in range(4)]]
    support = raw[:, [index[f"support_load{i}"] for i in range(4)]]
    actual_steering = np.rad2deg(raw[:, [index[f"actual_delta{i}"] for i in range(4)]])
    request_steering = np.rad2deg(raw[:, [index[f"request_delta{i}"] for i in range(4)]])
    wall = raw[:, index["solver_wall_s"]]
    impulse = np.column_stack([
        np.cumsum(sub[:, sub_index[f"force_impulse_{axis}{i}"]]) for i in range(4) for axis in ("x", "y")
    ]) if sub.shape[0] else np.zeros((1, 8))

    figures.mkdir(parents=True)
    fig, axes = plt.subplots(2, 3, figsize=(19.0, 10.2))

    # 1 XY reference vs actual four vehicles and payload
    axes[0, 0].plot(route["x_m"], route["y_m"], color="black", linewidth=1.2, label="reference path")
    axes[0, 0].plot(raw[:, index["x24"]], raw[:, index["x25"]], color="#d62728", linewidth=1.6, label="payload (actual)")
    for i in range(4):
        axes[0, 0].plot(raw[:, index[f"x{6 * i}"]], raw[:, index[f"x{6 * i + 1}"]], linewidth=1.0, label=f"vehicle {i + 1}")
    axes[0, 0].scatter([raw[0, index["x24"]]], [raw[0, index["x25"]]], color="green", zorder=5, s=28, label="start")
    axes[0, 0].scatter([raw[-1, index["x24"]]], [raw[-1, index["x25"]]], color="black", zorder=5, s=28, marker="x", label="last accepted tick")
    if not complete and not window_mode:
        axes[0, 0].scatter([route["x_m"][-1]], [route["y_m"][-1]], color="#8b0000", zorder=5, s=40, marker="*", label="route end (NOT reached)")
    axes[0, 0].set(xlabel="X (m)", ylabel="Y (m)", title="XY reference versus actual four vehicles and payload",
                   aspect="equal")
    axes[0, 0].legend(fontsize=7, loc="best")
    axes[0, 0].grid(alpha=0.25)

    # 2 error series
    axes[0, 1].plot(time, longitudinal, label="longitudinal (m)")
    axes[0, 1].plot(time, lateral, label="lateral (m)")
    axes[0, 1].plot(time, position_error, label="position norm (m)", linestyle="--")
    axes[0, 1].axhline(0.0, color="#7f7f7f", linewidth=0.8)
    axes[0, 1].set(xlabel="time (s)", ylabel="payload error (m)",
                   title=f"Payload error, D1 convention — final position {position_error[-1]:.4f} m")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    axes[0, 2].plot(time, heading_error_deg, color="#9467bd")
    axes[0, 2].axhline(0.0, color="#7f7f7f", linewidth=0.8)
    axes[0, 2].set(xlabel="time (s)", ylabel="heading error (deg)",
                   title=f"Heading error — RMSE {np.sqrt(np.mean(heading_error_deg ** 2)):.4f} deg")

    axes[0, 2].grid(alpha=0.25)

    # 3 four-point forces and internal force
    for i in range(4):
        axes[1, 0].plot(time, forces_endpoint[:, i], linewidth=1.0, label=f"point {i + 1} (endpoint)")
    axes[1, 0].plot(time, internal, color="black", linewidth=1.4, label="internal force norm")
    axes[1, 0].axhline(15000.0, color="red", linestyle=":", label="15000 N ultimate gate")
    axes[1, 0].set(xlabel="time (s)", ylabel="force (N)",
                   title=f"Forces — substep peak point {substep_peak_value:.3f} N, peak internal {internal.max():.3f} N")
    axes[1, 0].legend(fontsize=7.5)
    axes[1, 0].grid(alpha=0.25)

    # 4 impulse and tyre/support (two stacked quantities on twin axes)
    # The impulse x-axis must use the substeps own absolute timestamps.  The first
    # version used linspace(0, last_tick_time, n), which is harmless on a full route
    # but wrong by the whole route time on a 30-tick window run.
    substep_time = sub[:, sub_index["time_s"]] if sub.shape[0] else np.zeros(1)
    for i in range(4):
        magnitude = np.hypot(impulse[:, 2 * i], impulse[:, 2 * i + 1]) if impulse.shape[1] == 8 else np.zeros(1)
        axes[1, 1].plot(substep_time[: magnitude.size], magnitude, linewidth=1.0, label=f"point {i + 1}")
    axes[1, 1].set(xlabel="time (s)", ylabel="cumulative force impulse (N s)",
                   title="Force impulse accumulation (from accepted substeps)")
    axes[1, 1].legend(fontsize=7.5)
    axes[1, 1].grid(alpha=0.25)

    # 5 tyre and support
    for i in range(4):
        axes[1, 2].plot(time, tire[:, i], linewidth=1.0, label=f"tyre {i + 1}")
    axes[1, 2].axhline(1.0, color="red", linestyle=":", label="tyre limit 1.0")
    axes[1, 2].set(xlabel="time (s)", ylabel="tyre raw utilisation",
                   title=f"Tyre utilisation — peak {tire.max():.6f}; min support {support.min():.1f} N")
    axes[1, 2].legend(fontsize=7.5)
    axes[1, 2].grid(alpha=0.25)

    # steering and cost are added as a separate row via insets is avoided; instead annotate
    steering_note = (
        f"requested steering |max| {np.abs(request_steering).max():.6f} deg, "
        f"actual |max| {np.abs(actual_steering).max():.6f} deg\n"
        f"max |request - actual| {np.abs(request_steering - actual_steering).max():.6f} deg\n"
        f"solve cost: mean {wall.mean():.3f} s, max {wall.max():.3f} s, "
        f"{int(np.count_nonzero(wall <= 5.0))}/{wall.size} within the 5 s budget"
    )
    fig.text(0.012, 0.012, steering_note, fontsize=9, family="monospace", va="bottom")

    if complete:
        state = "COMPLETED"
    elif metrics:
        state = str(metrics.get("status"))
    elif interruption or status.get("status") != "COMPLETED":
        state = "INTERRUPTED"
    else:
        state = str(status.get("status"))
    fig.suptitle(
        (f"G3 window {window_name} — " if window_mode else f"R4 {run.name} — ")
        + f"plant step {step_label} — {state}, {ticks}/{expected} ticks, "
        + f"reference distance {distance[0]:.3f} to {distance[-1]:.3f} m"
        + ("" if complete else ("  (bounded window)" if window_mode else "  (unobserved remainder is NOT drawn)")),
        fontsize=12.5,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"{run.name}_six_panel.{suffix}"
        fig.savefig(figures / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(fig)

    summary = {
        "run": run.name,
        "state": state,
        "window_mode": window_mode,
        "window_name": window_name,
        "ticks": int(ticks),
        "expected_ticks": expected,
        "plant_step_ms": step_ms,
        "reference_distance_end_m": float(distance[-1]),
        "route_length_m": float(route["s_m"][-1]),
        "peak_point_force_n_substeps": substep_peak_value,
        "peak_point_force_n_endpoint": float(forces_endpoint.max()),
        "peak_internal_force_n": float(internal.max()),
        "peak_tyre_utilisation": float(tire.max()),
        "minimum_support_load_n": float(support.min()),
        "final_position_error_m": float(position_error[-1]),
        "max_position_error_m": float(position_error.max()),
        "final_lateral_error_m": float(lateral[-1]),
        "heading_rmse_deg": float(np.sqrt(np.mean(heading_error_deg ** 2))),
        "max_requested_steering_deg": float(np.abs(request_steering).max()),
        "max_actual_steering_deg": float(np.abs(actual_steering).max()),
        "max_request_minus_actual_steering_deg": float(np.abs(request_steering - actual_steering).max()),
        "solve_wall_mean_s": float(wall.mean()),
        "solve_wall_max_s": float(wall.max()),
        "solve_within_5s_fraction": float(np.mean(wall <= 5.0)),
    }
    (figures / "figure_data.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "science_status": state,
        "figure_status": "PENDING_VISUAL_QA",
        "run": run.name,
        "candidate_id": (metrics or {}).get("candidate_id", (status or {}).get("candidate_id", "EXP-R3-unfrozen-v1")),
        "implementation_id": (metrics or {}).get("implementation_id", (status or {}).get("implementation_id")),
        "protocol_sha256": (metrics or {}).get("protocol_sha256"),
        "experiment_question": args.question or "Does this R4 cell complete the frozen route inside the original hard gates, and what do its trajectory, error, force, input and cost records show?",
        "figures": names,
        "fields": {
            "trajectory": "state x0..x29: four vehicle poses and the payload pose in world coordinates",
            "error": "payload error against the route interpolated at the recorded reference distance, projected onto the reference heading (D1 convention)",
            "force": "four point-force norms, internal force norm, cumulative impulse from accepted substeps",
            "constraint": "tyre raw utilisation and payload support load",
            "input": "requested versus actual steering, maximum and maximum difference",
            "cost": "per-solve wall clock against the frozen 5 s budget",
        },
        "units": "m, s, N, N s, deg, dimensionless utilisation",
        "window": (f"window {window_name}, ticks {int((metrics or {}).get(chr(115)+chr(116)+chr(97)+chr(114)+chr(116)+chr(95)+chr(116)+chr(105)+chr(99)+chr(107), 0))}..{int((metrics or {}).get(chr(115)+chr(116)+chr(97)+chr(114)+chr(116)+chr(95)+chr(116)+chr(105)+chr(99)+chr(107), 0)) + ticks - 1}" if window_mode else f"ticks 0..{ticks - 1} of {expected}") + "; {'whole route' if complete else 'accepted segment only, unobserved remainder not drawn'}",
        "statistics_convention": "single trajectory, no confidence interval; peaks are taken over all accepted substeps",
        "generating_script": "tools/r4_cell_figure.py",
        "generating_script_sha256": args.script_sha or sha(Path(__file__)),
        "source_files": [
            {"path": f"results/{run.name}/raw.npz", "sha256": sha(run / "raw.npz")},
            {"path": f"results/{run.name}/substeps.npz", "sha256": sha(run / "substeps.npz")},
            {"path": f"results/{run.name}/status.json", "sha256": sha(run / "status.json")},
        ] + ([{"path": f"results/{run.name}/metrics.json", "sha256": sha(metrics_path)}] if metrics else [])
        + ([{"path": f"results/{run.name}/interruption.json", "sha256": sha(interruption_path)}] if interruption else []),
        "caption": (
            f"R4 {run.name}, plant step {step_label}, {state}. "
            f"{ticks} of {expected} ticks accepted, reference distance {distance[-1]:.3f} m of {route['s_m'][-1]:.3f} m. "
            f"Substep peak point force {substep_peak_value:.3f} N against the 15000 N gate; peak tyre utilisation {tire.max():.6f}; "
            f"minimum support {support.min():.1f} N; final payload position error {position_error[-1]:.4f} m."
            + ("" if complete else " The run was terminated externally; only the accepted segment is shown and the remainder is not extrapolated.")
        ),
        "claim_boundary": "Physical-gate passing and tracking quality are separate statements; this figure does not claim P1 tracking quality is acceptable, nor real-time behaviour from offline wall clock.",
    }
    (figures / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figures / "README.md").write_text(
        f"# {run.name} 单条六面板图\n\n"
        f"状态：**{state}**，植物步长 {step_label}，{ticks}/{expected} 周期，参考距离 {distance[-1]:.3f} m / {route['s_m'][-1]:.3f} m。\n\n"
        "六个面板覆盖§25.4对该类实验要求的五类信息：\n\n"
        "1. **XY 轨迹**：路线参考 vs 实际四车与货物（§25.4 明确要求）；\n"
        "2. **误差**：货物位置误差按 D1 口径分解为纵向/横向，另给位置范数；\n"
        "3. **航向误差**；\n"
        "4. **受力**：四点力范数、内部力范数、15000 N 硬界；冲量累积（由接受子步求和的单独面板）；\n"
        "5. **约束**：轮胎原始利用率与支撑载荷；\n"
        "6. **输入与耗时**：请求/实际转角最大值与最大差、每步求解墙钟与 5 s 预算（图下方文字块）。\n\n"
        + ("" if complete else
           "**中断说明**：本run被外部终止，仅绘制**已接受段**；未观测余段**不绘制、不外推**，"
           "XY图中以星号标出**未到达**的路线终点。\n")
        + "\n原始数据与图不可被后续run覆盖；重绘请重新运行 `tools/r4_cell_figure.py` 到新目录。\n",
        encoding="utf-8",
    )
    print(json.dumps({"run": run.name, "state": state, "figures": names, "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()

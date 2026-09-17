"""Compare a full-route GPU run against the historical CPU reference and the original hard gates.

Read-only.  Reports, separately:
  * completion and reference progress of the new route,
  * the original hard gates over the whole route,
  * CPU/GPU divergence over the overlapping prefix,
  * the configuration error, which the windowed runner does not maintain internally,
  * solve wall-clock statistics against the frozen 5 s per-solve budget.
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

POSITION_INDEX = (0, 1, 6, 7, 12, 13, 18, 19, 24, 25)
HEADING_INDEX = (2, 8, 14, 20, 26)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "R4-FULL-ROUTE-v1":
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.diagnostics.relative_motion import extract
    from paper_v4_core.e01_100m import params
    from paper_v4_core.pilot_runner import SPEED
    from paper_v4_core.reference_geometry import transition_targets

    new_run = paper / protocol["run"]["output"]
    reference_run = paper / "results/20260915_R4_P1_2MS01"
    raw, columns = load_archive(new_run / "raw.npz")
    index = {name: position for position, name in enumerate(columns)}
    ref_raw, ref_columns = load_archive(reference_run / "raw.npz")
    ref_index = {name: position for position, name in enumerate(ref_columns)}
    metrics = json.loads((new_run / "metrics.json").read_text(encoding="utf-8"))
    model = params(protocol["run"]["parameter_id"])

    ticks = raw.shape[0]
    overlap = int(min(ticks, ref_raw.shape[0]))
    new_state = raw[:overlap][:, [index[f"x{i}"] for i in range(30)]]
    ref_state = ref_raw[:overlap][:, [ref_index[f"x{i}"] for i in range(30)]]
    delta = np.abs(new_state - ref_state)
    position = delta[:, list(POSITION_INDEX)].max(axis=1)
    heading = delta[:, list(HEADING_INDEX)].max(axis=1)

    force_new = raw[:, [index[f"point_force_norm{i}"] for i in range(4)]].max(axis=1)
    force_ref = np.zeros(ticks)
    force_ref[:overlap] = ref_raw[:overlap][:, [ref_index[f"point_force_norm{i}"] for i in range(4)]].max(axis=1)

    # Configuration error from persisted state + reference distance + beta.
    # The reference yaw rate must come from the route curvature at the recorded
    # reference distance, exactly as post_r3_r4_runner.py computes it
    # (SPEED * _path_sample(distance)[3]); using zero would silently evaluate the
    # configuration error against a straight-line reference.
    from paper_v4_core.pilot_runner import _path_sample

    configuration_error = np.zeros(ticks)
    for k in range(ticks):
        distance = float(raw[k, index["reference_distance_m"]])
        beta = raw[k, [index[f"reference_beta{i}"] for i in range(4)]]
        yaw_rate = SPEED * float(_path_sample(distance)[3])
        qstar = transition_targets(np.asarray([SPEED, 0.0]), yaw_rate, beta, model)["centers"]
        state = raw[k, [index[f"x{i}"] for i in range(30)]]
        configuration_error[k] = float(np.max(np.linalg.norm(extract(state, model, qstar, beta)["e_g_m"], axis=1)))

    wall = raw[:, index["solver_wall_s"]]
    gates = protocol["gates"]
    gate_status = {
        "completion": metrics["status"],
        "route_length_m": float(metrics["reference_distance_m"]),
        "route_complete": bool(metrics["status"] == "COMPLETED" and metrics["reference_distance_m"] >= metrics["route_length_m"] - 1e-9),
        "maximum_point_force_n": float(metrics["maximum_point_force_n"]),
        "ultimate_force_pass": bool(metrics["maximum_point_force_n"] <= gates["ultimate_force_n"] + 1e-6),
        "maximum_tire_utilization": float(metrics["maximum_tire_utilization"]),
        "tire_pass": bool(metrics["maximum_tire_utilization"] <= gates["tire_limit"] + 1e-9),
        "minimum_support_load_n": float(metrics["minimum_support_load_n"]),
        "support_pass": bool(metrics["minimum_support_load_n"] >= gates["minimum_support_n"]),
    }

    report = {
        "status": "PASS_FULL_ROUTE_REPORT" if all(value for key, value in gate_status.items() if key.endswith("_pass") or key == "route_complete") else "FAIL_FULL_ROUTE_GATE",
        "scope": protocol["scope"],
        "new_run": protocol["run"]["output"],
        "reference_run": "results/20260915_R4_P1_2MS01",
        "ticks_completed": int(ticks),
        "expected_ticks": int(protocol["run"]["total_ticks"]),
        "overlap_ticks_compared": int(overlap),
        "hard_gates": gate_status,
        "divergence_over_prefix": {
            "position_max_abs_m": float(position.max()),
            "position_final_m": float(position[-1]),
            "heading_max_abs_rad": float(heading.max()),
            "heading_final_rad": float(heading[-1]),
            "force_peak_new_n": float(force_new[:overlap].max()),
            "force_peak_reference_n": float(force_ref[:overlap].max()),
            "position_series": position.tolist(),
            "heading_series": heading.tolist(),
        },
        "configuration_error_m": {
            "maximum": float(configuration_error.max()),
            "note": "computed by this comparator from persisted state, reference distance and reference beta; the windowed runner does not maintain it",
        },
        "solve_wall_clock_s": {
            "mean": float(wall.mean()), "median": float(np.median(wall)),
            "p95": float(np.percentile(wall, 95)), "max": float(wall.max()),
            "within_5s_budget": bool(wall.max() <= 5.0),
            "fraction_within_5s": float(np.mean(wall <= 5.0)),
        },
        "claim_boundary": "One GPU full route. No real-time claim from offline wall clock, no splicing onto the interrupted CPU prefix, no P1 root-cause claim.",
    }
    (output / "full_route_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    figure, axes = plt.subplots(2, 2, figsize=(14.5, 9.0))
    axes[0, 0].semilogy(np.arange(overlap), np.maximum(position, 1e-18), label="max position deviation (m)")
    axes[0, 0].semilogy(np.arange(overlap), np.maximum(heading, 1e-18), label="max heading deviation (rad)")
    first_nonzero = int(np.flatnonzero(position > 0.0)[0]) if np.any(position > 0.0) else -1
    axes[0, 0].axhline(1e-18, color="#7f7f7f", linestyle=":", label="1e-18 display floor (bitwise identical)")
    axes[0, 0].set(xlabel="tick index", ylabel="CPU/GPU divergence (log)",
                   title=f"GPU route vs historical CPU prefix ({overlap} ticks)\n"
                         f"position max {position.max():.3e} m; bitwise identical for ticks 0-{first_nonzero - 1 if first_nonzero > 0 else 0}, first difference at tick {first_nonzero}")
    axes[0, 0].legend(fontsize=7.5)
    axes[0, 0].grid(which="both", alpha=0.25)

    axes[0, 1].plot(np.arange(ticks), force_new, label="GPU route", color="#ff7f0e")
    axes[0, 1].plot(np.arange(overlap), force_ref[:overlap], label="CPU reference", color="#1f77b4", linestyle="--")
    axes[0, 1].axhline(gates["ultimate_force_n"], color="red", linestyle=":", label="15000 N ultimate gate")
    axes[0, 1].set(xlabel="tick index", ylabel="max point force (N)", title="Connector force over the route")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    axes[1, 0].plot(np.arange(ticks), wall, color="#2ca02c", marker=".", markersize=1.5, linestyle="none")
    axes[1, 0].axhline(5.0, color="red", linestyle=":", label="frozen 5 s budget")
    within = int(np.count_nonzero(wall <= 5.0))
    axes[1, 0].set(xlabel="tick index", ylabel="solve wall clock (s)",
                   title=f"Per-solve cost — mean {wall.mean():.3f} s, max {wall.max():.3f} s\n"
                         f"{within}/{wall.size} within the 5 s budget ({100.0 * within / wall.size:.3f}%), {wall.size - within} above it")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=0.25)

    axes[1, 1].plot(np.arange(ticks), configuration_error * 1000.0, color="#9467bd")
    axes[1, 1].set(xlabel="tick index", ylabel="max configuration error (mm)",
                   title=f"Configuration error from persisted state — max {configuration_error.max() * 1000:.3f} mm")
    axes[1, 1].grid(alpha=0.25)

    figure.suptitle("R4 P1 2 ms GPU full route: gates, CPU/GPU divergence, cost", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.96))
    figures = []
    for suffix in ("png", "svg"):
        name = f"full_route.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "figures": figures,
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [{"path": "full_route_report.json", "sha256": sha(output / "full_route_report.json")}],
        "claim_boundary": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# R4 P1 2ms GPU 全路线比较\n\n"
        "把GPU全路线结果与历史CPU参考在前2200个tick上逐tick比较，并在全程上核对原硬门、"
        "给出每步求解墙钟与构形误差（构形误差由本比较器从落盘状态/参考距离/beta计算，runner不内部维护）。\n\n"
        "只读；不做实时性、拼接或P1根因结论。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "hard_gates": gate_status,
                      "divergence": report["divergence_over_prefix"]["position_max_abs_m"],
                      "wall": report["solve_wall_clock_s"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

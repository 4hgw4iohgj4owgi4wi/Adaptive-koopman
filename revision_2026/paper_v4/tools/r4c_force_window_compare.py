"""Exact EXP-R4-C force-window comparison under the frozen integer-tick time contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_npz(folder: Path, name: str) -> tuple[np.ndarray, list[str]]:
    with np.load(folder / name, allow_pickle=False) as data:
        return data["values"].copy(), [str(x) for x in data["columns"]]


def load_solver(folder: Path) -> list[dict]:
    return [json.loads(line) for line in (folder / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def time_contract(values: np.ndarray, ticks: np.ndarray, dt: float) -> dict:
    expected = ticks.astype(float) * dt
    error = np.abs(values - expected)
    bound = 32.0 * np.finfo(np.float64).eps * np.maximum.reduce((np.ones_like(values), np.abs(values), np.abs(expected)))
    return {"pass": bool(np.all(error <= bound)), "maximum_error_s": float(error.max()), "minimum_bound_s": float(bound.min())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", type=Path, required=True)
    parser.add_argument("--parallel", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    serial, parallel, source, protocol, out = (p.resolve() for p in (args.serial, args.parallel, args.source, args.protocol, args.out))
    out.mkdir(parents=True, exist_ok=False)
    figures = out / "figures"
    figures.mkdir()

    sr, rc = load_npz(serial, "raw.npz")
    pr, pc = load_npz(parallel, "raw.npz")
    rr, xc = load_npz(source, "raw.npz")
    ss, sc = load_npz(serial, "substeps.npz")
    ps, psc = load_npz(parallel, "substeps.npz")
    rs, xsc = load_npz(source, "substeps.npz")
    assert rc == pc == xc and sc == psc == xsc
    assert sr.shape == pr.shape == (50, 63)
    assert ss.shape == ps.shape == (500, 22)
    raw_ticks = np.arange(1334, 1384)
    sub_ticks = np.arange(13331, 13831)
    source_raw_ticks = np.rint(rr[:, rc.index("time_s")] / .02).astype(int)
    source_sub_ticks = np.rint(rs[:, sc.index("time_s")] / .002).astype(int)
    ar = rr[np.isin(source_raw_ticks, raw_ticks)]
    ass = rs[np.isin(source_sub_ticks, sub_ticks)]
    assert ar.shape == sr.shape and ass.shape == ss.shape
    raw_physical = [i for i, name in enumerate(rc) if name not in ("time_s", "solver_wall_s")]
    sub_physical = [i for i, name in enumerate(sc) if name != "time_s"]

    sol_s, sol_p, sol_r_all = load_solver(serial), load_solver(parallel), load_solver(source)
    sol_r = [row for row in sol_r_all if 1333 <= int(row["tick"]) <= 1382]
    solver_ticks = np.arange(1333, 1383)
    solver_tick_exact = all(np.array_equal(np.asarray([int(row["tick"]) for row in rows]), solver_ticks) for rows in (sol_s, sol_p, sol_r))
    hashes_exact = all(a["problem_hashes"] == b["problem_hashes"] for a, b in zip(sol_s, sol_p))
    first_controls_sp = all(np.array_equal(np.asarray(a["first_control"]), np.asarray(b["first_control"])) for a, b in zip(sol_s, sol_p))
    first_controls_source = all(np.array_equal(np.asarray(a["first_control"]), np.asarray(b["first_control"])) and np.array_equal(np.asarray(a["first_control"]), np.asarray(c["first_control"])) for a, b, c in zip(sol_s, sol_p, sol_r))
    statuses = [json.loads((folder / "status.json").read_text(encoding="utf-8")) for folder in (serial, parallel)]
    complete = all(x["status"] == "COMPLETED" and x["iterations"] == 50 for x in statuses)
    solver_all_pass = all(row["status"] == "PASS" and row["validation"]["status"] == "PASS" for rows in (sol_s, sol_p) for row in rows)
    checks = {
        "both_runs_complete": complete,
        "raw_shape_exact": sr.shape == pr.shape == ar.shape == (50, 63),
        "substep_shape_exact": ss.shape == ps.shape == ass.shape == (500, 22),
        "solver_record_count_exact": len(sol_s) == len(sol_p) == len(sol_r) == 50,
        "solver_ticks_exact": solver_tick_exact,
        "solver_and_nonlinear_validation_all_pass": solver_all_pass,
        "serial_parallel_raw_physical_exact": bool(np.array_equal(sr[:, raw_physical], pr[:, raw_physical])),
        "serial_parallel_substeps_exact": bool(np.array_equal(ss, ps)),
        "serial_source_raw_physical_exact": bool(np.array_equal(sr[:, raw_physical], ar[:, raw_physical])),
        "parallel_source_raw_physical_exact": bool(np.array_equal(pr[:, raw_physical], ar[:, raw_physical])),
        "serial_source_substep_physical_exact": bool(np.array_equal(ss[:, sub_physical], ass[:, sub_physical])),
        "parallel_source_substep_physical_exact": bool(np.array_equal(ps[:, sub_physical], ass[:, sub_physical])),
        "serial_parallel_qp_hashes_exact": hashes_exact,
        "serial_parallel_first_controls_exact": first_controls_sp,
        "three_way_first_controls_exact": first_controls_source,
    }
    time_checks = {
        "serial_raw": time_contract(sr[:, 0], raw_ticks, .02),
        "parallel_raw": time_contract(pr[:, 0], raw_ticks, .02),
        "source_raw": time_contract(ar[:, 0], raw_ticks, .02),
        "serial_substeps": time_contract(ss[:, 0], sub_ticks, .002),
        "parallel_substeps": time_contract(ps[:, 0], sub_ticks, .002),
        "source_substeps": time_contract(ass[:, 0], sub_ticks, .002),
        "serial_solver": time_contract(np.asarray([row["time_s"] for row in sol_s]), solver_ticks, .02),
        "parallel_solver": time_contract(np.asarray([row["time_s"] for row in sol_p]), solver_ticks, .02),
        "source_solver": time_contract(np.asarray([row["time_s"] for row in sol_r]), solver_ticks, .02),
    }
    all_time_pass = all(item["pass"] for item in time_checks.values())
    max_force = float(ss[:, [sc.index(f"force_peak{i}") for i in range(4)]].max())
    force_gate = max_force == 288.0596665626036
    passed = all(checks.values()) and all_time_pass and force_gate
    report = {
        "status": "PASS_FORCE_WINDOW_EQUIVALENCE" if passed else "FAIL_FORCE_WINDOW_EQUIVALENCE",
        "protocol": str(protocol),
        "protocol_sha256": sha256(protocol),
        "window_s": [26.66, 27.66],
        "checks": checks,
        "time_identity_checks": time_checks,
        "registered_force_peak_exact": force_gate,
        "maximum_point_force_n": max_force,
        "serial_wall_s": statuses[0]["wall_s"],
        "parallel_wall_s": statuses[1]["wall_s"],
        "speedup": statuses[0]["wall_s"] / statuses[1]["wall_s"],
        "parallel_wall_per_control_cycle_s": statuses[1]["wall_s"] / 50.0,
        "full_route_2379_cycle_extrapolation_hours_not_guarantee": statuses[1]["wall_s"] / 50.0 * 2379.0 / 3600.0,
        "original_5s_offline_budget": "FAIL",
        "science_boundary": "This comparison can release only the 12 h full-route budget review; it is not a full-route accuracy or convergence result.",
    }
    (out / "force_window_equivalence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    c = {name: i for i, name in enumerate(rc)}
    cs = {name: i for i, name in enumerate(sc)}
    t = sr[:, 0]
    ts = ss[:, 0]
    fig, axes = plt.subplots(3, 2, figsize=(13.2, 12.0))
    axes[0, 0].plot(sr[:, c["x24"]], sr[:, c["x25"]], color="#315a9c", lw=2, label="Serial")
    axes[0, 0].plot(pr[:, c["x24"]], pr[:, c["x25"]], color="#d95f02", ls="--", label="8-process")
    axes[0, 0].set(title="Payload-path overlap", xlabel="World X (m)", ylabel="World Y (m)")
    physical_diff = np.max(np.abs(sr[:, raw_physical] - pr[:, raw_physical]), axis=1)
    axes[0, 1].plot(t, physical_diff, color="#d95f02", label="Max raw physical difference")
    axes[0, 1].set(title="Serial / 8-process physical difference", xlabel="Interval end time (s)", ylabel="Maximum absolute difference (native units)")
    colors = ["#315a9c", "#d95f02", "#1b9e77", "#7570b3"]
    for i, color in enumerate(colors):
        axes[1, 0].plot(ts, ss[:, cs[f"force_peak{i}"]], color=color, label=f"Connection {i + 1} serial")
        axes[1, 0].plot(ts, ps[:, cs[f"force_peak{i}"]], color=color, ls="--", alpha=.8, label=f"Connection {i + 1} 8-process")
        axes[1, 1].plot(t, np.rad2deg(sr[:, c[f"actual_delta{i}"]]), color=color, label=f"Vehicle {i + 1} serial")
        axes[1, 1].plot(t, np.rad2deg(pr[:, c[f"actual_delta{i}"]]), color=color, ls="--", alpha=.8, label=f"Vehicle {i + 1} 8-process")
    axes[1, 0].set(title="Unsmoothed 2 ms force peaks", xlabel="Time (s)", ylabel="Force (N)")
    axes[1, 1].set(title="Actual steering overlap", xlabel="Interval end time (s)", ylabel="Steering angle (deg)")
    raw_time_residual = np.maximum(np.abs(sr[:, 0] - raw_ticks * .02), np.abs(pr[:, 0] - raw_ticks * .02))
    raw_time_bound = 32 * np.finfo(np.float64).eps * np.maximum(1, np.abs(raw_ticks * .02))
    axes[2, 0].plot(t, raw_time_residual * 1e15, label="Maximum serial/8-process residual")
    axes[2, 0].plot(t, raw_time_bound * 1e15, ls=":", color="#d62728", label="Frozen 32 epsilon bound")
    axes[2, 0].set(title="Integer-tick time identity", xlabel="Interval end time (s)", ylabel="Time residual (fs)")
    wall_s = np.asarray([row["wall_s"] for row in sol_s])
    wall_p = np.asarray([row["wall_s"] for row in sol_p])
    axes[2, 1].plot(t, wall_s, color="#315a9c", label="Serial")
    axes[2, 1].plot(t, wall_p, color="#d95f02", label="8-process")
    axes[2, 1].axhline(5, color="#d62728", ls=":", label="Original 5 s offline budget")
    axes[2, 1].set(title=f"Optimization cost; speedup {report['speedup']:.3f}x", xlabel="Control tick time (s)", ylabel="Wall time (s)")
    for ax in axes.flat:
        ax.grid(alpha=.2)
        ax.legend(fontsize=7, ncol=2)
    fig.suptitle("Centralized Full-State Physical Model Predictive Control\nSerial / 8-process force-bearing-window equivalence; 26.66-27.66 s", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .955))
    stem = "force_window_equivalence"
    fig.savefig(figures / f"{stem}.png", dpi=240)
    fig.savefig(figures / f"{stem}.svg")
    plt.close(fig)

    files = []
    for folder in (serial, parallel, source):
        for name in ("raw.npz", "substeps.npz", "solver.jsonl"):
            path = folder / name
            files.append({"path": str(path), "sha256": sha256(path)})
    script = Path(__file__).resolve()
    manifest = {
        "run_pair": [serial.name, parallel.name],
        "candidate_id": statuses[0]["candidate_id"],
        "protocol": str(protocol),
        "protocol_sha256": sha256(protocol),
        "source_files": files,
        "generator": {"path": str(script), "sha256": sha256(script)},
        "figure": {"files": [f"{stem}.png", f"{stem}.svg"], "fields_and_units": "Payload XY (m); raw physical difference (native units); unsmoothed 2 ms force peak (N); actual steering (deg); time residual (fs); optimization wall time (s)."},
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
    }
    (figures / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (figures / "README.md").write_text(
        "# 有力窗口串并行配对图\n\n"
        "本图比较同一冻结候选在串行与8进程QP构建下的26.66—27.66 s闭环结果。受力为未平滑2 ms峰值；时间按预登记整数tick与32ε界审计。"
        "该结果只用于决定是否进入完整1 ms的12小时预算复核，不代表完整路线收敛或实时性。\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if passed else 20)


if __name__ == "__main__":
    main()

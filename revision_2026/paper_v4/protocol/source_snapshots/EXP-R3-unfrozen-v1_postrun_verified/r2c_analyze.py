"""Independent EXP-R2 R2c full-route audit and R3 candidate selection."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .e01_100m import LIMIT, RATE
from .pilot_runner import DT, ROUTE_LENGTH, SPEED
from .references import build_hairpin


EXPECTED_TICKS = int(np.ceil((ROUTE_LENGTH / SPEED) / DT))
EXPECTED_TIME_S = EXPECTED_TICKS * DT
PREDICTED_FORCE_BUDGET_N = 12000.0
ULTIMATE_STOP_N = 15000.0


def load(folder: Path):
    with np.load(folder / "raw.npz", allow_pickle=False) as z:
        raw = z["values"]
        raw_columns = {str(x): i for i, x in enumerate(z["columns"])}
    with np.load(folder / "substeps.npz", allow_pickle=False) as z:
        substeps = z["values"]
        substep_columns = {str(x): i for i, x in enumerate(z["columns"])}
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    solver = [
        json.loads(line)
        for line in (folder / "solver.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return raw, raw_columns, substeps, substep_columns, metrics, solver


def audit(label: str, folder: Path):
    raw, c, sub, s, metrics, solver = load(folder)
    point_raw = np.max(raw[:, [c[f"point_force_norm{i}"] for i in range(4)]])
    point_sub = np.max(sub[:, [s[f"force_peak{i}"] for i in range(4)]])
    point = float(max(point_raw, point_sub))
    tire_raw = np.max(raw[:, [c[f"tire_utilization{i}"] for i in range(4)]])
    tire_sub = np.max(sub[:, [s[f"tire_utilization{i}"] for i in range(4)]])
    tire = float(max(tire_raw, tire_sub))
    support_raw = np.min(raw[:, [c[f"support_load{i}"] for i in range(4)]])
    support_sub = np.min(sub[:, [s[f"support_load{i}"] for i in range(4)]])
    support = float(min(support_raw, support_sub))
    internal = float(np.max(raw[:, c["internal_force_norm_n"]]))
    configuration = float(np.max(raw[:, c["max_e_g_m"]]))
    route = build_hairpin()
    distance = raw[:, c["reference_distance_m"]]
    reference_x = np.interp(distance, route["s_m"], route["x_m"])
    reference_y = np.interp(distance, route["s_m"], route["y_m"])
    reference_heading = np.interp(distance, route["s_m"], route["heading_rad"])
    reference_yaw_rate = SPEED * np.interp(distance, route["s_m"], route["curvature_1pm"])
    position_error = np.hypot(raw[:, c["x24"]] - reference_x, raw[:, c["x25"]] - reference_y)
    heading_error = (raw[:, c["x26"]] - reference_heading + np.pi) % (2.0 * np.pi) - np.pi
    normalized_payload_error = np.c_[
        (raw[:, c["x24"]] - reference_x) / 0.1,
        (raw[:, c["x25"]] - reference_y) / 0.1,
        heading_error / np.deg2rad(2.0),
        (raw[:, c["x27"]] - SPEED) / 0.5,
        raw[:, c["x28"]] / 0.2,
        (raw[:, c["x29"]] - reference_yaw_rate) / 0.2,
    ]
    request_accel = raw[:, [c[f"request_accel{i}"] for i in range(4)]]
    request_delta = raw[:, [c[f"request_delta{i}"] for i in range(4)]]
    actual_delta = raw[:, [c[f"actual_delta{i}"] for i in range(4)]]
    first_controls = np.asarray([record["first_control"] for record in solver], float)
    recorded_controls = np.empty_like(first_controls)
    recorded_controls[:, 0::2] = request_accel
    recorded_controls[:, 1::2] = request_delta
    solver_walls = np.asarray([record["wall_s"] for record in solver], float)
    validation_forces = np.asarray(
        [record["validation"]["max_point_force_n"] for record in solver], float
    )
    validation_tires = np.asarray(
        [record["validation"]["max_tire_utilization"] for record in solver], float
    )
    validation_supports = np.asarray(
        [record["validation"]["minimum_support_n"] for record in solver], float
    )
    actual_delta_with_initial = np.vstack([np.zeros((1, 4)), actual_delta])
    checks = {
        "required_files": all(
            (folder / name).is_file()
            for name in ("raw.npz", "substeps.npz", "solver.jsonl", "metrics.json", "status.json")
        ),
        "finite_arrays": bool(np.all(np.isfinite(raw)) and np.all(np.isfinite(sub))),
        "raw_tick_count": len(raw) == EXPECTED_TICKS,
        "accepted_substeps": len(sub) >= EXPECTED_TICKS * 10,
        "solver_count": len(solver) == EXPECTED_TICKS,
        "all_solver_and_nonlinear_validation_pass": all(
            record["status"] == "PASS"
            and record["solver_status"] in ("solved", "solved inaccurate")
            and record["validation"]["status"] == "PASS"
            for record in solver
        ),
        "predicted_force_work_budget": bool(
            np.max(validation_forces) <= PREDICTED_FORCE_BUDGET_N + 1e-6
        ),
        "predicted_tire_and_support": bool(
            np.max(validation_tires) <= 1.0 + 1e-9 and np.min(validation_supports) >= 0.0
        ),
        "time_complete": bool(
            np.isclose(raw[-1, c["time_s"]], EXPECTED_TIME_S, atol=1e-12)
        ),
        "reference_complete": bool(
            np.isclose(raw[-1, c["reference_distance_m"]], ROUTE_LENGTH, atol=1e-9)
        ),
        "metrics_complete": bool(
            metrics["status"] == "COMPLETED" and metrics["trajectory_completed"]
        ),
        "actual_point_force_stop": point <= ULTIMATE_STOP_N + 1e-6,
        "actual_tire": tire <= 1.0 + 1e-9,
        "actual_support": support >= 0.0,
        "request_acceleration_bound": bool(np.max(np.abs(request_accel)) <= 2.0 + 1e-10),
        "request_steering_bound": bool(np.max(np.abs(request_delta)) <= LIMIT + 1e-10),
        "actual_steering_bound_and_rate": bool(
            np.max(np.abs(actual_delta)) <= LIMIT + 1e-10
            and np.max(np.abs(np.diff(actual_delta_with_initial, axis=0)))
            <= RATE * DT + 1e-10
        ),
        "request_is_solver_first_control": bool(
            np.allclose(recorded_controls, first_controls, rtol=0.0, atol=1e-12)
        ),
        "lambda_label_constant": bool(
            np.allclose(raw[:, c["lambda_internal"]], metrics["lambda_internal"], rtol=0.0, atol=0.0)
        ),
        "metrics_match_raw_and_substeps": bool(
            abs(point - metrics["maximum_point_force_n"]) < 1e-8
            and abs(internal - metrics["maximum_internal_force_norm_n"]) < 1e-8
            and abs(tire - metrics["maximum_tire_utilization"]) < 1e-10
            and abs(support - metrics["minimum_support_load_n"]) < 1e-8
            and abs(configuration - metrics["maximum_configuration_error_m"]) < 1e-10
        ),
        "source_identity": metrics["source_sha256"].lower()
        == "da2a33b6fcee6a975ae0561683720cc20d800a61c52cbd738fb165dfccafff82",
    }
    row = {
        "label": label,
        "folder": str(folder),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": {key: bool(value) for key, value in checks.items()},
        "duration_s": float(raw[-1, c["time_s"]]),
        "reference_distance_m": float(raw[-1, c["reference_distance_m"]]),
        "actual_payload_path_m": float(raw[-1, c["actual_payload_path_m"]]),
        "maximum_point_force_n": point,
        "maximum_predicted_point_force_n": float(np.max(validation_forces)),
        "maximum_internal_force_norm_n": internal,
        "maximum_tire_utilization": tire,
        "minimum_support_load_n": support,
        "maximum_configuration_error_m": configuration,
        "payload_position_rmse_m": float(np.sqrt(np.mean(position_error ** 2))),
        "maximum_payload_position_error_m": float(np.max(position_error)),
        "payload_heading_rmse_deg": float(np.rad2deg(np.sqrt(np.mean(heading_error ** 2)))),
        "payload_tracking_normalized_rms": float(np.sqrt(np.mean(normalized_payload_error ** 2))),
        "maximum_abs_request_steering_deg": float(np.rad2deg(np.max(np.abs(request_delta)))),
        "maximum_abs_actual_steering_deg": float(np.rad2deg(np.max(np.abs(actual_delta)))),
        "maximum_abs_acceleration_mps2": float(np.max(np.abs(request_accel))),
        "solver_wall_mean_s": float(np.mean(solver_walls)),
        "solver_wall_p95_s": float(np.quantile(solver_walls, 0.95)),
        "solver_wall_max_s": float(np.max(solver_walls)),
        "solver_over_5s_count": int(np.sum(solver_walls > 5.0)),
    }
    return row, (raw, c, sub, s, solver)


def main():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidate", action="append", nargs=2, required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    audits = []
    data = {}
    for label, path in args.candidate:
        row, arrays = audit(label, Path(path))
        audits.append(row)
        data[label] = arrays
    passed = [row for row in audits if row["status"] == "PASS"]
    selected = min(
        passed,
        key=lambda row: (
            row["maximum_internal_force_norm_n"],
            row["payload_tracking_normalized_rms"],
            row["solver_wall_mean_s"],
        ),
    )["label"] if passed else None
    comparison_complete = len(audits) == 2
    at_least_one_eligible = len(passed) >= 1
    report = {
        "status": "PASS" if comparison_complete and at_least_one_eligible else "FAIL",
        "selection_rule": "complete and hard/work gates, then internal force, payload tracking, then computation",
        "selected_for_r3": selected if comparison_complete and at_least_one_eligible else None,
        "eligible_candidates": [row["label"] for row in passed],
        "rejected_candidates": [
            {
                "label": row["label"],
                "failed_checks": [key for key, value in row["checks"].items() if not value],
            }
            for row in audits
            if row["status"] != "PASS"
        ],
        "audits": audits,
        "development_selection_only": True,
        "statistical_superiority_claimed": False,
        "source_sha256": sha(__file__),
    }
    save(out, "comparison.json", report)
    with (out / "comparison.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[key for key in audits[0] if key != "checks"])
        writer.writeheader()
        writer.writerows([{key: value for key, value in row.items() if key != "checks"} for row in audits])

    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    for label, (raw, c, _, _, solver) in data.items():
        t = raw[:, c["time_s"]]
        axes[0, 0].plot(t, np.max(raw[:, [c[f"point_force_norm{i}"] for i in range(4)]], axis=1), label=label)
        axes[0, 1].plot(t, raw[:, c["internal_force_norm_n"]], label=label)
        axes[1, 0].plot(t, raw[:, c["max_e_g_m"]], label=label)
        axes[1, 1].plot(t, np.max(raw[:, [c[f"tire_utilization{i}"] for i in range(4)]], axis=1), label=label)
        axes[2, 0].plot(t, np.rad2deg(np.max(np.abs(raw[:, [c[f"request_delta{i}"] for i in range(4)]]), axis=1)), label=label)
        axes[2, 1].plot(t, [record["wall_s"] for record in solver], label=label)
    for axis, ylabel in zip(
        axes.ravel(),
        ("max point force (N)", "internal force norm (N)", "max |e_g| (m)", "max tire utilization", "max request steer (deg)", "solver wall time (s)"),
    ):
        axis.set_xlabel("time (s)")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
        axis.legend()
    plotted_point_max = max(row["maximum_point_force_n"] for row in audits)
    plotted_tire_max = max(row["maximum_tire_utilization"] for row in audits)
    if plotted_point_max * 1.25 >= ULTIMATE_STOP_N:
        axes[0, 0].axhline(ULTIMATE_STOP_N, color="r", ls="--", lw=1)
    else:
        axes[0, 0].text(0.02, 0.96, "15 kN stop is off scale", transform=axes[0, 0].transAxes, va="top", color="r")
    if plotted_tire_max * 1.25 >= 1.0:
        axes[1, 1].axhline(1.0, color="r", ls="--", lw=1)
    else:
        axes[1, 1].text(0.02, 0.96, "tire limit 1 is off scale", transform=axes[1, 1].transAxes, va="top", color="r")
    axes[2, 0].axhline(np.rad2deg(LIMIT), color="r", ls="--", lw=1)
    axes[2, 1].axhline(5.0, color="r", ls="--", lw=1)
    fig.suptitle("EXP-R2 R2c full-route physical-MPC candidates")
    fig.savefig(out / "r2c_comparison.png", dpi=180)
    plt.close(fig)

    route = build_hairpin()
    fig, axis = plt.subplots(figsize=(9, 6), constrained_layout=True)
    axis.plot(route["x_m"], route["y_m"], "k--", label="frozen 11 m-transition reference")
    for label, (raw, c, _, _, _) in data.items():
        axis.plot(raw[:, c["x24"]], raw[:, c["x25"]], label=label)
    theta = np.linspace(0.0, np.pi, 500)
    ideal_x = np.r_[np.linspace(0.0, 24.0, 200), 24.0 + 11.5 * np.sin(theta), np.linspace(24.0, 0.0, 200)]
    ideal_y = np.r_[np.zeros(200), 11.5 * (1.0 - np.cos(theta)), np.full(200, 23.0)]
    axis.plot(ideal_x, ideal_y, ":", color="0.45", label="ideal instantaneous 11.5 m semicircle")
    axis.axis("equal")
    axis.set_xlabel("x (m)")
    axis.set_ylabel("y (m)")
    axis.grid(alpha=0.25)
    axis.legend()
    axis.set_title("Full route: actual frozen reference disclosed against ideal geometry")
    fig.savefig(out / "r2c_paths.png", dpi=180)
    plt.close(fig)

    lines = [
        "# R2c完整回头弯候选比较",
        "",
        f"状态：{report['status']}；R3开发候选：`{report['selected_for_r3']}`。该选择仅来自同批开发数据，不构成独立或统计显著的优越性证明。",
        "",
        "|候选|资格|失败检查|点力峰值 N|预测点力峰值 N|内力峰值 N|货物位置RMSE m|货物航向RMSE deg|最大构形误差 m|轮胎利用率|最小支撑 N|实际/参考路程 m|平均/P95/最大求解 s|",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in audits:
        lines.append(
            f"|{row['label']}|{row['status']}|{', '.join(key for key, value in row['checks'].items() if not value) or '-'}|"
            f"{row['maximum_point_force_n']:.6f}|{row['maximum_predicted_point_force_n']:.6f}|"
            f"{row['maximum_internal_force_norm_n']:.6f}|{row['payload_position_rmse_m']:.9f}|"
            f"{row['payload_heading_rmse_deg']:.9f}|{row['maximum_configuration_error_m']:.9f}|"
            f"{row['maximum_tire_utilization']:.6f}|{row['minimum_support_load_n']:.3f}|"
            f"{row['actual_payload_path_m']:.6f}/{row['reference_distance_m']:.6f}|"
            f"{row['solver_wall_mean_s']:.3f}/{row['solver_wall_p95_s']:.3f}/{row['solver_wall_max_s']:.3f}|"
        )
    lines += [
        "",
        "排序严格按任务书：先全程完成及全部硬门/工作预算；只有多个合格候选时，才继续比较内力峰值、货物跟踪和计算耗时。任一候选失败会被淘汰，只有两者都失败才停止后续。两个候选的全部原始指标与逐项检查均保留；没有把较小的开发差异表述为普适优势。",
        "",
        "图中的虚线是实际冻结参考，点线是理想瞬时11.5 m半圆，二者没有混称为同一路线。",
    ]
    (out / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["status"], "selected_for_r3": report["selected_for_r3"]}))
    if report["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()

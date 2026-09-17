"""C1 clean single-lane-change smoke/comparison on the coupled physical plant."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(__file__).resolve().parent
OUT = MODEL_DIR / "c1"
OUT.mkdir(parents=True, exist_ok=True)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from adapter import FrenetMap  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def lane_change_curvature(s_ref: np.ndarray, shift_m: float = 3.5) -> tuple[np.ndarray, dict]:
    """Parallel-lane transfer with zero initial/final heading and curvature."""
    s = np.asarray(s_ref, dtype=float)
    s0 = float(s[0] + 0.22 * (s[-1] - s[0]))
    length = float(min(40.0, 0.50 * (s[-1] - s[0])))
    length = max(length, 20.0)
    # Small-angle initial value; one Newton-like rescale below corrects geometry.
    theta_max = float(shift_m * np.pi / (2.0 * length))

    def profile(theta_peak: float) -> np.ndarray:
        xi = (s - s0) / length
        active = (xi >= 0.0) & (xi <= 1.0)
        out = np.zeros_like(s)
        out[active] = theta_peak * np.pi / length * np.cos(np.pi * xi[active])
        return out

    kappa = profile(theta_max)
    for _ in range(3):
        road = FrenetMap(s, kappa)
        actual_shift = float(road.y[-1] - road.y[0])
        if abs(actual_shift) < 1.0e-9:
            break
        theta_max *= float(shift_m / actual_shift)
        kappa = profile(theta_max)
    road = FrenetMap(s, kappa)
    return kappa, {
        "requested_shift_m": float(shift_m),
        "actual_shift_m": float(road.y[-1] - road.y[0]),
        "start_s_m": s0,
        "length_m": length,
        "curvature_peak_1pm": float(np.max(np.abs(kappa))),
        "final_heading_rad": float(road.heading[-1]),
    }


def set_reference_yaw_rate(ns: dict, curvature: np.ndarray) -> None:
    xref = np.asarray(ns["x_ref_raw"], dtype=float).copy()
    if xref.ndim != 2:
        raise ValueError(f"unexpected x_ref_raw shape {xref.shape}")
    if xref.shape[0] >= 6 and xref.shape[1] == curvature.size:
        xref[5, :] = xref[3, :] * curvature
    elif xref.shape[1] >= 6 and xref.shape[0] == curvature.size:
        xref[:, 5] = xref[:, 3] * curvature
    else:
        raise ValueError(f"cannot align x_ref_raw {xref.shape} with curvature {curvature.shape}")
    ns["x_ref_raw"] = xref


def metrics(result: dict) -> dict:
    steps = int(result["sim_steps"])
    states = np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1]
    rows = list(result.get("payload_force_hist", []))[:steps]
    connector = np.asarray([row["connector_force_n"] for row in rows], dtype=float)
    opening = np.asarray(
        [[row["q_front_rear_n"], row["q_left_right_n"]] for row in rows], dtype=float
    )
    residual = np.asarray([row["internal_force_residual_n"] for row in rows], dtype=float)
    icr = []
    for row in result.get("coupled_alloc_diag_hist", [])[:steps]:
        icr.extend(np.abs(np.asarray(row.get("normal_velocity_residual_mps", []), dtype=float)).tolist())
    team = np.asarray(result["team_state_hist"], dtype=float)[: steps + 1]
    ref = np.asarray(result["ref_team_hist"], dtype=float)
    n = min(team.shape[0], ref.shape[0])
    lat_err = team[:n, 1] - ref[:n, 1]
    heading_err = (team[:n, 2] - ref[:n, 2] + np.pi) % (2 * np.pi) - np.pi
    summary = dict(result.get("coupled_summary", {}))
    summary.update(
        {
            "sim_steps": steps,
            "full_path_reached": bool(result.get("full_path_reached", False)),
            "stop_reason": str(result.get("stop_reason", "")),
            "final_s_m": float(result.get("final_s", np.nan)),
            "target_s_m": float(result.get("target_s_team", np.nan)),
            "payload_lateral_rmse_m": float(np.sqrt(np.mean(lat_err**2))),
            "payload_lateral_peak_m": float(np.max(np.abs(lat_err))),
            "payload_heading_rmse_rad": float(np.sqrt(np.mean(heading_err**2))),
            "connector_force_rms_n": float(np.sqrt(np.mean(connector**2))),
            "opening_p99_n": float(np.percentile(np.abs(opening), 99.0)),
            "internal_force_residual_peak_n": float(np.max(np.linalg.norm(residual, axis=1))),
            "icr_normal_residual_peak_mps": float(max(icr) if icr else np.nan),
            "state_finite": bool(np.all(np.isfinite(states))),
            "mean_step_time_s": float(result.get("step_time_mean", np.nan)),
            "solve_success_count": int(result.get("mpc_solve_success_count", 0)),
            "solve_skip_count": int(result.get("mpc_solve_skip_count", 0)),
        }
    )
    return summary


def save_case(method_key: str, result: dict) -> None:
    steps = int(result["sim_steps"])
    np.savez_compressed(
        OUT / f"{method_key}.npz",
        coupled_state_hist=np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1],
        coupled_control_hist=np.asarray(result["coupled_control_hist"], dtype=float)[:steps],
        team_state_hist=np.asarray(result["team_state_hist"], dtype=float)[: steps + 1],
        ref_team_hist=np.asarray(result["ref_team_hist"], dtype=float),
        team_input_hist=np.asarray(result["team_input_hist"], dtype=float)[:steps],
        connector_force=np.asarray([r["connector_force_n"] for r in result["payload_force_hist"][:steps]]),
        connector_fx=np.asarray([r["connector_fx_body_n"] for r in result["payload_force_hist"][:steps]]),
        connector_fy=np.asarray([r["connector_fy_body_n"] for r in result["payload_force_hist"][:steps]]),
        opening=np.asarray(
            [[r["q_front_rear_n"], r["q_left_right_n"]] for r in result["payload_force_hist"][:steps]]
        ),
    )


def plot_results(results: dict[str, dict], road: FrenetMap) -> None:
    colors = {"baseline": "#4C78A8", "tf14_phase_role": "#D55E00"}
    labels = {"baseline": "AKE-M", "tf14_phase_role": "NR-KDCC"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes[0, 0].plot(road.x, road.y, "k--", lw=1.5, label="reference")
    for key, result in results.items():
        steps = int(result["sim_steps"])
        state = np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1]
        team = np.asarray(result["team_state_hist"], dtype=float)[: steps + 1]
        rows = result["payload_force_hist"][:steps]
        t = np.arange(steps) * float(result["dt"])
        connector = np.asarray([r["connector_force_n"] for r in rows], dtype=float)
        opening = np.asarray([[r["q_front_rear_n"], r["q_left_right_n"]] for r in rows], dtype=float)
        axes[0, 0].plot(state[:, 24], state[:, 25], color=colors[key], label=labels[key])
        axes[0, 1].plot(team[:, 0], team[:, 1], color=colors[key], label=labels[key])
        axes[1, 0].plot(t, np.max(connector, axis=1) / 1000.0, color=colors[key], label=labels[key])
        axes[1, 1].plot(t, np.max(np.abs(opening), axis=1) / 1000.0, color=colors[key], label=labels[key])
    axes[0, 0].set(xlabel="world X (m)", ylabel="world Y (m)", title="Payload path")
    axes[0, 0].axis("equal")
    axes[0, 1].set(xlabel="progress s (m)", ylabel="payload lateral error (m)", title="Tracking error")
    axes[1, 0].axhline(12.0, color="tab:orange", ls="--", lw=1, label="rated 12 kN")
    axes[1, 0].axhline(15.0, color="tab:red", ls=":", lw=1, label="ultimate 15 kN")
    axes[1, 0].set(xlabel="time (s)", ylabel="max point force (kN)", title="Four-point connector force")
    axes[1, 1].set(xlabel="time (s)", ylabel="max opening proxy (kN)", title="Payload opening load")
    for ax in axes.flat:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=220)
    plt.close(fig)


def write_stop(report: dict) -> None:
    failed = [key for key, item in report["methods"].items() if not item["accepted"]]
    lines = [
        "# C1停止与解决方案",
        "",
        "## 停止事实",
        "",
        f"同一新四车物理plant的clean单移线冒烟未通过：`{', '.join(failed)}`。按执行书停止C1多种子、C2回头弯和后续DoS比较。",
        "",
    ]
    for key in failed:
        lines.extend([f"- `{key}`：`{json.dumps(report['methods'][key], ensure_ascii=False, default=json_default)}`"])
    lines.extend(
        [
            "",
            "## 优先解决方案",
            "",
            "1. 若连接力超过15 kN：把四点位移/力直接加入MPC状态合同和约束；目前上层控制器只在旧等效plant上训练，ICR投影只能保证几何相容，不能替代受力约束。",
            "2. 若不能完成路径：在同一plant上重新生成Koopman数据并重训，而不是继续沿用旧等效自行车lift；先做AKE-M/NR-KDCC各自同预算调参。",
            "3. 若ICR残差失败：只修复等效转角到虚拟前/后轴角的投影接口，不改连接参数来掩盖几何问题。",
            "4. 若横向误差大但受力正常：扫描`virtual_front_scale/rear_ratio`并以曲率一致性选取，随后冻结映射供两种方法共用。",
            "5. 参数标定前，12/15 kN仍只作为参考阈值，不能据此形成实物安全结论。",
        ]
    )
    (OUT / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    runner = load_module(
        "tf14_remaining_for_c1",
        ROOT / "tf14_remaining_experiments_20260509" / "run_tf14_remaining_experiments.py",
    )
    runner._configure_output_root(OUT)
    stage5 = runner._load_stage5_module()
    stage6 = runner._load_stage6_module()
    stage1 = stage5._load_stage1_module()
    ns = stage5._bootstrap_env_for_path(stage1, "sine")
    curvature, lane_info = lane_change_curvature(ns["s_ref_path"])
    ns["curvature_ref_path"] = curvature
    set_reference_yaw_rate(ns, curvature)
    coordinator, ref_bundle = runner.tf14_runtime.build_a1_reference_bundle(
        payload_module=ns["payload_a1"],
        payload_cfg=ns["A1_PAYLOAD_CFG"],
        standardizer_x=ns["standardizer_x_kdnn"],
        x_ref_raw=ns["x_ref_raw"],
        leader_idx=ns["leader_idx"],
        horizon_pad=32,
    )
    ns["A1_COORDINATOR"] = coordinator
    ns["A1_REF_BUNDLE"] = ref_bundle
    road = FrenetMap(ns["s_ref_path"], curvature)

    all_methods = runner._final_method_plans(stage5, stage6, stage1, ns)
    scenario = runner.ScenarioPlan(
        "single_lane_clean",
        "clean single lane change",
        "sine",
        {
            "scenario_mode": "single_lane_clean",
            "enable_fault_tolerant_control": False,
            "comm_packet_loss_base": 0.0,
            "comm_packet_loss_gain": 0.0,
            "comm_delay_steps_max": 0,
            "comm_delay_bias": 0.0,
        },
    )
    seed = 3201
    results = {}
    report = {
        "stage": "C1_clean_single_lane_smoke",
        "seed": seed,
        "lane": lane_info,
        "plant": "four_vehicle_coupled",
        "common_icr": {"virtual_front_scale": 2.0 / 3.0, "virtual_rear_ratio": -0.5},
        "methods": {},
    }
    for key in ("baseline", "tf14_phase_role"):
        source = all_methods[key]
        cfg = dict(source.updates)
        cfg.update(
            {
                "plant_mode": "four_vehicle_coupled",
                "use_connection_compliance": False,
                "coupled_substep_s": 0.002,
                "coupled_virtual_front_scale": 2.0 / 3.0,
                "coupled_virtual_rear_ratio": -0.5,
                "save_history": False,
                "max_wall_time_sec": 0.0,
                "realtime_mode": False,
                "horizon": 12,
                "max_sqp_iters": 1,
                "mpc_decimation_steps": 1,
                "min_solve_vehicles_per_step": 4,
                "mpc_skip_on_budget": False,
                "time_limit": 0.03,
            }
        )
        method = runner.MethodPlan(key, source.display_name, cfg)
        log_path = OUT / f"{key}.log"
        result = runner._run_one(
            ns=ns,
            scenario=scenario,
            method=method,
            seed=seed,
            experiment="C1",
            log_path=log_path,
        )
        result_metrics = metrics(result)
        result_metrics["accepted"] = bool(
            result_metrics["full_path_reached"]
            and result_metrics["state_finite"]
            and result_metrics["connector_force_peak_n"] < 15000.0
            and result_metrics["internal_force_residual_peak_n"] <= 1.0e-9
            and result_metrics["icr_normal_residual_peak_mps"] <= 1.0e-8
        )
        results[key] = result
        report["methods"][key] = result_metrics
        save_case(key, result)
        print(key, json.dumps(result_metrics, ensure_ascii=False, default=json_default), flush=True)

    report["passed"] = bool(all(item["accepted"] for item in report["methods"].values()))
    plot_results(results, road)
    (OUT / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=json_default) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        write_stop(report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=json_default), flush=True)


if __name__ == "__main__":
    main()

"""C2 nominal clean hairpin comparison on the common coupled physical plant."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODEL_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
OUT = MODEL_DIR / "c2"
OUT.mkdir(parents=True, exist_ok=True)
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_c1 as c1  # noqa: E402


METHODS = ("baseline", "tf14_phase_role")
LABELS = {"baseline": "AKE-M", "tf14_phase_role": "NR-KDCC"}


def save_case(key: str, result: dict) -> None:
    steps = int(result["sim_steps"])
    np.savez_compressed(
        OUT / f"{key}.npz",
        coupled_state_hist=np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1],
        coupled_control_hist=np.asarray(result["coupled_control_hist"], dtype=float)[:steps],
        team_state_hist=np.asarray(result["team_state_hist"], dtype=float)[: steps + 1],
        ref_team_hist=np.asarray(result["ref_team_hist"], dtype=float),
        connector_force=np.asarray([r["connector_force_n"] for r in result["payload_force_hist"][:steps]]),
        connector_fx=np.asarray([r["connector_fx_body_n"] for r in result["payload_force_hist"][:steps]]),
        connector_fy=np.asarray([r["connector_fy_body_n"] for r in result["payload_force_hist"][:steps]]),
        opening=np.asarray(
            [[r["q_front_rear_n"], r["q_left_right_n"]] for r in result["payload_force_hist"][:steps]]
        ),
    )


def plot(results: dict, road: c1.FrenetMap) -> None:
    colors = {"baseline": "#4C78A8", "tf14_phase_role": "#D55E00"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes[0, 0].plot(road.x, road.y, "k--", lw=1.4, label="reference")
    for key, result in results.items():
        steps = int(result["sim_steps"])
        dt = float(result["dt"])
        state = np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1]
        team = np.asarray(result["team_state_hist"], dtype=float)[: steps + 1]
        rows = result["payload_force_hist"][:steps]
        t = np.arange(steps) * dt
        force = np.asarray([row["connector_force_n"] for row in rows], dtype=float)
        fy = np.asarray([row["connector_fy_body_n"] for row in rows], dtype=float)
        opening = np.asarray(
            [[row["q_front_rear_n"], row["q_left_right_n"]] for row in rows], dtype=float
        )
        sys_yaw = np.asarray([row["system_yaw_rate_radps"] for row in rows], dtype=float)
        axes[0, 0].plot(state[:, 24], state[:, 25], color=colors[key], label=LABELS[key])
        axes[0, 1].plot(team[:, 0], team[:, 1], color=colors[key], label=LABELS[key])
        axes[0, 2].plot(t, sys_yaw, color=colors[key], label=LABELS[key])
        axes[1, 0].plot(t, np.max(force, axis=1) / 1000.0, color=colors[key], label=LABELS[key])
        axes[1, 1].plot(t, np.max(np.abs(opening), axis=1) / 1000.0, color=colors[key], label=LABELS[key])
        # Positive/negative envelopes make inner/outer force direction visible.
        axes[1, 2].plot(t, np.max(fy, axis=1) / 1000.0, color=colors[key], label=f"{LABELS[key]} max")
        axes[1, 2].plot(t, np.min(fy, axis=1) / 1000.0, color=colors[key], ls="--", label=f"{LABELS[key]} min")
    axes[0, 0].set(xlabel="world X (m)", ylabel="world Y (m)", title="Payload hairpin path")
    axes[0, 0].axis("equal")
    axes[0, 1].set(xlabel="progress s (m)", ylabel="lateral error (m)", title="Payload tracking")
    axes[0, 2].set(xlabel="time (s)", ylabel="yaw rate (rad/s)", title="Array yaw")
    axes[1, 0].axhline(12.0, color="tab:orange", ls="--", lw=1)
    axes[1, 0].axhline(15.0, color="tab:red", ls=":", lw=1)
    axes[1, 0].set(xlabel="time (s)", ylabel="max point force (kN)", title="Connector force")
    axes[1, 1].set(xlabel="time (s)", ylabel="opening proxy (kN)", title="Opening load")
    axes[1, 2].set(xlabel="time (s)", ylabel="point Fy (kN)", title="Inner/outer force direction")
    for ax in axes.flat:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=220)
    plt.close(fig)


def write_stop(report: dict) -> None:
    lines = [
        "# C2停止与解决方案",
        "",
        "## 停止结论",
        "",
        "标称clean回头弯没有通过预先门，因此停止C3通讯扰动和DoS对比。不能在clean曲率问题未解决时把失败归因于网络。",
        "",
        "## 结果",
        "",
        f"```json\n{json.dumps(report, ensure_ascii=False, indent=2, default=c1.json_default)}\n```",
        "",
        "## 解决顺序",
        "",
        "1. 若任一方法不能完成或连接力越过15 kN：先在同一hairpin上降低速度/增大半径，定位物理可行边界；不得先加入网络保护。",
        "2. 若AKE-M能完成而NR-KDCC不能：审计phase-role/guard/PPC在入弯、弯中、出弯的切换，不用专门hairpin变体替换主方法；必要时同预算重调主方法。",
        "3. 若两方法都能完成但NR主指标劣化：把四点力、左右张开代理和力变化率加入NR预测目标，再重新跑C1/C2门。",
        "4. 若共同ICR残差正常而横向误差大：问题在上层曲率命令/模型失配，不应改连接刚度掩盖。",
        "5. 若轮胎利用率接近1：建立速度—曲率可行包络，并在上层参考生成器约束速度，而不是依赖状态裁剪。",
    ]
    (OUT / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    runner = c1.load_module(
        "tf14_remaining_for_c2",
        ROOT / "tf14_remaining_experiments_20260509" / "run_tf14_remaining_experiments.py",
    )
    runner._configure_output_root(OUT)
    stage5 = runner._load_stage5_module()
    stage6 = runner._load_stage6_module()
    stage1 = stage5._load_stage1_module()
    ns = stage5._bootstrap_env_for_path(stage1, "hairpin")
    road = c1.FrenetMap(ns["s_ref_path"], ns["curvature_ref_path"])
    methods = runner._final_method_plans(stage5, stage6, stage1, ns)
    scenario = runner.ScenarioPlan(
        "hairpin_nominal_clean",
        "nominal clean hairpin",
        "hairpin",
        {
            "scenario_mode": "hairpin_nominal_clean",
            "suite_path_mode": "hairpin",
            "enable_fault_tolerant_control": False,
            "comm_packet_loss_base": 0.0,
            "comm_packet_loss_gain": 0.0,
            "comm_delay_steps_max": 0,
            "comm_delay_bias": 0.0,
        },
    )
    seed = 3301
    results = {}
    report = {
        "stage": "C2_nominal_clean_hairpin",
        "seed": seed,
        "path": {
            "s_start_m": float(ns["s_ref_path"][0]),
            "s_end_m": float(ns["s_ref_path"][-1]),
            "curvature_peak_1pm": float(np.max(np.abs(ns["curvature_ref_path"]))),
            "reference_speed_peak_mps": float(np.max(np.asarray(ns["x_ref_raw"])[3, :])),
        },
        "methods": {},
    }
    for key in METHODS:
        source = methods[key]
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
        result = runner._run_one(
            ns=ns,
            scenario=scenario,
            method=method,
            seed=seed,
            experiment="C2",
            log_path=OUT / f"{key}.log",
        )
        row = c1.metrics(result)
        row["accepted_physics"] = bool(
            row["full_path_reached"]
            and row["state_finite"]
            and row["connector_force_peak_n"] < 15000.0
            and row["internal_force_residual_peak_n"] <= 1.0e-9
            and row["icr_normal_residual_peak_mps"] <= 1.0e-8
        )
        report["methods"][key] = row
        results[key] = result
        save_case(key, result)
        print(key, json.dumps(row, ensure_ascii=False, default=c1.json_default), flush=True)

    b = report["methods"]["baseline"]
    n = report["methods"]["tf14_phase_role"]
    report["comparison"] = {
        "lateral_rmse_change_fraction": float(
            (n["payload_lateral_rmse_m"] - b["payload_lateral_rmse_m"])
            / max(abs(b["payload_lateral_rmse_m"]), 1.0e-12)
        ),
        "connector_peak_change_fraction": float(
            (n["connector_force_peak_n"] - b["connector_force_peak_n"])
            / max(abs(b["connector_force_peak_n"]), 1.0e-12)
        ),
        "opening_p99_change_fraction": float(
            (n["opening_p99_n"] - b["opening_p99_n"])
            / max(abs(b["opening_p99_n"]), 1.0e-12)
        ),
    }
    report["predeclared_gate"] = {
        "both_physical_runs_accepted": bool(b["accepted_physics"] and n["accepted_physics"]),
        "nr_tracking_noninferior": bool(n["payload_lateral_rmse_m"] <= b["payload_lateral_rmse_m"]),
        "nr_improves_tracking_or_internal_force": bool(
            n["payload_lateral_rmse_m"] < b["payload_lateral_rmse_m"]
            or n["connector_force_peak_n"] < b["connector_force_peak_n"]
            or n["opening_p99_n"] < b["opening_p99_n"]
        ),
    }
    report["passed"] = bool(all(report["predeclared_gate"].values()))
    plot(results, road)
    (OUT / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default) + "\n",
        encoding="utf-8",
    )
    if not report["passed"]:
        write_stop(report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default), flush=True)


if __name__ == "__main__":
    main()

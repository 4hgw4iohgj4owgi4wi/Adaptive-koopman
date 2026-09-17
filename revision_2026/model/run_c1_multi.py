"""Five-seed paired C1 comparison; stop if the proposed-method claim is unsupported."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODEL_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
OUT = MODEL_DIR / "c1"
RUNS = OUT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_c1 as c1  # noqa: E402


SEEDS = [3201, 3202, 3203, 3204, 3205]
METHODS = ("baseline", "tf14_phase_role")
LABELS = {"baseline": "AKE-M", "tf14_phase_role": "NR-KDCC"}


def prepare_ns(runner, stage5, stage1):
    ns = stage5._bootstrap_env_for_path(stage1, "sine")
    curvature, lane_info = c1.lane_change_curvature(ns["s_ref_path"])
    ns["curvature_ref_path"] = curvature
    c1.set_reference_yaw_rate(ns, curvature)
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
    return ns, lane_info


def save_npz(path: Path, result: dict) -> None:
    steps = int(result["sim_steps"])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
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


def aggregate(rows: list[dict]) -> dict:
    numeric = [
        "payload_lateral_rmse_m",
        "payload_lateral_peak_m",
        "payload_heading_rmse_rad",
        "connector_force_peak_n",
        "connector_force_p99_n",
        "connector_force_rms_n",
        "opening_peak_n",
        "opening_p99_n",
        "tire_utilization_peak",
        "mean_step_time_s",
    ]
    out = {}
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        stats = {
            "n": len(selected),
            "accepted_count": int(sum(bool(row["accepted"]) for row in selected)),
            "completion_count": int(sum(bool(row["full_path_reached"]) for row in selected)),
        }
        for key in numeric:
            values = np.asarray([float(row[key]) for row in selected], dtype=float)
            stats[f"{key}_mean"] = float(np.mean(values))
            stats[f"{key}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        out[method] = stats

    paired = {}
    for key in numeric:
        b = np.asarray(
            [next(float(r[key]) for r in rows if r["seed"] == seed and r["method"] == "baseline") for seed in SEEDS]
        )
        n = np.asarray(
            [next(float(r[key]) for r in rows if r["seed"] == seed and r["method"] == "tf14_phase_role") for seed in SEEDS]
        )
        delta = n - b
        paired[key] = {
            "nr_minus_ake_mean": float(np.mean(delta)),
            "nr_minus_ake_std": float(np.std(delta, ddof=1)),
            "nr_relative_change_mean": float(np.mean(delta / np.maximum(np.abs(b), 1.0e-12))),
            "nr_better_seed_count": int(np.sum(n < b)),
        }
    return {"methods": out, "paired": paired}


def plot(rows: list[dict]) -> None:
    panels = [
        ("payload_lateral_rmse_m", 100.0, "Lateral RMSE (cm)"),
        ("connector_force_peak_n", 1.0 / 1000.0, "Peak point force (kN)"),
        ("opening_p99_n", 1.0 / 1000.0, "Opening P99 (kN)"),
        ("mean_step_time_s", 1000.0, "Mean step time (ms)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (key, scale, title) in zip(axes.flat, panels):
        for idx, seed in enumerate(SEEDS):
            y = [
                next(float(r[key]) for r in rows if r["seed"] == seed and r["method"] == method) * scale
                for method in METHODS
            ]
            ax.plot([0, 1], y, color="#999999", alpha=0.55, marker="o", ms=4)
        means = [
            np.mean([float(r[key]) for r in rows if r["method"] == method]) * scale
            for method in METHODS
        ]
        ax.scatter([0, 1], means, color=["#4C78A8", "#D55E00"], s=85, zorder=5, label="mean")
        ax.set_xticks([0, 1], [LABELS[m] for m in METHODS])
        ax.set_title(title)
        ax.grid(True, alpha=0.25)
    fig.suptitle("C1 clean single lane change: paired seeds 3201–3205")
    fig.tight_layout()
    fig.savefig(OUT / "multi.png", dpi=220)
    plt.close(fig)


def write_stop(report: dict) -> None:
    a = report["aggregate"]["methods"]["baseline"]
    n = report["aggregate"]["methods"]["tf14_phase_role"]
    p = report["aggregate"]["paired"]
    lines = [
        "# C1停止与解决方案",
        "",
        "## 停止结论",
        "",
        "五个配对seed的clean单移线均能在共同ICR四车物理plant上完成，数值和受力门也通过；但NR-KDCC没有形成相对AKE-M的支撑证据。按任务书停止C2回头弯以及后续DoS对比。",
        "",
        "## 事实证据",
        "",
        f"- AKE-M/NR-KDCC横向RMSE均值：`{a['payload_lateral_rmse_m_mean']:.6f}/{n['payload_lateral_rmse_m_mean']:.6f} m`；NR相对变化`{p['payload_lateral_rmse_m']['nr_relative_change_mean']:+.1%}`。",
        f"- 连接点峰值均值：`{a['connector_force_peak_n_mean']:.2f}/{n['connector_force_peak_n_mean']:.2f} N`；NR相对变化`{p['connector_force_peak_n']['nr_relative_change_mean']:+.1%}`。",
        f"- 开裂型内力P99均值：`{a['opening_p99_n_mean']:.2f}/{n['opening_p99_n_mean']:.2f} N`；NR相对变化`{p['opening_p99_n']['nr_relative_change_mean']:+.1%}`。",
        f"- 平均单步时间：`{a['mean_step_time_s_mean']*1000:.2f}/{n['mean_step_time_s_mean']*1000:.2f} ms`。",
        "- 上述是当前仿真事实，不等于AKE-M在一般场景必然更优，也不能通过只挑seed改写。",
        "",
        "## 原因判断",
        "",
        "1. 两个控制器的Koopman模型和权重来自旧等效自行车plant；新plant接口只是把上层等效转向公平投影到共同ICR，没有让lift学习四连接器快动态。",
        "2. NR-KDCC现有phase-role、PPC、guard和通信模块按旧plant调参；clean单移线中网络保护没有可利用的退化，而附加调度会增加控制/受力代价。",
        "3. 当前NR目标中没有四点Fx/Fy、张开代理或连接力变化率的直接预测项，因此不能期待名称中的network resilience自动转化为clean受力优势。",
        "",
        "## 解决顺序",
        "",
        "1. 用新30维联合plant重新生成训练/验证数据，建立控制器可用的降阶状态：四车Frenet误差、货物状态、四点相对位移/速度和AoI。",
        "2. 重新训练AKE-M与NR-KDCC，保持相同数据量、lift维数搜索预算、预测时域和调参次数；旧权重只作初始化，不作最终对比。",
        "3. 在NR-KDCC代价/约束中显式加入四点力、`Q_front_rear/Q_left_right`和力变化率，并保留作用反作用守恒检查。",
        "4. 先做clean单移线Pareto调参：跟踪不劣于AKE-M，同时连接力或张开载荷至少一项改善；不通过则不进入回头弯。",
        "5. 网络保护单独保留C0/N1已经成立的证据；不要把该保护层的成功外推成完整NR-KDCC在clean控制上的优越性。",
        "6. 参数/材料未标定前，12/15 kN仍是参考线，不形成实物安全或撕裂结论。",
        "",
        "## 恢复条件",
        "",
        "完成新plant重训和同预算调参后，重新运行本目录五seed门；只有主跟踪不劣且至少一个内部受力指标改善，才恢复C2。",
    ]
    (OUT / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    runner = c1.load_module(
        "tf14_remaining_for_c1_multi",
        ROOT / "tf14_remaining_experiments_20260509" / "run_tf14_remaining_experiments.py",
    )
    runner._configure_output_root(OUT)
    stage5 = runner._load_stage5_module()
    stage6 = runner._load_stage6_module()
    stage1 = stage5._load_stage1_module()
    rows = []
    lane_info = None
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
    for seed in SEEDS:
        ns, lane_info = prepare_ns(runner, stage5, stage1)
        methods = runner._final_method_plans(stage5, stage6, stage1, ns)
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
                experiment="C1M",
                log_path=RUNS / f"seed_{seed}_{key}.log",
            )
            row = c1.metrics(result)
            row.update({"seed": seed, "method": key, "label": LABELS[key]})
            row["accepted"] = bool(
                row["full_path_reached"]
                and row["state_finite"]
                and row["connector_force_peak_n"] < 15000.0
                and row["internal_force_residual_peak_n"] <= 1.0e-9
                and row["icr_normal_residual_peak_mps"] <= 1.0e-8
            )
            rows.append(row)
            save_npz(RUNS / f"seed_{seed}_{key}.npz", result)
            print(json.dumps(row, ensure_ascii=False, default=c1.json_default), flush=True)

    aggregate_result = aggregate(rows)
    physical_gate = all(bool(row["accepted"]) for row in rows)
    base = aggregate_result["methods"]["baseline"]
    nr = aggregate_result["methods"]["tf14_phase_role"]
    tracking_noninferior = nr["payload_lateral_rmse_m_mean"] <= base["payload_lateral_rmse_m_mean"]
    any_core_improvement = (
        nr["payload_lateral_rmse_m_mean"] < base["payload_lateral_rmse_m_mean"]
        or nr["connector_force_peak_n_mean"] < base["connector_force_peak_n_mean"]
        or nr["opening_p99_n_mean"] < base["opening_p99_n_mean"]
    )
    claim_supported = bool(physical_gate and tracking_noninferior and any_core_improvement)
    report = {
        "stage": "C1_clean_single_lane_five_seed",
        "seeds": SEEDS,
        "lane": lane_info,
        "predeclared_gate": {
            "all_physical_runs_accepted": physical_gate,
            "nr_tracking_noninferior_to_ake": tracking_noninferior,
            "nr_improves_at_least_one_core_metric": any_core_improvement,
        },
        "aggregate": aggregate_result,
        "claim_supported": claim_supported,
        "passed": claim_supported,
    }
    with (OUT / "runs.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "multi.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default) + "\n",
        encoding="utf-8",
    )
    plot(rows)
    if not claim_supported:
        write_stop(report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default), flush=True)


if __name__ == "__main__":
    main()

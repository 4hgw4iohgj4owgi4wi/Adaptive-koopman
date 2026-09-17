"""C3 paired communication and DoS comparison on the coupled single-lane plant."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODEL_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
OUT = MODEL_DIR / "c3"
RUNS = OUT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_c1 as c1  # noqa: E402
import run_c1_multi as c1m  # noqa: E402


SEEDS = [3401, 3402, 3403]
METHODS = ("baseline", "tf14_phase_role")
LABELS = {"baseline": "AKE-M", "tf14_phase_role": "NR-KDCC"}


SCENARIOS = {
    "delay_loss": {
        "scenario_mode": "single_lane_delay_loss",
        "comm_fault_trigger_mode": "step",
        "comm_fault_start_step": 0,
        "comm_fault_end_step": None,
        "comm_relative_state_delay_steps": 1,
        "comm_relative_state_variable_delay_min_steps": 0,
        "comm_relative_state_variable_delay_max_steps": 2,
        "comm_relative_state_dropout_prob": 0.10,
        "comm_team_ey_delay_steps": 1,
        "comm_team_ey_variable_delay_min_steps": 0,
        "comm_team_ey_variable_delay_max_steps": 2,
        "comm_team_ey_dropout_prob": 0.10,
        "upper_lower_comm_delay_steps": 1,
        "upper_lower_comm_variable_delay_min_steps": 0,
        "upper_lower_comm_variable_delay_max_steps": 2,
        "upper_lower_comm_dropout_prob": 0.10,
        "upper_lower_comm_ref_delay_steps": 1,
        "upper_lower_comm_ref_variable_delay_min_steps": 0,
        "upper_lower_comm_ref_variable_delay_max_steps": 2,
        "upper_lower_comm_ref_dropout_prob": 0.10,
    },
    "dos_2s": {
        "scenario_mode": "single_lane_dos_2s",
        "comm_fault_trigger_mode": "step",
        "comm_fault_start_step": 350,
        "comm_fault_end_step": 449,
        "comm_relative_state_dropout_prob": 1.0,
        "comm_team_ey_dropout_prob": 1.0,
        "upper_lower_comm_dropout_prob": 1.0,
        "upper_lower_comm_ref_dropout_prob": 1.0,
    },
    "dos_5s": {
        "scenario_mode": "single_lane_dos_5s",
        "comm_fault_trigger_mode": "step",
        "comm_fault_start_step": 350,
        "comm_fault_end_step": 599,
        "comm_relative_state_dropout_prob": 1.0,
        "comm_team_ey_dropout_prob": 1.0,
        "upper_lower_comm_dropout_prob": 1.0,
        "upper_lower_comm_ref_dropout_prob": 1.0,
    },
}


def trace_tokens(result: dict) -> list[str]:
    perception = result.get("comm_perception_diag_hist", [])
    upper = result.get("upper_lower_comm_diag_hist", [])
    count = min(len(perception), len(upper))
    tokens = []
    for idx in range(count):
        p = perception[idx]
        u = upper[idx]
        pairs = [
            [
                int(row.get("receiver", -1)),
                int(row.get("sender", -1)),
                int(row.get("delay_steps", 0)),
                bool(row.get("dropped", False)),
            ]
            for row in p.get("relative_pair_diag", [])
        ]
        payload = {
            "k": int(p.get("step", idx)),
            "active": bool(p.get("active", False)),
            "pairs": pairs,
            "team_delay": float(p.get("team_ey_delay_mean", 0.0)),
            "team_drop": float(p.get("team_ey_dropout_ratio", 0.0)),
            "upper_delay": list(u.get("delay_steps_per_vehicle", [])),
            "upper_drop": list(u.get("dropped_per_vehicle", [])),
        }
        tokens.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return tokens


def trace_compare(a: list[str], b: list[str]) -> dict:
    n = min(len(a), len(b))
    a_prefix = "\n".join(a[:n]).encode("utf-8")
    b_prefix = "\n".join(b[:n]).encode("utf-8")
    return {
        "common_steps": n,
        "length_a": len(a),
        "length_b": len(b),
        "prefix_equal": bool(a[:n] == b[:n]),
        "hash_a": hashlib.sha256(a_prefix).hexdigest(),
        "hash_b": hashlib.sha256(b_prefix).hexdigest(),
    }


def add_network_metrics(row: dict, result: dict) -> dict:
    out = dict(row)
    perception = result.get("comm_perception_diag_hist", [])
    comm = result.get("comm_summary", {}) or {}
    out.update(
        {
            "relative_delay_mean_steps": float(
                np.mean([d.get("relative_state_delay_mean", 0.0) for d in perception])
            ),
            "relative_dropout_mean": float(
                np.mean([d.get("relative_state_dropout_ratio", 0.0) for d in perception])
            ),
            "relative_state_error_mean": float(
                np.mean([d.get("relative_state_error_mean", 0.0) for d in perception])
            ),
            "comm_quality_min": float(comm.get("quality_min", 1.0)),
            "comm_degrade_mix_peak": float(comm.get("degrade_mix_peak", 0.0)),
            "fail_total": int(sum(result.get("fail_counts", []))),
        }
    )
    return out


def save_case(path: Path, result: dict) -> None:
    steps = int(result["sim_steps"])
    np.savez_compressed(
        path,
        coupled_state_hist=np.asarray(result["coupled_state_hist"], dtype=float)[: steps + 1],
        team_state_hist=np.asarray(result["team_state_hist"], dtype=float)[: steps + 1],
        ref_team_hist=np.asarray(result["ref_team_hist"], dtype=float),
        connector_force=np.asarray([r["connector_force_n"] for r in result["payload_force_hist"][:steps]]),
        opening=np.asarray(
            [[r["q_front_rear_n"], r["q_left_right_n"]] for r in result["payload_force_hist"][:steps]]
        ),
    )


def aggregate(rows: list[dict]) -> dict:
    metrics = [
        "payload_lateral_rmse_m",
        "payload_lateral_peak_m",
        "connector_force_peak_n",
        "connector_force_p99_n",
        "opening_p99_n",
        "mean_step_time_s",
        "relative_state_error_mean",
    ]
    out = {}
    for scenario in SCENARIOS:
        out[scenario] = {"methods": {}, "paired": {}}
        for method in METHODS:
            selected = [r for r in rows if r["scenario"] == scenario and r["method"] == method]
            stats = {
                "n": len(selected),
                "completion_count": int(sum(bool(r["full_path_reached"]) for r in selected)),
                "accepted_count": int(sum(bool(r["accepted_physics"]) for r in selected)),
            }
            for metric in metrics:
                values = np.asarray([float(r[metric]) for r in selected], dtype=float)
                stats[f"{metric}_mean"] = float(np.mean(values))
                stats[f"{metric}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            out[scenario]["methods"][method] = stats
        for metric in metrics:
            base = np.asarray(
                [next(float(r[metric]) for r in rows if r["scenario"] == scenario and r["seed"] == seed and r["method"] == "baseline") for seed in SEEDS]
            )
            nr = np.asarray(
                [next(float(r[metric]) for r in rows if r["scenario"] == scenario and r["seed"] == seed and r["method"] == "tf14_phase_role") for seed in SEEDS]
            )
            delta = nr - base
            out[scenario]["paired"][metric] = {
                "nr_minus_ake_mean": float(np.mean(delta)),
                "nr_relative_change_mean": float(np.mean(delta / np.maximum(np.abs(base), 1.0e-12))),
                "nr_better_seed_count": int(np.sum(nr < base)),
            }
    return out


def plot(aggregate_result: dict) -> None:
    scenario_names = list(SCENARIOS)
    metrics = [
        ("payload_lateral_rmse_m", "Lateral RMSE change"),
        ("connector_force_peak_n", "Connector peak change"),
        ("opening_p99_n", "Opening P99 change"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    for ax, (metric, title) in zip(axes, metrics):
        values = [aggregate_result[s]["paired"][metric]["nr_relative_change_mean"] * 100.0 for s in scenario_names]
        colors = ["#009E73" if value <= 0 else "#D55E00" for value in values]
        ax.bar(scenario_names, values, color=colors)
        ax.axhline(0.0, color="black", lw=0.8)
        ax.set_ylabel("NR-KDCC vs AKE-M (%)")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("C3 coupled plant: identical delivered communication trace")
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=220)
    plt.close(fig)


def write_stop(report: dict) -> None:
    lines = [
        "# C3停止与解决方案",
        "",
        "## 停止结论",
        "",
        "通讯/DoS配对门未通过，停止扩大攻击矩阵和论文鲁棒性主张。",
        "",
        f"```json\n{json.dumps(report['gate'], ensure_ascii=False, indent=2)}\n```",
        "",
        "## 解决顺序",
        "",
        "1. trace不一致：把网络trace预生成到文件并由两方法只读重放，不允许运行器内部继续采样。",
        "2. 物理门失败：先收紧降级控制的转角/加速度变化率和连接力约束，不能只调通信质量阈值。",
        "3. 跟踪改善但张开内力恶化：优化目标加入`Q_front_rear/Q_left_right`与恢复冲击，做Pareto调参。",
        "4. 长DoS不能完成：设计只依赖本车状态的本地安全路径/速度参考，并明确可维持时间边界。",
        "5. 在三seed门恢复前，不进入更多攻击时刻、拓扑或hairpin+DoS组合。",
    ]
    (OUT / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    runner = c1.load_module(
        "tf14_remaining_for_c3",
        ROOT / "tf14_remaining_experiments_20260509" / "run_tf14_remaining_experiments.py",
    )
    runner._configure_output_root(OUT)
    stage5 = runner._load_stage5_module()
    stage6 = runner._load_stage6_module()
    stage1 = stage5._load_stage1_module()
    rows = []
    trace_checks = []
    for seed in SEEDS:
        ns, _ = c1m.prepare_ns(runner, stage5, stage1)
        methods = runner._final_method_plans(stage5, stage6, stage1, ns)
        for scenario_key, scenario_updates in SCENARIOS.items():
            scenario = runner.ScenarioPlan(
                scenario_key,
                scenario_key,
                "sine",
                dict(scenario_updates),
            )
            scenario_results = {}
            scenario_tokens = {}
            for method_key in METHODS:
                source = methods[method_key]
                cfg = dict(source.updates)
                cfg.update(
                    {
                        "plant_mode": "four_vehicle_coupled",
                        "use_connection_compliance": False,
                        "coupled_substep_s": 0.002,
                        "coupled_virtual_front_scale": 2.0 / 3.0,
                        "coupled_virtual_rear_ratio": -0.5,
                        "comm_restructure_enabled": True,
                        "comm_restructure_seed_offset": 2400,
                        "upper_lower_comm_enabled": True,
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
                method = runner.MethodPlan(method_key, source.display_name, cfg)
                result = runner._run_one(
                    ns=ns,
                    scenario=scenario,
                    method=method,
                    seed=seed,
                    experiment="C3",
                    log_path=RUNS / f"{scenario_key}_seed_{seed}_{method_key}.log",
                )
                row = add_network_metrics(c1.metrics(result), result)
                row.update({"scenario": scenario_key, "seed": seed, "method": method_key})
                row["accepted_physics"] = bool(
                    row["full_path_reached"]
                    and row["state_finite"]
                    and row["connector_force_peak_n"] < 15000.0
                    and row["internal_force_residual_peak_n"] <= 1.0e-9
                    and row["icr_normal_residual_peak_mps"] <= 1.0e-8
                )
                rows.append(row)
                scenario_results[method_key] = result
                scenario_tokens[method_key] = trace_tokens(result)
                save_case(RUNS / f"{scenario_key}_seed_{seed}_{method_key}.npz", result)
                print(json.dumps(row, ensure_ascii=False, default=c1.json_default), flush=True)
            check = trace_compare(scenario_tokens["baseline"], scenario_tokens["tf14_phase_role"])
            check.update({"scenario": scenario_key, "seed": seed})
            trace_checks.append(check)
            print("trace", json.dumps(check, ensure_ascii=False), flush=True)

    aggregate_result = aggregate(rows)
    all_trace_equal = all(check["prefix_equal"] for check in trace_checks)
    all_physical = all(bool(row["accepted_physics"]) for row in rows)
    scenario_gate = {}
    for scenario in SCENARIOS:
        base = aggregate_result[scenario]["methods"]["baseline"]
        nr = aggregate_result[scenario]["methods"]["tf14_phase_role"]
        scenario_gate[scenario] = {
            "nr_tracking_noninferior": bool(
                nr["payload_lateral_rmse_m_mean"] <= base["payload_lateral_rmse_m_mean"]
            ),
            "nr_opening_not_worse_5pct": bool(
                nr["opening_p99_n_mean"] <= 1.05 * base["opening_p99_n_mean"]
            ),
        }
    support = bool(
        all_trace_equal
        and all_physical
        and all(all(item.values()) for item in scenario_gate.values())
    )
    report = {
        "stage": "C3_delay_loss_and_dos",
        "seeds": SEEDS,
        "scenarios": SCENARIOS,
        "trace_checks": trace_checks,
        "aggregate": aggregate_result,
        "gate": {
            "all_trace_prefixes_equal": all_trace_equal,
            "all_physical_runs_accepted": all_physical,
            "scenario_gate": scenario_gate,
            "supporting_evidence_available": support,
        },
        "passed": support,
    }
    with (OUT / "runs.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default) + "\n",
        encoding="utf-8",
    )
    plot(aggregate_result)
    if not support:
        write_stop(report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=c1.json_default), flush=True)


if __name__ == "__main__":
    main()

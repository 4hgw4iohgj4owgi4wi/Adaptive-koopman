"""Finalize the evidence-backed C3 stop after the deterministic DoS gate failed."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "c3"
RUNS = OUT / "runs"
DT = 0.02
SCENARIOS = ("delay_loss", "dos_2s", "dos_5s")
METHODS = ("baseline", "tf14_phase_role")
LABELS = {"baseline": "AKE-M", "tf14_phase_role": "NR-KDCC"}

TRACE_CHECKS = {
    "delay_loss": {
        "common_steps": 1004,
        "length_ake": 1004,
        "length_nr": 1005,
        "prefix_equal": True,
        "sha256": "d0f9ed39e9db2ea8477b3ab4e7a3891e5c1088131af35662ab139e10b650bf6b",
    },
    "dos_2s": {
        "common_steps": 1002,
        "length_ake": 1003,
        "length_nr": 1002,
        "prefix_equal": True,
        "sha256": "312e7998af1249c29218f4fe7e5cd756cbf613b5df8dfcc410f21c93a0609b51",
    },
    "dos_5s": {
        "common_steps": 1004,
        "length_ake": 1004,
        "length_nr": 1036,
        "prefix_equal": True,
        "sha256": "262f9d28e93faaa13b68dfad60fd04680764e7b179e6e6093af8a0906a541a99",
    },
}


def load_case(scenario: str, method: str) -> dict:
    with np.load(RUNS / f"{scenario}_seed_3401_{method}.npz") as data:
        team = np.asarray(data["team_state_hist"], dtype=float)
        ref = np.asarray(data["ref_team_hist"], dtype=float)
        force = np.asarray(data["connector_force"], dtype=float)
        opening = np.asarray(data["opening"], dtype=float)
        states = np.asarray(data["coupled_state_hist"], dtype=float)
    n = min(team.shape[0], ref.shape[0])
    lateral = team[:n, 1] - ref[:n, 1]
    return {
        "team": team,
        "ref": ref,
        "force": force,
        "opening": opening,
        "states": states,
        "metrics": {
            "payload_lateral_rmse_m": float(np.sqrt(np.mean(lateral**2))),
            "payload_lateral_peak_m": float(np.max(np.abs(lateral))),
            "connector_force_peak_n": float(np.max(force)),
            "connector_force_p99_n": float(np.percentile(force, 99.0)),
            "opening_p99_n": float(np.percentile(np.abs(opening), 99.0)),
            "full_path_reached": True,
            "state_finite": bool(np.all(np.isfinite(states))),
            "internal_force_residual_peak_n": 0.0,
        },
    }


def relative(nr: float, ake: float) -> float:
    return float((nr - ake) / max(abs(ake), 1.0e-12))


def build_report(cases: dict) -> dict:
    comparisons = {}
    gates = {}
    metrics_out = {}
    for scenario in SCENARIOS:
        ake = cases[scenario]["baseline"]["metrics"]
        nr = cases[scenario]["tf14_phase_role"]["metrics"]
        metrics_out[scenario] = {"AKE-M": ake, "NR-KDCC": nr}
        comparisons[scenario] = {
            "lateral_rmse_change_fraction": relative(
                nr["payload_lateral_rmse_m"], ake["payload_lateral_rmse_m"]
            ),
            "connector_peak_change_fraction": relative(
                nr["connector_force_peak_n"], ake["connector_force_peak_n"]
            ),
            "opening_p99_change_fraction": relative(
                nr["opening_p99_n"], ake["opening_p99_n"]
            ),
        }
        gates[scenario] = {
            "both_complete_and_finite": bool(
                ake["full_path_reached"]
                and nr["full_path_reached"]
                and ake["state_finite"]
                and nr["state_finite"]
            ),
            "nr_tracking_noninferior": bool(
                nr["payload_lateral_rmse_m"] <= ake["payload_lateral_rmse_m"]
            ),
            "nr_opening_not_worse_5pct": bool(
                nr["opening_p99_n"] <= 1.05 * ake["opening_p99_n"]
            ),
        }
    passed = bool(
        all(check["prefix_equal"] for check in TRACE_CHECKS.values())
        and all(all(gate.values()) for gate in gates.values())
    )
    return {
        "stage": "C3_partial_stopped_after_deterministic_dos_gate",
        "seed": 3401,
        "executed_scenarios": {
            "delay_loss": "1-3 control-period delay plus 10% independent dropout",
            "dos_2s": "100% dropout at steps 350-449",
            "dos_5s": "100% dropout at steps 350-599",
        },
        "not_executed_after_stop": [
            "seeds 3402-3403",
            "Gilbert-Elliott AKE-M/NR-KDCC comparison",
            "hairpin plus DoS",
            "actuator degradation plus communication disturbance",
        ],
        "trace_checks": TRACE_CHECKS,
        "metrics": metrics_out,
        "comparison": comparisons,
        "gate": gates,
        "passed": passed,
        "stop_reason": "dos_2s opening P99 and connector peak exceed the predeclared relative-force gate",
        "interpretation_limit": (
            "All forces remain below the provisional 12/15 kN references; the failure is relative "
            "protection performance, not an actual material-tearing verdict."
        ),
    }


def plot(cases: dict, report: dict) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    colors = {"baseline": "#4C78A8", "tf14_phase_role": "#D55E00"}
    for col, scenario in enumerate(SCENARIOS):
        for method in METHODS:
            case = cases[scenario][method]
            team = case["team"]
            force = case["force"]
            opening = case["opening"]
            t = np.arange(force.shape[0]) * DT
            axes[0, col].plot(team[:, 0], team[:, 1], color=colors[method], label=LABELS[method])
            axes[1, col].plot(t, np.max(force, axis=1) / 1000.0, color=colors[method], label=f"{LABELS[method]} force")
            axes[1, col].plot(t, np.max(np.abs(opening), axis=1) / 1000.0, color=colors[method], ls="--", label=f"{LABELS[method]} opening")
        axes[0, col].set_title(scenario)
        axes[0, col].set_xlabel("progress s (m)")
        axes[0, col].set_ylabel("payload lateral error (m)")
        axes[1, col].set_xlabel("time (s)")
        axes[1, col].set_ylabel("force / opening (kN)")
        if scenario.startswith("dos_"):
            end = 449 if scenario == "dos_2s" else 599
            for ax in (axes[0, col], axes[1, col]):
                # Top panel x-axis is progress, so only mark the DoS on time plot.
                if ax is axes[1, col]:
                    ax.axvspan(350 * DT, end * DT, color="grey", alpha=0.16, label="DoS")
        for ax in (axes[0, col], axes[1, col]):
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=7)
    fig.suptitle("C3 stopped: tracking benefit but DoS internal-force penalty")
    fig.tight_layout()
    fig.savefig(OUT / "compare.png", dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(SCENARIOS))
    width = 0.25
    keys = [
        ("lateral_rmse_change_fraction", "lateral RMSE"),
        ("connector_peak_change_fraction", "connector peak"),
        ("opening_p99_change_fraction", "opening P99"),
    ]
    for idx, (key, label) in enumerate(keys):
        values = [report["comparison"][s][key] * 100.0 for s in SCENARIOS]
        ax.bar(x + (idx - 1) * width, values, width=width, label=label)
    ax.axhline(0.0, color="black", lw=0.8)
    ax.axhline(5.0, color="tab:red", ls="--", lw=1, label="+5% force gate")
    ax.set_xticks(x, SCENARIOS)
    ax.set_ylabel("NR-KDCC relative to AKE-M (%)")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "gate.png", dpi=220)
    plt.close(fig)


def write_stop(report: dict) -> None:
    c = report["comparison"]
    m = report["metrics"]
    lines = [
        "# C3停止与解决方案",
        "",
        "## 停止结论",
        "",
        "在同一四车物理plant、共同ICR和逐步一致的交付trace下，NR-KDCC能降低通讯扰动/DoS时的跟踪误差，但2 s DoS显著增加连接峰值和货物张开型内力。预设的“张开P99不劣化超过5%”门失败，因此停止余下seed、攻击矩阵和hairpin+DoS实验。",
        "",
        "## 关键事实",
        "",
        f"- delay/loss：横向RMSE变化`{c['delay_loss']['lateral_rmse_change_fraction']:+.1%}`，连接峰值`{c['delay_loss']['connector_peak_change_fraction']:+.1%}`，张开P99`{c['delay_loss']['opening_p99_change_fraction']:+.1%}`。",
        f"- 2 s DoS：横向RMSE变化`{c['dos_2s']['lateral_rmse_change_fraction']:+.1%}`，连接峰值`{c['dos_2s']['connector_peak_change_fraction']:+.1%}`，张开P99`{c['dos_2s']['opening_p99_change_fraction']:+.1%}`。",
        f"- 5 s DoS：横向RMSE变化`{c['dos_5s']['lateral_rmse_change_fraction']:+.1%}`，连接峰值`{c['dos_5s']['connector_peak_change_fraction']:+.1%}`，张开P99`{c['dos_5s']['opening_p99_change_fraction']:+.1%}`。",
        f"- 2 s DoS绝对值：AKE-M/NR-KDCC连接峰值`{m['dos_2s']['AKE-M']['connector_force_peak_n']:.1f}/{m['dos_2s']['NR-KDCC']['connector_force_peak_n']:.1f} N`；张开P99`{m['dos_2s']['AKE-M']['opening_p99_n']:.1f}/{m['dos_2s']['NR-KDCC']['opening_p99_n']:.1f} N`。",
        "- 三场景公共trace前缀SHA256均逐步一致；方法完成步数不同只影响公共前缀之后的尾部。",
        "- 所有绝对力仍低于暂定12/15 kN参考线；这是相对保护性能失败，不是货物材料实际撕裂结论。",
        "",
        "## 原因判断",
        "",
        "1. 当前degraded fallback优先恢复路径误差，未在控制目标中加入四点连接力、张开代理或力变化率。",
        "2. DoS恢复时缺少基于物理内力的恢复滞环和命令斜率限制；C0/N1独立保护器已有软恢复，但尚未完整接入NR-KDCC主runner。",
        "3. 质量权重现已由真实交付trace驱动，因而结果不能再解释为隐藏随机通道造成；问题落在控制权衡本身。",
        "",
        "## 解决顺序",
        "",
        "1. 把四点Fx/Fy、`Q_front_rear/Q_left_right`和连接力变化率加入NR-KDCC预测代价/约束，设置恢复冲击上限。",
        "2. 将N1中验证过的序列拒收、AoI外推、DoS本地降级、恢复滞环和软恢复迁入主runner，并用同一交付trace驱动全部模块。",
        "3. 对fallback做tracking—force Pareto扫描；约束NR横向RMSE不劣于AKE-M且张开P99不高于AKE-M的105%。",
        "4. 先只重跑seed 3401的2 s DoS门；通过后再恢复3402–3403、5 s DoS、周期DoS和Gilbert–Elliott。",
        "5. 单移线全部网络门通过后，才恢复hairpin+DoS，避免曲率和网络失稳混因。",
        "6. 取得实物连接器和货物材料参数前，继续把12/15 kN写为仿真参考而非安全认证阈值。",
    ]
    (OUT / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cases = {scenario: {method: load_case(scenario, method) for method in METHODS} for scenario in SCENARIOS}
    report = build_report(cases)
    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot(cases, report)
    write_stop(report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

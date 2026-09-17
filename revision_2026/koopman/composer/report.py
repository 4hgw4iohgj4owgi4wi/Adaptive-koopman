from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import pickle
import shutil
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import offline


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def _status_plot(path: Path, title: str, reason: str) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8)); ax.axis("off")
    ax.text(.5, .65, "NOT EXECUTED", ha="center", va="center", fontsize=28, weight="bold", color="#a61b1b")
    ax.text(.5, .46, title, ha="center", va="center", fontsize=17)
    ax.text(.5, .28, reason, ha="center", va="center", fontsize=11, wrap=True)
    fig.tight_layout(); fig.savefig(path, dpi=180); plt.close(fig)


def run(rs: Any) -> bool:
    stage = rs.OUT / "t9"; stage.mkdir(parents=True, exist_ok=True)
    dev_path = rs.OUT / "t4" / "development_results.json"
    if not dev_path.exists():
        rs.append_solution("T9缺少T4结果", [str(dev_path)], ["T4尚未完成"], ["完成T4后只读生成报告"], "不能生成结果报告。")
        return False
    dev = json.loads(dev_path.read_text(encoding="utf-8")); selection = json.loads((rs.OUT / "t3" / "selection.json").read_text(encoding="utf-8"))
    seed = int(selection["representative_seed"])
    with (rs.OUT / "t3" / f"selector_seed_{seed}.pkl").open("rb") as handle: selector = pickle.load(handle)
    records = offline._records(rs, "development-test")

    # Causality and cache-contract audit.
    sample = records[0][1]; feature0 = offline._features(sample)
    altered = dict(sample); altered["truth_x"] = np.random.default_rng(7).normal(size=sample["truth_x"].shape); altered["truth_f"] = np.zeros_like(sample["truth_f"])
    tests = {
        "causal_features_invariant_to_truth": bool(np.array_equal(feature0, offline._features(altered))),
        "cache_contract_shapes": bool(sample["pred_x"].shape[1:] == (4, 20, 46) and sample["pred_f"].shape[1:] == (4, 20, 18)),
        "d5_not_created_or_read": not rs.D5.exists(),
        "initial_metric_bug_archived": (rs.OUT / "t4" / "development_results_initial_metric_bug.json").exists(),
        "g3_stop_respected": not bool(dev["passed"]),
    }
    rs.write_json(stage / "tests.json", {"passed": all(tests.values()), "tests": tests})

    history = rs.OUT / "solutions_history.md"
    if (rs.OUT / "solutions.md").exists() and not history.exists():
        shutil.copy2(rs.OUT / "solutions.md", history)
    current_solutions = f"""# SHKC实验问题与当前处置

## G3组合预测门失败

- 已确认事实：C9相对逐轨迹`min(K0,K1)`改善为`{100*dev['C9_improvement']:.3f}%`，95% CI=`[{dev['paired_bootstrap']['ci_low']:.6g}, {dev['paired_bootstrap']['ci_high']:.6g}]`；8%改善、正向CI、正向Holm、force/load、方向门均失败。
- 最可能原因：D3 oracle互补依赖未来误差标签，当前低容量因果特征无法稳定实现；C9又有约92%拒绝回退。
- 替代解释：物理合同/分歧门可能过保守，但阈值已在validation冻结，不能看过development后放宽并继续称独立验证。
- 已采取方案：C0–C10完整消融、micro与逐轨迹口径统一报告、统计实现错误初版已归档。
- 结论边界：停止D5、网络监督器和正式闭环；K1保留主预测器，K4/K5F2只可作风险监视。

## D4高载荷证据缺失

- 已确认事实：train/validation/development中峰值连接力≥0.8 rated的不重叠20步窗均为0。
- 允许方案：未来另立协议，在不越过plant安全合同的合法工况增加持续加载覆盖。
- 禁止方案：本轮事后增大转角/加速度、降低0.8 rated定义或虚构FM3结果。
- 结论边界：不能声明高载荷选择器、UCB校准或高载荷安全泛化有效。

## T7冻结闭环源hash缺失

- 预注册hash：`{rs.EXPECTED_CLOSED_LOOP_SHA256}`；当前同名脚本hash：`{rs.sha256(rs.KOOPMAN/'universal_v2_closedloop.py')}`。
- `revision_2026`递归检索未找到预注册版本；同名文件不能视为同一冻结源。
- 允许方案：恢复精确hash，或基于冻结plant接口建立新适配器并做逐元素D3回归。
- 结论边界：该问题不影响已完成的离线T1–T4，但独立阻断T7。

## 未生成的D4外部/网络数据

- 本轮只生成了进入G3所需的D4 internal 288条；参数/网络D4未生成。
- 原因：internal development的G3已失败，按任务树其后的网络监督、D5和正式闭环均停止；继续生成不会修复核心预测门。
- 结论边界：不得据本轮对参数外推或通信保护下结论。
"""
    (rs.OUT / "solutions.md").write_text(current_solutions, encoding="utf-8")

    methods = []
    for name, metric in dev["methods"].items():
        methods.append({"method": name, "J_pred": metric["J_pred"], "mean_per_trajectory_J": metric["mean_per_trajectory_J"],
                        "state": metric["state"], "force": metric["force"], "load": metric["load"],
                        "direction_accuracy": metric["direction_accuracy"], "divergence_rate": metric["divergence_rate"],
                        "rejection_rate": metric["rejection_rate"], "p99_ms": metric["inference_p99_ms_per_window"]})
    _csv(rs.OUT / "prediction_results.csv", methods)
    _csv(rs.OUT / "horizon_expert_map.csv", [{"horizon": i + 1, "expert": name} for i, name in enumerate(selection["fixed_map"])])
    _csv(rs.OUT / "task_specific_weights.csv", [{"expert": k, "global_weight": v} for k, v in selection["global_weights"].items()])
    feature_names = ([f"payload_state_{i}" for i in range(6)] + [f"vehicle_yaw_{i}" for i in range(4)] +
                     ["mean_accel", "mean_steer", "steer_delta"] + [f"connector_disp_norm_{i}" for i in range(4)] +
                     [f"connector_vel_norm_{i}" for i in range(4)] + ["network_drop", "network_delay", "network_aoi", "network_quality"] +
                     ["horizon", "state_disagreement", "force_disagreement"] + [f"contract_{x}" for x in offline.EXPERTS] + ["lift_drift_K1", "lift_drift_K4"])
    _csv(rs.OUT / "selector_features.csv", [{"index": i, "feature": name, "latest_time": "prediction_origin", "causal": True} for i, name in enumerate(feature_names)])
    cache_manifest = json.loads((rs.OUT / "t2" / "cache_manifest.json").read_text(encoding="utf-8"))
    contact_rows = [{"split": split, "windows": cache_manifest["windows"][split],
                     "high_load_windows": cache_manifest["high_load_windows"][split], "high_load_trainable": False}
                    for split in ("train", "validation", "development-test")]
    _csv(rs.OUT / "contact_highload_results.csv", contact_rows)

    # Recompute horizon curves and diagnostic arrays from frozen caches only.
    curves = {method: {"state": np.zeros(20), "force": np.zeros(20), "n": np.zeros(20)} for method in ("C1", "C5", "C9", "C10")}
    occupancy = Counter(); disagreement, error, ratios, rejects = [], [], [], []
    with np.load(rs.CFG.universal_root / "normalizers.npz", allow_pickle=False) as src:
        fmean, fstd = np.asarray(src["force_mean"]), np.asarray(src["force_std"])
    rated = rs.gen.base.ConnectorParams().rated_force_n
    for _, data in records:
        for method in curves:
            x, f, aux = offline._compose(method, data, selector, selection["thresholds"])
            curves[method]["state"] += np.sum(np.mean((x - data["truth_x"])**2, axis=-1), axis=0)
            curves[method]["force"] += np.sum(np.mean((f[..., :10] - data["truth_f"][..., :10])**2, axis=-1), axis=0)
            curves[method]["n"] += len(x)
            if method == "C9":
                occupancy.update(aux["selected"].reshape(-1).tolist())
                d = np.mean(np.std(data["pred_x"], axis=1), axis=-1)
                disagreement.extend(d.reshape(-1)); error.extend(np.mean((x-data["truth_x"])**2, axis=-1).reshape(-1))
                truth = data["truth_f"] * fstd + fmean
                ratios.extend((np.max(np.linalg.norm(truth[..., :8].reshape(len(truth), 20, 4, 2), axis=-1), axis=(1,2))/rated).tolist())
                rejects.extend(np.any(aux["rejected"], axis=1).astype(float).tolist())
    occupancy_rows = [{"expert": offline.EXPERTS[i], "count": occupancy[i], "fraction": occupancy[i]/max(sum(occupancy.values()),1)} for i in range(4)]
    _csv(rs.OUT / "selector_occupancy.csv", occupancy_rows)
    for method in curves:
        for key in ("state", "force"): curves[method][key] = np.sqrt(curves[method][key] / np.maximum(curves[method]["n"], 1))

    fig, ax = plt.subplots(figsize=(8.5, 5)); labels = ["K0", "K1", "K0/K1 envelope", "C5 global", "C9 causal", "C10 oracle"]
    values = [dev["methods"]["C0"]["mean_per_trajectory_J"], dev["methods"]["C1"]["mean_per_trajectory_J"],
              dev["simple_envelope_mean_J"], dev["methods"]["C5"]["mean_per_trajectory_J"],
              dev["methods"]["C9"]["mean_per_trajectory_J"], dev["methods"]["C10"]["mean_per_trajectory_J"]]
    colors = ["#788", "#376a9f", "#222", "#7a62a3", "#c4573f", "#4f8b58"]
    ax.bar(labels, values, color=colors); ax.set_ylabel("Mean per-trajectory J"); ax.set_title("Oracle ceiling vs causal SHKC (D4 development)"); ax.tick_params(axis="x", rotation=22)
    fig.tight_layout(); fig.savefig(rs.OUT / "oracle_vs_causal.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.8)); ax.bar([r["expert"] for r in occupancy_rows], [r["fraction"] for r in occupancy_rows], color="#587a9c")
    ax.set_ylim(0,1); ax.set_ylabel("Selected fraction"); ax.set_title("C9 expert occupancy after rejection/fallback")
    fig.tight_layout(); fig.savefig(rs.OUT / "expert_occupancy.png", dpi=180); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharex=True)
    for method, color in zip(curves, ("#376a9f", "#7a62a3", "#c4573f", "#4f8b58")):
        axes[0].plot(range(1,21), curves[method]["state"], label=method, color=color)
        axes[1].plot(range(1,21), curves[method]["force"], label=method, color=color)
    axes[0].set_title("State NRMSE by horizon"); axes[1].set_title("Force/load NRMSE by horizon")
    for ax in axes: ax.set_xlabel("Horizon"); ax.grid(alpha=.25); ax.legend()
    fig.tight_layout(); fig.savefig(rs.OUT / "horizon_state_force.png", dpi=180); plt.close(fig)

    d, e = np.asarray(disagreement), np.sqrt(np.asarray(error)); edges = np.quantile(d, np.linspace(0,1,11)); centers=[]; means=[]; counts=[]
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (d >= lo) & (d <= hi); centers.append(float(np.mean(d[mask]))); means.append(float(np.mean(e[mask]))); counts.append(int(mask.sum()))
    _csv(rs.OUT / "uncertainty_error_calibration.csv", [{"bin":i,"disagreement":centers[i],"rmse":means[i],"n":counts[i]} for i in range(10)])
    fig, ax = plt.subplots(figsize=(7.5,4.8)); ax.plot(centers, means, marker="o"); ax.set_xlabel("Expert state disagreement"); ax.set_ylabel("C9 state RMSE"); ax.set_title("Uncertainty-error calibration"); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(rs.OUT / "uncertainty_error_calibration.png", dpi=180); plt.close(fig)

    ratio, reject = np.asarray(ratios), np.asarray(rejects); edges=np.linspace(0,max(.05,float(ratio.max())*1.01),9); centers=[]; rates=[]; ns=[]
    for lo,hi in zip(edges[:-1],edges[1:]):
        mask=(ratio>=lo)&(ratio<hi); centers.append((lo+hi)/2); rates.append(float(np.mean(reject[mask])) if mask.any() else np.nan); ns.append(int(mask.sum()))
    _csv(rs.OUT / "contact_force_gate.csv", [{"load_ratio_center":centers[i],"rejection_rate":rates[i],"n":ns[i]} for i in range(len(centers))])
    fig, ax=plt.subplots(figsize=(7.5,4.8)); ax.plot(centers,rates,marker="o"); ax.axvline(.8,color="r",ls="--",label="high-load threshold"); ax.set_xlabel("True peak connector force / rated"); ax.set_ylabel("Window rejection rate"); ax.set_ylim(0,1.05); ax.set_title("Force-risk guard coverage (no high-load windows)"); ax.legend(); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(rs.OUT / "contact_force_gate.png", dpi=180); plt.close(fig)

    fig, ax=plt.subplots(figsize=(8,5));
    for row in methods:
        ax.scatter(row["mean_per_trajectory_J"], row["rejection_rate"], s=55); ax.annotate(row["method"], (row["mean_per_trajectory_J"],row["rejection_rate"]), xytext=(4,3), textcoords="offset points")
    ax.set_xlabel("Mean per-trajectory J (lower better)"); ax.set_ylabel("Rejection rate"); ax.set_title("Offline accuracy-safety fallback tradeoff"); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig(rs.OUT / "accuracy_safety_cost_pareto.png", dpi=180); plt.close(fig)

    stop_reason = "Blocked by preregistered G3: C9 did not improve the K0/K1 envelope by 8%."
    _status_plot(rs.OUT / "network_modes.png", "Network supervisor experiment", stop_reason)
    _status_plot(rs.OUT / "closed_loop_100m.png", "100 m FCS-MPC experiment", stop_reason)
    _status_plot(rs.OUT / "lane_change_hairpin.png", "Lane-change and hairpin closed loop", stop_reason)
    shutil.copy2(rs.OUT / "t4" / "g3.json", rs.OUT / "gates.json")

    c9 = dev["methods"]["C9"]; c10 = dev["methods"]["C10"]; c5 = dev["methods"]["C5"]
    report = f"""# SHKC组合实验最终报告（D4 development停止）

## 结论

本轮按`koopman_combo.md`完成进入G3所需的T0–T4 internal主线，并在预注册G3停止。C9相对逐轨迹`min(K0,K1)`包络的改善为`{100*dev['C9_improvement']:.3f}%`（实际为恶化），配对95% CI为`[{dev['paired_bootstrap']['ci_low']:.6g}, {dev['paired_bootstrap']['ci_high']:.6g}]`。因此没有生成D5，也没有启动正式闭环；这不是程序跑不通，而是方法在新development数据上未达到进入下一阶段的证据门。参数/网络D4也因该停止门未继续生成，不能据本轮对外推或通信保护作结论。

## 已确认事实

- D4 internal：288/288条，失败0；train/validation/development不重叠20步窗为9440/3776/3776。
- 高载荷（峰值连接力≥0.8 rated）窗为0，FM3高载荷选择器不可训练，不能作高载荷泛化主张。
- C9逐轨迹J=`{c9['mean_per_trajectory_J']:.8f}`，简单包络=`{dev['simple_envelope_mean_J']:.8f}`，拒绝/回退率=`{100*c9['rejection_rate']:.2f}%`。
- C5全局凸权重J=`{c5['mean_per_trajectory_J']:.8f}`，仍未超过8%门；C10 oracle J=`{c10['mean_per_trajectory_J']:.8f}`，说明互补上限存在但当前因果选择器没有实现。
- C9方向准确率micro=`{c9['direction_accuracy']:.6f}`，逐轨迹均值=`{dev['C9_mean_per_trajectory_components']['direction_accuracy']:.6f}`，后者低于包络`{dev['simple_envelope_components']['direction_accuracy']:.6f}`，所以方向门失败。
- T7所需历史闭环脚本预注册hash未找到；该问题按协议不阻断T1–T6，但即使G3通过也需先恢复精确源或完成等价回归。

## 推断与边界

最合理解释是D3 oracle优势主要依赖未来误差标签，当前低容量因果特征无法可靠判别专家；91%以上的安全拒绝又使C9接近K1。替代解释包括当前物理合同残差门过于保守，但阈值已按validation冻结，不能在看过development后放宽再声称独立验证。

可保留的论文结论是“异构专家存在后验互补性，但本轮因果SHKC未超过简单K0/K1包络”。必须删除或暂缓“组合预测最优”“网络保护有效”“闭环控制最优”和“高载荷安全有效”的主张。

## 停止后的允许工作

可以只读分析C5/C6/C7/C8差异，或在未来另立全新协议与新D4/D5研究更好的因果特征；不能用当前development/D3反复调门后继续把结果称为盲验证。本轮不颠覆方法、不降低8%门、不伪造D5或闭环图片。
"""
    (rs.OUT / "final_report.md").write_text(report, encoding="utf-8")
    rs.write_json(stage / "complete.json", {"stage":"T9-negative-report", "accepted": True, "g3_passed": False,
                  "tests_passed": all(tests.values()), "final_report_sha256": rs.sha256(rs.OUT/"final_report.md")})
    rs.append_log("C006", "T9 G3负结果收口与图片", [f"tests={tests}。", "生成离线5张证据图、1张Pareto图和3张明确标注NOT EXECUTED的停止状态图。",
                  f"final_report={rs.sha256(rs.OUT/'final_report.md')}；gates={rs.sha256(rs.OUT/'gates.json')}；未创建/读取D5。"])
    return True

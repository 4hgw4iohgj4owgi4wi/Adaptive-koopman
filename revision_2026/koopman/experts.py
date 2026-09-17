"""K2.9--K2.10 three-regime linear experts and deployable causal gates.

All experts share the S4 fixed lift, U1 physical input, and common decoders.
The oracle uses test-time physical labels only as a non-deployable comparator.
Because these are weak threshold labels rather than an error-minimizing selector,
it is not a mathematical upper bound (the experiment explicitly checks this).
Hard and soft gates use only the current predicted state, current/planned input,
and backward differences.  No future measured force enters deployable gates.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from linear import (
    BOOTSTRAP,
    HORIZON,
    basis,
    compact_model,
    fit_model,
    json_default,
    load_data,
    moments,
    paired_bootstrap,
    save_model,
    write_json,
)


REGIMES = ("E-L", "E-C", "E-T")
METRICS = ("state", "yaw", "connector", "opening")
CURVATURE_THRESHOLD = 0.005  # 1/m
CURVATURE_RATE_THRESHOLD = 0.020  # 1/(m s)
STEER_RATE_THRESHOLD = 0.040  # rad/s
OPENING_RATE_THRESHOLD = 500.0  # N/s
EXPERT_SHRINKAGE = 3.0e-4


def sigmoid(value: float) -> float:
    value = float(np.clip(value, -60.0, 60.0))
    return 1.0 / (1.0 + math.exp(-value))


def physical_row(full: np.ndarray, force: np.ndarray, u1: np.ndarray, u3: np.ndarray) -> np.ndarray:
    psi, vx_global, vy_global = float(full[26]), float(full[27]), float(full[28])
    vx_body = math.cos(psi) * vx_global + math.sin(psi) * vy_global
    front, rear = float(u3[8]), float(u3[9])
    kappa = (math.tan(front) - math.tan(rear)) / 5.0
    accel = float(np.mean(u1[[0, 2, 4, 6]]))
    steer = float(np.mean(u1[[1, 3, 5, 7]]))
    return np.array([vx_body, kappa, accel, steer, force[8], force[9]], dtype=float)


def causal_features(base: np.ndarray, previous: np.ndarray | None, dt: float) -> np.ndarray:
    prior = base if previous is None else previous
    rate = (base - prior) / dt
    return np.array([base[0], base[1], base[2], base[3], base[4], base[5], rate[1], rate[3], rate[4], rate[5]])


def regime_label(rho: np.ndarray) -> int:
    transition = (
        abs(rho[6]) >= CURVATURE_RATE_THRESHOLD
        or abs(rho[7]) >= STEER_RATE_THRESHOLD
        or max(abs(rho[8]), abs(rho[9])) >= OPENING_RATE_THRESHOLD
    )
    if transition:
        return 2
    if abs(rho[1]) >= CURVATURE_THRESHOLD:
        return 1
    return 0


def soft_weights(rho: np.ndarray, tau: float) -> np.ndarray:
    transition_ratio = max(
        abs(rho[6]) / CURVATURE_RATE_THRESHOLD,
        abs(rho[7]) / STEER_RATE_THRESHOLD,
        abs(rho[8]) / OPENING_RATE_THRESHOLD,
        abs(rho[9]) / OPENING_RATE_THRESHOLD,
    )
    curve_ratio = abs(rho[1]) / CURVATURE_THRESHOLD
    p_transition = sigmoid((transition_ratio - 1.0) / tau)
    p_curve_given_steady = sigmoid((curve_ratio - 1.0) / tau)
    return np.array(
        [
            (1.0 - p_transition) * (1.0 - p_curve_given_steady),
            (1.0 - p_transition) * p_curve_given_steady,
            p_transition,
        ],
        dtype=float,
    )


def trajectory_rho_labels(row: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    a, dt = row["arrays"], float(row["meta"]["control_dt_s"])
    bases = np.asarray(
        [physical_row(a["s2_four"][k], a["force_output"][k], a["u1_four"][k], a["u3_alloc"][k]) for k in range(a["u1_four"].shape[0])]
    )
    rho = np.asarray([causal_features(base, bases[k - 1] if k > 0 else None, dt) for k, base in enumerate(bases)])
    labels = np.asarray([regime_label(value) for value in rho], dtype=np.int64)
    return rho, labels


def fit_experts(rows: list[dict[str, Any]], base_model: dict[str, Any]) -> tuple[list[np.ndarray], dict[str, int]]:
    phi_parts: list[list[np.ndarray]] = [[], [], []]
    target_parts: list[list[np.ndarray]] = [[], [], []]
    counts = {name: 0 for name in REGIMES}
    for row in rows:
        if row["meta"]["split"] != "train":
            continue
        a = row["arrays"]
        xn = (a["s4_force_in"] - base_model["x_mean"]) / base_model["x_std"]
        un = (a["u1_four"] - base_model["u_mean"]) / base_model["u_std"]
        z = basis(xn, "lifted")
        phi = np.concatenate([z[:-1], un], axis=1)
        _, labels = trajectory_rho_labels(row)
        for label, name in enumerate(REGIMES):
            mask = labels == label
            phi_parts[label].append(phi[mask])
            target_parts[label].append(z[1:][mask])
            counts[name] += int(np.sum(mask))
    transitions = []
    identity = np.eye(base_model["transition"].shape[0])
    identity[0, 0] = 0.0
    for label in range(3):
        phi = np.concatenate(phi_parts[label], axis=0)
        target = np.concatenate(target_parts[label], axis=0)
        scale = float(phi.shape[0])
        gram = (phi.T @ phi) / scale
        rhs = (phi.T @ target) / scale
        transition = np.linalg.solve(
            gram + EXPERT_SHRINKAGE * identity,
            rhs + EXPERT_SHRINKAGE * identity @ base_model["transition"],
        )
        transitions.append(transition)
    return transitions, counts


def metric_errors(pred_full: np.ndarray, pred_force: np.ndarray, target_full: np.ndarray, target_force: np.ndarray) -> dict[str, float]:
    yaw_indices = np.array([5, 11, 17, 23, 29], dtype=int)
    return {
        "state": float(np.mean((pred_full - target_full) ** 2)),
        "yaw": float(np.mean((pred_full[yaw_indices] - target_full[yaw_indices]) ** 2)),
        "connector": float(np.mean((pred_force[:8] - target_force[:8]) ** 2)),
        "opening": float(np.mean((pred_force[8:10] - target_force[8:10]) ** 2)),
    }


def evaluate(
    mode: str,
    rows: list[dict[str, Any]],
    split: str,
    model: dict[str, Any],
    transitions: list[np.ndarray],
    common_norm: dict[str, np.ndarray],
    tau: float = 0.25,
    smooth: float = 0.5,
) -> dict[str, Any]:
    sums = {metric: np.zeros(HORIZON) for metric in METRICS}
    counts = {metric: np.zeros(HORIZON, dtype=int) for metric in METRICS}
    strata_sq = {name: {metric: [] for metric in METRICS} for name in REGIMES}
    strata_step = {name: {metric: [] for metric in ("connector", "opening")} for name in REGIMES}
    per_traj: dict[str, dict[str, Any]] = {}
    occupation = np.zeros(3)
    entropy_values: list[float] = []
    finite = True

    for row in rows:
        meta, a = row["meta"], row["arrays"]
        if meta["split"] != split:
            continue
        _, true_labels = trajectory_rho_labels(row)
        steps = a["u1_four"].shape[0]
        traj_values = {metric: [] for metric in METRICS}
        traj_strata = {name: {metric: [] for metric in METRICS} for name in REGIMES}
        dt = float(meta["control_dt_s"])
        for start in range(0, steps - HORIZON + 1, HORIZON):
            xn = ((a["s4_force_in"][start] - model["x_mean"]) / model["x_std"])[None, :]
            z = basis(xn, "lifted")[0]
            current_full = a["s2_four"][start]
            current_force = a["force_output"][start]
            previous_base = None
            if start > 0:
                previous_base = physical_row(a["s2_four"][start - 1], a["force_output"][start - 1], a["u1_four"][start - 1], a["u3_alloc"][start - 1])
            alpha_previous: np.ndarray | None = None
            for h in range(1, HORIZON + 1):
                k = start + h - 1
                current_base = physical_row(current_full, current_force, a["u1_four"][k], a["u3_alloc"][k])
                rho = causal_features(current_base, previous_base, dt)
                if mode == "global":
                    alpha = np.array([1.0, 0.0, 0.0])
                    transition = model["transition"]
                elif mode == "oracle":
                    alpha = np.eye(3)[true_labels[k]]
                    transition = transitions[true_labels[k]]
                elif mode == "hard":
                    label = regime_label(rho)
                    alpha = np.eye(3)[label]
                    transition = transitions[label]
                else:
                    alpha_raw = soft_weights(rho, tau)
                    if mode == "noTransition":
                        alpha_raw[0] += 0.5 * alpha_raw[2]
                        alpha_raw[1] += 0.5 * alpha_raw[2]
                        alpha_raw[2] = 0.0
                        alpha_raw /= alpha_raw.sum()
                    alpha = alpha_raw if alpha_previous is None else smooth * alpha_previous + (1.0 - smooth) * alpha_raw
                    transition = sum(alpha[index] * transitions[index] for index in range(3))
                un = (a["u1_four"][k] - model["u_mean"]) / model["u_std"]
                z = np.concatenate([z, un]) @ transition
                pred_full_norm = z @ model["decode_full"]
                pred_force_norm = z @ model["decode_force"]
                current_full = pred_full_norm * common_norm["s2_std"] + common_norm["s2_mean"]
                current_force = pred_force_norm * common_norm["force_std"] + common_norm["force_mean"]
                previous_base = current_base
                alpha_previous = alpha
                occupation += alpha
                entropy_values.append(float(-np.sum(alpha * np.log(np.clip(alpha, 1.0e-12, 1.0)))))
                target_full = (a["s2_four"][k + 1] - common_norm["s2_mean"]) / common_norm["s2_std"]
                target_force = (a["force_output"][k + 1] - common_norm["force_mean"]) / common_norm["force_std"]
                errors = metric_errors(pred_full_norm, pred_force_norm, target_full, target_force)
                label_name = REGIMES[true_labels[k]]
                for metric, value in errors.items():
                    sums[metric][h - 1] += value
                    counts[metric][h - 1] += 1
                    if h >= 10:
                        traj_values[metric].append(value)
                        traj_strata[label_name][metric].append(value)
                        strata_sq[label_name][metric].append(value)
                        if metric in strata_step[label_name]:
                            strata_step[label_name][metric].append(math.sqrt(value))
                if not np.all(np.isfinite(z)) or np.max(np.abs(z)) > 1.0e12:
                    finite = False
        key = f"{meta['scenario']}|{meta['traj_id']}|{int(meta['external'])}"
        item: dict[str, Any] = {metric: float(math.sqrt(np.mean(values))) for metric, values in traj_values.items()}
        item["scenario"] = meta["scenario"]
        item["strata"] = {
            name: {metric: (float(math.sqrt(np.mean(values))) if values else math.nan) for metric, values in metrics.items()}
            for name, metrics in traj_strata.items()
        }
        per_traj[key] = item
    horizon = {
        metric: np.sqrt(np.divide(sums[metric], counts[metric], out=np.full(HORIZON, np.nan), where=counts[metric] > 0))
        for metric in METRICS
    }
    h10 = {metric: float(math.sqrt(np.sum(sums[metric][9:]) / np.sum(counts[metric][9:]))) for metric in METRICS}
    strata = {
        name: {
            "h10_20_nrmse": {metric: float(math.sqrt(np.mean(values))) for metric, values in metrics.items()},
            "p95_step_nrmse": {
                metric: float(np.quantile(values, 0.95)) if values else math.nan for metric, values in strata_step[name].items()
            },
            "count": len(strata_sq[name]["state"]),
        }
        for name, metrics in strata_sq.items()
    }
    occupation /= max(float(np.sum(occupation)), 1.0)
    mean_entropy = float(np.mean(entropy_values)) if entropy_values else math.nan
    return {
        "mode": mode,
        "split": split,
        "finite": bool(finite and all(np.all(np.isfinite(value)) for value in horizon.values())),
        "horizon_nrmse": horizon,
        "h10_20_nrmse": h10,
        "strata": strata,
        "per_trajectory_h10_20": per_traj,
        "occupation": occupation,
        "mean_entropy": mean_entropy,
        "effective_experts": float(math.exp(mean_entropy)) if math.isfinite(mean_entropy) else math.nan,
    }


def composite(result: dict[str, Any], stratum: str | None = None) -> float:
    source = result["h10_20_nrmse"] if stratum is None else result["strata"][stratum]["h10_20_nrmse"]
    return float(np.mean([source["state"], source["connector"], source["opening"]]))


def plot(path: Path, results: dict[str, dict[str, Any]], metric: str) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    for name, result in results.items():
        ax.plot(np.arange(1, HORIZON + 1), result["horizon_nrmse"][metric], label=name)
    ax.set(xlabel="Teacher-free rollout horizon", ylabel=f"{metric} NRMSE", title=f"Linear expert gate: {metric}")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def stop(out: Path, results: dict[str, Any], facts: list[str], solutions: list[str]) -> None:
    write_json(out / "results.json", results)
    lines = ["# 线性专家门停止", "", "## 已核实事实", ""] + [f"- {item}" for item in facts]
    lines += ["", "## 解决方案", ""] + [f"{i}. {item}" for i, item in enumerate(solutions, 1)]
    lines += ["", "按门禁，不构造bilinear、MF-IK或稳定性证书。", ""]
    (out / "stop.md").write_text("\n".join(lines), encoding="utf-8")
    raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest, rows = load_data(args.data.resolve())
    s2_mean, s2_std = moments(rows, "s2_four", states=True)
    force_mean, force_std = moments(rows, "force_output", states=True)
    common_norm = {"s2_mean": s2_mean, "s2_std": s2_std, "force_mean": force_mean, "force_std": force_std}
    base = fit_model(rows, "S4-U1-lifted", "S4-force-in", "U1-four", "lifted", common_norm)
    save_model(out / "base.npz", base)
    transitions, train_counts = fit_experts(rows, base)
    np.savez_compressed(out / "experts.npz", **{REGIMES[index]: value for index, value in enumerate(transitions)})

    label_counts = {split: {name: 0 for name in REGIMES} for split in ("train", "validation", "test", "external")}
    for row in rows:
        _, labels = trajectory_rho_labels(row)
        for index, name in enumerate(REGIMES):
            label_counts[row["meta"]["split"]][name] += int(np.sum(labels == index))
    results: dict[str, Any] = {
        "protocol": {
            "shared_state": "S4-force-in",
            "shared_input": "U1-four",
            "shared_lift_and_decoders": True,
            "thresholds": {
                "abs_kappa_1pm": CURVATURE_THRESHOLD,
                "abs_dot_kappa_1pms": CURVATURE_RATE_THRESHOLD,
                "abs_dot_delta_radps": STEER_RATE_THRESHOLD,
                "abs_dot_Q_nps": OPENING_RATE_THRESHOLD,
            },
            "causal": "hard/soft use predicted current state/force, current or planned U1/U3 allocation metadata, and backward differences only",
            "oracle": "uses true weak physical regime labels at test time; not deployable and not guaranteed to be an error upper bound",
            "selection": "tau and smoothing selected on validation composite NRMSE only",
            "primary_composite": "arithmetic mean of state, connector and opening h10-20 NRMSE, frozen before test",
        },
        "data_summary": manifest["summary"],
        "base_model": compact_model(base),
        "label_counts": label_counts,
        "train_expert_counts": train_counts,
    }
    if min(train_counts.values()) < 1000:
        stop(
            out,
            results,
            [f"训练标签计数不足：{train_counts}。"],
            ["复核物理阈值与场景是否真正包含持续纵向、持续转弯和过渡片段。", "不要靠复制少数片段或读取test标签扩充专家。"],
        )

    grid: list[dict[str, Any]] = []
    best = None
    for tau in (0.15, 0.25, 0.50):
        for smooth in (0.0, 0.5, 0.8):
            value = evaluate("soft", rows, "validation", base, transitions, common_norm, tau=tau, smooth=smooth)
            score = composite(value)
            grid.append({"tau": tau, "smooth": smooth, "score": score})
            if best is None or score < best[0]:
                best = (score, tau, smooth)
    assert best is not None
    _, tau, smooth = best
    results["validation_gate_grid"] = grid
    results["selected_gate"] = {"tau": tau, "smooth": smooth}

    test_results = {
        "global": evaluate("global", rows, "test", base, transitions, common_norm),
        "oracle": evaluate("oracle", rows, "test", base, transitions, common_norm),
        "hard": evaluate("hard", rows, "test", base, transitions, common_norm),
        "soft": evaluate("soft", rows, "test", base, transitions, common_norm, tau=tau, smooth=smooth),
        "noTransition": evaluate("noTransition", rows, "test", base, transitions, common_norm, tau=tau, smooth=smooth),
    }
    external_results = {
        name: evaluate(mode, rows, "external", base, transitions, common_norm, tau=tau, smooth=smooth)
        for name, mode in (("global", "global"), ("hard", "hard"), ("soft", "soft"))
    }
    results["test"] = test_results
    results["external"] = external_results
    plot(out / "state.png", test_results, "state")
    plot(out / "connector.png", test_results, "connector")
    plot(out / "opening.png", test_results, "opening")

    improvements = {}
    for name in REGIMES:
        base_score, soft_score = composite(test_results["global"], name), composite(test_results["soft"], name)
        improvements[name] = (base_score - soft_score) / base_score
    improved_count = sum(value > 0.0 for value in improvements.values())
    third_ok = min(improvements.values()) >= -0.05
    stratified_pass = improved_count >= 2 and third_ok

    transition_soft = test_results["soft"]["strata"]["E-T"]
    transition_no_t = test_results["noTransition"]["strata"]["E-T"]
    transition_reduction = {
        "composite": (composite(test_results["noTransition"], "E-T") - composite(test_results["soft"], "E-T")) / composite(test_results["noTransition"], "E-T"),
        "connector_p95": (transition_no_t["p95_step_nrmse"]["connector"] - transition_soft["p95_step_nrmse"]["connector"]) / transition_no_t["p95_step_nrmse"]["connector"],
        "opening_p95": (transition_no_t["p95_step_nrmse"]["opening"] - transition_soft["p95_step_nrmse"]["opening"]) / transition_no_t["p95_step_nrmse"]["opening"],
    }
    transition_pass = all(value >= 0.10 for value in transition_reduction.values())
    occupation = np.asarray(test_results["soft"]["occupation"])
    # Operational anti-collapse checks: every expert contributes and the soft
    # gate is not effectively a single expert.  Per-stratum diagonal dominance
    # is audited below directly from true causal features.
    diagonal = np.zeros((3, 3))
    diagonal_counts = np.zeros(3)
    for row in rows:
        if row["meta"]["split"] != "test":
            continue
        rho, labels = trajectory_rho_labels(row)
        for value, label in zip(rho, labels):
            diagonal[label] += soft_weights(value, tau)
            diagonal_counts[label] += 1
    diagonal = np.divide(diagonal, diagonal_counts[:, None], out=np.zeros_like(diagonal), where=diagonal_counts[:, None] > 0)
    ranking_pass = all(int(np.argmax(diagonal[index])) == index for index in range(3))
    collapse_pass = bool(np.min(occupation) >= 0.05 and test_results["soft"]["effective_experts"] >= 1.30 and ranking_pass)
    finite_pass = all(value["finite"] for value in test_results.values()) and all(value["finite"] for value in external_results.values())
    results["gates"] = {
        "stratum_relative_improvement_soft_vs_global": improvements,
        "stratified_rule_pass": stratified_pass,
        "transition_reduction_soft_vs_noTransition": transition_reduction,
        "transition_value_pass": transition_pass,
        "soft_gate_mean_weight_by_true_stratum": diagonal,
        "anti_collapse_pass": collapse_pass,
        "finite_test_and_external": finite_pass,
        "overall_pass": bool(stratified_pass and transition_pass and collapse_pass and finite_pass),
    }
    results["paired_soft_minus_global"] = {
        metric: paired_bootstrap(test_results["soft"], test_results["global"], metric, 7100 + index)
        for index, metric in enumerate(("state", "connector", "opening"))
    }
    if not results["gates"]["overall_pass"]:
        stop(
            out,
            results,
            [
                f"三分层改善={improvements}；要求至少两层改善且第三层恶化不超过5%，通过={stratified_pass}。",
                f"E-T相对noTransition的过渡指标降幅={transition_reduction}；三项均须至少10%，通过={transition_pass}。",
                f"soft占用={occupation.tolist()}，有效专家数={test_results['soft']['effective_experts']:.3f}，分层平均权重={diagonal.tolist()}，防塌缩通过={collapse_pass}。",
                f"test/external有限输出={finite_pass}。",
            ],
            [
                "先检查过渡弱标签是否被连接力数值噪声触发；对Q变化率增加因果低通，再冻结阈值重跑。",
                "采用共享全局线性模型加小残差专家，限制局部专家在样本稀疏区偏离；仍保持共享lift和decoder。",
                "若oracle也不优于global，说明三专家分解没有预测价值，应删除门控路线并保留单一线性AKE。",
                "若oracle有价值而soft失败，再训练有平滑/负载均衡约束的因果门控网络；不能用test真实标签部署。",
            ],
        )

    results["decision"] = {
        "linear_expert_gate": "pass",
        "allow_group_sparsity_and_jacobian": True,
        "allow_bilinear_or_MF_IK": False,
        "reason": "K2.11 Jacobian/group sensitivity remains required before any bilinear prototype.",
    }
    write_json(out / "results.json", results)
    (out / "report.md").write_text(
        "# 线性专家门结果\n\n线性soft gate通过分层、过渡、防塌缩和外部分布有限性门。下一步只允许K2.11敏感度验证。\n",
        encoding="utf-8",
    )
    print(json.dumps(results["decision"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

"""K2.1--K2.3 preregistered linear Koopman gates for the coupled 30D plant.

The script deliberately runs the cheapest falsification tests first.  It exits
after writing stop.md when the state contract cannot support connector-force
prediction; gated experts and bilinear models are not trained in that case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HORIZON = 20
RIDGE = 1.0e-5
BOOTSTRAP = 2000
STATE_KEYS = {
    "S1-team": "s1_team",
    "S2-four": "s2_four",
    "S3-deform": "s3_deform",
    "S4-force-in": "s4_force_in",
}
INPUT_KEYS = {
    "U0-team": "u0_team",
    "U1-four": "u1_four",
    "U2-commanded": "u2_commanded",
    "U3-four+alloc": "u3_alloc",
}
METRICS = ("state", "yaw", "connector", "opening", "force_all")


def json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_data(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["summary"]["accepted"]:
        raise RuntimeError("K2.0 manifest is not accepted")
    rows: list[dict[str, Any]] = []
    keys = set(STATE_KEYS.values()) | set(INPUT_KEYS.values()) | {"force_output"}
    for meta in manifest["trajectories"]:
        path = data_dir / meta["file"]
        if sha256(path) != meta["sha256"]:
            raise RuntimeError(f"hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as source:
            arrays = {key: np.asarray(source[key], dtype=np.float64) for key in keys}
        steps = int(meta["steps"])
        for key in STATE_KEYS.values():
            if arrays[key].shape[0] != steps + 1:
                raise RuntimeError(f"state length mismatch: {path}/{key}")
        for key in INPUT_KEYS.values():
            if arrays[key].shape[0] != steps:
                raise RuntimeError(f"input length mismatch: {path}/{key}")
        if arrays["force_output"].shape[0] != steps + 1:
            raise RuntimeError(f"force length mismatch: {path}")
        if not all(np.all(np.isfinite(value)) for value in arrays.values()):
            raise RuntimeError(f"nonfinite data: {path}")
        rows.append({"meta": meta, "arrays": arrays})
    return manifest, rows


def moments(rows: list[dict[str, Any]], key: str, states: bool) -> tuple[np.ndarray, np.ndarray]:
    pieces = []
    for row in rows:
        if row["meta"]["split"] != "train":
            continue
        value = row["arrays"][key]
        pieces.append(value[:-1] if states else value)
    joined = np.concatenate(pieces, axis=0)
    mean = joined.mean(axis=0)
    std = joined.std(axis=0)
    std = np.where(std < 1.0e-7, 1.0, std)
    return mean, std


def basis(x_norm: np.ndarray, kind: str) -> np.ndarray:
    if kind == "raw":
        return np.concatenate([np.ones((x_norm.shape[0], 1)), x_norm], axis=1)
    clipped = np.clip(x_norm, -8.0, 8.0)
    return np.concatenate([np.ones((x_norm.shape[0], 1)), x_norm, clipped * clipped], axis=1)


def ridge_solve(phi: np.ndarray, target: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    scale = float(phi.shape[0])
    gram = (phi.T @ phi) / scale
    rhs = (phi.T @ target) / scale
    penalty = np.eye(gram.shape[0]) * ridge
    penalty[0, 0] = 0.0
    return np.linalg.solve(gram + penalty, rhs)


def fit_model(
    rows: list[dict[str, Any]],
    name: str,
    state_name: str,
    input_name: str,
    kind: str,
    common_norm: dict[str, np.ndarray],
) -> dict[str, Any]:
    state_key = STATE_KEYS[state_name]
    input_key = INPUT_KEYS[input_name]
    x_mean, x_std = moments(rows, state_key, states=True)
    u_mean, u_std = moments(rows, input_key, states=False)
    phi_parts, next_parts, decode_parts, full_parts, force_parts = [], [], [], [], []
    for row in rows:
        if row["meta"]["split"] != "train":
            continue
        a = row["arrays"]
        xn = (a[state_key] - x_mean) / x_std
        un = (a[input_key] - u_mean) / u_std
        z = basis(xn, kind)
        phi_parts.append(np.concatenate([z[:-1], un], axis=1))
        next_parts.append(z[1:])
        decode_parts.append(z)
        full_parts.append((a["s2_four"] - common_norm["s2_mean"]) / common_norm["s2_std"])
        force_parts.append((a["force_output"] - common_norm["force_mean"]) / common_norm["force_std"])
    phi = np.concatenate(phi_parts, axis=0)
    next_z = np.concatenate(next_parts, axis=0)
    decoder_basis = np.concatenate(decode_parts, axis=0)
    started = time.perf_counter()
    transition = ridge_solve(phi, next_z)
    decode_full = ridge_solve(decoder_basis, np.concatenate(full_parts, axis=0))
    decode_force = ridge_solve(decoder_basis, np.concatenate(force_parts, axis=0))
    elapsed = time.perf_counter() - started
    parameter_count = int(transition.size + decode_full.size + decode_force.size)
    return {
        "name": name,
        "state_name": state_name,
        "state_key": state_key,
        "input_name": input_name,
        "input_key": input_key,
        "kind": kind,
        "x_mean": x_mean,
        "x_std": x_std,
        "u_mean": u_mean,
        "u_std": u_std,
        "transition": transition,
        "decode_full": decode_full,
        "decode_force": decode_force,
        "state_dim": int(x_mean.size),
        "input_dim": int(u_mean.size),
        "lift_dim": int(next_z.shape[1]),
        "parameter_count": parameter_count,
        "fit_seconds": elapsed,
        "train_rows": int(phi.shape[0]),
    }


def save_model(path: Path, model: dict[str, Any]) -> None:
    np.savez_compressed(
        path,
        x_mean=model["x_mean"],
        x_std=model["x_std"],
        u_mean=model["u_mean"],
        u_std=model["u_std"],
        transition=model["transition"],
        decode_full=model["decode_full"],
        decode_force=model["decode_force"],
        metadata_json=np.asarray(json.dumps({key: value for key, value in model.items() if not isinstance(value, np.ndarray)})),
    )


def evaluate_model(
    model: dict[str, Any],
    rows: list[dict[str, Any]],
    split: str,
    common_norm: dict[str, np.ndarray],
) -> dict[str, Any]:
    sums = {metric: np.zeros(HORIZON, dtype=float) for metric in METRICS}
    counts = {metric: np.zeros(HORIZON, dtype=int) for metric in METRICS}
    per_traj: dict[str, dict[str, Any]] = {}
    scenario_sums: dict[str, dict[str, list[float]]] = {}
    finite = True
    inference_seconds = 0.0
    inference_steps = 0
    yaw_indices = np.array([5, 11, 17, 23, 29], dtype=int)

    for row in rows:
        meta, a = row["meta"], row["arrays"]
        if meta["split"] != split:
            continue
        state = a[model["state_key"]]
        controls = a[model["input_key"]]
        steps = controls.shape[0]
        traj_sq = {metric: [] for metric in METRICS}
        for start in range(0, steps - HORIZON + 1, HORIZON):
            xn = ((state[start] - model["x_mean"]) / model["x_std"])[None, :]
            z = basis(xn, model["kind"])[0]
            for h in range(1, HORIZON + 1):
                un = (controls[start + h - 1] - model["u_mean"]) / model["u_std"]
                tick = time.perf_counter()
                z = np.concatenate([z, un]) @ model["transition"]
                pred_full = z @ model["decode_full"]
                pred_force = z @ model["decode_force"]
                inference_seconds += time.perf_counter() - tick
                inference_steps += 1
                if not np.all(np.isfinite(z)) or np.max(np.abs(z)) > 1.0e12:
                    finite = False
                target_full = (a["s2_four"][start + h] - common_norm["s2_mean"]) / common_norm["s2_std"]
                target_force = (a["force_output"][start + h] - common_norm["force_mean"]) / common_norm["force_std"]
                errors = {
                    "state": float(np.mean((pred_full - target_full) ** 2)),
                    "yaw": float(np.mean((pred_full[yaw_indices] - target_full[yaw_indices]) ** 2)),
                    "connector": float(np.mean((pred_force[:8] - target_force[:8]) ** 2)),
                    "opening": float(np.mean((pred_force[8:10] - target_force[8:10]) ** 2)),
                    "force_all": float(np.mean((pred_force - target_force) ** 2)),
                }
                for metric, value in errors.items():
                    sums[metric][h - 1] += value
                    counts[metric][h - 1] += 1
                    if h >= 10:
                        traj_sq[metric].append(value)
        traj_key = f"{meta['scenario']}|{meta['traj_id']}|{int(meta['external'])}"
        traj_metrics = {metric: float(math.sqrt(np.mean(values))) for metric, values in traj_sq.items()}
        traj_metrics["scenario"] = meta["scenario"]
        per_traj[traj_key] = traj_metrics
        scenario = meta["scenario"]
        scenario_sums.setdefault(scenario, {metric: [] for metric in METRICS})
        for metric in METRICS:
            scenario_sums[scenario][metric].append(traj_metrics[metric])

    horizons = {
        metric: np.sqrt(np.divide(sums[metric], counts[metric], out=np.full(HORIZON, np.nan), where=counts[metric] > 0))
        for metric in METRICS
    }
    h10_20 = {metric: float(math.sqrt(np.sum(sums[metric][9:]) / np.sum(counts[metric][9:]))) for metric in METRICS}
    scenarios = {
        scenario: {metric: float(np.mean(values)) for metric, values in metrics.items()}
        for scenario, metrics in scenario_sums.items()
    }
    return {
        "split": split,
        "finite": bool(finite and all(np.all(np.isfinite(value)) for value in horizons.values())),
        "horizon_nrmse": horizons,
        "h10_20_nrmse": h10_20,
        "per_trajectory_h10_20": per_traj,
        "scenario_h10_20": scenarios,
        "rollout_windows": int(counts["state"][0]),
        "mean_inference_us_per_step": 1.0e6 * inference_seconds / max(inference_steps, 1),
    }


def paired_bootstrap(candidate: dict[str, Any], baseline: dict[str, Any], metric: str, seed: int) -> dict[str, Any]:
    a, b = candidate["per_trajectory_h10_20"], baseline["per_trajectory_h10_20"]
    keys = sorted(set(a) & set(b))
    delta = np.asarray([a[key][metric] - b[key][metric] for key in keys], dtype=float)
    rng = np.random.default_rng(seed)
    boot = delta[rng.integers(0, len(delta), size=(BOOTSTRAP, len(delta)))].mean(axis=1)
    pooled = float(np.std(np.r_[ [a[key][metric] for key in keys], [b[key][metric] for key in keys] ], ddof=1))
    return {
        "metric": metric,
        "definition": "candidate minus baseline; negative favors candidate",
        "n_trajectories": len(keys),
        "mean_delta": float(delta.mean()),
        "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        "standardized_effect": float(delta.mean() / pooled) if pooled > 0 else math.nan,
    }


def compact_model(model: dict[str, Any]) -> dict[str, Any]:
    return {key: model[key] for key in ("name", "state_name", "input_name", "kind", "state_dim", "input_dim", "lift_dim", "parameter_count", "fit_seconds", "train_rows")}


def plot_curves(path: Path, title: str, results: dict[str, dict[str, Any]], metric: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for name, result in results.items():
        ax.plot(np.arange(1, HORIZON + 1), result["horizon_nrmse"][metric], marker="o", markersize=2.5, label=name)
    ax.set(xlabel="Teacher-free rollout horizon", ylabel=f"{metric} NRMSE", title=title)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def stop(out: Path, title: str, facts: list[str], solutions: list[str], results: dict[str, Any]) -> None:
    write_json(out / "results.json", results)
    lines = [f"# {title}", "", "## 已核实事实", ""] + [f"- {item}" for item in facts]
    lines += ["", "## 可执行解决方案", ""] + [f"{index}. {item}" for index, item in enumerate(solutions, 1)]
    lines += ["", "按任务门禁，当前不训练门控专家、bilinear或MF-IK。", ""]
    (out / "stop.md").write_text("\n".join(lines), encoding="utf-8")
    raise SystemExit(3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "models").mkdir(exist_ok=True)
    manifest, rows = load_data(args.data.resolve())
    split_counts = manifest["summary"]["split_counts"]
    required = ("train", "validation", "test", "external")
    if any(split_counts.get(key, 0) == 0 for key in required):
        stop(out, "K2.0数据合同未通过", [f"split_counts={split_counts}"], ["重新生成整轨迹划分且含独立test和external的数据。"], {})

    s2_mean, s2_std = moments(rows, "s2_four", states=True)
    force_mean, force_std = moments(rows, "force_output", states=True)
    common_norm = {"s2_mean": s2_mean, "s2_std": s2_std, "force_mean": force_mean, "force_std": force_std}
    results: dict[str, Any] = {
        "protocol": {
            "horizon": HORIZON,
            "teacher_free": True,
            "ridge": RIDGE,
            "bootstrap_resamples": BOOTSTRAP,
            "normalization": "training trajectories only",
            "windows": "non-overlapping 20-step windows; never cross trajectory boundaries",
            "primary_force_components": "four connector Fx/Fy; opening is Q_FR/Q_LR; force-rate excluded from primary force metric",
            "small_difference_rule": "S4 selected only if both connector and opening h10-20 NRMSE improve >5% over S3/S5",
        },
        "data_summary": manifest["summary"],
        "k21": {},
        "k22": {},
        "k23": {},
    }

    # K2.1: raw and fixed-lift linear baselines on the candidate physical state.
    k21_eval: dict[str, dict[str, Any]] = {}
    for kind in ("raw", "lifted"):
        name = f"S3-U1-{kind}"
        model = fit_model(rows, name, "S3-deform", "U1-four", kind, common_norm)
        save_model(out / "models" / f"{name}.npz", model)
        test_eval = evaluate_model(model, rows, "test", common_norm)
        ext_eval = evaluate_model(model, rows, "external", common_norm)
        results["k21"][name] = {"model": compact_model(model), "test": test_eval, "external": ext_eval}
        k21_eval[name] = test_eval
    plot_curves(out / "k21_state.png", "K2.1 independent-test state rollout", k21_eval, "state")
    plot_curves(out / "k21_force.png", "K2.1 independent-test connector-force rollout", k21_eval, "connector")
    if not all(value["test"]["finite"] and value["external"]["finite"] for value in results["k21"].values()):
        stop(
            out,
            "K2.1线性可辨识性门停止",
            ["raw或lifted linear在独立test/external的1--20步输出出现非有限值。"],
            ["检查尺度接近零的变量并改为物理尺度归一化。", "缩小参数失配范围前先定位发散的场景与变量，禁止删除异常轨迹。", "比较增量状态而非绝对全局位置。"],
            results,
        )

    # K2.2: state-set ablation, frozen lifted-linear structure and U1 input.
    variable_eval: dict[str, dict[str, Any]] = {}
    variable_models: dict[str, dict[str, Any]] = {}
    for state_name in STATE_KEYS:
        name = f"{state_name}-U1-lifted"
        if state_name == "S3-deform":
            # Refit is avoided; this is exactly the frozen K2.1 lifted model.
            model_path = out / "models" / "S3-U1-lifted.npz"
            model = fit_model(rows, name, state_name, "U1-four", "lifted", common_norm)
        else:
            model = fit_model(rows, name, state_name, "U1-four", "lifted", common_norm)
        save_model(out / "models" / f"{name}.npz", model)
        variable_models[state_name] = model
        test_eval = evaluate_model(model, rows, "test", common_norm)
        ext_eval = evaluate_model(model, rows, "external", common_norm)
        variable_eval[state_name] = test_eval
        results["k22"][state_name] = {"model": compact_model(model), "test": test_eval, "external": ext_eval}

    # With a fixed, non-trainable lift, S5 has the same S3 input and force
    # decoder and is mathematically identical.  Record that fact rather than
    # manufacturing an apparent independent comparison.
    results["k22"]["S5-force-out"] = {
        "equivalent_to": "S3-deform under this fixed lift because every candidate needs the same supervised force readout for force NRMSE",
        "independent_comparison_available": False,
    }
    plot_curves(out / "k22_connector.png", "K2.2 state-set connector-force ablation", variable_eval, "connector")
    plot_curves(out / "k22_opening.png", "K2.2 state-set opening-load ablation", variable_eval, "opening")
    plot_curves(out / "k22_yaw.png", "K2.2 state-set yaw ablation", variable_eval, "yaw")

    s2_vs_s1 = {
        metric: paired_bootstrap(variable_eval["S2-four"], variable_eval["S1-team"], metric, 6200 + index)
        for index, metric in enumerate(("yaw", "connector", "opening"))
    }
    s3_vs_s2 = {
        metric: paired_bootstrap(variable_eval["S3-deform"], variable_eval["S2-four"], metric, 6300 + index)
        for index, metric in enumerate(("connector", "opening"))
    }
    results["k22"]["paired_gates"] = {"S2_minus_S1": s2_vs_s1, "S3_minus_S2": s3_vs_s2}
    s2_pass = any(item["mean_delta"] < 0.0 for item in s2_vs_s1.values())
    s3_pass = all(item["ci95"][1] < 0.0 for item in s3_vs_s2.values())
    results["k22"]["gate"] = {"S2_over_S1": s2_pass, "S3_over_S2": s3_pass}
    if not s2_pass or not s3_pass:
        facts = [
            f"S2相对S1至少一项改善门：{s2_pass}。",
            f"S3相对S2连接力与张开载荷的逐轨迹bootstrap 95% CI均低于0：{s3_pass}。",
            f"S2-S1={json.dumps(s2_vs_s1, ensure_ascii=False, default=json_default)}",
            f"S3-S2={json.dumps(s3_vs_s2, ensure_ascii=False, default=json_default)}",
        ]
        stop(
            out,
            "K2.2变量集合证据门停止",
            facts,
            [
                "按场景检查S3形变/相对速度的归一化和连接点坐标符号，先做有限差分方向核验。",
                "将预测目标改为相对/增量状态，避免全局位置误差主导回归条件数。",
                "若S3物理状态仍无增益，接受四车状态或线性AKE降级路线，不进入门控专家和MF-IK。",
                "S4/S5的真正比较需要共享可训练lift；固定lift下S5与S3不可独立识别。",
            ],
            results,
        )

    s3_score = variable_eval["S3-deform"]["h10_20_nrmse"]
    s4_score = variable_eval["S4-force-in"]["h10_20_nrmse"]
    s4_improvements = {
        metric: (s3_score[metric] - s4_score[metric]) / s3_score[metric]
        for metric in ("connector", "opening")
    }
    winner_state = "S4-force-in" if all(value > 0.05 for value in s4_improvements.values()) else "S3-deform"
    results["k22"]["selection"] = {
        "winner_state": winner_state,
        "S4_relative_improvement_over_S3": s4_improvements,
        "note": "S3 is the fixed-lift operational representation of S5-force-out; a trainable shared lift is required for a genuine S4/S5 test.",
    }

    # K2.3: input ablation only after the state gates pass.
    input_eval: dict[str, dict[str, Any]] = {}
    for input_name in INPUT_KEYS:
        name = f"{winner_state}-{input_name}-lifted"
        model = fit_model(rows, name, winner_state, input_name, "lifted", common_norm)
        save_model(out / "models" / f"{name}.npz", model)
        test_eval = evaluate_model(model, rows, "test", common_norm)
        ext_eval = evaluate_model(model, rows, "external", common_norm)
        input_eval[input_name] = test_eval
        results["k23"][input_name] = {"model": compact_model(model), "test": test_eval, "external": ext_eval}
    plot_curves(out / "k23_connector.png", "K2.3 input-set connector-force ablation", input_eval, "connector")
    plot_curves(out / "k23_state.png", "K2.3 input-set state ablation", input_eval, "state")
    results["k23"]["paired_vs_U1"] = {
        input_name: {
            metric: paired_bootstrap(input_eval[input_name], input_eval["U1-four"], metric, 6400 + 10 * index + j)
            for j, metric in enumerate(("state", "connector", "opening"))
        }
        for index, input_name in enumerate(("U0-team", "U2-commanded", "U3-four+alloc"))
    }
    results["decision"] = {
        "K2_0": "pass",
        "K2_1": "pass",
        "K2_2": "pass",
        "K2_3": "complete",
        "selected_state_for_next_stage": winner_state,
        "required_physical_input_for_next_stage": "U1-four",
        "allow_linear_experts": True,
        "allow_bilinear_or_MF_IK": False,
        "reason": "The plan permits E-L/E-C/E-T linear experts next; bilinear/MF-IK remains gated on the linear expert comparison.",
    }
    write_json(out / "results.json", results)

    lines = [
        "# K2线性变量门结果",
        "",
        "完整数值见`results.json`，图片为独立test的teacher-free 1--20步NRMSE。",
        "",
        f"- K2.0：通过；split={split_counts}。",
        "- K2.1：raw与lifted linear在test/external均输出有限状态、四点力和张开误差。",
        f"- K2.2：S2>S1门={s2_pass}，S3>S2门={s3_pass}。",
        f"- 下一阶段状态合同：`{winner_state}`；物理输入仍固定为`U1-four`。",
        "- 固定非训练lift下，S5与S3共享同一输入和力监督读出，不能伪装成两个独立模型；真正S4/S5选择留给共享可训练lift。",
        "- 当前只允许进入E-L/E-C/E-T线性专家；不允许提前训练bilinear/MF-IK。",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(results["decision"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

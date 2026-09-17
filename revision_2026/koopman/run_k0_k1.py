"""K0/K1 audit for the current Koopman evidence chain.

This script is deliberately diagnostic-only.  It does not retrain or modify the
controller.  It freezes the active matrices and evaluates 1--20 step open-loop
rollouts on the data that the current project calls validation data.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import pickle
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "k01"
OUT.mkdir(parents=True, exist_ok=True)
HORIZON = 20
MAX_WINDOWS = 2048
WINDOW_SEED = 42026


def json_default(value: Any):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return str(value)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def radius(matrix: np.ndarray) -> float:
    return float(np.max(np.abs(np.linalg.eigvals(np.asarray(matrix, dtype=float)))))


def matrix_summary(matrix: np.ndarray) -> dict[str, Any]:
    arr = np.asarray(matrix, dtype=float)
    return {
        "shape": list(arr.shape),
        "finite": bool(np.all(np.isfinite(arr))),
        "spectral_radius": radius(arr) if arr.shape[0] == arr.shape[1] else None,
        "norm_2": float(np.linalg.norm(arr, 2)),
        "norm_fro": float(np.linalg.norm(arr)),
    }


def build_windows(xs_val: np.ndarray, us_val: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t_eff = min(xs_val.shape[1] - 1, us_val.shape[1])
    candidates = [(i, k) for i in range(xs_val.shape[0]) for k in range(0, t_eff - HORIZON + 1, HORIZON)]
    rng = np.random.default_rng(WINDOW_SEED)
    if len(candidates) > MAX_WINDOWS:
        chosen = rng.choice(len(candidates), size=MAX_WINDOWS, replace=False)
        candidates = [candidates[int(i)] for i in np.sort(chosen)]
    x0 = np.asarray([xs_val[i, k] for i, k in candidates], dtype=float)
    target = np.asarray([[xs_val[i, k + h] for h in range(1, HORIZON + 1)] for i, k in candidates], dtype=float)
    controls = np.asarray([[us_val[i, k + h] for h in range(HORIZON)] for i, k in candidates], dtype=float)
    return x0, target, controls


def lift_batch(net, x_scaled: np.ndarray) -> np.ndarray:
    import torch

    rows = []
    net.eval()
    with torch.no_grad():
        for start in range(0, x_scaled.shape[0], 4096):
            xb = torch.from_numpy(x_scaled[start : start + 4096].astype(np.float32)).to(net.device)
            rows.append(net.lift(xb).detach().cpu().numpy())
    return np.vstack(rows)


def rollout(
    *,
    mode: str,
    A: np.ndarray,
    B: np.ndarray,
    C: np.ndarray,
    z0: np.ndarray,
    controls_raw: np.ndarray,
    targets_raw: np.ndarray,
    standardizer_x,
    standardizer_u,
) -> dict[str, np.ndarray]:
    z = np.asarray(z0, dtype=float).copy()
    predictions = []
    for h in range(HORIZON):
        u = np.asarray(controls_raw[:, h, :], dtype=float)
        if standardizer_u is not None:
            u = standardizer_u.transform(u)
        if mode == "linear":
            z = z @ np.asarray(A, dtype=float).T + u @ np.asarray(B, dtype=float).T
        elif mode == "bilinear":
            zu = np.einsum("bi,bj->bij", z, u).reshape(z.shape[0], -1)
            z = z @ np.asarray(A, dtype=float).T + zu @ np.asarray(B, dtype=float).T
        else:
            raise ValueError(mode)
        x_scaled = z @ np.asarray(C, dtype=float).T
        if standardizer_x is not None:
            x_raw = standardizer_x.inverse_transform(x_scaled)
        else:
            x_raw = x_scaled
        predictions.append(x_raw)
    pred = np.stack(predictions, axis=1)
    error = pred - targets_raw
    rmse = np.sqrt(np.mean(error**2, axis=0))
    target_std = np.maximum(np.std(targets_raw.reshape(-1, targets_raw.shape[-1]), axis=0), 1.0e-9)
    nrmse = rmse / target_std[None, :]
    return {"prediction": pred, "rmse": rmse, "nrmse": nrmse}


def force_nonidentifiability() -> dict[str, Any]:
    model_dir = ROOT / "revision_2026" / "model"
    if str(model_dir) not in sys.path:
        sys.path.insert(0, str(model_dir))
    from four_vehicle_coupled import ModelParams, connector_diagnostics, initialize_state

    params = ModelParams()
    state_a = initialize_state(params, speed_mps=2.0)
    state_b = state_a.copy()
    # The old Koopman observation contains vehicle states only.  Moving the
    # omitted payload leaves every old observation and input identical while
    # changing all connector deformations and forces.
    state_b[24] += 0.012
    diag_a = connector_diagnostics(state_a, params)
    diag_b = connector_diagnostics(state_b, params)
    vehicle_observation_equal = bool(np.array_equal(state_a[:24], state_b[:24]))
    force_a = np.asarray(diag_a["force_payload_body_n"], dtype=float)
    force_b = np.asarray(diag_b["force_payload_body_n"], dtype=float)
    return {
        "old_vehicle_observation_equal": vehicle_observation_equal,
        "old_control_equal": True,
        "omitted_payload_x_difference_m": float(state_b[24] - state_a[24]),
        "case_a_force_body_n": force_a,
        "case_b_force_body_n": force_b,
        "max_point_force_change_n": float(np.max(np.linalg.norm(force_b - force_a, axis=1))),
        "proof_result": bool(vehicle_observation_equal and not np.allclose(force_a, force_b)),
        "interpretation": "No unique four-point force map exists from the old vehicle-only Koopman observation and control.",
    }


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    dataset = ROOT / "saved_data" / "payload_team" / "offline_dataset_a1_rigid_payload_2t.npz"
    pars_path = ROOT / "saved_data" / "payload_team" / "offline_dataset_pars_a1_rigid_payload_2t.pkl"
    cached_e1 = ROOT / "tf14_paper_figures_20260508" / "source" / "fig03_prediction_model_comparison.npz"
    stage5_path = ROOT / "tf14_stage5_phase_role_scenarios_20260507" / "run_tf14_stage5_phase_role_suite.py"
    stage1_path = ROOT / "tf14_stage1_suite_20260506" / "run_tf14_stage1_suite.py"
    tracked = [
        ROOT / "tf14_pre.ipynb",
        ROOT / "tf14_runtime.py",
        ROOT / "core" / "koopman_core_linear.py",
        ROOT / "control_files" / "tf11_a1" / "mpc_helpers.py",
        ROOT / "dynamics" / "learned_models_control" / "bilinear_dynamics.py",
        stage1_path,
        stage5_path,
        dataset,
        pars_path,
        cached_e1,
    ]
    file_manifest = {
        str(p.relative_to(ROOT)): {"sha256": sha256(p), "bytes": p.stat().st_size}
        for p in tracked
        if p.exists()
    }

    with pars_path.open("rb") as handle:
        pars = pickle.load(handle)
    with np.load(dataset, allow_pickle=True) as data:
        dataset_shapes = {key: list(data[key].shape) for key in data.files}
    old_num_traj = int(pars["num_traj"])
    old_num_train = int(pars["num_train"])
    old_num_val = int(pars["num_val"])

    split_contract = {
        "frozen_before_new_training": True,
        "old_dataset": {
            "num_trajectories": old_num_traj,
            "train_indices": [0, old_num_train - 1],
            "validation_indices": [old_num_train, old_num_train + old_num_val - 1],
            "independent_test_indices": None,
            "independent_test_exists": False,
            "reason": "All non-training trajectories were used as validation during lifting-network development.",
        },
        "new_coupled_dataset_rule": {
            "unit": "whole trajectory; windows may not cross splits",
            "stratification": ["straight", "single_lane_change", "hairpin"],
            "assignment": "within each scenario, traj_id modulo 20: 0-13 train, 14-16 validation, 17-19 test",
            "fractions": {"train": 0.70, "validation": 0.15, "test": 0.15},
            "external_mismatch": "separate parameter/speed/friction/connector set; never used for tuning",
            "network_variables": "excluded from physical Koopman state and stored only as exogenous metadata",
        },
    }
    write_json(OUT / "split.json", split_contract)

    stage5 = load_module("stage5_for_k01", stage5_path)
    stage1 = stage5._load_stage1_module()
    ns = stage5._bootstrap_env_for_path(stage1, "sine")
    model = ns["model_koop_dnn_lin"]
    net = model.net
    xs_train = np.asarray(ns["xs_train"], dtype=float)
    us_train = np.asarray(ns["us_train"], dtype=float)
    xs_val = np.asarray(ns["xs_val"], dtype=float)
    us_val = np.asarray(ns["us_val"], dtype=float)

    raw_pack = ns["get_tf9_model_pack"](
        {
            "use_stable_projected_A": False,
            "use_input_aware_stable_projection": False,
        }
    )
    helpers = importlib.import_module("control_files.tf11_a1.mpc_helpers")
    u_samples, u_bounds = helpers._build_scaled_control_projection_samples(model, us_train, max_samples=96)
    A_bil_irsp, B_bil_irsp, irsp_info = helpers._input_aware_project_bilinear_matrices(
        raw_pack["A_bilinear"],
        raw_pack["B_bilinear"],
        u_samples=u_samples,
        u_bounds=u_bounds,
        radius=0.998,
        drift_radius=0.992,
        max_iter=32,
        enforce_norm_bound=False,
    )
    A_lin = np.asarray(ns["A_lin"], dtype=float)
    A_lin_stable = np.asarray(ns["A_lin_stable"], dtype=float)
    B_lin = np.asarray(ns["B_lin"], dtype=float)
    C_lin = np.asarray(ns["C_lin"], dtype=float)
    A_bil = np.asarray(raw_pack["A_bilinear"], dtype=float)
    B_bil = np.asarray(raw_pack["B_bilinear"], dtype=float)

    np.savez_compressed(
        OUT / "matrices.npz",
        A_linear=A_lin,
        A_linear_projected=A_lin_stable,
        B_linear=B_lin,
        C_linear=C_lin,
        A_bilinear=A_bil,
        B_bilinear=B_bil,
        A_bilinear_irsp=A_bil_irsp,
        B_bilinear_irsp=B_bil_irsp,
        input_samples_scaled=u_samples,
        input_bounds_scaled=u_bounds,
    )

    x0, targets, controls = build_windows(xs_val, us_val)
    x0_scaled = net.standardizer_x.transform(x0) if net.standardizer_x is not None else x0
    z0 = lift_batch(net, x0_scaled)
    models = {
        "lifted_linear": ("linear", A_lin, B_lin),
        "lifted_linear_projected": ("linear", A_lin_stable, B_lin),
        "bilinear": ("bilinear", A_bil, B_bil),
        "bilinear_irsp": ("bilinear", A_bil_irsp, B_bil_irsp),
    }
    results = {}
    for name, (mode, A, B) in models.items():
        results[name] = rollout(
            mode=mode,
            A=A,
            B=B,
            C=C_lin,
            z0=z0,
            controls_raw=controls,
            targets_raw=targets,
            standardizer_x=net.standardizer_x,
            standardizer_u=net.standardizer_u,
        )

    state_labels = ["s", "e_y", "e_psi", "v_x", "v_y", "r"]
    force_audit = force_nonidentifiability()
    cached_summary = {}
    with np.load(cached_e1, allow_pickle=True) as cached:
        labels = [str(v) for v in cached["model_labels"]]
        horizons = np.asarray(cached["horizons"], dtype=int)
        for i, label in enumerate(labels):
            cached_summary[label] = {
                "h10_l2": float(cached["rollout_mean"][i, np.where(horizons == 10)[0][0]]),
                "h20_l2": float(cached["rollout_mean"][i, np.where(horizons == 20)[0][0]]),
            }

    matrix_report = {
        "linear": matrix_summary(A_lin),
        "linear_projected": matrix_summary(A_lin_stable),
        "bilinear": matrix_summary(A_bil),
        "bilinear_irsp": matrix_summary(A_bil_irsp),
        "B_linear": matrix_summary(B_lin),
        "B_bilinear": matrix_summary(B_bil),
        "B_bilinear_irsp": matrix_summary(B_bil_irsp),
        "irsp_info": irsp_info,
        "irsp_zero_input_norm_gate": {
            "required_upper_bound": 0.998,
            "actual_norm_2": float(np.linalg.norm(A_bil_irsp, 2)),
            "passes": bool(np.linalg.norm(A_bil_irsp, 2) <= 0.998 + 1.0e-12),
        },
    }
    model_metrics = {}
    for name, item in results.items():
        model_metrics[name] = {
            "h1_rmse": dict(zip(state_labels, item["rmse"][0].tolist())),
            "h10_rmse": dict(zip(state_labels, item["rmse"][9].tolist())),
            "h20_rmse": dict(zip(state_labels, item["rmse"][19].tolist())),
            "h10_mean_nrmse": float(np.mean(item["nrmse"][9])),
            "h20_mean_nrmse": float(np.mean(item["nrmse"][19])),
        }

    report = {
        "stage": "K0_K1_current_koopman_audit",
        "diagnostic_only": True,
        "data": {
            "dataset_shapes": dataset_shapes,
            "bootstrap_train_shape": list(xs_train.shape),
            "bootstrap_validation_shape": list(xs_val.shape),
            "independent_test_exists": False,
            "validation_used_for_training_selection": True,
            "scenario_labels_available": False,
            "network_metadata_available": False,
            "evaluation_windows": int(x0.shape[0]),
            "window_seed": WINDOW_SEED,
        },
        "state_contract": {
            "old_output_states": state_labels,
            "old_output_dimension": 6,
            "payload_state_included": False,
            "connector_deformation_included": False,
            "connector_force_included": False,
            "force_prediction_defined": False,
        },
        "matrix_report": matrix_report,
        "actual_lifted_validation_metrics": model_metrics,
        "cached_lightweight_screening": cached_summary,
        "force_nonidentifiability": force_audit,
        "gates": {
            "GK0_independent_test": False,
            "GK1_1_to_20_state_diagnostic": True,
            "GK1_scenario_stratification": False,
            "GK1_force_prediction_error": False,
            "continue_to_K2": False,
        },
        "stop_reason": "The current model has no independent test split and its six-state output cannot define four-point connector-force prediction.",
    }
    write_json(OUT / "report.json", report)
    write_json(OUT / "files.json", file_manifest)

    np.savez_compressed(
        OUT / "rollout.npz",
        horizons=np.arange(1, HORIZON + 1),
        state_labels=np.asarray(state_labels, dtype=object),
        model_labels=np.asarray(list(results), dtype=object),
        rmse=np.stack([results[name]["rmse"] for name in results]),
        nrmse=np.stack([results[name]["nrmse"] for name in results]),
    )

    colors = {
        "lifted_linear": "#4C78A8",
        "lifted_linear_projected": "#72B7B2",
        "bilinear": "#F58518",
        "bilinear_irsp": "#E45756",
    }
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    h = np.arange(1, HORIZON + 1)
    for j, label in enumerate(state_labels):
        ax = axes.flat[j]
        for name, item in results.items():
            ax.plot(h, item["nrmse"][:, j], label=name, color=colors[name], lw=1.5)
        ax.set_title(label)
        ax.set_xlabel("prediction step")
        ax.set_ylabel("NRMSE")
        ax.grid(True, alpha=0.25)
    axes.flat[0].legend(fontsize=7)
    fig.suptitle("K1 actual lifted-model rollout on the existing validation trajectories")
    fig.tight_layout()
    fig.savefig(OUT / "state.png", dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for name, item in results.items():
        axes[0].plot(h, np.mean(item["nrmse"], axis=1), label=name, color=colors[name], lw=1.7)
    axes[0].set(xlabel="prediction step", ylabel="mean state NRMSE", title="Actual lifted models")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(fontsize=7)
    fa = np.asarray(force_audit["case_a_force_body_n"], dtype=float)
    fb = np.asarray(force_audit["case_b_force_body_n"], dtype=float)
    x = np.arange(4)
    axes[1].bar(x - 0.18, np.linalg.norm(fa, axis=1), width=0.36, label="same old observation: case A")
    axes[1].bar(x + 0.18, np.linalg.norm(fb, axis=1), width=0.36, label="same old observation: case B")
    axes[1].set_xticks(x, ["FL", "FR", "RL", "RR"])
    axes[1].set(xlabel="connector", ylabel="point force (N)", title="Force is not identifiable from old state")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "diagnosis.png", dpi=220)
    plt.close(fig)

    stop_lines = [
        "# K1停止与解决方案",
        "",
        "## 停止事实",
        "",
        "按 Koopman 方案执行到 K1 后停止，没有进入 MF-IK 训练。原因不是程序跑不动，而是当前证据合同不允许计算审稿人所需的独立受力预测误差。",
        "",
        f"- 原离线数据共 `{old_num_traj}` 条轨迹，其中 `{old_num_train}` 条训练、`{old_num_val}` 条验证；不存在从未参与模型选择的独立测试集。",
        "- 旧 Koopman 输出只有 `s/e_y/e_psi/v_x/v_y/r` 六个单车状态，没有货物状态、连接形变、四点力或张开内力。",
        f"- 物理反例保持全部旧车辆观测和控制完全相同，只改变被遗漏的货物纵向位置 `0.012 m`，单点连接力最多改变 `{force_audit['max_point_force_change_n']:.2f} N`。因此旧状态到四点力不存在唯一映射。",
        "- 现有 Fig.3 是轻量最小二乘缓存筛选，不是实际 DNN lifted 模型的独立多种子试验；不能作为20步贡献证据。",
        f"- IRSP后零输入矩阵二范数为 `{matrix_report['irsp_zero_input_norm_gate']['actual_norm_2']:.6f}`，仍未满足 `0.998` 的连续域范数门。",
        "",
        "## 允许恢复K2的最小修复",
        "",
        "1. 用30维四车—货物plant生成带场景标签的新数据；整条轨迹按 `split.json` 的70/15/15规则分组，严禁窗口跨集合。",
        "2. 先保存四点Fx/Fy、连接形变/速度、前后/左右张开代理和力变化率，再训练任何模型。",
        "3. 在新合同上先实现raw-state linear与lifted linear AKE，确认两者都能输出20步状态和受力误差；这一步通过后才能实现MF-IK。",
        "4. 新独立测试集只运行一次最终比较；外部失配集不参与权重、正则或时域选择。",
        "5. 不再把旧Fig.3、sampled spectral radius或clean闭环改善写成Koopman专项收益。",
        "",
        "恢复条件：`GK0_independent_test`、`GK1_scenario_stratification`和`GK1_force_prediction_error`全部变为true。",
    ]
    (OUT / "stop.md").write_text("\n".join(stop_lines) + "\n", encoding="utf-8")
    print(json.dumps(report["gates"], ensure_ascii=False))


if __name__ == "__main__":
    main()

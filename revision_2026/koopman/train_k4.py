"""K4.2 fixed-lift multi-step refit and baseline-anchored low-rank correction.

The script consumes only K2 train/validation and the already-viewed development
splits.  It never generates or reads confirmation trajectories.  G42 failure
writes stop/solutions records and exits successfully after preserving evidence.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import platform
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


HORIZON = 20
METRICS = ("state", "connector", "opening")


def json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        metadata = json.loads(str(source["metadata_json"].item()))
        result = dict(metadata)
        for key in ("x_mean", "x_std", "u_mean", "u_std", "transition", "decode_full", "decode_force"):
            result[key] = np.asarray(source[key], dtype=np.float64)
    return result


def composite(metrics: dict[str, float]) -> float:
    return float(np.mean([metrics[name] for name in METRICS]))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


@dataclass
class WindowData:
    z0: np.ndarray
    controls: np.ndarray
    state_target: np.ndarray
    force_target: np.ndarray
    trajectory_index: np.ndarray
    trajectory_keys: list[str]


def build_windows(
    rows: list[dict[str, Any]],
    split: str,
    model: dict[str, Any],
    linear: Any,
    common_norm: dict[str, np.ndarray],
    stride: int,
) -> WindowData:
    z0_parts: list[np.ndarray] = []
    u_parts: list[np.ndarray] = []
    state_parts: list[np.ndarray] = []
    force_parts: list[np.ndarray] = []
    index_parts: list[np.ndarray] = []
    keys: list[str] = []
    trajectory_counter = 0
    for row in rows:
        meta, arrays = row["meta"], row["arrays"]
        if meta["split"] != split:
            continue
        steps = arrays["u1_four"].shape[0]
        origins = np.arange(0, steps - HORIZON + 1, stride, dtype=int)
        if origins.size == 0:
            continue
        xn = (arrays["s3_deform"][origins] - model["x_mean"]) / model["x_std"]
        z0_parts.append(linear.basis(xn, model["kind"]))
        controls = np.stack([arrays["u1_four"][origins + h] for h in range(HORIZON)], axis=1)
        u_parts.append((controls - model["u_mean"][None, None, :]) / model["u_std"][None, None, :])
        state_parts.append(
            np.stack(
                [
                    (arrays["s2_four"][origins + h] - common_norm["s2_mean"]) / common_norm["s2_std"]
                    for h in range(1, HORIZON + 1)
                ],
                axis=1,
            )
        )
        force_parts.append(
            np.stack(
                [
                    (arrays["force_output"][origins + h] - common_norm["force_mean"]) / common_norm["force_std"]
                    for h in range(1, HORIZON + 1)
                ],
                axis=1,
            )
        )
        index_parts.append(np.full(origins.size, trajectory_counter, dtype=np.int64))
        keys.append(f"{meta['scenario']}|{meta['traj_id']}|{int(meta['external'])}")
        trajectory_counter += 1
    return WindowData(
        z0=np.concatenate(z0_parts).astype(np.float32),
        controls=np.concatenate(u_parts).astype(np.float32),
        state_target=np.concatenate(state_parts).astype(np.float32),
        force_target=np.concatenate(force_parts).astype(np.float32),
        trajectory_index=np.concatenate(index_parts),
        trajectory_keys=keys,
    )


class CorrectionModel(nn.Module):
    def __init__(
        self,
        fixed: dict[str, Any],
        mode: str,
        rank: int | None,
        projection_limit: float | None,
        factor_seeds: dict[str, int],
    ) -> None:
        super().__init__()
        zdim = int(fixed["transition"].shape[1])
        udim = int(fixed["u_mean"].size)
        force_dim = int(fixed["decode_force"].shape[1])
        self.mode = mode
        self.rank = rank
        self.projection_limit = projection_limit
        self.register_buffer("A0", torch.as_tensor(fixed["transition"][:zdim], dtype=torch.float32))
        self.register_buffer("B0", torch.as_tensor(fixed["transition"][zdim:], dtype=torch.float32))
        self.register_buffer("Cstate", torch.as_tensor(fixed["decode_full"], dtype=torch.float32))
        self.register_buffer("CF0", torch.as_tensor(fixed["decode_force"], dtype=torch.float32))
        if mode == "M2-full":
            self.dA_param = nn.Parameter(torch.zeros(zdim, zdim))
            self.dB_param = nn.Parameter(torch.zeros(udim, zdim))
            self.dCF_param = nn.Parameter(torch.zeros(zdim, force_dim))
        elif mode == "M3-anchor":
            if rank is None or projection_limit is None:
                raise ValueError("M3 requires rank and projection limit")
            self.LA = nn.Parameter(torch.zeros(zdim, rank))
            self.RA = nn.Parameter(self._orthogonal(zdim, rank, factor_seeds["A"]))
            self.LB = nn.Parameter(torch.zeros(udim, rank))
            self.RB = nn.Parameter(self._orthogonal(zdim, rank, factor_seeds["B"]))
            self.LF = nn.Parameter(torch.zeros(zdim, rank))
            self.RF = nn.Parameter(self._orthogonal(force_dim, rank, factor_seeds["force_decoder"]))
        else:
            raise KeyError(mode)

    @staticmethod
    def _orthogonal(rows: int, columns: int, seed: int) -> torch.Tensor:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed)
        matrix = torch.randn(rows, columns, generator=generator)
        q, _ = torch.linalg.qr(matrix, mode="reduced")
        return q[:, :columns].contiguous()

    def corrections(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.mode == "M2-full":
            return self.dA_param, self.dB_param, self.dCF_param
        return self.LA @ self.RA.T, self.LB @ self.RB.T, self.LF @ self.RF.T

    def matrices(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        d_a, d_b, d_cf = self.corrections()
        return self.A0 + d_a, self.B0 + d_b, self.CF0 + d_cf

    def rollout(self, z0: torch.Tensor, controls: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        a, b, cf = self.matrices()
        z = z0
        states = []
        forces = []
        for step in range(HORIZON):
            z = z @ a + controls[:, step] @ b
            states.append(z @ self.Cstate)
            forces.append(z @ cf)
        return torch.stack(states, dim=1), torch.stack(forces, dim=1)

    def normalized_correction(self) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        d_a, d_b, d_cf = self.corrections()
        eps = torch.tensor(1.0e-12, device=d_a.device)
        return (
            torch.linalg.vector_norm(d_a) / torch.maximum(torch.linalg.vector_norm(self.A0), eps),
            torch.linalg.vector_norm(d_b) / torch.maximum(torch.linalg.vector_norm(self.B0), eps),
            torch.linalg.vector_norm(d_cf) / torch.maximum(torch.linalg.vector_norm(self.CF0), eps),
        )

    @torch.no_grad()
    def project(self) -> dict[str, float]:
        before = self.normalized_correction()
        if self.mode == "M3-anchor":
            limit = float(self.projection_limit)
            for left, ratio in ((self.LA, before[0]), (self.LB, before[1]), (self.LF, before[2])):
                value = float(ratio.detach().cpu())
                if value > limit:
                    left.mul_(limit / value)
        after = self.normalized_correction()
        return {
            "A_before": float(before[0].cpu()),
            "B_before": float(before[1].cpu()),
            "CF_before": float(before[2].cpu()),
            "A_after": float(after[0].cpu()),
            "B_after": float(after[1].cpu()),
            "CF_after": float(after[2].cpu()),
        }

    def correction_summary(self) -> dict[str, float]:
        values = [float(value.detach().cpu()) for value in self.normalized_correction()]
        return {
            "A_relative": values[0],
            "B_relative": values[1],
            "CF_relative": values[2],
            "combined_R": float(math.sqrt(sum(value * value for value in values))),
        }


def tensor_dataset(data: WindowData) -> TensorDataset:
    return TensorDataset(
        torch.from_numpy(data.z0),
        torch.from_numpy(data.controls),
        torch.from_numpy(data.state_target),
        torch.from_numpy(data.force_target),
    )


def loss_value(
    model: CorrectionModel,
    batch: tuple[torch.Tensor, ...],
    weights: torch.Tensor,
    lambda_anchor: float,
    lambda_force_rate: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    z0, controls, target_state, target_force = batch
    pred_state, pred_force = model.rollout(z0, controls)
    state_h = torch.mean((pred_state - target_state) ** 2, dim=(0, 2))
    connector_h = torch.mean((pred_force[:, :, :8] - target_force[:, :, :8]) ** 2, dim=(0, 2))
    opening_h = torch.mean((pred_force[:, :, 8:10] - target_force[:, :, 8:10]) ** 2, dim=(0, 2))
    rollout = torch.sum(weights * (state_h + connector_h + opening_h) / 3.0)
    pred_delta = pred_force[:, 1:, :8] - pred_force[:, :-1, :8]
    target_delta = target_force[:, 1:, :8] - target_force[:, :-1, :8]
    rate = torch.mean((pred_delta - target_delta) ** 2)
    relative = model.normalized_correction()
    anchor = sum(value * value for value in relative)
    total = rollout + lambda_anchor * anchor + lambda_force_rate * rate
    return total, {
        "total": float(total.detach().cpu()),
        "rollout": float(rollout.detach().cpu()),
        "rate": float(rate.detach().cpu()),
        "anchor": float(anchor.detach().cpu()),
    }


@torch.no_grad()
def evaluate(model: CorrectionModel, data: WindowData, device: torch.device, batch_size: int = 1024) -> dict[str, Any]:
    model.eval()
    loader = DataLoader(tensor_dataset(data), batch_size=batch_size, shuffle=False)
    horizon_sum = {name: np.zeros(HORIZON, dtype=np.float64) for name in METRICS}
    horizon_count = np.zeros(HORIZON, dtype=np.int64)
    per_window = {name: [] for name in METRICS}
    all_finite = True
    for batch in loader:
        z0, controls, target_state, target_force = [value.to(device, non_blocking=True) for value in batch]
        pred_state, pred_force = model.rollout(z0, controls)
        error = {
            "state": torch.mean((pred_state - target_state) ** 2, dim=2),
            "connector": torch.mean((pred_force[:, :, :8] - target_force[:, :, :8]) ** 2, dim=2),
            "opening": torch.mean((pred_force[:, :, 8:10] - target_force[:, :, 8:10]) ** 2, dim=2),
        }
        all_finite = all_finite and all(bool(torch.all(torch.isfinite(value))) for value in error.values())
        count = z0.shape[0]
        horizon_count += count
        for name, value in error.items():
            array = value.detach().cpu().double().numpy()
            horizon_sum[name] += np.sum(array, axis=0)
            per_window[name].append(array)
    merged = {name: np.concatenate(values, axis=0) for name, values in per_window.items()}
    horizon = {name: np.sqrt(horizon_sum[name] / horizon_count) for name in METRICS}
    h10 = {name: float(math.sqrt(np.mean(merged[name][:, 9:]))) for name in METRICS}
    per_trajectory: dict[str, dict[str, float]] = {}
    for index, key in enumerate(data.trajectory_keys):
        select = data.trajectory_index == index
        per_trajectory[key] = {name: float(math.sqrt(np.mean(merged[name][select, 9:]))) for name in METRICS}
    return {
        "finite": bool(all_finite),
        "horizon_nrmse": horizon,
        "h10_20_nrmse": h10,
        "composite": composite(h10),
        "per_trajectory_h10_20": per_trajectory,
        "windows": int(data.z0.shape[0]),
        "correction": model.correction_summary(),
    }


def train_one(
    fixed: dict[str, Any],
    train: WindowData,
    validation: WindowData,
    config: dict[str, Any],
    mode: str,
    seed: int,
    rank: int | None,
    projection_limit: float | None,
    device: torch.device,
    output: Path,
) -> tuple[CorrectionModel, dict[str, Any]]:
    set_seed(seed)
    model = CorrectionModel(fixed, mode, rank, projection_limit, config["factor_seeds"]).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"]
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    loader = DataLoader(
        tensor_dataset(train),
        batch_size=config["batch"],
        shuffle=True,
        generator=generator,
        pin_memory=device.type == "cuda",
        num_workers=0,
    )
    weights = torch.arange(1, HORIZON + 1, dtype=torch.float32, device=device)
    weights = 2.0 * weights / (HORIZON * (HORIZON + 1))
    history = []
    best_score = math.inf
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = -1
    patience = 0
    started = time.perf_counter()
    max_projection_before = 0.0
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        sums = {name: 0.0 for name in ("total", "rollout", "rate", "anchor")}
        batches = 0
        for batch in loader:
            batch = tuple(value.to(device, non_blocking=True) for value in batch)
            optimizer.zero_grad(set_to_none=True)
            loss, parts = loss_value(model, batch, weights, config["lambda_anchor"], config["lambda_force_rate"])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config["gradient_clip"])
            optimizer.step()
            projected = model.project()
            max_projection_before = max(
                max_projection_before,
                projected["A_before"],
                projected["B_before"],
                projected["CF_before"],
            )
            for name in sums:
                sums[name] += parts[name]
            batches += 1
        validation_result = evaluate(model, validation, device)
        score = validation_result["composite"]
        history.append(
            {
                "epoch": epoch,
                "train": {name: value / max(batches, 1) for name, value in sums.items()},
                "validation": validation_result["h10_20_nrmse"],
                "validation_composite": score,
                "correction": validation_result["correction"],
            }
        )
        if score < best_score - config["min_delta"]:
            best_score = score
            best_state = copy.deepcopy({name: value.detach().cpu() for name, value in model.state_dict().items()})
            best_epoch = epoch
            patience = 0
        else:
            patience += 1
        if patience >= config["patience"]:
            break
    if best_state is None:
        raise RuntimeError("no best checkpoint")
    model.load_state_dict(best_state)
    final_validation = evaluate(model, validation, device)
    metadata = {
        "mode": mode,
        "seed": seed,
        "rank": rank,
        "projection_limit": projection_limit,
        "best_epoch": best_epoch,
        "epochs_run": len(history),
        "best_validation": final_validation,
        "training_seconds": time.perf_counter() - started,
        "maximum_preprojection_relative_norm": max_projection_before,
        "history": history,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": best_state,
            "metadata": {key: value for key, value in metadata.items() if key != "history"},
        },
        output,
    )
    write_json(output.with_suffix(".json"), metadata)
    return model, metadata


def mean_evaluation(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    h10 = {name: float(np.mean([row["h10_20_nrmse"][name] for row in evaluations])) for name in METRICS}
    horizon = {
        name: np.mean([np.asarray(row["horizon_nrmse"][name]) for row in evaluations], axis=0) for name in METRICS
    }
    return {
        "h10_20_nrmse": h10,
        "composite": composite(h10),
        "horizon_nrmse": horizon,
        "composite_std_across_seeds": float(np.std([row["composite"] for row in evaluations], ddof=1)),
        "combined_R_mean": float(np.mean([row["correction"]["combined_R"] for row in evaluations])),
        "all_finite": bool(all(row["finite"] for row in evaluations)),
    }


def plot_horizons(fixed: dict[str, Any], m2: dict[str, Any], m3: dict[str, Any], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(1, HORIZON + 1)
    ax.plot(x, fixed["horizon_nrmse"]["state"], label="M1 fixed S5", linewidth=2)
    ax.plot(x, m2["horizon_nrmse"]["state"], label="M2 full refit")
    ax.plot(x, m3["horizon_nrmse"]["state"], label="M3 anchored low-rank")
    ax.set_xlabel("prediction horizon")
    ax.set_ylabel("state NRMSE")
    ax.set_title("K4.2 dev_test_old state rollout")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "development" / "horizon_state.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True)
    for axis, metric in zip(axes, ("connector", "opening")):
        axis.plot(x, fixed["horizon_nrmse"][metric], label="M1 fixed S5", linewidth=2)
        axis.plot(x, m2["horizon_nrmse"][metric], label="M2 full refit")
        axis.plot(x, m3["horizon_nrmse"][metric], label="M3 anchored low-rank")
        axis.set_title(metric)
        axis.set_xlabel("prediction horizon")
        axis.set_ylabel("NRMSE")
        axis.grid(True, alpha=0.25)
    axes[0].legend()
    fig.suptitle("K4.2 dev_test_old force/opening rollout")
    fig.tight_layout()
    fig.savefig(out / "development" / "horizon_force.png", dpi=180)
    plt.close(fig)


def stop_documents(out: Path, gate: dict[str, Any]) -> None:
    text = [
        "# K4停止记录",
        "",
        "K4.2开发门G42失败。按预注册规则停止：不生成confirm、不接入MPC、不增加网格或训练seed，最终预测器回退M1 fixed S5-operational。",
        "",
        "## 失败项",
        "",
    ]
    text.extend(f"- {name}: `{passed}`" for name, passed in gate["checks"].items())
    text.extend(["", "完整原始值见`k42_results.json`。", ""])
    (out / "stop.md").write_text("\n".join(text), encoding="utf-8")
    solutions = [
        "# K4.2失败后的解决方案",
        "",
        "1. 当前论文与闭环实现采用M1 fixed S5-operational，不再声称低秩多步修正或显式力输入具有部署优势。",
        "2. 保留本轮M2/M3负结果，先检查误差是否集中于staged_100m或力变化率；该诊断只能解释失败，不能在同一确认协议下追加调参。",
        "3. 若以后重启，应建立全新的开发/确认划分，重新预注册残差参数化、损失权重与切换最小驻留；不得继续使用本轮validation追门。",
        "4. 闭环主线可以继续研究fixed S5下的受力约束和网络保护，但不能把收益归因于K4多步修正。",
        "",
    ]
    (out / "solutions.md").write_text("\n".join(solutions), encoding="utf-8")


def append_work_log(root: Path, out: Path, result: dict[str, Any]) -> None:
    gate = result["gate"]
    files = [
        root / "koopman" / "train_k4.py",
        out / "development" / "k42_freeze.json",
        out / "development" / "k42_results.json",
        out / "development" / "horizon_state.png",
        out / "development" / "horizon_force.png",
    ]
    if not gate["G42_pass"]:
        files.extend([out / "stop.md", out / "solutions.md"])
    lines = [
        "",
        "### W0038｜K4.2 S5固定lift多步修正开发门",
        "",
        "- 前置：修正版G41失败，S4+S5 supervisor因随机丢包下逐包抖振被关闭；K4.2唯一合同为S5-operational。",
        "- 实验：固定K2二次lift和U1-four，比较M1 fixed、M2全量20步refit和M3低秩小范数锚定修正；M3只搜索预注册的3个rank×3个范数上限，随后M2/M3各五seed。",
        f"- validation M1/M2/M3综合NRMSE=`{result['baseline']['validation']['composite']:.8f}/{result['means']['M2-full']['validation']['composite']:.8f}/{result['means']['M3-anchor']['validation']['composite']:.8f}`。",
        f"- dev_test_old M1/M2/M3综合NRMSE=`{result['baseline']['dev_test_old']['composite']:.8f}/{result['means']['M2-full']['dev_test_old']['composite']:.8f}/{result['means']['M3-anchor']['dev_test_old']['composite']:.8f}`。",
        f"- G42=`{gate['G42_pass']}`，决策=`{gate['decision']}`；confirm生成/查看均为false。",
        "- 本阶段没有生成确认集、没有接入MPC或闭环，也没有恢复trainable lift、三专家、bilinear、MF-IK或IRSP。",
        "- SHA256：",
    ]
    lines.extend(f"  - `{path.relative_to(root)}` = `{sha256(path)}`" for path in files)
    lines.append("")
    with (root / "work_log.md").open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main() -> int:
    koopman_dir = Path(__file__).resolve().parent
    root = koopman_dir.parent
    out = koopman_dir / "k4"
    development = out / "development"
    models_dir = out / "models"
    started = time.perf_counter()
    linear = load_module(koopman_dir / "linear.py", "k42_linear")
    config = json.loads((out / "config.json").read_text(encoding="utf-8"))["k42_preregistered_training"]
    freeze_k41 = json.loads((out / "freeze.json").read_text(encoding="utf-8"))
    sensor = json.loads((development / "sensor_stress.json").read_text(encoding="utf-8"))
    if not freeze_k41["G40_pass"]:
        raise RuntimeError("G40 is not passed")
    if sensor["gate"]["selected_contract_for_K4_2"] != "S5-operational":
        raise RuntimeError("K4.2 contract is not frozen to S5-operational")
    confirm_files = list((koopman_dir / "k3").glob("confirm/**/*.npz")) + list(out.glob("confirm/**/*.npz"))
    if confirm_files:
        raise RuntimeError("confirmation trajectories already exist")
    required = [
        koopman_dir / "train_k4.py",
        koopman_dir / "run_k4.py",
        koopman_dir / "k4.md",
        out / "config.json",
        out / "freeze.json",
        development / "sensor_stress.json",
        koopman_dir / "k2" / "data_full" / "manifest.json",
        koopman_dir / "k2" / "linear" / "models" / "S3-U1-lifted.npz",
    ]
    freeze = {
        "stage": "K4.2_before_training",
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python": sys.version,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "contract": "S5-operational",
        "config": config,
        "hashes": {str(path.relative_to(root)): sha256(path) for path in required},
        "confirm_files": 0,
        "confirm_viewed": False,
    }
    write_json(development / "k42_freeze.json", freeze)

    _, rows = linear.load_data(koopman_dir / "k2" / "data_full")
    fixed = load_model(koopman_dir / "k2" / "linear" / "models" / "S3-U1-lifted.npz")
    common_norm = {
        "s2_mean": linear.moments(rows, "s2_four", states=True)[0],
        "s2_std": linear.moments(rows, "s2_four", states=True)[1],
        "force_mean": linear.moments(rows, "force_output", states=True)[0],
        "force_std": linear.moments(rows, "force_output", states=True)[1],
    }
    datasets = {
        split: build_windows(rows, split, fixed, linear, common_norm, int(config["window_stride"]))
        for split in ("train", "validation", "test", "external")
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    baseline_json = json.loads((development / "fixed_recalculation.json").read_text(encoding="utf-8"))["evaluations"]["s5"]
    baseline = {
        label: {
            "h10_20_nrmse": baseline_json[label]["h10_20_nrmse"],
            "horizon_nrmse": baseline_json[label]["horizon_nrmse"],
            "composite": composite(baseline_json[label]["h10_20_nrmse"]),
        }
        for label in ("validation", "dev_test_old", "dev_external_old")
    }

    zero_model = CorrectionModel(fixed, "M3-anchor", 2, 0.005, config["factor_seeds"]).to(device)
    zero_eval = evaluate(zero_model, datasets["validation"], device)
    zero_difference = max(
        abs(zero_eval["h10_20_nrmse"][name] - baseline["validation"]["h10_20_nrmse"][name]) for name in METRICS
    )
    if zero_difference > 2.0e-5:
        raise RuntimeError(f"torch zero-correction audit failed: {zero_difference}")

    search = []
    selected_model: CorrectionModel | None = None
    selected_metadata: dict[str, Any] | None = None
    for rank in config["ranks"]:
        for limit in config["relative_projection_limits"]:
            tag = f"M3-r{rank}-n{limit:.3f}-s74201"
            model, metadata = train_one(
                fixed,
                datasets["train"],
                datasets["validation"],
                config,
                "M3-anchor",
                74201,
                int(rank),
                float(limit),
                device,
                models_dir / f"{tag}.pt",
            )
            search.append(
                {
                    "rank": int(rank),
                    "projection_limit": float(limit),
                    "validation_composite": metadata["best_validation"]["composite"],
                    "best_epoch": metadata["best_epoch"],
                    "checkpoint": str((models_dir / f"{tag}.pt").relative_to(root)),
                }
            )
            if selected_metadata is None or metadata["best_validation"]["composite"] < selected_metadata["best_validation"]["composite"]:
                selected_model = model
                selected_metadata = metadata
    search.sort(key=lambda value: (value["validation_composite"], value["rank"], value["projection_limit"]))
    selected = search[0]
    write_json(development / "k42_search.json", {"selected": selected, "grid": search})

    evaluations: dict[str, dict[str, list[dict[str, Any]]]] = {
        "M2-full": {label: [] for label in ("validation", "dev_test_old", "dev_external_old")},
        "M3-anchor": {label: [] for label in ("validation", "dev_test_old", "dev_external_old")},
    }
    seed_rows: dict[str, list[dict[str, Any]]] = {"M2-full": [], "M3-anchor": []}
    for mode in ("M2-full", "M3-anchor"):
        for seed in config["model_seeds"]:
            if mode == "M3-anchor" and seed == 74201:
                if selected_model is None or selected_metadata is None:
                    raise RuntimeError("selected search model missing")
                model = selected_model
                metadata = selected_metadata
                checkpoint = models_dir / f"M3-r{selected['rank']}-n{selected['projection_limit']:.3f}-s74201.pt"
            else:
                rank = int(selected["rank"]) if mode == "M3-anchor" else None
                limit = float(selected["projection_limit"]) if mode == "M3-anchor" else None
                checkpoint = models_dir / (
                    f"M3-r{rank}-n{limit:.3f}-s{seed}.pt" if mode == "M3-anchor" else f"M2-full-s{seed}.pt"
                )
                model, metadata = train_one(
                    fixed,
                    datasets["train"],
                    datasets["validation"],
                    config,
                    mode,
                    int(seed),
                    rank,
                    limit,
                    device,
                    checkpoint,
                )
            row = {
                "seed": int(seed),
                "best_epoch": metadata["best_epoch"],
                "epochs_run": metadata["epochs_run"],
                "training_seconds": metadata["training_seconds"],
                "checkpoint": str(checkpoint.relative_to(root)),
                "checkpoint_sha256": sha256(checkpoint),
            }
            for split, label in (("validation", "validation"), ("test", "dev_test_old"), ("external", "dev_external_old")):
                result = evaluate(model, datasets[split], device)
                evaluations[mode][label].append(result)
                row[label] = {
                    "h10_20_nrmse": result["h10_20_nrmse"],
                    "composite": result["composite"],
                    "correction": result["correction"],
                    "finite": result["finite"],
                }
            seed_rows[mode].append(row)

    means = {
        mode: {label: mean_evaluation(values) for label, values in split_values.items()}
        for mode, split_values in evaluations.items()
    }
    m3_val = means["M3-anchor"]["validation"]
    m2_val = means["M2-full"]["validation"]
    fixed_val = baseline["validation"]
    improvement = (fixed_val["composite"] - m3_val["composite"]) / fixed_val["composite"]
    direction_count = sum(row["validation"]["composite"] < fixed_val["composite"] for row in seed_rows["M3-anchor"])
    metric_degradation = {
        name: (m3_val["h10_20_nrmse"][name] - fixed_val["h10_20_nrmse"][name])
        / fixed_val["h10_20_nrmse"][name]
        for name in METRICS
    }
    external_degradation = (
        means["M3-anchor"]["dev_external_old"]["composite"] - baseline["dev_external_old"]["composite"]
    ) / baseline["dev_external_old"]["composite"]
    m3_vs_m2_better = m3_val["composite"] <= 0.99 * m2_val["composite"]
    m3_vs_m2_compact_noninferior = (
        m3_val["composite"] <= 1.01 * m2_val["composite"]
        and m3_val["combined_R_mean"] <= 0.5 * m2_val["combined_R_mean"]
        and m3_val["composite_std_across_seeds"] <= m2_val["composite_std_across_seeds"]
    )
    checks = {
        "validation_composite_improvement_at_least_8pct": improvement >= 0.08,
        "at_least_4_of_5_seed_directions": direction_count >= 4,
        "no_validation_primary_metric_worse_than_5pct": all(value <= 0.05 for value in metric_degradation.values()),
        "dev_external_composite_not_worse_than_10pct": external_degradation <= 0.10,
        "all_H20_rollouts_finite": bool(
            all(means[mode][label]["all_finite"] for mode in means for label in means[mode])
        ),
        "anchoring_has_independent_value_vs_M2": bool(m3_vs_m2_better or m3_vs_m2_compact_noninferior),
        "confirm_not_generated_or_viewed": True,
    }
    g42_pass = all(checks.values())
    gate = {
        "improvement_vs_M1": improvement,
        "seed_direction_count": int(direction_count),
        "metric_relative_degradation_vs_M1": metric_degradation,
        "external_relative_degradation_vs_M1": external_degradation,
        "M3_vs_M2_better_by_1pct": m3_vs_m2_better,
        "M3_vs_M2_compact_noninferior": m3_vs_m2_compact_noninferior,
        "checks": checks,
        "G42_pass": g42_pass,
        "decision": "eligible_for_one_time_confirm" if g42_pass else "stop_return_to_M1_fixed_S5",
        "confirm_generated": False,
        "confirm_viewed": False,
    }
    result = {
        "stage": "K4.2",
        "device": str(device),
        "elapsed_seconds": time.perf_counter() - started,
        "zero_correction_max_difference": zero_difference,
        "selected_M3": selected,
        "baseline": baseline,
        "means": means,
        "seeds": seed_rows,
        "gate": gate,
    }
    write_json(development / "k42_results.json", result)
    plot_horizons(
        baseline_json["dev_test_old"],
        means["M2-full"]["dev_test_old"],
        means["M3-anchor"]["dev_test_old"],
        out,
    )
    if not g42_pass:
        stop_documents(out, gate)
    append_work_log(root, out, result)
    print(
        json.dumps(
            {
                "G42_pass": g42_pass,
                "decision": gate["decision"],
                "M1_validation": fixed_val["composite"],
                "M2_validation": m2_val["composite"],
                "M3_validation": m3_val["composite"],
                "confirm_generated": False,
                "elapsed_seconds": result["elapsed_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

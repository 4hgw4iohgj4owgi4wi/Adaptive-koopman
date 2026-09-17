"""Execute K3 trainable-lift gates.  Initial implementation covers G31."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lift import CONTRACTS, SharedLiftedLinear, graph_audit
from transition import connector_quantities


HORIZON = 20


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_rows(root: Path) -> list[dict[str, Any]]:
    k3 = root / "revision_2026" / "koopman" / "k3"
    development = json.loads((k3 / "development_split.json").read_text(encoding="utf-8"))
    data = root / "revision_2026" / "koopman" / "k2" / "data_full"
    rows = []
    for meta in development["trajectories"]:
        path = data / meta["file"]
        if sha256(path) != meta["sha256"]:
            raise RuntimeError(f"data hash mismatch: {path}")
        with np.load(path, allow_pickle=False) as source:
            arrays = {
                key: np.asarray(source[key], dtype=np.float32)
                for key in ("s2_four", "s3_deform", "s4_force_in", "force_output", "u1_four")
            }
        rows.append({"meta": meta, "arrays": arrays})
    return rows


def mean_std(rows: list[dict[str, Any]], key: str, state: bool) -> tuple[np.ndarray, np.ndarray]:
    values = []
    for row in rows:
        if row["meta"]["k3_role"] != "train":
            continue
        array = row["arrays"][key]
        values.append(array[:-1] if state else array)
    joined = np.concatenate(values, axis=0).astype(np.float64)
    mean = joined.mean(axis=0).astype(np.float32)
    std = joined.std(axis=0).astype(np.float32)
    std[std < 1.0e-7] = 1.0
    return mean, std


def normalizers(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for name, key, state in (
        ("s3", "s3_deform", True),
        ("s4", "s4_force_in", True),
        ("s2", "s2_four", True),
        ("force", "force_output", True),
        ("u1", "u1_four", False),
    ):
        result[f"{name}_mean"], result[f"{name}_std"] = mean_std(rows, key, state)
    result["s4aug_mean"] = np.concatenate([result["s4_mean"], np.ones(4, dtype=np.float32), np.zeros(4, dtype=np.float32)])
    result["s4aug_std"] = np.concatenate([result["s4_std"], np.ones(8, dtype=np.float32)])
    train_force = np.concatenate(
        [row["arrays"]["force_output"][:-1] for row in rows if row["meta"]["k3_role"] == "train"], axis=0
    )
    aggregate = aggregate_from_force_np(train_force)
    max_force = np.linalg.norm(train_force[:, :8].reshape(-1, 4, 2), axis=-1).max(axis=1)
    result["aggregate_mean"] = aggregate.mean(axis=0).astype(np.float32)
    result["aggregate_std"] = aggregate.std(axis=0).astype(np.float32)
    result["aggregate_std"][result["aggregate_std"] < 1.0e-7] = 1.0
    result["max_force_mean"] = np.asarray([max_force.mean()], dtype=np.float32)
    result["max_force_std"] = np.asarray([max(max_force.std(), 1.0e-7)], dtype=np.float32)
    return result


def aggregate_from_force_np(force: np.ndarray) -> np.ndarray:
    f = force[..., :8].reshape(*force.shape[:-1], 4, 2)
    net = f.sum(axis=-2)
    anchors = np.asarray([[2.5, 1.0], [2.5, -1.0], [-2.5, 1.0], [-2.5, -1.0]], dtype=np.float32)
    moment = (anchors[:, 0] * f[..., :, 1] - anchors[:, 1] * f[..., :, 0]).sum(axis=-1, keepdims=True)
    return np.concatenate([net, moment, force[..., 8:10]], axis=-1)


def training_windows(rows: list[dict[str, Any]], role: str = "train", stride: int = HORIZON) -> list[tuple[int, int]]:
    indices = []
    for row_index, row in enumerate(rows):
        if row["meta"]["k3_role"] != role:
            continue
        steps = row["arrays"]["u1_four"].shape[0]
        indices.extend((row_index, start) for start in range(0, steps - HORIZON + 1, stride))
    return indices


def batch(
    rows: list[dict[str, Any]],
    indices: list[tuple[int, int]],
    contract: str,
    norm: dict[str, np.ndarray],
    device: torch.device,
    stress: str | None = None,
) -> dict[str, torch.Tensor]:
    key = CONTRACTS[contract].input_key
    prefix = "s4aug" if contract == "S4-force-in" else "s3"
    x, u, state, force = [], [], [], []
    for row_index, start in indices:
        arrays = rows[row_index]["arrays"]
        state_input = arrays[key][start : start + HORIZON + 1]
        if contract == "S4-force-in":
            clean_sensor_meta = np.column_stack(
                [np.ones((state_input.shape[0], 4), dtype=np.float32), np.zeros((state_input.shape[0], 4), dtype=np.float32)]
            )
            state_input = np.concatenate([state_input, clean_sensor_meta], axis=1)
            if stress in {"aoi1", "aoi2", "aoi4"}:
                delay = int(stress[-1])
                stale = arrays[key][max(start - delay, 0), 46:64]
                state_input[0, 46:64] = stale
                state_input[0, 68:72] = delay
            elif stress in {"missing_zero", "missing_hold"}:
                point = int(rows[row_index]["meta"]["trajectory_id"]) % 4
                force_columns = [46 + 2 * point, 47 + 2 * point, 56 + 2 * point, 57 + 2 * point]
                if stress == "missing_zero":
                    state_input[0, force_columns] = 0.0
                else:
                    prior = arrays[key][max(start - 1, 0)]
                    state_input[0, force_columns] = prior[force_columns]
                state_input[0, 64 + point] = 0.0
                state_input[0, 68 + point] = 1.0
        x.append(state_input)
        u.append(arrays["u1_four"][start : start + HORIZON])
        state.append(arrays["s2_four"][start : start + HORIZON + 1])
        force.append(arrays["force_output"][start : start + HORIZON + 1])
    x_np = (np.stack(x) - norm[f"{prefix}_mean"]) / norm[f"{prefix}_std"]
    if contract == "S4-force-in" and stress == "noise_2pct":
        rng = np.random.default_rng(84001)
        x_np[:, 0, 46:64] += rng.normal(0.0, 0.02, size=x_np[:, 0, 46:64].shape)
    if contract == "S4-force-in" and stress == "bias_2pct":
        x_np[:, 0, 46:64] += 0.02
    u_np = (np.stack(u) - norm["u1_mean"]) / norm["u1_std"]
    state_np = (np.stack(state) - norm["s2_mean"]) / norm["s2_std"]
    force_np = (np.stack(force) - norm["force_mean"]) / norm["force_std"]
    return {
        "x": torch.as_tensor(x_np, device=device),
        "u": torch.as_tensor(u_np, device=device),
        "state": torch.as_tensor(state_np, device=device),
        "force": torch.as_tensor(force_np, device=device),
    }


def smoke_loss(model: SharedLiftedLinear, values: dict[str, torch.Tensor], norm: dict[str, np.ndarray]) -> tuple[torch.Tensor, dict[str, float]]:
    x, u, target_state, target_force = values["x"], values["u"], values["state"], values["force"]
    z0 = model.encode(x[:, 0])
    decoded0 = model.decode(z0)
    z_roll, pred_state, pred_force = model.rollout(x[:, 0], u)
    encoded_true = torch.stack([model.encode(x[:, h]) for h in range(1, HORIZON + 1)], dim=1)
    rec = torch.mean((decoded0["state"] - target_state[:, 0]) ** 2) + torch.mean((decoded0["force"] - target_force[:, 0]) ** 2)
    latent = torch.mean((z_roll - encoded_true) ** 2)
    state = torch.mean((pred_state - target_state[:, 1:]) ** 2)
    force = torch.mean((pred_force[..., :8] - target_force[:, 1:, :8]) ** 2)
    q_rate = torch.mean((pred_force[..., 8:] - target_force[:, 1:, 8:]) ** 2)
    q_scale = torch.as_tensor(norm["force_std"][8:10], device=x.device)
    q_mean = torch.as_tensor(norm["force_mean"][8:10], device=x.device)
    f_scale = torch.as_tensor(norm["force_std"], device=x.device)
    f_mean = torch.as_tensor(norm["force_mean"], device=x.device)
    pred_force_physical = pred_force * f_scale + f_mean
    quantities = connector_quantities(pred_force_physical)
    q_head_normalized = (quantities["q_head"] - q_mean) / q_scale
    q_from_force_normalized = (quantities["q_from_force"] - q_mean) / q_scale
    physics = torch.mean((q_head_normalized - q_from_force_normalized) ** 2)
    regularization = torch.mean(model.transition.A**2) + torch.mean(model.transition.B**2)
    total = 0.20 * rec + latent + state + 0.50 * force + 0.50 * q_rate + 0.10 * physics + 1.0e-5 * regularization
    return total, {
        "rec": float(rec.detach()),
        "latent": float(latent.detach()),
        "state": float(state.detach()),
        "force": float(force.detach()),
        "q_rate": float(q_rate.detach()),
        "physics_q_consistency": float(physics.detach()),
        "total": float(total.detach()),
    }


def configured_loss(
    model: SharedLiftedLinear,
    values: dict[str, torch.Tensor],
    norm: dict[str, np.ndarray],
    weights: dict[str, float],
) -> tuple[torch.Tensor, dict[str, float]]:
    x, u, target_state, target_force = values["x"], values["u"], values["state"], values["force"]
    z0 = model.encode(x[:, 0])
    decoded0 = model.decode(z0)
    z_roll, pred_state, pred_force = model.rollout(x[:, 0], u)
    encoded_true = torch.stack([model.encode(x[:, h]) for h in range(1, HORIZON + 1)], dim=1)
    rec = torch.mean((decoded0["state"] - target_state[:, 0]) ** 2) + torch.mean((decoded0["force"] - target_force[:, 0]) ** 2)
    one = torch.mean((z_roll[:, 0] - encoded_true[:, 0]) ** 2) + torch.mean((pred_state[:, 0] - target_state[:, 1]) ** 2)
    rollout = torch.mean((z_roll - encoded_true) ** 2) + torch.mean((pred_state - target_state[:, 1:]) ** 2)
    force = torch.mean((pred_force[..., :8] - target_force[:, 1:, :8]) ** 2)
    q_rate = torch.mean((pred_force[..., 8:] - target_force[:, 1:, 8:]) ** 2)
    f_scale = torch.as_tensor(norm["force_std"], device=x.device)
    f_mean = torch.as_tensor(norm["force_mean"], device=x.device)
    q_scale = torch.as_tensor(norm["force_std"][8:10], device=x.device)
    q_mean = torch.as_tensor(norm["force_mean"][8:10], device=x.device)
    quantities = connector_quantities(pred_force * f_scale + f_mean)
    physics = torch.mean(
        (((quantities["q_head"] - q_mean) / q_scale) - ((quantities["q_from_force"] - q_mean) / q_scale)) ** 2
    )
    regularization = torch.mean(model.transition.A**2) + torch.mean(model.transition.B**2)
    total = (
        weights["lambda_rec"] * rec
        + weights["lambda_1"] * one
        + weights["lambda_H"] * rollout
        + weights["lambda_F"] * force
        + weights["lambda_Q"] * q_rate
        + weights["lambda_P"] * physics
        + weights["lambda_R"] * regularization
    )
    return total, {
        "rec": float(rec.detach()),
        "one": float(one.detach()),
        "rollout": float(rollout.detach()),
        "force": float(force.detach()),
        "q_rate": float(q_rate.detach()),
        "physics": float(physics.detach()),
        "total": float(total.detach()),
    }


def evaluate_model(
    model: SharedLiftedLinear,
    rows: list[dict[str, Any]],
    role: str,
    contract: str,
    norm: dict[str, np.ndarray],
    device: torch.device,
    stress: str | None = None,
) -> dict[str, Any]:
    metrics = ("state", "yaw", "connector", "opening", "force_rate", "aggregate", "max_force")
    horizon_sq = {name: np.zeros(HORIZON, dtype=float) for name in metrics}
    horizon_count = {name: np.zeros(HORIZON, dtype=int) for name in metrics}
    per_trajectory: dict[str, dict[str, Any]] = {}
    model.eval()
    with torch.no_grad():
        for row_index, row in enumerate(rows):
            if row["meta"]["k3_role"] != role:
                continue
            steps = row["arrays"]["u1_four"].shape[0]
            indices = [(row_index, start) for start in range(0, steps - HORIZON + 1, HORIZON)]
            if not indices:
                continue
            values = batch(rows, indices, contract, norm, device, stress=stress)
            _, pred_state, pred_force = model.rollout(values["x"][:, 0], values["u"])
            target_state, target_force = values["state"][:, 1:], values["force"][:, 1:]
            pred_state_np = pred_state.cpu().numpy()
            pred_force_np = pred_force.cpu().numpy()
            target_state_np = target_state.cpu().numpy()
            target_force_np = target_force.cpu().numpy()
            yaw_indices = np.asarray([5, 11, 17, 23, 29])
            pred_force_physical = pred_force_np * norm["force_std"] + norm["force_mean"]
            target_force_physical = target_force_np * norm["force_std"] + norm["force_mean"]
            pred_aggregate = (aggregate_from_force_np(pred_force_physical) - norm["aggregate_mean"]) / norm["aggregate_std"]
            target_aggregate = (aggregate_from_force_np(target_force_physical) - norm["aggregate_mean"]) / norm["aggregate_std"]
            pred_max = (np.linalg.norm(pred_force_physical[..., :8].reshape(*pred_force_physical.shape[:-1], 4, 2), axis=-1).max(axis=-1) - norm["max_force_mean"][0]) / norm["max_force_std"][0]
            target_max = (np.linalg.norm(target_force_physical[..., :8].reshape(*target_force_physical.shape[:-1], 4, 2), axis=-1).max(axis=-1) - norm["max_force_mean"][0]) / norm["max_force_std"][0]
            errors = {
                "state": np.mean((pred_state_np - target_state_np) ** 2, axis=-1),
                "yaw": np.mean((pred_state_np[..., yaw_indices] - target_state_np[..., yaw_indices]) ** 2, axis=-1),
                "connector": np.mean((pred_force_np[..., :8] - target_force_np[..., :8]) ** 2, axis=-1),
                "opening": np.mean((pred_force_np[..., 8:10] - target_force_np[..., 8:10]) ** 2, axis=-1),
                "force_rate": np.mean((pred_force_np[..., 10:18] - target_force_np[..., 10:18]) ** 2, axis=-1),
                "aggregate": np.mean((pred_aggregate - target_aggregate) ** 2, axis=-1),
                "max_force": (pred_max - target_max) ** 2,
            }
            item: dict[str, Any] = {"scenario": row["meta"]["scenario"]}
            for name, values_sq in errors.items():
                horizon_sq[name] += values_sq.sum(axis=0)
                horizon_count[name] += values_sq.shape[0]
                item[name] = float(math.sqrt(np.mean(values_sq[:, 9:])))
            key = f"{row['meta']['scenario']}|{row['meta']['trajectory_id']}"
            per_trajectory[key] = item
    horizon_nrmse = {
        name: np.sqrt(np.divide(horizon_sq[name], horizon_count[name], out=np.full(HORIZON, np.nan), where=horizon_count[name] > 0))
        for name in metrics
    }
    h10 = {name: float(math.sqrt(np.sum(horizon_sq[name][9:]) / np.sum(horizon_count[name][9:]))) for name in metrics}
    return {
        "role": role,
        "stress": stress or "clean",
        "finite": bool(all(np.all(np.isfinite(value)) for value in horizon_nrmse.values())),
        "horizon_nrmse": {name: value.tolist() for name, value in horizon_nrmse.items()},
        "h10_20_nrmse": h10,
        "per_trajectory_h10_20": per_trajectory,
    }


def validation_score(result: dict[str, Any]) -> float:
    values = result["h10_20_nrmse"]
    return float(np.mean([values["state"], values["connector"], values["opening"]]))


def train_one(
    root: Path,
    rows: list[dict[str, Any]],
    norm: dict[str, np.ndarray],
    contract: str,
    seed: int,
    learning_rate: float,
    weights: dict[str, float],
    label: str,
    device: torch.device,
) -> tuple[SharedLiftedLinear, dict[str, Any]]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = SharedLiftedLinear(contract).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1.0e-6)
    indices = training_windows(rows, role="train")
    rng = np.random.default_rng(seed)
    best_score = math.inf
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    patience = 0
    history = []
    started = time.perf_counter()
    for epoch in range(1, 61):
        model.train()
        order = rng.permutation(len(indices))
        epoch_losses = []
        for offset in range(0, len(order), 256):
            selected = [indices[index] for index in order[offset : offset + 256]]
            values = batch(rows, selected, contract, norm, device)
            optimizer.zero_grad(set_to_none=True)
            loss, parts = configured_loss(model, values, norm, weights)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"nonfinite training loss {contract}/{seed}/{label}/epoch{epoch}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            epoch_losses.append(parts["total"])
        validation = evaluate_model(model, rows, "validation", contract, norm, device)
        score = validation_score(validation)
        history.append({"epoch": epoch, "train_loss": float(np.mean(epoch_losses)), "validation_score": score})
        if score < best_score - 1.0e-5:
            best_score = score
            best_epoch = epoch
            best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
        if epoch == 1 or epoch % 5 == 0:
            print(f"{label} {contract} seed={seed} epoch={epoch} train={np.mean(epoch_losses):.5f} val={score:.5f} best={best_score:.5f}", flush=True)
        if patience >= 10:
            break
    if best_state is None:
        raise RuntimeError("no finite best checkpoint")
    model.load_state_dict(best_state)
    elapsed = time.perf_counter() - started
    checkpoint = root / "revision_2026" / "koopman" / "k3" / "models" / f"{label}_{contract}_seed{seed}.pt"
    torch.save(
        {
            "model": model.state_dict(),
            "contract": contract,
            "seed": seed,
            "learning_rate": learning_rate,
            "weights": weights,
            "best_epoch": best_epoch,
            "best_validation_score": best_score,
        },
        checkpoint,
    )
    record = {
        "contract": contract,
        "seed": seed,
        "learning_rate": learning_rate,
        "weights": weights,
        "best_epoch": best_epoch,
        "best_validation_score": best_score,
        "epochs_ran": len(history),
        "train_seconds": elapsed,
        "history": history,
        "checkpoint": str(checkpoint.relative_to(root)).replace("\\", "/"),
        "checkpoint_sha256": sha256(checkpoint),
    }
    return model, record


def average_eval(seed_results: list[dict[str, Any]], role: str) -> dict[str, Any]:
    metrics = tuple(seed_results[0][role]["h10_20_nrmse"])
    horizons = {
        metric: np.mean([np.asarray(row[role]["horizon_nrmse"][metric]) for row in seed_results], axis=0).tolist()
        for metric in metrics
    }
    h10 = {metric: float(np.mean([row[role]["h10_20_nrmse"][metric] for row in seed_results])) for metric in metrics}
    keys = sorted(seed_results[0][role]["per_trajectory_h10_20"])
    per_trajectory = {}
    for key in keys:
        per_trajectory[key] = {
            metric: float(np.mean([row[role]["per_trajectory_h10_20"][key][metric] for row in seed_results]))
            for metric in metrics
        }
        per_trajectory[key]["scenario"] = seed_results[0][role]["per_trajectory_h10_20"][key]["scenario"]
    return {"horizon_nrmse": horizons, "h10_20_nrmse": h10, "per_trajectory_h10_20": per_trajectory}


def paired_ci(candidate: dict[str, Any], baseline: dict[str, Any], metric: str, seed: int) -> dict[str, Any]:
    keys = sorted(set(candidate["per_trajectory_h10_20"]) & set(baseline["per_trajectory_h10_20"]))
    delta = np.asarray(
        [candidate["per_trajectory_h10_20"][key][metric] - baseline["per_trajectory_h10_20"][key][metric] for key in keys]
    )
    rng = np.random.default_rng(seed)
    boot = delta[rng.integers(0, len(delta), size=(2000, len(delta)))].mean(axis=1)
    return {
        "definition": "candidate minus baseline; negative favors candidate",
        "n_trajectories": len(keys),
        "mean_delta": float(delta.mean()),
        "ci95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
    }


def plot_a(path: Path, averaged: dict[str, dict[str, Any]], metric: str) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for name, result in averaged.items():
        ax.plot(np.arange(1, HORIZON + 1), result["horizon_nrmse"][metric], label=name)
    ax.set(xlabel="Teacher-free rollout horizon", ylabel=f"{metric} NRMSE", title=f"K3 A-model development: {metric}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_train_a(root: Path) -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    k3 = root / "revision_2026" / "koopman" / "k3"
    config = json.loads((k3 / "config.json").read_text(encoding="utf-8"))
    rows = load_rows(root)
    norm = normalizers(rows)
    np.savez_compressed(k3 / "development" / "normalizers.npz", **norm)
    seeds = config["training"]["model_seeds"]
    search: dict[str, list[dict[str, Any]]] = {contract: [] for contract in CONTRACTS}
    selected: dict[str, dict[str, Any]] = {}
    selected_seed1_models: dict[str, SharedLiftedLinear] = {}
    selected_seed1_records: dict[str, dict[str, Any]] = {}
    for contract in CONTRACTS:
        candidates = []
        candidate_index = 0
        for learning_rate in config["training"]["learning_rate_grid"]:
            for weights in config["training"]["loss_grid"]:
                candidate_index += 1
                label = f"search{candidate_index}"
                model, record = train_one(root, rows, norm, contract, seeds[0], learning_rate, weights, label, device)
                record["search_index"] = candidate_index
                search[contract].append(record)
                candidates.append((record["best_validation_score"], learning_rate, weights, model, record))
        candidates.sort(key=lambda item: item[0])
        score, learning_rate, weights, model, record = candidates[0]
        selected[contract] = {"validation_score": score, "learning_rate": learning_rate, "weights": weights, "search_index": record["search_index"]}
        selected_seed1_models[contract] = model
        selected_seed1_records[contract] = record
    write_json(k3 / "development" / "search_A.json", {"search": search, "selected": selected})

    all_results: dict[str, list[dict[str, Any]]] = {contract: [] for contract in CONTRACTS}
    for contract in CONTRACTS:
        model = selected_seed1_models[contract]
        record = dict(selected_seed1_records[contract])
        final_checkpoint = k3 / "models" / f"A_{contract}_seed{seeds[0]}.pt"
        torch.save(torch.load(root / record["checkpoint"], map_location="cpu", weights_only=False), final_checkpoint)
        record["checkpoint"] = str(final_checkpoint.relative_to(root)).replace("\\", "/")
        record["checkpoint_sha256"] = sha256(final_checkpoint)
        record["validation"] = evaluate_model(model, rows, "validation", contract, norm, device)
        record["dev_test_old"] = evaluate_model(model, rows, "dev_test_old", contract, norm, device)
        record["dev_external_old"] = evaluate_model(model, rows, "dev_external_old", contract, norm, device)
        all_results[contract].append(record)
        for seed in seeds[1:]:
            model, record = train_one(root, rows, norm, contract, seed, selected[contract]["learning_rate"], selected[contract]["weights"], "A", device)
            record["validation"] = evaluate_model(model, rows, "validation", contract, norm, device)
            record["dev_test_old"] = evaluate_model(model, rows, "dev_test_old", contract, norm, device)
            record["dev_external_old"] = evaluate_model(model, rows, "dev_external_old", contract, norm, device)
            all_results[contract].append(record)
    averaged = {
        contract: {
            "dev_test_old": average_eval(seed_rows, "dev_test_old"),
            "dev_external_old": average_eval(seed_rows, "dev_external_old"),
            "validation": average_eval(seed_rows, "validation"),
        }
        for contract, seed_rows in all_results.items()
    }
    for metric in ("state", "connector", "opening"):
        plot_a(k3 / "development" / f"A_{metric}.png", {name: value["dev_test_old"] for name, value in averaged.items()}, metric)

    # S4 sensor-assumption stress is evaluated for every seed, even if S5 wins.
    stress_names = ("noise_2pct", "bias_2pct", "aoi1", "aoi2", "aoi4", "missing_zero", "missing_hold")
    stress: dict[str, Any] = {}
    for stress_name in stress_names:
        evaluations = []
        for record in all_results["S4-force-in"]:
            checkpoint = torch.load(root / record["checkpoint"], map_location=device, weights_only=False)
            model = SharedLiftedLinear("S4-force-in").to(device)
            model.load_state_dict(checkpoint["model"])
            evaluations.append({"dev_test_old": evaluate_model(model, rows, "dev_test_old", "S4-force-in", norm, device, stress=stress_name)})
        stress[stress_name] = average_eval(evaluations, "dev_test_old")

    primary = ("state", "connector", "opening")
    s4, s5 = averaged["S4-force-in"]["dev_test_old"], averaged["S5-force-out"]["dev_test_old"]
    comparisons = {
        metric: paired_ci(s4, s5, metric, 85000 + index) for index, metric in enumerate(primary)
    }
    relative_s4_improvement = {
        metric: (s5["h10_20_nrmse"][metric] - s4["h10_20_nrmse"][metric]) / s5["h10_20_nrmse"][metric]
        for metric in primary
    }
    clean_s4 = s4["h10_20_nrmse"]
    stress_degradation = {
        name: {
            metric: (value["h10_20_nrmse"][metric] - clean_s4[metric]) / clean_s4[metric] for metric in primary
        }
        for name, value in stress.items()
    }
    stress_pass = bool(
        all(max(values.values()) <= (0.10 if name in {"aoi4", "missing_hold"} else 0.05) for name, values in stress_degradation.items() if name != "missing_zero")
        and stress["missing_hold"]["h10_20_nrmse"]["connector"] <= stress["missing_zero"]["h10_20_nrmse"]["connector"]
    )

    linear_results = json.loads((root / "revision_2026" / "koopman" / "k2" / "linear" / "results.json").read_text(encoding="utf-8"))
    fixed = {
        "S4-force-in": linear_results["k22"]["S4-force-in"]["test"]["h10_20_nrmse"],
        "S5-force-out": linear_results["k22"]["S3-deform"]["test"]["h10_20_nrmse"],
    }
    trained_composite = {contract: float(np.mean([averaged[contract]["dev_test_old"]["h10_20_nrmse"][metric] for metric in primary])) for contract in CONTRACTS}
    fixed_composite = {contract: float(np.mean([fixed[contract][metric] for metric in primary])) for contract in CONTRACTS}
    improves_fixed = {contract: trained_composite[contract] < fixed_composite[contract] for contract in CONTRACTS}
    s4_selection = bool(
        any(relative_s4_improvement[metric] >= 0.10 and comparisons[metric]["ci95"][1] < 0.0 for metric in primary)
        and all(relative_s4_improvement[metric] >= -0.05 for metric in primary)
        and stress_pass
    )
    s5_no_worse = all(
        averaged["S5-force-out"]["dev_test_old"]["h10_20_nrmse"][metric]
        <= 1.05 * averaged["S4-force-in"]["dev_test_old"]["h10_20_nrmse"][metric]
        for metric in primary
    )
    external_composite = {
        contract: float(np.mean([averaged[contract]["dev_external_old"]["h10_20_nrmse"][metric] for metric in primary]))
        for contract in CONTRACTS
    }
    s5_selection = bool(s5_no_worse and external_composite["S5-force-out"] < external_composite["S4-force-in"])
    selected_contract = "S4-force-in" if s4_selection else ("S5-force-out" if s5_selection else None)
    both_fail_fixed = not any(improves_fixed.values())
    passed = bool(not both_fail_fixed and selected_contract is not None)
    result = {
        "stage": "K3.2_A_and_C",
        "gate": "G32",
        "passed": passed,
        "selected_hyperparameters": selected,
        "seed_results": all_results,
        "averaged": averaged,
        "S4_sensor_stress": stress,
        "S4_sensor_stress_relative_degradation": stress_degradation,
        "S4_sensor_stress_pass": stress_pass,
        "S4_minus_S5_paired": comparisons,
        "S4_relative_improvement_over_S5": relative_s4_improvement,
        "fixed_baselines": fixed,
        "trainable_composite": trained_composite,
        "fixed_composite": fixed_composite,
        "improves_corresponding_fixed": improves_fixed,
        "external_composite": external_composite,
        "selection_checks": {
            "S4_rule_pass": s4_selection,
            "S5_not_worse_than_S4_by_5pct": s5_no_worse,
            "S5_external_better": external_composite["S5-force-out"] < external_composite["S4-force-in"],
            "S5_rule_pass": s5_selection,
            "both_trainable_fail_fixed": both_fail_fixed,
        },
        "selected_contract": selected_contract,
        "decision": "continue_to_B" if passed else ("return_to_old_fixed_linear" if both_fail_fixed else "no_state_contract_passed"),
    }
    write_json(k3 / "development" / "A_results.json", result)
    if not passed:
        lines = [
            "# K3停止：G32状态合同门失败",
            "",
            f"- trainable/fixed composite：`{trained_composite}` / `{fixed_composite}`。",
            f"- improves fixed：`{improves_fixed}`。",
            f"- S4相对S5：`{relative_s4_improvement}`；逐轨迹CI见`development/A_results.json`。",
            f"- S4传感压力门：`{stress_pass}`。",
            f"- S5不劣5%：`{s5_no_worse}`；S5 external更好：`{external_composite['S5-force-out'] < external_composite['S4-force-in']}`。",
            "",
            "按k3.md停止：不训练方案B，不生成confirm，不接入闭环。若两种可训练lift均不优于fixed linear，论文回到旧fixed方案A。",
        ]
        (k3 / "stop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def run_g31(root: Path) -> dict[str, Any]:
    torch.manual_seed(73101)
    np.random.seed(73101)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rows = load_rows(root)
    norm = normalizers(rows)
    k3 = root / "revision_2026" / "koopman" / "k3"
    np.savez_compressed(k3 / "development" / "normalizers.npz", **norm)
    indices = training_windows(rows)[:256]
    models: dict[str, Any] = {}
    counts = {}
    finite = True
    conservation_peak = 0.0
    for contract in CONTRACTS:
        model = SharedLiftedLinear(contract).to(device)
        counts[contract] = model.trainable_parameter_count()
        values = batch(rows, indices, contract, norm, device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3.0e-4, weight_decay=1.0e-6)
        before, before_parts = smoke_loss(model, values, norm)
        for _ in range(3):
            optimizer.zero_grad(set_to_none=True)
            loss, _ = smoke_loss(model, values, norm)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
        after, after_parts = smoke_loss(model, values, norm)
        with torch.no_grad():
            z = model.encode(values["x"][:, 0])
            decoded = model.decode(z)
            reconstruction_peak = float(torch.max(torch.abs(decoded["state"] - values["state"][:, 0])))
            force_physical = decoded["force"] * torch.as_tensor(norm["force_std"], device=device) + torch.as_tensor(norm["force_mean"], device=device)
            conservation_peak = max(conservation_peak, float(torch.max(torch.abs(connector_quantities(force_physical)["action_reaction_residual"]))))
            z_roll, state_roll, force_roll = model.rollout(values["x"][:, 0], values["u"])
            model_finite = all(torch.all(torch.isfinite(item)).item() for item in (z_roll, state_roll, force_roll, after))
        audit = graph_audit(model)
        checkpoint = k3 / "models" / f"g31_{contract}.pt"
        torch.save({"model": model.state_dict(), "contract": contract, "normalizer_sha256": sha256(k3 / "development" / "normalizers.npz")}, checkpoint)
        models[contract] = {
            "parameter_count": counts[contract],
            "before": before_parts,
            "after_three_updates": after_parts,
            "finite": model_finite,
            "state_reconstruction_peak_normalized": reconstruction_peak,
            "graph_audit": audit,
            "checkpoint": str(checkpoint.relative_to(root)).replace("\\", "/"),
            "checkpoint_sha256": sha256(checkpoint),
        }
        finite = finite and model_finite
    parameter_relative_gap = abs(counts["S4-force-in"] - counts["S5-force-out"]) / max(counts.values())
    s5_clean = bool(models["S5-force-out"]["graph_audit"]["s5_no_force_input_path"])
    state_reconstruction_ok = all(item["state_reconstruction_peak_normalized"] <= 1.0e-6 for item in models.values())
    passed = bool(finite and parameter_relative_gap <= 0.02 and s5_clean and state_reconstruction_ok and conservation_peak <= 1.0e-12)
    result = {
        "gate": "G31",
        "passed": passed,
        "device": str(device),
        "models": models,
        "parameter_relative_gap": parameter_relative_gap,
        "action_reaction_residual_peak_n": conservation_peak,
        "checks": {
            "finite_20_step_after_backprop": finite,
            "parameter_count_within_2_percent": parameter_relative_gap <= 0.02,
            "s5_no_force_input_path": s5_clean,
            "exact_physical_state_passthrough": state_reconstruction_ok,
            "action_reaction_by_construction": conservation_peak <= 1.0e-12,
        },
        "boundary": "G31 is an implementation/numerical gate, not evidence that the trainable lift improves prediction.",
    }
    write_json(k3 / "g31.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", choices=("g31", "train-a"), required=True)
    args = parser.parse_args()
    result = run_g31(args.root.resolve()) if args.stage == "g31" else run_train_a(args.root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if not result["passed"] and args.stage == "g31":
        stop = args.root.resolve() / "revision_2026" / "koopman" / "k3" / "stop.md"
        stop.write_text("# K3停止\n\nG31可训练lift数值门失败；见`g31.json`。不得进入A-S4/A-S5训练。\n", encoding="utf-8")
        raise SystemExit(2)


if __name__ == "__main__":
    main()

"""GDM-RK training: one-step warm start then multi-horizon training with CVaR
tail and Koopman closure, on train-family folds with a family-balanced batch
generator.  A0/B0/b0 stay frozen buffers; only encoder/E/F/G/c are trained."""

from __future__ import annotations

import time
from pathlib import Path

import torch

from data_contract import FrozenSequenceDataset
from lift import TriangularResidualKoopman
from losses import (
    cvar_tail,
    group_rmse,
    group_slices_from_protocol,
    koopman_closure,
    per_sample_group_error,
)


def _samples_for_window_batch(dataset: FrozenSequenceDataset, indices: list[int], device) -> dict:
    samples = [dataset.get_sample(index) for index in indices]
    return {
        "x0": torch.stack([sample["x0"] for sample in samples]).to(device),
        "u_seq": torch.stack([sample["u_seq"] for sample in samples]).to(device),
        "x_target": torch.stack([sample["x_target"] for sample in samples]).to(device),
    }


def _step_loss(
    model: TriangularResidualKoopman,
    batch: dict,
    group_weights: dict,
    horizons: tuple,
    inv_lambda_scale: float,
    tail_lambda_scale: float,
    multi_weights: dict,
) -> dict:
    rollout = model.rollout(batch["x0"], batch["u_seq"], horizons, return_eta=True)
    predictions = rollout["xhat"]  # (B, H, 47)
    targets = batch["x_target"][:, 1:]  # (B, H, 47)
    per_horizon = {}
    for horizon in horizons:
        per_horizon[horizon] = group_rmse(
            predictions[:, horizon - 1], targets[:, horizon - 1], group_weights
        )
    multi = sum(float(multi_weights[str(horizon)]) * per_horizon[horizon] for horizon in horizons)
    per_sample20 = per_sample_group_error(predictions[:, 19], targets[:, 19], group_weights)
    tail = cvar_tail(per_sample20, quantile=0.90, min_samples=4)
    eta_prop = rollout["eta"][:, 1:]  # (B, H, r)
    closure_terms = []
    for horizon in horizons:
        # closure against the stop-gradient encoding of the true future state
        # with the control u_{k+h} that starts the next interval
        eta_enc_h = model.encoder(
            batch["x_target"][:, horizon], batch["u_seq"][:, horizon]
        )
        closure_terms.append(koopman_closure(eta_prop[:, horizon - 1], eta_enc_h))
    inv = sum(closure_terms) / len(closure_terms)
    e_decay = 1e-4 * torch.sum(model.E**2)
    theta_decay = 1e-5 * sum(torch.sum(param**2) for param in model.parameters())
    total = (
        multi
        + float(tail_lambda_scale) * tail
        + float(inv_lambda_scale) * inv
        + e_decay
        + theta_decay
    )
    return {
        "total": total,
        "multi": multi,
        "tail": tail,
        "inv": inv,
        "per_horizon": per_horizon,
    }


def train_warm_start(
    model: TriangularResidualKoopman,
    dataset: FrozenSequenceDataset,
    protocol: dict,
    *,
    device,
    steps: int = 2000,
    lr: float = 1e-3,
    batch_windows: int = 256,
    grad_clip: float = 1.0,
    seed: int = 990100,
    log_every: int = 250,
    checkpoint_path: Path | None = None,
    trace: list | None = None,
) -> dict:
    """One-step warm start: only encoder/E/G/F/c are trained; S0 buffers frozen."""
    group_weights = group_slices_from_protocol(protocol)
    trainable = [param for param in model.parameters() if param.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=float(lr))
    model.to(device)
    model.train()
    step = 0
    curves = []
    started = time.perf_counter()
    while step < int(steps):
        for indices in dataset.family_balanced_batches(batch_windows, seed=seed + step):
            batch = _samples_for_window_batch(dataset, indices, device)
            optimizer.zero_grad(set_to_none=True)
            rollout = model.rollout(batch["x0"], batch["u_seq"][:, :1], (1,))
            loss = group_rmse(rollout["xhat"][:, 0], batch["x_target"][:, 1], group_weights)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite warm-start loss at step {step}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, float(grad_clip))
            optimizer.step()
            step += 1
            if step % int(log_every) == 0 or step == int(steps):
                entry = {"step": step, "loss": float(loss.item())}
                curves.append(entry)
                if trace is not None:
                    trace.append(entry)
            if step >= int(steps):
                break
    if checkpoint_path is not None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": model.state_dict(),
                "step": step,
                "kind": "warm",
                "loss_curve": curves,
            },
            checkpoint_path,
        )
    return {"step": step, "wall_s": time.perf_counter() - started, "curve": curves}


def train_multihorizon(
    model: TriangularResidualKoopman,
    dataset: FrozenSequenceDataset,
    protocol: dict,
    loss_scale: dict,
    *,
    device,
    steps: int = 15000,
    lr: float = 3e-4,
    batch_windows: int = 256,
    grad_clip: float = 1.0,
    early_stop_patience: int = 2000,
    checkpoint_every: int = 1000,
    curve_every: int = 250,
    seed: int = 990100,
    checkpoint_path: Path | None = None,
    resume: Path | None = None,
    trace: list | None = None,
    validation_batch: dict | None = None,
    use_cvar: bool = True,
) -> dict:
    """Multi-horizon training with CVaR tail and closure; early stopping on the
    train-CV fold objective (a held-out fold, never the validation split).

    use_cvar=False implements the A2 ablation (multi-horizon without the CVaR
    tail term)."""
    group_weights = group_slices_from_protocol(protocol)
    horizons = tuple(int(h) for h in protocol["loss"]["multi_weights"])
    multi_weights = {
        str(h): float(protocol["loss"]["multi_weights"][str(h)]) for h in horizons
    }
    tail_median = float(loss_scale.get("tail_median") or 1.0)
    inv_median = float(loss_scale.get("closure_median") or 1.0)
    inv_lambda_scale = float(protocol["loss"]["inv_lambda"]) / max(inv_median, 1e-12)
    tail_lambda_scale = (
        0.0 if not use_cvar
        else float(protocol["loss"]["tail_lambda"]) / max(tail_median, 1e-12)
    )

    trainable = [param for param in model.parameters() if param.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=float(lr))
    model.to(device)
    model.train()
    start_step = 0
    curves: list[dict] = []
    if resume is not None and resume.exists():
        state = torch.load(resume, map_location=device)
        model.load_state_dict(state["model_state"])
        start_step = int(state.get("step", 0))
        optimizer.load_state_dict(state["optimizer_state"])
        curves = list(state.get("curve", []))
        print(f"resumed multihorizon from step {start_step}")
    step = start_step
    best_fold_value = float("inf")
    patience_counter = 0
    started = time.perf_counter()
    while step < int(steps):
        for indices in dataset.family_balanced_batches(batch_windows, seed=seed + step):
            batch = _samples_for_window_batch(dataset, indices, device)
            optimizer.zero_grad(set_to_none=True)
            losses = _step_loss(
                model, batch, group_weights, horizons,
                inv_lambda_scale, tail_lambda_scale, multi_weights,
            )
            if not torch.isfinite(losses["total"]):
                raise FloatingPointError(f"non-finite multi-horizon loss at step {step}")
            losses["total"].backward()
            torch.nn.utils.clip_grad_norm_(trainable, float(grad_clip))
            optimizer.step()
            step += 1
            if step % int(curve_every) == 0:
                entry = {
                    "step": step,
                    "total": float(losses["total"].item()),
                    "multi": float(losses["multi"].item()),
                    "tail": float(losses["tail"].item()),
                    "inv": float(losses["inv"].item()),
                    **{f"h{horizon}": float(losses["per_horizon"][horizon].item()) for horizon in horizons},
                }
                curves.append(entry)
                if trace is not None:
                    trace.append(entry)
                if validation_batch is not None:
                    with torch.no_grad():
                        val_losses = _step_loss(
                            model, validation_batch, group_weights, horizons,
                            inv_lambda_scale, tail_lambda_scale, multi_weights,
                        )
                    value = float(val_losses["multi"].item())
                    if value < best_fold_value - 1e-9:
                        best_fold_value = value
                        patience_counter = 0
                    else:
                        patience_counter += int(curve_every)
                    if patience_counter >= int(early_stop_patience):
                        _save_checkpoint(checkpoint_path, model, optimizer, step, curves, "multihorizon")
                        return {
                            "step": step,
                            "wall_s": time.perf_counter() - started,
                            "curve": curves,
                            "early_stopped": True,
                            "best_fold_value": best_fold_value,
                        }
            if step % int(checkpoint_every) == 0 and checkpoint_path is not None:
                _save_checkpoint(checkpoint_path, model, optimizer, step, curves, "multihorizon")
            if step >= int(steps):
                break
    if checkpoint_path is not None:
        _save_checkpoint(checkpoint_path, model, optimizer, step, curves, "multihorizon")
    return {
        "step": step,
        "wall_s": time.perf_counter() - started,
        "curve": curves,
        "early_stopped": False,
        "best_fold_value": best_fold_value,
    }


def _save_checkpoint(path, model, optimizer, step, curve, kind) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "step": int(step),
            "kind": kind,
            "curve": curve,
        },
        path,
    )

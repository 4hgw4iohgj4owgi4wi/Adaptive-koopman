"""v3r unified training: shared warm + equal-budget second phases with
best/last checkpointing, exact resume, full-fold Q_CV monitoring and
structured loss accounting (E01/E02/E03/E04/E10/E11/E13).

Loss specs (frozen in protocol):
  warm/ONE16 : one-step group-weighted ell_1 + regularisation
  MH16       : L_MH + regularisation
  MHC16      : L_MH + 0.10 * closure_tilde + regularisation
  BCV16      : MHC + 0.25 * batch_tail_tilde + regularisation

Regularisation is recorded separately: 1e-4*||E||^2 + 1e-5*||theta||^2.
All variants of one fold start from the SAME warm checkpoint and consume the
SAME precomputed phase batch stream (position-indexed), so resume is exact by
construction and ONE/MH/MHC/BCV differ only in the second-phase objective.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from checkpoint import EarlyStopState, save_checkpoint, restore_rng
from data_contract import FrozenSequenceDataset
from lift import TriangularResidualKoopman
from losses import cvar_tail, group_rmse, group_slices_from_protocol, koopman_closure, per_sample_group_error


def build_batch_stream(
    dataset: FrozenSequenceDataset,
    *,
    batches: int,
    batch_windows: int,
    seed: int,
    out_path: Path | None = None,
) -> list[list[int]]:
    from sampler import FamilyBalancedSampler

    records = []
    for index in range(len(dataset)):
        trajectory_index, start = dataset._sample_index[index]
        records.append(
            {"index": index, "base_family_id": dataset._trajectories[trajectory_index]["entry"]["base_family_id"]}
        )
    sampler = FamilyBalancedSampler(records, batch_windows=batch_windows, families_per_batch=32, seed=seed)
    return sampler.precompute(int(batches), out_path)


def _batch_tensors(dataset: FrozenSequenceDataset, batch_indices: list[int], device) -> dict:
    samples = [dataset.get_sample(index) for index in batch_indices]
    return {
        "x0": torch.stack([sample["x0"] for sample in samples]).to(device),
        "u_seq": torch.stack([sample["u_seq"] for sample in samples]).to(device),
        "x_target": torch.stack([sample["x_target"] for sample in samples]).to(device),
        "metadata": samples,
    }


def step_loss(
    model: TriangularResidualKoopman,
    batch: dict,
    protocol: dict,
    loss_spec: str,
    group_weights: dict,
    closure_scale: float | None,
    tail_scale: float | None,
) -> dict:
    """One batch forward/objective for a loss spec; returns raw/weighted/share
    components plus rollout artifacts (used for audit and tail membership)."""
    horizons = tuple(int(h) for h in protocol["loss"]["multi_weights"])
    multi_weights = {int(h): float(protocol["loss"]["multi_weights"][str(h)]) for h in horizons}
    one_step_spec = loss_spec in {"warm", "one_step"}
    rollout_horizons = (1,) if one_step_spec else horizons
    rollout = model.rollout(batch["x0"], batch["u_seq"][:, : max(rollout_horizons)], rollout_horizons, return_eta=True)
    predictions = rollout["xhat"]  # (B, H, 47)
    targets = batch["x_target"][:, 1:]  # (B, H, 47)
    if one_step_spec:
        per_horizon = {1: group_rmse(predictions[:, 0], targets[:, 0], group_weights)}
    else:
        per_horizon = {
            horizon: group_rmse(predictions[:, horizon - 1], targets[:, horizon - 1], group_weights)
            for horizon in horizons
        }
    if one_step_spec:
        main = per_horizon[1]
        main_name = "ell_1"
        l_mh = None
    else:
        l_mh = sum(float(multi_weights[h]) * per_horizon[h] for h in horizons)
        main = l_mh
        main_name = "l_mh"
    e_decay_raw = float(protocol["loss"]["e_weight_decay"]) * torch.sum(model.E**2)
    theta_decay_raw = float(protocol["loss"]["theta_weight_decay"]) * sum(
        torch.sum(param**2) for param in model.parameters()
    )
    regularization = e_decay_raw + theta_decay_raw

    closure_raw = None
    tail_raw = None
    tail_indices = None
    per_sample20 = None
    if not one_step_spec:
        per_sample20 = per_sample_group_error(predictions[:, 19], targets[:, 19], group_weights)

    if loss_spec in {"MHC", "BCV"}:
        eta_prop = rollout["eta"][:, 1:]
        closure_terms = []
        for horizon in horizons:
            eta_enc_h = model.encoder(batch["x_target"][:, horizon], batch["u_seq"][:, horizon])
            closure_terms.append(koopman_closure(eta_prop[:, horizon - 1], eta_enc_h))
        closure_raw = sum(closure_terms) / len(closure_terms)
    if loss_spec == "BCV":
        tail_raw, tail_indices = cvar_tail(
            per_sample20,
            quantile=float(protocol["loss"]["tail_quantile"]),
            min_samples=int(protocol["loss"]["tail_min_samples"]),
        )

    # Weighted auxiliary terms keep their tensor form so they contribute
    # gradients (E10 regression fix: .item() scalars detached closure/tail and
    # made MHC/BCV train identically to MH); float mirrors are only for logs.
    closure_weighted_float = 0.0 if closure_raw is None else float(closure_scale) * float(closure_raw.item())
    tail_weighted_float = 0.0 if tail_raw is None else float(tail_scale) * float(tail_raw.item())
    closure_term = 0.0 if closure_raw is None else float(closure_scale) * closure_raw
    tail_term = 0.0 if tail_raw is None else float(tail_scale) * tail_raw
    total = main + closure_term + tail_term + regularization
    denominator = max(float(total.item()), 1e-12)
    return {
        "total": total,
        "components": {
            "main": {"raw": float(main.item()), "weight": 1.0, "weighted": float(main.item()), "share": float(main.item()) / denominator},
            "closure": {"raw": None if closure_raw is None else float(closure_raw.item()), "weight": 0.0 if closure_scale is None else float(closure_scale), "weighted": float(closure_weighted_float), "share": float(closure_weighted_float) / denominator},
            "tail": {"raw": None if tail_raw is None else float(tail_raw.item()), "weight": 0.0 if tail_scale is None else float(tail_scale), "weighted": float(tail_weighted_float), "share": float(tail_weighted_float) / denominator},
            "e_decay": {"raw": float(e_decay_raw.item()), "weight": float(protocol["loss"]["e_weight_decay"]), "weighted": float(e_decay_raw.item()), "share": float(e_decay_raw) / denominator},
            "theta_decay": {"raw": float(theta_decay_raw.item()), "weight": float(protocol["loss"]["theta_weight_decay"]), "weighted": float(theta_decay_raw.item()), "share": float(theta_decay_raw) / denominator},
        },
        "per_horizon": {str(h): float(per_horizon[h].item()) for h in sorted(per_horizon)},
        "rollout": rollout,
        "per_sample20": per_sample20,
        "tail_indices": tail_indices,
        "e_norm_sq": float(torch.sum(model.E**2).item()),
    }


def train_phase(
    model: TriangularResidualKoopman,
    dataset: FrozenSequenceDataset,
    protocol: dict,
    *,
    loss_spec: str,
    fold: int,
    variant: str,
    run_id: str,
    attempt_id: str,
    stage: str,
    identity: dict,
    device,
    batch_stream: list[list[int]],
    lr: float,
    steps: int,
    grad_clip: float,
    monitor_every: int,
    early_stop_patience: int,
    closure_scale: float | None,
    tail_scale: float | None,
    out_dir: Path,
    monitor_fn=None,
    trace: list | None = None,
    tail_member_log: list | None = None,
    resume: bool = False,
) -> dict:
    """Unified training loop over a position-indexed batch stream."""
    group_weights = group_slices_from_protocol(protocol)
    trainable = [param for param in model.parameters() if param.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=float(lr))
    model.to(device)
    model.train()

    last_path = out_dir / "last.pt"
    best_path = out_dir / "best.pt"
    best = EarlyStopState(patience=int(early_stop_patience))
    start_step = 0
    curves: list[dict] = []
    tail_rows: list[dict] = []
    if resume and last_path.exists():
        sidecar = json.loads(last_path.with_suffix(".json").read_text(encoding="utf-8"))
        payload = torch.load(last_path, map_location=device)
        model.load_state_dict(payload["model_state"])
        optimizer.load_state_dict(payload["optimizer_state"])
        start_step = int(sidecar["step"])
        best = EarlyStopState.from_dict(sidecar["best"])
        restore_rng(sidecar["rng_state"])
        curves = list(sidecar.get("loss_curve", []))
        print(f"resumed {variant} fold {fold} from step {start_step}")

    step = start_step
    stream_position = start_step  # one batch per optimizer step
    best_model_state = None
    started = time.perf_counter()
    while step < int(steps):
        if stream_position >= len(batch_stream):
            raise RuntimeError(f"batch stream exhausted at step {step} (stream has {len(batch_stream)})")
        batch = _batch_tensors(dataset, batch_stream[stream_position], device)
        stream_position += 1
        optimizer.zero_grad(set_to_none=True)
        losses = step_loss(
            model, batch, protocol, loss_spec, group_weights, closure_scale, tail_scale
        )
        if not torch.isfinite(losses["total"]):
            raise FloatingPointError(f"non-finite loss at step {step} for {variant} fold {fold}")
        losses["total"].backward()
        torch.nn.utils.clip_grad_norm_(trainable, float(grad_clip))
        optimizer.step()
        step += 1

        if tail_member_log is not None and losses["tail_indices"] is not None:
            batch_meta = batch["metadata"]
            for position_in_batch in losses["tail_indices"].detach().cpu().tolist():
                sample = batch_meta[int(position_in_batch)]
                tail_rows.append(
                    {
                        "step": step,
                        "batch_position": int(position_in_batch),
                        "trajectory_id": int(sample["trajectory_id"]),
                        "base_family_id": str(sample["base_family_id"]),
                        "scenario": str(sample["scenario"]),
                        "window_class": str(sample["window_class"]),
                        "window_start": int(sample["start"]),
                    }
                )
            if step % 250 == 0:
                tail_member_log.extend(tail_rows)
                tail_rows = []

        if step % int(monitor_every) == 0 or step == int(steps):
            entry = {
                "step": step,
                **losses["components"],
                "total": float(losses["total"].item()),
            }
            curves.append(entry)
            if trace is not None:
                trace.append(entry)
            if monitor_fn is not None:
                qcv = float(monitor_fn(model))
                entry["qcv"] = qcv
                improved = best.observe(qcv, step)
                if improved:
                    best_model_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
                    save_checkpoint(
                        best_path,
                        run_id=run_id, attempt_id=attempt_id, stage=stage, variant=variant,
                        fold=fold, seed=int(identity.get("seed", 0)), identity=identity, kind="best",
                        model=model, optimizer=optimizer, step=step, best=best,
                        sampler_position=stream_position, loss_curve=curves,
                    )
                if best.should_stop():
                    print(f"early stop {variant} fold {fold} at step {step} (best step {best.best_step})")
                    break
    if tail_member_log is not None:
        tail_member_log.extend(tail_rows)

    save_checkpoint(
        last_path,
        run_id=run_id, attempt_id=attempt_id, stage=stage, variant=variant,
        fold=fold, seed=int(identity.get("seed", 0)), identity=identity, kind="last",
        model=model, optimizer=optimizer, step=step, best=best,
        sampler_position=stream_position, loss_curve=curves,
    )
    if best_model_state is None and best.best_step == 0 and monitor_fn is not None:
        best_model_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        save_checkpoint(
            best_path,
            run_id=run_id, attempt_id=attempt_id, stage=stage, variant=variant,
            fold=fold, seed=int(identity.get("seed", 0)), identity=identity, kind="best",
            model=model, optimizer=optimizer,
            step=best.best_step if best.best_step else step, best=best,
            sampler_position=stream_position, loss_curve=curves,
        )
    return {
        "variant": variant,
        "fold": int(fold),
        "step": step,
        "best_step": best.best_step,
        "best_metric": best.best_metric,
        "wall_s": time.perf_counter() - started,
        "curve": curves,
    }

"""GDM-RK losses: group-weighted RMSE, CVaR tail, Koopman closure, and the
frozen initial scale calibration for the auxiliary terms."""

from __future__ import annotations

import torch

from lift import GroupedResidualEncoder


def group_rmse(
    prediction: torch.Tensor,
    target: torch.Tensor,
    group_weights: dict[str, tuple[float, slice]],
) -> torch.Tensor:
    """Scalar group-weighted RMSE over the whole batch:
    l_h = w_g0 RMSE(g0) + w_g1 RMSE(g1) + w_g2 RMSE(g2) + w_g3 RMSE(g3)."""
    error = prediction - target
    total = None
    for _, (weight, selected) in group_weights.items():
        term = float(weight) * torch.sqrt(torch.mean(error[:, selected] ** 2))
        total = term if total is None else total + term
    return total


def per_sample_group_error(
    prediction: torch.Tensor,
    target: torch.Tensor,
    group_weights: dict[str, tuple[float, slice]],
) -> torch.Tensor:
    """Per-sample group-weighted error (B,) used by the CVaR tail."""
    error = (prediction - target) ** 2
    total = torch.zeros(prediction.shape[0], dtype=prediction.dtype, device=prediction.device)
    for _, (weight, selected) in group_weights.items():
        total = total + float(weight) * torch.sqrt(torch.mean(error[:, selected], dim=1))
    return total


def cvar_tail(
    per_sample_errors: torch.Tensor,
    quantile: float = 0.90,
    min_samples: int = 4,
) -> torch.Tensor:
    """Mean of the worst (1-quantile) fraction of a batch; at least min_samples."""
    values = per_sample_errors.reshape(-1)
    if values.numel() == 0:
        raise ValueError("empty per-sample error vector")
    keep = max(int(min_samples), int(math_ceil((1.0 - float(quantile)) * values.numel())))
    keep = min(keep, values.numel())
    top = torch.topk(values, k=keep).values
    return torch.mean(top)


def math_ceil(value: float) -> int:
    import math

    return int(math.ceil(value))


def koopman_closure(
    eta_propagated: torch.Tensor,
    eta_encoded: torch.Tensor,
) -> torch.Tensor:
    """|| eta_propagated - sg[eta_encoded] ||^2 averaged over the batch."""
    if eta_propagated.shape != eta_encoded.shape:
        raise ValueError(f"closure shape mismatch: {eta_propagated.shape} vs {eta_encoded.shape}")
    return torch.mean((eta_propagated - eta_encoded.detach()) ** 2)


def group_slices_from_protocol(protocol: dict) -> dict[str, tuple[float, slice]]:
    groups = protocol["state_groups"]
    weights = groups["group_loss_weights"]
    return {
        name: (float(weights[name]), slice(*groups[name]))
        for name in ("g0", "g1", "g2", "g3")
    }


def freeze_loss_scale(
    model: torch.nn.Module,
    samples: list[dict],
    protocol: dict,
    *,
    device,
) -> dict:
    """Compute the frozen median auxiliary losses over the first 256 train
    windows; saved to the run as loss_scale.json before any formal training."""
    from losses import group_slices_from_protocol, per_sample_group_error

    group_weights = group_slices_from_protocol(protocol)
    tails = []
    invs = []
    with torch.no_grad():
        for sample in samples[:256]:
            x0 = sample["x0"].to(device)[None]
            u_seq = sample["u_seq"].to(device)[None]
            target20 = sample["target20"].to(device)[None]
            rollout = model.rollout(x0, u_seq, (20,), return_eta=True)
            pred20 = rollout["xhat"][:, 19]
            per_sample = per_sample_group_error(pred20, target20, group_weights)
            tails.append(float(torch.mean(per_sample).item()))
            eta_prop = rollout["eta"][:, 20]
            eta_enc = model.encoder(target20, u_seq[:, 19])
            invs.append(float(torch.mean((eta_prop - eta_enc.detach()) ** 2).item()))
    import numpy as np

    return {
        "window_count": len(samples[:256]),
        "tail_median": float(np.median(tails)) if tails else None,
        "closure_median": float(np.median(invs)) if invs else None,
    }

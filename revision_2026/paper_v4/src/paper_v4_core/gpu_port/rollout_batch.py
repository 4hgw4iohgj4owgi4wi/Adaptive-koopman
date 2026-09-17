"""Batched 20 ms predictor rollout on CUDA, preserving the CPU update order."""
from __future__ import annotations

import torch

from .physics_torch import TorchModel, rk4_step_batch


PLANT_DT = 0.002
TAU = 0.12
RATE = 1.2
LIMIT = torch.deg2rad(torch.tensor(15.0, dtype=torch.float64)).item()


def actuator_step_batch(request: torch.Tensor, actual: torch.Tensor) -> torch.Tensor:
    free = request + torch.exp(torch.as_tensor(-PLANT_DT / TAU, dtype=actual.dtype, device=actual.device)) * (actual - request)
    increment = torch.clamp(free - actual, -RATE * PLANT_DT, RATE * PLANT_DT)
    return torch.clamp(actual + increment, -LIMIT, LIMIT)


def rollout_batch_torch(z: torch.Tensor, u: torch.Tensor, model: TorchModel, *, strict: bool = False) -> torch.Tensor:
    if z.ndim != 2 or z.shape[1] != 34 or u.shape != (z.shape[0], 8):
        raise ValueError("z must be [B,34] and u [B,8]")
    state = z[:, :30].clone()
    delta = z[:, 30:34].clone()
    control = u.reshape(-1, 4, 2)
    for _ in range(10):
        delta = actuator_step_batch(control[..., 1], delta)
        applied = torch.stack((control[..., 0], delta), dim=-1)
        state = rk4_step_batch(state, applied, PLANT_DT, model, strict=strict)
    output = torch.cat((state, delta), dim=1)
    if strict and not bool(torch.isfinite(output).all().item()):
        raise FloatingPointError("nonfinite torch rollout")
    return output

"""Shared linear transition and deterministic connector physics heads for K3."""

from __future__ import annotations

import torch
from torch import nn


class GlobalLinearTransition(nn.Module):
    def __init__(self, lift_dim: int, input_dim: int) -> None:
        super().__init__()
        self.A = nn.Parameter(torch.eye(lift_dim) + 1.0e-4 * torch.randn(lift_dim, lift_dim))
        self.B = nn.Parameter(1.0e-4 * torch.randn(lift_dim, input_dim))

    def forward(self, z: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        return z @ self.A.T + u @ self.B.T


def connector_quantities(force_output: torch.Tensor) -> dict[str, torch.Tensor]:
    """Derive loads from [4x(Fx,Fy), Q_FR, Q_LR, 4x(dFx,dFy)]."""
    forces = force_output[..., :8].reshape(*force_output.shape[:-1], 4, 2)
    fx, fy = forces[..., :, 0], forces[..., :, 1]
    q_fr_from_force = 0.5 * ((fx[..., 0] + fx[..., 1]) - (fx[..., 2] + fx[..., 3]))
    q_lr_from_force = 0.5 * ((fy[..., 0] + fy[..., 2]) - (fy[..., 1] + fy[..., 3]))
    q_from_force = torch.stack([q_fr_from_force, q_lr_from_force], dim=-1)
    net_force = forces.sum(dim=-2)
    anchors = force_output.new_tensor([[2.5, 1.0], [2.5, -1.0], [-2.5, 1.0], [-2.5, -1.0]])
    moment = (anchors[:, 0] * fy - anchors[:, 1] * fx).sum(dim=-1, keepdim=True)
    max_force = torch.linalg.vector_norm(forces, dim=-1).amax(dim=-1, keepdim=True)
    action_reaction = forces + (-forces)
    return {
        "q_from_force": q_from_force,
        "q_head": force_output[..., 8:10],
        "net_force": net_force,
        "payload_moment": moment,
        "max_connector_force": max_force,
        "action_reaction_residual": action_reaction,
    }


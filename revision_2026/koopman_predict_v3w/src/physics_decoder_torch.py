"""Differentiable float64 Torch R3/V1 connector readout and full internal force.

Mirrors physics_decoder.R3Decoder (NumPy) exactly so the P6 oracle check
(real d/v -> force) can compare Torch vs NumPy element-wise.  The planar grasp
projector uses torch.linalg.pinv on the frozen W matrix (deterministic, float64).
"""

from __future__ import annotations

import torch


class TorchR3Decoder:
    def __init__(self, build_planar_grasp_matrix):
        self._build_grasp = build_planar_grasp_matrix

    def _params(self, params: object) -> dict:
        return {
            "free_play_m": float(params.connector.free_play_m),
            "smoothing_width_m": float(params.connector.smoothing_width_m),
            "stiffness_npm": float(params.connector.stiffness_npm),
            "damping_nspm": float(params.connector.damping_nspm),
            "anchor_body": torch.as_tensor(
                params.payload_anchor_body_m, dtype=torch.float64
            ),
        }

    def connector_force(
        self,
        relative_state47: torch.Tensor,
        params: object,
        law: str,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return (force8, internal8); identical math to the NumPy R3Decoder."""
        values = relative_state47
        if values.ndim == 1:
            values = values.reshape(1, -1)
        g3 = values[:, 31:47].reshape(-1, 4, 4)
        displacement = g3[:, :, :2]
        velocity = g3[:, :, 2:]
        distance = torch.linalg.vector_norm(displacement, dim=2)
        normal = displacement / torch.clamp(distance[:, :, None], min=1.0e-12)
        penetration = torch.clamp(distance - self._params(params)["free_play_m"], min=0.0)
        normal_speed = torch.sum(velocity * normal, dim=2)
        if str(law).upper() == "V1":
            weight = (penetration > 0.0).to(dtype=torch.float64)
        elif str(law).upper() == "R3":
            width = self._params(params)["smoothing_width_m"]
            ratio = torch.clamp(penetration / width, 0.0, 1.0)
            weight = torch.where(
                penetration <= 0.0,
                torch.zeros_like(penetration),
                torch.where(
                    penetration >= width,
                    torch.ones_like(penetration),
                    3 * ratio**2 - 2 * ratio**3,
                ),
            )
        else:
            raise ValueError(law)
        magnitude = (
            self._params(params)["stiffness_npm"] * penetration
            + self._params(params)["damping_nspm"]
            * weight
            * torch.clamp(normal_speed, min=0.0)
        )
        force = magnitude[:, :, None] * normal
        grasp = torch.as_tensor(
            self._build_grasp(self._params(params)["anchor_body"].numpy()),
            dtype=torch.float64,
        )
        projector = torch.eye(8, dtype=torch.float64) - torch.linalg.pinv(grasp) @ grasp
        force8 = force.reshape(-1, 8)
        internal8 = force8 @ projector.T
        if relative_state47.ndim == 1:
            return force8[0], internal8[0]
        return force8, internal8

    def internal_force(self, force8: torch.Tensor, params: object) -> torch.Tensor:
        grasp = torch.as_tensor(
            self._build_grasp(self._params(params)["anchor_body"].numpy()),
            dtype=torch.float64,
        )
        projector = torch.eye(8, dtype=torch.float64) - torch.linalg.pinv(grasp) @ grasp
        return force8 @ projector.T

    def null_space_residual(self, force8: torch.Tensor, params: object) -> float:
        grasp = torch.as_tensor(
            self._build_grasp(self._params(params)["anchor_body"].numpy()),
            dtype=torch.float64,
        )
        internal = self.internal_force(force8, params)
        scale = max(float(torch.max(torch.abs(internal))) if internal.numel() else 1.0, 1.0)
        return float(torch.max(torch.abs(grasp @ internal.T))) / scale

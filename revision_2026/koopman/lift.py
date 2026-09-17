"""Shared trainable physical-passthrough lift for K3 S4/S5 experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import nn

from transition import GlobalLinearTransition, connector_quantities


S2_FIELDS = [f"{body}.{name}" for body in ("FL", "FR", "RL", "RR", "payload") for name in ("x_m", "y_m", "psi_rad", "vx_mps", "vy_mps", "yaw_rate_radps")]
DEFORMATION_FIELDS = [f"{point}.{name}" for point in ("FL", "FR", "RL", "RR") for name in ("dx_body_m", "dy_body_m")]
RELATIVE_VELOCITY_FIELDS = [f"{point}.{name}" for point in ("FL", "FR", "RL", "RR") for name in ("dvx_body_mps", "dvy_body_mps")]
FORCE_FIELDS = [f"{point}.{axis}_n" for point in ("FL", "FR", "RL", "RR") for axis in ("Fx", "Fy")]
Q_FIELDS = ["Q_front_rear_n", "Q_left_right_n"]
FORCE_RATE_FIELDS = [f"{point}.d{axis}_nps" for point in ("FL", "FR", "RL", "RR") for axis in ("Fx", "Fy")]
SENSOR_META_FIELDS = [f"{point}.force_available_mask" for point in ("FL", "FR", "RL", "RR")] + [f"{point}.force_AoI_steps" for point in ("FL", "FR", "RL", "RR")]
S3_FIELDS = S2_FIELDS + DEFORMATION_FIELDS + RELATIVE_VELOCITY_FIELDS
S4_FIELDS = S3_FIELDS + FORCE_FIELDS + Q_FIELDS + FORCE_RATE_FIELDS
U1_FIELDS = [f"{point}.{name}" for point in ("FL", "FR", "RL", "RR") for name in ("accel_mps2", "steer_rad")]


@dataclass(frozen=True)
class Contract:
    name: str
    input_key: str
    input_fields: Sequence[str]
    input_dim: int


CONTRACTS = {
    "S4-force-in": Contract("S4-force-in", "s4_force_in", S4_FIELDS + SENSOR_META_FIELDS, 72),
    "S5-force-out": Contract("S5-force-out", "s3_deform", S3_FIELDS, 46),
}


class SharedLiftedLinear(nn.Module):
    """z=[normalized physical input, learned observables], total dimension fixed."""

    def __init__(self, contract_name: str, lift_dim: int = 96, hidden_dim: int = 64, input_dim: int = 8) -> None:
        super().__init__()
        contract = CONTRACTS[contract_name]
        if lift_dim <= contract.input_dim:
            raise ValueError("lift_dim must exceed physical input dimension")
        latent_dim = lift_dim - contract.input_dim
        self.contract_name = contract_name
        self.contract = contract
        self.lift_dim = lift_dim
        self.latent_dim = latent_dim
        self.encoder = nn.Sequential(
            nn.Linear(contract.input_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, latent_dim),
        )
        self.transition = GlobalLinearTransition(lift_dim, input_dim)
        # Same output capacity for S4 and S5.  The common 30-state physical
        # output is decoded exactly from the passthrough prefix z[:30].
        self.force_decoder = nn.Linear(lift_dim, 18)

    def encode(self, x_normalized: torch.Tensor) -> torch.Tensor:
        if x_normalized.shape[-1] != self.contract.input_dim:
            raise ValueError(f"{self.contract_name} expects {self.contract.input_dim} inputs")
        return torch.cat([x_normalized, self.encoder(x_normalized)], dim=-1)

    @staticmethod
    def decode_state(z: torch.Tensor) -> torch.Tensor:
        return z[..., :30]

    def decode(self, z: torch.Tensor) -> dict[str, torch.Tensor]:
        force = self.force_decoder(z)
        return {"state": self.decode_state(z), "force": force, **connector_quantities(force)}

    def step(self, z: torch.Tensor, u_normalized: torch.Tensor) -> torch.Tensor:
        return self.transition(z, u_normalized)

    def rollout(self, x0_normalized: torch.Tensor, controls_normalized: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z = self.encode(x0_normalized)
        z_rows, state_rows, force_rows = [], [], []
        for horizon in range(controls_normalized.shape[1]):
            z = self.step(z, controls_normalized[:, horizon])
            decoded = self.decode(z)
            z_rows.append(z)
            state_rows.append(decoded["state"])
            force_rows.append(decoded["force"])
        return torch.stack(z_rows, dim=1), torch.stack(state_rows, dim=1), torch.stack(force_rows, dim=1)

    def trainable_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)


def graph_audit(model: SharedLiftedLinear) -> dict[str, object]:
    fields = list(model.contract.input_fields)
    forbidden = FORCE_FIELDS + Q_FIELDS + FORCE_RATE_FIELDS
    present_forbidden = sorted(set(fields) & set(forbidden))
    return {
        "contract": model.contract_name,
        "input_key": model.contract.input_key,
        "input_dim": model.contract.input_dim,
        "input_fields": fields,
        "forbidden_force_fields_present": present_forbidden if model.contract_name == "S5-force-out" else "not_applicable",
        "s5_no_force_input_path": bool(model.contract_name != "S5-force-out" or not present_forbidden),
        "state_decoder": "exact passthrough z[...,0:30]",
        "force_decoder": "shared-capacity Linear(96,18)",
    }

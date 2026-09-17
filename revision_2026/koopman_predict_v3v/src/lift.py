"""GDM-RK: physical-group damped-mode residual Koopman.

x_{k+1} = A0 x_k + B0 u_k + b0 + E eta_k
eta_{k+1} = F eta_k + G u_k + c_eta

with F a block-diagonal product of 2x2 damped rotations
(F_j = r_j R(omega_j), r_j = 0.995 sigmoid(a_j) < 0.995, omega_j = pi sigmoid(b_j)),
so the residual modes are Schur-stable by construction and the linear part

    K = [[A0, E], [0, F]],  C = [I 0]

is block triangular, hence sigma(K) = sigma(A0) union sigma(F).
A0/B0/b0 are the frozen S0 coefficients (buffers, requires_grad=False).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn


class DampedModeMatrix(nn.Module):
    """F built from 2x2 damped-rotation blocks; even residual dim only."""

    def __init__(self, pairs: int, radius_max: float = 0.995):
        super().__init__()
        if int(pairs) <= 0 or int(pairs) != pairs:
            raise ValueError(f"pairs must be a positive integer, got {pairs}")
        self.pairs = int(pairs)
        self.radius_max = float(radius_max)
        if not 0.0 < self.radius_max < 1.0:
            raise ValueError(f"radius_max must lie in (0, 1), got {radius_max}")
        # a_j drives the radius toward radius_max; b_j drives omega toward pi
        self.a = nn.Parameter(torch.zeros(self.pairs))
        self.b = nn.Parameter(torch.zeros(self.pairs))

    @property
    def radius(self) -> torch.Tensor:
        return self.radius_max * torch.sigmoid(self.a)

    @property
    def omega(self) -> torch.Tensor:
        return math.pi * torch.sigmoid(self.b)

    def forward(self) -> torch.Tensor:
        radius = self.radius
        omega = self.omega
        blocks = []
        for index in range(self.pairs):
            cosine = torch.cos(omega[index])
            sine = torch.sin(omega[index])
            blocks.append(
                torch.stack(
                    [
                        torch.stack([radius[index] * cosine, -radius[index] * sine]),
                        torch.stack([radius[index] * sine, radius[index] * cosine]),
                    ]
                )
            )
        return torch.block_diag(*blocks)  # (2*pairs, 2*pairs)

    def per_pair_radius(self) -> list[float]:
        return [float(value) for value in self.radius.detach().cpu().tolist()]

    def spectral_radius(self) -> float:
        return max(self.per_pair_radius())


class _MLP(nn.Module):
    def __init__(self, input_dim: int, hidden_width: int, output_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(int(input_dim), int(hidden_width)),
            nn.SiLU(),
            nn.Linear(int(hidden_width), int(hidden_width)),
            nn.SiLU(),
            nn.Linear(int(hidden_width), int(output_dim)),
            nn.Tanh(),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.net(value)


class GroupedResidualEncoder(nn.Module):
    """Dual-branch residual observable.

    eta = [ phi_d([g0, g1, g2, u]) ; phi_c([g2, g3, u]) ] in R^r.

    g2 feeds both branches because it is the causal coupling quantity between
    vehicle dynamics and connector dynamics.  No attention, no scenario labels,
    no expert softmax.
    """

    G0 = slice(0, 3)
    G1 = slice(3, 19)
    G2 = slice(19, 31)
    G3 = slice(31, 47)

    def __init__(
        self, residual_dim: int, branch_output: int, hidden_width: int, input_dim: int = 7
    ):
        super().__init__()
        if int(residual_dim) != 2 * int(branch_output):
            raise ValueError(
                f"residual_dim must equal 2*branch_output: {residual_dim} vs {branch_output}"
            )
        if int(input_dim) < 7:
            raise ValueError(f"input_dim must be >= 7 (7-dim baseline or 11-dim protocol): {input_dim}")
        self.residual_dim = int(residual_dim)
        self.branch_output = int(branch_output)
        self.input_dim = int(input_dim)
        u_extra = self.input_dim - 7  # control11 protocol appends four accel differentials
        # phi_d: g0(3) + g1(16) + g2(12) + u = 38 + u_extra
        self.branch_d = _MLP(3 + 16 + 12 + self.input_dim, int(hidden_width), self.branch_output)
        # phi_c: g2(12) + g3(16) + u = 35 + u_extra
        self.branch_c = _MLP(12 + 16 + self.input_dim, int(hidden_width), self.branch_output)

    def forward(self, x: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        g0 = x[:, self.G0]
        g1 = x[:, self.G1]
        g2 = x[:, self.G2]
        g3 = x[:, self.G3]
        eta_d = self.branch_d(torch.cat([g0, g1, g2, u], dim=-1))
        eta_c = self.branch_c(torch.cat([g2, g3, u], dim=-1))
        return torch.cat([eta_d, eta_c], dim=-1)


class TriangularResidualKoopman(nn.Module):
    """Frozen-S0-backbone residual Koopman model with damped-mode propagation."""

    def __init__(
        self,
        a0: torch.Tensor,
        b0: torch.Tensor,
        bias0: torch.Tensor,
        residual_dim: int,
        branch_output: int,
        hidden_width: int,
        e_init_scale: float = 0.01,
        radius_max: float = 0.995,
        dense_f: bool = False,
        input_dim: int = 7,
    ):
        super().__init__()
        a0 = torch.as_tensor(a0, dtype=torch.float64)
        b0 = torch.as_tensor(b0, dtype=torch.float64)
        bias0 = torch.as_tensor(bias0, dtype=torch.float64)
        if a0.shape != (47, 47) or b0.shape != (47, int(input_dim)) or bias0.shape != (47,):
            raise ValueError(
                f"frozen S0 block shape mismatch: {a0.shape} {b0.shape} {bias0.shape} (input_dim={input_dim})"
            )
        # S0 blocks stay float64 at full frozen precision; trainable params are float32
        self.register_buffer("A0", a0, persistent=True)
        self.register_buffer("B0", b0, persistent=True)
        self.register_buffer("b0", bias0, persistent=True)
        self.residual_dim = int(residual_dim)
        self.input_dim = int(input_dim)
        self.input_schema = f"u{self.input_dim}"
        if self.residual_dim % 2 != 0:
            raise ValueError("only even residual dimensions are allowed (16/32)")
        self.encoder = GroupedResidualEncoder(residual_dim, branch_output, hidden_width, input_dim=self.input_dim)
        self.E = nn.Parameter(torch.zeros(47, self.residual_dim))
        with torch.no_grad():
            self.E.normal_(0.0, e_init_scale)
        self.dense_f = bool(dense_f)
        if self.dense_f:
            # AF ablation: free dense F (no damped-mode structure)
            self.F_dense = nn.Parameter(torch.zeros(self.residual_dim, self.residual_dim))
            with torch.no_grad():
                self.F_dense.normal_(0.0, 0.02)
        else:
            self.F = DampedModeMatrix(self.residual_dim // 2, radius_max=radius_max)
        self.G = nn.Parameter(torch.zeros(self.residual_dim, self.input_dim))
        self.c = nn.Parameter(torch.zeros(self.residual_dim))

    # -- structure ----------------------------------------------------------
    def f_matrix(self) -> torch.Tensor:
        if self.dense_f:
            return self.F_dense
        return self.F()

    def full_k_matrix(self) -> torch.Tensor:
        """Effective column K; rollout uses row eta @ F, so F_c=F.T."""
        a0 = self.A0.double()
        e = self.E.double()
        f = self.f_matrix().double().T
        rows = a0.shape[0] + f.shape[0]
        k = torch.zeros(rows, rows, dtype=torch.float64, device=a0.device)
        k[:47, :47] = a0
        k[:47, 47:] = e
        k[47:, 47:] = f
        return k

    def frozen_blocks_unchanged(self) -> bool:
        """Buffers must never receive gradients (A0/B0/b0 are frozen)."""
        return not (
            self.A0.requires_grad or self.B0.requires_grad or self.b0.requires_grad
        )

    # -- rollout -------------------------------------------------------------
    def rollout(
        self,
        x0: torch.Tensor,
        u_seq: torch.Tensor,
        horizons: tuple[int, ...] | list[int],
        *,
        return_eta: bool = False,
    ):
        """Propagate eta over the horizon window starting from the real x0.

        x0: (B, 47) normalized real state at k.
        u_seq: (B, H_max, 7) normalized controls for intervals k..k+H_max-1.
        eta is encoded once from the real state and then propagated with F;
        the physical state is read directly from xhat (C = [I 0]).
        Returns dict with 'xhat' (B, H_max, 47) and per-horizon slices.
        """
        device = x0.device
        dtype = x0.dtype
        a0 = self.A0.to(dtype=dtype)
        b0 = self.B0.to(dtype=dtype)
        bias0 = self.b0.to(dtype=dtype)
        xhat = x0.clone()
        eta = self.encoder(x0, u_seq[:, 0])
        h_max = u_seq.shape[1]
        predictions = []
        etas = [eta]
        # F is constant across one rollout. Reuse the same differentiable tensor;
        # do not rebuild identical damped-mode blocks at each horizon step.
        propagation_f = self.f_matrix().to(dtype=dtype)
        for step in range(int(h_max)):
            u_t = u_seq[:, step]
            xhat = xhat @ a0.T + u_t @ b0.T + bias0 + eta @ self.E.to(dtype=dtype).T
            eta = eta @ propagation_f + u_t @ self.G.to(dtype=dtype).T + self.c.to(dtype=dtype)
            predictions.append(xhat)
            etas.append(eta)
        stacked = torch.stack(predictions, dim=1)  # (B, H_max, 47)
        result = {"xhat": stacked}
        if return_eta:
            result["eta"] = torch.stack(etas, dim=1)  # (B, H_max+1, r)
        return result

    def parameter_count(self) -> dict:
        total = sum(param.numel() for param in self.parameters())
        trainable = sum(param.numel() for param in self.parameters() if param.requires_grad)
        frozen_s0 = self.A0.numel() + self.B0.numel() + self.b0.numel()
        return {
            "total": int(total + frozen_s0),
            "trainable": int(trainable),
            "frozen_s0": int(frozen_s0),
        }

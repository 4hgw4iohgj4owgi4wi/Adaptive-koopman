"""KC1: truly fixed-linear Koopman (pure A0/B0/b0 recursion), no encoder, no
random residual term (koopman_next.md C01).  Three-way equivalence targets:
direct NumPy recursion, this pure class, and an E=0 copy of the residual model.
"""
from __future__ import annotations

import numpy as np
import torch


class PureLinearKoopman:
    """x_{h+1} = A0 x_h + B0 u_{k+h} + b0, x_0 = x_k.  Buffers float64."""

    def __init__(self, a0, b0, bias0, input_dim: int):
        if int(input_dim) not in (7, 11):
            raise ValueError(f"input_dim must be exactly 7 or 11 (C11): {input_dim}")
        a0 = torch.as_tensor(a0, dtype=torch.float64)
        b0 = torch.as_tensor(b0, dtype=torch.float64)
        bias0 = torch.as_tensor(bias0, dtype=torch.float64)
        if a0.shape != (47, 47) or b0.shape != (47, int(input_dim)) or bias0.shape != (47,):
            raise ValueError(f"pure linear block shape mismatch: {a0.shape} {b0.shape} {bias0.shape}")
        self.register = None  # plain attributes; buffers kept for parity checks
        self.A0 = a0
        self.B0 = b0
        self.b0 = bias0
        self.input_dim = int(input_dim)
        self.input_schema = f"u{self.input_dim}"
        self.model_kind = "M0_FIXED_LINEAR"
        self.encoder = None
        self.E = None

    def rollout(self, x0: torch.Tensor, u_seq: torch.Tensor, horizons, *, return_eta: bool = False):
        """Pure linear recursion; returns the same dict shape as the residual model."""
        x0 = x0.to(dtype=torch.float64)
        u_seq = u_seq.to(dtype=torch.float64)
        if u_seq.ndim == 2:
            u_seq = u_seq[:, None, :]
        max_h = int(max(horizons))
        if u_seq.shape[1] < max_h:
            raise ValueError(f"u_seq horizon {u_seq.shape[1]} < {max_h}")
        A = self.A0.to(device=x0.device)
        B = self.B0.to(device=x0.device)
        bias = self.b0.to(device=x0.device)
        x = x0
        predictions = []
        for h in range(max_h):
            x = x @ A.T + u_seq[:, h] @ B.T + bias
            predictions.append(x)
        stacked = torch.stack(predictions, dim=1)  # (B, max_h, 47)
        out = {"xhat": stacked}
        if return_eta:
            out["eta"] = torch.zeros(stacked.shape[0], max_h + 1, 1, dtype=torch.float64, device=x0.device)
        return out


def numpy_linear_rollout(a0: np.ndarray, b0: np.ndarray, bias0: np.ndarray,
                         x0: np.ndarray, u_seq: np.ndarray, max_h: int) -> np.ndarray:
    """Direct NumPy recursion (path 1).  Accepts single-sequence x0 (47,) with
    u_seq (H, udim), or batched x0 (B,47) with u_seq (B,H,udim)."""
    x = np.array(x0, dtype=float, copy=True)
    batched = x.ndim == 2
    out = []
    for h in range(max_h):
        u_h = u_seq[:, h] if batched else u_seq[h]
        x = x @ a0.T + u_h @ b0.T + bias0
        out.append(np.array(x, copy=True))
    return np.stack(out, axis=1) if batched else np.stack(out, axis=0)


def residual_copy_e0(model, coeff_slices):
    """Path 3: residual model with E forced to zero (copy only; never mutates the
    original training weights)."""
    clone = copy_model(model)
    with torch.no_grad():
        clone.E.zero_()
    return clone


def copy_model(model):
    import copy

    return copy.deepcopy(model)

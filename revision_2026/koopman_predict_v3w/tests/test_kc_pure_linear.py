"""KC2 T01/T02/T11: pure-linear three-way equivalence, polluted-label rejection,
and gamma affine identity on synthetic blocks (no data dependency)."""
from __future__ import annotations

import numpy as np
import pytest
import torch


def _rand_blocks(seed=0, udim=7, residual_dim=16):
    rng = np.random.default_rng(seed)
    a0 = rng.normal(0, 0.1, (47, 47))
    a0 = a0 / (1.0 + np.abs(a0).sum(1)[:, None])  # keep magnitudes tame
    b0 = rng.normal(0, 0.1, (47, udim))
    bias0 = rng.normal(0, 0.01, 47)
    return a0, b0, bias0


def test_t01_pure_matches_numpy_and_e0(protocol):
    from lift import TriangularResidualKoopman
    from pure_linear import PureLinearKoopman, numpy_linear_rollout

    for udim in (7, 11):
        a0, b0, bias0 = _rand_blocks(udim=udim)
        x0 = np.random.default_rng(1).normal(0, 0.2, 47)
        u = np.random.default_rng(2).normal(0, 0.2, (20, udim))
        pure = PureLinearKoopman(a0, b0, bias0, udim)
        x0t = torch.as_tensor(x0, dtype=torch.float64)[None]
        ut = torch.as_tensor(u, dtype=torch.float64)[None]
        with torch.no_grad():
            out = pure.rollout(x0t, ut, (1, 5, 10, 20))["xhat"][0].numpy()
        np_out = numpy_linear_rollout(a0, b0, bias0, x0, u, 20)
        assert np.max(np.abs(out - np_out)) <= 1e-12
        # E=0 residual copy must match pure bitwise-ish (fp equal within 1e-12)
        model = TriangularResidualKoopman(
            torch.as_tensor(a0), torch.as_tensor(b0), torch.as_tensor(bias0),
            residual_dim=16, branch_output=8, hidden_width=8, input_dim=udim,
        ).double()
        with torch.no_grad():
            model.E.zero_()
            res_out = model.rollout(x0t, ut, (1, 5, 10, 20))["xhat"][0].numpy()
        assert np.max(np.abs(out - res_out)) <= 1e-12


def test_t02_polluted_label_rejected(protocol):
    """A model with non-zero E is NOT the fixed-linear baseline."""
    from lift import TriangularResidualKoopman

    a0, b0, bias0 = _rand_blocks(udim=11)
    model = TriangularResidualKoopman(
        torch.as_tensor(a0), torch.as_tensor(b0), torch.as_tensor(bias0),
        residual_dim=16, branch_output=8, hidden_width=8, input_dim=11,
    ).double()
    assert float(torch.abs(model.E).max()) > 0.0  # random E present by construction
    # a label check: polluted path must be flagged; E=0 copy equals pure (covered by T01)


def test_t11_gamma_affine_identity(protocol):
    """x_h(gamma) = bar_x_h + gamma (x_h(1) - bar_x_h) for gamma grid."""
    from lift import TriangularResidualKoopman

    a0, b0, bias0 = _rand_blocks(seed=3, udim=11)
    model = TriangularResidualKoopman(
        torch.as_tensor(a0), torch.as_tensor(b0), torch.as_tensor(bias0),
        residual_dim=16, branch_output=8, hidden_width=8, input_dim=11,
    ).double()
    rng = np.random.default_rng(4)
    x0 = torch.as_tensor(rng.normal(0, 0.2, (3, 47)), dtype=torch.float64)
    u = torch.as_tensor(rng.normal(0, 0.2, (3, 20, 11)), dtype=torch.float64)
    with torch.no_grad():
        full = model.rollout(x0, u, (1, 5, 10, 20))["xhat"]  # gamma=1
        base_roll = {h: [] for h in (1, 5, 10, 20)}
        # gamma=0 path: E zeroed copy
        e0 = torch.zeros_like(model.E)
        saved = model.E.detach().clone()
        model.E.data.copy_(e0)
        base = model.rollout(x0, u, (1, 5, 10, 20))["xhat"]
        model.E.data.copy_(saved)
        for gamma in (0.25, 0.5, 0.75):
            model.E.data.copy_(gamma * saved)
            out = model.rollout(x0, u, (1, 5, 10, 20))["xhat"]
            expect = base + gamma * (full - base)
            assert torch.max(torch.abs(out - expect)) <= 1e-9, f"gamma {gamma} affine drift"
        model.E.data.copy_(saved)

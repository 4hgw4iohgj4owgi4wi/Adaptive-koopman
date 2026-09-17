from __future__ import annotations

import copy

import numpy as np
import pytest
import torch

from background_core import (
    INTERNAL_2_4,
    LEGACY_3_5,
    QualityPolicy,
    policy_constraints,
    select_gamma,
)
from lift import TriangularResidualKoopman


def _stats(value: float = 1.0) -> torch.Tensor:
    return torch.full((12, 4, 6), value, dtype=torch.float64)


def test_kr07_legacy_policy_is_bitwise_equivalent_to_frozen_constraints():
    from guard_core import constraints

    anchor = _stats()
    candidate = anchor.clone()
    candidate[1, 0, 0] = 1.01
    assert torch.equal(policy_constraints(candidate, anchor, LEGACY_3_5),
                       constraints(candidate, anchor))


def test_kr08_internal_margin_does_not_modify_legacy_policy():
    anchor = _stats()
    candidate = anchor.clone()
    candidate[1, 0, 0] = 1.025
    old = policy_constraints(candidate, anchor, LEGACY_3_5)
    new = policy_constraints(candidate, anchor, INTERNAL_2_4)
    assert old[7] <= 0 < new[7]
    assert LEGACY_3_5.scenario_limit == .03
    assert INTERNAL_2_4.scenario_limit == .02


def test_kr09_dense_gamma_selector_rejects_missing_and_nan_grid():
    rows = [dict(gamma=g, protected=True, finite=True, i20=6.0, m20=1-g/100)
            for g in INTERNAL_2_4.gamma_grid]
    with pytest.raises(ValueError, match="incomplete gamma grid"):
        select_gamma(rows[:-1], INTERNAL_2_4)
    broken = copy.deepcopy(rows)
    broken[3]["m20"] = float("nan")
    # A complete grid with a non-finite score must never silently become a candidate.
    with pytest.raises(ValueError, match="nonfinite gamma record"):
        select_gamma(broken, INTERNAL_2_4)


def test_kr04_kr05_gamma_zero_and_affine_state_identity():
    torch.manual_seed(17)
    model = TriangularResidualKoopman(torch.eye(47), torch.zeros(47, 11),
                                     torch.zeros(47), 16, 8, 16, input_dim=11).double()
    x = torch.randn(5, 47, dtype=torch.float64)
    u = torch.randn(5, 20, 11, dtype=torch.float64)
    original = model.E.detach().clone()

    def rollout(gamma: float):
        with torch.no_grad():
            model.E.copy_(gamma * original)
            return model.rollout(x, u, (1, 5, 10, 20))["xhat"].clone()

    p0, p1, p37 = rollout(0.0), rollout(1.0), rollout(.37)
    with torch.no_grad():
        model.E.copy_(original)
    pure = x[:, None, :].expand_as(p0)
    assert torch.allclose(p0, pure, atol=1e-12, rtol=1e-12)
    assert torch.allclose(p37, p0 + .37 * (p1 - p0), atol=1e-10, rtol=1e-8)


def test_kr06_force_must_not_be_linearly_interpolated():
    # Smooth free-play connector magnitude is nonlinear around engagement.
    free, width, stiffness = .01, .004, 4200.0
    distance = np.array([.009, .011, .013])
    penetration = np.maximum(distance-free, 0)
    ratio = np.clip(penetration/width, 0, 1)
    smooth = np.where(penetration <= 0, 0,
                      np.where(penetration >= width, 1, 3*ratio**2-2*ratio**3))
    velocity = .2
    force = stiffness*penetration + 120*smooth*velocity
    assert not np.isclose(force[1], .5*(force[0]+force[2]))


"""F2: equal-budget test (E10): ONE/MH/MHC/BCV share the same warm start
budget, the same maximum phase budget, and the same phase batch stream per
fold; no variant may run fewer steps."""

from __future__ import annotations

import numpy as np
import pytest
import torch


def test_all_variants_have_equal_budgets(protocol):
    f4 = protocol["f4"]
    assert f4["warm_steps"] == 2000
    for variant in f4["variants"]:
        assert f4["loss_specs"][variant] in {"one_step", "MH", "MHC", "BCV"}
    # second phase budget is the same maximum for every variant
    assert f4["phase_steps"] == 15000
    assert f4["max_total_steps"] == f4["warm_steps"] + f4["phase_steps"]


def test_same_fold_share_warm_and_stream_design(protocol):
    # The fold runner seeds the shared warm with central_seed+fold and the
    # phase stream with the same seed plus a fixed protocol offset, so all
    # variants in a fold see the identical batch stream.
    offset = int(protocol["f4"]["phase_sampler_seed_offset"])
    assert offset == 50000
    assert protocol["training"]["cv_seed"] == 990700
    assert protocol["training"]["central_seed"] == 990100


def test_loss_specs_share_batch_stream_shape(protocol):
    """step_loss must accept every loss spec on the same batch shape."""
    import torch

    from losses import group_slices_from_protocol
    from train import step_loss

    batch = {
        "x0": torch.zeros(8, 47),
        "u_seq": torch.zeros(8, 21, 7),
        "x_target": torch.zeros(8, 21, 47),
        "metadata": [{"scenario": "D0", "window_class": "steady", "start": 0, "trajectory_id": 0, "base_family_id": "f"} for _ in range(8)],
    }
    model = _dummy_model()
    weights = group_slices_from_protocol(protocol)
    for spec in ("one_step", "MH", "MHC", "BCV"):
        losses = step_loss(model, batch, protocol, spec, weights, closure_scale=0.1, tail_scale=0.25)
        assert torch.isfinite(losses["total"])
        assert set(losses["components"]) == {"main", "closure", "tail", "e_decay", "theta_decay"}
    # BCV tail members must be recoverable
    losses = step_loss(model, batch, protocol, "BCV", weights, 0.1, 0.25)
    assert losses["tail_indices"] is not None and losses["tail_indices"].numel() >= 1


def test_closure_and_tail_terms_flow_into_gradients(protocol):
    """E10 regression: auxiliary terms were added as .item() scalars, so
    MHC/BCV trained identically to MH.  The closure/tail terms must change
    the parameter gradient of the total objective."""
    import torch

    from losses import group_slices_from_protocol
    from train import step_loss

    torch.manual_seed(7)
    batch = {
        "x0": torch.randn(8, 47),
        "u_seq": torch.randn(8, 21, 7) * 0.1,
        "x_target": torch.randn(8, 21, 47) * 0.1,
        "metadata": [{"scenario": "D0", "window_class": "steady", "start": 0, "trajectory_id": 0, "base_family_id": "f"} for _ in range(8)],
    }
    weights = group_slices_from_protocol(protocol)

    def grad_for(spec, closure_scale, tail_scale):
        model = _dummy_model()
        losses = step_loss(model, batch, protocol, spec, weights, closure_scale=closure_scale, tail_scale=tail_scale)
        total = losses["total"]
        assert total.requires_grad
        grads = torch.autograd.grad(total, [p for p in model.parameters() if p.requires_grad])
        return torch.cat([g.detach().reshape(-1) for g in grads])

    g_mh = grad_for("MH", None, None)
    g_mhc = grad_for("MHC", 0.1, None)
    g_bcv = grad_for("BCV", 0.1, 0.25)
    assert g_mh.numel() > 0 and g_mhc.numel() > 0 and g_bcv.numel() > 0
    # closure term must alter the gradient vs plain MH
    assert not torch.allclose(g_mh, g_mhc, atol=1e-12), "closure term detached from gradients"
    # tail term must alter the gradient vs MHC
    assert not torch.allclose(g_mhc, g_bcv, atol=1e-12), "tail term detached from gradients"


def _dummy_model():
    from lift import TriangularResidualKoopman

    return TriangularResidualKoopman(
        torch.as_tensor(__import__("numpy").eye(47) * 0.9, dtype=torch.float64),
        torch.as_tensor(__import__("numpy").zeros((47, 7)), dtype=torch.float64),
        torch.as_tensor(__import__("numpy").zeros(47), dtype=torch.float64),
        residual_dim=16, branch_output=8, hidden_width=8,
    )

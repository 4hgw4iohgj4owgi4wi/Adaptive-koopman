"""SB2 tests for scenario balance (koopman_ab.md SB route).

Covers: weight math (equal/up, mean==1), no-future leakage (train labels only),
gradient divergence SB16 vs MH, bitwise identity when balancing disabled, and
equal-budget protocol assertions.  Uses synthetic data (no N5 access).
"""
from __future__ import annotations

import torch


class _FakeDataset:
    """Duck-typed FrozenSequenceDataset: scenario window counts only."""

    def __init__(self, counts: dict):
        self._counts = counts

    def scenario_window_counts(self) -> dict:
        return dict(self._counts)


def test_equal_scenario_weight_math(protocol):
    from train import build_scenario_weights

    counts = {"D1": 100, "D2": 400, "D10": 300, "D11": 200}
    out = build_scenario_weights(_FakeDataset(counts), protocol, "equal_scenario")
    n_total = sum(counts.values())
    # inverse-window proportionality: w_s / w_t == n_t / n_s
    for s in counts:
        for t in counts:
            if s != t:
                ratio = out["weights"][s] / out["weights"][t]
                assert abs(ratio - counts[t] / counts[s]) < 1e-9
    # window-share weighted mean == 1 (normalised)
    mean_w = sum((counts[s] / n_total) * out["weights"][s] for s in counts)
    assert abs(mean_w - 1.0) <= 1e-9
    assert out["mode"] == "equal_scenario"
    # base formula check on a full 12-scenario fold (no renormalisation shift)
    full = {f"D{i}": 100 for i in range(12)}
    out_full = build_scenario_weights(_FakeDataset(full), protocol, "equal_scenario")
    assert abs(out_full["weights"]["D1"] - 1200 / (12.0 * 100)) < 1e-12


def test_up_weight_d1_threefold(protocol):
    from train import build_scenario_weights

    counts = {"D1": 100, "D2": 400, "D10": 300, "D11": 200}
    sb = protocol["loss"]["scenario_balance"]
    up = sb["modes"]["up_weight"]
    assert up["scenarios"] == ["D1"]
    assert float(up["factor"]) == 3.0
    out = build_scenario_weights(_FakeDataset(counts), protocol, "up_weight")
    n_total = sum(counts.values())
    # relative ratio D1 vs D2 is 3x the equal-scenario ratio
    eq = build_scenario_weights(_FakeDataset(counts), protocol, "equal_scenario")
    ratio_up = out["weights"]["D1"] / out["weights"]["D2"]
    ratio_eq = eq["weights"]["D1"] / eq["weights"]["D2"]
    assert abs(ratio_up - 3.0 * ratio_eq) < 1e-9
    mean_check = sum((counts[s] / n_total) * out["weights"][s] for s in counts)
    assert abs(mean_check - 1.0) <= 1e-9


def test_weights_from_train_labels_only():
    """build_scenario_weights consumes only dataset.scenario_window_counts()"""
    import inspect

    from train import build_scenario_weights

    src = inspect.getsource(build_scenario_weights)
    assert "scenario_window_counts" in src
    assert "validation" not in src.lower() or "no future/validation info" in src


def test_equal_budget_protocol(protocol):
    sb = protocol["sb"]
    assert sb["warm_steps"] == 2000
    assert sb["phase_steps"] == 15000
    assert set(sb["variants"]) == {"SB16EQ", "SB16UP"}
    assert sb["variants"]["SB16EQ"]["balance_mode"] == "equal_scenario"
    assert sb["variants"]["SB16UP"]["balance_mode"] == "up_weight"


def _dummy_model():
    from lift import TriangularResidualKoopman

    import numpy as np

    return TriangularResidualKoopman(
        torch.as_tensor(np.eye(47) * 0.9, dtype=torch.float64),
        torch.as_tensor(np.zeros((47, 7)), dtype=torch.float64),
        torch.as_tensor(np.zeros(47), dtype=torch.float64),
        residual_dim=16, branch_output=8, hidden_width=8,
    )


def _batch(protocol, scenarios, with_weights, weights_map):
    n = len(scenarios)
    batch = {
        "x0": torch.randn(n, 47),
        "u_seq": torch.randn(n, 21, 7) * 0.1,
        "x_target": torch.randn(n, 21, 47) * 0.1,
        "metadata": [
            {"scenario": sc, "window_class": "maneuver", "start": 0, "trajectory_id": 0, "base_family_id": "f"}
            for sc in scenarios
        ],
    }
    if with_weights:
        batch["window_weights"] = torch.as_tensor(
            [weights_map[sc] for sc in scenarios], dtype=torch.float32)
    return batch


def test_disabled_balancing_bitwise_identical(protocol):
    """Batch without window_weights == plain v3r loss path (bitwise)."""
    from losses import group_slices_from_protocol
    from train import step_loss

    torch.manual_seed(3)
    scenarios = ["D1", "D2", "D1", "D10"] * 2
    weights = group_slices_from_protocol(protocol)
    model = _dummy_model()
    base = _batch(protocol, scenarios, with_weights=False, weights_map=None)
    b_plain = dict(base)
    b_weighted1 = dict(base)
    b_weighted1["window_weights"] = torch.as_tensor([1.0] * len(scenarios), dtype=torch.float32)
    out_plain = step_loss(model, b_plain, protocol, "MH", weights, None, None)
    out_w1 = step_loss(model, b_weighted1, protocol, "MH", weights, None, None)
    assert torch.equal(out_plain["total"].detach(), out_w1["total"].detach()), (
        "weighted path with ww=1 must be bitwise identical to the plain loss")


def test_sb16_gradient_differs_from_mh(protocol):
    """SB16 (window weights) must change the gradient vs plain MH (E10-style guard)."""
    from losses import group_slices_from_protocol
    from train import build_scenario_weights, step_loss

    torch.manual_seed(11)
    scenarios = ["D1", "D2", "D1", "D1", "D10", "D11", "D2", "D1"]
    counts = {"D1": 100, "D2": 400, "D10": 300, "D11": 200}
    sb_weights = build_scenario_weights(_FakeDataset(counts), protocol, "equal_scenario")
    weights = group_slices_from_protocol(protocol)

    def grad_for(with_ww):
        model = _dummy_model()
        b = _batch(protocol, scenarios, with_ww, sb_weights["weights"])
        total = step_loss(model, b, protocol, "MH", weights, None, None)["total"]
        grads = torch.autograd.grad(total, [p for p in model.parameters() if p.requires_grad])
        return torch.cat([g.detach().reshape(-1) for g in grads])

    g_mh = grad_for(False)
    g_sb = grad_for(True)
    assert g_mh.numel() > 0 and g_sb.numel() > 0
    assert not torch.allclose(g_mh, g_sb, atol=1e-12), "scenario balancing detached from gradients"

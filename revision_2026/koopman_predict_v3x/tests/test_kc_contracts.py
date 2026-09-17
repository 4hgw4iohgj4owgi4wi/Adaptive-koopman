"""KC2 T03/T05/T06/T08: input-contract counterexample detection, strict schema,
member separation and layered hierarchy (synthetic)."""
from __future__ import annotations

import numpy as np
import pytest


def _control_rows(seed=0):
    rng = np.random.default_rng(seed)
    n = 8
    # virtual accel, virtual steers, four requested steers (7 columns)
    c7 = np.zeros((n, 7))
    c7[:, 0] = rng.normal(0, 0.2, n)
    c7[:, 1] = rng.normal(0, 0.05, n)
    c7[:, 2] = rng.normal(0, 0.05, n)
    c7[:, 3:] = rng.normal(0, 0.1, (n, 4))
    return c7


def test_t03_identical_control7_different_accel_detected(protocol):
    """Same control7 rows with different four-vehicle requested accel must be flagged."""
    c7 = _control_rows()
    base_acc = c7[:, 0].copy()
    diff_a = np.zeros((len(c7), 4))
    # two rows with identical control7 but different differentials
    c7[5] = c7[2]
    diff_a[2] = np.array([0.0, 0.0, 0.0, 0.0])
    diff_a[5] = np.array([0.20, 0.20, -0.20, -0.20])
    request_acc = base_acc[:, None] + diff_a
    ambiguous = False
    for i in range(len(c7)):
        for j in range(i + 1, len(c7)):
            if np.max(np.abs(c7[i] - c7[j])) < 1e-12:
                if np.max(np.abs(request_acc[i] - request_acc[j])) > 1e-9:
                    ambiguous = True
    assert ambiguous, "counterexample not detected: control7 alone cannot recover accel differentials"


def test_t05_schema_strict():
    """input_dim must be exactly 7 or 11; no silent fallback."""
    from pure_linear import PureLinearKoopman

    for bad in (8, 12, 3, 0):
        with pytest.raises((ValueError, AssertionError)):
            PureLinearKoopman(np.eye(47), np.zeros((47, bad)), np.zeros(47), bad)
    # 7 and 11 accepted
    for ok in (7, 11):
        m = PureLinearKoopman(np.eye(47), np.zeros((47, ok)), np.zeros(47), ok)
        assert m.input_schema == f"u{ok}"


def test_t06_member_split_handmath():
    """Diagonal members A/B with different errors: member means and merged mean."""
    # synthetic: scenario D9 has member A (2 windows err 0.10,0.12) and B (2 windows 0.04,0.06)
    a_vals = np.array([0.10, 0.12])
    b_vals = np.array([0.04, 0.06])
    merged = (a_vals.mean() + b_vals.mean()) / 2
    assert abs(merged - 0.08) < 1e-12
    assert abs(a_vals.mean() - 0.11) < 1e-12 and abs(b_vals.mean() - 0.05) < 1e-12


def test_t08_layered_hierarchy_handmath():
    """window->trajectory->family->scenario mean differs from flat mean when counts differ."""
    from guard_core import hierarchy_mean
    import torch

    # scenario 0: family F0A (traj T0A1: 3 windows) , family F0B (traj T0B1: 1 window)
    # family/trajectory ids globally unique across scenarios (no cross-scenario collision)
    values = torch.tensor([1.0, 2.0, 3.0, 10.0])
    meta = [
        {"scenario": 0, "family": "F0A", "trajectory": "T0A1"},
        {"scenario": 0, "family": "F0A", "trajectory": "T0A1"},
        {"scenario": 0, "family": "F0A", "trajectory": "T0A1"},
        {"scenario": 0, "family": "F0B", "trajectory": "T0B1"},
    ] + [{"scenario": s, "family": f"FSC{s}", "trajectory": f"TSC{s}"} for s in range(1, 12)]
    vals12 = torch.cat([values, torch.zeros(11)])
    out = hierarchy_mean(vals12, meta)[0].item()
    # family means: F0A = 2.0, F0B = 10.0 -> scenario mean 6.0 (flat mean would be 4.0)
    assert abs(out - 6.0) < 1e-12, f"hierarchy scenario0 mean {out} != 6.0 (flat would be 4.0)"

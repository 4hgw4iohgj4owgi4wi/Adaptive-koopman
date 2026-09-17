from pathlib import Path

import numpy as np

from evaluation import design_matrix, macro_summary


def _normalization():
    return {
        "relative_state47_mean": np.zeros(47),
        "relative_state47_scale": np.ones(47),
        "actual_steering4_mean": np.zeros(4),
        "actual_steering4_scale": np.ones(4),
        "control7_mean": np.zeros(7),
        "control7_scale": np.ones(7),
    }


def _cache():
    return {
        "relative_state47": np.zeros((3, 47)),
        "actual_steering4": np.zeros((3, 4)),
        "control7": np.zeros((2, 7)),
        "analytic_actual_next4": np.zeros((2, 4)),
        "analytic_rate_mask4": np.zeros((2, 4)),
        "analytic_angle_mask4": np.zeros((2, 4)),
    }


def test_s0_s1_s2_target_dimensions_are_fair():
    expected = {"S0": 47, "S1": 51, "S2": 47}
    for variant, output_dimension in expected.items():
        _, target, layout = design_matrix(
            _cache(), variant, "M0_FIXED_LINEAR", _normalization()
        )
        assert target.shape == (2, output_dimension)
        assert layout["output_dimension"] == output_dimension
    _, _, s2 = design_matrix(_cache(), "S2", "M0_FIXED_LINEAR", _normalization())
    assert s2["side_dimension"] == 12


def test_common_macro_ignores_missing_s0_actuator_metric():
    rows = [
        {
            "horizon": 20,
            "scenario": scenario,
            "window": "steady",
            "j_common": value,
            "j_full": None,
            "divergent": False,
            "inference_s": 1e-5,
        }
        for scenario, value in (("D0", 1.0), ("D1", 3.0))
    ]
    summary = macro_summary(rows)
    assert summary["j_common_macro"] == 2.0


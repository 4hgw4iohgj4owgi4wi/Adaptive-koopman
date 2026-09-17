"""Baseline reproduction test: refit M0-S0 from frozen train caches and
regress it against the frozen N6 model (J20, parameter count, condition
number, fit row count)."""

from __future__ import annotations

from baselines import reproduce_m0_s0


def test_reproduce_m0_s0_passes(frozen, data, protocol):
    result = reproduce_m0_s0(frozen, data, protocol)
    assert result["passed"]
    regression = result["regression"]
    assert regression["coefficient_relative_error"] <= 1e-9
    assert regression["parameter_count_refitted"] == regression["parameter_count_frozen"]
    assert regression["fit_row_count_refitted"] == regression["fit_row_count_frozen"]
    assert regression["condition_number_error"] <= 1e-9 * max(abs(regression["condition_number_frozen"]), 1.0)
    assert regression["j20_common_abs_error"] <= float(protocol["p0_gates"]["s0_j20_common_abs_tolerance"])
    assert regression["j20_common_refitted"] > 0.0

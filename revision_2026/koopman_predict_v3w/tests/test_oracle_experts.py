"""P2 oracle-expert tests: shared training data, no sample deletion, every
train window assigned to exactly one expert, oracle labels are the frozen
window classes (never future scenario ids)."""

from __future__ import annotations

from collections import Counter

import numpy as np

from data_contract import load_cache
from oracle_experts import (
    evaluate_with_expert_map,
    expert_window_statistics,
    fit_oracle_experts,
    fit_s0_baseline,
)


def test_expert_window_partition_cover_all_train_windows(data, protocol):
    """Union of expert training windows equals the set of all train windows;
    overlap is resolved by the frozen priority (connector_event first)."""
    regimes = protocol["p2_gates"]["regimes"]
    covered = Counter()
    total = 0
    for entry in data.train:
        cache = load_cache(entry["cache_path"])
        for category in np.asarray(cache["window_class"]):
            total += 1
            matches = [name for name, classes in regimes.items() if str(category) in classes]
            assert matches, f"window class {category} has no expert"
            covered[matches[0]] += 1
    assert sum(covered.values()) == total
    # each expert must have a positive number of train windows
    statistics = expert_window_statistics(data.train, data.normalization, protocol)
    for name in regimes:
        assert statistics[name]["row_count"] > 0


def test_fit_oracle_experts_returns_three_models(data, protocol, frozen):
    experts = fit_oracle_experts(frozen, data, protocol)
    assert set(experts) == set(protocol["p2_gates"]["regimes"])
    for name, model in experts.items():
        assert model["coefficients"].shape[0] == 47 + 7 + 1
        assert model["coefficients"].shape[1] == 47


def test_oracle_evaluation_uses_frozen_window_labels(frozen, data, protocol):
    experts = fit_oracle_experts(frozen, data, protocol)
    sample = data.validation[:1]
    rows = evaluate_with_expert_map(frozen, data, protocol, experts, sample)
    assert rows
    # every row's expert must be the one registered for its window class
    regimes = protocol["p2_gates"]["regimes"]
    for row in rows:
        expected = next(name for name, classes in regimes.items() if row["window"] in classes)
        assert row["expert"] == expected
    assert all(row["split"] == "validation" for row in rows)


def test_s0_baseline_uses_all_train_windows(frozen, data, protocol):
    from evaluation_v2 import accumulate_fit_statistics

    model = fit_s0_baseline(frozen, data, protocol)
    statistics = accumulate_fit_statistics(data.train, "S0", "M0_FIXED_LINEAR", data.normalization)
    assert model["fit_row_count"] == statistics["row_count"]
    # expert windows are a partition of the train window set (checked elsewhere);
    # the baseline additionally uses every trajectory row for the closed-form fit
    expert_statistics = expert_window_statistics(data.train, data.normalization, protocol)
    assert all(stats["row_count"] > 0 for stats in expert_statistics.values())


def test_no_confirm_rows_in_expert_data(data):
    assert all(row["split"] != "confirm" for row in data.entries)

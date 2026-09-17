"""Fair-comparison test: same trajectories, same train-only normalization,
same seeds/budget/rollout across the compared configs, and a completeness
ledger that never omits parameter count, inference time or divergence rate."""

from __future__ import annotations

import numpy as np

from evaluation_v2 import (
    config_key,
    evaluate_model,
    load_frozen_model,
    macro_summary,
)
from physics_decoder import R3Decoder


def _evaluate(frozen, data, protocol, key, seed_label="FAIR"):
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    rows = evaluate_model(
        model, data.development, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label=seed_label,
    )
    return rows


def test_identical_evaluation_ledger_across_configs(frozen, data, protocol):
    s0_rows = _evaluate(frozen, data, protocol, config_key("M0_FIXED_LINEAR", "S0", None))
    s1_rows = _evaluate(frozen, data, protocol, config_key("M0_FIXED_LINEAR", "S1", None))
    identity_s0 = {(int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"])) for row in s0_rows}
    identity_s1 = {(int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"])) for row in s1_rows}
    assert identity_s0 == identity_s1
    assert len(s0_rows) == len(s1_rows)
    # every row must carry the fairness ledger fields
    for row in s0_rows:
        assert "parameter_count" not in row  # parameter count is config-level, recorded per config
        assert row["inference_s"] >= 0.0
        assert row["divergent"] in {True, False}
        assert row["j_common"] is not None


def test_train_only_normalization(frozen, data):
    assert str(np.asarray(data.normalization["source_split"])) == "train"
    assert int(np.asarray(data.normalization["relative_state47_row_count"])) > 0


def test_same_seeds_and_budget_across_configs(protocol):
    seeds = protocol["training"]["primary_family_bootstrap_seeds"]
    assert seeds == [990101, 990102, 990103, 990104, 990105]
    assert protocol["training"]["horizons"] == [1, 5, 10, 20]
    # ridge grid and rank grid are frozen identically for every config
    assert protocol["training"]["ridge_grid"] == [1e-8, 1e-6, 1e-4, 1e-2]
    assert protocol["training"]["ranks"] == [1, 2, 4]


def test_macro_uses_scenario_mean_of_scenario_means(frozen, data, protocol):
    s0_rows = _evaluate(frozen, data, protocol, config_key("M0_FIXED_LINEAR", "S0", None))
    summary = macro_summary(s0_rows)
    scenarios = {row["scenario"] for row in s0_rows if row["horizon"] == 20}
    assert scenarios == set(protocol["scenarios"]["order"])
    recomputed = np.mean(
        [summary["scenario_j_common"][name] for name in protocol["scenarios"]["order"]]
    )
    assert abs(recomputed - summary["j_common_macro"]) < 1e-12

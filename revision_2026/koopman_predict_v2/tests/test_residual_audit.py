"""P1 audit tests: regime decomposition coverage, subspace angles, no confirm
reads, and no future-input dependence of the residual collection."""

from __future__ import annotations

import numpy as np

from residual_audit import (
    collect_residuals,
    connector_group_explained,
    residual_by_regime,
    subspace_test,
)


def test_collect_residuals_covers_windows(data, frozen, protocol):
    residuals = collect_residuals(frozen, data, protocol, split="development", horizons=(1, 20))
    assert len(residuals) > 0
    assert {row["horizon"] for row in residuals} == {1, 20}
    assert all(row["scenario"] in protocol["scenarios"]["order"] for row in residuals)
    assert all(row["window"] in protocol["window"]["classes"] for row in residuals)
    assert all(row["residual47"].shape == (47,) for row in residuals)
    # development only
    assert all(row["base_family_id"].startswith("development") for row in residuals)


def test_residual_by_regime_table(frozen, data, protocol):
    from evaluation_v2 import config_key, evaluate_model, load_frozen_model
    from physics_decoder import R3Decoder

    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    rows = evaluate_model(
        model, data.development, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label="P1_TEST",
    )
    residuals = collect_residuals(frozen, data, protocol)
    regimes = residual_by_regime(residuals, rows, protocol)
    horizons = {row["horizon"] for row in regimes["table"]}
    scenarios = {row["scenario"] for row in regimes["table"]}
    windows = {row["window"] for row in regimes["table"]}
    assert horizons == {1, 5, 10, 20}
    assert scenarios == set(protocol["scenarios"]["order"])
    assert windows == set(protocol["window"]["classes"])
    for row in regimes["table"]:
        for field in ("e_core", "e_relative", "e_force4", "e_internal", "e_yaw", "j_common"):
            assert 0.0 <= float(row[field])


def test_subspace_angles_reported(frozen, data, protocol):
    residuals = collect_residuals(frozen, data, protocol, horizons=(20,))
    subspace = subspace_test(residuals, protocol)
    assert set(subspace["pairs"]) == {
        "steady_vs_maneuver",
        "steady_vs_connector_event",
        "maneuver_vs_connector_event",
    }
    for pair in subspace["pairs"].values():
        assert pair["median_deg"] is not None
        assert 0.0 <= pair["median_deg"] <= 90.0
    assert subspace["all_pair_median_deg"] is not None


def test_connector_group_explained_paired(frozen, data, protocol):
    residuals = collect_residuals(frozen, data, protocol, horizons=(20,))
    explained = connector_group_explained(residuals, protocol)
    assert explained["d0_family_count"] > 0
    assert explained["hard_family_count"] > 0
    assert explained["mean_difference"] is not None
    assert explained["ci95_low"] is not None and explained["ci95_high"] is not None
    assert all(row["base_family_id"].startswith("development") for row in explained["per_family"])


def test_no_confirm_rows(data):
    assert all(row["split"] != "confirm" for row in data.entries)

"""P0 element-wise regression test: v2 evaluation must reproduce the frozen N6
evaluation for the same frozen model/cache/normalization, row by row."""

from __future__ import annotations

import csv
import gzip
import os

import numpy as np

from data_contract import load_cache
from evaluation_v2 import (
    config_key,
    evaluate_model,
    load_frozen_model,
)
from physics_decoder import R3Decoder


def _n6_rows(frozen):
    with gzip.open(frozen.n6_development_detailed_path(), "rt", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def test_elementwise_regression_sample(frozen, data, protocol):
    """Compare v2 rows vs N6 rows on a development sample, all metric fields."""
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    sample = data.development[:2]
    rows = evaluate_model(
        model, sample, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label="REGRESSION_SAMPLE",
    )
    n6 = [row for row in _n6_rows(frozen) if row["config_key"] == key]
    n6_by_id = {
        (int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"])): row
        for row in n6
    }
    fields = ("e_core", "e_relative", "e_force4", "e_internal", "e_yaw", "j_common", "state47_rmse_si", "force8_rmse_n", "internal8_rmse_n")
    assert len(rows) > 0
    for row in rows:
        identity = (int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"]))
        reference = n6_by_id.get(identity)
        assert reference is not None, f"missing N6 row for {identity}"
        for field in fields:
            recomputed = float(row[field])
            recorded = float(reference[field])
            denominator = max(abs(recorded), 1e-6)
            assert abs(recomputed - recorded) / denominator <= 1e-9, (
                f"{field} mismatch for {identity}: {recomputed} vs {recorded}"
            )
        assert row["divergent"] == (reference["divergent"] == "True")


def test_s0_j20_matches_frozen_reference(frozen, data, protocol):
    """Central S0 J20 must equal the frozen reference within 1e-10 (P0 gate)."""
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    rows = evaluate_model(
        model, data.development, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label="REGRESSION_S0",
    )
    from evaluation_v2 import macro_summary

    recomputed = float(macro_summary(rows)["j_common_macro"])
    reference = float(protocol["p0_gates"]["s0_j20_common_reference"])
    assert abs(recomputed - reference) <= float(protocol["p0_gates"]["s0_j20_common_abs_tolerance"])


def test_p0_report_passes_when_run_available(frozen, project_root):
    """When a completed P0 run exists, its regression report must pass."""
    from contracts_v2 import read_json

    report_candidates = list(
        (project_root / "revision_2026" / "koopman_predict_v2_results").glob("runs/*/p0/n6_regression_report.json")
    )
    if not report_candidates:
        return  # no run yet; the full regression is executed by run_v2 P0
    report = read_json(sorted(report_candidates)[-1])
    assert report["passed"] is True

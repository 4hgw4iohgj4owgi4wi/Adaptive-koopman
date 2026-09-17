"""No-future-leakage test: tampering future measurements must not change the
causal input digest of the current row, for S0, S1, S2 and the A3 analytic
side information."""

from __future__ import annotations

import numpy as np

from data_contract import causal_input_digest_variant, load_cache
from evaluation_v2 import _normalized_state_target, design_matrix


def _cache_and_index(data):
    entry = data.train[0]
    cache = load_cache(entry["cache_path"])
    index = int(np.asarray(cache["window_start"])[0])
    return cache, index


def test_s0_digest_unchanged_by_future_tampering(data):
    cache, index = _cache_and_index(data)
    baseline = causal_input_digest_variant(cache, index, "S0")
    tampered = dict(cache)
    tampered["relative_state47"] = np.asarray(cache["relative_state47"], dtype=float).copy()
    tampered["relative_state47"][index + 1 :] += 1.0
    tampered["control7"] = np.asarray(cache["control7"], dtype=float).copy()
    tampered["control7"][index + 1 :] += 1.0
    assert causal_input_digest_variant(tampered, index, "S0") == baseline
    # current-row tampering must change the digest
    tampered_current = dict(cache)
    tampered_current["relative_state47"] = np.asarray(cache["relative_state47"], dtype=float).copy()
    tampered_current["relative_state47"][index] += 1.0
    assert causal_input_digest_variant(tampered_current, index, "S0") != baseline


def test_s1_digest_unchanged_by_future_actuator_tampering(data):
    cache, index = _cache_and_index(data)
    baseline = causal_input_digest_variant(cache, index, "S1")
    tampered = dict(cache)
    tampered["actual_steering4"] = np.asarray(cache["actual_steering4"], dtype=float).copy()
    tampered["actual_steering4"][index + 1 :] += 1.0
    assert causal_input_digest_variant(tampered, index, "S1") == baseline


def test_s2_digest_covers_analytic_side_only(data):
    cache, index = _cache_and_index(data)
    baseline = causal_input_digest_variant(cache, index, "S2")
    tampered = dict(cache)
    tampered["relative_state47"] = np.asarray(cache["relative_state47"], dtype=float).copy()
    tampered["relative_state47"][index + 1 :] += 1.0
    tampered["actual_steering4"] = np.asarray(cache["actual_steering4"], dtype=float).copy()
    tampered["actual_steering4"][index + 1 :] += 1.0
    tampered["analytic_actual_next4"] = np.asarray(cache["analytic_actual_next4"], dtype=float).copy()
    tampered["analytic_actual_next4"][index + 1 :] += 1.0
    assert causal_input_digest_variant(tampered, index, "S2") == baseline
    # current analytic side is part of the input: tampering it changes the digest
    tampered_side = dict(cache)
    tampered_side["analytic_actual_next4"] = np.asarray(cache["analytic_actual_next4"], dtype=float).copy()
    tampered_side["analytic_actual_next4"][index] += 1.0
    assert causal_input_digest_variant(tampered_side, index, "S2") != baseline


def test_rollout_prediction_does_not_read_future_rows(data, frozen, protocol):
    """A h-step rollout may only read cache rows <= start+h-1 as inputs; the
    evaluation target is the row at start+h.  Mutating rows beyond the horizon
    must not change the prediction at horizon h."""
    from evaluation_v2 import load_frozen_model, rollout_model

    entry = data.train[0]
    cache = load_cache(entry["cache_path"])
    index = int(np.asarray(cache["window_start"])[0])
    model = load_frozen_model(frozen.n6_models_dir() / "M0_FIXED_LINEAR_S0_none_FULL_TRAIN.npz")
    normalization = data.normalization
    horizon = 5
    prediction, _, _ = rollout_model(model, cache, index, horizon, normalization, protocol)
    tampered = dict(cache)
    tampered["relative_state47"] = np.asarray(cache["relative_state47"], dtype=float).copy()
    tampered["relative_state47"][index + horizon :] += 100.0
    tampered["control7"] = np.asarray(cache["control7"], dtype=float).copy()
    tampered["control7"][index + horizon :] += 100.0
    prediction_tampered, _, _ = rollout_model(model, tampered, index, horizon, normalization, protocol)
    assert np.allclose(prediction, prediction_tampered, rtol=0.0, atol=0.0)


def test_design_matrix_uses_only_current_and_previous_rows(data):
    cache = load_cache(data.train[0]["cache_path"])
    state, control, side, target = _normalized_state_target(cache, "S0", data.normalization)
    assert state.shape[0] == control.shape[0] == target.shape[0] == len(cache["relative_state47"]) - 1
    assert side.shape[1] == 0

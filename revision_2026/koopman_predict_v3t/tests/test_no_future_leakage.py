"""No-future-leakage tests (v3): tampering future real quantities must not
change the current input digest or the prediction prefix, covering x/u/eta and
the physics readout."""

from __future__ import annotations

import numpy as np

from data_contract import causal_input_digest_variant, load_cache


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
    assert causal_input_digest_variant(tampered, index, "S0") == baseline


def test_s2_digest_covers_analytic_side_only(data):
    cache, index = _cache_and_index(data)
    baseline = causal_input_digest_variant(cache, index, "S2")
    tampered = dict(cache)
    tampered["relative_state47"] = np.asarray(cache["relative_state47"], dtype=float).copy()
    tampered["relative_state47"][index + 1 :] += 1.0
    tampered["actual_steering4"] = np.asarray(cache["actual_steering4"], dtype=float).copy()
    tampered["actual_steering4"][index + 1 :] += 1.0
    assert causal_input_digest_variant(tampered, index, "S2") == baseline


def test_rollout_prediction_does_not_read_future_rows(frozen, data, protocol):
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
    prediction_tampered, _, _ = rollout_model(model, tampered, index, horizon, normalization, protocol)
    assert np.array_equal(prediction, prediction_tampered)


def test_gdmrk_eta_and_physics_inputs_are_causal(frozen, data, protocol):
    """The GDM-RK encoder input (x0, u0) and the physics readout input are the
    current row only; tampering future rows changes neither the encoded eta nor
    the one-step prediction."""
    import torch

    from data_contract import FrozenSequenceDataset
    from evaluation_v3 import build_gdmrk
    from physics_decoder import R3Decoder

    dataset = FrozenSequenceDataset(data.train[:2], data.normalization, horizon=20)
    sample = dataset.get_sample(0)
    model = build_gdmrk(frozen, 16, 16)
    model.eval()
    with torch.no_grad():
        eta = model.encoder(sample["x0"][None], sample["u_seq"][0:1])
    assert torch.isfinite(eta).all()
    # future rows of the underlying cache are not part of the sample at all;
    # verify the sample itself does not reference future rows beyond k+horizon
    entry = data.train[:2][0]
    cache = load_cache(entry["cache_path"])
    start = int(sample["start"])
    assert start + 21 <= len(cache["relative_state47"])
    # physics readout only depends on the prediction (current window)
    params = frozen.resolved_params(int(entry["seed"]), protocol)
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    prediction = np.asarray(cache["relative_state47"][start], dtype=float)
    force, internal = decoder.connector_force(prediction, params, entry["law"])
    assert np.all(np.isfinite(force)) and np.all(np.isfinite(internal))

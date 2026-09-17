"""P5 gate fault-injection tests: every P5C gate must REJECT a crafted failure
mode, so a stage PASS can never be confused with a candidate that actually
passes; plus S1 structural gates (E=0 S0 regression, damped spectrum,
frozen S0 blocks, dataset containment)."""

from __future__ import annotations

import numpy as np

from data_contract import FrozenSequenceDataset, load_cache
from evaluation_v3 import build_gdmrk, compute_p5c_gates, s0_blocks_from_frozen


def _row(horizon, scenario, window_start, j_common, family="dev_X_988000", divergent=False, force=10.0, internal=10.0, window="steady"):
    return {
        "horizon": int(horizon),
        "scenario": scenario,
        "window_start": int(window_start),
        "window": window,
        "j_common": float(j_common),
        "divergent": bool(divergent),
        "base_family_id": family,
        "force8_rmse_n": float(force),
        "internal8_rmse_n": float(internal),
    }


def _make_rows(protocol, j_macro=None, j_scenarios=None, j_hard=None, divergent=False, force=10.0, internal=10.0):
    """Synthetic candidate rows covering all scenarios/windows/horizons."""
    rows = []
    j_macro = j_macro if j_macro is not None else 0.12
    j_scenarios = j_scenarios if j_scenarios is not None else {"D7": 0.11, "D10": 0.115}
    j_hard = j_hard if j_hard is not None else 0.16
    for scenario in protocol["scenarios"]["order"]:
        value = j_scenarios.get(scenario, j_macro)
        for start in range(0, 400, 20):
            rows.append(_row(1, scenario, start, value))
            rows.append(_row(5, scenario, start, value))
            rows.append(_row(10, scenario, start, value))
            rows.append(_row(20, scenario, start, value if scenario != "D5" or start not in (100, 120) else j_hard, divergent=divergent))
    return rows


def _s0_rows(protocol, j_macro=0.1278, d5_hard=0.1649):
    rows = []
    for scenario in protocol["scenarios"]["order"]:
        for start in range(0, 400, 20):
            for horizon in (1, 5, 10, 20):
                value = d5_hard if scenario == "D5" and start in (100, 120) and horizon == 20 else j_macro
                rows.append(_row(horizon, scenario, start, value))
    return rows


def test_all_gates_pass_for_good_candidate(protocol):
    candidate = _make_rows(protocol, j_macro=0.12, j_hard=0.15)
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, report = compute_p5c_gates(protocol, candidate, s0, stress={"summary": {"divergent_count": 0}}, timing={"gpu_median_ms": 0.3, "gpu_p99_ms": 0.8, "cpu_median_ms": 2.0})
    assert all(gates.values()), gates


def test_macro_gate_rejects_weak_candidate(protocol):
    candidate = _make_rows(protocol, j_macro=0.125)  # < 5% improvement
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, None, None)
    assert gates["validation_macro_improvement"] is False


def test_d5_hard_gate_rejects_degraded_hard_windows(protocol):
    candidate = _make_rows(protocol, j_macro=0.12, j_hard=0.20)  # hard windows too bad
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, None, None)
    assert gates["d5_hard_mean"] is False


def test_divergence_gate_rejects_divergent_rows(protocol):
    candidate = _make_rows(protocol, j_macro=0.12, divergent=True)
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, None, None)
    assert gates["divergence_zero"] is False


def test_stress_gate_rejects_new_divergence(protocol):
    candidate = _make_rows(protocol, j_macro=0.12)
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, {"summary": {"divergent_count": 3}}, None)
    assert gates["d5_stress_no_divergence"] is False


def test_d7_d10_gate_rejects_no_hard_gain(protocol):
    candidate = _make_rows(protocol, j_macro=0.12, j_scenarios={"D7": 0.31, "D10": 0.30})
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, None, None)
    assert gates["d7_or_d10_improvement"] is False


def test_timing_gate_rejects_slow_inference(protocol):
    candidate = _make_rows(protocol, j_macro=0.12)
    s0 = _s0_rows(protocol, j_macro=0.1278)
    gates, _ = compute_p5c_gates(protocol, candidate, s0, None, {"gpu_median_ms": 5.0, "gpu_p99_ms": 9.0, "cpu_median_ms": 20.0})
    assert gates["gpu_inference_median"] is False
    assert gates["cpu_inference_median"] is False


def test_e_zero_s0_elementwise_regression(frozen, data, protocol):
    """E=0 -> xhat = A0 x + B0 u + b0 matches the frozen S0 rollout to 1e-10."""
    import torch

    from evaluation_v2 import rollout_model
    from evaluation_v3 import build_gdmrk

    model = build_gdmrk(frozen, 16, 16)
    with torch.no_grad():
        model.E.zero_()
    model.double()
    model.eval()
    entry = data.development[0]
    cache = load_cache(entry["cache_path"])
    start = int(np.asarray(cache["window_start"])[0])
    normalization = data.normalization
    s0_key = "M0_FIXED_LINEAR|S0|none"
    from evaluation_v2 import load_frozen_model

    s0_model = load_frozen_model(frozen.n6_models_dir() / "M0_FIXED_LINEAR_S0_none_FULL_TRAIN.npz")
    for horizon in (1, 5, 10, 20):
        prediction_s0, _, _ = rollout_model(s0_model, cache, start, horizon, normalization, protocol)
        x0 = torch.as_tensor((np.asarray(cache["relative_state47"][start], dtype=np.float64) - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"], dtype=torch.float64)[None]
        u = torch.as_tensor((np.asarray(cache["control7"][start : start + horizon], dtype=np.float64) - normalization["control7_mean"]) / normalization["control7_scale"], dtype=torch.float64)[None]
        with torch.no_grad():
            with torch.no_grad():
                rollout = model.rollout(x0, u, (horizon,))
            pred_n = rollout["xhat"][0, horizon - 1]
        prediction = pred_n.numpy() * normalization["relative_state47_scale"] + normalization["relative_state47_mean"]
        assert np.max(np.abs(prediction - prediction_s0)) <= 1e-10, f"horizon {horizon} E=0 regression failed"


def test_damped_spectrum_and_block_triangular(frozen, data, protocol):
    import torch

    from stability import triangular_spectrum

    model = build_gdmrk(frozen, 16, 16)
    with torch.no_grad():
        for param in model.parameters():
            param.fill_(0.0)  # F radius 0; E=0 so K = blockdiag(A0, F)
    spectrum = triangular_spectrum(model)
    assert spectrum["spectrum_membership_max_error"] <= 1e-8
    assert spectrum["spectral_radius_max_residual"] is not None and spectrum["spectral_radius_max_residual"] < 0.995


def test_frozen_s0_blocks_require_grad_false_and_sha_stable(frozen, data, protocol):
    import hashlib

    import torch

    from evaluation_v3 import build_gdmrk

    model = build_gdmrk(frozen, 16, 16)

    def digest(model):
        digest = hashlib.sha256()
        for name in ("A0", "B0", "b0"):
            digest.update(np.ascontiguousarray(getattr(model, name).detach().cpu().numpy()).tobytes())
        return digest.hexdigest()

    before = digest(model)
    assert not model.A0.requires_grad and not model.B0.requires_grad and not model.b0.requires_grad
    # run a dummy training step
    optimizer = torch.optim.AdamW([param for param in model.parameters() if param.requires_grad], lr=1e-3)
    dataset = FrozenSequenceDataset(data.train[:1], data.normalization, horizon=20)
    sample = dataset.get_sample(0)
    loss = torch.mean(model.rollout(sample["x0"][None], sample["u_seq"][:1][None], (1,))["xhat"])
    loss.backward()
    optimizer.step()
    after = digest(model)
    assert before == after


def test_dataset_no_cross_trajectory_or_family(data, protocol):
    dataset = FrozenSequenceDataset(data.train[:4], data.normalization, horizon=20)
    entries_by_id = {row["trajectory_id"]: row for row in data.train[:4]}
    for index in range(min(50, len(dataset))):
        sample = dataset.get_sample(index)
        trajectory_index, start = dataset._sample_index[index]
        trajectory = dataset._trajectories[trajectory_index]
        entry = entries_by_id[int(trajectory["entry"]["trajectory_id"])]
        assert sample["base_family_id"] == entry["base_family_id"]
        assert start + 21 <= trajectory["length"]

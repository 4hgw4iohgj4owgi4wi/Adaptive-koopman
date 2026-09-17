"""P3 bilinear diagnosis tests: N=0 ablation, control permutation sensitivity,
one-step regression recovery on synthetic systems (via temp NPZ caches), and
B0 reproduction of the frozen N6 rank-1 model (fit-level only)."""

from __future__ import annotations

import numpy as np

from bilinear_diag import _als_rank_r, fit_full_bilinear, reproduce_rank1_b0


def _write_synthetic_caches(protocol, state_dim=47, control_dim=7, length=200, seed=1):
    """Build temp NPZ caches whose one-step map encodes a known system
    y = A x + B u + c + sum_j u_j N_j x."""
    import json
    import tempfile
    from pathlib import Path

    rng = np.random.default_rng(seed)
    a = rng.normal(size=(state_dim, state_dim)) * 0.05
    b = rng.normal(size=(state_dim, control_dim)) * 0.05
    c = rng.normal(size=state_dim) * 0.01
    n = rng.normal(size=(control_dim, state_dim, state_dim)) * 0.001
    base_family = "synthetic_family"
    tmp = Path(tempfile.mkdtemp(prefix="v2_synth_"))
    entries = []
    x_prev = rng.normal(size=state_dim) * 0.5
    for trajectory_id in range(3):
        x = np.zeros((length, state_dim))
        u = np.zeros((length - 1, control_dim))
        x[0] = x_prev
        for t in range(length - 1):
            u_t = rng.normal(size=control_dim) * 0.5
            u[t] = u_t
            y = a @ x[t] + b @ u_t + c
            for j in range(control_dim):
                y = y + u_t[j] * (n[j] @ x[t])
            x[t + 1] = y
        cache_path = tmp / f"syn_{trajectory_id}.npz"
        np.savez(
            cache_path,
            relative_state47=x,
            actual_steering4=np.zeros((length, 4)),
            control7=u,
        )
        entries.append(
            {
                "trajectory_id": trajectory_id,
                "base_family_id": f"{base_family}_{trajectory_id}",
                "cache_path": str(cache_path),
                "split": "train",
                "scenario": "D0",
                "seed": seed,
                "law": "V1",
            }
        )
    return entries, a, b, c, n, tmp


class _SyntheticData:
    def __init__(self, entries, normalization):
        self.train = entries
        self.normalization = normalization
        self.validation = entries
        self.development = entries


def _synthetic_data(protocol):
    entries, _, _, _, _, tmp = _write_synthetic_caches(protocol)
    normalization = {
        "relative_state47_mean": np.zeros(47),
        "relative_state47_scale": np.ones(47),
        "actual_steering4_mean": np.zeros(4),
        "actual_steering4_scale": np.ones(4),
        "control7_mean": np.zeros(7),
        "control7_scale": np.ones(7),
        "force_payload_body8_mean": np.zeros(8),
        "force_payload_body8_scale": np.ones(8),
        "internal_force8_mean": np.zeros(8),
        "internal_force8_scale": np.ones(8),
        "source_split": np.asarray("train"),
    }
    return _SyntheticData(entries, normalization), tmp


class _FakeFrozen:
    """Stub satisfying the parts of FrozenN6 used by the fit paths."""

    def __init__(self):
        self.n6_models_dir = None  # not used by synthetic tests

    def resolved_params(self, seed, protocol):
        return None

    def build_planar_grasp_matrix(self, anchor_body):
        import numpy as np

        r = np.asarray(anchor_body, float)
        g = np.zeros((3, 8))
        g[0, 0::2] = 1.0
        g[1, 1::2] = 1.0
        g[2, 0::2] = -r[:, 1]
        g[2, 1::2] = r[:, 0]
        return g


def test_full_bilinear_one_step_recovers_known_system(protocol):
    data, tmp = _synthetic_data(protocol)
    try:
        model = fit_full_bilinear(_FakeFrozen(), data, protocol, 1e-12)
        coefficients = model["coefficients"]
        start = 47 + 7
        # coefficients order in the design is [state, control, bilinear, bias]
        # -> bias column is last, but for S0 output dim 47 the matrix is (47+7+329+1) x 47
        _, a, b, c, n, _ = _write_synthetic_caches(protocol)
        recovered_a = coefficients[:47, :47].T
        recovered_b = coefficients[47:54, :].T
        recovered_c = coefficients[54 + 47 * 7, :]  # bias is the last design column
        assert np.allclose(recovered_a, a, atol=1e-4)
        assert np.allclose(recovered_b, b, atol=1e-4)
        assert np.allclose(recovered_c, c, atol=1e-4)
        for j in range(7):
            recovered_n = coefficients[start + j * 47 : start + (j + 1) * 47].T
            assert np.allclose(recovered_n, n[j], atol=1e-3), f"N_{j} not recovered"
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_zero_ablation_equals_linear_part(protocol):
    """Zeroing the bilinear block makes predictions identical to the pure
    linear model built from the same linear coefficients."""
    from evaluation_v2 import rollout_model
    from data_contract import load_cache

    data, tmp = _synthetic_data(protocol)
    try:
        cache = load_cache(data.train[0]["cache_path"])
        model = fit_full_bilinear(_FakeFrozen(), data, protocol, 1e-6)
        linear_only = np.array(model["coefficients"], dtype=float, copy=True)
        linear_only[47 + 7 : 47 + 7 + 47 * 7] = 0.0
        linear_model = dict(model)
        linear_model["coefficients"] = linear_only
        zeroed = dict(model)
        zeroed_coefficients = np.array(model["coefficients"], dtype=float, copy=True)
        zeroed_coefficients[47 + 7 : 47 + 7 + 47 * 7] = 0.0
        zeroed["coefficients"] = zeroed_coefficients
        start = 0
        zeroed_prediction, _, _ = rollout_model(zeroed, cache, start, 3, data.normalization, protocol)
        linear_prediction, _, _ = rollout_model(linear_model, cache, start, 3, data.normalization, protocol)
        assert np.array_equal(zeroed_prediction, linear_prediction)
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_control_permutation_changes_bilinear_output(protocol):
    """Permuting the control sequence changes the bilinear term's output when
    controls vary (synthetic controls are non-constant)."""
    from evaluation_v2 import rollout_model
    from data_contract import load_cache

    data, tmp = _synthetic_data(protocol)
    try:
        cache = load_cache(data.train[0]["cache_path"])
        model = fit_full_bilinear(_FakeFrozen(), data, protocol, 1e-6)
        rng = np.random.default_rng(11)
        order = rng.permutation(cache["control7"].shape[0])
        modified = dict(cache)
        modified["control7"] = np.asarray(cache["control7"], dtype=float)[order]
        base_prediction, _, _ = rollout_model(model, cache, 0, 3, data.normalization, protocol)
        permuted_prediction, _, _ = rollout_model(model, modified, 0, 3, data.normalization, protocol)
        assert np.max(np.abs(base_prediction - permuted_prediction)) > 1e-9
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


def test_als_rank1_recovers_low_rank_system(protocol):
    """ALS rank-1 must recover a synthetic rank-1 bilinear N_j."""
    import shutil

    rng = np.random.default_rng(13)
    u = rng.normal(size=(47, 1)) * 0.1
    v = rng.normal(size=(47, 1)) * 0.1
    n_true = np.asarray([u @ v.T for _ in range(7)])

    entries, a, b, c, _, tmp = _write_synthetic_caches(protocol, seed=13)
    # rewrite caches with a rank-1 N_j
    from pathlib import Path

    for entry in entries:
        path = Path(entry["cache_path"])
        with np.load(path, allow_pickle=False) as archive:
            x = np.asarray(archive["relative_state47"], dtype=float).copy()
            uu = np.asarray(archive["control7"], dtype=float).copy()
        length = x.shape[0]
        for t in range(length - 1):
            y = a @ x[t] + b @ uu[t] + c
            for j in range(7):
                y = y + uu[t, j] * (n_true[j] @ x[t])
            x[t + 1] = y
        np.savez(path, relative_state47=x, actual_steering4=np.zeros((length, 4)), control7=uu)
    normalization = {
        "relative_state47_mean": np.zeros(47),
        "relative_state47_scale": np.ones(47),
        "actual_steering4_mean": np.zeros(4),
        "actual_steering4_scale": np.ones(4),
        "control7_mean": np.zeros(7),
        "control7_scale": np.ones(7),
        "force_payload_body8_mean": np.zeros(8),
        "force_payload_body8_scale": np.ones(8),
        "internal_force8_mean": np.zeros(8),
        "internal_force8_scale": np.ones(8),
        "source_split": np.asarray("train"),
    }
    data = _SyntheticData(entries, normalization)
    try:
        model = _als_rank_r(_FakeFrozen(), data, protocol, 1e-6, 1, iterations=80)
        coefficients = model["coefficients"]
        assert np.all(np.isfinite(coefficients))
        assert np.isfinite(model["als_objective"])
        start = 47 + 7
        for j in range(7):
            block = coefficients[start + j * 47 : start + (j + 1) * 47].T
            singular = np.linalg.svd(block, compute_uv=False)
            # rank-1 by construction: the second singular value is numerically zero
            assert singular[1] <= 1e-9 * max(singular[0], 1.0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_reproduce_rank1_b0(frozen, data, protocol):
    """B0 reproduce of the frozen N6 rank-1 model (fit-level regression)."""
    result = reproduce_rank1_b0(frozen, data, protocol)
    assert result["coefficient_relative_error"] <= 1e-9

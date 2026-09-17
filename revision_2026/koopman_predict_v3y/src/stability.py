"""GDM-RK stability evidence: block-triangular spectrum check and finite-horizon
input/state gains with worst-family stress numbers.

The block-triangular structure only guarantees that the residual modes add no
larger eigenvalue; it does not remove rho(A0) ~ 1.0049 nor exclude non-normal
transient amplification, so the finite-horizon pressure numbers are the
decision evidence, not a stability certificate.
"""

from __future__ import annotations

import numpy as np
import torch

from lift import TriangularResidualKoopman


def triangular_spectrum(model: TriangularResidualKoopman, *, tolerance: float = 1e-8) -> dict:
    """Check spec(K) == spec(A0) union spec(F) on the block-triangular K."""
    k = model.full_k_matrix().detach().cpu()  # float64
    a0 = model.A0.double().cpu()
    f = model.f_matrix().double().detach().cpu()
    spectrum_k = np.linalg.eigvals(k.numpy())
    spectrum_a0 = np.linalg.eigvals(a0.numpy())
    spectrum_f = np.linalg.eigvals(f.numpy())
    union = np.concatenate([spectrum_a0, spectrum_f])
    # smallest matching distance over all permutations (sorted by |z| then angle)
    sorted_k = np.sort_complex(spectrum_k)
    sorted_union = np.sort_complex(union)
    max_error = float(np.max(np.abs(sorted_k - sorted_union))) if len(sorted_k) == len(sorted_union) else float("inf")
    radius_a0 = float(np.max(np.abs(spectrum_a0)))
    radius_f = float(np.max(np.abs(spectrum_f)))
    radius_k = float(np.max(np.abs(spectrum_k)))
    return {
        "spectrum_membership_max_error": max_error,
        "passed": max_error <= float(tolerance),
        "radius_A0": radius_a0,
        "radius_F": radius_f,
        "radius_K": radius_k,
        "per_pair_radius": None if model.dense_f else model.F.per_pair_radius(),
        "spectral_radius_max_residual": (
            None if model.dense_f else max(model.F.per_pair_radius())
        ),
        "dense_f": bool(model.dense_f),
    }


def finite_horizon_gain(
    model: TriangularResidualKoopman,
    dataset,
    protocol: dict,
    *,
    device,
    horizons: tuple[int, ...] = (1, 5, 10, 20, 40, 80),
    sample_limit: int = 256,
    seed: int = 990800,
) -> dict:
    """Propagate with actual control sequences and report per-horizon error
    growth and latent-norm growth (P99), plus induced input-to-state gain."""
    model.eval()
    model.to(device)
    dtype = torch.float64
    group_weights = {
        name: (float(protocol["state_groups"]["group_loss_weights"][name]), slice(*protocol["state_groups"][name]))
        for name in ("g0", "g1", "g2", "g3")
    }
    rng = np.random.default_rng(int(seed))
    indices = rng.choice(len(dataset), size=min(int(sample_limit), len(dataset)), replace=False)
    rows = {h: [] for h in horizons}
    latent_rows = {h: [] for h in horizons}
    with torch.no_grad():
        for index in indices:
            sample = dataset.get_sample(int(index))
            h_max = max(horizons)
            start = int(sample["start"])
            trajectory_index, _ = dataset._sample_index[int(index)]
            trajectory = dataset._trajectories[trajectory_index]
            if start + h_max >= trajectory["length"]:
                continue
            x0 = sample["x0"].to(dtype=dtype, device=device)
            u_raw = trajectory["control"][start : start + h_max]
            u = torch.as_tensor(
                (u_raw - dataset.normalization["control7_mean"]) / dataset.normalization["control7_scale"],
                dtype=dtype,
                device=device,
            )
            rollout = model.rollout(x0[None], u[None], horizons, return_eta=True)
            xhat = rollout["xhat"][0]  # (h_max, 47)
            eta = rollout["eta"][0]  # (h_max+1, r)
            for h in horizons:
                target = sample["x_target"][h].to(dtype=dtype, device=device)
                pred = xhat[h - 1]
                error = (pred - target) / dataset.rel_scale.to(dtype=dtype, device=device)
                rows[h].append(float(torch.sqrt(torch.mean(error**2))))
                latent_rows[h].append(float(torch.linalg.vector_norm(eta[h])))
    result = {}
    for h in horizons:
        values = np.asarray(rows[h], dtype=float)
        latents = np.asarray(latent_rows[h], dtype=float)
        result[str(h)] = {
            "sample_count": len(values),
            "rmse_mean": float(np.mean(values)) if values.size else None,
            "p99": float(np.percentile(values, 99.0)) if values.size else None,
            "max": float(np.max(values)) if values.size else None,
            "latent_norm_p99": float(np.percentile(latents, 99.0)) if latents.size else None,
            "divergent": bool(np.any(~np.isfinite(values)) or (values.size and np.max(values) > float(protocol["training"]["divergence_abs_normalized"]))),
        }
    return {"horizons": result, "seed": int(seed), "note": "finite-horizon pressure evidence, not a global certificate"}

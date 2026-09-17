"""Reproduce the Eq. (22) / gamma_norm false-certificate condition.

This is an expected-failure regression test for the original implementation.
It succeeds only when the counterexample is reproduced.
"""

import json
from pathlib import Path

import numpy as np


def spectral_project_matrix(A: np.ndarray, radius: float) -> np.ndarray:
    """Exact projection logic used by the original core_utils.py."""
    eigvals, eigvecs = np.linalg.eig(A)
    eigvals_proj = np.array(
        [ev if np.abs(ev) <= radius else ev / np.abs(ev) * radius for ev in eigvals]
    )
    return np.real(eigvecs @ np.diag(eigvals_proj) @ np.linalg.inv(eigvecs))


def effective(A: np.ndarray, B: np.ndarray, u: float) -> np.ndarray:
    return A + u * B


def main() -> None:
    radius = 0.998
    # Stable eigenvalues but strong non-normal transient amplification.
    # Spectral projection leaves this A unchanged because rho(A) < radius,
    # while ||A||_2 is much larger than radius.
    A = np.array([[0.90, 10.0], [0.0, 0.80]], dtype=np.float64)
    B = np.array([[0.10, 0.00], [0.00, 0.10]], dtype=np.float64)
    u_bounds = np.array([[-1.0, 1.0]], dtype=np.float64)

    A_proj = spectral_project_matrix(A, radius=0.992)
    budget = float(np.max(np.abs(u_bounds)) * np.linalg.norm(B, 2))
    norm_a = float(np.linalg.norm(A_proj, 2))
    gamma_norm = float(np.clip((radius - norm_a) / budget, 0.0, 1.0))
    # This is the original enforce_norm_bound branch when gamma_sampled >= gamma_norm.
    gamma_applied = gamma_norm
    B_proj = gamma_applied * B
    A_eff_zero = effective(A_proj, B_proj, 0.0)
    norm_eff_zero = float(np.linalg.norm(A_eff_zero, 2))
    rho_eff_zero = float(np.max(np.abs(np.linalg.eigvals(A_eff_zero))))

    reproduced = bool(
        gamma_norm == 0.0
        and gamma_applied == 0.0
        and norm_eff_zero > radius
    )
    result = {
        "expected_counterexample_reproduced": reproduced,
        "radius": radius,
        "norm_A_projected_2": norm_a,
        "norm_A_eff_at_zero_input_2": norm_eff_zero,
        "spectral_radius_A_eff_at_zero_input": rho_eff_zero,
        "projection_gamma_norm_bound": gamma_norm,
        "projection_gamma_applied": gamma_applied,
        "source_logic": "Exact Eq. (22) gamma_norm and spectral_project_matrix logic isolated from core_utils.py",
        "conclusion": (
            "gamma=0 does not certify the claimed induced-norm bound"
            if reproduced
            else "counterexample was not reproduced; investigate implementation/environment"
        ),
    }
    output = Path(__file__).with_name("eq22_counterexample_result.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not reproduced:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

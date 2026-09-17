"""Bootstrap the original TF14 notebook and audit its actual bilinear model.

No original project file is modified. Outputs are written under revision_2026.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = (
    PROJECT_ROOT
    / "tf14_remaining_experiments_20260509"
    / "run_tf14_remaining_experiments.py"
)
OUTPUT_DIR = Path(__file__).resolve().parent


def load_runner():
    spec = importlib.util.spec_from_file_location("revision_original_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def split_input_matrices(B: np.ndarray, nz: int, nu: int) -> list[np.ndarray]:
    return [B[:, j::nu] for j in range(nu)]


def main() -> None:
    runner = load_runner()
    stage5 = runner._load_stage5_module()
    stage1 = stage5._load_stage1_module()
    ns = stage5._bootstrap_env_for_path(stage1, "sine")
    methods = runner._ablation_method_plans(stage5, stage1, ns)
    cfg = dict(methods["full_tf14"].updates)

    raw_A, raw_B, fit_info = ns["fit_koopman_bilinear_matrices"](
        ns["model_koop_dnn_lin"],
        ns["xs_train"],
        ns["us_train"],
        ridge_lambda=ns["KOOPMAN_CFG"].get("ridge_lambda", 1e-5),
        batch_size=4096,
    )
    pack = ns["get_tf9_model_pack"](cfg)
    projected_A = np.asarray(pack["A_bilinear"], dtype=np.float64)
    projected_B = np.asarray(pack["B_bilinear"], dtype=np.float64)
    projection_info = dict(pack.get("bilinear_info") or {})

    net = ns["model_koop_dnn_lin"].net
    u_flat = np.asarray(ns["us_train"], dtype=np.float64).reshape(-1, ns["us_train"].shape[-1])
    if net.standardizer_u is not None:
        u_scaled = net.standardizer_u.transform(u_flat)
    else:
        u_scaled = u_flat
    u_min = np.min(u_scaled, axis=0)
    u_max = np.max(u_scaled, axis=0)
    u_abs = np.maximum(np.abs(u_min), np.abs(u_max))

    nz = int(projected_A.shape[0])
    nu = int(projected_B.shape[1] // nz)
    n_mats = split_input_matrices(projected_B, nz, nu)
    norm_A = float(np.linalg.norm(projected_A, 2))
    rho_A = float(np.max(np.abs(np.linalg.eigvals(projected_A))))
    bilinear_budget = float(sum(u_abs[j] * np.linalg.norm(n_mats[j], 2) for j in range(nu)))
    radius = float(cfg.get("input_aware_projection_radius", 0.998))
    continuous_triangle_upper_bound = norm_A + bilinear_budget
    gamma_norm_recomputed = (
        1.0
        if bilinear_budget <= 1e-12
        else float(np.clip((radius - norm_A) / bilinear_budget, 0.0, 1.0))
    )

    result = {
        "actual_interpreter": sys.executable,
        "matrix_shapes": {
            "raw_A": list(raw_A.shape),
            "raw_B": list(raw_B.shape),
            "projected_A": list(projected_A.shape),
            "projected_B": list(projected_B.shape),
        },
        "fit_info": fit_info,
        "projection_info": projection_info,
        "configured_enforce_norm_bound": bool(cfg.get("input_aware_enforce_norm_bound", False)),
        "continuous_domain_audit": {
            "radius": radius,
            "u_scaled_min": u_min.tolist(),
            "u_scaled_max": u_max.tolist(),
            "spectral_radius_A_projected": rho_A,
            "induced_norm_A_projected_2": norm_A,
            "bilinear_norm_budget": bilinear_budget,
            "triangle_upper_bound": continuous_triangle_upper_bound,
            "gamma_norm_recomputed": gamma_norm_recomputed,
            "continuous_bound_feasible_without_reprojecting_A": bool(norm_A <= radius),
        },
        "interpretation": (
            "Current projected A alone violates the Euclidean induced-norm radius; "
            "scaling bilinear matrices to zero cannot certify the stated bound."
            if norm_A > radius
            else "Projected A is within the Euclidean norm radius; bilinear budget still requires checking."
        ),
    }

    np.savez_compressed(
        OUTPUT_DIR / "actual_irsp_matrices.npz",
        raw_A=np.asarray(raw_A),
        raw_B=np.asarray(raw_B),
        projected_A=projected_A,
        projected_B=projected_B,
        u_scaled_min=u_min,
        u_scaled_max=u_max,
    )
    (OUTPUT_DIR / "actual_irsp_audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


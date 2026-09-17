from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connector_r3 import connector_force_r3, smoothing_weight
from internal_force import (
    build_planar_grasp_matrix,
    build_radial_grasp_matrix,
    decompose_planar_point_forces,
    decompose_radial_forces,
    legacy_q_fr_q_lr,
)
from schema_r3 import PARAMETER_UNITS, params_from_delta_freeze


def one(delta, vn, p, angle=0.0):
    n = np.array([np.cos(angle), np.sin(angle)])
    return connector_force_r3((p.free_play_m + delta) * n, vn * n, p)


def main() -> None:
    p = params_from_delta_freeze(Path(sys.argv[1]))
    out = Path(sys.argv[2]); out.parent.mkdir(parents=True, exist_ok=True)
    ds = p.smoothing_width_m
    eps = ds * 1e-8
    inside = connector_force_r3(np.array([0.5 * p.free_play_m, 0.0]), np.array([1.0, 0.0]), p)
    boundary = [float(one(ds * x, 0.8, p).raw_force_n) for x in (1e-8, 1e-7, 1e-6, 1e-5)]
    grid = np.linspace(0, ds, 1001); g = smoothing_weight(grid, ds)
    gp0 = float((smoothing_weight(np.array(eps), ds) - smoothing_weight(np.array(0.0), ds)) / eps)
    gp1 = float((smoothing_weight(np.array(ds), ds) - smoothing_weight(np.array(ds - eps), ds)) / eps)
    static_deltas = np.array([0.0, ds / 10, ds, 10 * ds, 0.01, 0.05])
    static_err = max(abs(float(one(d, 0.0, p).raw_force_n) - p.stiffness_npm * d) for d in static_deltas)
    full_err = max(abs(float(one(d, v, p).raw_force_n) - (p.stiffness_npm * d + p.damping_nspm * v)) for d in (ds, 2 * ds, 0.01) for v in (.01, .2, 1.0))
    unload_err = max(abs(float(one(d, -v, p).damping_force_n)) for d in (ds / 2, ds, .01) for v in (.1, 1.0))
    directional = []
    for a in (0, np.pi / 2, np.pi, -np.pi / 2, np.pi / 6, np.pi / 3):
        r = one(2 * ds, .2, p, a)
        directional.append(float(np.linalg.norm(r.force_payload_world_n / r.raw_force_n - np.array([np.cos(a), np.sin(a)]))))
    action = one(2 * ds, .2, p, np.pi / 3)
    action_residual = float(np.linalg.norm(action.force_payload_world_n + action.force_vehicle_world_n))
    mirror_l, mirror_r = one(2 * ds, .2, p, np.pi / 4), one(2 * ds, .2, p, -np.pi / 4)
    mirror_residual = float(np.max(np.abs(mirror_l.force_payload_world_n * np.array([1, -1]) - mirror_r.force_payload_world_n)))

    anchors = np.array([[2.5, 1.0], [2.5, -1.0], [-2.5, 1.0], [-2.5, -1.0]])
    force = np.array([[100, 40], [-30, 70], [60, -90], [-80, -20]], float)
    dec = decompose_planar_point_forces(force, anchors)
    normals = np.array([[1, 0], [0, 1], [-1, 0], [0, -1]], float)
    radial = decompose_radial_forces(np.array([100, 80, 60, 40]), anchors, normals)
    q = legacy_q_fr_q_lr(force)
    checks = {
        "inside_gap_zero": float(inside.raw_force_n) == 0.0,
        "boundary_force_tends_zero": boundary[-1] < 1e-3 and all(x < y for x, y in zip(boundary, boundary[1:])),
        "g_endpoints": float(g[0]) == 0.0 and float(g[-1]) == 1.0,
        "g_endpoint_derivatives_zero": abs(gp0) < 1e-2 and abs(gp1) < 1e-2,
        "g_monotone_bounded": bool(np.all(np.diff(g) >= -1e-15) and np.all((g >= 0) & (g <= 1))),
        "static_global_v1_equivalence": static_err < 1e-10,
        "full_v1_equivalence_after_smoothing": full_err < 1e-10,
        "unloading_no_damping": unload_err == 0.0,
        "directions_and_rotations": max(directional) < 1e-12,
        "mirror": mirror_residual < 1e-12,
        "action_reaction": action_residual == 0.0,
        "energy_dissipation_nonnegative": all(float(one(d, v, p).elastic_energy_j) >= 0 and float(one(d, v, p).damping_power_w) >= 0 for d in static_deltas for v in (-1, 0, 1)),
        "planar_internal_null": float(np.linalg.norm(dec["null_residual"])) < 1e-10,
        "planar_internal_reconstruct": float(np.linalg.norm(dec["reconstruction_residual"])) < 1e-12,
        "radial_internal_null": float(np.linalg.norm(radial["radial_null_residual"])) < 1e-10,
        "legacy_q_exact": bool(np.allclose(q, [45.0, -50.0])),
        "grasp_ranks": dec["grasp_rank"] == 3 and radial["radial_rank"] >= 3,
        "parameter_units_complete": set(PARAMETER_UNITS) == {"stiffness_npm", "damping_nspm", "free_play_m", "smoothing_width_m", "rated_force_n", "ultimate_force_n"},
        "strength_source_unverified": p.strength_source == "numerical_legacy_unverified",
    }
    result = {
        "passed": all(checks.values()),
        "checks": {k: bool(v) for k, v in checks.items()},
        "params": asdict(p),
        "boundary_forces_n": boundary,
        "g_endpoint_derivatives": [gp0, gp1],
        "static_max_abs_error_n": static_err,
        "post_smoothing_max_abs_error_n": full_err,
        "action_reaction_residual_n": action_residual,
        "internal_null_residual": float(np.linalg.norm(dec["null_residual"])),
        "radial_internal_null_residual": float(np.linalg.norm(radial["radial_null_residual"])),
        "development_read": False,
        "confirm_read": False,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()

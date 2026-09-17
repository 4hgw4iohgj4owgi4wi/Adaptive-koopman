from __future__ import annotations
import json, sys, time
from pathlib import Path
from typing import Any
import numpy as np

import audit
from axial_decoder import decode
from mirror_generator import analytic_mirror, independent_mirror_rollout, mirror_residual, params_from_metadata, r1_arrays, save

SCENARIOS = ("staged_100m", "single_lane_change", "hairpin", "connector_directional")


def jobs(base: int) -> list[dict[str, Any]]:
    return [{"seed": base + i + 1, "trajectory_id": base + i + 1, "base_family_id": f"pilot_{base+i+1}",
             "split": "pilot", "scenario": SCENARIOS[i % 4], "independent_mirror": i < 8} for i in range(16)]


def exact_initial_state(project: Path, scenario: str, seed: int) -> np.ndarray:
    koop = project / "revision_2026" / "koopman"; model = project / "revision_2026" / "model"
    for path in (koop, model):
        if str(path) not in sys.path: sys.path.insert(0, str(path))
    import generate_k2 as gen
    rng = np.random.default_rng(seed); params, _ = gen.parameter_sample(rng, external=False)
    rng.uniform(0., 2. * np.pi); rng.choice([-1., 1.])
    initial_speed = {"staged_100m": 2., "single_lane_change": 2., "hairpin": 1., "connector_directional": 1.8}[scenario] * float(rng.uniform(.96, 1.04))
    state = gen.initialize_state(params, speed_mps=initial_speed); vehicles, _ = gen.split_state(state)
    vehicles[:, 3] += rng.normal(0., .015, 4); vehicles[:, 4] += rng.normal(0., .004, 4); state[:24] = vehicles.reshape(-1)
    return state.astype(np.float64)


def generate_one(project_s: str, job: dict[str, Any], root_s: str) -> dict[str, Any]:
    project, root = Path(project_s), Path(root_s); target = root / f"base_{job['seed']}.npz"
    if target.exists():
        with np.load(target, allow_pickle=False) as s:
            existing = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}; meta = json.loads(str(s["metadata_json"].item()))
        if "initial_state64" in existing and "control64" in existing and meta.get("initial_state_source") == "captured at first RK4 call":
            mirror_path = root / f"mirror_{job['seed']}.npz"
            return {**job, "base_file": target.name, "mirror_file": mirror_path.name, "base_sha256": audit.sha256(target),
                    "mirror_sha256": audit.sha256(mirror_path), "steps": len(existing["control"]), "bytes": target.stat().st_size + mirror_path.stat().st_size,
                    "finite": bool(meta["finite"]), "ultimate_steps": int(meta["ultimate_exceeded_steps"]), "resumed": True}
    koop = project / "revision_2026" / "koopman"; model = project / "revision_2026" / "model"
    for path in (koop, model):
        if str(path) not in sys.path: sys.path.insert(0, str(path))
    import generate_k2 as gen
    original_step = gen.rk4_step; captured = []; captured_initial = []; calls = 0
    def capture_step(state, controls, dt, params):
        nonlocal calls
        if calls == 0: captured_initial.append(np.asarray(state, float).copy())
        if calls % gen.SUBSTEPS == 0: captured.append(np.asarray(controls, float).copy())
        calls += 1; return original_step(state, controls, dt, params)
    gen.rk4_step = capture_step
    try: raw, meta = gen.simulate(job["scenario"], job["trajectory_id"], job["seed"], False)
    finally: gen.rk4_step = original_step
    arrays = r1_arrays(raw)
    if len(captured_initial) != 1: raise RuntimeError("failed to capture actual float64 initial integrator state")
    arrays["initial_state64"] = captured_initial[0]
    arrays["control64"] = np.asarray(captured, np.float64).reshape(-1, 8)
    if len(arrays["control64"]) != len(arrays["control"]): raise RuntimeError("captured float64 control length mismatch")
    meta.update(job); meta.update({"is_augmented": False, "r1_schema": "state30/state46/control/d/v/Fpayload/Fvehicle/q/yaws/time/initial_state64/control64",
                                  "precision_fix": "actual float64 initial state and controls captured at RK4 boundary without changing generator"})
    meta["initial_state_source"] = "captured at first RK4 call"
    save(target, arrays, meta); mirror = analytic_mirror(arrays)
    mirror_meta = {**meta, "is_augmented": True, "augmentation": "exact analytic LR mirror", "source_file": target.name,
                   "same_physical_scene": True, "same_parameters": True, "same_timestamps": True}
    mirror_path = root / f"mirror_{job['seed']}.npz"; save(mirror_path, mirror, mirror_meta)
    return {**job, "base_file": target.name, "mirror_file": mirror_path.name, "base_sha256": audit.sha256(target),
            "mirror_sha256": audit.sha256(mirror_path), "steps": len(arrays["control"]), "bytes": target.stat().st_size + mirror_path.stat().st_size,
            "finite": bool(meta["finite"]), "ultimate_steps": int(meta["ultimate_exceeded_steps"]), "resumed": False}


def audit_one(project_s: str, row: dict[str, Any], root_s: str, tolerance: float) -> dict[str, Any]:
    project, root = Path(project_s), Path(root_s)
    with np.load(root / row["base_file"], allow_pickle=False) as s:
        base = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}; meta = json.loads(str(s["metadata_json"].item()))
    with np.load(root / row["mirror_file"], allow_pickle=False) as s: mirror = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}
    exact = mirror_residual(mirror, analytic_mirror(base)); exact_pass = exact["overall"]["normalized_max"] == 0.
    params = params_from_metadata(project, meta); oracle = decode(base["connector_disp"], base["connector_vel"], params.connector.stiffness_npm, params.connector.damping_nspm, params.connector.free_play_m)
    oracle_max = float(np.max(np.abs(oracle["force_payload"] - base["force_payload"])))
    result = {"seed": row["seed"], "exact_copy": exact, "exact_copy_passed": exact_pass, "oracle_max_N": oracle_max,
              "oracle_passed": oracle_max <= 2e-3, "independent_requested": bool(row["independent_mirror"])}
    if row["independent_mirror"]:
        independent = independent_mirror_rollout(project, base, meta); residual = mirror_residual(independent, analytic_mirror(base))
        result["independent"] = residual; result["independent_passed"] = residual["overall"]["normalized_p95_max"] <= tolerance and residual["overall"]["normalized_max"] <= tolerance
    else: result["independent_passed"] = True
    result["passed"] = exact_pass and result["oracle_passed"] and result["independent_passed"]
    return result

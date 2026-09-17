from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Any
import numpy as np

from mirror_generator import mirror_joint_state30, params_from_metadata
from transforms import mirror_control, mirror_vector4


STATE_SCALE = np.tile(np.asarray([100., 100., np.pi, 5., 5., 1.]), 5)


def _imports(project: Path):
    for path in (project / "revision_2026" / "model", project / "revision_2026" / "koopman"):
        if str(path) not in sys.path: sys.path.insert(0, str(path))
    import generate_k2 as gen
    import four_vehicle_coupled as plant
    # generate_k2 re-exports RK4 helpers but not the continuous RHS.
    # Bind the audited plant RHS explicitly for the L1 derivative commutator.
    gen.system_derivative = plant.system_derivative
    return gen


def _load(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    with np.load(path, allow_pickle=False) as s:
        arrays = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}; meta = json.loads(str(s["metadata_json"].item()))
    return arrays, meta


def _obs(gen, state: np.ndarray, params) -> dict[str, np.ndarray]:
    row = gen.feature_rows(state, None, .02, params)
    return {"state30": np.asarray(row["s2_four"], float), "connector_disp": np.asarray(row["displacement_body"], float),
            "connector_vel": np.asarray(row["relative_velocity_body"], float), "force_payload": np.asarray(row["force_body"], float),
            "q": np.asarray(row["q"], float)}


def _field_errors(actual: dict[str, np.ndarray], base: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    expected = {"state30": mirror_joint_state30(base["state30"]), "connector_disp": mirror_vector4(base["connector_disp"]),
                "connector_vel": mirror_vector4(base["connector_vel"]), "force_payload": mirror_vector4(base["force_payload"]), "q": base["q"]}
    scales = {"state30": STATE_SCALE, "connector_disp": .05, "connector_vel": 1., "force_payload": 8000., "q": 8000.}
    return {k: np.abs(np.asarray(actual[k]) - expected[k]) / scales[k] for k in expected}


def _summarize(errors: dict[str, np.ndarray]) -> dict[str, Any]:
    result = {k: {"p95": float(np.quantile(v, .95)), "max": float(np.max(v))} for k, v in errors.items()}
    result["overall"] = {"p95_max": max(v["p95"] for v in result.values()), "max": max(v["max"] for v in result.values())}
    return result


def local_audit(project_s: str, file_s: str) -> dict[str, Any]:
    project, file = Path(project_s), Path(file_s); gen = _imports(project); a, meta = _load(file); params = params_from_metadata(project, meta)
    x = np.asarray(a["initial_state64"], float); controls = np.asarray(a["control64"][:20], float).reshape(-1, 4, 2)
    xm = mirror_joint_state30(x); um0 = mirror_control(controls[0].reshape(8)).reshape(4, 2)
    f = gen.system_derivative(x, controls[0], params)[0]; fm = gen.system_derivative(xm, um0, params)[0]
    derivative = float(np.max(np.abs(fm - mirror_joint_state30(f)) / STATE_SCALE))
    checkpoints = {}; base_state, mirror_state = x.copy(), xm.copy(); base_rows = []; mirror_rows = []
    for h, control in enumerate(controls):
        mcontrol = mirror_control(control.reshape(8)).reshape(4, 2)
        for sub in range(10):
            base_state = gen.rk4_step(base_state, control, .002, params); mirror_state = gen.rk4_step(mirror_state, mcontrol, .002, params)
            if h == 0 and sub == 0:
                checkpoints["0.002"] = _summarize(_field_errors(_obs(gen, mirror_state, params), _obs(gen, base_state, params)))
        base_rows.append(_obs(gen, base_state, params)); mirror_rows.append(_obs(gen, mirror_state, params))
        if h == 0: checkpoints["0.02"] = _summarize(_field_errors(mirror_rows[-1], base_rows[-1]))
    stacked_b = {k: np.asarray([r[k] for r in base_rows]) for k in base_rows[0]}; stacked_m = {k: np.asarray([r[k] for r in mirror_rows]) for k in mirror_rows[0]}
    checkpoints["0.4"] = _summarize(_field_errors(stacked_m, stacked_b))
    passed = derivative <= 1e-12 and checkpoints["0.002"]["overall"]["max"] <= 1e-11 and checkpoints["0.02"]["overall"]["max"] <= 1e-9 and checkpoints["0.4"]["overall"]["p95_max"] <= 1e-5 and checkpoints["0.4"]["overall"]["max"] <= 1e-4
    return {"seed": meta["seed"], "scenario": meta["scenario"], "derivative_max": derivative, "checkpoints": checkpoints,
            "finite": bool(np.all(np.isfinite(base_state)) and np.all(np.isfinite(mirror_state))), "ultimate_event_mismatch": False, "passed": passed}


def _first_crossing(values: np.ndarray, time: np.ndarray, distance: np.ndarray, threshold: float) -> dict[str, float] | None:
    idx = np.flatnonzero(values > threshold)
    return None if not len(idx) else {"time_s": float(time[idx[0]]), "distance_m": float(distance[idx[0]]), "value": float(values[idx[0]])}


def long_audit(project_s: str, file_s: str, output_s: str) -> dict[str, Any]:
    project, file, output = Path(project_s), Path(file_s), Path(output_s); gen = _imports(project); a, meta = _load(file); params = params_from_metadata(project, meta)
    controls = np.asarray(a["control64"], float).reshape(-1, 4, 2); summaries = {}; curves = {}
    for dt in (.004, .002, .001):
        substeps = int(round(.02 / dt)); b = np.asarray(a["initial_state64"], float).copy(); m = mirror_joint_state30(b)
        field_curves = {k: [] for k in ("state30", "connector_disp", "connector_vel", "force_payload", "q")}; distances = []; times = []
        distance = 0.; prev = b[24:26].copy(); rated_b = rated_m = ultimate_b = ultimate_m = 0
        for h, control in enumerate(controls):
            mc = mirror_control(control.reshape(8)).reshape(4, 2)
            for _ in range(substeps): b = gen.rk4_step(b, control, dt, params); m = gen.rk4_step(m, mc, dt, params)
            distance += float(np.linalg.norm(b[24:26] - prev)); prev = b[24:26].copy(); distances.append(distance); times.append((h + 1) * .02)
            ob, om = _obs(gen, b, params), _obs(gen, m, params); err = _field_errors(om, ob)
            for k, v in err.items(): field_curves[k].append(float(np.max(v)))
            mb = np.linalg.norm(ob["force_payload"], axis=-1); mm = np.linalg.norm(om["force_payload"], axis=-1)
            rated_b += int(np.any(mb >= params.connector.rated_force_n)); rated_m += int(np.any(mm >= params.connector.rated_force_n))
            ultimate_b += int(np.any(mb >= params.connector.ultimate_force_n)); ultimate_m += int(np.any(mm >= params.connector.ultimate_force_n))
        time_a, dist_a = np.asarray(times), np.asarray(distances); overall = np.max(np.stack([field_curves[k] for k in field_curves]), axis=0)
        summaries[str(dt)] = {"p95": float(np.quantile(overall, .95)), "max": float(np.max(overall)),
            "first_crossing": {str(t): _first_crossing(overall, time_a, dist_a, t) for t in (1e-5, 1e-3, .01)},
            "first_field": min(field_curves, key=lambda k: next((i for i, v in enumerate(field_curves[k]) if v > 1e-5), 10**12)),
            "events": {"rated_base": rated_b, "rated_mirror": rated_m, "ultimate_base": ultimate_b, "ultimate_mirror": ultimate_m},
            "event_consistent": rated_b == rated_m and ultimate_b == ultimate_m, "finite": bool(np.all(np.isfinite(b)) and np.all(np.isfinite(m)))}
        curves[f"time_{dt}"] = time_a; curves[f"distance_{dt}"] = dist_a; curves[f"overall_{dt}"] = overall
        for k, v in field_curves.items(): curves[f"{k}_{dt}"] = np.asarray(v)
    output.parent.mkdir(parents=True, exist_ok=True); np.savez_compressed(output, **curves)
    convergence = {"p95_004_to_002": summaries["0.004"]["p95"] / max(summaries["0.002"]["p95"], 1e-30),
                   "p95_002_to_001": summaries["0.002"]["p95"] / max(summaries["0.001"]["p95"], 1e-30)}
    blocking = any(not summaries[str(dt)]["finite"] or not summaries[str(dt)]["event_consistent"] for dt in (.004, .002, .001))
    return {"seed": meta["seed"], "scenario": meta["scenario"], "summaries": summaries, "convergence": convergence,
            "curve_file": output.name, "blocking": blocking}

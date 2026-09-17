from __future__ import annotations
import json, sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
import numpy as np

from transforms import mirror_control, mirror_state, mirror_vector4


def mirror_joint_state30(state: np.ndarray) -> np.ndarray:
    out = np.asarray(state, float).copy()
    v = out[..., :24].reshape(*out.shape[:-1], 4, 6)[..., [1, 0, 3, 2], :].copy()
    v[..., 1] *= -1; v[..., 2] *= -1; v[..., 4] *= -1; v[..., 5] *= -1
    p = out[..., 24:30].copy(); p[..., 1] *= -1; p[..., 2] *= -1; p[..., 4] *= -1; p[..., 5] *= -1
    out[..., :24] = v.reshape(*out.shape[:-1], 24); out[..., 24:30] = p; return out


def r1_arrays(base: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    state30 = np.asarray(base["s2_four"], np.float32)
    vehicles = state30[:, :24].reshape(len(state30), 4, 6)
    system_yaw = np.arctan2(np.mean(np.sin(vehicles[:, :, 2]), axis=1), np.mean(np.cos(vehicles[:, :, 2]), axis=1))
    force = np.asarray(base["force_body"], np.float32)
    return {
        "state30": state30, "state46": np.asarray(base["s3_deform"], np.float32),
        "control": np.asarray(base["u1_four"], np.float32),
        "connector_disp": np.asarray(base["displacement_body"], np.float32),
        "connector_vel": np.asarray(base["relative_velocity_body"], np.float32),
        "force_payload": force, "force_vehicle": -force,
        "q": np.asarray(base["q"], np.float32), "payload_yaw": state30[:, 26].astype(np.float32),
        "system_yaw": system_yaw.astype(np.float32), "time_s": np.asarray(base["time_s"], np.float32),
    }


def analytic_mirror(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    out = {
        "state30": mirror_joint_state30(arrays["state30"]).astype(np.float32),
        "state46": mirror_state(arrays["state46"]).astype(np.float32),
        "control": mirror_control(arrays["control"]).astype(np.float32),
        "connector_disp": mirror_vector4(arrays["connector_disp"]).astype(np.float32),
        "connector_vel": mirror_vector4(arrays["connector_vel"]).astype(np.float32),
        "force_payload": mirror_vector4(arrays["force_payload"]).astype(np.float32),
        "force_vehicle": mirror_vector4(arrays["force_vehicle"]).astype(np.float32),
        "q": arrays["q"].copy(), "payload_yaw": (-arrays["payload_yaw"]).astype(np.float32),
        "system_yaw": (-arrays["system_yaw"]).astype(np.float32), "time_s": arrays["time_s"].copy(),
    }
    if "initial_state64" in arrays: out["initial_state64"] = mirror_joint_state30(arrays["initial_state64"])
    if "control64" in arrays: out["control64"] = mirror_control(arrays["control64"])
    return out


def save(path: Path, arrays: dict[str, np.ndarray], metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    tmp.replace(path)


def params_from_metadata(project: Path, metadata: dict[str, Any]):
    model = project / "revision_2026" / "model"
    if str(model) not in sys.path: sys.path.insert(0, str(model))
    from four_vehicle_coupled import ConnectorParams, ModelParams, PayloadParams, VehicleParams
    p = metadata["params"]
    return ModelParams(vehicle=VehicleParams(**p["vehicle"]), payload=PayloadParams(**p["payload"]), connector=ConnectorParams(**p["connector"]))


def independent_mirror_rollout(project: Path, base_arrays: dict[str, np.ndarray], metadata: dict[str, Any]) -> dict[str, np.ndarray]:
    koop = project / "revision_2026" / "koopman"; model = project / "revision_2026" / "model"
    for path in (koop, model):
        if str(path) not in sys.path: sys.path.insert(0, str(path))
    import generate_k2 as gen
    params = params_from_metadata(project, metadata); controls = mirror_control(base_arrays.get("control64", base_arrays["control"]))
    initial = base_arrays.get("initial_state64", base_arrays["state30"][0])
    injected_initial = mirror_joint_state30(initial); state = injected_initial.copy(); rows = []
    force_prev = None
    for k in range(len(controls)):
        rows.append(gen.feature_rows(state, force_prev, gen.CONTROL_DT, params)); force_prev = rows[-1]["force_body"].copy()
        for _ in range(gen.SUBSTEPS): state = gen.rk4_step(state, controls[k].reshape(4, 2), gen.PLANT_DT, params)
    rows.append(gen.feature_rows(state, force_prev, gen.CONTROL_DT, params))
    raw = {key: np.asarray([r[key] for r in rows], np.float32) for key in ("s2_four", "s3_deform", "displacement_body", "relative_velocity_body", "force_body", "q")}
    raw["u1_four"] = controls.astype(np.float32); raw["time_s"] = base_arrays["time_s"].copy()
    result = r1_arrays(raw); result["initial_state64"] = injected_initial; result["control64"] = controls; return result


def mirror_residual(actual: dict[str, np.ndarray], expected: dict[str, np.ndarray]) -> dict[str, Any]:
    fields = ("state30", "state46", "control", "connector_disp", "connector_vel", "force_payload", "force_vehicle", "q", "payload_yaw", "system_yaw", "time_s")
    if "initial_state64" in expected: fields = fields + ("initial_state64",)
    if "control64" in expected: fields = fields + ("control64",)
    result = {}; all_p95 = []; all_max = []
    for key in fields:
        a, e = np.asarray(actual[key], float), np.asarray(expected[key], float)
        scale = max(float(np.quantile(np.abs(e), .95)), 1.)
        rel = np.abs(a - e) / scale
        result[key] = {"normalized_p95": float(np.quantile(rel, .95)), "normalized_max": float(np.max(rel)), "scale": scale}
        all_p95.append(result[key]["normalized_p95"]); all_max.append(result[key]["normalized_max"])
    result["overall"] = {"normalized_p95_max": max(all_p95), "normalized_max": max(all_max)}
    return result

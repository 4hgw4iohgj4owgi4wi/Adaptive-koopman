"""Frozen diagnostic-only closed-loop adapter for universal v2.

No method passed the absolute offline deployment gate.  This executor therefore
uses one identical finite-control-set receding-horizon adapter and labels every
result diagnostic-only.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE / "universal_v2"
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))

import universal_v2_modules as m  # noqa: E402


BASE = m.uv2.v1.base
H = 20
UPDATE_STEPS = 10
ACCEL_OFFSETS = (-0.15, 0.0, 0.15)
STEER_SCALES = (0.9, 1.0, 1.1)
SELECTED_STATE = np.asarray([2, 5, 8, 11, 14, 17, 20, 23, 24, 25, 26, 27, 28, 29])


def reference_job(scenario: str, seed: int, external: bool, path_text: str) -> dict[str, Any]:
    arrays, metadata = BASE.simulate(scenario, seed % 100000, seed, external)
    path = Path(path_text)
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    return {"file": path.name, "sha256": m.uv2.sha256(path), "scenario": scenario, "seed": seed,
            "external": external, "steps": metadata["steps"], "distance_m": metadata["distance_m"]}


def reconstruct_params(metadata: dict[str, Any]) -> Any:
    p = metadata["params"]
    return BASE.ModelParams(vehicle=BASE.VehicleParams(**p["vehicle"]), payload=BASE.PayloadParams(**p["payload"]),
                            connector=BASE.ConnectorParams(**p["connector"]))


def model_estimate(model: dict[str, Any], observed: np.ndarray, origin: int, current: int,
                   applied: list[np.ndarray]) -> np.ndarray:
    z = m.cp.lift(model, observed)
    for k in range(origin, current):
        z, _ = m.cp.model_step(model, z, applied[k])
    _, _, xn = m.cp.decode(model, z)
    return xn * model.get("metric_x_std", model["x_std"]) + model.get("metric_x_mean", model["x_mean"])


def candidate_cost(model: dict[str, Any], estimated_s3: np.ndarray, controls: np.ndarray,
                   ref_s3: np.ndarray, ref_force: np.ndarray, norms: dict[str, np.ndarray],
                   adaptation_bias: np.ndarray) -> tuple[float, bool]:
    z = m.cp.lift(model, estimated_s3)
    cost = 0.0
    for h in range(H):
        z, _ = m.cp.model_step(model, z, controls)
        _, fn, xn = m.cp.decode(model, z)
        prediction = np.r_[xn, fn] + adaptation_bias
        if not np.all(np.isfinite(prediction)) or np.max(np.abs(prediction)) > 1.0e5:
            return math.inf, False
        target_x = (ref_s3[h] - norms["x_mean"]) / norms["x_std"]
        target_f = (ref_force[h] - norms["force_mean"]) / norms["force_std"]
        state_error = prediction[SELECTED_STATE] - target_x[SELECTED_STATE]
        deform_error = prediction[30:46] - target_x[30:46]
        force_error = prediction[46:56] - target_f[:10]
        cost += float(np.mean(state_error**2) + 0.20 * np.mean(deform_error**2) + 0.10 * np.mean(force_error**2))
    return cost / H, True


def simulate_job(job: dict[str, Any], model: dict[str, Any], norms: dict[str, np.ndarray],
                 basis: np.ndarray | None, prior: float) -> dict[str, Any]:
    with np.load(job["reference_path"], allow_pickle=False) as source:
        ref = {key: np.asarray(source[key], dtype=float) for key in source.files if key != "metadata_json"}
        metadata = json.loads(str(source["metadata_json"].item()))
    params = reconstruct_params(metadata)
    state = ref["s2_four"][0].copy(); force_prev = None
    alloc_cfg = BASE.AllocationConfig(max_steering_deg=15.0)
    max_steps = len(ref["u1_four"])
    if job["profile"] == "clean":
        aoi = np.zeros((max_steps, 4), dtype=np.int16)
    else:
        _, aoi, _ = m.network_trace(job["profile"], job["trace_id"], max_steps)
    observed_history, applied, true_s3, true_force = [], [], [], []
    selected_controls = ref["u1_four"][0].reshape(4, 2).copy()
    solve_times, fallback = [], 0
    residual_memory = []
    max_force = max_tire = 0.0; ultimate = 0; distance = 0.0
    previous_payload = state[24:26].copy()
    for k in range(max_steps):
        obs = BASE.feature_rows(state, force_prev, BASE.CONTROL_DT, params)
        force_prev = obs["force_body"].copy(); observed_history.append(obs["s3_deform"].copy())
        true_s3.append(obs["s3_deform"].copy()); true_force.append(obs["force_output"].copy())
        # Causal adaptation uses only residuals whose target has just arrived.
        adaptation_mode = job.get("adaptation_mode", "none")
        can_update = adaptation_mode == "online" or (adaptation_mode == "fixed-2s" and len(residual_memory) < int(2.0 / BASE.CONTROL_DT))
        if basis is not None and k > 0 and can_update:
            zprev = m.cp.lift(model, observed_history[k - 1]); zprev, _ = m.cp.model_step(model, zprev, applied[k - 1])
            _, fpn, xpn = m.cp.decode(model, zprev)
            tx = (obs["s3_deform"] - norms["x_mean"]) / norms["x_std"]
            tf = (obs["force_output"] - norms["force_mean"]) / norms["force_std"]
            residual_memory.append(np.r_[tx, tf] - np.r_[xpn, fpn])
        adaptation_bias = np.zeros(64)
        if basis is not None and len(residual_memory) >= int(2.0 / BASE.CONTROL_DT):
            mean_residual = np.mean(residual_memory, axis=0)
            adaptation_bias = basis @ (basis.T @ mean_residual) / (1.0 + prior)
        stale = int(np.max(aoi[k])); origin = max(0, k - stale)
        estimated_s3 = observed_history[origin]
        if job["protected"] and origin < k:
            estimated_s3 = model_estimate(model, estimated_s3, origin, k, applied)
        if k % UPDATE_STEPS == 0:
            tic = time.perf_counter_ns()
            ref_index = min(k, len(ref["u3_alloc"]) - 1)
            nominal_accel = float(np.mean(ref["u1_four"][ref_index, 0::2]))
            front_deg = math.degrees(float(ref["u3_alloc"][ref_index, 8]))
            rear_deg = math.degrees(float(ref["u3_alloc"][ref_index, 9]))
            best = (math.inf, None)
            estimate_state = estimated_s3[:30]
            stop = min(k + H + 1, len(ref["s3_deform"]))
            ref_s3 = ref["s3_deform"][k + 1:stop]
            ref_force = ref["force_output"][k + 1:stop]
            if len(ref_s3) < H:
                ref_s3 = np.vstack([ref_s3, np.repeat(ref_s3[-1:], H - len(ref_s3), axis=0)])
                ref_force = np.vstack([ref_force, np.repeat(ref_force[-1:], H - len(ref_force), axis=0)])
            for da in ACCEL_OFFSETS:
                for scale in STEER_SCALES:
                    controls, _ = BASE.allocate_controls(estimate_state, nominal_accel + da, front_deg * scale, rear_deg * scale, params, alloc_cfg)
                    cost, finite = candidate_cost(model, estimated_s3, controls.reshape(8), ref_s3, ref_force, norms, adaptation_bias)
                    cost += 0.05 * (da / 0.15) ** 2 + 0.02 * ((scale - 1.0) / 0.1) ** 2
                    if finite and cost < best[0]: best = (cost, controls)
            if best[1] is None:
                fallback += 1
                selected_controls = ref["u1_four"][ref_index].reshape(4, 2)
            else:
                selected_controls = best[1]
            solve_times.append((time.perf_counter_ns() - tic) * 1.0e-6)
        selected_controls[:, 0] = np.clip(selected_controls[:, 0], -1.4, 1.2)
        selected_controls[:, 1] = np.clip(selected_controls[:, 1], -math.radians(15), math.radians(15))
        applied.append(selected_controls.reshape(8).copy())
        diag = BASE.aggregate_diagnostics(state, selected_controls, params)
        forces = np.asarray(diag["connectors"]["force_norm_n"]); max_force = max(max_force, float(forces.max()))
        max_tire = max(max_tire, float(np.max(diag["tire_utilization"]))); ultimate += int(np.any(forces >= params.connector.ultimate_force_n))
        for _ in range(BASE.SUBSTEPS): state = BASE.rk4_step(state, selected_controls, BASE.PLANT_DT, params)
        distance += float(np.linalg.norm(state[24:26] - previous_payload)); previous_payload = state[24:26].copy()
        if not np.all(np.isfinite(state)) or ultimate:
            break
        if job["scenario"] == "staged_100m" and distance >= 100.0:
            break
    n = min(len(true_s3), len(ref["s3_deform"]))
    actual = np.asarray(true_s3[:n]); target = ref["s3_deform"][:n]
    actual_force = np.asarray(true_force[:n]); target_force = ref["force_output"][:n]
    payload_error = actual[:, 24:30] - target[:, 24:30]
    vehicle_yaw = actual[:, [2, 8, 14, 20]] - target[:, [2, 8, 14, 20]]
    q_error = actual_force[:, 8:10] - target_force[:, 8:10]
    solve = np.asarray(solve_times)
    return {**{key: job[key] for key in ("model", "scenario", "seed", "profile", "protected", "external", "trace_id")},
            "method": job.get("method", job["model"]), "adaptation_mode": job.get("adaptation_mode", "none"),
            "status": "diagnostic_only_offline_gate_failed", "completed_steps": len(true_s3), "distance_m": distance,
            "distance_gate": job["scenario"] != "staged_100m" or distance >= 100.0,
            "finite": bool(np.all(np.isfinite(state))), "ultimate_steps": ultimate,
            "max_connector_force_n": max_force, "max_tire_utilization": max_tire,
            "payload_position_rmse_m": float(np.sqrt(np.mean(payload_error[:, :2] ** 2))),
            "payload_yaw_rmse_rad": float(np.sqrt(np.mean(payload_error[:, 2] ** 2))),
            "payload_speed_rmse_mps": float(np.sqrt(np.mean(payload_error[:, 3:5] ** 2))),
            "system_yaw_rate_rmse_radps": float(np.sqrt(np.mean(payload_error[:, 5] ** 2))),
            "vehicle_yaw_rmse_rad": float(np.sqrt(np.mean(vehicle_yaw**2))),
            "payload_tension_rmse_n": float(np.sqrt(np.mean(q_error**2))),
            "solve_p50_ms": float(np.percentile(solve, 50)), "solve_p95_ms": float(np.percentile(solve, 95)),
            "solve_p99_ms": float(np.percentile(solve, 99)), "timeout_rate_20ms": float(np.mean(solve > 20.0)),
            "fallback_count": fallback, "adaptation_updates": max(0, len(residual_memory) - int(2.0 / BASE.CONTROL_DT)) if basis is not None else 0}


def extend_parameter() -> None:
    complete = OUT / "t8" / "parameter_extension_complete.json"
    if complete.exists(): print("closed-loop parameter extension already complete", flush=True); return
    _, norms, _, models = m.context()
    refs = OUT / "t8" / "references"
    jobs = []
    for method, backbone, mode in (("K0", "K0", "none"), ("K1", "K1", "none"),
                                   ("K5-linear-A0", "K5-linear", "none"),
                                   ("K5-linear-A1-2s", "K5-linear", "fixed-2s")):
        for offset in range(10):
            seed = 985300 + offset
            jobs.append({"model": backbone, "method": method, "adaptation_mode": mode, "scenario": "hairpin", "seed": seed,
                         "profile": "clean", "protected": False, "external": True, "trace_id": offset,
                         "reference_path": str(refs / f"hairpin_ext_{seed}.npz")})
    with np.load(OUT / "t5" / "A-K5-linear.npz", allow_pickle=False) as source:
        basis, prior = np.asarray(source["basis"]), float(source["prior"])
    results, failures = [], []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {}
        for job in jobs:
            local_basis = basis if job["adaptation_mode"] != "none" else None
            futures[pool.submit(simulate_job, job, models[job["model"]], norms, local_basis, prior)] = job
        for index, future in enumerate(as_completed(futures), 1):
            try: results.append(future.result())
            except Exception as exc: failures.append({"job": futures[future], "error": repr(exc)})
            print(f"CL parameter extension [{index:02d}/40] failures={len(failures)}", flush=True)
    results.sort(key=lambda row: (row["method"], row["seed"]))
    import csv
    with (OUT / "closed_loop_parameter_extension.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0])); writer.writeheader(); writer.writerows(results)
    m.write_json(OUT / "t8" / "parameter_extension.json", {"results": results, "failures": failures,
                 "note": "original K5-linear rows are A2-online and are relabelled at report time"})
    m.write_json(complete, {"status": "complete" if not failures else "partial_failure", "completed": len(results),
                            "failures": len(failures), "results_sha256": m.uv2.sha256(OUT / "t8" / "parameter_extension.json")})
    m.uv2.append_log("W0070", "参数闭环配对补充", [
        f"识别到首轮K5参数闭环持续更新，按事实重标A2-online；补跑K0/K1/K5-A0/K5-A1-2s同seed={len(results)}/40，失败={len(failures)}。",
        "A1只使用前2s残差后冻结，A2保留持续1步残差更新；不得混写。",
        f"结果hash={m.uv2.sha256(OUT/'t8'/'parameter_extension.json')}。",
    ])


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--run", action="store_true"); parser.add_argument("--extend-parameter", action="store_true"); args = parser.parse_args()
    if args.extend_parameter:
        extend_parameter(); return
    if not args.run: return
    complete = OUT / "t8" / "complete.json"
    if complete.exists(): print("T8 closed loop already complete", flush=True); return
    gates = json.loads((OUT / "universality_gates.json").read_text(encoding="utf-8"))
    if gates["absolute_deployment_candidates"]:
        raise RuntimeError("this diagnostic executor cannot run official candidates")
    rows, norms, _, models = m.context()
    del rows
    stage = OUT / "t8"; refs = stage / "references"; refs.mkdir(parents=True, exist_ok=True)
    plans = []
    for scenario, external, seed_base in (("staged_100m", False, 985000), ("single_lane_change", False, 985100),
                                          ("hairpin", False, 985200), ("hairpin", True, 985300)):
        for offset in range(10):
            seed = seed_base + offset; path = refs / f"{scenario}_{'ext' if external else 'int'}_{seed}.npz"
            plans.append((scenario, seed, external, str(path)))
    freeze = {"status": "frozen_before_first_closed_loop", "models": ["K0", "K1", "K5-linear+A"],
              "horizon": H, "update_steps": UPDATE_STEPS, "accel_offsets": ACCEL_OFFSETS,
              "steer_scales": STEER_SCALES, "script_sha256": m.uv2.sha256(Path(__file__).resolve()),
              "protocol_sha256": m.uv2.sha256(OUT / "protocol_v2.md"), "reference_plans": plans}
    m.write_json(stage / "freeze.json", freeze)
    ref_rows = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(reference_job, *plan): plan for plan in plans}
        for index, future in enumerate(as_completed(futures), 1):
            ref_rows.append(future.result()); print(f"CL reference [{index:02d}/40]", flush=True)
    ref_lookup = {(row["scenario"], row["external"], row["seed"]): str(refs / row["file"]) for row in ref_rows}
    jobs = []
    for model_name in ("K0", "K1"):
        for scenario, seed_base in (("staged_100m", 985000), ("single_lane_change", 985100), ("hairpin", 985200)):
            for offset in range(10):
                seed = seed_base + offset
                jobs.append({"model": model_name, "scenario": scenario, "seed": seed, "profile": "clean", "protected": False,
                             "external": False, "trace_id": offset, "reference_path": ref_lookup[(scenario, False, seed)]})
        for profile in ("iid", "burst", "delay", "dos"):
            for protected in (False, True):
                for offset in range(10):
                    seed = 985000 + offset
                    jobs.append({"model": model_name, "scenario": "staged_100m", "seed": seed, "profile": profile,
                                 "protected": protected, "external": False, "trace_id": offset,
                                 "reference_path": ref_lookup[("staged_100m", False, seed)]})
    for offset in range(10):
        seed = 985300 + offset
        jobs.append({"model": "K5-linear", "method": "K5-linear-A2-online", "adaptation_mode": "online", "scenario": "hairpin", "seed": seed, "profile": "clean", "protected": False,
                     "external": True, "trace_id": offset, "reference_path": ref_lookup[("hairpin", True, seed)]})
    m.write_json(stage / "job_manifest.json", {"planned": len(jobs), "jobs": jobs})
    with np.load(OUT / "t5" / "A-K5-linear.npz", allow_pickle=False) as source:
        k5_basis, k5_prior = np.asarray(source["basis"]), float(source["prior"])
    results, failures = [], []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {}
        for job in jobs:
            basis = k5_basis if job["model"] == "K5-linear" else None
            prior = k5_prior if basis is not None else 1.0
            futures[pool.submit(simulate_job, job, models[job["model"]], norms, basis, prior)] = job
        for index, future in enumerate(as_completed(futures), 1):
            try: results.append(future.result())
            except Exception as exc: failures.append({"job": futures[future], "error": repr(exc)})
            print(f"CL [{index:03d}/{len(jobs)}] failures={len(failures)}", flush=True)
    results.sort(key=lambda row: (row["model"], row["scenario"], row["profile"], row["protected"], row["seed"]))
    fields = list(results[0])
    import csv
    with (OUT / "closed_loop_metrics.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(results)
    m.write_json(stage / "results.json", {"results": results, "failures": failures})
    accepted = not failures and len(results) == len(jobs)
    m.write_json(complete, {"stage": "T8", "status": "complete" if accepted else "partial_failure", "accepted": accepted,
                            "official_candidates": [], "diagnostic_runs": len(results), "failures": len(failures),
                            "results_sha256": m.uv2.sha256(stage / "results.json")})
    m.uv2.append_log("W0069", "v2诊断闭环", [
        f"绝对部署候选为空，正式闭环=0；统一有限控制集20步适配器完成诊断={len(results)}/{len(jobs)}，失败={len(failures)}。",
        "K0/K1覆盖100m clean、单移线、回头弯以及IID/burst/delay/DoS有无状态传播保护；K5+A只做外部参数回头弯。",
        f"结果hash={m.uv2.sha256(stage/'results.json')}；全部标记diagnostic_only_offline_gate_failed。",
    ])


if __name__ == "__main__": main()

"""v3r window evaluator and fold metrics.

Evaluates at the frozen CACHE window starts (the V2-compatible window set) with
full per-row evidence: J_common, group errors, force/internal/yaw errors,
latent norm, normalized max abs and divergence.  stress_rollout_v3r accepts
only explicit entries (never the validation split), fixing E08.
"""

from __future__ import annotations

import time

import numpy as np
import torch

from data_contract import load_cache
from evaluation_v2 import config_key, load_frozen_model
from lift import TriangularResidualKoopman
from physics_decoder import R3Decoder

YAW_INDICES = np.asarray([2, 21, 24, 27, 30])
STATE_GROUPS = {"g0": slice(0, 3), "g1": slice(3, 19), "g2": slice(19, 31), "g3": slice(31, 47)}


def _normalized_metrics(prediction_si, target_si, normalization):
    normalized_error = (prediction_si - target_si) / normalization["relative_state47_scale"]
    group_errors = {
        name: float(np.sqrt(np.mean(normalized_error[selected] ** 2)))
        for name, selected in STATE_GROUPS.items()
    }
    return normalized_error, group_errors


def evaluate_windows(
    model: TriangularResidualKoopman,
    entries: list[dict],
    normalization: dict,
    protocol: dict,
    params_resolver,
    decoder: R3Decoder,
    *,
    seed_label: str,
    device="cpu",
    dtype=torch.float64,
    horizons=(1, 5, 10, 20),
) -> list[dict]:
    """Per-window rows at the frozen cache window starts (V2 window set)."""
    model.eval()
    model.to(device)
    model.to(dtype)
    weights = protocol["metric_weights"]
    rows = []
    with torch.no_grad():
        for entry in entries:
            cache = load_cache(entry["cache_path"])
            params = params_resolver(int(entry["seed"]), protocol)
            relative = np.asarray(cache["relative_state47"], dtype=np.float64)
            control = np.asarray(cache["control7"], dtype=np.float64)
            for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
                start = int(start)
                for horizon in horizons:
                    horizon = int(horizon)
                    x0_np = (relative[start] - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"]
                    u_np = (control[start : start + horizon] - normalization["control7_mean"]) / normalization["control7_scale"]
                    x0 = torch.as_tensor(x0_np, dtype=dtype, device=device)[None]
                    u_seq = torch.as_tensor(u_np, dtype=dtype, device=device)[None]
                    started = time.perf_counter()
                    rollout = model.rollout(x0, u_seq, (horizon,), return_eta=True)
                    elapsed = time.perf_counter() - started
                    pred_n = rollout["xhat"][0, horizon - 1]
                    latent_norm = float(torch.linalg.vector_norm(rollout["eta"][0, horizon]).item())
                    prediction = (pred_n.cpu().numpy() * normalization["relative_state47_scale"]) + normalization["relative_state47_mean"]
                    target = relative[start + horizon]
                    normalized_error, group_errors = _normalized_metrics(prediction, target, normalization)
                    predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                    true_force = np.asarray(cache["force_payload_body8"][start + horizon], dtype=float)
                    true_internal = np.asarray(cache["internal_force8"][start + horizon], dtype=float)
                    force_error = (predicted_force - true_force) / normalization["force_payload_body8_scale"]
                    internal_error = (predicted_internal - true_internal) / normalization["internal_force8_scale"]
                    metrics = {
                        "e_core": group_errors["g0"],
                        "e_relative": float(np.sqrt(np.mean(normalized_error[3:] ** 2))),
                        "e_force4": float(np.sqrt(np.mean(force_error**2))),
                        "e_internal": float(np.sqrt(np.mean(internal_error**2))),
                        "e_yaw": float(np.sqrt(np.mean(normalized_error[YAW_INDICES] ** 2))),
                        "state47_rmse_si": float(np.sqrt(np.mean((prediction - target) ** 2))),
                        "force8_rmse_n": float(np.sqrt(np.mean((predicted_force - true_force) ** 2))),
                        "internal8_rmse_n": float(np.sqrt(np.mean((predicted_internal - true_internal) ** 2))),
                    }
                    for name, selected in STATE_GROUPS.items():
                        metrics[f"e_{name}_norm"] = float(np.sqrt(np.mean(normalized_error[selected] ** 2)))
                    j_common = sum(
                        float(weights[name]) * metrics[f"e_{name}"]
                        for name in ("core", "relative", "force4", "internal", "yaw")
                    ) / float(weights["common_weight_sum"])
                    finite = bool(np.all(np.isfinite(prediction)) and np.all(np.isfinite(predicted_force)) and np.isfinite(j_common))
                    divergent = bool(
                        not finite
                        or np.max(np.abs(normalized_error)) > float(protocol["training"]["divergence_abs_normalized"])
                    )
                    rows.append(
                        {
                            "model_kind": "GDM_RK",
                            "variant": "S0",
                            "ridge": None,
                            "rank": None,
                            "seed_label": seed_label,
                            "trajectory_id": int(entry["trajectory_id"]),
                            "base_family_id": entry["base_family_id"],
                            "split": entry["split"],
                            "scenario": entry["scenario"],
                            "direction": entry["direction"],
                            "member": entry["member"],
                            "plant": entry["plant"],
                            "window": str(category),
                            "window_start": start,
                            "horizon": horizon,
                            "j_common": j_common,
                            "divergent": divergent,
                            "inference_s": elapsed,
                            "latent_norm": latent_norm,
                            "normalized_max_abs": float(np.max(np.abs(normalized_error))),
                            **metrics,
                        }
                    )
    return rows


def evaluate_s0_windows(
    frozen,
    entries: list[dict],
    normalization: dict,
    protocol: dict,
    *,
    seed_label: str,
    horizons=(1, 5, 10, 20),
) -> list[dict]:
    """Frozen S0 evaluated on the same window set (V2 numpy path)."""
    from evaluation_v2 import evaluate_model

    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    base = evaluate_model(
        model, entries, normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label=seed_label,
    )
    # normalize rows to the common schema (add missing audit fields)
    for row in base:
        row.setdefault("latent_norm", None)
        row.setdefault("normalized_max_abs", None)
    return base


def macro_j(rows: list[dict], horizon: int) -> float:
    selected = [row for row in rows if int(row["horizon"]) == int(horizon)]
    if not selected:
        return float("nan")
    scenario = {}
    for row in selected:
        scenario.setdefault(row["scenario"], []).append(float(row["j_common"]))
    return float(np.mean([np.mean(value) for value in scenario.values()]))


def qcv_from_rows(rows: list[dict], protocol: dict) -> float:
    weights = protocol["f4"]["qcv_weights"]
    return sum(float(weights[str(h)]) * macro_j(rows, h) for h in (1, 5, 10, 20))


def stress_rollout_v3r(
    model: TriangularResidualKoopman,
    entries: list[dict],
    normalization: dict,
    protocol: dict,
    params_resolver,
    decoder: R3Decoder,
    *,
    device="cpu",
    dtype=torch.float64,
    horizons=(40, 80),
    d5_starts=(100, 120),
) -> dict:
    """D5 long-horizon stress on EXPLICIT entries only (train-CV folds for the
    F/M layers; never the old validation split)."""
    model.eval()
    model.to(device)
    model.to(dtype)
    results = []
    with torch.no_grad():
        for entry in entries:
            if entry["scenario"] != "D5":
                continue
            cache = load_cache(entry["cache_path"])
            params = params_resolver(int(entry["seed"]), protocol)
            relative = np.asarray(cache["relative_state47"], dtype=np.float64)
            control = np.asarray(cache["control7"], dtype=np.float64)
            length = relative.shape[0]
            for start in d5_starts:
                for horizon in horizons:
                    if start + horizon >= length:
                        continue
                    x0_np = (relative[start] - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"]
                    u_np = (control[start : start + horizon] - normalization["control7_mean"]) / normalization["control7_scale"]
                    x0 = torch.as_tensor(x0_np, dtype=dtype, device=device)[None]
                    u_seq = torch.as_tensor(u_np, dtype=dtype, device=device)[None]
                    rollout = model.rollout(x0, u_seq, (int(horizon),), return_eta=True)
                    pred_n = rollout["xhat"][0, int(horizon) - 1]
                    latent_norm = float(torch.linalg.vector_norm(rollout["eta"][0, int(horizon)]).item())
                    prediction = (pred_n.cpu().numpy() * normalization["relative_state47_scale"]) + normalization["relative_state47_mean"]
                    target = relative[start + horizon]
                    normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                    divergent = bool(
                        not (np.all(np.isfinite(prediction)) and np.all(np.isfinite(normalized_error)))
                        or np.max(np.abs(normalized_error)) > float(protocol["training"]["divergence_abs_normalized"])
                    )
                    predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                    true_force = np.asarray(cache["force_payload_body8"][start + horizon], dtype=float)
                    true_internal = np.asarray(cache["internal_force8"][start + horizon], dtype=float)
                    results.append(
                        {
                            "trajectory_id": int(entry["trajectory_id"]),
                            "base_family_id": entry["base_family_id"],
                            "direction": entry["direction"],
                            "plant": entry["plant"],
                            "window_start": int(start),
                            "horizon": int(horizon),
                            "state47_rmse_si": float(np.sqrt(np.mean((prediction - target) ** 2))),
                            "normalized_max_abs": float(np.max(np.abs(normalized_error))),
                            "divergent": divergent,
                            "latent_norm": latent_norm,
                            "force8_rmse_n": float(np.sqrt(np.mean((predicted_force - true_force) ** 2))),
                            "internal8_rmse_n": float(np.sqrt(np.mean((predicted_internal - true_internal) ** 2))),
                        }
                    )
    return {
        "rows": results,
        "summary": {
            "row_count": len(results),
            "divergent_count": int(sum(row["divergent"] for row in results)),
            "per_horizon": {
                str(h): {"count": int(sum(1 for row in results if row["horizon"] == h)),
                         "divergent": int(sum(1 for row in results if row["horizon"] == h and row["divergent"]))}
                for h in horizons
            },
        },
        "note": "explicit entries only; no validation split is ever read",
    }

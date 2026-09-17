"""v3 evaluation: torch-model rollout on the SAME windows/controls/horizons as
V2, the S0 wrapper consistency path, and the D5 stress rollout.

The S0 wrapper is exactly evaluation_v2's frozen-model evaluation; the torch
path is used for GDM-RK candidates.  All metrics share the V2 formulas and the
same NumPy R3 readout so candidate rows are directly comparable with S0/B1 rows.
"""

from __future__ import annotations

import time

import numpy as np
import torch

from contracts_v2 import write_csv
from data_contract import load_cache
from evaluation_v2 import config_key, load_frozen_model
from lift import TriangularResidualKoopman
from physics_decoder import R3Decoder


def s0_blocks_from_frozen(frozen) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A0/B0/b0 in normalized coordinates from the frozen S0 FULL_TRAIN model."""
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    coefficients = np.asarray(model["coefficients"], dtype=np.float64)
    a0 = coefficients[:47, :47].T
    b0 = coefficients[47:54, :].T
    bias0 = coefficients[54, :]
    return a0, b0, bias0


def build_gdmrk(
    frozen,
    residual_dim: int,
    hidden_width: int,
    *,
    device=None,
    e_init_scale: float = 0.01,
    dense_f: bool = False,
) -> TriangularResidualKoopman:
    a0, b0, bias0 = s0_blocks_from_frozen(frozen)
    branch_output = residual_dim // 2
    model = TriangularResidualKoopman(
        torch.as_tensor(a0), torch.as_tensor(b0), torch.as_tensor(bias0),
        residual_dim=residual_dim, branch_output=branch_output, hidden_width=hidden_width,
        e_init_scale=e_init_scale, dense_f=dense_f,
    )
    return model


def evaluate_numpy_s0(frozen, data, protocol, *, seed_label: str = "S0_WRAPPER", split: str = "development"):
    """The S0 wrapper: the frozen N6 S0 model evaluated exactly as V2."""
    from evaluation_v2 import evaluate_model

    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    return evaluate_model(
        model, data.split(split), data.normalization, protocol,
        frozen.resolved_params, R3Decoder(frozen.build_planar_grasp_matrix),
        seed_label=seed_label,
    )


def rollout_torch_model(
    model: TriangularResidualKoopman,
    entries: list[dict],
    normalization: dict[str, np.ndarray],
    protocol: dict,
    params_resolver,
    decoder: R3Decoder,
    *,
    seed_label: str,
    device="cpu",
    dtype=torch.float64,
) -> list[dict]:
    """Evaluate a GDM-RK candidate with the V2 window/control/horizon schema."""
    model.eval()
    model.to(device)
    model.to(dtype)
    weights = protocol["metric_weights"]
    yaw_indices = np.asarray([2, 21, 24, 27, 30])
    rel_mean = torch.as_tensor(normalization["relative_state47_mean"], dtype=dtype, device=device)
    rel_scale = torch.as_tensor(normalization["relative_state47_scale"], dtype=dtype, device=device)
    u_mean = torch.as_tensor(normalization["control7_mean"], dtype=dtype, device=device)
    u_scale = torch.as_tensor(normalization["control7_scale"], dtype=dtype, device=device)
    rows = []
    for entry in entries:
        cache = load_cache(entry["cache_path"])
        params = params_resolver(int(entry["seed"]), protocol)
        relative = np.asarray(cache["relative_state47"], dtype=np.float64)
        control = np.asarray(cache["control7"], dtype=np.float64)
        for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
            start = int(start)
            for horizon in protocol["training"]["horizons"]:
                x0_np = (relative[start] - normalization["relative_state47_mean"]) / normalization["relative_state47_scale"]
                u_np = (control[start : start + horizon] - normalization["control7_mean"]) / normalization["control7_scale"]
                x0 = torch.as_tensor(x0_np, dtype=dtype, device=device)[None]
                u_seq = torch.as_tensor(u_np, dtype=dtype, device=device)[None]
                started = time.perf_counter()
                with torch.no_grad():
                    rollout = model.rollout(x0, u_seq, (int(horizon),))
                    pred_n = rollout["xhat"][0, int(horizon) - 1]
                elapsed = time.perf_counter() - started
                prediction = (pred_n.cpu().numpy() * normalization["relative_state47_scale"]) + normalization["relative_state47_mean"]
                target = relative[start + horizon]
                normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                true_force = np.asarray(cache["force_payload_body8"][start + horizon], dtype=float)
                true_internal = np.asarray(cache["internal_force8"][start + horizon], dtype=float)
                force_error = (predicted_force - true_force) / normalization["force_payload_body8_scale"]
                internal_error = (predicted_internal - true_internal) / normalization["internal_force8_scale"]
                metrics = {
                    "e_core": float(np.sqrt(np.mean(normalized_error[:3] ** 2))),
                    "e_relative": float(np.sqrt(np.mean(normalized_error[3:] ** 2))),
                    "e_force4": float(np.sqrt(np.mean(force_error**2))),
                    "e_internal": float(np.sqrt(np.mean(internal_error**2))),
                    "e_yaw": float(np.sqrt(np.mean(normalized_error[yaw_indices] ** 2))),
                    "state47_rmse_si": float(np.sqrt(np.mean((prediction - target) ** 2))),
                    "force8_rmse_n": float(np.sqrt(np.mean((predicted_force - true_force) ** 2))),
                    "internal8_rmse_n": float(np.sqrt(np.mean((predicted_internal - true_internal) ** 2))),
                }
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
                        "horizon": int(horizon),
                        "j_common": j_common,
                        "j_full": None,
                        "e_actuator": None,
                        "actuator_rmse_rad": None,
                        "divergent": divergent,
                        "inference_s": elapsed,
                        **metrics,
                    }
                )
    return rows


def stress_rollout(
    model: TriangularResidualKoopman,
    frozen,
    data,
    protocol: dict,
    *,
    device="cpu",
    dtype=torch.float64,
    horizons: tuple[int, ...] = (40, 80),
    d5_starts: tuple[int, ...] = (100, 120),
) -> dict:
    """D5 stress: long-horizon rollouts on the frozen D5 windows, plus worst
    family and left/right direction breakdown."""
    model.eval()
    model.to(device)
    model.to(dtype)
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    entries = [row for row in data.validation if row["scenario"] == "D5"]
    results = []
    for entry in entries:
        cache = load_cache(entry["cache_path"])
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
                with torch.no_grad():
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
                params = frozen.resolved_params(int(entry["seed"]), protocol)
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
            "max_state47_rmse": float(max(row["state47_rmse_si"] for row in results)) if results else None,
            "max_normalized_abs": float(max(row["normalized_max_abs"] for row in results)) if results else None,
            "per_horizon": {
                str(h): {
                    "count": int(sum(1 for row in results if row["horizon"] == h)),
                    "divergent": int(sum(1 for row in results if row["horizon"] == h and row["divergent"])),
                }
                for h in horizons
            },
        },
        "note": "D5 stress uses validation split; no trajectory end crossing",
    }


def compute_p5c_gates(protocol: dict, candidate_rows: list[dict], s0_rows: list[dict], stress: dict | None, timing: dict | None) -> tuple[dict, dict]:
    """P5C validation gates as a pure function of the evaluation rows.

    Returns (gates, report).  test_p5_gates injects fake rows to verify each
    gate rejects the corresponding failure mode, so a PASS stage can never be
    confused with a candidate that actually passes.
    """
    import numpy as np

    from evaluation_v2 import improvement, macro_summary, paired_family_bootstrap

    gates: dict[str, bool] = {}
    macro_candidate = float(macro_summary(candidate_rows)["j_common_macro"])
    macro_s0 = float(macro_summary(s0_rows)["j_common_macro"])
    improvement_percent = 100.0 * (macro_s0 - macro_candidate) / max(abs(macro_s0), 1e-12)
    gates["validation_macro_improvement"] = improvement_percent >= float(protocol["p5c_gates"]["macro_improvement_min_percent"])

    ci = paired_family_bootstrap(
        candidate_rows, s0_rows,
        replicates=int(protocol["training"]["paired_ci_replicates"]),
        seed=int(protocol["training"]["paired_ci_seed"]),
    )
    gates["paired_ci_positive"] = float(ci["ci95_low_percent"]) > 0.0

    for horizon in (1, 5, 10):
        cand_h = float(macro_summary(candidate_rows, horizon=horizon)["j_common_macro"])
        s0_h = float(macro_summary(s0_rows, horizon=horizon)["j_common_macro"])
        degradation = 100.0 * (cand_h - s0_h) / max(abs(s0_h), 1e-12)
        gates[f"horizon{horizon}_not_worse_3pct"] = degradation <= float(protocol["p5c_gates"]["one_step_degradation_max_percent"])

    gates["divergence_zero"] = all(
        not bool(row["divergent"]) for row in candidate_rows if int(row["horizon"]) == 20
    )

    d7_candidate = float(np.mean([row["j_common"] for row in candidate_rows if int(row["horizon"]) == 20 and row["scenario"] == "D7"]))
    d10_candidate = float(np.mean([row["j_common"] for row in candidate_rows if int(row["horizon"]) == 20 and row["scenario"] == "D10"]))
    d7_s0 = float(np.mean([row["j_common"] for row in s0_rows if int(row["horizon"]) == 20 and row["scenario"] == "D7"]))
    d10_s0 = float(np.mean([row["j_common"] for row in s0_rows if int(row["horizon"]) == 20 and row["scenario"] == "D10"]))
    d7_improvement = 100.0 * (d7_s0 - d7_candidate) / max(abs(d7_s0), 1e-12)
    d10_improvement = 100.0 * (d10_s0 - d10_candidate) / max(abs(d10_s0), 1e-12)
    gates["d7_or_d10_improvement"] = max(d7_improvement, d10_improvement) >= float(protocol["p5c_gates"]["d7_or_d10_improvement_min_percent"])

    d5_candidate = float(np.mean([row["j_common"] for row in candidate_rows if int(row["horizon"]) == 20 and row["scenario"] == "D5"]))
    d5_s0 = float(np.mean([row["j_common"] for row in s0_rows if int(row["horizon"]) == 20 and row["scenario"] == "D5"]))
    d5_improvement = 100.0 * (d5_s0 - d5_candidate) / max(abs(d5_s0), 1e-12)
    gates["d5_not_worse_3pct"] = d5_improvement >= -3.0

    d5_hard_candidate = [row["j_common"] for row in candidate_rows if int(row["horizon"]) == 20 and row["scenario"] == "D5" and int(row["window_start"]) in (100, 120)]
    d5_hard_s0 = [row["j_common"] for row in s0_rows if int(row["horizon"]) == 20 and row["scenario"] == "D5" and int(row["window_start"]) in (100, 120)]
    hard_values = np.asarray(d5_hard_candidate, dtype=float)
    hard_s0_values = np.asarray(d5_hard_s0, dtype=float)
    hard_mean_c = float(np.mean(hard_values)) if hard_values.size else float("nan")
    hard_p95_c = float(np.percentile(hard_values, 95.0)) if hard_values.size else float("nan")
    hard_max_c = float(np.max(hard_values)) if hard_values.size else float("nan")
    hard_mean_s0 = float(np.mean(hard_s0_values)) if hard_s0_values.size else float("nan")
    gates["d5_hard_mean"] = hard_mean_c <= hard_mean_s0 * (1.0 + 0.03)
    gates["d5_hard_p95"] = hard_p95_c <= float(protocol["p5c_gates"]["d5_hard_p95_max"])
    gates["d5_hard_max"] = hard_max_c <= float(protocol["p5c_gates"]["d5_hard_max_max"])

    force_candidate = float(np.mean([row["force8_rmse_n"] for row in candidate_rows if int(row["horizon"]) == 20]))
    force_s0 = float(np.mean([row["force8_rmse_n"] for row in s0_rows if int(row["horizon"]) == 20]))
    internal_candidate = float(np.mean([row["internal8_rmse_n"] for row in candidate_rows if int(row["horizon"]) == 20]))
    internal_s0 = float(np.mean([row["internal8_rmse_n"] for row in s0_rows if int(row["horizon"]) == 20]))
    gates["force_not_worse_5pct"] = 100.0 * (force_candidate - force_s0) / max(abs(force_s0), 1e-12) <= float(protocol["p5c_gates"]["force_internal_degradation_max_percent"])
    gates["internal_not_worse_5pct"] = 100.0 * (internal_candidate - internal_s0) / max(abs(internal_s0), 1e-12) <= float(protocol["p5c_gates"]["force_internal_degradation_max_percent"])

    if stress is not None:
        gates["d5_stress_no_divergence"] = int(stress["summary"]["divergent_count"]) == 0
    if timing is not None:
        gates["gpu_inference_median"] = timing.get("gpu_median_ms") is None or timing["gpu_median_ms"] <= float(protocol["p5c_gates"]["gpu_infer_median_ms"])
        gates["gpu_inference_p99"] = timing.get("gpu_p99_ms") is None or timing["gpu_p99_ms"] <= float(protocol["p5c_gates"]["gpu_infer_p99_ms"])
        gates["cpu_inference_median"] = timing.get("cpu_median_ms") is None or timing["cpu_median_ms"] <= float(protocol["p5c_gates"]["cpu_infer_median_ms"])

    report = {
        "macro_improvement_percent": float(improvement_percent),
        "macro_candidate": float(macro_candidate),
        "macro_s0": float(macro_s0),
        "paired_ci": ci,
        "d7": {"candidate": float(d7_candidate), "s0": float(d7_s0), "improvement_percent": float(d7_improvement)},
        "d10": {"candidate": float(d10_candidate), "s0": float(d10_s0), "improvement_percent": float(d10_improvement)},
        "d5": {"candidate": float(d5_candidate), "s0": float(d5_s0), "improvement_percent": float(d5_improvement)},
        "d5_hard": {"candidate_mean": hard_mean_c, "candidate_p95": hard_p95_c, "candidate_max": hard_max_c, "s0_mean": hard_mean_s0},
        "force": {"candidate": float(force_candidate), "s0": float(force_s0)},
        "internal": {"candidate": float(internal_candidate), "s0": float(internal_s0)},
        "gates": gates,
    }
    return gates, report

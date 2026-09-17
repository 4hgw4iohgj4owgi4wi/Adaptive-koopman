from __future__ import annotations

"""Unified v2 evaluation engine (1/5/10/20-step, four windows, D0-D11, physics
quantities and paired CI) plus the P0 element-wise regression against the
frozen N6 evaluation.

The metric math is a faithful re-implementation of the frozen N6
``evaluation.py`` (identical operation order, float64) so that, given the same
frozen models, normalization, caches and parameters, the recomputed tables are
bit-close to N6.  P0's hard gates verify this numerically.
"""

import csv
import gzip
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from contracts_v2 import load_npz, read_json, write_csv
from data_contract import load_cache
from physics_decoder import R3Decoder


# --------------------------------------------------------------------------
# model fitting (identical math to frozen evaluation.py)
# --------------------------------------------------------------------------

def _normalized_state_target(
    cache: dict[str, np.ndarray], variant: str, normalization: dict[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    relative = np.asarray(cache["relative_state47"], dtype=float)
    actual = np.asarray(cache["actual_steering4"], dtype=float)
    ukey = "control11" if "control11_mean" in normalization else "control7"
    control = np.asarray(cache[ukey], dtype=float)
    rel_mean = normalization["relative_state47_mean"]
    rel_scale = normalization["relative_state47_scale"]
    act_mean = normalization["actual_steering4_mean"]
    act_scale = normalization["actual_steering4_scale"]
    u_mean = normalization[f"{ukey}_mean"]
    u_scale = normalization[f"{ukey}_scale"]
    selected = str(variant).upper()
    if selected == "S0":
        state = (relative[:-1] - rel_mean) / rel_scale
        target = (relative[1:] - rel_mean) / rel_scale
        side = np.empty((len(control), 0))
    elif selected == "S1":
        state = np.c_[
            (relative[:-1] - rel_mean) / rel_scale,
            (actual[:-1] - act_mean) / act_scale,
        ]
        target = np.c_[
            (relative[1:] - rel_mean) / rel_scale,
            (actual[1:] - act_mean) / act_scale,
        ]
        side = np.empty((len(control), 0))
    elif selected == "S2":
        state = np.c_[
            (relative[:-1] - rel_mean) / rel_scale,
            (actual[:-1] - act_mean) / act_scale,
        ]
        target = (relative[1:] - rel_mean) / rel_scale
        side = np.c_[
            (np.asarray(cache["analytic_actual_next4"], dtype=float) - act_mean) / act_scale,
            np.asarray(cache["analytic_rate_mask4"], dtype=float),
            np.asarray(cache["analytic_angle_mask4"], dtype=float),
        ]
    else:
        raise ValueError(variant)
    return state, (control - u_mean) / u_scale, side, target


def design_matrix(
    cache: dict[str, np.ndarray],
    variant: str,
    model_kind: str,
    normalization: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, dict]:
    state, control, side, target = _normalized_state_target(cache, variant, normalization)
    blocks = [state, control, side]
    bilinear_start = sum(block.shape[1] for block in blocks)
    if model_kind == "M1_LOWRANK_BILINEAR":
        blocks.append((control[:, :, None] * state[:, None, :]).reshape(len(state), -1))
    elif model_kind != "M0_FIXED_LINEAR":
        raise ValueError(model_kind)
    blocks.append(np.ones((len(state), 1)))
    design = np.concatenate(blocks, axis=1)
    return design, target, {
        "state_dimension": state.shape[1],
        "control_dimension": control.shape[1],
        "side_dimension": side.shape[1],
        "output_dimension": target.shape[1],
        "bilinear_start": bilinear_start,
    }


def accumulate_fit_statistics(
    entries: list[dict],
    variant: str,
    model_kind: str,
    normalization: dict[str, np.ndarray],
    family_counts: Counter | None = None,
) -> dict:
    gram = None
    cross = None
    layout = None
    row_count = 0
    for entry in entries:
        weight = 1 if family_counts is None else int(family_counts[entry["base_family_id"]])
        if weight <= 0:
            continue
        design, target, current_layout = design_matrix(
            load_cache(Path(entry["cache_path"])), variant, model_kind, normalization
        )
        if layout is None:
            layout = current_layout
            gram = np.zeros((design.shape[1], design.shape[1]), dtype=float)
            cross = np.zeros((design.shape[1], target.shape[1]), dtype=float)
        if current_layout != layout:
            raise ValueError("fit layout drift")
        gram += weight * (design.T @ design)
        cross += weight * (design.T @ target)
        row_count += weight * len(design)
    if gram is None or cross is None or layout is None:
        raise ValueError("empty fit statistics")
    return {"gram": gram, "cross": cross, "layout": layout, "row_count": row_count}


def solve_model(
    statistics: dict,
    *,
    variant: str,
    model_kind: str,
    ridge: float,
    rank: int | None,
) -> dict:
    gram = np.asarray(statistics["gram"], dtype=float)
    cross = np.asarray(statistics["cross"], dtype=float)
    regularizer = np.eye(gram.shape[0]) * float(ridge)
    regularizer[-1, -1] = 0.0
    regularized = gram + regularizer
    coefficients = np.linalg.solve(regularized, cross)
    layout = dict(statistics["layout"])
    if model_kind == "M1_LOWRANK_BILINEAR":
        if rank not in {1, 2, 4}:
            raise ValueError(f"invalid low-rank bilinear rank: {rank}")
        start = int(layout["bilinear_start"])
        state_dim = int(layout["state_dimension"])
        control_dim = int(layout["control_dimension"])
        output_dim = int(layout["output_dimension"])
        stop = start + state_dim * control_dim
        tensor = coefficients[start:stop].reshape(control_dim, state_dim, output_dim)
        truncated = np.empty_like(tensor)
        for index, matrix in enumerate(tensor):
            u, singular, vt = np.linalg.svd(matrix, full_matrices=False)
            keep = min(int(rank), len(singular))
            truncated[index] = (u[:, :keep] * singular[:keep]) @ vt[:keep]
        coefficients[start:stop] = truncated.reshape(control_dim * state_dim, output_dim)
        parameter_count = (
            (start + 1) * output_dim
            + control_dim * int(rank) * (state_dim + output_dim + 1)
        )
    else:
        parameter_count = coefficients.size
    singular = np.linalg.svd(regularized, compute_uv=False)
    condition = float(singular[0] / max(singular[-1], 1.0e-300))
    return {
        "variant": str(variant),
        "model_kind": str(model_kind),
        "ridge": float(ridge),
        "rank": None if rank is None else int(rank),
        "coefficients": coefficients,
        "layout": layout,
        "condition_number": condition,
        "parameter_count": int(parameter_count),
        "fit_row_count": int(statistics["row_count"]),
    }


def _features_one(
    state_normalized: np.ndarray,
    control_normalized: np.ndarray,
    side: np.ndarray,
    model: dict,
) -> np.ndarray:
    blocks = [state_normalized, control_normalized, side]
    if model["model_kind"] == "M1_LOWRANK_BILINEAR":
        blocks.append((control_normalized[:, None] * state_normalized[None, :]).ravel())
    blocks.append(np.ones(1))
    return np.concatenate(blocks)


# --------------------------------------------------------------------------
# actuator (identical math to frozen steering_actuator / actuator_rollout)
# --------------------------------------------------------------------------

def _step_actuator(
    delta_req_rad: np.ndarray,
    delta_act_rad: np.ndarray,
    step_s: float,
    tau_delta_s: float,
    rate_max_radps: float,
    angle_max_rad: float,
) -> dict[str, np.ndarray]:
    request = np.asarray(delta_req_rad, dtype=float)
    actual = np.asarray(delta_act_rad, dtype=float)
    decay = float(np.exp(-float(step_s) / float(tau_delta_s)))
    free_next = request + decay * (actual - request)
    free_increment = free_next - actual
    maximum_increment = float(rate_max_radps) * float(step_s)
    rate_limited_increment = np.clip(free_increment, -maximum_increment, maximum_increment)
    before_angle_clip = actual + rate_limited_increment
    actual_next = np.clip(before_angle_clip, -float(angle_max_rad), float(angle_max_rad))
    rate = (actual_next - actual) / float(step_s)
    return {
        "delta_act_next_rad": actual_next,
        "delta_rate_radps": rate,
        "free_next_rad": free_next,
        "rate_limited_mask": np.abs(free_increment - rate_limited_increment) > 1.0e-15,
        "angle_limited_mask": np.abs(before_angle_clip - actual_next) > 1.0e-15,
    }


def rollout_actuator_interval(
    delta_act_k_rad: np.ndarray,
    delta_req_k_rad: np.ndarray,
    *,
    plant_step_s: float,
    substeps: int,
    tau_delta_s: float,
    rate_max_radps: float,
    angle_max_rad: float,
) -> dict[str, np.ndarray]:
    actual = np.asarray(delta_act_k_rad, dtype=float).copy()
    request = np.asarray(delta_req_k_rad, dtype=float)
    endpoints = []
    rate_masks = []
    angle_masks = []
    for _ in range(int(substeps)):
        previous = actual.copy()
        result = _step_actuator(
            request, previous, plant_step_s, tau_delta_s, rate_max_radps, angle_max_rad
        )
        actual = result["delta_act_next_rad"]
        endpoints.append(actual.copy())
        rate_masks.append(result["rate_limited_mask"].copy())
        angle_masks.append(result["angle_limited_mask"].copy())
    return {
        "delta_act_k1_rad": actual,
        "rate_limited_substeps": np.asarray(rate_masks, dtype=bool),
        "angle_limited_substeps": np.asarray(angle_masks, dtype=bool),
    }


def _rollout_actuator_step(
    delta_act_k_rad: np.ndarray,
    delta_req_k_rad: np.ndarray,
    *,
    model_step_s: float,
    plant_step_s: float,
    tau_delta_s: float,
    rate_max_radps: float,
    angle_max_rad: float,
) -> dict[str, np.ndarray]:
    substeps = int(round(float(model_step_s) / float(plant_step_s)))
    return rollout_actuator_interval(
        delta_act_k_rad,
        delta_req_k_rad,
        plant_step_s=plant_step_s,
        substeps=substeps,
        tau_delta_s=tau_delta_s,
        rate_max_radps=rate_max_radps,
        angle_max_rad=angle_max_rad,
    )


# --------------------------------------------------------------------------
# rollout + evaluation (identical math to frozen evaluation.py)
# --------------------------------------------------------------------------

def rollout_model(
    model: dict,
    cache: dict[str, np.ndarray],
    start: int,
    horizon: int,
    normalization: dict[str, np.ndarray],
    protocol: dict,
) -> tuple[np.ndarray, np.ndarray | None, float]:
    variant = model["variant"]
    rel_mean = normalization["relative_state47_mean"]
    rel_scale = normalization["relative_state47_scale"]
    act_mean = normalization["actual_steering4_mean"]
    act_scale = normalization["actual_steering4_scale"]
    u_mean = normalization["control7_mean"]
    u_scale = normalization["control7_scale"]
    ukey = "control11" if "control11_mean" in normalization else "control7"
    if ukey == "control11":
        u_mean = normalization["control11_mean"]
        u_scale = normalization["control11_scale"]
    relative = np.asarray(cache["relative_state47"][start], dtype=float).copy()
    actual = np.asarray(cache["actual_steering4"][start], dtype=float).copy()
    tau_delta_s = float(protocol["actuator"]["tau_delta_s"])
    rate_max_radps = float(protocol["actuator"]["rate_max_radps"])
    angle_max_rad = float(np.deg2rad(protocol["actuator"]["angle_max_deg"]))
    model_step_s = float(protocol["actuator"]["model_step_s"])
    plant_step_s = float(protocol["actuator"]["plant_step_s"])
    elapsed = 0.0
    for offset in range(int(horizon)):
        control = np.asarray(cache[ukey][start + offset], dtype=float)
        control_n = (control - u_mean) / u_scale
        if variant == "S0":
            state_n = (relative - rel_mean) / rel_scale
            side = np.empty(0)
        else:
            state_n = np.r_[
                (relative - rel_mean) / rel_scale,
                (actual - act_mean) / act_scale,
            ]
            side = np.empty(0)
            if variant == "S2":
                analytic = _rollout_actuator_step(
                    actual,
                    control[-4:],
                    model_step_s=model_step_s,
                    plant_step_s=plant_step_s,
                    tau_delta_s=tau_delta_s,
                    rate_max_radps=rate_max_radps,
                    angle_max_rad=angle_max_rad,
                )
                analytic_next = analytic["delta_act_k1_rad"]
                side = np.r_[
                    (analytic_next - act_mean) / act_scale,
                    np.any(analytic["rate_limited_substeps"], axis=0).astype(float),
                    np.any(analytic["angle_limited_substeps"], axis=0).astype(float),
                ]
        started = time.perf_counter()
        prediction_n = _features_one(state_n, control_n, side, model) @ model["coefficients"]
        elapsed += time.perf_counter() - started
        if variant == "S1":
            relative = prediction_n[:47] * rel_scale + rel_mean
            actual = prediction_n[47:] * act_scale + act_mean
        else:
            relative = prediction_n[:47] * rel_scale + rel_mean
            if variant == "S2":
                actual = analytic_next
    return relative, None if variant == "S0" else actual, elapsed


def evaluate_model(
    model: dict,
    entries: list[dict],
    normalization: dict[str, np.ndarray],
    protocol: dict,
    params_resolver,
    decoder: R3Decoder,
    *,
    seed_label: str,
) -> list[dict]:
    rows = []
    weights = protocol["metric_weights"]
    yaw_indices = np.asarray([2, 21, 24, 27, 30])
    for entry in entries:
        cache = load_cache(Path(entry["cache_path"]))
        params = params_resolver(int(entry["seed"]), protocol)
        for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
            start = int(start)
            for horizon in protocol["training"]["horizons"]:
                prediction, actuator_prediction, infer_s = rollout_model(
                    model, cache, start, int(horizon), normalization, protocol
                )
                target = np.asarray(cache["relative_state47"][start + horizon], dtype=float)
                normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = decoder.connector_force(
                    prediction, params, entry["law"]
                )
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
                numerator = sum(
                    float(weights[name]) * metrics[f"e_{name}"]
                    for name in ("core", "relative", "force4", "internal", "yaw")
                )
                j_common = numerator / float(weights["common_weight_sum"])
                if actuator_prediction is None:
                    e_actuator = None
                    j_full = None
                    actuator_rmse = None
                else:
                    actuator_target = np.asarray(cache["actual_steering4"][start + horizon], dtype=float)
                    actuator_normalized = (actuator_prediction - actuator_target) / normalization["actual_steering4_scale"]
                    e_actuator = float(np.sqrt(np.mean(actuator_normalized**2)))
                    actuator_rmse = float(np.sqrt(np.mean((actuator_prediction - actuator_target) ** 2)))
                    j_full = float(weights["common_weight_sum"]) * j_common + float(weights["actuator"]) * e_actuator
                finite = bool(
                    np.all(np.isfinite(prediction))
                    and np.all(np.isfinite(predicted_force))
                    and np.isfinite(j_common)
                )
                divergent = bool(
                    not finite
                    or np.max(np.abs(normalized_error)) > float(protocol["training"]["divergence_abs_normalized"])
                )
                rows.append(
                    {
                        "model_kind": model["model_kind"],
                        "variant": model["variant"],
                        "ridge": model["ridge"],
                        "rank": model["rank"],
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
                        "j_full": j_full,
                        "e_actuator": e_actuator,
                        "actuator_rmse_rad": actuator_rmse,
                        "divergent": divergent,
                        "inference_s": infer_s,
                        **metrics,
                    }
                )
    return rows


# --------------------------------------------------------------------------
# summaries (identical math to frozen evaluation.py)
# --------------------------------------------------------------------------

def macro_summary(rows: list[dict], *, horizon: int = 20) -> dict:
    selected = [row for row in rows if int(row["horizon"]) == int(horizon)]
    if not selected:
        raise ValueError("no rows for macro summary")
    scenario = defaultdict(list)
    window = defaultdict(list)
    for row in selected:
        scenario[row["scenario"]].append(float(row["j_common"]))
        window[row["window"]].append(float(row["j_common"]))
    return {
        "j_common_macro": float(np.mean([np.mean(value) for value in scenario.values()])),
        "scenario_j_common": {key: float(np.mean(value)) for key, value in sorted(scenario.items())},
        "window_j_common": {key: float(np.mean(value)) for key, value in sorted(window.items())},
        "divergence_rate": float(np.mean([bool(row["divergent"]) for row in selected])),
        "inference_mean_s_per_window": float(
            np.mean([float(row.get("inference_s", 0.0)) for row in selected])
        ),
        "row_count": len(selected),
    }


def field_macro(rows: list[dict], field: str, horizon: int = 20) -> float | None:
    selected = [row for row in rows if int(row["horizon"]) == horizon and row[field] is not None]
    if not selected:
        return None
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in selected:
        grouped[row["scenario"]].append(float(row[field]))
    return float(np.mean([np.mean(value) for value in grouped.values()]))


def improvement(baseline: float, candidate: float) -> float:
    return 100.0 * (baseline - candidate) / max(abs(baseline), 1.0e-12)


def paired_family_bootstrap(
    candidate_rows: list[dict],
    baseline_rows: list[dict],
    *,
    replicates: int,
    seed: int,
) -> dict:
    def family_scores(rows):
        bucket = defaultdict(list)
        for row in rows:
            if int(row["horizon"]) == 20:
                bucket[row["base_family_id"]].append(float(row["j_common"]))
        return {key: float(np.mean(value)) for key, value in bucket.items()}

    candidate = family_scores(candidate_rows)
    baseline = family_scores(baseline_rows)
    families = sorted(set(candidate) & set(baseline))
    if not families:
        raise ValueError("no paired families")
    improvement_array = np.asarray(
        [100.0 * (baseline[key] - candidate[key]) / max(abs(baseline[key]), 1.0e-12) for key in families]
    )
    rng = np.random.default_rng(int(seed))
    draws = np.empty(int(replicates), dtype=float)
    for index in range(int(replicates)):
        draws[index] = float(np.mean(rng.choice(improvement_array, size=len(improvement_array), replace=True)))
    return {
        "family_count": len(families),
        "mean_improvement_percent": float(np.mean(improvement_array)),
        "median_improvement_percent": float(np.median(improvement_array)),
        "ci95_low_percent": float(np.percentile(draws, 2.5)),
        "ci95_high_percent": float(np.percentile(draws, 97.5)),
        "replicates": int(replicates),
        "seed": int(seed),
    }


def compare_rows(baseline: list[dict], candidate: list[dict], protocol: dict) -> dict:
    base = macro_summary(baseline)
    cand = macro_summary(candidate)
    scenarios = {
        name: improvement(base["scenario_j_common"][name], cand["scenario_j_common"][name])
        for name in base["scenario_j_common"]
    }
    windows = {
        name: improvement(base["window_j_common"][name], cand["window_j_common"][name])
        for name in base["window_j_common"]
        if name in cand["window_j_common"]
    }
    return {
        "macro_improvement_percent": improvement(base["j_common_macro"], cand["j_common_macro"]),
        "scenario_improvement_percent": scenarios,
        "window_improvement_percent": windows,
        "max_important_degradation_percent": max(
            [max(-scenarios[name], 0.0) for name in protocol["training"]["important_scenarios"]],
            default=0.0,
        ),
        "divergence_rate_change": cand["divergence_rate"] - base["divergence_rate"],
        "inference_ratio": cand["inference_mean_s_per_window"] / max(base["inference_mean_s_per_window"], 1.0e-12),
        "paired_ci": paired_family_bootstrap(
            candidate,
            baseline,
            replicates=int(protocol["training"]["paired_ci_replicates"]),
            seed=int(protocol["training"]["paired_ci_seed"]),
        ),
    }


# --------------------------------------------------------------------------
# frozen model loading + orchestration
# --------------------------------------------------------------------------

def config_key(model_kind: str, variant: str, rank: int | None) -> str:
    return f"{model_kind}|{variant}|{'none' if rank is None else rank}"


def load_frozen_model(path: Path) -> dict:
    """Load one frozen N6 model (NPZ coefficients + sidecar JSON metadata)."""
    data = load_npz(path)
    metadata = read_json(path.with_suffix(".json"))
    return {**metadata, "coefficients": data["coefficients"]}


def frozen_model_paths(frozen, protocol: dict) -> dict[str, Path]:
    """Map every frozen config key to its FULL_TRAIN model path."""
    paths: dict[str, Path] = {}
    models_dir = frozen.n6_models_dir()
    for variant in protocol["interfaces"]["variants"]:
        for kind in protocol["training"]["models"]:
            ranks = [None] if kind == "M0_FIXED_LINEAR" else protocol["training"]["ranks"]
            for rank in ranks:
                key = config_key(kind, variant, rank)
                stem = key.replace("|", "_") + "_FULL_TRAIN.npz"
                paths[key] = models_dir / stem
    return paths


def evaluate_all(
    frozen,
    data: "FrozenData",
    protocol: dict,
    *,
    split: str = "development",
    seed_label: str = "FULL_TRAIN",
    configs: list[str] | None = None,
) -> tuple[dict[str, list[dict]], dict[str, dict], dict[str, dict]]:
    """Evaluate the frozen N6 FULL_TRAIN models on one split.

    Returns (detailed rows by config, macro summaries by config, models by config).
    """
    entries = data.split(split)
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    paths = frozen_model_paths(frozen, protocol)
    selected = configs if configs is not None else sorted(paths)
    detailed: dict[str, list[dict]] = {}
    summaries: dict[str, dict] = {}
    models: dict[str, dict] = {}
    for key in selected:
        path = paths[key]
        if not path.is_file():
            raise RuntimeError(f"frozen model missing: {path}")
        model = load_frozen_model(path)
        models[key] = model
        rows = evaluate_model(
            model, entries, normalization, protocol, frozen.resolved_params, decoder,
            seed_label=seed_label,
        )
        detailed[key] = rows
        summary = macro_summary(rows)
        summaries[key] = {
            "config_key": key,
            "seed_label": seed_label,
            **summary,
            "j_full_macro": field_macro(rows, "j_full"),
            "e_actuator_macro": field_macro(rows, "e_actuator"),
            "condition_number": model["condition_number"],
            "parameter_count": model["parameter_count"],
            "fit_row_count": model["fit_row_count"],
        }
    return detailed, summaries, models


# --------------------------------------------------------------------------
# P0 regression against frozen N6 records
# --------------------------------------------------------------------------

def _row_identity(rows: list[dict]) -> set[tuple]:
    return {(int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"])) for row in rows}


def _read_n6_detailed(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _family_counts(train_families: list[str], seed: int) -> Counter:
    rng = np.random.default_rng(int(seed))
    return Counter(rng.choice(train_families, size=len(train_families), replace=True))


def bootstrap_summaries(
    frozen,
    data,
    protocol: dict,
    seeds: list[int],
    keys: list[str],
    selected: dict[str, dict],
    train_families: list[str],
) -> dict[tuple[int, str], dict]:
    """Refit every selected config with family-bootstrap counts and evaluate on
    development.  Mirrors the frozen N6 bootstrap loop."""
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    results: dict[tuple[int, str], dict] = {}
    for seed in seeds:
        counts = _family_counts(train_families, seed)
        statistics: dict[tuple[str, str], dict] = {}
        for variant in protocol["interfaces"]["variants"]:
            for kind in protocol["training"]["models"]:
                statistics[(variant, kind)] = accumulate_fit_statistics(
                    data.train, variant, kind, normalization, counts
                )
        for key in keys:
            selected_config = selected[key]
            model = solve_model(
                statistics[(selected_config["variant"], selected_config["model_kind"])],
                variant=selected_config["variant"],
                model_kind=selected_config["model_kind"],
                ridge=selected_config["ridge"],
                rank=selected_config["rank"],
            )
            rows = evaluate_model(
                model, data.development, normalization, protocol, frozen.resolved_params,
                decoder, seed_label=str(seed),
            )
            results[(int(seed), key)] = {
                "config_key": key,
                "seed_label": str(seed),
                **macro_summary(rows),
                "j_full_macro": field_macro(rows, "j_full"),
                "e_actuator_macro": field_macro(rows, "e_actuator"),
                "condition_number": model["condition_number"],
                "parameter_count": model["parameter_count"],
            }
    return results


def reproduce_n6_tables(
    frozen,
    data,
    protocol: dict,
) -> dict:
    """Recompute the complete N6 main tables from frozen models + frozen data.

    Returns detailed rows (central, 12 configs), central summaries, the
    s1/s2/bilinear comparisons including seed directions (primary seeds, plus
    backup seeds whenever the frozen classification rules select them), and the
    classification/selection outcomes.
    """
    detailed, summaries, _ = evaluate_all(frozen, data, protocol, split="development")
    n6_stage = frozen.n6_stage_dir()
    selections = read_json(n6_stage / "frozen_hyperparameter_selection.json")

    m0_keys = [config_key("M0_FIXED_LINEAR", variant, None) for variant in protocol["interfaces"]["variants"]]
    m1_s0_keys = [config_key("M1_LOWRANK_BILINEAR", "S0", rank) for rank in protocol["training"]["ranks"]]
    all_keys = m0_keys + m1_s0_keys
    train_families = sorted({row["base_family_id"] for row in data.train})

    bootstrap = bootstrap_summaries(
        frozen, data, protocol,
        seeds=list(protocol["training"]["primary_family_bootstrap_seeds"]),
        keys=all_keys, selected=selections, train_families=train_families,
    )

    # ---- S1/S2 classification (frozen N6 rules) ---------------------------
    def direction_values(baseline_key: str, candidate_key: str, seed_keys: list[int]) -> list[float]:
        return [
            improvement(
                bootstrap[(int(seed), baseline_key)]["j_common_macro"],
                bootstrap[(int(seed), candidate_key)]["j_common_macro"],
            )
            for seed in seed_keys
        ]

    s0_key, s1_key, s2_key = m0_keys
    comparisons = {
        "s1_vs_s0": compare_rows(detailed[s0_key], detailed[s1_key], protocol),
        "s2_vs_s1": compare_rows(detailed[s1_key], detailed[s2_key], protocol),
    }
    primary_seeds = list(protocol["training"]["primary_family_bootstrap_seeds"])
    comparisons["s1_vs_s0"]["seed_improvement_percent"] = direction_values(s0_key, s1_key, primary_seeds)
    comparisons["s2_vs_s1"]["seed_improvement_percent"] = direction_values(s1_key, s2_key, primary_seeds)
    comparisons["s1_vs_s0"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s1_vs_s0"]["seed_improvement_percent"])
    comparisons["s2_vs_s1"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s2_vs_s1"]["seed_improvement_percent"])

    s1 = comparisons["s1_vs_s0"]
    switch_value = s1["window_improvement_percent"].get("switch", float("-inf"))
    important_count = sum(
        s1["scenario_improvement_percent"].get(name, float("-inf")) >= 5.0
        for name in protocol["training"]["important_scenarios"]
    )
    if s1["macro_improvement_percent"] >= 5.0 and switch_value >= 8.0 and s1["max_important_degradation_percent"] <= 3.0 and s1["paired_ci"]["ci95_low_percent"] > 0.0:
        s1_class = "GLOBAL_EFFECTIVE"
    elif s1["macro_improvement_percent"] >= 0.0 and switch_value >= 5.0 and important_count >= 2 and s1["max_important_degradation_percent"] <= 5.0 and comparisons["s1_vs_s0"]["seed_positive_count"] >= 4:
        s1_class = "LOCAL_EFFECTIVE"
    elif s1["max_important_degradation_percent"] <= 5.0 and (0.0 <= s1["macro_improvement_percent"] < 5.0 or s1["paired_ci"]["ci95_low_percent"] <= 0.0 or comparisons["s1_vs_s0"]["seed_positive_count"] < 4):
        s1_class = "GRAY"
    else:
        s1_class = "INEFFECTIVE_OR_DEGRADED"

    s2 = comparisons["s2_vs_s1"]
    s1_full = float(summaries[s1_key]["j_full_macro"])
    s2_full = float(summaries[s2_key]["j_full_macro"])
    full_improvement = improvement(s1_full, s2_full)
    comparisons["s2_vs_s1"]["j_full_improvement_percent"] = full_improvement
    if (s2["macro_improvement_percent"] >= 3.0 or s2["divergence_rate_change"] < 0.0) and s2["max_important_degradation_percent"] <= 3.0:
        s2_class = "COMMON_DYNAMICS_EFFECTIVE"
    elif full_improvement > 0.0 and s2["macro_improvement_percent"] < 3.0:
        s2_class = "ACTUATOR_ONLY_EFFECTIVE"
    elif 0.0 <= s2["macro_improvement_percent"] < 3.0 and s2["max_important_degradation_percent"] <= 3.0:
        s2_class = "GRAY"
    else:
        s2_class = "DEGRADED"

    backup_seeds_used: list[int] = []
    if s1_class == "GRAY" or s2_class == "GRAY":
        for seed in protocol["training"]["backup_family_bootstrap_seeds"]:
            backup_seeds_used.append(int(seed))
            counts = _family_counts(train_families, seed)
            statistics = {
                (variant, "M0_FIXED_LINEAR"): accumulate_fit_statistics(
                    data.train, variant, "M0_FIXED_LINEAR", data.normalization, counts
                )
                for variant in ("S0", "S1", "S2")
            }
            for key in (s0_key, s1_key, s2_key):
                selected_config = selections[key]
                model = solve_model(
                    statistics[(selected_config["variant"], selected_config["model_kind"])],
                    variant=selected_config["variant"],
                    model_kind=selected_config["model_kind"],
                    ridge=selected_config["ridge"],
                    rank=None,
                )
                rows = evaluate_model(
                    model, data.development, data.normalization, protocol,
                    frozen.resolved_params, R3Decoder(frozen.build_planar_grasp_matrix),
                    seed_label=str(seed),
                )
                bootstrap[(int(seed), key)] = {
                    "config_key": key,
                    "seed_label": str(seed),
                    **macro_summary(rows),
                    "j_full_macro": field_macro(rows, "j_full"),
                    "e_actuator_macro": field_macro(rows, "e_actuator"),
                    "condition_number": model["condition_number"],
                    "parameter_count": model["parameter_count"],
                }
        all_seeds = [*primary_seeds, *backup_seeds_used]
        comparisons["s1_vs_s0"]["seed_improvement_percent"] = direction_values(s0_key, s1_key, all_seeds)
        comparisons["s2_vs_s1"]["seed_improvement_percent"] = direction_values(s1_key, s2_key, all_seeds)
        comparisons["s1_vs_s0"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s1_vs_s0"]["seed_improvement_percent"])
        comparisons["s2_vs_s1"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s2_vs_s1"]["seed_improvement_percent"])
        if s1_class == "GRAY":
            s1_class = "LOCAL_EFFECTIVE" if comparisons["s1_vs_s0"]["seed_positive_count"] >= 6 and s1["macro_improvement_percent"] >= 0.0 else "INEFFECTIVE_OR_DEGRADED"
        if s2_class == "GRAY":
            s2_class = "COMMON_DYNAMICS_EFFECTIVE" if comparisons["s2_vs_s1"]["seed_positive_count"] >= 6 and s2["macro_improvement_percent"] >= 3.0 else "ACTUATOR_ONLY_EFFECTIVE" if full_improvement > 0.0 else "DEGRADED"

    comparisons["s1_vs_s0"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s1_vs_s0"]["seed_improvement_percent"])
    comparisons["s2_vs_s1"]["seed_positive_count"] = sum(value > 0.0 for value in comparisons["s2_vs_s1"]["seed_improvement_percent"])

    selected_interface = "S0" if s1_class not in {"GLOBAL_EFFECTIVE", "LOCAL_EFFECTIVE"} else "S2" if s2_class == "COMMON_DYNAMICS_EFFECTIVE" else "S1"
    fixed_key = config_key("M0_FIXED_LINEAR", selected_interface, None)
    bilinear = []
    for rank in protocol["training"]["ranks"]:
        key = config_key("M1_LOWRANK_BILINEAR", selected_interface, rank)
        comparison = compare_rows(detailed[fixed_key], detailed[key], protocol)
        seed_values = [
            improvement(
                bootstrap[(int(seed), fixed_key)]["j_common_macro"],
                bootstrap[(int(seed), key)]["j_common_macro"],
            )
            for seed in primary_seeds
        ]
        strong_best = max(
            comparison["scenario_improvement_percent"].get(name, float("-inf"))
            for name in protocol["training"]["strong_coupling_scenarios"]
        )
        bilinear.append(
            {
                "rank": rank,
                "config_key": key,
                **comparison,
                "seed_improvement_percent": seed_values,
                "seed_positive_count": sum(value > 0.0 for value in seed_values),
                "strong_coupling_best_percent": strong_best,
                "effective": strong_best >= 8.0 and comparison["macro_improvement_percent"] >= -3.0 and sum(value > 0.0 for value in seed_values) >= 4,
            }
        )

    return {
        "detailed": detailed,
        "summaries": summaries,
        "comparisons": comparisons,
        "bilinear": bilinear,
        "classification": {
            "s1_class": s1_class,
            "s2_class": s2_class,
            "selected_interface": selected_interface,
            "backup_seeds_used": backup_seeds_used,
        },
    }


class _ItemScanner:
    def __init__(self) -> None:
        self.max_relative_error = 0.0
        self.worst: tuple | None = None

    def compare(self, name: str, recomputed_value: float, recorded_value: float) -> None:
        denominator = max(abs(recorded_value), 1.0e-12)
        relative_error = abs(float(recomputed_value) - float(recorded_value)) / denominator
        if relative_error > self.max_relative_error:
            self.max_relative_error = relative_error
            self.worst = (name, float(recomputed_value), float(recorded_value))


def regress_against_n6(
    frozen,
    recomputed: dict,
    protocol: dict,
) -> dict:
    """P0 element-wise regression of the v2 recomputation against frozen N6 records."""
    gates: dict[str, bool] = {}
    report: dict = {}

    detailed = recomputed["detailed"]
    summaries = recomputed["summaries"]
    comparisons = recomputed["comparisons"]
    bilinear = recomputed["bilinear"]

    # 1. S0 FULL_TRAIN J20_common (development macro)
    s0_key = config_key("M0_FIXED_LINEAR", "S0", None)
    recomputed_value = float(summaries[s0_key]["j_common_macro"])
    reference = float(protocol["p0_gates"]["s0_j20_common_reference"])
    abs_error = abs(recomputed_value - reference)
    gates["s0_j20_common"] = abs_error <= float(protocol["p0_gates"]["s0_j20_common_abs_tolerance"])
    report["s0_j20_common"] = {"recomputed": recomputed_value, "reference": reference, "abs_error": abs_error}

    # 2. main table per-item relative error vs frozen N6 json records
    n6_stage = frozen.n6_stage_dir()
    n6_comparisons = read_json(n6_stage / "interface_comparisons.json")
    n6_bilinear = read_json(n6_stage / "bilinear_comparison.json")
    scanner = _ItemScanner()

    # 2a. central summaries (model_seed_summary.csv FULL_TRAIN rows)
    summary_rows = list(
        csv.DictReader(open(n6_stage / "model_seed_summary.csv", encoding="utf-8-sig"))
    )
    central_records = {
        row["config_key"]: row for row in summary_rows if row["seed_label"] == "FULL_TRAIN"
    }
    for key, row in central_records.items():
        if key not in summaries:
            continue
        for field in (
            "j_common_macro",
            "divergence_rate",
            "condition_number",
            "parameter_count",
            "j_full_macro",
            "e_actuator_macro",
        ):
            if field in summaries[key] and summaries[key][field] is not None:
                scanner.compare(f"{key}.{field}", float(summaries[key][field]), float(row[field]))

    for name in ("s1_vs_s0", "s2_vs_s1"):
        record = n6_comparisons[name]
        current = comparisons[name]
        for field in (
            "macro_improvement_percent",
            "max_important_degradation_percent",
            "divergence_rate_change",
        ):
            scanner.compare(f"{name}.{field}", current[field], float(record[field]))
        for scenario in protocol["scenarios"]["order"]:
            scanner.compare(
                f"{name}.scenario.{scenario}",
                current["scenario_improvement_percent"][scenario],
                float(record["scenario_improvement_percent"][scenario]),
            )
        for window in protocol["window"]["classes"]:
            if window in record["window_improvement_percent"]:
                scanner.compare(
                    f"{name}.window.{window}",
                    current["window_improvement_percent"][window],
                    float(record["window_improvement_percent"][window]),
                )
        ci = record["paired_ci"]
        for field in ("mean_improvement_percent", "median_improvement_percent", "ci95_low_percent", "ci95_high_percent"):
            scanner.compare(f"{name}.paired_ci.{field}", current["paired_ci"][field], float(ci[field]))
        for index, value in enumerate(record["seed_improvement_percent"]):
            scanner.compare(f"{name}.seed[{index}]", current["seed_improvement_percent"][index], float(value))
        scanner.compare(f"{name}.seed_positive_count", current["seed_positive_count"], float(record["seed_positive_count"]))
        if name == "s2_vs_s1":
            scanner.compare(f"{name}.j_full_improvement_percent", current["j_full_improvement_percent"], float(record["j_full_improvement_percent"]))

    fixed_key = config_key("M0_FIXED_LINEAR", "S0", None)
    for record in n6_bilinear:
        key = record["config_key"]
        current = next(item for item in bilinear if item["config_key"] == key)
        for field in (
            "macro_improvement_percent",
            "max_important_degradation_percent",
            "divergence_rate_change",
            "strong_coupling_best_percent",
        ):
            scanner.compare(f"{key}.{field}", current[field], float(record[field]))
        for scenario in protocol["scenarios"]["order"]:
            scanner.compare(
                f"{key}.scenario.{scenario}",
                current["scenario_improvement_percent"][scenario],
                float(record["scenario_improvement_percent"][scenario]),
            )
        for window in protocol["window"]["classes"]:
            if window in record["window_improvement_percent"]:
                scanner.compare(
                    f"{key}.window.{window}",
                    current["window_improvement_percent"][window],
                    float(record["window_improvement_percent"][window]),
                )
        ci = record["paired_ci"]
        for field in ("mean_improvement_percent", "median_improvement_percent", "ci95_low_percent", "ci95_high_percent"):
            scanner.compare(f"{key}.paired_ci.{field}", current["paired_ci"][field], float(ci[field]))
        for index, value in enumerate(record["seed_improvement_percent"]):
            scanner.compare(f"{key}.seed[{index}]", current["seed_improvement_percent"][index], float(value))
        scanner.compare(f"{key}.seed_positive_count", current["seed_positive_count"], float(record["seed_positive_count"]))

    tolerance = float(protocol["p0_gates"]["main_metric_relative_tolerance"])
    gates["main_table_relative_error"] = scanner.max_relative_error <= tolerance
    report["main_table"] = {
        "max_relative_error": scanner.max_relative_error,
        "tolerance": tolerance,
        "worst_item": scanner.worst,
        "excluded_timing_fields": [
            "inference_ratio",
            "inference_mean_s_per_window",
            "inference_s",
        ],
        "note": "timing fields are machine-state dependent and cannot be reproduced to 1e-9; "
        "they are excluded from the scientific-metric regression and reported in the fairness ledger only",
    }

    # 3. classification/selection outcomes match N6
    record_selection = read_json(n6_stage / "selection.json")
    classification = recomputed["classification"]
    gates["classification_match"] = (
        classification["s1_class"] == record_selection["s1_classification"]
        and classification["s2_class"] == record_selection["s2_classification"]
        and classification["selected_interface"] == record_selection["selected_interface"]
        and classification["backup_seeds_used"] == list(record_selection["backup_seeds_used"])
    )
    report["classification"] = {"recomputed": classification, "recorded": record_selection}

    # 4. development window identity (3820 windows, per config)
    n6_detailed = _read_n6_detailed(frozen.n6_development_detailed_path())
    n6_by_config: dict[str, list[dict]] = defaultdict(list)
    for row in n6_detailed:
        n6_by_config[row["config_key"]].append(row)
    identity_checks = {}
    for key in sorted(detailed):
        expected = _row_identity(n6_by_config.get(key, []))
        actual = _row_identity(detailed[key])
        identity_checks[key] = {
            "equal": actual == expected,
            "expected_count": len(expected),
            "actual_count": len(actual),
        }
    all_equal = all(item["equal"] for item in identity_checks.values())
    dev_windows = len(
        {(int(row["trajectory_id"]), int(row["window_start"])) for row in detailed[s0_key]}
    )
    gates["development_window_identity"] = all_equal and dev_windows == int(protocol["p0_gates"]["development_window_count"])
    report["development_windows"] = {
        "count": dev_windows,
        "expected": int(protocol["p0_gates"]["development_window_count"]),
        "per_config": identity_checks,
        "note": "count = unique (trajectory_id, window_start) pairs; the per-config identity check also includes the horizon dimension",
    }

    # 5. confirm reads == 0
    confirm_reads = sum(1 for row in n6_detailed if row["split"] == "confirm") + sum(
        1 for rows in detailed.values() for row in rows if row["split"] == "confirm"
    )
    gates["confirm_not_read"] = confirm_reads == 0
    report["confirm_read_count"] = confirm_reads

    report["gates"] = gates
    report["passed"] = all(gates.values())
    return report


def write_products(stage_root: Path, detailed: dict[str, list[dict]], summaries: dict[str, dict], report: dict) -> None:
    stage_root.mkdir(parents=True, exist_ok=True)
    combined = []
    for key, rows in sorted(detailed.items()):
        combined.extend({"config_key": key, **row} for row in rows)
    write_csv(stage_root / "development_detailed_v2.csv", combined)
    write_csv(stage_root / "model_summary_v2.csv", list(summaries.values()))
    from contracts_v2 import atomic_json
    atomic_json(stage_root / "n6_regression_report.json", report)

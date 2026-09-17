from __future__ import annotations

import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from actuator_rollout import rollout_actuator_step
from steering_actuator import SteeringActuatorConfig


def load_cache(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def fit_normalization(entries: list[dict]) -> dict[str, np.ndarray]:
    """Fit every normalization statistic from train cache rows only."""

    if not entries or {entry["split"] for entry in entries} != {"train"}:
        raise ValueError("normalization entries must be non-empty and train-only")
    keys = {
        "relative_state47": [],
        "actual_steering4": [],
        "control7": [],
        "force_payload_body8": [],
        "internal_force8": [],
    }
    for entry in entries:
        cache = load_cache(Path(entry["cache_path"]))
        for key in keys:
            keys[key].append(np.asarray(cache[key], dtype=float))
    output = {"source_split": np.asarray("train")}
    for key, parts in keys.items():
        values = np.concatenate(parts, axis=0)
        output[f"{key}_mean"] = np.mean(values, axis=0)
        output[f"{key}_scale"] = np.maximum(np.std(values, axis=0), 1.0e-9)
        output[f"{key}_row_count"] = np.asarray(values.shape[0])
    output["source_base_family_count"] = np.asarray(
        len({entry["base_family_id"] for entry in entries})
    )
    return output


def _normalized_state_target(
    cache: dict[str, np.ndarray], variant: str, normalization: dict[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    relative = np.asarray(cache["relative_state47"], dtype=float)
    actual = np.asarray(cache["actual_steering4"], dtype=float)
    control = np.asarray(cache["control7"], dtype=float)
    rel_mean = normalization["relative_state47_mean"]
    rel_scale = normalization["relative_state47_scale"]
    act_mean = normalization["actual_steering4_mean"]
    act_scale = normalization["actual_steering4_scale"]
    u_mean = normalization["control7_mean"]
    u_scale = normalization["control7_scale"]
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
            (np.asarray(cache["analytic_actual_next4"], dtype=float) - act_mean)
            / act_scale,
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
    state, control, side, target = _normalized_state_target(
        cache, variant, normalization
    )
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
    relative = np.asarray(cache["relative_state47"][start], dtype=float).copy()
    actual = np.asarray(cache["actual_steering4"][start], dtype=float).copy()
    actuator = SteeringActuatorConfig(
        tau_delta_s=float(protocol["actuator"]["tau_delta_s"]),
        rate_max_radps=float(protocol["actuator"]["rate_max_radps"]),
        angle_max_rad=float(np.deg2rad(protocol["actuator"]["angle_max_deg"])),
    )
    elapsed = 0.0
    for offset in range(horizon):
        control = np.asarray(cache["control7"][start + offset], dtype=float)
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
                analytic = rollout_actuator_step(
                    actual,
                    control[-4:],
                    model_step_s=float(protocol["actuator"]["model_step_s"]),
                    plant_step_s=float(protocol["actuator"]["plant_step_s"]),
                    config=actuator,
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


def connector_outputs(
    relative_state47: np.ndarray, params: object, law: str
) -> tuple[np.ndarray, np.ndarray]:
    relative = np.asarray(relative_state47, dtype=float)
    values = relative.reshape(1, -1) if relative.ndim == 1 else relative
    g3 = values[:, 31:47].reshape(-1, 4, 4)
    displacement = g3[:, :, :2]
    velocity = g3[:, :, 2:]
    distance = np.linalg.norm(displacement, axis=2)
    normal = displacement / np.maximum(distance[:, :, None], 1.0e-12)
    penetration = np.maximum(distance - float(params.connector.free_play_m), 0.0)
    normal_speed = np.sum(velocity * normal, axis=2)
    if str(law).upper() == "V1":
        weight = (penetration > 0.0).astype(float)
    elif str(law).upper() == "R3":
        ratio = np.clip(
            penetration / float(params.connector.smoothing_width_m), 0.0, 1.0
        )
        weight = np.where(
            penetration <= 0.0,
            0.0,
            np.where(penetration >= float(params.connector.smoothing_width_m), 1.0, 3 * ratio**2 - 2 * ratio**3),
        )
    else:
        raise ValueError(law)
    magnitude = (
        float(params.connector.stiffness_npm) * penetration
        + float(params.connector.damping_nspm)
        * weight
        * np.maximum(normal_speed, 0.0)
    )
    force = magnitude[:, :, None] * normal
    from internal_force import build_planar_grasp_matrix

    grasp = build_planar_grasp_matrix(np.asarray(params.payload_anchor_body_m, dtype=float))
    projector = np.eye(8) - np.linalg.pinv(grasp) @ grasp
    force8 = force.reshape(-1, 8)
    internal8 = force8 @ projector.T
    if relative.ndim == 1:
        return force8[0], internal8[0]
    return force8, internal8


def evaluate_model(
    model: dict,
    entries: list[dict],
    normalization: dict[str, np.ndarray],
    protocol: dict,
    params_resolver,
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
                normalized_error = (
                    prediction - target
                ) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = connector_outputs(
                    prediction, params, entry["law"]
                )
                true_force = np.asarray(
                    cache["force_payload_body8"][start + horizon], dtype=float
                )
                true_internal = np.asarray(
                    cache["internal_force8"][start + horizon], dtype=float
                )
                force_error = (predicted_force - true_force) / normalization[
                    "force_payload_body8_scale"
                ]
                internal_error = (predicted_internal - true_internal) / normalization[
                    "internal_force8_scale"
                ]
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
                    actuator_target = np.asarray(
                        cache["actual_steering4"][start + horizon], dtype=float
                    )
                    actuator_normalized = (
                        actuator_prediction - actuator_target
                    ) / normalization["actual_steering4_scale"]
                    e_actuator = float(np.sqrt(np.mean(actuator_normalized**2)))
                    actuator_rmse = float(
                        np.sqrt(np.mean((actuator_prediction - actuator_target) ** 2))
                    )
                    j_full = float(weights["common_weight_sum"]) * j_common + float(
                        weights["actuator"]
                    ) * e_actuator
                finite = bool(
                    np.all(np.isfinite(prediction))
                    and np.all(np.isfinite(predicted_force))
                    and np.isfinite(j_common)
                )
                divergent = bool(
                    not finite
                    or np.max(np.abs(normalized_error))
                    > float(protocol["training"]["divergence_abs_normalized"])
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
        "inference_mean_s_per_window": float(np.mean([row["inference_s"] for row in selected])),
        "row_count": len(selected),
    }


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
    improvement = np.asarray(
        [100.0 * (baseline[key] - candidate[key]) / max(abs(baseline[key]), 1.0e-12) for key in families]
    )
    rng = np.random.default_rng(int(seed))
    draws = np.empty(int(replicates), dtype=float)
    for index in range(int(replicates)):
        draws[index] = float(np.mean(rng.choice(improvement, size=len(improvement), replace=True)))
    return {
        "family_count": len(families),
        "mean_improvement_percent": float(np.mean(improvement)),
        "median_improvement_percent": float(np.median(improvement)),
        "ci95_low_percent": float(np.percentile(draws, 2.5)),
        "ci95_high_percent": float(np.percentile(draws, 97.5)),
        "replicates": int(replicates),
        "seed": int(seed),
    }

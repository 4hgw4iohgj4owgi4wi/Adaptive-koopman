from __future__ import annotations

"""P3: one-time bilinear mechanism diagnosis (frozen ridge candidates only).

B0  reproduce the current post-hoc-SVD rank-1 bilinear (N6 M1|S0|1).
B1  full bilinear ridge regression, NO post-hoc SVD truncation.
B2  jointly trained low-rank bilinear, rank 1 (alternating least squares).
B3  jointly trained low-rank bilinear, rank 2 (alternating least squares).

If B1's one-step error is clearly worse than S0 (+3% threshold), B2/B3 stop
with a recorded reason: the failure is not caused by SVD truncation alone.
No rank growth, no depth growth, no extra candidates beyond the pre-registered
diagnostic matrix.
"""

from collections import Counter, defaultdict

import numpy as np

from contracts_v2 import read_json, write_csv
from data_contract import load_cache
from evaluation_v2 import (
    accumulate_fit_statistics,
    config_key,
    design_matrix,
    evaluate_model,
    improvement,
    load_frozen_model,
    macro_summary,
    rollout_model,
    solve_model,
)
from physics_decoder import R3Decoder


ONE_STEP_FAILURE_THRESHOLD_PERCENT = 3.0
ALS_ITERATIONS = 50
ALS_RIDGE = 1e-4
BOX_RANDOM_POINTS = 1000


def fit_full_bilinear(
    frozen,
    data,
    protocol: dict,
    ridge: float,
    family_counts: Counter | None = None,
) -> dict:
    """B1: ridge regression with the complete bilinear block, no SVD truncation."""
    statistics = accumulate_fit_statistics(
        data.train, "S0", "M1_LOWRANK_BILINEAR", data.normalization, family_counts
    )
    gram = np.asarray(statistics["gram"], dtype=float)
    cross = np.asarray(statistics["cross"], dtype=float)
    regularizer = np.eye(gram.shape[0]) * float(ridge)
    regularizer[-1, -1] = 0.0
    coefficients = np.linalg.solve(gram + regularizer, cross)
    layout = dict(statistics["layout"])
    start = int(layout["bilinear_start"])
    state_dim = int(layout["state_dimension"])
    control_dim = int(layout["control_dimension"])
    output_dim = int(layout["output_dimension"])
    singular = np.linalg.svd(gram + regularizer, compute_uv=False)
    condition = float(singular[0] / max(singular[-1], 1.0e-300))
    return {
        "variant": "S0",
        "model_kind": "M1_LOWRANK_BILINEAR",
        "ridge": float(ridge),
        "rank": None,
        "coefficients": coefficients,
        "layout": layout,
        "condition_number": condition,
        "parameter_count": int(coefficients.size),
        "fit_row_count": int(statistics["row_count"]),
        "bilinear_tensor": coefficients[start : start + state_dim * control_dim].reshape(
            control_dim, state_dim, output_dim
        ),
    }


def _als_rank_r(
    frozen,
    data,
    protocol: dict,
    ridge: float,
    rank: int,
    family_counts: Counter | None = None,
    iterations: int = ALS_ITERATIONS,
) -> dict:
    """Joint low-rank bilinear via alternating least squares.

    Model: y = A x + B u + c + sum_j U_j (V_j^T x), with U_j, V_j in
    R^{state_dim x rank}.  Initialized from the SVD of the B1 full-bilinear
    tensor (deterministic), then ALS alternates:
      U-step: joint ridge solve of [A, B, c, U] given V;
      V-step: per-j closed-form normal equations given U and the residual.
    """
    from evaluation_v2 import _normalized_state_target

    state_rows = []
    control_rows = []
    target_rows = []
    weights = []
    for entry in data.train:
        weight = 1 if family_counts is None else int(family_counts[entry["base_family_id"]])
        if weight <= 0:
            continue
        cache = load_cache(entry["cache_path"])
        state, control, _, target = _normalized_state_target(cache, "S0", data.normalization)
        state_rows.append(state)
        control_rows.append(control)
        target_rows.append(target)
        weights.append(np.full(state.shape[0], weight))
    state = np.concatenate(state_rows, axis=0)
    control = np.concatenate(control_rows, axis=0)
    target = np.concatenate(target_rows, axis=0)
    weight_vector = np.concatenate(weights, axis=0)
    state_dim = state.shape[1]
    control_dim = control.shape[1]
    output_dim = target.shape[1]

    # deterministic SVD initialization from the full-bilinear solution
    full = fit_full_bilinear(frozen, data, protocol, ALS_RIDGE, family_counts)
    tensor = full["bilinear_tensor"]
    v_blocks = []
    u_blocks = []
    for index in range(control_dim):
        u_j, singular_j, vt_j = np.linalg.svd(tensor[index], full_matrices=False)
        keep = min(int(rank), vt_j.shape[0])
        v_blocks.append(vt_j[:keep].T)
        u_blocks.append((u_j[:, :keep] * singular_j[:keep]).copy())
    v_blocks = [np.asarray(block, dtype=float) for block in v_blocks]
    u_blocks = [np.asarray(block, dtype=float) for block in u_blocks]
    # warm-start the linear part from the full-bilinear solution
    linear_coefficients = np.zeros((47 + 7 + 1 + control_dim * int(rank), output_dim), dtype=float)
    linear_coefficients[:47, :47] = full["coefficients"][:47, :47]
    linear_coefficients[47:54, :] = full["coefficients"][47:54, :]
    linear_coefficients[54, :] = full["coefficients"][54, :]

    weighted_state = state * weight_vector[:, None]
    # per-control modulated state gram: (u_j .* X)^T W (u_j .* X), used by the V-step
    modulated_state = [
        control[:, index][:, None] * state for index in range(control_dim)
    ]
    gram_j = [
        (modulated_state[index] * weight_vector[:, None]).T @ modulated_state[index]
        for index in range(control_dim)
    ]
    objective = float("inf")
    for iteration in range(int(iterations)):
        # U-step: joint ridge solve over [A, B, c, U] with features
        # [x, u, 1, u_1 .* (V_1^T x), ..., u_7 .* (V_7^T x)]
        features = [state, control, np.ones((state.shape[0], 1))]
        for index in range(control_dim):
            features.append(control[:, index][:, None] * (state @ v_blocks[index]))
        design = np.concatenate(features, axis=1)
        weighted_design = design * weight_vector[:, None]
        gram = weighted_design.T @ design
        cross = weighted_design.T @ target
        regularizer = np.eye(gram.shape[0]) * float(ridge)
        regularizer[47 + 7, 47 + 7] = 0.0  # bias column is unregularized
        linear_coefficients = np.linalg.solve(gram + regularizer, cross)
        u_blocks = [
            linear_coefficients[47 + 7 + 1 + index * rank : 47 + 7 + 1 + (index + 1) * rank].T
            for index in range(control_dim)
        ]
        u_blocks = [np.asarray(block, dtype=float) for block in u_blocks]

        # V-step: for each j, solve V_j from the residual that excludes j's
        # own bilinear term (block coordinate descent):
        #   R_j = target - (A x + B u + c) - sum_{l != j} u_l .* (U_l (X V_l))
        #   sum_l (U_k . U_l) (u_j .* X)^T W (u_j .* X) V_l = (u_j .* X)^T W (R_j U_k)
        base_prediction = np.concatenate([state, control, np.ones((state.shape[0], 1))], axis=1) @ linear_coefficients[: 47 + 7 + 1]
        for index in range(control_dim):
            u_block = u_blocks[index]
            others = np.zeros_like(target)
            for other in range(control_dim):
                if other == index:
                    continue
                others = others + control[:, other][:, None] * ((state @ v_blocks[other]) @ u_blocks[other].T)
            residual_j = target - base_prediction - others
            gram_v = np.zeros((rank * state_dim, rank * state_dim), dtype=float)
            cross_v = np.zeros(rank * state_dim, dtype=float)
            for k in range(int(rank)):
                for ell in range(int(rank)):
                    gram_v[
                        k * state_dim : (k + 1) * state_dim,
                        ell * state_dim : (ell + 1) * state_dim,
                    ] = float(np.dot(u_block[:, k], u_block[:, ell])) * gram_j[index]
            for k in range(int(rank)):
                cross_v[k * state_dim : (k + 1) * state_dim] = (
                    (modulated_state[index] * weight_vector[:, None]).T @ (residual_j @ u_block[:, k])
                )
            gram_v += np.eye(rank * state_dim) * float(ridge)
            solution = np.linalg.solve(gram_v, cross_v)
            v_blocks[index] = solution.reshape(state_dim, int(rank))

        # objective on weighted squared error of the joint model
        rebuilt = _rebuilt_coefficients(
            linear_coefficients, u_blocks, v_blocks, state_dim, control_dim, output_dim
        )
        prediction_new = _predict_rebuilt(rebuilt, state, control)
        objective = float(np.sum(weight_vector[:, None] * (target - prediction_new) ** 2))
        if not np.all(np.isfinite(prediction_new)) or not np.isfinite(objective):
            raise FloatingPointError("ALS produced non-finite values; mechanism diagnosis cannot continue")

    linear_part = linear_coefficients[: 47 + 7 + 1]
    u_blocks = [
        np.asarray(block, dtype=float) for block in u_blocks
    ]
    model = _rebuilt_model(
        frozen, data, protocol, ridge, rank, linear_part, u_blocks, v_blocks,
        state_dim, control_dim, output_dim,
    )
    model["als_objective"] = objective
    model["als_iterations"] = int(iterations)
    return model


def _rebuilt_coefficients(
    linear_coefficients: np.ndarray,
    u_blocks: list[np.ndarray],
    v_blocks: list[np.ndarray],
    state_dim: int,
    control_dim: int,
    output_dim: int,
) -> np.ndarray:
    coefficients = np.zeros((47 + 7 + 1 + state_dim * control_dim, output_dim), dtype=float)
    coefficients[: 47 + 7 + 1] = linear_coefficients[: 47 + 7 + 1]
    start = 47 + 7
    for index in range(control_dim):
        # design block for control j is N_j^T (state x output): the row at
        # j*state+i multiplies u_j * x_i and maps to outputs.
        n_j = u_blocks[index] @ v_blocks[index].T
        coefficients[start + index * state_dim : start + (index + 1) * state_dim] = n_j.T
    return coefficients


def _predict_rebuilt(coefficients: np.ndarray, state: np.ndarray, control: np.ndarray) -> np.ndarray:
    design = np.concatenate(
        [state, control, np.ones((state.shape[0], 1))], axis=1
    )
    bilinear = np.zeros((state.shape[0], 47), dtype=float)
    start = 47 + 7
    for index in range(7):
        n_j = coefficients[start + index * 47 : start + (index + 1) * 47]
        bilinear += control[:, index][:, None] * (state @ n_j)
    return design @ coefficients[: 47 + 7 + 1] + bilinear


def _rebuilt_model(
    frozen,
    data,
    protocol: dict,
    ridge: float,
    rank: int,
    linear_part: np.ndarray,
    u_blocks: list[np.ndarray],
    v_blocks: list[np.ndarray],
    state_dim: int,
    control_dim: int,
    output_dim: int,
) -> dict:
    statistics = accumulate_fit_statistics(
        data.train, "S0", "M1_LOWRANK_BILINEAR", data.normalization
    )
    layout = dict(statistics["layout"])
    coefficients = _rebuilt_coefficients(
        linear_part, u_blocks, v_blocks, state_dim, control_dim, output_dim
    )
    return {
        "variant": "S0",
        "model_kind": "M1_LOWRANK_BILINEAR",
        "ridge": float(ridge),
        "rank": int(rank),
        "coefficients": coefficients,
        "layout": layout,
        "condition_number": None,
        "parameter_count": int(
            47 * 47 + 7 * 47 + 47 + control_dim * int(rank) * (state_dim + output_dim)
        ),
        "fit_row_count": int(statistics["row_count"]),
    }


def reproduce_rank1_b0(
    frozen,
    data,
    protocol: dict,
) -> dict:
    """B0: reproduce the frozen N6 post-hoc-SVD rank-1 bilinear model."""
    n6_stage = frozen.n6_stage_dir()
    selections = read_json(n6_stage / "frozen_hyperparameter_selection.json")
    key = config_key("M1_LOWRANK_BILINEAR", "S0", 1)
    selected = selections[key]
    statistics = accumulate_fit_statistics(
        data.train, selected["variant"], selected["model_kind"], data.normalization
    )
    refitted = solve_model(
        statistics,
        variant=selected["variant"],
        model_kind=selected["model_kind"],
        ridge=selected["ridge"],
        rank=selected["rank"],
    )
    frozen_model = load_frozen_model(
        frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz")
    )
    coefficient_error = float(
        np.max(np.abs(refitted["coefficients"] - frozen_model["coefficients"]))
    )
    scale = float(np.max(np.abs(frozen_model["coefficients"])))
    return {
        "passed": coefficient_error / max(scale, 1.0e-300) <= 1e-9,
        "coefficient_relative_error": coefficient_error / max(scale, 1.0e-300),
        "coefficient_max_abs_error": coefficient_error,
        "ridge": float(selected["ridge"]),
        "model": refitted,
        "frozen_model": frozen_model,
    }


def _evaluate_candidate(frozen, data, protocol, model, entries) -> list[dict]:
    return evaluate_model(
        model, entries, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label="P3_CANDIDATE",
    )


def mechanism_checks(
    frozen,
    data,
    protocol: dict,
    candidate: dict,
    s0_model: dict,
    *,
    seed: int = 990800,
) -> dict:
    """N=0 ablation, control time permutation, error growth, A(u) box spectrum."""
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    layout = candidate["layout"]
    start = int(layout["bilinear_start"])
    state_dim = int(layout["state_dimension"])
    control_dim = int(layout["control_dimension"])

    candidate_rows = _evaluate_candidate(frozen, data, protocol, candidate, data.validation)
    candidate_macro = macro_summary(candidate_rows)
    s0_rows = _evaluate_candidate(frozen, data, protocol, s0_model, data.validation)
    s0_macro = macro_summary(s0_rows)

    zeroed = dict(candidate)
    zeroed_coefficients = np.array(candidate["coefficients"], dtype=float, copy=True)
    zeroed_coefficients[start : start + state_dim * control_dim] = 0.0
    zeroed["coefficients"] = zeroed_coefficients
    zeroed_rows = _evaluate_candidate(frozen, data, protocol, zeroed, data.validation)
    zeroed_macro = macro_summary(zeroed_rows)

    # control time permutation within each trajectory
    rng = np.random.default_rng(int(seed))
    permuted_caches: dict[int, dict[str, np.ndarray]] = {}
    for entry in data.validation:
        cache = load_cache(entry["cache_path"])
        modified = dict(cache)
        control = np.asarray(cache["control7"], dtype=float).copy()
        order = rng.permutation(control.shape[0])
        modified["control7"] = control[order]
        permuted_caches[int(entry["trajectory_id"])] = modified
    permuted_rows = []
    for entry in data.validation:
        cache = permuted_caches[int(entry["trajectory_id"])]
        params = frozen.resolved_params(int(entry["seed"]), protocol)
        for window_start, category in zip(cache["window_start"], cache["window_class"], strict=True):
            window_start = int(window_start)
            for horizon in (1, 5, 10, 20):
                prediction, _, _ = rollout_model(
                    candidate, cache, window_start, int(horizon), normalization, protocol
                )
                target = np.asarray(cache["relative_state47"][window_start + int(horizon)], dtype=float)
                normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                true_force = np.asarray(cache["force_payload_body8"][window_start + int(horizon)], dtype=float)
                true_internal = np.asarray(cache["internal_force8"][window_start + int(horizon)], dtype=float)
                force_error = (predicted_force - true_force) / normalization["force_payload_body8_scale"]
                internal_error = (predicted_internal - true_internal) / normalization["internal_force8_scale"]
                weights = protocol["metric_weights"]
                j_common = (
                    weights["core"] * float(np.sqrt(np.mean(normalized_error[:3] ** 2)))
                    + weights["relative"] * float(np.sqrt(np.mean(normalized_error[3:] ** 2)))
                    + weights["force4"] * float(np.sqrt(np.mean(force_error**2)))
                    + weights["internal"] * float(np.sqrt(np.mean(internal_error**2)))
                    + weights["yaw"] * float(np.sqrt(np.mean(normalized_error[[2, 21, 24, 27, 30]] ** 2)))
                ) / float(weights["common_weight_sum"])
                divergent = bool(
                    not (np.all(np.isfinite(prediction)) and np.all(np.isfinite(predicted_force)) and np.isfinite(j_common))
                    or np.max(np.abs(normalized_error)) > float(protocol["training"]["divergence_abs_normalized"])
                )
                permuted_rows.append(
                    {
                        "horizon": int(horizon),
                        "scenario": entry["scenario"],
                        "window": str(category),
                        "base_family_id": entry["base_family_id"],
                        "j_common": j_common,
                        "divergent": divergent,
                    }
                )
    permuted_macro = macro_summary(permuted_rows)

    # A(u) spectral radius over the normalized control box
    a0 = np.asarray(candidate["coefficients"])[:state_dim, :state_dim]
    n_blocks = [
        np.asarray(candidate["coefficients"])[
            start + index * state_dim : start + (index + 1) * state_dim, :state_dim
        ]
        for index in range(control_dim)
    ]
    # frozen normalized control box over the training caches (the fit domain)
    control_parts = []
    for entry in data.train:
        cache = load_cache(entry["cache_path"])
        control_parts.append(np.asarray(cache["control7"], dtype=float))
    control_values = np.concatenate(control_parts, axis=0)
    control_normalized = (control_values - normalization["control7_mean"]) / normalization["control7_scale"]
    control_min = float(np.min(control_normalized))
    control_max = float(np.max(control_normalized))
    vertices = []
    for code in range(2 ** control_dim):
        vertex = np.asarray([control_min if (code >> index) & 1 else control_max for index in range(control_dim)], dtype=float)
        vertices.append(vertex)
    interior = np.random.default_rng(int(seed) + 1).uniform(control_min, control_max, size=(BOX_RANDOM_POINTS, control_dim))
    spectral_max = 0.0
    norm_max = 0.0
    worst_vertex = None
    for vertex in list(vertices) + list(interior):
        a_u = a0 + sum(float(vertex[index]) * n_blocks[index] for index in range(control_dim))
        radius = float(np.max(np.abs(np.linalg.eigvals(a_u))))
        norm = float(np.linalg.norm(a_u, ord=2))
        if radius > spectral_max:
            spectral_max = radius
            worst_vertex = vertex
        norm_max = max(norm_max, norm)

    growth = {
        horizon: {
            "candidate": float(macro_summary(candidate_rows, horizon=horizon)["j_common_macro"]),
            "s0": float(macro_summary(s0_rows, horizon=horizon)["j_common_macro"]),
        }
        for horizon in protocol["training"]["horizons"]
    }
    return {
        "one_step": {
            "candidate_j1": float(macro_summary(candidate_rows, horizon=1)["j_common_macro"]),
            "s0_j1": float(macro_summary(s0_rows, horizon=1)["j_common_macro"]),
            "improvement_percent": float(
                improvement(
                    macro_summary(s0_rows, horizon=1)["j_common_macro"],
                    macro_summary(candidate_rows, horizon=1)["j_common_macro"],
                )
            ),
        },
        "zero_ablation": {
            "full_j20": float(candidate_macro["j_common_macro"]),
            "zeroed_j20": float(zeroed_macro["j_common_macro"]),
            "zeroed_degradation_percent": float(improvement(candidate_macro["j_common_macro"], zeroed_macro["j_common_macro"])),
        },
        "control_permutation": {
            "unpermuted_j20": float(candidate_macro["j_common_macro"]),
            "permuted_j20": float(permuted_macro["j_common_macro"]),
            "permuted_degradation_percent": float(improvement(candidate_macro["j_common_macro"], permuted_macro["j_common_macro"])),
        },
        "error_growth": growth,
        "a_u_box": {
            "control_min": float(control_min),
            "control_max": float(control_max),
            "vertices_checked": len(vertices),
            "interior_points_checked": BOX_RANDOM_POINTS,
            "spectral_radius_max": spectral_max,
            "induced_norm_max": norm_max,
            "worst_vertex": [float(value) for value in worst_vertex] if worst_vertex is not None else None,
        },
        "condition_number": candidate.get("condition_number"),
        "parameter_count": candidate.get("parameter_count"),
        "feature_scale_note": "condition number reported from the ridge gram; feature column scales are recorded in the fit stage",
    }


def _seed_directions(
    frozen,
    data,
    protocol: dict,
    candidate_fit,
    entries,
) -> tuple[list[float], list[dict]]:
    train_families = sorted({row["base_family_id"] for row in data.train})
    directions = []
    details = []
    for seed in protocol["training"]["primary_family_bootstrap_seeds"]:
        rng = np.random.default_rng(int(seed))
        counts = Counter(rng.choice(train_families, size=len(train_families), replace=True))
        boot_candidate = candidate_fit(counts)
        boot_baseline = solve_model(
            accumulate_fit_statistics(data.train, "S0", "M0_FIXED_LINEAR", data.normalization, counts),
            variant="S0",
            model_kind="M0_FIXED_LINEAR",
            ridge=float(protocol["p2_gates"]["expert_ridge"]),
            rank=None,
        )
        candidate_rows = _evaluate_candidate(frozen, data, protocol, boot_candidate, entries)
        baseline_rows = _evaluate_candidate(frozen, data, protocol, boot_baseline, entries)
        direction = improvement(
            macro_summary(baseline_rows)["j_common_macro"],
            macro_summary(candidate_rows)["j_common_macro"],
        )
        directions.append(float(direction))
        details.append({"seed": int(seed), "direction_percent": float(direction)})
    return directions, details


def run_p3(frozen, data, protocol, stage_root) -> dict:
    """Full P3 diagnostic: B0 reproduce, B1 full bilinear, then B2/B3 if allowed."""
    from contracts_v2 import atomic_json

    results: dict = {}
    gates: dict[str, bool] = {}

    # ---- B0: reproduce frozen rank-1 ------------------------------------
    b0 = reproduce_rank1_b0(frozen, data, protocol)
    results["B0"] = {key: value for key, value in b0.items() if key not in {"model", "frozen_model"}}
    gates["B0_reproduce"] = bool(b0["passed"])

    # ---- S0 reference on validation -------------------------------------
    s0_model = solve_model(
        accumulate_fit_statistics(data.train, "S0", "M0_FIXED_LINEAR", data.normalization),
        variant="S0",
        model_kind="M0_FIXED_LINEAR",
        ridge=float(protocol["p2_gates"]["expert_ridge"]),
        rank=None,
    )
    s0_rows = _evaluate_candidate(frozen, data, protocol, s0_model, data.validation)
    s0_macro = macro_summary(s0_rows)

    # ---- B1: full bilinear (ridge selected on validation macro J20) ------
    b1_choices = []
    for ridge in protocol["training"]["ridge_grid"]:
        model = fit_full_bilinear(frozen, data, protocol, float(ridge))
        rows = _evaluate_candidate(frozen, data, protocol, model, data.validation)
        summary = macro_summary(rows)
        b1_choices.append(
            {
                "ridge": float(ridge),
                "j20_macro": float(summary["j_common_macro"]),
                "j1_macro": float(macro_summary(rows, horizon=1)["j_common_macro"]),
                "condition_number": model["condition_number"],
            }
        )
    chosen_b1 = min(b1_choices, key=lambda item: item["j20_macro"])
    b1_model = fit_full_bilinear(frozen, data, protocol, float(chosen_b1["ridge"]))
    b1_rows = _evaluate_candidate(frozen, data, protocol, b1_model, data.validation)
    b1_macro = macro_summary(b1_rows)
    b1_one_step = macro_summary(b1_rows, horizon=1)["j_common_macro"]
    s0_one_step = macro_summary(s0_rows, horizon=1)["j_common_macro"]
    b1_one_step_improvement = improvement(s0_one_step, b1_one_step)
    results["B1"] = {
        "ridge_choices": b1_choices,
        "chosen_ridge": float(chosen_b1["ridge"]),
        "one_step": {"candidate_j1": float(b1_one_step), "s0_j1": float(s0_one_step), "improvement_percent": float(b1_one_step_improvement)},
        "j20_macro": float(b1_macro["j_common_macro"]),
        "s0_j20_macro": float(s0_macro["j_common_macro"]),
        "condition_number": b1_model["condition_number"],
    }
    # one-step "clearly failed" means the candidate is worse than S0 by more
    # than the frozen threshold (improvement < -3%); better one-step error does
    # NOT stop B2/B3, because then the failure cannot be attributed to SVD
    # truncation alone.
    b1_one_step_failed = b1_one_step_improvement < -ONE_STEP_FAILURE_THRESHOLD_PERCENT

    # ---- mechanism checks for B1 ----------------------------------------
    b1_mechanism = mechanism_checks(frozen, data, protocol, b1_model, s0_model)
    results["B1"]["mechanism"] = b1_mechanism

    candidates = [("B1", b1_model, b1_rows)]
    if b1_one_step_failed:
        results["B2_B3"] = {
            "status": "NOT_RUN",
            "reason": "B1 one-step degraded more than 3% vs S0; failure is not SVD-truncation-only, so joint low-rank B2/B3 stop per protocol",
        }
    else:
        for name, rank in (("B2", 1), ("B3", 2)):
            model = _als_rank_r(frozen, data, protocol, ALS_RIDGE, rank)
            rows = _evaluate_candidate(frozen, data, protocol, model, data.validation)
            results[name] = {
                "rank": rank,
                "als_objective": float(model["als_objective"]),
                "als_iterations": int(model["als_iterations"]),
                "j20_macro": float(macro_summary(rows)["j_common_macro"]),
                "one_step": float(macro_summary(rows, horizon=1)["j_common_macro"]),
            }
            results[name]["mechanism"] = mechanism_checks(frozen, data, protocol, model, s0_model)
            candidates.append((name, model, rows))

    # ---- gates for each evaluated candidate ------------------------------
    decision = {"B1": "FAILED_ONE_STEP" if b1_one_step_failed else "EVALUATED"}
    for name, model, rows in candidates:
        macro = macro_summary(rows)
        scenario_improvement = {
            scenario: improvement(s0_macro["scenario_j_common"][scenario], macro["scenario_j_common"][scenario])
            for scenario in s0_macro["scenario_j_common"]
        }
        strong_best = max(
            scenario_improvement.get(scenario, float("-inf"))
            for scenario in protocol["training"]["strong_coupling_scenarios"]
        )
        directions, details = _seed_directions(
            frozen, data, protocol, lambda counts: _candidate_fit(frozen, data, protocol, name, model, counts), data.validation
        )
        candidate_gates = {
            "one_step_not_worse_3pct": results[name]["mechanism"]["one_step"]["improvement_percent"] >= -float(protocol["p3_gates"]["one_step_degradation_max_percent"]),
            "strong_scenario_improvement": strong_best >= float(protocol["p3_gates"]["strong_scenario_improvement_min_percent"]),
            "macro_not_worse_3pct": improvement(s0_macro["j_common_macro"], macro["j_common_macro"]) >= -float(protocol["p3_gates"]["macro_degradation_max_percent"]),
            "bootstrap_direction": sum(value > 0.0 for value in directions) >= int(protocol["p3_gates"]["bootstrap_same_direction_min"]),
            "divergence_rate_increase": macro["divergence_rate"] - s0_macro["divergence_rate"] <= float(protocol["p3_gates"]["divergence_rate_increase_max"]),
            "zero_ablation_destroys_advantage": results[name]["mechanism"]["zero_ablation"]["zeroed_degradation_percent"] >= 5.0 if results[name]["mechanism"]["zero_ablation"]["full_j20"] < s0_macro["j_common_macro"] else True,
            "control_permutation_destroys_advantage": results[name]["mechanism"]["control_permutation"]["permuted_degradation_percent"] >= 5.0 if results[name]["mechanism"]["control_permutation"]["unpermuted_j20"] < s0_macro["j_common_macro"] else True,
        }
        candidate_gates["passed"] = all(candidate_gates.values())
        gates[name] = candidate_gates["passed"]
        decision[name] = "RETAIN" if candidate_gates["passed"] else "REJECT"
        results[name]["gates"] = candidate_gates
        results[name]["scenario_improvement_percent"] = scenario_improvement
        results[name]["seed_directions"] = directions
        results[name]["seed_details"] = details
        results[name]["divergence_rate"] = float(macro["divergence_rate"])

    results["decision"] = decision
    results["summary"] = {
        "B0_reproduce_passed": bool(b0["passed"]),
        "B1_one_step_failed": bool(b1_one_step_failed),
        "gates": gates,
        "note": "if B2/B3 fail the gate, bilinear stays a permanent negative result and never enters P8 combinations",
    }

    write_csv(stage_root / "b1_ridge_choices.csv", results["B1"]["ridge_choices"])
    for name, _, rows in candidates:
        write_csv(stage_root / f"{name.lower()}_rows_validation.csv", rows)
    atomic_json(stage_root / "diagnosis.json", results)
    return {
        "stage": "P3",
        "passed": bool(b0["passed"]),
        "decision": decision,
        "gates": gates,
        "B1_one_step_improvement_percent": float(b1_one_step_improvement),
        "note": "diagnostic stage; gate failure keeps bilinear as a permanent negative result",
    }


def _candidate_fit(frozen, data, protocol, name: str, central_model: dict, counts: Counter) -> dict:
    """Refit a candidate under family-bootstrap counts (B1 exact refit; B2/B3 ALS refit)."""
    if name == "B1":
        return fit_full_bilinear(frozen, data, protocol, float(central_model["ridge"]), counts)
    rank = int(central_model["rank"])
    return _als_rank_r(frozen, data, protocol, ALS_RIDGE, rank, counts)

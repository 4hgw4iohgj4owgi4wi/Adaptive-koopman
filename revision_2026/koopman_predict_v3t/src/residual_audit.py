from __future__ import annotations

"""P1: error-propagation and active-subspace audit of the frozen S0 operator.

Decomposes the S0 residuals by scenario (D0-D11), window class (four classes),
horizon (1/5/10/20) and physical component (core/relative/force4/internal/yaw),
then tests whether "one global fixed operator averages over regimes" has data
support: principal angles between regime residual subspaces, partitioned
linear one-step CV improvement, connector-group explained variance, the S0
Jacobian block structure, and causal group permutation.

All inputs are causal frozen cache fields; confirm is never read; no future
measurement enters any input digest.
"""

from collections import defaultdict

import numpy as np

from contracts_v2 import read_json, write_csv
from data_contract import load_cache
from evaluation_v2 import (
    accumulate_fit_statistics,
    config_key,
    evaluate_model,
    improvement,
    load_frozen_model,
    macro_summary,
    paired_family_bootstrap,
    rollout_model,
    solve_model,
)
from physics_decoder import R3Decoder


# variable groups of the 47-dim relative state
STATE_GROUPS = {
    "g0_payload_velocity_yawrate": slice(0, 3),
    "g1_rho_heading": slice(3, 19),
    "g2_relative_velocity_yawrate": slice(19, 31),
    "g3_connector_disp_vel": slice(31, 47),
}

CV_SEED = 990600
CV_FOLDS = 5
SUBSPACE_DIM = 8
PAIRED_SEED = 990500
PAIRED_REPLICATES = 2000


def collect_residuals(
    frozen,
    data,
    protocol: dict,
    *,
    split: str = "development",
    horizons: tuple[int, ...] = (1, 20),
) -> list[dict]:
    """Roll out the frozen S0 model and store per-window normalized residuals."""
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    normalization = data.normalization
    rows = []
    for entry in data.split(split):
        cache = load_cache(entry["cache_path"])
        params = frozen.resolved_params(int(entry["seed"]), protocol)
        for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
            start = int(start)
            for horizon in horizons:
                prediction, _, _ = rollout_model(
                    model, cache, start, int(horizon), normalization, protocol
                )
                target = np.asarray(cache["relative_state47"][start + int(horizon)], dtype=float)
                residual = (prediction - target) / normalization["relative_state47_scale"]
                rows.append(
                    {
                        "trajectory_id": int(entry["trajectory_id"]),
                        "base_family_id": entry["base_family_id"],
                        "scenario": entry["scenario"],
                        "window": str(category),
                        "window_start": start,
                        "horizon": int(horizon),
                        "residual47": np.asarray(residual, dtype=float),
                    }
                )
    return rows


def residual_by_regime(
    residual_rows: list[dict],
    rows: list[dict],
    protocol: dict,
) -> dict:
    """Decompose S0 metrics by scenario/window/horizon and physical component."""
    table = []
    metrics = ("e_core", "e_relative", "e_force4", "e_internal", "e_yaw", "j_common")
    for horizon in protocol["training"]["horizons"]:
        for scenario in protocol["scenarios"]["order"]:
            for window in protocol["window"]["classes"]:
                selected = [
                    row for row in rows
                    if int(row["horizon"]) == int(horizon)
                    and row["scenario"] == scenario
                    and row["window"] == window
                ]
                if not selected:
                    continue
                table.append(
                    {
                        "horizon": int(horizon),
                        "scenario": scenario,
                        "window": window,
                        "window_count": len(selected),
                        **{name: float(np.mean([row[name] for row in selected])) for name in metrics},
                        "divergence_rate": float(np.mean([row["divergent"] for row in selected])),
                    }
                )
    residual_vectors = {
        horizon: {
            window: np.asarray(
                [row["residual47"] for row in residual_rows if row["horizon"] == horizon and row["window"] == window],
                dtype=float,
            )
            for window in protocol["window"]["classes"]
        }
        for horizon in {int(row["horizon"]) for row in residual_rows}
    }
    covariance = {}
    for horizon, by_window in residual_vectors.items():
        covariance[horizon] = {
            window: (np.cov(matrix, rowvar=False) if matrix.shape[0] > 1 else np.zeros((47, 47)))
            for window, matrix in by_window.items()
        }
    return {
        "table": table,
        "residual_vector_count": len(residual_rows),
        "residual_vector_shapes": {
            str(horizon): {window: list(by_window[window].shape) for window in by_window}
            for horizon, by_window in residual_vectors.items()
        },
        "covariance_frobenius": {
            str(horizon): {
                window: float(np.linalg.norm(cov, ord="fro")) for window, cov in by_window.items()
            }
            for horizon, by_window in covariance.items()
        },
        "covariance_trace_ratio_to_steady": {
            str(horizon): {
                window: (
                    float(np.trace(covariance[horizon][window]) / max(np.trace(covariance[horizon]["steady"]), 1.0e-300))
                    if window != "steady"
                    else 1.0
                )
                for window in by_window
            }
            for horizon, by_window in covariance.items()
        },
    }


def _principal_angles(matrix_a: np.ndarray, matrix_b: np.ndarray, dim: int = SUBSPACE_DIM) -> list[float]:
    if matrix_a.shape[0] < 2 or matrix_b.shape[0] < 2:
        return []
    # orthonormal bases of the 47-dim row spaces (right singular vectors)
    _, _, vt_a = np.linalg.svd(matrix_a, full_matrices=False)
    _, _, vt_b = np.linalg.svd(matrix_b, full_matrices=False)
    keep = min(int(dim), vt_a.shape[0], vt_b.shape[0])
    if keep <= 0:
        return []
    basis_a = vt_a[:keep].T  # (47, keep)
    basis_b = vt_b[:keep].T  # (47, keep)
    cross = basis_a.T @ basis_b
    singular = np.linalg.svd(cross, compute_uv=False)
    angles = np.clip(np.rad2deg(np.arccos(np.clip(singular, -1.0, 1.0))), 0.0, 90.0)
    return [float(value) for value in angles]


def subspace_test(
    residual_rows: list[dict],
    protocol: dict,
    *,
    horizon: int = 20,
) -> dict:
    """Principal angles and separability between regime residual subspaces."""
    groups = {
        "steady": [row for row in residual_rows if row["horizon"] == horizon and row["window"] == "steady"],
        "maneuver": [row for row in residual_rows if row["horizon"] == horizon and row["window"] in {"maneuver", "switch"}],
        "connector_event": [row for row in residual_rows if row["horizon"] == horizon and row["window"] == "connector_event"],
    }
    matrices = {
        name: np.asarray([row["residual47"] for row in rows], dtype=float)
        for name, rows in groups.items()
    }
    pairs = {}
    angle_lists = []
    for left, right in (("steady", "maneuver"), ("steady", "connector_event"), ("maneuver", "connector_event")):
        angles = _principal_angles(matrices[left], matrices[right])
        pairs[f"{left}_vs_{right}"] = {
            "angles_deg": angles,
            "median_deg": float(np.median(angles)) if angles else None,
            "count_left": matrices[left].shape[0],
            "count_right": matrices[right].shape[0],
        }
        angle_lists.extend(angles)

    # between/within scatter on the top-20 principal components
    combined = np.concatenate([matrices[name] for name in groups], axis=0)
    labels = np.concatenate(
        [np.full(matrices[name].shape[0], name) for name in groups], axis=0
    )
    _, singular, vt = np.linalg.svd(combined, full_matrices=False)
    keep = min(20, singular.size)
    projected = combined @ vt[:keep].T
    centers = {
        name: np.mean(matrices[name] @ vt[:keep].T, axis=0) for name in groups
    }
    global_center = np.mean(projected, axis=0)
    between = sum(
        matrices[name].shape[0] * float(np.sum((centers[name] - global_center) ** 2))
        for name in groups
    )
    within = sum(
        float(np.sum((matrices[name] @ vt[:keep].T - centers[name]) ** 2))
        for name in groups
    )
    spectrum = {
        "singular_values_top20": [float(value) for value in singular[:20]],
        "explained_variance_top5": [float((singular[:5] ** 2).sum() / (singular**2).sum())] if singular.size else None,
    }
    return {
        "horizon": int(horizon),
        "pairs": pairs,
        "all_pair_median_deg": float(np.median(angle_lists)) if angle_lists else None,
        "separability": {
            "between_scatter": float(between),
            "within_scatter": float(within),
            "between_within_ratio": float(between / max(within, 1.0e-300)),
        },
        "spectrum": spectrum,
    }


def sensitivity_structure(model: dict) -> dict:
    """Jacobian of the normalized one-step map x_{k+1} = A x_k + B u_k + c."""
    coefficients = np.asarray(model["coefficients"], dtype=float)
    layout = model["layout"]
    state_dim = int(layout["state_dimension"])
    control_dim = int(layout["control_dimension"])
    a = coefficients[:state_dim, :state_dim]
    b = coefficients[:state_dim, state_dim : state_dim + control_dim]
    rows = []
    for name, selected in STATE_GROUPS.items():
        block = a[selected, selected]
        rows.append(
            {
                "group": name,
                "state_columns": f"{selected.start}:{selected.stop}",
                "self_block_frobenius": float(np.linalg.norm(block, ord="fro")),
                "self_block_max_abs": float(np.max(np.abs(block))) if block.size else 0.0,
                "row_norm_max": float(np.max(np.linalg.norm(a[selected, :], axis=1))) if a[selected, :].shape[0] else 0.0,
                "col_norm_max": float(np.max(np.linalg.norm(a[:, selected], axis=0))) if a[:, selected].shape[1] else 0.0,
            }
        )
    control_row = {
        "group": "control7",
        "state_columns": "control",
        "self_block_frobenius": float(np.linalg.norm(b, ord="fro")),
        "self_block_max_abs": float(np.max(np.abs(b))) if b.size else 0.0,
        "row_norm_max": float(np.max(np.linalg.norm(b, axis=1))) if b.shape[0] else 0.0,
        "col_norm_max": float(np.max(np.linalg.norm(b, axis=0))) if b.shape[1] else 0.0,
    }
    return {
        "a_block_rows": rows,
        "control_row": control_row,
        "spectral_radius_A": float(np.max(np.abs(np.linalg.eigvals(a)))) if state_dim else None,
        "largest_singular_A": float(np.linalg.norm(a, ord=2)) if state_dim else None,
    }


def permuted_cache_evaluation(
    frozen,
    data,
    protocol: dict,
    *,
    seed: int = 990700,
) -> dict:
    """Causal group permutation with in-memory cache substitution."""
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz"))
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)

    def evaluate_with_caches(caches: dict[int, dict[str, np.ndarray]]) -> dict:
        rows = []
        for entry in data.development:
            cache = caches[int(entry["trajectory_id"])]
            params = frozen.resolved_params(int(entry["seed"]), protocol)
            for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
                start = int(start)
                for horizon in protocol["training"]["horizons"]:
                    prediction, actuator_prediction, infer_s = rollout_model(
                        model, cache, start, int(horizon), normalization, protocol
                    )
                    target = np.asarray(cache["relative_state47"][start + int(horizon)], dtype=float)
                    normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                    predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                    true_force = np.asarray(cache["force_payload_body8"][start + int(horizon)], dtype=float)
                    true_internal = np.asarray(cache["internal_force8"][start + int(horizon)], dtype=float)
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
                    rows.append(
                        {
                            "horizon": int(horizon),
                            "scenario": entry["scenario"],
                            "window": str(category),
                            "base_family_id": entry["base_family_id"],
                            "j_common": j_common,
                            "divergent": divergent,
                            "inference_s": 0.0,
                        }
                    )
        return rows

    base_caches = {
        int(entry["trajectory_id"]): load_cache(entry["cache_path"]) for entry in data.development
    }
    rng = np.random.default_rng(int(seed))
    baseline_rows = evaluate_with_caches(base_caches)
    baseline = macro_summary(baseline_rows)["j_common_macro"]

    results = {}
    for name, selected in STATE_GROUPS.items():
        permuted = {}
        for trajectory_id, cache in base_caches.items():
            values = np.asarray(cache["relative_state47"], dtype=float).copy()
            count = values.shape[0]
            order = rng.permutation(count)
            values[:, selected] = values[order, selected]
            modified = dict(cache)
            modified["relative_state47"] = values
            permuted[trajectory_id] = modified
        rows = evaluate_with_caches(permuted)
        macro = macro_summary(rows)["j_common_macro"]
        results[name] = {
            "macro_j20": float(macro),
            "j20_degradation_percent": float(improvement(baseline, macro)),
        }
    return {
        "baseline_macro_j20": float(baseline),
        "seed": int(seed),
        "groups": results,
        "note": "negative degradation percent means the permutation made J20 worse (group is causally informative)",
    }


def partitioned_linear_cv(
    frozen,
    data,
    protocol: dict,
    *,
    folds: int = CV_FOLDS,
    seed: int = CV_SEED,
) -> dict:
    """5-fold family CV: single S0 vs regime-partitioned linear (oracle labels)."""
    families = sorted({row["base_family_id"] for row in data.train})
    rng = np.random.default_rng(int(seed))
    order = rng.permutation(families)
    fold_size = (len(order) + int(folds) - 1) // int(folds)
    ridge = float(protocol["p2_gates"]["expert_ridge"])
    normalization = data.normalization
    regimes = protocol["p2_gates"]["regimes"]
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)

    single_errors = []
    partitioned_errors = []
    per_fold = []
    for fold in range(int(folds)):
        test_families = set(order[fold * fold_size : (fold + 1) * fold_size])
        train_entries = [row for row in data.train if row["base_family_id"] not in test_families]
        test_entries = [row for row in data.train if row["base_family_id"] in test_families]
        if not train_entries or not test_entries:
            continue

        # single S0
        single_stats = accumulate_fit_statistics(train_entries, "S0", "M0_FIXED_LINEAR", normalization)
        single_model = solve_model(single_stats, variant="S0", model_kind="M0_FIXED_LINEAR", ridge=ridge, rank=None)
        single_rows = evaluate_model(single_model, test_entries, normalization, protocol, frozen.resolved_params, decoder, seed_label=f"CV_{fold}_SINGLE")
        single_error = macro_summary(single_rows, horizon=1)["j_common_macro"]

        # partitioned experts (oracle window labels): window-level accumulation
        from evaluation_v2 import design_matrix
        expert_stats: dict[str, dict] = {}
        for name, classes in regimes.items():
            gram = None
            cross = None
            layout = None
            row_count = 0
            for entry in train_entries:
                cache = load_cache(entry["cache_path"])
                for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
                    if str(category) not in classes:
                        continue
                    design, target, current_layout = design_matrix(cache, "S0", "M0_FIXED_LINEAR", normalization)
                    # design/target are full-trajectory matrices; select the window row
                    row_design = design[start]
                    row_target = target[start]
                    if layout is None:
                        layout = current_layout
                        gram = np.zeros((design.shape[1], design.shape[1]), dtype=float)
                        cross = np.zeros((design.shape[1], target.shape[1]), dtype=float)
                    gram += np.outer(row_design, row_design)
                    cross += np.outer(row_design, row_target)
                    row_count += 1
            if gram is None:
                raise ValueError(f"expert {name} has no training windows")
            expert_stats[name] = {"gram": gram, "cross": cross, "layout": layout, "row_count": row_count}

        experts = {
            name: solve_model(stats, variant="S0", model_kind="M0_FIXED_LINEAR", ridge=ridge, rank=None)
            for name, stats in expert_stats.items()
        }
        # evaluate each held-out window with the expert of its own class
        partitioned_rows = []
        for entry in test_entries:
            cache = load_cache(entry["cache_path"])
            params = frozen.resolved_params(int(entry["seed"]), protocol)
            for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
                start = int(start)
                expert_name = next(name for name, classes in regimes.items() if str(category) in classes)
                prediction, _, _ = rollout_model(experts[expert_name], cache, start, 1, normalization, protocol)
                target = np.asarray(cache["relative_state47"][start + 1], dtype=float)
                normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                true_force = np.asarray(cache["force_payload_body8"][start + 1], dtype=float)
                true_internal = np.asarray(cache["internal_force8"][start + 1], dtype=float)
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
                partitioned_rows.append(
                    {
                        "horizon": 1,
                        "scenario": entry["scenario"],
                        "window": str(category),
                        "base_family_id": entry["base_family_id"],
                        "j_common": j_common,
                        "divergent": divergent,
                    }
                )
        partitioned_error = macro_summary(partitioned_rows, horizon=1)["j_common_macro"]
        single_errors.append(single_error)
        partitioned_errors.append(partitioned_error)
        per_fold.append(
            {
                "fold": fold,
                "test_family_count": len(test_families),
                "single_j1_macro": float(single_error),
                "partitioned_j1_macro": float(partitioned_error),
                "improvement_percent": float(improvement(single_error, partitioned_error)),
            }
        )

    single_mean = float(np.mean(single_errors))
    partitioned_mean = float(np.mean(partitioned_errors))
    return {
        "folds": int(folds),
        "seed": int(seed),
        "single_j1_macro": single_mean,
        "partitioned_j1_macro": partitioned_mean,
        "improvement_percent": float(improvement(single_mean, partitioned_mean)),
        "per_fold": per_fold,
        "note": "partitioned model uses oracle window labels as an upper-bound diagnostic",
    }


def connector_group_explained(
    residual_rows: list[dict],
    protocol: dict,
    *,
    horizon: int = 20,
) -> dict:
    """Connector-group (g3) share of the S0 residual variance.

    Base families are scenario-specific in the frozen split, so D7/D9/D10
    families and D0 families cannot be paired within family.  We therefore
    report per-scenario family-level means and an unpaired family-bootstrap CI
    of (mean hard-scenario share) minus (mean D0 share); the CI must not cross
    zero for the P1 signal.
    """
    g3 = STATE_GROUPS["g3_connector_disp_vel"]
    family_scores: dict[str, dict[str, float]] = defaultdict(dict)
    for row in residual_rows:
        if row["horizon"] != horizon or row["scenario"] not in {"D0", "D7", "D9", "D10"}:
            continue
        residual = np.asarray(row["residual47"], dtype=float)
        total = float(np.sum(residual**2))
        share = float(np.sum(residual[g3] ** 2)) / max(total, 1.0e-300)
        family_scores[row["base_family_id"]][row["scenario"]] = share

    per_scenario_means: dict[str, float] = {}
    for scenario in ("D0", "D7", "D9", "D10"):
        values = [
            family_scores[family][scenario]
            for family in family_scores
            if scenario in family_scores[family]
        ]
        per_scenario_means[scenario] = float(np.mean(values)) if values else None

    d0_families = [family for family in family_scores if "D0" in family_scores[family]]
    hard_families = [family for family in family_scores if any(name in family_scores[family] for name in ("D7", "D9", "D10"))]
    d0_values = np.asarray([family_scores[f]["D0"] for f in d0_families], dtype=float)
    hard_values = np.asarray(
        [float(np.mean([family_scores[f][name] for name in ("D7", "D9", "D10") if name in family_scores[f]])) for f in hard_families],
        dtype=float,
    )
    difference = float(np.mean(hard_values) - np.mean(d0_values)) if d0_values.size and hard_values.size else None
    ci_low = ci_high = None
    crosses_zero = True
    if d0_values.size and hard_values.size:
        rng = np.random.default_rng(PAIRED_SEED)
        draws = np.empty(PAIRED_REPLICATES, dtype=float)
        for index in range(PAIRED_REPLICATES):
            d0_sample = rng.choice(d0_values, size=len(d0_values), replace=True)
            hard_sample = rng.choice(hard_values, size=len(hard_values), replace=True)
            draws[index] = float(np.mean(hard_sample) - np.mean(d0_sample))
        ci_low = float(np.percentile(draws, 2.5))
        ci_high = float(np.percentile(draws, 97.5))
        crosses_zero = bool(ci_low <= 0.0 <= ci_high)
    return {
        "horizon": int(horizon),
        "per_scenario_mean_share": per_scenario_means,
        "d0_family_count": int(len(d0_values)),
        "hard_family_count": int(len(hard_values)),
        "mean_difference": difference,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "ci_crosses_zero": crosses_zero,
        "bootstrap": "unpaired family bootstrap over scenario-specific families; within-family pairing is impossible by split construction",
        "per_family": [{"base_family_id": key, **value} for key, value in sorted(family_scores.items())],
    }


def run_p1(frozen, data, protocol, stage_root: Path) -> dict:
    """Full P1 audit."""
    from contracts_v2 import atomic_json, load_npz, write_csv

    s0_key = config_key("M0_FIXED_LINEAR", "S0", None)
    model = load_frozen_model(frozen.n6_models_dir() / (s0_key.replace("|", "_") + "_FULL_TRAIN.npz"))

    residuals = collect_residuals(frozen, data, protocol)
    rows = evaluate_model(
        model, data.development, data.normalization, protocol, frozen.resolved_params,
        R3Decoder(frozen.build_planar_grasp_matrix), seed_label="P1_S0",
    )
    regimes = residual_by_regime(residuals, rows, protocol)
    write_csv(stage_root / "residual_by_regime.csv", regimes["table"])

    subspace = subspace_test(residuals, protocol)
    sensitivity = sensitivity_structure(model)
    permutation = permuted_cache_evaluation(frozen, data, protocol)
    cv = partitioned_linear_cv(frozen, data, protocol)
    connector = connector_group_explained(residuals, protocol)

    signals = {
        "principal_angle_signal": bool(
            subspace["all_pair_median_deg"] is not None
            and subspace["all_pair_median_deg"] >= float(protocol["p1_signals"]["principal_angle_median_min_deg"])
        ),
        "partitioned_linear_signal": bool(
            cv["improvement_percent"] >= float(protocol["p1_signals"]["partitioned_linear_one_step_improvement_min_percent"])
        ),
        "connector_group_signal": bool(
            connector["ci_crosses_zero"] is False and connector["mean_difference"] is not None and connector["mean_difference"] > 0.0
        ),
    }
    signals["any_signal"] = any(signals.values())

    write_csv(stage_root / "sensitivity_blocks.csv", sensitivity["a_block_rows"] + [sensitivity["control_row"]])
    write_csv(stage_root / "causal_permutation.csv", [{"group": key, **value} for key, value in permutation["groups"].items()])
    write_csv(stage_root / "partitioned_cv.csv", cv["per_fold"])
    write_csv(stage_root / "connector_group_explained.csv", connector["per_family"])
    atomic_json(stage_root / "subspace_test.json", subspace)
    atomic_json(stage_root / "sensitivity.json", sensitivity)
    atomic_json(stage_root / "permutation.json", permutation)
    atomic_json(stage_root / "partitioned_cv.json", cv)
    atomic_json(stage_root / "connector_group_explained.json", connector)
    atomic_json(stage_root / "signals.json", signals)
    return {
        "stage": "P1",
        "signals": signals,
        "subspace": {key: subspace[key] for key in ("all_pair_median_deg", "pairs", "separability")},
        "partitioned_cv": {key: cv[key] for key in ("improvement_percent", "single_j1_macro", "partitioned_j1_macro")},
        "connector_group": {key: connector[key] for key in ("mean_difference", "ci95_low", "ci95_high", "ci_crosses_zero")},
        "permutation": permutation["groups"],
        "note": "gate failure does not block P5 residual lift; it only removes the 'active subspace proven' claim",
    }

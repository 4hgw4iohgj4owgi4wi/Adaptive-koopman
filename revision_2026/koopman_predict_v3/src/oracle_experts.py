from __future__ import annotations

"""P2: three-expert oracle upper bound.

E0=steady, E1=maneuver or switch, E2=connector_event (connector_event wins on
overlap).  Every expert is a closed-form linear S0 model fitted only on the
train windows of its regime.  Oracle labels (the frozen window classes) are
used only to answer "even if the true regime were known, is there an upper
bound gain from multiple operators"; the oracle is not a deployable model.
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
    macro_summary,
    paired_family_bootstrap,
    rollout_model,
    solve_model,
)
from physics_decoder import R3Decoder


def expert_window_statistics(
    entries: list[dict],
    normalization: dict[str, np.ndarray],
    protocol: dict,
    family_counts: Counter | None = None,
) -> dict[str, dict]:
    """Window-class gram/cross per regime over ALL rows inside the windows of
    that regime (no sample deletion: every row t in [start, stop) inherits the
    frozen class of its non-overlapping 20-step window; rows outside the last
    window have no class and are excluded by construction)."""
    regimes = protocol["p2_gates"]["regimes"]
    steps = int(protocol["window"]["steps"])
    results: dict[str, dict] = {}
    for name, classes in regimes.items():
        gram = None
        cross = None
        layout = None
        row_count = 0
        for entry in entries:
            weight = 1 if family_counts is None else int(family_counts[entry["base_family_id"]])
            if weight <= 0:
                continue
            cache = load_cache(entry["cache_path"])
            design, target, current_layout = design_matrix(
                cache, "S0", "M0_FIXED_LINEAR", normalization
            )
            if layout is None:
                layout = current_layout
                gram = np.zeros((design.shape[1], design.shape[1]), dtype=float)
                cross = np.zeros((design.shape[1], target.shape[1]), dtype=float)
            for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
                if str(category) not in classes:
                    continue
                for row_index in range(int(start), int(start) + steps):
                    row_design = design[row_index]
                    row_target = target[row_index]
                    gram += weight * np.outer(row_design, row_design)
                    cross += weight * np.outer(row_design, row_target)
                    row_count += weight
        if gram is None:
            raise ValueError(f"expert {name} has no training windows")
        results[name] = {"gram": gram, "cross": cross, "layout": layout, "row_count": row_count}
    return results


def fit_oracle_experts(
    frozen,
    data,
    protocol: dict,
    family_counts: Counter | None = None,
) -> dict[str, dict]:
    """Fit the three closed-form linear experts (shared ridge from the protocol)."""
    ridge = float(protocol["p2_gates"]["expert_ridge"])
    statistics = expert_window_statistics(data.train, data.normalization, protocol, family_counts)
    return {
        name: solve_model(stats, variant="S0", model_kind="M0_FIXED_LINEAR", ridge=ridge, rank=None)
        for name, stats in statistics.items()
    }


def fit_s0_baseline(
    frozen,
    data,
    protocol: dict,
    family_counts: Counter | None = None,
) -> dict:
    """S0 fixed-linear baseline fitted on all train windows (frozen ridge)."""
    ridge = float(protocol["p2_gates"]["expert_ridge"])
    statistics = accumulate_fit_statistics(
        data.train, "S0", "M0_FIXED_LINEAR", data.normalization, family_counts
    )
    return solve_model(statistics, variant="S0", model_kind="M0_FIXED_LINEAR", ridge=ridge, rank=None)


def evaluate_with_expert_map(
    frozen,
    data,
    protocol: dict,
    expert_map: dict[str, dict],
    entries: list[dict],
) -> list[dict]:
    """Evaluate every window of ``entries`` with the expert of its own class."""
    normalization = data.normalization
    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    weights = protocol["metric_weights"]
    rows = []
    for entry in entries:
        cache = load_cache(entry["cache_path"])
        params = frozen.resolved_params(int(entry["seed"]), protocol)
        for start, category in zip(cache["window_start"], cache["window_class"], strict=True):
            start = int(start)
            expert_name = next(
                name for name, classes in protocol["p2_gates"]["regimes"].items()
                if str(category) in classes
            )
            for horizon in protocol["training"]["horizons"]:
                prediction, _, _ = rollout_model(
                    expert_map[expert_name], cache, start, int(horizon), normalization, protocol
                )
                target = np.asarray(cache["relative_state47"][start + int(horizon)], dtype=float)
                normalized_error = (prediction - target) / normalization["relative_state47_scale"]
                predicted_force, predicted_internal = decoder.connector_force(prediction, params, entry["law"])
                true_force = np.asarray(cache["force_payload_body8"][start + int(horizon)], dtype=float)
                true_internal = np.asarray(cache["internal_force8"][start + int(horizon)], dtype=float)
                force_error = (predicted_force - true_force) / normalization["force_payload_body8_scale"]
                internal_error = (predicted_internal - true_internal) / normalization["internal_force8_scale"]
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
                        "model_kind": "M0_FIXED_LINEAR",
                        "variant": "S0",
                        "ridge": float(protocol["p2_gates"]["expert_ridge"]),
                        "rank": None,
                        "seed_label": "ORACLE_EXPERT",
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
                        "expert": expert_name,
                        "j_common": j_common,
                        "divergent": divergent,
                    }
                )
    return rows


def run_p2(frozen, data, protocol, stage_root) -> dict:
    """Full P2 oracle-expert run on validation with 5 primary bootstrap seeds."""
    from contracts_v2 import atomic_json

    # central oracle
    experts = fit_oracle_experts(frozen, data, protocol)
    baseline_model = fit_s0_baseline(frozen, data, protocol)
    baseline_rows = evaluate_model(
        baseline_model, data.validation, data.normalization, protocol,
        frozen.resolved_params, R3Decoder(frozen.build_planar_grasp_matrix),
        seed_label="S0_BASELINE",
    )
    oracle_rows = evaluate_with_expert_map(frozen, data, protocol, experts, data.validation)
    comparison = _compare_oracle(baseline_rows, oracle_rows, protocol)

    # bootstrap seeds
    train_families = sorted({row["base_family_id"] for row in data.train})
    seed_directions = []
    for seed in protocol["training"]["primary_family_bootstrap_seeds"]:
        rng = np.random.default_rng(int(seed))
        counts = Counter(rng.choice(train_families, size=len(train_families), replace=True))
        boot_experts = fit_oracle_experts(frozen, data, protocol, counts)
        boot_baseline = fit_s0_baseline(frozen, data, protocol, counts)
        boot_baseline_rows = evaluate_model(
            boot_baseline, data.validation, data.normalization, protocol,
            frozen.resolved_params, R3Decoder(frozen.build_planar_grasp_matrix),
            seed_label=str(seed),
        )
        boot_oracle_rows = evaluate_with_expert_map(frozen, data, protocol, boot_experts, data.validation)
        direction = improvement(
            macro_summary(boot_baseline_rows)["j_common_macro"],
            macro_summary(boot_oracle_rows)["j_common_macro"],
        )
        seed_directions.append(float(direction))

    gates = {
        "macro_improvement": comparison["macro_improvement_percent"] >= float(protocol["p2_gates"]["macro_improvement_min_percent"]),
        "switch_or_connector_window": max(
            comparison["window_improvement_percent"].get("switch", float("-inf")),
            comparison["window_improvement_percent"].get("connector_event", float("-inf")),
        ) >= float(protocol["p2_gates"]["switch_or_connector_window_improvement_min_percent"]),
        "hard_scenario": max(
            comparison["scenario_improvement_percent"].get(name, float("-inf"))
            for name in ("D7", "D9", "D10")
        ) >= float(protocol["p2_gates"]["hard_scenario_improvement_min_percent"]),
        "scenario_degradation": max(
            [-comparison["scenario_improvement_percent"].get(name, 0.0) for name in comparison["scenario_improvement_percent"]],
            default=0.0,
        ) <= float(protocol["p2_gates"]["scenario_degradation_max_percent"]),
        "divergence_not_increased": comparison["divergence_rate_change"] <= 0.0,
        "bootstrap_direction": sum(value > 0.0 for value in seed_directions) >= int(protocol["p2_gates"]["bootstrap_same_direction_min"]),
    }
    gates["passed"] = all(gates.values())

    write_csv(stage_root / "oracle_vs_s0_validation.csv", baseline_rows)
    write_csv(stage_root / "oracle_rows_validation.csv", oracle_rows)
    atomic_json(stage_root / "comparison.json", {**comparison, "seed_improvement_percent": seed_directions, "seed_positive_count": int(sum(value > 0.0 for value in seed_directions))})
    atomic_json(stage_root / "gates.json", {"hard_gates": gates, "note": "oracle upper bound only; not a deployable model"})
    return {
        "stage": "P2",
        "passed": gates["passed"],
        "gates": gates,
        "comparison_macro_percent": comparison["macro_improvement_percent"],
        "window_improvement_percent": comparison["window_improvement_percent"],
        "hard_scenario_improvement_percent": {name: comparison["scenario_improvement_percent"][name] for name in ("D7", "D9", "D10")},
        "seed_directions": seed_directions,
        "decision": "ALLOW_P4_CAUSAL_GATE" if gates["passed"] else "CANCEL_MULTI_EXPERT_ROUTE",
    }


def _compare_oracle(baseline_rows: list[dict], candidate_rows: list[dict], protocol: dict) -> dict:
    base = macro_summary(baseline_rows)
    cand = macro_summary(candidate_rows)
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
        "divergence_rate_change": cand["divergence_rate"] - base["divergence_rate"],
        "paired_ci": paired_family_bootstrap(
            candidate_rows,
            baseline_rows,
            replicates=int(protocol["training"]["paired_ci_replicates"]),
            seed=int(protocol["training"]["paired_ci_seed"]),
        ),
        "baseline_j20_macro": float(base["j_common_macro"]),
        "oracle_j20_macro": float(cand["j_common_macro"]),
    }

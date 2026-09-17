from __future__ import annotations

"""P0 baseline reproduction: refit the frozen M0-S0 central model from the
frozen train statistics and regress it against the frozen N6 S0 model."""

import numpy as np

from contracts_v2 import load_npz, read_json
from evaluation_v2 import (
    accumulate_fit_statistics,
    config_key,
    evaluate_model,
    macro_summary,
    solve_model,
)
from physics_decoder import R3Decoder


def reproduce_m0_s0(
    frozen,
    data,
    protocol: dict,
) -> dict:
    """Exactly reproduce the N6 M0-FIXED-LINEAR S0 central (FULL_TRAIN) model.

    Refits the closed-form ridge model from the frozen train caches with the
    frozen hyperparameters, then regresses coefficients, condition number,
    parameter count, fit row count and development J20 against the frozen N6
    model artifacts.
    """
    n6_stage = frozen.n6_stage_dir()
    selections = read_json(n6_stage / "frozen_hyperparameter_selection.json")
    key = config_key("M0_FIXED_LINEAR", "S0", None)
    selected = selections[key]
    normalization = data.normalization

    statistics = accumulate_fit_statistics(
        data.train, selected["variant"], selected["model_kind"], normalization
    )
    refitted = solve_model(
        statistics,
        variant=selected["variant"],
        model_kind=selected["model_kind"],
        ridge=selected["ridge"],
        rank=selected["rank"],
    )

    frozen_model_path = frozen.n6_models_dir() / (key.replace("|", "_") + "_FULL_TRAIN.npz")
    frozen_model = load_npz(frozen_model_path)
    frozen_metadata = read_json(frozen_model_path.with_suffix(".json"))
    frozen_coefficients = frozen_model["coefficients"]

    coefficient_max_abs = float(np.max(np.abs(refitted["coefficients"] - frozen_coefficients)))
    coefficient_scale = float(np.max(np.abs(frozen_coefficients))) if frozen_coefficients.size else 1.0
    coefficient_relative = coefficient_max_abs / max(coefficient_scale, 1.0e-300)

    decoder = R3Decoder(frozen.build_planar_grasp_matrix)
    rows = evaluate_model(
        refitted, data.development, normalization, protocol, frozen.resolved_params,
        decoder, seed_label="V2_REPRODUCE",
    )
    summary = macro_summary(rows)
    j20_reference = float(protocol["p0_gates"]["s0_j20_common_reference"])
    j20_error = abs(float(summary["j_common_macro"]) - j20_reference)

    regression = {
        "config_key": key,
        "ridge": float(selected["ridge"]),
        "coefficient_max_abs_error": coefficient_max_abs,
        "coefficient_relative_error": coefficient_relative,
        "condition_number_refitted": float(refitted["condition_number"]),
        "condition_number_frozen": float(frozen_metadata["condition_number"]),
        "condition_number_error": abs(float(refitted["condition_number"]) - float(frozen_metadata["condition_number"])),
        "parameter_count_refitted": int(refitted["parameter_count"]),
        "parameter_count_frozen": int(frozen_metadata["parameter_count"]),
        "fit_row_count_refitted": int(refitted["fit_row_count"]),
        "fit_row_count_frozen": int(frozen_metadata["fit_row_count"]),
        "j20_common_refitted": float(summary["j_common_macro"]),
        "j20_common_frozen_reference": j20_reference,
        "j20_common_abs_error": j20_error,
        "coefficients_shape": list(frozen_coefficients.shape),
    }
    passed = (
        regression["coefficient_relative_error"] <= 1e-9
        and regression["condition_number_error"] <= 1e-9 * max(abs(regression["condition_number_frozen"]), 1.0)
        and regression["parameter_count_refitted"] == regression["parameter_count_frozen"]
        and regression["fit_row_count_refitted"] == regression["fit_row_count_frozen"]
        and regression["j20_common_abs_error"] <= float(protocol["p0_gates"]["s0_j20_common_abs_tolerance"])
    )
    return {"passed": passed, "regression": regression, "model": refitted, "rows": rows}

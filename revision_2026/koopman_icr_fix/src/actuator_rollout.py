from __future__ import annotations

import numpy as np

from steering_actuator import SteeringActuatorConfig, step_actuator


def rollout_actuator_interval(
    delta_act_k_rad: np.ndarray,
    delta_req_k_rad: np.ndarray,
    *,
    plant_step_s: float,
    substeps: int,
    config: SteeringActuatorConfig,
) -> dict[str, np.ndarray]:
    """Causally propagate a held request and return trapezoidal interval means."""

    if int(substeps) != substeps or int(substeps) <= 0:
        raise ValueError(f"invalid actuator substep count: {substeps}")
    actual = np.asarray(delta_act_k_rad, dtype=float).copy()
    request = np.asarray(delta_req_k_rad, dtype=float)
    if actual.shape != request.shape:
        raise ValueError("request and actuator state must have identical shapes")
    endpoints = []
    rates = []
    rate_masks = []
    angle_masks = []
    trapezoid_sum = np.zeros_like(actual)
    for _ in range(int(substeps)):
        previous = actual.copy()
        result = step_actuator(request, previous, plant_step_s, config)
        actual = result["delta_act_next_rad"]
        trapezoid_sum += 0.5 * (previous + actual)
        endpoints.append(actual.copy())
        rates.append(result["delta_rate_radps"].copy())
        rate_masks.append(result["rate_limited_mask"].copy())
        angle_masks.append(result["angle_limited_mask"].copy())
    return {
        "delta_act_k1_rad": actual,
        "delta_act_mean_rad": trapezoid_sum / float(substeps),
        "delta_act_substeps_rad": np.asarray(endpoints),
        "delta_rate_substeps_radps": np.asarray(rates),
        "rate_limited_substeps": np.asarray(rate_masks, dtype=bool),
        "angle_limited_substeps": np.asarray(angle_masks, dtype=bool),
    }

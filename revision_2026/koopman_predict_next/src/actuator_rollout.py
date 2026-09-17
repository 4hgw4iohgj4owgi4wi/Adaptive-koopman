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


def rollout_actuator_step(
    delta_act_k_rad: np.ndarray,
    delta_req_k_rad: np.ndarray,
    *,
    model_step_s: float,
    plant_step_s: float,
    config: SteeringActuatorConfig,
    step_atol_s: float = 1.0e-12,
) -> dict[str, np.ndarray]:
    """Propagate one model interval on the frozen integer A3 substep grid."""

    if not np.isfinite(model_step_s) or model_step_s <= 0.0:
        raise ValueError(f"invalid model step: {model_step_s}")
    if not np.isfinite(plant_step_s) or plant_step_s <= 0.0:
        raise ValueError(f"invalid plant step: {plant_step_s}")
    substeps = int(round(model_step_s / plant_step_s))
    if substeps <= 0 or abs(substeps * plant_step_s - model_step_s) > step_atol_s:
        raise ValueError(
            "model interval must contain an integer number of actuator substeps: "
            f"model_step_s={model_step_s}, plant_step_s={plant_step_s}"
        )
    return rollout_actuator_interval(
        delta_act_k_rad,
        delta_req_k_rad,
        plant_step_s=plant_step_s,
        substeps=substeps,
        config=config,
    )


def rollout_actuator_horizon(
    delta_act_k_rad: np.ndarray,
    delta_req_horizon_rad: np.ndarray,
    *,
    model_step_s: float,
    plant_step_s: float,
    config: SteeringActuatorConfig,
    step_atol_s: float = 1.0e-12,
) -> dict[str, np.ndarray]:
    """Causally propagate known requests for an arbitrary model horizon.

    Row ``h`` of ``delta_req_horizon_rad`` is the request held on model
    interval ``[t_{k+h}, t_{k+h+1}]``.  No future measured actuator state is
    read.  Endpoint row ``h`` therefore represents ``t_{k+h+1}``.
    """

    actual = np.asarray(delta_act_k_rad, dtype=float).copy()
    requests = np.asarray(delta_req_horizon_rad, dtype=float)
    if actual.ndim != 1:
        raise ValueError(f"actuator state must be one-dimensional: {actual.shape}")
    if requests.ndim != 2 or requests.shape[1:] != actual.shape:
        raise ValueError(
            "request horizon must have shape (horizon, actuator_count): "
            f"actual={actual.shape}, requests={requests.shape}"
        )
    if requests.shape[0] <= 0:
        raise ValueError("request horizon is empty")
    if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(requests)):
        raise ValueError("non-finite actuator horizon input")

    endpoints = []
    means = []
    rates = []
    rate_masks = []
    angle_masks = []
    for request in requests:
        interval = rollout_actuator_step(
            actual,
            request,
            model_step_s=model_step_s,
            plant_step_s=plant_step_s,
            config=config,
            step_atol_s=step_atol_s,
        )
        actual = np.asarray(interval["delta_act_k1_rad"], dtype=float)
        endpoints.append(actual.copy())
        means.append(np.asarray(interval["delta_act_mean_rad"], dtype=float).copy())
        rates.append(np.asarray(interval["delta_rate_substeps_radps"], dtype=float).copy())
        rate_masks.append(
            np.any(np.asarray(interval["rate_limited_substeps"], dtype=bool), axis=0)
        )
        angle_masks.append(
            np.any(np.asarray(interval["angle_limited_substeps"], dtype=bool), axis=0)
        )
    return {
        "delta_act_endpoints_rad": np.asarray(endpoints),
        "delta_act_means_rad": np.asarray(means),
        "delta_rate_substeps_radps": np.asarray(rates),
        "rate_limited_intervals": np.asarray(rate_masks, dtype=bool),
        "angle_limited_intervals": np.asarray(angle_masks, dtype=bool),
    }

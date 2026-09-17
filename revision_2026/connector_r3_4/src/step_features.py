from __future__ import annotations

import numpy as np


def _weighted_mean(values: np.ndarray, dt: np.ndarray, duration: float) -> np.ndarray:
    return np.sum(values * dt.reshape((-1,) + (1,) * (values.ndim - 1)), axis=0) / duration


def aggregate_step_audit(state_endpoint: np.ndarray, control: np.ndarray, audit: dict) -> dict:
    segments = audit.get("interval_segments", [])
    duration = sum(float(segment["dt_s"]) for segment in segments)
    if duration <= 0:
        raise ValueError("interval audit has no advanced duration")
    dt = np.asarray([segment["dt_s"] for segment in segments], dtype=float)
    force = np.asarray([segment["force_payload_world_n"] for segment in segments], dtype=float)
    gaps = np.asarray([segment["signed_gap_m"] for segment in segments], dtype=float)
    weight = np.asarray([segment["smoothing_weight"] for segment in segments], dtype=float)
    contact = np.asarray([segment["contact_active"] for segment in segments], dtype=float)
    smooth = np.asarray([segment["smoothing_active"] for segment in segments], dtype=float)
    internal = np.asarray([segment.get("internal_force_vector_n", np.zeros(8)) for segment in segments], dtype=float)
    tension = np.asarray(
        [[segment.get("tension_x_n", 0.0), segment.get("tension_y_n", 0.0)] for segment in segments],
        dtype=float,
    )
    tire_raw = np.asarray([segment.get("tire_raw_utilization", np.zeros(4)) for segment in segments], dtype=float)
    tire_saturated = np.asarray([segment.get("tire_saturated", np.zeros(4)) for segment in segments], dtype=float)
    impulse = np.sum(force * dt[:, None, None], axis=0)
    events = audit["events"]
    endpoint = audit["endpoint_diagnostics"]
    event_counts = np.r_[
        [sum(1 for event in events if event["connector_id"] == index and event["surface"] == "contact" and event["direction"] == "load") for index in range(4)],
        [sum(1 for event in events if event["connector_id"] == index and event["surface"] == "contact" and event["direction"] == "unload") for index in range(4)],
        [sum(1 for event in events if event["connector_id"] == index and event["surface"] == "smoothing" and event["direction"] == "load") for index in range(4)],
        [sum(1 for event in events if event["connector_id"] == index and event["surface"] == "smoothing" and event["direction"] == "unload") for index in range(4)],
    ].astype(int)
    return {
        "state_endpoint": np.asarray(state_endpoint, dtype=float).copy(),
        "control": np.asarray(control, dtype=float).reshape(4, 2).copy(),
        "interval_duration_s": duration,
        "force_endpoint_world": np.asarray(endpoint["force_payload_world_n"], dtype=float).copy(),
        "force_endpoint_body": np.asarray(endpoint["force_payload_body_n"], dtype=float).copy(),
        "force_direction_body_rad": np.asarray(endpoint.get("force_direction_body_rad", np.zeros(4)), dtype=float).copy(),
        "force_active_mask": np.asarray(endpoint.get("force_active_mask", np.zeros(4)), dtype=bool).copy(),
        "force_mean_world": impulse / duration,
        "force_peak_norm": np.asarray(audit["force_peak_n"], dtype=float).copy(),
        "force_impulse_world": impulse,
        "force_impulse_norm": np.linalg.norm(impulse, axis=1),
        "internal_force_mean": _weighted_mean(internal, dt, duration),
        "tension_proxy_mean": _weighted_mean(tension, dt, duration),
        "damping_work": np.asarray(audit["damping_work_j"], dtype=float).copy(),
        "contact_fraction": _weighted_mean(contact, dt, duration),
        "smoothing_fraction": _weighted_mean(smooth, dt, duration),
        "g_min": np.min(weight, axis=0),
        "g_mean": _weighted_mean(weight, dt, duration),
        "g_max": np.max(weight, axis=0),
        "delta_min": np.min(gaps, axis=0),
        "delta_max": np.max(gaps, axis=0),
        "event_counts16": event_counts,
        "contact_on_count": event_counts[0:4],
        "contact_off_count": event_counts[4:8],
        "smoothing_in_count": event_counts[8:12],
        "smoothing_out_count": event_counts[12:16],
        "tire_raw_utilization_max": np.max(tire_raw, axis=0),
        "tire_saturation_fraction": _weighted_mean(tire_saturated, dt, duration),
        "substep_count": int(audit["accepted_steps"]),
        "min_substep_s": float(audit["min_physical_dt_s"]),
        "max_substep_s": float(audit["max_physical_dt_s"]),
        "event_time_offsets_s": np.asarray([event["time_offset_s"] for event in events], dtype=float),
        "event_connector_ids": np.asarray([event["connector_id"] for event in events], dtype=int),
        "solver_status": audit["status"],
    }


def aggregate_control_interval(step_features: list[dict], expected_duration_s: float = 0.02) -> dict:
    duration = sum(float(item["interval_duration_s"]) for item in step_features)
    if abs(duration - expected_duration_s) > 1e-12:
        raise ValueError("control interval duration mismatch")
    durations = np.asarray([item["interval_duration_s"] for item in step_features], dtype=float)
    impulse = sum((np.asarray(item["force_impulse_world"], dtype=float) for item in step_features), start=np.zeros((4, 2)))
    weighted = lambda key: np.sum(
        np.asarray([item[key] for item in step_features], dtype=float) * durations[:, None], axis=0
    ) / duration
    return {
        "interval_duration_s": duration,
        "state_endpoint": np.asarray(step_features[-1]["state_endpoint"], dtype=float),
        "control": np.asarray(step_features[-1]["control"], dtype=float),
        "force_impulse_world": impulse,
        "force_mean_world": impulse / duration,
        "internal_force_mean": weighted("internal_force_mean"),
        "tension_proxy_mean": weighted("tension_proxy_mean"),
        "contact_fraction": weighted("contact_fraction"),
        "smoothing_fraction": weighted("smoothing_fraction"),
        "g_min": np.min([item["g_min"] for item in step_features], axis=0),
        "g_mean": weighted("g_mean"),
        "g_max": np.max([item["g_max"] for item in step_features], axis=0),
        "delta_min": np.min([item["delta_min"] for item in step_features], axis=0),
        "delta_max": np.max([item["delta_max"] for item in step_features], axis=0),
        "event_counts16": np.sum([item["event_counts16"] for item in step_features], axis=0),
        "force_active_mask": np.asarray(step_features[-1]["force_active_mask"], dtype=bool),
        "force_direction_body_rad": np.asarray(step_features[-1]["force_direction_body_rad"], dtype=float),
        "tire_raw_utilization_max": np.max([item["tire_raw_utilization_max"] for item in step_features], axis=0),
        "tire_saturation_fraction": weighted("tire_saturation_fraction"),
    }

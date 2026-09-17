from __future__ import annotations

import numpy as np


def aggregate_step_audit(state_endpoint: np.ndarray, control: np.ndarray, audit: dict) -> dict:
    """Protocol 2.7 fields from the already completed interval only."""
    endpoint = audit["endpoint_diagnostics"]
    events = audit["events"]
    gaps = np.asarray(endpoint["signed_gap_m"], dtype=float)
    weight = np.asarray(endpoint["smoothing_weight"], dtype=float)
    width = 0.0001776170305060031
    return {
        "state_endpoint": np.asarray(state_endpoint, dtype=float).copy(),
        "control": np.asarray(control, dtype=float).reshape(4, 2).copy(),
        "force_endpoint_world": np.asarray(endpoint["force_payload_world_n"], dtype=float).copy(),
        "force_endpoint_body": np.asarray(endpoint["force_payload_body_n"], dtype=float).copy(),
        "force_mean_world": np.asarray(audit["force_impulse_world_ns"], dtype=float) / 0.002,
        "force_peak_norm": np.asarray(audit["force_peak_n"], dtype=float).copy(),
        "force_impulse_world": np.asarray(audit["force_impulse_world_ns"], dtype=float).copy(),
        "force_impulse_norm": np.linalg.norm(audit["force_impulse_world_ns"], axis=1),
        "damping_work": np.asarray(audit["damping_work_j"], dtype=float).copy(),
        "contact_fraction": (gaps > 0.0).astype(float),
        "smoothing_fraction": ((gaps > 0.0) & (gaps < width)).astype(float),
        "g_min": weight.copy(), "g_mean": weight.copy(), "g_max": weight.copy(),
        "delta_min": gaps.copy(), "delta_max": gaps.copy(),
        "contact_on_count": np.asarray([sum(1 for event in events if event["connector_id"] == index and event["surface"] == "contact" and event["direction"] == "load") for index in range(4)]),
        "contact_off_count": np.asarray([sum(1 for event in events if event["connector_id"] == index and event["surface"] == "contact" and event["direction"] == "unload") for index in range(4)]),
        "smoothing_in_count": np.asarray([sum(1 for event in events if event["connector_id"] == index and event["surface"] == "smoothing" and event["direction"] == "load") for index in range(4)]),
        "smoothing_out_count": np.asarray([sum(1 for event in events if event["connector_id"] == index and event["surface"] == "smoothing" and event["direction"] == "unload") for index in range(4)]),
        "substep_count": int(audit["accepted_steps"]),
        "min_substep_s": float(audit["min_physical_dt_s"]),
        "max_substep_s": float(audit["max_physical_dt_s"]),
        "event_time_offsets_s": np.asarray([event["time_offset_s"] for event in events], dtype=float),
        "event_connector_ids": np.asarray([event["connector_id"] for event in events], dtype=int),
        "solver_status": audit["status"],
    }


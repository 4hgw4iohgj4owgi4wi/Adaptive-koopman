"""Accounting contract for accepted plant intervals, including terminal failures."""
from __future__ import annotations

import numpy as np


def consume_audit(
    audit: dict,
    t_start_s: float,
    state_at_t_end=None,
    actuator_state_before=None,
    actuator_state_after=None,
) -> dict:
    """Normalize an integrator audit without treating rejected probes as motion."""
    segments = list(audit.get("interval_segments", ()))
    accepted_duration = float(sum(float(seg["dt_s"]) for seg in segments))
    reported_duration = float(audit.get("duration_actual_s", accepted_duration))
    if not np.isclose(accepted_duration, reported_duration, atol=1e-12, rtol=0.0):
        raise ValueError("accepted segment duration disagrees with duration_actual_s")
    accepted_steps = int(audit.get("accepted_steps", len(segments)))
    if accepted_steps != len(segments):
        raise ValueError("accepted step count disagrees with interval_segments")

    peak = np.zeros(4, dtype=float)
    argmax = [{"time_s": float(t_start_s), "source": "none", "value_n": 0.0} for _ in range(4)]
    offset = 0.0
    for seg_index, seg in enumerate(segments):
        dt = float(seg["dt_s"])
        samples = (
            (offset, "segment_start", seg.get("force_start_n", np.zeros(4))),
            (offset + 0.5 * dt, "segment_midpoint", seg.get("force_midpoint_n", np.zeros(4))),
            (offset + dt, "segment_endpoint", seg.get("force_endpoint_n", np.zeros(4))),
        )
        for sample_offset, source, values in samples:
            values = np.asarray(values, dtype=float)
            for connector in range(4):
                if values[connector] >= peak[connector]:
                    peak[connector] = values[connector]
                    argmax[connector] = {
                        "time_s": float(t_start_s + sample_offset),
                        "source": f"{source}:{seg_index}",
                        "value_n": float(values[connector]),
                    }
        offset += dt

    audit_peak = np.asarray(audit.get("force_peak_n", peak), dtype=float)
    if np.any(audit_peak > peak + 1e-12):
        for connector in np.flatnonzero(audit_peak > peak + 1e-12):
            peak[connector] = audit_peak[connector]
            argmax[connector] = {
                "time_s": float(t_start_s + accepted_duration),
                "source": "audit_peak_time_unresolved",
                "value_n": float(audit_peak[connector]),
            }

    status = str(audit.get("status", "PASS"))
    t_end = float(t_start_s + accepted_duration)
    return {
        "status": status,
        "accepted": accepted_steps > 0,
        "accepted_steps": accepted_steps,
        "accepted_duration_s": accepted_duration,
        "t_start_s": float(t_start_s),
        "t_end_s": t_end,
        "failure_event_time_s": t_end if status != "PASS" else None,
        "force_peak_n": peak,
        "force_peak_argmax": argmax,
        "segments": segments,
        "state_at_t_end": None if state_at_t_end is None else np.asarray(state_at_t_end, dtype=float).copy(),
        "actuator_update_time_s": float(t_start_s) if actuator_state_after is not None else None,
        "actuator_state_before": None if actuator_state_before is None else np.asarray(actuator_state_before, dtype=float).copy(),
        "actuator_state_after": None if actuator_state_after is None else np.asarray(actuator_state_after, dtype=float).copy(),
        "actuator_semantics": "discrete jump at interval start" if actuator_state_after is not None else None,
    }

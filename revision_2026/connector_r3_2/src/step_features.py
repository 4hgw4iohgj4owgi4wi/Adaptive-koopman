from __future__ import annotations


def scalar_step_features(result: dict) -> dict:
    """Return the registered scalar subset of per-step event diagnostics."""
    return {
        "force_peak_n": result["peak_force_n"],
        "force_impulse_ns": result["impulse_ns"],
        "damping_work_j": result["damping_work_j"],
        "substep_count": result["accepted_steps"],
        "min_substep_s": result["min_accepted_dt_s"],
        "event_time_offsets_s": [event["time_s"] for event in result["events"]],
        "solver_status": result["status"],
    }


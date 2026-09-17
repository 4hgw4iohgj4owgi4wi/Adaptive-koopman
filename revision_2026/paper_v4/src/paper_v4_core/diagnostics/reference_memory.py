"""Reference-chain memory replay, used to rebuild a checkpoint from saved artifacts.

The frozen runner writes ``time_s = k*Ts + accepted_duration`` and never persists
``beta`` (the integrated reference relative-heading memory).  ``beta`` is not an
independent memory: it is a deterministic function of the reference chain, so it
can be replayed from the persisted artifacts.

This rule is identical to the one registered and validated in
``analysis/20260915_D1B_BETA_MEMORY_REPLAY_03`` (protocol
``D1B_BETA_MEMORY_REPLAY_20260915_v3.json``), where the replayed reference
distance reproduced the persisted ``reference_distance_m`` to 1.42e-14 m
(2.2e-16 relative).  Callers should re-verify that closure before trusting a
checkpoint; ``verify_replay`` below performs exactly that check.
"""
from __future__ import annotations

import numpy as np

from ..e01_100m import DT
from ..pilot_runner import ROUTE_LENGTH, SPEED, make_preview


def recover_interval_duration(time_s) -> np.ndarray:
    """Accepted duration of tick k, recoverable as time_s[k] - k*Ts."""
    time_s = np.asarray(time_s, dtype=float)
    return time_s - np.arange(time_s.size, dtype=float) * DT


def replay_reference_chain(model, duration) -> tuple[np.ndarray, np.ndarray]:
    """Replay distance and beta exactly in the frozen runner's order.

    The frozen runner updates ``distance`` first and then uses the *same*
    ``refs[0]["beta_star"]`` taken from the preview at the pre-update
    ``(distance, beta)``; see post_r3_r4_runner.py lines 171-172.
    """
    duration = np.asarray(duration, dtype=float)
    ticks = duration.size
    distance = 0.0
    beta = np.zeros(4, dtype=float)
    distances = np.zeros(ticks, dtype=float)
    betas = np.zeros((ticks, 4), dtype=float)
    for k in range(ticks):
        _controls, refs, _preview = make_preview(distance, beta, model, np.zeros(8), 20)
        distance = min(distance + SPEED * duration[k], ROUTE_LENGTH)
        beta = beta + (duration[k] / DT) * (np.asarray(refs[0]["beta_star"], float) - beta)
        distances[k] = distance
        betas[k] = beta
    return distances, betas


def verify_replay(model, time_s, reference_distance_m) -> dict:
    """Independent closure check of the replay against the persisted distance."""
    duration = recover_interval_duration(time_s)
    distances, betas = replay_reference_chain(model, duration)
    reference_distance_m = np.asarray(reference_distance_m, dtype=float)
    error = np.abs(distances - reference_distance_m)
    scale = np.maximum(np.abs(reference_distance_m), np.finfo(float).tiny)
    return {
        "ticks": int(duration.size),
        "duration_sum_s": float(duration.sum()),
        "duration_max_abs_deviation_from_Ts_s": float(np.max(np.abs(duration - DT))) if duration.size else 0.0,
        "distance_max_abs_error_m": float(error.max()) if error.size else 0.0,
        "distance_max_relative_error": float(np.max(error / scale)) if error.size else 0.0,
        "distances": distances,
        "betas": betas,
    }

"""Isolated loader and wrapper for the frozen physical plant snapshot."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import numpy as np


WORKTREE = Path(__file__).resolve().parents[1]
VENDOR = WORKTREE / "src" / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

physical = importlib.import_module("four_vehicle_coupled")
steering = importlib.import_module("steering_allocator")

ModelParams = physical.ModelParams
split_state = physical.split_state
rotation = physical.rotation
aggregate_diagnostics = physical.aggregate_diagnostics
connector_diagnostics = physical.connector_diagnostics


def initialize(speed_mps: float = 2.5, params: ModelParams | None = None) -> np.ndarray:
    return physical.initialize_state(params or ModelParams(), speed_mps=float(speed_mps))


def step(state: np.ndarray, controls: np.ndarray, dt: float, params: ModelParams | None = None) -> np.ndarray:
    """Advance with stable 2 ms RK4 substeps; connector forces are recomputed each stage."""
    values = np.asarray(state, dtype=float).copy()
    p = params or ModelParams()
    n_sub = max(1, int(np.ceil(float(dt) / 0.002)))
    h = float(dt) / n_sub
    for _ in range(n_sub):
        values = physical.rk4_step(values, np.asarray(controls, dtype=float), h, p)
    return values


def direct_step(state: np.ndarray, controls: np.ndarray, dt: float, params: ModelParams | None = None) -> np.ndarray:
    """One RK4 transition retained for smoke/performance diagnostics.

    The registered ablation runner uses ``step`` (2 ms substeps); this helper is
    only used by the analytic contract tests and by the optional fast probe.
    """
    p = params or ModelParams()
    return physical.rk4_step(np.asarray(state, dtype=float), np.asarray(controls, dtype=float), float(dt), p)


def allocate(
    state: np.ndarray,
    acceleration: float,
    virtual_front_deg: float,
    virtual_rear_deg: float,
    params: ModelParams | None = None,
    *,
    heading_gain: float = 2.0,
    speed_gain: float = 0.8,
) -> tuple[np.ndarray, dict]:
    cfg = steering.AllocationConfig(
        heading_gain=float(heading_gain),
        speed_gain=float(speed_gain),
        max_steering_deg=15.0,
        max_zero_sum_accel_mps2=0.8,
    )
    return steering.allocate_controls(
        np.asarray(state, dtype=float),
        float(acceleration),
        float(virtual_front_deg),
        float(virtual_rear_deg),
        params or ModelParams(),
        cfg,
    )


def output_vector(state: np.ndarray, params: ModelParams | None = None) -> np.ndarray:
    """Physical outputs used by the one-step LTV objective."""
    vehicles, payload = split_state(np.asarray(state, dtype=float))
    conn = connector_diagnostics(state, params or ModelParams())
    disp = np.asarray(conn["displacement_world_m"], dtype=float)
    return np.r_[payload[:6], vehicles[:, 2], vehicles[:, 3], disp.reshape(-1)]

"""Finite-difference linearization of the physical RK4 transition."""

from __future__ import annotations

import numpy as np

from . import plant


def linearize_step(
    state: np.ndarray,
    controls: np.ndarray,
    dt: float,
    params=None,
    eps_x: float = 1e-5,
    eps_u: float = 1e-4,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(state, dtype=float)
    u = np.asarray(controls, dtype=float)
    f0 = plant.step(x, u, dt, params)
    a = np.empty((x.size, x.size), dtype=float)
    b = np.empty((x.size, u.size), dtype=float)
    for index in range(x.size):
        delta = eps_x * max(1.0, abs(float(x[index])))
        xp = x.copy(); xm = x.copy()
        xp[index] += delta; xm[index] -= delta
        a[:, index] = (plant.step(xp, u, dt, params) - plant.step(xm, u, dt, params)) / (2.0 * delta)
    flat = u.reshape(-1)
    for index in range(flat.size):
        delta = eps_u * max(1.0, abs(float(flat[index])))
        up = flat.copy(); um = flat.copy()
        up[index] += delta; um[index] -= delta
        b[:, index] = (
            plant.step(x, up.reshape(u.shape), dt, params)
            - plant.step(x, um.reshape(u.shape), dt, params)
        ) / (2.0 * delta)
    c = f0 - a @ x - b @ flat
    return a, b, c


def output_control_jacobian(state: np.ndarray, controls: np.ndarray, dt: float, params=None, eps_u: float = 1e-4) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(state, dtype=float)
    u = np.asarray(controls, dtype=float)
    next0 = plant.step(x, u, dt, params)
    y0 = plant.output_vector(next0, params)
    jac = np.empty((y0.size, u.size), dtype=float)
    flat = u.reshape(-1)
    for index in range(flat.size):
        delta = eps_u * max(1.0, abs(float(flat[index])))
        up = flat.copy(); um = flat.copy()
        up[index] += delta; um[index] -= delta
        yp = plant.output_vector(plant.step(x, up.reshape(u.shape), dt, params), params)
        ym = plant.output_vector(plant.step(x, um.reshape(u.shape), dt, params), params)
        jac[:, index] = (yp - ym) / (2.0 * delta)
    return y0, jac

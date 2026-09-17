from __future__ import annotations
import numpy as np
from transforms import PERM, signed_permutation_matrix


def feature(x: np.ndarray, u: np.ndarray, horizon: int) -> np.ndarray:
    x = np.asarray(x, float); u = np.asarray(u, float)
    v = x[..., :24].reshape(*x.shape[:-1], 4, 6); p = x[..., 24:30]
    yaw = p[..., 2]; c, s = np.cos(yaw), np.sin(yaw)
    delta = v[..., :2] - p[..., None, :2]
    # row-world vector multiplied by body->world rotation gives payload-body coordinates
    rx = delta[..., 0] * c[..., None] + delta[..., 1] * s[..., None]
    ry = -delta[..., 0] * s[..., None] + delta[..., 1] * c[..., None]
    rel = v[..., 2] - yaw[..., None]
    vehicle = np.stack([rx, ry, np.cos(rel), np.sin(rel), v[..., 3], v[..., 4], v[..., 5]], axis=-1)
    parts = [np.ones((*x.shape[:-1], 1)), vehicle.reshape(*x.shape[:-1], 28), p[..., 3:6], x[..., 30:46], u[..., :horizon, :].reshape(*x.shape[:-1], 8 * horizon)]
    return np.concatenate(parts, axis=-1)


def mirror_matrix(horizon: int) -> np.ndarray:
    blocks: list[tuple[int, float]] = [(0, 1.)]; offset = 1
    signs7 = (1., -1., 1., -1., 1., -1., -1.)
    for new_corner, old_corner in enumerate(PERM):
        for j, sign in enumerate(signs7): blocks.append((offset + int(old_corner) * 7 + j, sign))
    offset += 28
    blocks.extend([(offset, 1.), (offset + 1, -1.), (offset + 2, -1.)]); offset += 3
    for field in range(2):
        base = offset + field * 8
        for old_corner in PERM: blocks.extend([(base + 2 * int(old_corner), 1.), (base + 2 * int(old_corner) + 1, -1.)])
    offset += 16
    for h in range(horizon):
        base = offset + 8 * h
        for old_corner in PERM: blocks.extend([(base + 2 * int(old_corner), 1.), (base + 2 * int(old_corner) + 1, -1.)])
    return signed_permutation_matrix(blocks)


def symmetric_normalizer(mean: np.ndarray, std: np.ndarray, transform: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean_eq = .5 * (mean + transform @ mean)
    std_eq = .5 * (std + np.abs(transform) @ std)
    mean_eq[0] = 0.; std_eq[0] = 1.
    return mean_eq, np.maximum(std_eq, 1e-10)

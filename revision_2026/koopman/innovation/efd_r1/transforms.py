from __future__ import annotations
import numpy as np

PERM = np.asarray([1, 0, 3, 2])


def rotate_global(x: np.ndarray, angle_rad: float) -> np.ndarray:
    """Rotate world position/yaw. Body-frame velocities and connector fields stay invariant."""
    out = np.asarray(x, float).copy(); c, s = np.cos(angle_rad), np.sin(angle_rad)
    r = np.asarray([[c, -s], [s, c]])
    vehicles = out[..., :24].reshape(*out.shape[:-1], 4, 6)
    vehicles[..., :2] = vehicles[..., :2] @ r.T
    vehicles[..., 2] += angle_rad
    payload = out[..., 24:30]
    payload[..., :2] = payload[..., :2] @ r.T
    payload[..., 2] += angle_rad
    out[..., :24] = vehicles.reshape(*out.shape[:-1], 24); out[..., 24:30] = payload
    return out


def mirror_state(x: np.ndarray) -> np.ndarray:
    out = np.asarray(x, float).copy()
    v = out[..., :24].reshape(*out.shape[:-1], 4, 6)[..., PERM, :].copy()
    v[..., 1] *= -1; v[..., 2] *= -1; v[..., 4] *= -1; v[..., 5] *= -1
    p = out[..., 24:30].copy(); p[..., 1] *= -1; p[..., 2] *= -1; p[..., 4] *= -1; p[..., 5] *= -1
    d = out[..., 30:38].reshape(*out.shape[:-1], 4, 2)[..., PERM, :].copy(); d[..., 1] *= -1
    rv = out[..., 38:46].reshape(*out.shape[:-1], 4, 2)[..., PERM, :].copy(); rv[..., 1] *= -1
    out[..., :24] = v.reshape(*out.shape[:-1], 24); out[..., 24:30] = p
    out[..., 30:38] = d.reshape(*out.shape[:-1], 8); out[..., 38:46] = rv.reshape(*out.shape[:-1], 8)
    return out


def mirror_control(u: np.ndarray) -> np.ndarray:
    out = np.asarray(u, float).reshape(*u.shape[:-1], 4, 2)[..., PERM, :].copy()
    out[..., 1] *= -1
    return out.reshape(*u.shape[:-1], 8)


def mirror_vector4(v: np.ndarray) -> np.ndarray:
    out = np.asarray(v, float)[..., PERM, :].copy(); out[..., 1] *= -1; return out


def signed_permutation_matrix(blocks: list[tuple[int, float]]) -> np.ndarray:
    """new[i] = sign * old[source] for a signed permutation description."""
    n = len(blocks); m = np.zeros((n, n))
    for i, (source, sign) in enumerate(blocks): m[i, source] = sign
    return m


def output_transform(include_velocity: bool = True) -> np.ndarray:
    one = []
    for new_corner, old_corner in enumerate(PERM):
        one.extend([(2 * int(old_corner), 1.), (2 * int(old_corner) + 1, -1.)])
    blocks = one + ([(i + 8, s) for i, s in one] if include_velocity else [])
    return signed_permutation_matrix(blocks)

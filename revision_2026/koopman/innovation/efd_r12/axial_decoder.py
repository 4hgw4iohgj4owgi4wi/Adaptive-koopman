from __future__ import annotations
import numpy as np


def decode(d: np.ndarray, v: np.ndarray, stiffness_npm: np.ndarray | float,
           damping_nspm: np.ndarray | float, free_play_m: np.ndarray | float,
           epsilon_dir_m: float = 1e-8) -> dict[str, np.ndarray]:
    d = np.asarray(d, float); v = np.asarray(v, float)
    norm = np.linalg.norm(d, axis=-1); valid = norm >= epsilon_dir_m
    n = d / np.maximum(norm[..., None], 1e-12)
    penetration = np.maximum(norm - np.asarray(free_play_m), 0.)
    normal_speed = np.sum(v * n, axis=-1)
    loading_speed = np.maximum(normal_speed, 0.)
    magnitude = np.where(penetration > 0., np.asarray(stiffness_npm) * penetration + np.asarray(damping_nspm) * loading_speed, 0.)
    magnitude = np.maximum(magnitude, 0.)
    force = magnitude[..., None] * n
    return {"force_payload": force, "force_vehicle": -force, "magnitude": magnitude,
            "direction_valid": valid, "penetration": penetration, "normal_speed": normal_speed}


def reconstruct_q(force: np.ndarray) -> np.ndarray:
    p = np.asarray(force, float)
    return np.stack([.5 * ((p[..., 0, 0] + p[..., 1, 0]) - (p[..., 2, 0] + p[..., 3, 0])),
                     .5 * ((p[..., 0, 1] + p[..., 2, 1]) - (p[..., 1, 1] + p[..., 3, 1]))], axis=-1)

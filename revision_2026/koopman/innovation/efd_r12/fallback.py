from __future__ import annotations
import numpy as np


def causal_direction(predicted_d: np.ndarray, predicted_magnitude: np.ndarray,
                     current_d: np.ndarray, point_floor: np.ndarray,
                     epsilon_dir_m: float = 1e-8) -> dict[str, np.ndarray]:
    d = np.asarray(predicted_d, float); mag = np.asarray(predicted_magnitude, float)
    norm = np.linalg.norm(d, axis=-1); valid = norm >= epsilon_dir_m
    direction = d / np.maximum(norm[..., None], 1e-12)
    current_norm = np.linalg.norm(current_d, axis=-1); current_valid = current_norm >= epsilon_dir_m
    last = current_d / np.maximum(current_norm[..., None], 1e-12)
    unresolved = np.zeros_like(valid)
    used_fallback = np.zeros_like(valid)
    for h in range(d.shape[-3]):
        use = ~valid[..., h, :]; used_fallback[..., h, :] = use
        can = use & current_valid
        direction[..., h, :, :] = np.where(can[..., None], last, direction[..., h, :, :])
        unresolved[..., h, :] = use & ~current_valid & (mag[..., h, :] >= point_floor)
        accepted = valid[..., h, :] | can
        last = np.where(accepted[..., None], direction[..., h, :, :], last)
        current_valid = current_valid | accepted
    active = mag >= point_floor
    return {"direction": direction, "fallback": used_fallback, "predicted_active": active,
            "unresolved_active": unresolved}

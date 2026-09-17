from __future__ import annotations

"""R3 analytic physical readout shared by every method.

``R3Decoder`` reconstructs the four connector point forces and the complete
internal force vector from predicted relative connector displacement/velocity
using the frozen connector law and the frozen planar grasp projector ``W``.
The math is a faithful re-implementation of the frozen N6
``evaluation.connector_outputs`` so that every method shares one readout and
the P0 element-wise regression against N6 holds.

The ``W`` projector is built from the frozen N6 ``internal_force`` module
(read-only dependency); the force law constants come from the frozen resolved
parameters of each trajectory (``params.connector.*``).
"""

import numpy as np


class R3Decoder:
    def __init__(self, build_planar_grasp_matrix):
        self._build_grasp = build_planar_grasp_matrix

    def connector_force(
        self,
        relative_state47: np.ndarray,
        params: object,
        law: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (force8, internal8) for one or many 47-dim relative states.

        Operation order mirrors the frozen N6 evaluation exactly:
        g3 = columns 31:47 -> (n, 4, 4); displacement = [:, :, :2];
        velocity = [:, :, 2:]; distance = norm(displacement, axis=2);
        normal = displacement / max(distance, 1e-12);
        penetration = max(distance - free_play, 0);
        normal_speed = sum(velocity * normal, axis=2);
        V1 weight = (penetration > 0); R3 weight = smoothstep over
        smoothing_width_m with the frozen piecewise formula;
        magnitude = stiffness * penetration + damping * weight * max(normal_speed, 0);
        force = magnitude[..., None] * normal; internal = force @ (I - pinv(W) W).T.
        """
        relative = np.asarray(relative_state47, dtype=float)
        values = relative.reshape(1, -1) if relative.ndim == 1 else relative
        g3 = values[:, 31:47].reshape(-1, 4, 4)
        displacement = g3[:, :, :2]
        velocity = g3[:, :, 2:]
        distance = np.linalg.norm(displacement, axis=2)
        normal = displacement / np.maximum(distance[:, :, None], 1.0e-12)
        penetration = np.maximum(distance - float(params.connector.free_play_m), 0.0)
        normal_speed = np.sum(velocity * normal, axis=2)
        if str(law).upper() == "V1":
            weight = (penetration > 0.0).astype(float)
        elif str(law).upper() == "R3":
            ratio = np.clip(
                penetration / float(params.connector.smoothing_width_m), 0.0, 1.0
            )
            weight = np.where(
                penetration <= 0.0,
                0.0,
                np.where(
                    penetration >= float(params.connector.smoothing_width_m),
                    1.0,
                    3 * ratio**2 - 2 * ratio**3,
                ),
            )
        else:
            raise ValueError(law)
        magnitude = (
            float(params.connector.stiffness_npm) * penetration
            + float(params.connector.damping_nspm)
            * weight
            * np.maximum(normal_speed, 0.0)
        )
        force = magnitude[:, :, None] * normal
        grasp = self._build_grasp(np.asarray(params.payload_anchor_body_m, dtype=float))
        projector = np.eye(8) - np.linalg.pinv(grasp) @ grasp
        force8 = force.reshape(-1, 8)
        internal8 = force8 @ projector.T
        if relative.ndim == 1:
            return force8[0], internal8[0]
        return force8, internal8

    def internal_force(self, force8: np.ndarray, params: object) -> np.ndarray:
        """Complete internal force vector via the frozen W null-space projector."""
        grasp = self._build_grasp(np.asarray(params.payload_anchor_body_m, dtype=float))
        projector = np.eye(8) - np.linalg.pinv(grasp) @ grasp
        force = np.asarray(force8, dtype=float)
        return force @ projector.T

    def null_space_residual(self, force8: np.ndarray, params: object) -> float:
        """Relative W @ f_int residual used by the P6 physical-consistency gate."""
        grasp = self._build_grasp(np.asarray(params.payload_anchor_body_m, dtype=float))
        internal = self.internal_force(force8, params)
        scale = max(float(np.max(np.abs(internal))) if internal.size else 1.0, 1.0)
        return float(np.max(np.abs(grasp @ internal.T))) / scale

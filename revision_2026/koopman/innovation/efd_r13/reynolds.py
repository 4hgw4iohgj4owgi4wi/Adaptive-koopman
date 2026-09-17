from __future__ import annotations
import numpy as np


def project_linear_map(w: np.ndarray, rphi: np.ndarray, ry: np.ndarray) -> np.ndarray:
    """Project row-regression W (y_row=phi_row@W) onto mirror-equivariant maps."""
    return .5 * (w + rphi.T @ w @ ry.T)


def commutator(w: np.ndarray, rphi: np.ndarray, ry: np.ndarray) -> float:
    # Column form is W.T Rphi = Ry W.T.
    return float(np.max(np.abs(w.T @ rphi - ry @ w.T)))

"""P5 (deferred): small-dimension stable residual lift.

Not authorized in the first P0-P3 round (koopman_path.md section 12).  The
final structure keeps the full physical state passing through and adds a
small-dimension residual observable:

    z_k = [x_k; phi_theta(g(rho_k) .* x_k, rho_k)],   xhat_k = C z_k,  C = [I 0]

Only L16 (16-dim) and L32 (32-dim) residual observables are candidates; the
old 96-dim end-to-end lift is not rerun.  Warm-start from the S0 matrices,
freeze the physical block, train phi + readout one-step, then unfreeze and
optimize the 1/5/10/20-step loss with weights (0.10, 0.20, 0.25, 0.45).
"""

from __future__ import annotations


class ResidualLift16:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "P5 residual lift is outside the first authorization (P0-P3 only). "
            "See koopman_path.md section 12."
        )


class ResidualLift32:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "P5 residual lift is outside the first authorization (P0-P3 only). "
            "See koopman_path.md section 12."
        )

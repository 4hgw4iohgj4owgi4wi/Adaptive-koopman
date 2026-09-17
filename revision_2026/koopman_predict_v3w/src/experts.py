"""P4/P5 (deferred): shared backbone with three low-rank residual experts.

Not authorized in the first P0-P3 round.  Only used after P2's oracle gate
passes (P4) and/or P5 is authorized:

    z_{k+1} = sum_m alpha_m(rho_k) [(A0 + U_m V_m^T) z_k + (B0 + R_m S_m^T) u_k],
    alpha_m >= 0, sum_m alpha_m = 1

E0 steady / weak excitation, E1 steering-curvature-switch transients,
E2 connector events and internal-force null space.  No future scenario id,
window label, future measured steering or in-horizon future event may enter
the gate variable rho_k.
"""

from __future__ import annotations


class SharedResidualExperts:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "shared residual experts are outside the first authorization (P0-P3 only)."
        )

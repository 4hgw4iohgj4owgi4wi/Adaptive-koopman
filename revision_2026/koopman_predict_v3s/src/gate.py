"""P4 (deferred): causal gate and variable-group gate.

Not authorized in the first P0-P3 round; P4 runs only if P2's oracle gate
passes.  Gate variable rho_k may only use t_k and earlier:

    rho_k = [v_x, |a_req|, |delta_req|, |Delta_delta_req|, ||d_conn||,
             ||v_conn||, ||f_int,k||, c_k]

A3 steering tracking error joins only in a separate P4 ablation.  Gate loss:

    L_gate = L_pred + lambda_s sum_k ||alpha_k - alpha_{k-1}||^2
             + lambda_e L_occupancy
"""

from __future__ import annotations


class CausalGate:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "causal gate is outside the first authorization (P0-P3 only)."
        )


class GroupGate:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "variable-group gate is outside the first authorization (P0-P3 only)."
        )

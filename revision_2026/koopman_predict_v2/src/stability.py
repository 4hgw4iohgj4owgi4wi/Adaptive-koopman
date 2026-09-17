"""P7 (deferred): stability certificate and IRSP necessity.

Not authorized in the first P0-P3 round.  For gated experts check the common
quadratic certificate A_m^T P A_m - P <= -eps I (P > 0, m = 1..3) and, with
bounded controls, the discrete ISS form.  If P3 retains the bilinear term:

    A(u) = A + sum_{j=1}^7 u_j N_j

the continuous input-box certificate must cover all 2^7 = 128 vertices and
validate interior random points; spectral radius on training controls only is
not a certificate.
"""

from __future__ import annotations


def common_lyapunov(*args, **kwargs):
    raise NotImplementedError(
        "stability certificates are outside the first authorization (P0-P3 only)."
    )


def verify_input_box(*args, **kwargs):
    raise NotImplementedError(
        "input-box certificates are outside the first authorization (P0-P3 only)."
    )

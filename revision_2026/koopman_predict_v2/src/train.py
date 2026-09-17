"""P5 (deferred): multi-horizon training loop.

Not authorized in the first P0-P3 round.  Training order:

1. initialize the physical block from the S0 matrices;
2. freeze the physical block, warm-start phi + readout one-step;
3. unfreeze allowed residual blocks and optimize the 1/5/10/20-step loss
   with weights (0.10, 0.20, 0.25, 0.45);
4. validation selects L16 or L32 exactly once;
5. all five primary seeds must finish before judgement.

OOM handling is restricted to micro-batch reduction with gradient
accumulation: effective batch, optimization steps and seeds must not change.
"""

from __future__ import annotations


def warm_start(*args, **kwargs):
    raise NotImplementedError(
        "multi-horizon training is outside the first authorization (P0-P3 only)."
    )


def train_multihorizon(*args, **kwargs):
    raise NotImplementedError(
        "multi-horizon training is outside the first authorization (P0-P3 only)."
    )

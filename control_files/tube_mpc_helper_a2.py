import numpy as np


class TubeMpcHelperA2:
    """A2-specific tube-style tightening and ancillary feedback helper."""

    def __init__(
        self,
        disturbance_bound,
        tighten_scale=1.35,
        input_tighten_scale=0.40,
        ancillary_gain=None,
    ):
        self.disturbance_bound = np.asarray(disturbance_bound, dtype=float).reshape(-1)
        self.tighten_scale = float(tighten_scale)
        self.input_tighten_scale = float(input_tighten_scale)

        if ancillary_gain is None:
            ancillary_gain = np.array(
                [
                    [0.00, -1.35, -2.40, 0.00, -0.45, -0.70],
                    [0.00, 0.00, 0.00, -0.90, 0.00, 0.00],
                ],
                dtype=float,
            )
        self.ancillary_gain = np.asarray(ancillary_gain, dtype=float)

    @classmethod
    def from_prediction_errors(
        cls,
        pred_error,
        *,
        tighten_scale=1.35,
        input_tighten_scale=0.40,
        ancillary_gain=None,
        quantile=0.985,
        margin=0.015,
    ):
        err = np.asarray(pred_error, dtype=float)
        if err.ndim != 2:
            raise ValueError("pred_error must have shape (num_samples, num_states)")
        bound = np.quantile(np.abs(err), quantile, axis=0) + float(margin)
        return cls(
            disturbance_bound=bound,
            tighten_scale=tighten_scale,
            input_tighten_scale=input_tighten_scale,
            ancillary_gain=ancillary_gain,
        )

    def state_margin(self):
        return self.tighten_scale * self.disturbance_bound

    def tighten_state_bounds(self, xmin, xmax):
        xmin = np.asarray(xmin, dtype=float).copy()
        xmax = np.asarray(xmax, dtype=float).copy()
        margin = self.state_margin()
        n = min(xmin.size, margin.size)

        # Keep the path-progress state mostly free; tighten the lateral-dynamic states.
        idx = [1, 2, 3, 4, 5]
        for i in idx:
            if i < n:
                local_margin = min(margin[i], 0.20 * max(xmax[i] - xmin[i], 1e-6))
                xmin[i] += local_margin
                xmax[i] -= local_margin
                if xmin[i] > xmax[i]:
                    mid = 0.5 * (xmin[i] + xmax[i])
                    xmin[i] = mid - 1e-3
                    xmax[i] = mid + 1e-3
        return xmin, xmax

    def tighten_input_bounds(self, umin, umax):
        umin = np.asarray(umin, dtype=float).copy()
        umax = np.asarray(umax, dtype=float).copy()
        if umin.size != umax.size:
            raise ValueError("umin and umax must have the same size")
        span = np.maximum(umax - umin, 1e-6)
        margin = self.input_tighten_scale * np.array([0.06 * span[0], 0.08 * span[1]], dtype=float)
        umin += margin
        umax -= margin
        return umin, umax

    def ancillary_control(self, x_now, x_ref):
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
        if x_now.size != self.ancillary_gain.shape[1]:
            raise ValueError("x_now dimension does not match ancillary gain")
        err = x_now - x_ref
        return self.ancillary_gain @ err

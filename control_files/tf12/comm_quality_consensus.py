import numpy as np


class CommAwareConsensusTF12:
    """Communication-quality-aware consensus + delay compensation helper.

    Design goals:
    - Map packet-loss / delay quality into adaptive consensus strength.
    - Provide delayed-state prediction for cooperative correction.
    - Tighten team-level actuator bounds under poor communication.
    - Offer graceful degraded fallback to keep closed-loop stable.
    """

    def __init__(
        self,
        *,
        num_vehicles,
        dt,
        seed=2026,
        packet_loss_base=0.03,
        packet_loss_gain=0.20,
        delay_steps_max=3,
        delay_bias=0.35,
        quality_smooth_beta=0.80,
        quality_tau_steps=3.0,
        consensus_blend_min=0.10,
        consensus_blend_max=0.70,
        tighten_max_frac=0.26,
        degrade_threshold=0.45,
        degrade_delta_scale=0.60,
    ):
        self.num_vehicles = int(num_vehicles)
        self.dt = float(dt)
        self.rng = np.random.default_rng(int(seed))

        self.packet_loss_base = float(packet_loss_base)
        self.packet_loss_gain = float(packet_loss_gain)
        self.delay_steps_max = int(max(0, delay_steps_max))
        self.delay_bias = float(delay_bias)
        self.quality_smooth_beta = float(np.clip(quality_smooth_beta, 0.0, 0.999))
        self.quality_tau_steps = float(max(1e-3, quality_tau_steps))
        self.consensus_blend_min = float(np.clip(consensus_blend_min, 0.0, 1.0))
        self.consensus_blend_max = float(np.clip(consensus_blend_max, self.consensus_blend_min, 1.0))
        self.tighten_max_frac = float(np.clip(tighten_max_frac, 0.0, 0.75))
        self.degrade_threshold = float(np.clip(degrade_threshold, 1e-3, 1.0))
        self.degrade_delta_scale = float(np.clip(degrade_delta_scale, 0.0, 1.0))

        self.quality = np.ones((self.num_vehicles, self.num_vehicles), dtype=float)
        self.delay_steps = np.zeros((self.num_vehicles, self.num_vehicles), dtype=int)
        self.packet_ok = np.ones((self.num_vehicles, self.num_vehicles), dtype=bool)
        np.fill_diagonal(self.quality, 1.0)

        self.state_buffers = [[] for _ in range(self.num_vehicles)]
        self.last_diag = {
            "quality_global": 1.0,
            "mean_delay_steps": 0.0,
            "loss_ratio": 0.0,
        }

    def push_states(self, step_idx, local_states):
        arr = np.asarray(local_states, dtype=float)
        if arr.ndim != 2 or arr.shape[0] != self.num_vehicles:
            raise ValueError(
                f"local_states must have shape ({self.num_vehicles}, n_state), got {arr.shape}"
            )
        k = int(step_idx)
        for v in range(self.num_vehicles):
            st = np.asarray(arr[v], dtype=float).reshape(-1)
            self.state_buffers[v].append((k, st.copy()))
            if len(self.state_buffers[v]) > 300:
                self.state_buffers[v] = self.state_buffers[v][-300:]

    @staticmethod
    def _clip01(x):
        return float(np.clip(x, 0.0, 1.0))

    def _offdiag_mask(self):
        m = np.ones((self.num_vehicles, self.num_vehicles), dtype=bool)
        np.fill_diagonal(m, False)
        return m

    def _global_quality(self):
        mask = self._offdiag_mask()
        vals = self.quality[mask]
        if vals.size == 0:
            return 1.0
        return float(np.mean(vals))

    def _global_delay(self):
        mask = self._offdiag_mask()
        vals = self.delay_steps[mask]
        if vals.size == 0:
            return 0.0
        return float(np.mean(vals))

    def _loss_ratio(self):
        mask = self._offdiag_mask()
        vals = self.packet_ok[mask]
        if vals.size == 0:
            return 0.0
        return float(np.mean(~vals))

    def update_channel(self, step_idx, team_state=None, control_spread=None):
        """Sample packet/drop/delay and update smoothed reliability matrix."""
        _ = int(step_idx)
        if team_state is None:
            dyn = 0.0
        else:
            x = np.asarray(team_state, dtype=float).reshape(-1)
            dyn = min(1.0, 0.45 * abs(x[5]) + 0.18 * abs(x[4]) + 0.15 * abs(x[2]))
        if control_spread is None:
            spread_dyn = 0.0
        else:
            spread_dyn = min(
                1.0,
                0.25 * abs(float(control_spread.get("delta_spread", 0.0)))
                + 0.40 * abs(float(control_spread.get("ax_spread", 0.0))),
            )

        load = self._clip01(dyn + spread_dyn)
        p_loss = self._clip01(self.packet_loss_base + self.packet_loss_gain * load)

        for i in range(self.num_vehicles):
            for j in range(self.num_vehicles):
                if i == j:
                    self.packet_ok[i, j] = True
                    self.delay_steps[i, j] = 0
                    self.quality[i, j] = 1.0
                    continue

                ok = bool(self.rng.random() > p_loss)
                self.packet_ok[i, j] = ok

                if self.delay_steps_max <= 0:
                    d = 0
                else:
                    # Larger load -> more high-delay samples.
                    bias = float(np.clip(self.delay_bias + 0.45 * load, 0.0, 1.0))
                    if self.rng.random() < bias:
                        d = int(self.rng.integers(1, self.delay_steps_max + 1))
                    else:
                        d = 0
                self.delay_steps[i, j] = d

                q_inst = np.exp(-float(d) / self.quality_tau_steps)
                if not ok:
                    q_inst *= 0.10
                q_prev = float(self.quality[i, j])
                q_new = self.quality_smooth_beta * q_prev + (1.0 - self.quality_smooth_beta) * q_inst
                self.quality[i, j] = self._clip01(q_new)

        self.last_diag = {
            "quality_global": self._global_quality(),
            "mean_delay_steps": self._global_delay(),
            "loss_ratio": self._loss_ratio(),
        }
        return dict(self.last_diag)

    def _predict_forward(self, x_raw, steps):
        x = np.asarray(x_raw, dtype=float).reshape(-1).copy()
        n = int(max(0, steps))
        if x.shape[0] < 6 or n == 0:
            return x
        dt_n = float(n) * self.dt
        x[0] = x[0] + x[3] * dt_n
        x[1] = x[1] + x[4] * dt_n
        x[2] = x[2] + x[5] * dt_n
        return x

    def _get_state_at_or_before(self, sender, step_idx):
        buf = self.state_buffers[int(sender)]
        if len(buf) == 0:
            return None, None
        target = int(step_idx)
        for k, st in reversed(buf):
            if k <= target:
                return int(k), st.copy()
        k0, s0 = buf[0]
        return int(k0), s0.copy()

    def get_predicted_remote_state(self, receiver, sender, current_step, fallback_state):
        """Return delayed-then-predicted sender state as received by receiver."""
        i = int(sender)
        j = int(receiver)
        k = int(current_step)
        d = int(max(0, self.delay_steps[i, j]))
        k_delayed = k - d
        k_avail, st = self._get_state_at_or_before(i, k_delayed)
        if st is None:
            return np.asarray(fallback_state, dtype=float).reshape(-1).copy()
        pred_steps = max(0, k - int(k_avail))
        return self._predict_forward(st, pred_steps)

    def _incoming_quality(self):
        if self.num_vehicles <= 1:
            return np.ones((self.num_vehicles,), dtype=float)
        q_in = np.zeros((self.num_vehicles,), dtype=float)
        for v in range(self.num_vehicles):
            mask = np.ones((self.num_vehicles,), dtype=bool)
            mask[v] = False
            q_in[v] = float(np.mean(self.quality[mask, v]))
        return np.clip(q_in, 0.0, 1.0)

    def project_vehicle_commands(self, desired_u_stack, prev_team_u=None):
        """Communication-aware consensus projection on per-vehicle commands."""
        u = np.asarray(desired_u_stack, dtype=float)
        if u.ndim != 2 or u.shape[0] != self.num_vehicles or u.shape[1] != 2:
            raise ValueError("desired_u_stack must have shape (num_vehicles, 2)")

        q_in = self._incoming_quality()
        w = q_in + 1e-3
        u_weighted = np.sum(u * w[:, None], axis=0) / np.sum(w)
        if prev_team_u is not None:
            pu = np.asarray(prev_team_u, dtype=float).reshape(-1)
            if pu.shape[0] == 2:
                # Softly stabilize aggregate command.
                u_weighted = 0.15 * pu + 0.85 * u_weighted

        blend = self.consensus_blend_min + (1.0 - q_in) * (
            self.consensus_blend_max - self.consensus_blend_min
        )
        blend = np.clip(blend, self.consensus_blend_min, self.consensus_blend_max)

        u_proj = np.zeros_like(u)
        for v in range(self.num_vehicles):
            u_proj[v, :] = (1.0 - blend[v]) * u[v, :] + blend[v] * u_weighted

        diag = {
            "quality_in_min": float(np.min(q_in)),
            "quality_in_mean": float(np.mean(q_in)),
            "quality_in_max": float(np.max(q_in)),
            "blend_mean": float(np.mean(blend)),
            "blend_max": float(np.max(blend)),
            "quality_global": float(self.last_diag.get("quality_global", self._global_quality())),
            "mean_delay_steps": float(self.last_diag.get("mean_delay_steps", self._global_delay())),
            "loss_ratio": float(self.last_diag.get("loss_ratio", self._loss_ratio())),
        }
        return u_proj, diag

    def tightened_bounds(self, umin, umax):
        umin = np.asarray(umin, dtype=float).reshape(-1)
        umax = np.asarray(umax, dtype=float).reshape(-1)
        qg = float(self.last_diag.get("quality_global", self._global_quality()))
        frac = self.tighten_max_frac * (1.0 - qg)
        frac = float(np.clip(frac, 0.0, self.tighten_max_frac))
        c = 0.5 * (umin + umax)
        h = 0.5 * (umax - umin)
        h_t = np.maximum((1.0 - frac) * h, 1e-6)
        umin_t = c - h_t
        umax_t = c + h_t
        return umin_t, umax_t, {"tighten_frac": frac, "quality_global": qg}

    def apply_degraded_fallback(self, u_team, team_state, team_ref, umin_eff, umax_eff):
        u = np.asarray(u_team, dtype=float).reshape(-1).copy()
        x = np.asarray(team_state, dtype=float).reshape(-1)
        xr = np.asarray(team_ref, dtype=float).reshape(-1)
        umin_eff = np.asarray(umin_eff, dtype=float).reshape(-1)
        umax_eff = np.asarray(umax_eff, dtype=float).reshape(-1)

        qg = float(self.last_diag.get("quality_global", self._global_quality()))
        loss_ratio = float(self.last_diag.get("loss_ratio", self._loss_ratio()))
        degrade_score = max(
            (self.degrade_threshold - qg) / self.degrade_threshold,
            (loss_ratio - 0.30) / 0.70,
        )
        mix = float(np.clip(degrade_score, 0.0, 1.0))

        if mix <= 1e-8:
            return u, {"degrade_mix": 0.0, "quality_global": qg, "loss_ratio": loss_ratio}

        lag_s = float(np.clip(xr[0] - x[0], 0.0, 8.0))
        delta_safe = -0.85 * x[1] - 1.35 * x[2] - 0.45 * x[5]
        ax_safe = 0.22 * lag_s - 0.10 * abs(x[4]) - 0.10 * abs(x[5])
        ax_safe = max(ax_safe, -0.15)
        u_safe = np.array([delta_safe, ax_safe], dtype=float)
        u_mix = (1.0 - mix) * u + mix * u_safe

        # Reduce steering aggressiveness in deep degraded mode.
        steer_center = 0.5 * (umin_eff[0] + umax_eff[0])
        u_mix[0] = steer_center + self.degrade_delta_scale * (u_mix[0] - steer_center)
        u_mix[0] = np.clip(u_mix[0], umin_eff[0], umax_eff[0])
        u_mix[1] = np.clip(u_mix[1], umin_eff[1], umax_eff[1])

        return u_mix, {
            "degrade_mix": mix,
            "quality_global": qg,
            "loss_ratio": loss_ratio,
            "lag_s": lag_s,
        }

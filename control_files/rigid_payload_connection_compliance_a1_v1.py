import numpy as np


class RigidPayloadConnectionComplianceA1V1:
    """A1 compliant connector model (small relative displacement + yaw).

    The team state remains the payload-center state, while each corner vehicle can
    have tiny relative pose offsets w.r.t. rigid corners:
      - longitudinal offset ds
      - lateral offset dey
      - relative yaw dpsi
    plus their rates. This avoids overly-hard rigid locking.
    """

    def __init__(
        self,
        *,
        dt,
        num_vehicles=4,
        enabled=True,
        max_rel_s=0.07,
        max_rel_ey=0.07,
        max_rel_psi=0.035,
        max_rel_vs=0.32,
        max_rel_vey=0.32,
        max_rel_r=0.22,
        k_s=5.6,
        c_s=3.8,
        k_ey=6.6,
        c_ey=4.2,
        k_psi=5.0,
        c_psi=3.4,
        gain_ax=0.20,
        gain_delta_ey=0.58,
        gain_delta_psi=0.36,
        gain_r_psi=0.08,
    ):
        self.dt = float(dt)
        self.num_vehicles = int(num_vehicles)
        self.enabled = bool(enabled)

        self.max_rel = np.array(
            [float(max_rel_s), float(max_rel_ey), float(max_rel_psi)], dtype=float
        )
        self.max_rel_rate = np.array(
            [float(max_rel_vs), float(max_rel_vey), float(max_rel_r)], dtype=float
        )

        self.k = np.array([float(k_s), float(k_ey), float(k_psi)], dtype=float)
        self.c = np.array([float(c_s), float(c_ey), float(c_psi)], dtype=float)

        self.gain_ax = float(gain_ax)
        self.gain_delta_ey = float(gain_delta_ey)
        self.gain_delta_psi = float(gain_delta_psi)
        self.gain_r_psi = float(gain_r_psi)

        self.rel = np.zeros((self.num_vehicles, 3), dtype=float)
        self.rel_rate = np.zeros((self.num_vehicles, 3), dtype=float)

    @staticmethod
    def _wrap_angle(a):
        return (a + np.pi) % (2.0 * np.pi) - np.pi

    def reset(self):
        self.rel.fill(0.0)
        self.rel_rate.fill(0.0)

    def _clip_state(self):
        self.rel = np.clip(self.rel, -self.max_rel[None, :], self.max_rel[None, :])
        self.rel_rate = np.clip(
            self.rel_rate, -self.max_rel_rate[None, :], self.max_rel_rate[None, :]
        )
        self.rel[:, 2] = np.vectorize(self._wrap_angle)(self.rel[:, 2])

    def _zero_mean_constraint(self):
        # Team state is payload center; keep relative offsets zero-mean.
        self.rel -= np.mean(self.rel, axis=0, keepdims=True)
        self.rel_rate -= np.mean(self.rel_rate, axis=0, keepdims=True)

    def update(
        self,
        *,
        desired_u_stack,
        u_team,
        team_state,
        team_ref=None,
        dt=None,
    ):
        if not self.enabled:
            return {
                "enabled": False,
                "max_abs_ds": 0.0,
                "max_abs_dey": 0.0,
                "max_abs_dpsi": 0.0,
                "rms_rel": 0.0,
            }

        dt_use = self.dt if dt is None else float(dt)
        u_des = np.asarray(desired_u_stack, dtype=float)
        u_team = np.asarray(u_team, dtype=float).reshape(-1)
        x_team = np.asarray(team_state, dtype=float).reshape(-1)
        if u_des.ndim != 2 or u_des.shape[1] != 2:
            raise ValueError("desired_u_stack must have shape (n_vehicle, 2)")

        lag_scale = 1.0
        if team_ref is not None:
            x_ref = np.asarray(team_ref, dtype=float).reshape(-1)
            lag_s = float(np.clip(x_ref[0] - x_team[0], 0.0, 8.0))
            lag_scale = 1.0 + 0.03 * lag_s

        for v in range(min(self.num_vehicles, u_des.shape[0])):
            du_delta = float(u_des[v, 0] - u_team[0])
            du_ax = float(u_des[v, 1] - u_team[1])

            # Excitation due to per-vehicle command differences.
            excite = np.array(
                [
                    self.gain_ax * du_ax,
                    self.gain_delta_ey * du_delta,
                    self.gain_delta_psi * du_delta + self.gain_r_psi * float(x_team[5]),
                ],
                dtype=float,
            ) * lag_scale

            rel_acc = excite - self.k * self.rel[v, :] - self.c * self.rel_rate[v, :]
            self.rel_rate[v, :] += dt_use * rel_acc
            self.rel[v, :] += dt_use * self.rel_rate[v, :]

        self._zero_mean_constraint()
        self._clip_state()

        return {
            "enabled": True,
            "max_abs_ds": float(np.max(np.abs(self.rel[:, 0]))),
            "max_abs_dey": float(np.max(np.abs(self.rel[:, 1]))),
            "max_abs_dpsi": float(np.max(np.abs(self.rel[:, 2]))),
            "rms_rel": float(np.sqrt(np.mean(self.rel ** 2))),
        }

    def corner_states_from_team(self, team_state, payload_module, payload_cfg):
        base_states = payload_module.team_to_corner_states(team_state, payload_cfg=payload_cfg)
        out = []
        for v in range(min(self.num_vehicles, len(base_states))):
            x = np.asarray(base_states[v], dtype=float).copy()
            x[0] += self.rel[v, 0]
            x[1] += self.rel[v, 1]
            x[2] = self._wrap_angle(float(x[2] + self.rel[v, 2]))
            x[3] += self.rel_rate[v, 0]
            x[4] += self.rel_rate[v, 1]
            x[5] += self.rel_rate[v, 2]
            out.append(x)
        return out


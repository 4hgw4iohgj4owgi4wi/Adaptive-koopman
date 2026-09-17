import copy

import numpy as np


class HybridRigidPayloadDynamicsA2:
    """A2 hybrid model: prior rigid-payload dynamics + lifted residual correction."""

    def __init__(
        self,
        *,
        payload_module,
        nominal_pars,
        residual_model,
        koopman_model=None,
        koopman_blend=0.0,
        clip_fn=None,
        eps_fd=1e-4,
    ):
        self.payload_module = payload_module
        self.nominal_pars = copy.deepcopy(nominal_pars)
        self.base_nominal_pars = copy.deepcopy(nominal_pars)
        self.residual_model = copy.deepcopy(residual_model)
        self.koopman_model = copy.deepcopy(koopman_model) if koopman_model is not None else None
        self.koopman_blend = float(np.clip(koopman_blend, 0.0, 1.0))
        self.clip_fn = clip_fn
        self.eps_fd = float(eps_fd)

        self.C = np.eye(6, dtype=float)
        self.nz = 6
        self.nx = 6
        self.m = 2

    @staticmethod
    def lift_state(x):
        x = np.asarray(x, dtype=float).reshape(-1)
        s, ey, epsi, vx, vy, r = x
        return np.array(
            [
                s,
                ey,
                epsi,
                vx,
                vy,
                r,
                ey * ey,
                epsi * epsi,
                vy * vy,
                r * r,
                ey * epsi,
                vy * r,
                vx * epsi,
                1.0,
            ],
            dtype=float,
        )

    def set_cornering_stiffness_scale(self, front_scale=1.0, rear_scale=1.0):
        self.nominal_pars["Cf"] = float(self.base_nominal_pars["Cf"]) * float(front_scale)
        self.nominal_pars["Cr"] = float(self.base_nominal_pars["Cr"]) * float(rear_scale)

    def set_koopman_blend(self, blend):
        self.koopman_blend = float(np.clip(blend, 0.0, 1.0))

    def update_koopman_model(self, koopman_model):
        if koopman_model is None:
            self.koopman_model = None
            return
        self.koopman_model = copy.deepcopy(koopman_model)

    def nominal_step(self, x, u):
        return np.asarray(
            self.payload_module.FK_solver(
                x,
                u,
                self.nominal_pars,
                sensor_noise=False,
                SNR_DB=0,
                i=0,
            ),
            dtype=float,
        )

    def residual_step(self, x, u):
        x = np.asarray(x, dtype=float).reshape(-1)
        u = np.asarray(u, dtype=float).reshape(-1)
        feat = self.lift_state(x)

        feat_mu = np.asarray(self.residual_model.get("feat_mu", np.zeros_like(feat)), dtype=float)
        feat_scale = np.asarray(self.residual_model.get("feat_scale", np.ones_like(feat)), dtype=float)
        u_mu = np.asarray(self.residual_model.get("u_mu", np.zeros_like(u)), dtype=float)
        u_scale = np.asarray(self.residual_model.get("u_scale", np.ones_like(u)), dtype=float)

        feat_n = (feat - feat_mu) / np.maximum(feat_scale, 1e-6)
        u_n = (u - u_mu) / np.maximum(u_scale, 1e-6)
        reg = np.concatenate((feat_n, u_n, np.array([1.0], dtype=float)))
        w = np.asarray(self.residual_model["W"], dtype=float)
        dx = w @ reg

        clip_bound = np.asarray(self.residual_model.get("clip_bound", np.full(self.nx, 0.35)), dtype=float)
        dx = np.clip(dx, -clip_bound, clip_bound)
        blend = float(self.residual_model.get("blend", 1.0))
        return blend * dx

    def koopman_step(self, x, u):
        if self.koopman_model is None:
            return np.asarray(x, dtype=float).reshape(-1)
        x = np.asarray(x, dtype=float).reshape(-1)
        u = np.asarray(u, dtype=float).reshape(-1)

        feat = self.lift_state(x)
        feat_mu = np.asarray(self.koopman_model.get("feat_mu", np.zeros_like(feat)), dtype=float)
        feat_scale = np.asarray(self.koopman_model.get("feat_scale", np.ones_like(feat)), dtype=float)
        u_mu = np.asarray(self.koopman_model.get("u_mu", np.zeros_like(u)), dtype=float)
        u_scale = np.asarray(self.koopman_model.get("u_scale", np.ones_like(u)), dtype=float)

        feat_n = (feat - feat_mu) / np.maximum(feat_scale, 1e-6)
        u_n = (u - u_mu) / np.maximum(u_scale, 1e-6)
        reg = np.concatenate((feat_n, u_n, np.array([1.0], dtype=float)))
        k = np.asarray(self.koopman_model["K"], dtype=float)
        dx = k @ reg
        x_next = x + dx
        clip_bound = np.asarray(
            self.koopman_model.get("clip_bound", np.full(self.nx, 0.55)),
            dtype=float,
        )
        x_next = np.clip(x_next, x - clip_bound, x + clip_bound)
        return x_next

    def eval_dot(self, z, u, t=None):
        x = np.asarray(z, dtype=float).reshape(-1)
        u = np.asarray(u, dtype=float).reshape(-1)
        x_hybrid = self.nominal_step(x, u) + self.residual_step(x, u)
        if self.koopman_model is not None and self.koopman_blend > 1e-8:
            x_koop = self.koopman_step(x, u)
            x_next = (1.0 - self.koopman_blend) * x_hybrid + self.koopman_blend * x_koop
        else:
            x_next = x_hybrid
        if self.clip_fn is not None:
            x_next = np.asarray(self.clip_fn(x_next), dtype=float)
        return x_next

    def get_linearization(self, z0, z1, u):
        z0 = np.asarray(z0, dtype=float).reshape(-1)
        z1 = np.asarray(z1, dtype=float).reshape(-1)
        u = np.asarray(u, dtype=float).reshape(-1)

        f0 = self.eval_dot(z0, u)
        a_lin = np.zeros((self.nz, self.nz), dtype=float)
        b_lin = np.zeros((self.nz, self.m), dtype=float)

        for i in range(self.nz):
            dz = np.zeros(self.nz, dtype=float)
            dz[i] = self.eps_fd
            fp = self.eval_dot(z0 + dz, u)
            fm = self.eval_dot(z0 - dz, u)
            a_lin[:, i] = (fp - fm) / (2.0 * self.eps_fd)

        for j in range(self.m):
            du = np.zeros(self.m, dtype=float)
            du[j] = self.eps_fd
            fp = self.eval_dot(z0, u + du)
            fm = self.eval_dot(z0, u - du)
            b_lin[:, j] = (fp - fm) / (2.0 * self.eps_fd)

        r_lin = f0 - z1
        return a_lin, b_lin, r_lin

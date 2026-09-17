import numpy as np

from dynamics.sync_pendulum import FK_solver


def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    """
    Generate nominal and changed trajectories for single-vehicle path tracking.

    Returns
    -------
    X_1 : nominal trajectories, shape (num_traj, num_snaps, n)
    X_2 : changed trajectories, shape (num_traj, num_snaps, n)
    U   : control inputs, shape (num_traj, num_snaps-1, m)
    """
    n = pars['num_states']
    m = pars['num_inputs']
    dt = pars['dt']

    delta_max = pars.get('delta_max', 0.08)
    ax_max = pars.get('ax_max', 2.0)

    X_1 = np.zeros((num_traj, num_snaps, n))
    X_2 = np.zeros((num_traj, num_snaps, n))
    U = np.zeros((num_traj, num_snaps - 1, m))

    for i in range(num_traj):
        # initial condition near path-tracking equilibrium
        x0 = np.array([
            np.random.uniform(-0.5, 0.5),   # e_y
            np.random.uniform(-0.1, 0.1),   # e_psi
            np.random.uniform(-0.5, 0.5),   # v_y
            np.random.uniform(-0.2, 0.2),   # r
            np.random.uniform(-2.0, 2.0),   # e_v
        ])

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        num_list = np.linspace(1, 10, 10)
        seed_1 = np.random.choice(num_list)
        seed_2 = np.random.choice(num_list)

        for j in range(num_snaps - 1):
            if pars.get("U_type", "random") == "random":
                delta = np.random.uniform(-delta_max, delta_max)
                a_x = np.random.uniform(-ax_max, ax_max)
                U[i, j, :] = np.array([delta, a_x])

            elif pars.get("U_type", "random") == "sinusoidal":
                delta = delta_max * np.sin(seed_1 * np.pi * j * dt)
                a_x = ax_max * np.cos(seed_2 * np.pi * j * dt)
                U[i, j, :] = np.array([delta, a_x])

            X_1[i, j + 1, :] = FK_solver(X_1[i, j, :], U[i, j, :], pars)
            X_2[i, j + 1, :] = FK_solver(
                X_2[i, j, :], U[i, j, :], pars_new, sensor_noise, SNR_DB, j
            )

    return X_1, X_2, U

# import numpy as np
# import scipy.sparse as sp
#
#
# class PathTrackingLinearDynamics:
#     """
#     Discrete-time linear vehicle model for path tracking
#     with both lateral and longitudinal dynamics.
#
#     State:
#         x = [e_y, e_psi, v_y, r, e_v]^T
#
#         e_y   : lateral error [m]
#         e_psi : heading error [rad]
#         v_y   : lateral velocity [m/s]
#         r     : yaw rate [rad/s]
#         e_v   : longitudinal speed error = v_x - v_ref [m/s]
#
#     Input:
#         u = [delta, a_x]^T
#
#         delta : steering angle [rad]
#         a_x   : longitudinal acceleration command [m/s^2]
#     """
#
#     def __init__(
#         self,
#         dt,
#         m=1500.0,
#         Iz=2250.0,
#         lf=1.2,
#         lr=1.6,
#         Cf=80000.0,
#         Cr=80000.0,
#         vx_ref=15.0,
#         curvature_ref=0.0,
#         use_sparse=True,
#     ):
#         self.dt = dt
#         self.m = m
#         self.Iz = Iz
#         self.lf = lf
#         self.lr = lr
#         self.Cf = Cf
#         self.Cr = Cr
#         self.vx_ref = vx_ref
#         self.curvature_ref = curvature_ref
#
#         self.nx = 5
#         self.m_in = 2
#         self.nz = self.nx
#
#         A_c, B_c = self._build_continuous_model(vx_ref, curvature_ref)
#         A_d, B_d = self._discretize(A_c, B_c, dt)
#
#         self.A = sp.csc_matrix(A_d) if use_sparse else A_d
#         self.B = sp.csc_matrix(B_d) if use_sparse else B_d
#         self.C = sp.csc_matrix(np.eye(self.nx)) if use_sparse else np.eye(self.nx)
#
#     def _build_continuous_model(self, vx_ref, curvature_ref):
#         """
#         Continuous-time linearized bicycle model around reference speed vx_ref.
#         """
#         vx = max(float(vx_ref), 0.5)  # avoid division by zero
#
#         m = self.m
#         Iz = self.Iz
#         lf = self.lf
#         lr = self.lr
#         Cf = self.Cf
#         Cr = self.Cr
#
#         # State: [e_y, e_psi, v_y, r, e_v]
#         A = np.zeros((5, 5), dtype=float)
#         B = np.zeros((5, 2), dtype=float)
#
#         # e_y_dot = v_y + vx * e_psi
#         A[0, 1] = vx
#         A[0, 2] = 1.0
#
#         # e_psi_dot = r - vx * kappa_ref
#         A[1, 3] = 1.0
#
#         # v_y_dot
#         A[2, 2] = -(2 * Cf + 2 * Cr) / (m * vx)
#         A[2, 3] = -vx - (2 * Cf * lf - 2 * Cr * lr) / (m * vx)
#         B[2, 0] = 2 * Cf / m
#
#         # r_dot
#         A[3, 2] = -(2 * Cf * lf - 2 * Cr * lr) / (Iz * vx)
#         A[3, 3] = -(2 * Cf * lf**2 + 2 * Cr * lr**2) / (Iz * vx)
#         B[3, 0] = 2 * Cf * lf / Iz
#
#         # e_v_dot = a_x
#         B[4, 1] = 1.0
#
#         return A, B
#
#     def _discretize(self, A_c, B_c, dt):
#         """
#         Euler discretization.
#         For first implementation this is enough.
#         """
#         nx = A_c.shape[0]
#         A_d = np.eye(nx) + dt * A_c
#         B_d = dt * B_c
#         return A_d, B_d
#
#     def eval_dot(self, x, u, t=None):
#         """
#         Computes x_{k+1} = A x_k + B u_k
#         """
#         A = self.A.toarray() if hasattr(self.A, "toarray") else self.A
#         B = self.B.toarray() if hasattr(self.B, "toarray") else self.B
#         return A @ x + B @ u
#
#     def output(self, x):
#         """
#         Computes y_k = C x_k
#         """
#         C = self.C.toarray() if hasattr(self.C, "toarray") else self.C
#         return C @ x
#
#     def get_linearization(self, x0, x1, u):
#         """
#         Same interface as your original class.
#         """
#         A_lin = self.A.toarray() if hasattr(self.A, "toarray") else self.A
#         B_lin = self.B.toarray() if hasattr(self.B, "toarray") else self.B
#
#         x_next = self.eval_dot(x0, u)
#         r_lin = x_next - x1
#
#         return A_lin, B_lin, r_lin
#
#     def update_reference(self, vx_ref, curvature_ref=0.0):
#         """
#         Rebuild linearization around new reference speed / curvature.
#         Useful if you do gain scheduling along the path.
#         """
#         self.vx_ref = vx_ref
#         self.curvature_ref = curvature_ref
#
#         A_c, B_c = self._build_continuous_model(vx_ref, curvature_ref)
#         A_d, B_d = self._discretize(A_c, B_c, self.dt)
#
#         if hasattr(self.A, "toarray"):
#             self.A = sp.csc_matrix(A_d)
#             self.B = sp.csc_matrix(B_d)
#         else:
#             self.A = A_d
#             self.B = B_d
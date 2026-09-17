import time
import os
import numpy as np
import osqp
from scipy import sparse
import importlib


class NonlinearMPCController():
    """
    Class for nonlinear MPC with control-affine dynamics.

    Quadratic programs are solved using OSQP.

    Added:
    - PPC soft constraints on e_y and e_psi
    - slack variables with quadratic + linear penalties
    """

    def __init__(self, dynamics, N, dt, umin, umax, xmin, xmax,
                 Q, R, QN, solver_settings,
                 add_ppc_soft=True,
                 q_slack_ey=2e4,
                 q_slack_epsi=2e4,
                 p_slack_ey=2e3,
                 p_slack_epsi=2e3,
                 ppc_params=None):
        """
        Initialize the nonlinear mpc class.
        """

        self.dynamics_object = dynamics
        self.nz = self.dynamics_object.nz
        self.nx = self.dynamics_object.nx
        self.nu = self.dynamics_object.m
        self.dt = dt
        self.C = self.dynamics_object.C

        self.Q = Q
        self.QN = QN
        self.R = R
        self.N = N
        self.xmin = xmin
        self.xmax = xmax
        self.umin = umin
        self.umax = umax

        self.solver_settings = dict(solver_settings) if solver_settings is not None else {}
        self.last_solve_info = {}

        self.prep_time = []
        self.qp_time = []
        self.comp_time = []
        self.x_iter = []
        self.u_iter = []

        # ---------------- PPC soft constraints ----------------
        self.add_ppc_soft = add_ppc_soft
        self.q_slack_ey = q_slack_ey
        self.q_slack_epsi = q_slack_epsi
        self.p_slack_ey = p_slack_ey
        self.p_slack_epsi = p_slack_epsi

        default_ppc = {
            "rho_ey_0": 0.50,
            "rho_ey_inf": 0.03,
            "lambda_ey": 1.5,
            "rho_epsi_0": 0.25,
            "rho_epsi_inf": 0.02,
            "lambda_epsi": 1.8
        }
        self.ppc_params = default_ppc if ppc_params is None else ppc_params

        self.setup_var_indices_()

    def _setting(self, key, default):
        return self.solver_settings.get(key, default)

    def _base_solver_kwargs(self):
        setup_kwargs = {
            'P': self._osqp_P,
            'q': self._osqp_q,
            'A': self._osqp_A,
            'l': self._osqp_l,
            'u': self._osqp_u,
            'verbose': bool(self._setting('verbose', False)),
            'warm_start': bool(self._setting('warm_start', True)),
            'polish': bool(self._setting('polish', True)),
            'polish_refine_iter': int(self._setting('polish_refine_iter', 3)),
            'check_termination': int(self._setting('check_termination', 10)),
            'eps_abs': float(self._setting('eps_abs', 1e-3)),
            'eps_rel': float(self._setting('eps_rel', 1e-3)),
            'eps_prim_inf': float(self._setting('eps_prim_inf', 1e-3)),
            'eps_dual_inf': float(self._setting('eps_dual_inf', 1e-3)),
            'adaptive_rho': bool(self._setting('adaptive_rho', True)),
            'max_iter': int(self._setting('max_iter', 5000)),
            'scaling': int(bool(self._setting('scaling', True))),
        }

        if 'linsys_solver' in self.solver_settings:
            setup_kwargs['linsys_solver'] = self.solver_settings['linsys_solver']
        if 'rho' in self.solver_settings:
            setup_kwargs['rho'] = float(self.solver_settings['rho'])
        if 'adaptive_rho_interval' in self.solver_settings:
            setup_kwargs['adaptive_rho_interval'] = int(self.solver_settings['adaptive_rho_interval'])
        if 'adaptive_rho_tolerance' in self.solver_settings:
            setup_kwargs['adaptive_rho_tolerance'] = float(self.solver_settings['adaptive_rho_tolerance'])
        if 'time_limit' in self.solver_settings:
            tlim = float(self.solver_settings['time_limit'])
            if tlim > 0:
                setup_kwargs['time_limit'] = tlim
        return setup_kwargs

    # ------------------------------------------------------------------
    # helper
    # ------------------------------------------------------------------
    def setup_var_indices_(self):
        self.n_opt_x = self.nz * (self.N + 1)
        self.n_opt_u = self.nu * self.N
        self.n_opt_x_u = self.n_opt_x + self.n_opt_u

        if self.add_ppc_soft:
            self.idx_s_ey_0 = self.n_opt_x_u
            self.idx_s_ey_1 = self.idx_s_ey_0 + (self.N + 1)

            self.idx_s_epsi_0 = self.idx_s_ey_1
            self.idx_s_epsi_1 = self.idx_s_epsi_0 + (self.N + 1)

            self.n_opt_total = self.idx_s_epsi_1
        else:
            self.n_opt_total = self.n_opt_x_u

    def build_ppc_envelope_(self):
        k = np.arange(self.N + 1) * self.dt
        p = self.ppc_params

        rho_ey = (
            (p["rho_ey_0"] - p["rho_ey_inf"]) * np.exp(-p["lambda_ey"] * k)
            + p["rho_ey_inf"]
        )
        rho_epsi = (
            (p["rho_epsi_0"] - p["rho_epsi_inf"]) * np.exp(-p["lambda_epsi"] * k)
            + p["rho_epsi_inf"]
        )
        return rho_ey, rho_epsi

    def rebuild_osqp_problem_(self):
        self.prob = osqp.OSQP()
        setup_kwargs = self._base_solver_kwargs()
        try:
            self.prob.setup(**setup_kwargs)
        except TypeError:
            # Compatibility fallback for older OSQP builds without time_limit.
            setup_kwargs.pop('time_limit', None)
            self.prob.setup(**setup_kwargs)

    # ------------------------------------------------------------------
    # controller construction
    # ------------------------------------------------------------------
    def construct_controller(self, z_init, u_init, x_ref):
        """
        Construct NMPC controller.

        Parameters
        ----------
        z_init : (N+1, nz)
        u_init : (N, nu)
        x_ref  : (nx, N+1)  reference window
        """
        if x_ref.ndim != 2 or x_ref.shape[0] != self.nx or x_ref.shape[1] != self.N + 1:
            raise ValueError(
                f"construct_controller expects x_ref shape ({self.nx}, {self.N+1}), "
                f"but got {x_ref.shape}"
            )

        z0 = z_init[0, :]
        self.z_init = z_init.copy()
        self.u_init = u_init.copy()
        self.x_init = self.C @ z_init.T
        self.u_init_flat = self.u_init.flatten()
        self.x_init_flat = self.x_init.flatten(order='F')
        self.warm_start = np.zeros(self.n_opt_total)

        A_lst = [np.eye(self.nz) for _ in range(self.N)]
        B_lst = [np.zeros((self.nz, self.nu)) for _ in range(self.N)]
        r_lst = [np.zeros(self.nz) for _ in range(self.N)]
        self.r_vec = np.array(r_lst).flatten()

        self.construct_objective_(x_ref)
        self.construct_constraint_vecs_(z0, x_ref)
        self.construct_constraint_matrix_(A_lst, B_lst)

        self.rebuild_osqp_problem_()

    def update_solver_settings(self, solver_settings):
        self.solver_settings = dict(solver_settings) if solver_settings is not None else {}

        update_kwargs = {
            'warm_start': bool(self._setting('warm_start', True)),
            'polish': bool(self._setting('polish', True)),
            'polish_refine_iter': int(self._setting('polish_refine_iter', 3)),
            'check_termination': int(self._setting('check_termination', 10)),
            'eps_abs': float(self._setting('eps_abs', 1e-3)),
            'eps_rel': float(self._setting('eps_rel', 1e-3)),
            'eps_prim_inf': float(self._setting('eps_prim_inf', 1e-3)),
            'eps_dual_inf': float(self._setting('eps_dual_inf', 1e-3)),
            'max_iter': int(self._setting('max_iter', 5000)),
            'adaptive_rho': bool(self._setting('adaptive_rho', True)),
            'scaling': int(bool(self._setting('scaling', True))),
        }

        if 'time_limit' in self.solver_settings:
            tlim = float(self.solver_settings['time_limit'])
            if tlim > 0:
                update_kwargs['time_limit'] = tlim

        try:
            self.prob.update_settings(**update_kwargs)
        except TypeError:
            update_kwargs.pop('time_limit', None)
            self.prob.update_settings(**update_kwargs)

    def trajectory_tracking(self, x0, z0, x_ref_traj, max_iter=1):
        """
        compute control input for each reference position using solve_to_convergence

        x_ref_traj should be provided as a sequence of reference windows if used.
        """
        self.xr_traj = x_ref_traj
        self.N_traj = x_ref_traj.shape[0]
        self.x_traced = np.empty((self.N_traj + 1, self.nx))
        self.z_N0 = z0
        self.x_N0 = x0
        self.x_traced[0, :] = x0
        self.controls = np.empty((self.N_traj, self.nu))

        for i in range(self.N_traj):
            xr = self.xr_traj[i, :]
            self.solve_to_convergence(xr, self.z_N0, self.z_init, self.u_init, max_iter=max_iter, eps=1e-3)
            self.update_initial_guess_()
            self.x_traced[i + 1, :] = self.x_N0
            self.controls[i, :] = self.cur_u[0, :]

    def solve_to_convergence(self, xr, z, z_init_0, u_init_0, max_iter=1, eps=1e-3):
        """
        Run SQP-algorithm to convergence

        xr must be reference window with shape (nx, N+1)
        """
        if xr.ndim != 2 or xr.shape[0] != self.nx or xr.shape[1] != self.N + 1:
            raise ValueError(
                f"solve_to_convergence expects xr shape ({self.nx}, {self.N+1}), "
                f"but got {xr.shape}"
            )

        iter = 0
        self.cur_z = z_init_0.copy()
        self.cur_u = u_init_0.copy()
        u_prev = np.zeros_like(u_init_0)
        sqp_step_size = float(self._setting('sqp_step_size', 1.0))
        du_clip = self._setting('du_clip', None)
        dz_clip = self._setting('dz_clip', None)
        if du_clip is not None:
            du_clip = float(abs(du_clip))
        if dz_clip is not None:
            dz_clip = float(abs(dz_clip))

        while iter < max_iter:
            if iter > 0:
                den = max(np.linalg.norm(u_prev), 1e-8)
                rel_change = np.linalg.norm(u_prev - self.cur_u) / den
                if rel_change <= eps:
                    break

            t0 = time.time()
            u_prev = self.cur_u.copy()
            self.z_init = self.cur_z.copy()
            self.x_init = (self.C @ self.z_init.T)
            self.x_init_flat = self.x_init.flatten(order='F')
            self.u_init = self.cur_u.copy()
            self.u_init_flat = self.u_init.flatten()

            # Update equality constraint matrices:
            A_lst, B_lst = self.update_linearization_()

            # Solve MPC instance
            self.construct_objective_(xr)
            self.construct_constraint_vecs_(z, xr)
            self.construct_constraint_matrix_(A_lst, B_lst)

            # IMPORTANT:
            # P changes if Q/QN/R changed outside, and A changes with linearization.
            # Rebuild OSQP problem for correctness.
            self.rebuild_osqp_problem_()

            t_prep = time.time() - t0

            self.solve_mpc_()
            dz = self.dz_flat.reshape(self.N + 1, self.nz)
            du = self.du_flat.reshape(self.N, self.nu)

            if dz_clip is not None:
                dz = np.clip(dz, -dz_clip, dz_clip)
                self.dz_flat = dz.reshape(-1)
            if du_clip is not None:
                du = np.clip(du, -du_clip, du_clip)
                self.du_flat = du.reshape(-1)

            alpha = np.clip(sqp_step_size, 0.05, 1.0)
            self.cur_z = self.z_init + alpha * dz
            self.cur_u = self.u_init + alpha * du
            self.u_init_flat = self.u_init_flat + alpha * self.du_flat

            iter += 1
            self.comp_time.append(time.time() - t0)
            self.prep_time.append(t_prep)
            self.qp_time.append(self.comp_time[-1] - t_prep)

        self.z_N0 = self.cur_z[1, :]
        self.x_N0 = self.C @ self.z_N0.T

    # ------------------------------------------------------------------
    # objective
    # ------------------------------------------------------------------
    def construct_objective_(self, xr):
        """
        Construct MPC objective function
        """
        Pz = sparse.block_diag([
            sparse.kron(sparse.eye(self.N), self.C.T @ self.Q @ self.C),
            self.C.T @ self.QN @ self.C
        ], format='csc')

        Pu = sparse.kron(sparse.eye(self.N), self.R, format='csc')

        if self.add_ppc_soft:
            Ps_ey = self.q_slack_ey * sparse.eye(self.N + 1, format='csc')
            Ps_epsi = self.q_slack_epsi * sparse.eye(self.N + 1, format='csc')
            self._osqp_P = sparse.block_diag([Pz, Pu, Ps_ey, Ps_epsi], format='csc')
        else:
            self._osqp_P = sparse.block_diag([Pz, Pu], format='csc')

        q_zu = np.hstack([
            (self.C.T @ self.Q @ (self.x_init[:, :-1] - xr[:, :-1])).flatten(order='F'),
            self.C.T @ self.QN @ (self.x_init[:, -1] - xr[:, -1]),
            (self.R @ (self.u_init.T)).flatten(order='F')
        ])

        if self.add_ppc_soft:
            q_slack = np.hstack([
                self.p_slack_ey * np.ones(self.N + 1),
                self.p_slack_epsi * np.ones(self.N + 1)
            ])
            self._osqp_q = np.hstack([q_zu, q_slack])
        else:
            self._osqp_q = q_zu

    def update_objective_(self, xr):
        """
        Keep compatibility. Full reconstruction is safer because P may change.
        """
        self.construct_objective_(xr)

    # ------------------------------------------------------------------
    # constraints
    # ------------------------------------------------------------------
    def construct_constraint_matrix_(self, A_lst, B_lst):
        """
        Construct MPC constraint matrix
        """
        # Linear dynamics constraints:
        A_dyn = sparse.vstack((
            sparse.csc_matrix((self.nz, (self.N + 1) * self.nz)),
            sparse.hstack((
                sparse.block_diag(A_lst),
                sparse.csc_matrix((self.N * self.nz, self.nz))
            ))
        ))
        Ax = -sparse.eye((self.N + 1) * self.nz) + A_dyn
        Bu = sparse.vstack((
            sparse.csc_matrix((self.nz, self.N * self.nu)),
            sparse.block_diag(B_lst)
        ))

        Aeq_core = sparse.hstack([Ax, Bu])

        # Input constraints:
        Aineq_u_core = sparse.hstack([
            sparse.csc_matrix((self.N * self.nu, (self.N + 1) * self.nz)),
            sparse.eye(self.N * self.nu)
        ])

        # State constraints:
        Aineq_x_core = sparse.hstack([
            sparse.kron(sparse.eye(self.N + 1), self.C),
            sparse.csc_matrix(((self.N + 1) * self.nx, self.N * self.nu))
        ])

        if self.add_ppc_soft:
            # add zero cols for equality and box constraints
            Aeq = sparse.hstack([
                Aeq_core,
                sparse.csc_matrix((Aeq_core.shape[0], 2 * (self.N + 1)))
            ], format='csc')

            Aineq_u = sparse.hstack([
                Aineq_u_core,
                sparse.csc_matrix((Aineq_u_core.shape[0], 2 * (self.N + 1)))
            ], format='csc')

            Aineq_x = sparse.hstack([
                Aineq_x_core,
                sparse.csc_matrix((Aineq_x_core.shape[0], 2 * (self.N + 1)))
            ], format='csc')

            # PPC constraints
            C_ey = self.C[1:2, :]
            C_epsi = self.C[2:3, :]

            Aey = sparse.kron(sparse.eye(self.N + 1), C_ey)
            Aepsi = sparse.kron(sparse.eye(self.N + 1), C_epsi)

            Zxu = sparse.csc_matrix((self.N + 1, self.N * self.nu))
            I = sparse.eye(self.N + 1, format='csc')
            Z = sparse.csc_matrix((self.N + 1, self.N + 1))

            # ey - ey_ref <= rho + s_ey
            Appc_ey_pos = sparse.hstack([Aey, Zxu, -I, Z], format='csc')
            # -(ey - ey_ref) <= rho + s_ey
            Appc_ey_neg = sparse.hstack([-Aey, Zxu, -I, Z], format='csc')

            # epsi - epsi_ref <= rho + s_epsi
            Appc_epsi_pos = sparse.hstack([Aepsi, Zxu, Z, -I], format='csc')
            # -(epsi - epsi_ref) <= rho + s_epsi
            Appc_epsi_neg = sparse.hstack([-Aepsi, Zxu, Z, -I], format='csc')

            # slack >= 0
            Aslack_pos = sparse.hstack([
                sparse.csc_matrix((2 * (self.N + 1), self.n_opt_x_u)),
                sparse.eye(2 * (self.N + 1), format='csc')
            ], format='csc')

            self._osqp_A = sparse.vstack([
                Aeq,
                Aineq_u,
                Aineq_x,
                Appc_ey_pos,
                Appc_ey_neg,
                Appc_epsi_pos,
                Appc_epsi_neg,
                Aslack_pos
            ], format='csc')
        else:
            Aeq = Aeq_core
            Aineq_u = Aineq_u_core
            Aineq_x = Aineq_x_core
            self._osqp_A = sparse.vstack([Aeq, Aineq_u, Aineq_x], format='csc')

        self._osqp_A.eliminate_zeros()

    def construct_constraint_matrix_data_(self, A_lst, B_lst):
        """
        Deprecated for PPC mode. Kept only for compatibility.
        """
        self._osqp_A_data = self._osqp_A.data.copy()

    def update_constraint_matrix_data_(self, A_lst, B_lst):
        """
        Deprecated for PPC mode. Kept only for compatibility.
        """
        self._osqp_A_data = self._osqp_A.data.copy()

    def construct_constraint_vecs_(self, z, xr=None):
        """
        Construct MPC constraint vectors (lower and upper bounds)
        """
        dz0 = z - self.z_init[0, :]
        leq = np.hstack([-dz0, -self.r_vec])
        ueq = leq

        # Input constraints:
        u_init_flat = self.u_init.flatten()
        self.umin_tiled = np.tile(self.umin, self.N)
        self.umax_tiled = np.tile(self.umax, self.N)
        lineq_u = self.umin_tiled - u_init_flat
        uineq_u = self.umax_tiled - u_init_flat

        # State constraints:
        x_init_flat = self.x_init.flatten(order='F')
        self.xmin_tiled = np.tile(self.xmin, self.N + 1)
        self.xmax_tiled = np.tile(self.xmax, self.N + 1)
        lineq_x = self.xmin_tiled - x_init_flat
        uineq_x = self.xmax_tiled - x_init_flat

        l_all = [leq, lineq_u, lineq_x]
        u_all = [ueq, uineq_u, uineq_x]

        if self.add_ppc_soft:
            if xr is None:
                raise ValueError("construct_constraint_vecs_ requires xr when add_ppc_soft=True")

            rho_ey, rho_epsi = self.build_ppc_envelope_()

            ey_init = self.x_init[1, :]
            epsi_init = self.x_init[2, :]

            ey_ref = xr[1, :]
            epsi_ref = xr[2, :]

            infv = 1e20

            ub_ey_pos = rho_ey - (ey_init - ey_ref)
            ub_ey_neg = rho_ey + (ey_init - ey_ref)

            ub_epsi_pos = rho_epsi - (epsi_init - epsi_ref)
            ub_epsi_neg = rho_epsi + (epsi_init - epsi_ref)

            l_ppc_ey_pos = -infv * np.ones(self.N + 1)
            l_ppc_ey_neg = -infv * np.ones(self.N + 1)
            l_ppc_epsi_pos = -infv * np.ones(self.N + 1)
            l_ppc_epsi_neg = -infv * np.ones(self.N + 1)

            # slack >= 0
            l_slack = np.zeros(2 * (self.N + 1))
            u_slack = infv * np.ones(2 * (self.N + 1))

            l_all += [l_ppc_ey_pos, l_ppc_ey_neg, l_ppc_epsi_pos, l_ppc_epsi_neg, l_slack]
            u_all += [ub_ey_pos, ub_ey_neg, ub_epsi_pos, ub_epsi_neg, u_slack]

        self._osqp_l = np.hstack(l_all)
        self._osqp_u = np.hstack(u_all)

    def update_constraint_vecs_(self, z, xr=None):
        """
        Rebuild completely for safety.
        """
        self.construct_constraint_vecs_(z, xr)

    # ------------------------------------------------------------------
    # solve
    # ------------------------------------------------------------------
    def solve_mpc_(self):
        """
        Solve the MPC sub-problem
        """
        if self._setting('warm_start', True):
            self.prob.warm_start(x=self.warm_start)

        num_retries = int(self._setting('retry_on_fail', 0))
        relax_factor = float(self._setting('retry_relax_factor', 1.6))
        base_eps_abs = float(self._setting('eps_abs', 1e-3))
        base_eps_rel = float(self._setting('eps_rel', 1e-3))
        base_max_iter = int(self._setting('max_iter', 5000))
        accept_inaccurate = bool(self._setting('accept_solved_inaccurate', True))
        accept_partial = bool(self._setting('accept_partial_solution', True))
        max_prim = float(self._setting('accept_partial_prim_res', 3e-3))
        max_dual = float(self._setting('accept_partial_dual_res', 3e-3))

        accepted = False
        last_status = None
        for attempt in range(num_retries + 1):
            if attempt > 0:
                self.prob.update_settings(
                    eps_abs=base_eps_abs * (relax_factor ** attempt),
                    eps_rel=base_eps_rel * (relax_factor ** attempt),
                    max_iter=max(base_max_iter, int(base_max_iter * (1.0 + 0.6 * attempt)))
                )

            self.res = self.prob.solve()

            status = self.res.info.status
            prim_res = self.res.info.prim_res
            dual_res = self.res.info.dual_res
            solve_time = getattr(self.res.info, "solve_time", None)
            run_time = getattr(self.res.info, "run_time", None)

            self.last_solve_info = {
                "status": status,
                "status_val": self.res.info.status_val,
                "iter": self.res.info.iter,
                "obj_val": self.res.info.obj_val,
                "prim_res": prim_res,
                "dual_res": dual_res,
                "solve_time": solve_time,
                "run_time": run_time,
                "attempt": attempt,
            }
            last_status = status

            if self.res.x is None:
                continue

            if status == 'solved':
                accepted = True
                break

            if status == 'solved inaccurate' and accept_inaccurate:
                print('[WARN] OSQP solved inaccurate, accepting solution.')
                accepted = True
                break

            if status in ('maximum iterations reached', 'run time limit reached'):
                if accept_partial and prim_res < max_prim and dual_res < max_dual:
                    print('[WARN] OSQP reached iteration/time limit with small residuals, accepting solution.')
                    accepted = True
                    break

        if not accepted:
            print("OSQP status:", last_status)
            print("status_val:", self.res.info.status_val)
            print("iter:", self.res.info.iter)
            print("obj_val:", self.res.info.obj_val)
            print("prim_res:", self.res.info.prim_res)
            print("dual_res:", self.res.info.dual_res)
            raise ValueError('OSQP did not solve the problem!')

        self.dz_flat = self.res.x[:(self.N + 1) * self.nz]
        self.du_flat = self.res.x[(self.N + 1) * self.nz:(self.N + 1) * self.nz + self.nu * self.N]

        if self.add_ppc_soft:
            self.s_ey = self.res.x[self.idx_s_ey_0:self.idx_s_ey_1]
            self.s_epsi = self.res.x[self.idx_s_epsi_0:self.idx_s_epsi_1]
        else:
            self.s_ey = np.zeros(self.N + 1)
            self.s_epsi = np.zeros(self.N + 1)

    def update_initial_guess_(self):
        """
        Update the intial guess of the solution (z_init, u_init)
        """
        z_last = self.cur_z[-1, :]
        u_new = self.cur_u[-1, :]
        z_new = self.dynamics_object.eval_dot(z_last, u_new, None)

        self.z_init[:-1, :] = self.cur_z[1:, :]
        self.z_init[-1, :] = z_new

        self.u_init[:-1, :] = self.cur_u[1:, :]
        self.u_init[-1, :] = u_new
        self.u_init_flat[:-self.nu] = self.u_init_flat[self.nu:]
        self.u_init_flat[-self.nu:] = u_new

        self.x_init = self.C @ self.z_init.T
        self.x_init_flat = self.x_init.flatten(order='F')

        # Warm start of OSQP:
        self.warm_start = np.zeros(self.n_opt_total)

        du_new = self.du_flat[-self.nu:]
        dz_last = self.dz_flat[-self.nz:]
        dz_new = self.dynamics_object.eval_dot(dz_last, du_new, None)
        self.warm_start[:self.nz * self.N] = self.dz_flat[self.nz:]
        self.warm_start[self.nz * self.N:self.nz * (self.N + 1)] = dz_new
        self.warm_start[self.nz * (self.N + 1):self.nz * (self.N + 1) + self.nu * self.N - self.nu] = self.du_flat[self.nu:]
        self.warm_start[self.nz * (self.N + 1) + self.nu * self.N - self.nu:self.nz * (self.N + 1) + self.nu * self.N] = du_new

        if self.add_ppc_soft:
            self.warm_start[self.idx_s_ey_0:self.idx_s_ey_1 - 1] = self.s_ey[1:]
            self.warm_start[self.idx_s_ey_1 - 1] = self.s_ey[-1]

            self.warm_start[self.idx_s_epsi_0:self.idx_s_epsi_1 - 1] = self.s_epsi[1:]
            self.warm_start[self.idx_s_epsi_1 - 1] = self.s_epsi[-1]

    def update_linearization_(self):
        """
        Update the linearization of the dynamics around the initial guess
        """
        A_lst, B_lst, r_lst = [], [], []
        for z, z_next, u in zip(self.z_init[:-1, :], self.z_init[1:, :], self.u_init):
            a, b, r = self.dynamics_object.get_linearization(z, z_next, u)
            A_lst.append(a)
            B_lst.append(b)
            r_lst.append(r)

        self.r_vec = np.array(r_lst).flatten()
        return A_lst, B_lst

    def get_state_prediction(self):
        return self.cur_z

    def get_control_prediction(self):
        return self.cur_u

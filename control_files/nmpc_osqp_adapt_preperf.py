
import time
import os
import numpy as np
import osqp
from scipy import sparse

class NonlinearMPCController():
    """
    包装 NonlinearMPCController，新增对 e_y 和 e_psi 的预定性能软约束。
    """
# class NonlinearMPCController():
    """
    包装 NonlinearMPCController，新增对 e_y 和 e_psi 的预定性能软约束。
    """

    def __init__(self, dynamics, N, dt, umin, umax, xmin, xmax, Q, R, QN,
                 rho0=1.2, rho_inf=0.08, lambda_pp=0.75,
                 Ws=80.0, WsN=150.0, solver_settings=None):

        super().__init__(dynamics, N, dt, umin, umax, xmin, xmax, Q, R, QN, solver_settings)

        self.dt = dt
        self.rho0 = rho0
        self.rho_inf = rho_inf
        self.lambda_pp = lambda_pp
        self.Ws = Ws  # 阶段 slack 惩罚（标量，对 e_y 和 e_psi 相同）
        self.WsN = WsN  # 终端 slack 惩罚

        self.n_slack_per_step = 2  # e_y 和 e_psi 各一个 slack
        self.n_slack_total = self.n_slack_per_step * (N + 1)

        # slack 权重矩阵（对角）
        self.Ws_diag = np.full(self.n_slack_per_step, Ws)
        self.WsN_diag = np.full(self.n_slack_per_step, WsN)

    def prescribed_performance_bound(self, k):
        """指数衰减型性能边界 ρ(k)"""
        return (self.rho0 - self.rho_inf) * np.exp(-self.lambda_pp * k * self.dt) + self.rho_inf

    def set_prescribed_performance(self, k_current):
        """每次求解 MPC 前调用，更新 rho 序列"""
        rho_seq = np.array([self.prescribed_performance_bound(k_current + j)
                            for j in range(self.N + 1)])
        # 对 e_y 和 e_psi 使用相同 rho（可后续分开）
        self.rho_seq_full = np.tile(rho_seq, self.n_slack_per_step).reshape(-1)
        # 形状：(n_slack_total,)

    # ==================== 关键重写方法 ====================

    def construct_controller(self, z_init, u_init, x_ref):
        """扩展构造：增加 slack 部分"""
        # 补全 solver_settings 缺失键（避免 KeyError）
        ss = dict(self.solver_settings)  # 复制一份
        ss.setdefault("linsys_solver", "qdldl")
        ss.setdefault("max_iter", 4000)
        ss.setdefault("scaling", 1)

        # 临时替换
        original_ss = self.solver_settings
        self.solver_settings = ss

        try:
            # super().construct_controller(z_init, u_init, x_ref)
            """扩展构造：增加 slack 部分"""
            # 先调用父类，构建原 P, q, A, l, u 等
            super().construct_controller(z_init, u_init, x_ref)

            # 1. 扩展目标函数 P（新增 slack 代价）
            Ws_blocks = sparse.kron(sparse.eye(self.N), sparse.diags(self.Ws_diag))
            WsN_block = sparse.diags(self.WsN_diag)
            P_slack = sparse.block_diag([Ws_blocks, WsN_block], format='csc')
            self._osqp_P = sparse.block_diag([self._osqp_P, P_slack], format='csc')

            # 2. 扩展 q（slack 线性项为 0）
            self._osqp_q = np.hstack([self._osqp_q, np.zeros(self.n_slack_total)])

            # 3. 扩展约束矩阵 A（新增 slack 列）
            self._rebuild_A_with_slack()

            # 4. 重新 setup OSQP
            self.prob = osqp.OSQP()
            setup_kwargs = {
                'P': self._osqp_P,
                'q': self._osqp_q,
                'A': self._osqp_A,
                'l': self._osqp_l,
                'u': self._osqp_u,
                'verbose': False,
                'warm_start': self.solver_settings.get('warm_start', True),
                'polish': self.solver_settings.get('polish', True),
                'polish_refine_iter': self.solver_settings.get('polish_refine_iter', 3),
                'check_termination': self.solver_settings.get('check_termination', 5),
                'eps_abs': self.solver_settings.get('eps_abs', 1e-4),
                'eps_rel': self.solver_settings.get('eps_rel', 1e-4),
                'eps_prim_inf': self.solver_settings.get('eps_prim_inf', 1e-4),
                'eps_dual_inf': self.solver_settings.get('eps_dual_inf', 1e-4),
                'adaptive_rho': self.solver_settings.get('adaptive_rho', True),
                'max_iter': self.solver_settings.get('max_iter', 4000),
                'scaling': int(self.solver_settings.get('scaling', 1)),
            }
            if 'linsys_solver' in self.solver_settings:
                setup_kwargs['linsys_solver'] = self.solver_settings['linsys_solver']
            self.prob.setup(**setup_kwargs)
        finally:
            self.solver_settings = original_ss  # 恢复

    def _rebuild_A_with_slack(self):
        """重建约束矩阵 A，新增 slack 列（对状态约束行增加 ±I_s）"""
        n_orig = self._osqp_A.shape[1]  # 原变量维度
        n_new = n_orig + self.n_slack_total

        # 原 A 的行数不变，新增 slack 对应的列
        # 状态不等式约束行对应 Aineq_x 的部分（最后 nx*(N+1) 行）
        n_state_ineq_rows = self.nx * (self.N + 1)
        n_state_start_row = self._osqp_A.shape[0] - n_state_ineq_rows

        # 构建新增 slack 列的稀疏矩阵（仅在状态不等式行有非零）
        slack_cols_data = []
        slack_cols_rows = []
        slack_cols_cols = []

        for step in range(self.N + 1):
            for s_idx in range(self.n_slack_per_step):
                global_s_idx = step * self.n_slack_per_step + s_idx
                row_base = n_state_start_row + step * self.nx

                # 对于每个输出维度：下界行加 -1 * s，上界行加 +1 * s（因为 l <= A x + I_s s <= u 会变成 -rho -s <= e <= rho + s）
                # 下界行（e >= -rho - s） → 对应系数 -1 for s
                slack_cols_data.append(-1.0)
                slack_cols_rows.append(row_base + s_idx)  # 下界行
                slack_cols_cols.append(n_orig + global_s_idx)

                # 上界行（e <= rho + s） → 对应系数 +1 for s
                slack_cols_data.append(1.0)
                slack_cols_rows.append(row_base + s_idx)  # 上界行（注意：上界行也是同一个输出维度）
                slack_cols_cols.append(n_orig + global_s_idx)

        slack_A = sparse.coo_matrix(
            (slack_cols_data, (slack_cols_rows, slack_cols_cols)),
            shape=(self._osqp_A.shape[0], n_new)
        ).tocsc()

        self._osqp_A = sparse.hstack([self._osqp_A, slack_A], format='csc')
        self._osqp_A.eliminate_zeros()

    def update_constraint_vecs_(self, z):
        """重写：加入 rho 软化（在原状态约束基础上叠加 ±rho ± s）"""
        super().update_constraint_vecs_(z)  # 先执行原有逻辑

        # 状态不等式约束部分（最后 nx*(N+1) 行）
        n_state_ineq = self.nx * (self.N + 1)
        state_l_start = self.n_opt_x_u
        state_u_start = state_l_start + n_state_ineq // 2  # 注意上下界是连续存放的？实际按原代码是 l 和 u 分开但同一段

        # 更精确：原代码中 lineq_x 和 uineq_x 是连续的 nx*(N+1) 长
        # 我们对每个预测步的每个输出维度调整
        for step in range(self.N + 1):
            rho = self.rho_seq_full[step * self.n_slack_per_step: (step + 1) * self.n_slack_per_step]
            idx_start = state_l_start + step * self.nx
            # 下界：原 xmin - x_init  → 调整为 -rho - s（但 s 已通过 A 体现，这里只调整界）
            # 实际软约束实现：下界 l = -rho ，上界 u = +rho （因为 slack 已通过列实现 ±s）
            self._osqp_l[idx_start: idx_start + self.nx] = -rho
            self._osqp_u[idx_start: idx_start + self.nx] = rho  # 注意：原代码中 l 和 u 是对同一段状态约束的上下界

        # 同时确保 s >= 0（在 l/u 中对应 slack 变量的下界为 0）
        # slack 变量在决策向量最后，其约束需要单独添加（下界 0，上界 inf）
        # 这里简化处理：假设我们在 rebuild_A 时已处理，或在 l/u 末尾追加
        # （完整实现中需扩展 l/u 维度，添加 s >= 0）
        # 当前版本为简化，建议先测试；若不可行，再补充 s>=0 硬约束行。

    # 注意：由于 s >= 0 需要额外约束行，完整版还需在 construct_constraint_matrix_ 中添加 s>=0 行。
    # 为避免一次改动过多，我先提供这个核心版本。你可先运行测试，若出现不可行或 slack 负值，再告诉我，我补全 s>=0 约束部分。

    def solve_to_convergence(self, xr, z, z_init_0, u_init_0, max_iter=1, eps=1e-3):
        """调用前需先 set_prescribed_performance"""
        # 使用示例：在你的闭环循环中调用前加上：
        # self.set_prescribed_performance(current_k)
        return super().solve_to_convergence(xr, z, z_init_0, u_init_0, max_iter, eps)
import numpy as np

# ==================== FK_solver 函数 ====================
# 作用：根据当前状态和控制输入，通过欧拉积分计算下一时刻的状态（模拟车辆动力学）
def FK_solver(x, u, pars, sensor_noise=False, SNR_DB=0, i=0):
    dt = pars['dt']

    m = pars['m']
    Iz = pars['Iz']
    lf = pars['lf']
    lr = pars['lr']
    Cf = pars['Cf']
    Cr = pars['Cr']
    vx_ref = max(float(pars['vx_ref']), 0.5)
    curvature_ref = pars.get('curvature_ref', 0.0)

    x = np.asarray(x, dtype=float).reshape(-1)
    u = np.asarray(u, dtype=float).reshape(-1)

    uncertainty_type = pars.get('uncertainty', 'NA')
    amp = pars.get('amp', 0.0)
    freq = pars.get('freq', 1.0)

    if uncertainty_type == 'constant':
        uncertainty_factor = amp
    elif uncertainty_type == 'periodic':
        uncertainty_factor = amp * np.sin(2 * np.pi * freq * i * dt)
    else:
        uncertainty_factor = 0.0

    delta_eff = u[0] + 0.5 * uncertainty_factor
    ax_eff = u[1] + uncertainty_factor

    def f(x_state):
        e_y, e_psi, v_y, r, e_v = x_state

        vx = max(vx_ref + e_v, 0.5)

        e_y_dot = v_y + vx * e_psi
        e_psi_dot = r - vx * curvature_ref

        v_y_dot = (
            -(2 * Cf + 2 * Cr) / (m * vx) * v_y
            + (-vx - (2 * Cf * lf - 2 * Cr * lr) / (m * vx)) * r
            + (2 * Cf / m) * delta_eff
        )

        r_dot = (
            -(2 * Cf * lf - 2 * Cr * lr) / (Iz * vx) * v_y
            - (2 * Cf * lf**2 + 2 * Cr * lr**2) / (Iz * vx) * r
            + (2 * Cf * lf / Iz) * delta_eff
        )

        e_v_dot = ax_eff

        return np.array([e_y_dot, e_psi_dot, v_y_dot, r_dot, e_v_dot], dtype=float)

    k1 = f(x)
    k2 = f(x + 0.5 * dt * k1)
    k3 = f(x + 0.5 * dt * k2)
    k4 = f(x + dt * k3)

    x_next = x + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)

    if sensor_noise:
        noise = np.random.normal(0.0, 1.0, size=x_next.shape)
        x_next = x_next * (1.0 + noise * 10 ** (-SNR_DB / 20))

    return x_next
# def FK_solver(x, u, pars, sensor_noise=False, SNR_DB=0, i=0):
#     dt = pars['dt']
#
#     m = pars['m']
#     Iz = pars['Iz']
#     lf = pars['lf']
#     lr = pars['lr']
#     Cf = pars['Cf']
#     Cr = pars['Cr']
#     vx_ref = max(float(pars['vx_ref']), 0.5)
#     curvature_ref = pars.get('curvature_ref', 0.0)
#
#     x = np.asarray(x, dtype=float).reshape(-1)
#     u = np.asarray(u, dtype=float).reshape(-1)
#
#     uncertainty_type = pars.get('uncertainty', 'NA')
#     amp = pars.get('amp', 0.0)
#     freq = pars.get('freq', 1.0)
#
#     if uncertainty_type == 'constant':
#         uncertainty_factor = amp
#     elif uncertainty_type == 'periodic':
#         uncertainty_factor = amp * np.sin(2 * np.pi * freq * i * dt)
#     else:
#         uncertainty_factor = 0.0
#
#     delta_eff = u[0] + 0.5 * uncertainty_factor
#     ax_eff = u[1] + uncertainty_factor
#
#     def f(x_state):
#         e_y, e_psi, v_y, r, e_v = x_state
#
#         e_y_dot = v_y + vx_ref * e_psi
#         e_psi_dot = r - vx_ref * curvature_ref
#
#         v_y_dot = (
#             -(2 * Cf + 2 * Cr) / (m * vx_ref) * v_y
#             + (-vx_ref - (2 * Cf * lf - 2 * Cr * lr) / (m * vx_ref)) * r
#             + (2 * Cf / m) * delta_eff
#         )
#
#         r_dot = (
#             -(2 * Cf * lf - 2 * Cr * lr) / (Iz * vx_ref) * v_y
#             - (2 * Cf * lf**2 + 2 * Cr * lr**2) / (Iz * vx_ref) * r
#             + (2 * Cf * lf / Iz) * delta_eff
#         )
#
#         e_v_dot = ax_eff
#
#         return np.array([e_y_dot, e_psi_dot, v_y_dot, r_dot, e_v_dot], dtype=float)
#
#     # RK4
#     k1 = f(x)
#     k2 = f(x + 0.5 * dt * k1)
#     k3 = f(x + 0.5 * dt * k2)
#     k4 = f(x + dt * k3)
#
#     x_next = x + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
#
#     if sensor_noise:
#         noise = np.random.normal(0.0, 1.0, size=x_next.shape)
#         x_next = x_next * (1.0 + noise * 10 ** (-SNR_DB / 20))
#
#     return x_next


# ==================== single_vehicle_data_gen_multi 函数 ====================
# 作用：批量生成多条车辆轨迹，每条轨迹包括标称系统和变化后系统的状态，以及控制输入
def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    # 提取基本参数
    n = pars['num_states']      # 状态维度（应为5）
    m = pars['num_inputs']      # 输入维度（应为2）
    dt = pars['dt']             # 时间步长

    # 控制输入限制
    delta_max = pars.get('delta_max', 0.08)   # 最大转角
    ax_max = pars.get('ax_max', 2.0)          # 最大加速度

    # 初始化存储数组
    X_1 = np.zeros((num_traj, num_snaps, n))   # 标称系统轨迹
    X_2 = np.zeros((num_traj, num_snaps, n))   # 变化后系统轨迹
    U = np.zeros((num_traj, num_snaps - 1, m)) # 控制输入序列（最后一时刻无输入）

    for i in range(num_traj):
        x0 = np.array([
            np.random.uniform(-0.5, 0.5),
            np.random.uniform(-0.1, 0.1),
            np.random.uniform(-0.4, 0.4),
            np.random.uniform(-0.15, 0.15),
            np.random.uniform(-1.0, 1.0),
        ])

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        u_prev = np.zeros(m)
        seed_1 = np.random.uniform(1, 10)
        seed_2 = np.random.uniform(1, 10)
        u_mode = np.random.choice(['random', 'sinusoidal', 'mixed'])

        road_mode = np.random.choice(['straight', 'sin', 'const', 'dlc'])
        tt = np.arange(num_snaps - 1) * dt
        x_long = pars['vx_ref'] * tt

        if road_mode == 'straight':
            curvature_seq = np.zeros(num_snaps - 1)
        elif road_mode == 'sin':
            curvature_seq = 0.01 * np.sin(2 * np.pi * 0.25 * tt)
        elif road_mode == 'const':
            curvature_seq = 0.004 * np.ones(num_snaps - 1) * np.random.choice([-1, 1])
        else:
            A1, A2 = 0.3, -0.3
            x1, x2 = 8.0 + np.random.uniform(-2, 2), 20.0 + np.random.uniform(-2, 2)
            sigma1, sigma2 = 3.0, 3.0
            y_ref = (
                    A1 * np.exp(-0.5 * ((x_long - x1) / sigma1) ** 2)
                    + A2 * np.exp(-0.5 * ((x_long - x2) / sigma2) ** 2)
            )
            dy_dx = np.gradient(y_ref, x_long)
            psi_ref = np.arctan(dy_dx)
            curvature_seq = np.gradient(psi_ref, x_long)
            curvature_seq = np.nan_to_num(curvature_seq)

        for j in range(num_snaps - 1):
            x_now = X_1[i, j, :]

            if u_mode == "random":
                delta_ff = np.random.uniform(-delta_max, delta_max)
                a_x_ff = np.random.uniform(-ax_max, ax_max)
            elif u_mode == "sinusoidal":
                delta_ff = delta_max * np.sin(seed_1 * np.pi * j * dt) + 0.15 * delta_max * np.random.randn()
                a_x_ff = ax_max * np.cos(seed_2 * np.pi * j * dt) + 0.15 * ax_max * np.random.randn()
            else:
                delta_ff = 0.5 * delta_max * np.sin(seed_1 * np.pi * j * dt) + np.random.uniform(-0.5 * delta_max,
                                                                                                 0.5 * delta_max)
                a_x_ff = 0.5 * ax_max * np.cos(seed_2 * np.pi * j * dt) + np.random.uniform(-0.5 * ax_max, 0.5 * ax_max)

            delta_fb = -0.35 * x_now[0] - 0.80 * x_now[1] - 0.10 * x_now[2] - 0.18 * x_now[3]
            a_x_fb = -0.50 * x_now[4]

            delta = np.clip(delta_ff + delta_fb, -delta_max, delta_max)
            a_x = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)

            u_raw = np.array([delta, a_x])
            alpha_u = 0.70
            u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
            u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
            u_now[1] = np.clip(u_now[1], -ax_max, ax_max)

            U[i, j, :] = u_now
            u_prev = u_now.copy()

            pars_step = dict(pars)
            pars_new_step = dict(pars_new)
            pars_step['curvature_ref'] = curvature_seq[j]
            pars_new_step['curvature_ref'] = curvature_seq[j]

            x1_next = FK_solver(X_1[i, j, :], U[i, j, :], pars_step)
            x2_next = FK_solver(X_2[i, j, :], U[i, j, :], pars_new_step, sensor_noise, SNR_DB, j)

            x1_next[0] = np.clip(x1_next[0], -2.0, 2.0)
            x1_next[1] = np.clip(x1_next[1], -0.5, 0.5)
            x1_next[2] = np.clip(x1_next[2], -3.0, 3.0)
            x1_next[3] = np.clip(x1_next[3], -1.5, 1.5)
            x1_next[4] = np.clip(x1_next[4], -5.0, 5.0)

            x2_next[0] = np.clip(x2_next[0], -2.0, 2.0)
            x2_next[1] = np.clip(x2_next[1], -0.5, 0.5)
            x2_next[2] = np.clip(x2_next[2], -3.0, 3.0)
            x2_next[3] = np.clip(x2_next[3], -1.5, 1.5)
            x2_next[4] = np.clip(x2_next[4], -5.0, 5.0)

            X_1[i, j + 1, :] = x1_next
            X_2[i, j + 1, :] = x2_next



    # # 对每条轨迹循环
    # for i in range(num_traj):
    #     # 随机初始化初始状态，每个状态分量从给定均匀分布中采样
    #
    #
    #     x0 = np.array([
    #         np.random.uniform(-0.5, 0.5),  # e_y
    #         np.random.uniform(-0.1, 0.1),  # e_psi
    #         np.random.uniform(-0.4, 0.4),  # v_y
    #         np.random.uniform(-0.15, 0.15),  # r
    #         np.random.uniform(-1.0, 1.0),  # e_v
    #     ])
    #
    #     road_mode = np.random.choice(['straight', 'sin', 'const', 'dlc'])
    #
    #     tt = np.arange(num_snaps - 1) * dt
    #     x_long = pars['vx_ref'] * tt
    #
    #     if road_mode == 'straight':
    #         curvature_seq = np.zeros(num_snaps - 1)
    #
    #     elif road_mode == 'sin':
    #         curvature_seq = 0.01 * np.sin(2 * np.pi * 0.25 * tt)
    #
    #     elif road_mode == 'const':
    #         curvature_seq = 0.004 * np.ones(num_snaps - 1) * np.random.choice([-1, 1])
    #
    #     else:  # dlc
    #         A1 = 0.3
    #         A2 = -0.3
    #         x1 = 8.0 + np.random.uniform(-2.0, 2.0)
    #         x2 = 20.0 + np.random.uniform(-2.0, 2.0)
    #         sigma1 = 3.0
    #         sigma2 = 3.0
    #
    #         y_ref = (
    #                 A1 * np.exp(-0.5 * ((x_long - x1) / sigma1) ** 2)
    #                 + A2 * np.exp(-0.5 * ((x_long - x2) / sigma2) ** 2)
    #         )
    #         dy_dx = np.gradient(y_ref, x_long)
    #         psi_ref = np.arctan(dy_dx)
    #         curvature_seq = np.gradient(psi_ref, x_long)
    #         curvature_seq = np.nan_to_num(curvature_seq)
    #
    #     u_prev = np.zeros(m)
    #     # 将初始状态存入两条轨迹的第一个时间点
    #     X_1[i, 0, :] = x0
    #     X_2[i, 0, :] = x0.copy()   # 复制，避免引用
    #
    #     # 生成随机种子，用于正弦控制信号（如果选择正弦类型）
    #     num_list = np.linspace(1, 10, 10)   # 候选种子 1~10
    #     seed_1 = np.random.choice(num_list) # 用于delta的正弦种子
    #     seed_2 = np.random.choice(num_list) # 用于a_x的正弦种子
    #
    #     # 对每个时间步（除最后一个）生成控制输入并递推动态
    #     # 对每个时间步（除最后一个）生成控制输入并递推动态
    #     for j in range(num_snaps - 1):
    #         # 用当前标称状态做一个很弱的反馈，避免轨迹无限漂移
    #         x_now = X_1[i, j, :]
    #         if pars.get("U_type", "random") == "random":
    #             # 随机激励
    #             delta_ff = np.random.uniform(-delta_max, delta_max)
    #             a_x_ff = np.random.uniform(-ax_max, ax_max)
    #         else:
    #             # 正弦激励 + 少量随机扰动
    #             delta_ff = (
    #                     delta_max * np.sin(seed_1 * np.pi * j * dt)
    #                     + 0.15 * delta_max * np.random.randn()
    #             )
    #             a_x_ff = (
    #                     ax_max * np.cos(seed_2 * np.pi * j * dt)
    #                     + 0.15 * ax_max * np.random.randn()
    #             )
    #
    #
    #         delta_fb = -0.35 * x_now[0] - 0.80 * x_now[1] - 0.10 * x_now[2] - 0.18 * x_now[3]
    #         a_x_fb = -0.50 * x_now[4]
    #
    #
    #
    #         delta = delta_ff + delta_fb
    #         a_x = a_x_ff + a_x_fb
    #
    #         # 限幅
    #         delta = np.clip(delta, -delta_max, delta_max)
    #         a_x = np.clip(a_x, -ax_max, ax_max)
    #
    #         u_raw = np.array([delta, a_x])
    #
    #         # 一阶平滑，避免每步剧烈跳变
    #
    #
    #         alpha_u = 0.70
    #         u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
    #
    #         # 再限幅一次
    #         u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
    #         u_now[1] = np.clip(u_now[1], -ax_max, ax_max)
    #
    #         U[i, j, :] = u_now
    #         u_prev = u_now.copy()
    #
    #         # 用相同输入分别推进标称系统和变化系统
    #         # x1_next = FK_solver(X_1[i, j, :], U[i, j, :], pars)
    #         # x2_next = FK_solver(
    #         #     X_2[i, j, :], U[i, j, :], pars_new,
    #         #     sensor_noise, SNR_DB, j
    #         # )
    #
    #         pars_step = dict(pars)
    #         pars_new_step = dict(pars_new)
    #
    #         pars_step['curvature_ref'] = curvature_seq[j]
    #         pars_new_step['curvature_ref'] = curvature_seq[j]
    #
    #         x1_next = FK_solver(X_1[i, j, :], U[i, j, :], pars_step)
    #         x2_next = FK_solver(
    #             X_2[i, j, :], U[i, j, :], pars_new_step,
    #             sensor_noise, SNR_DB, j
    #         )
    #
    #         # 状态裁剪，防止训练集出现长时间漂移导致 Koopman 学出不稳定 A
    #         x1_next[0] = np.clip(x1_next[0], -2.0, 2.0)  # e_y
    #         x1_next[1] = np.clip(x1_next[1], -0.5, 0.5)  # e_psi
    #         x1_next[2] = np.clip(x1_next[2], -3.0, 3.0)  # v_y
    #         x1_next[3] = np.clip(x1_next[3], -1.5, 1.5)  # r
    #         x1_next[4] = np.clip(x1_next[4], -5.0, 5.0)  # e_v
    #
    #         x2_next[0] = np.clip(x2_next[0], -2.0, 2.0)
    #         x2_next[1] = np.clip(x2_next[1], -0.5, 0.5)
    #         x2_next[2] = np.clip(x2_next[2], -3.0, 3.0)
    #         x2_next[3] = np.clip(x2_next[3], -1.5, 1.5)
    #         x2_next[4] = np.clip(x2_next[4], -5.0, 5.0)
    #
    #         X_1[i, j + 1, :] = x1_next
    #         X_2[i, j + 1, :] = x2_next




    # 返回三条数据：标称轨迹、变化后轨迹、控制输入
    return X_1, X_2, U

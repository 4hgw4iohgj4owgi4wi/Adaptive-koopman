import numpy as np


# ============================================================
# Frenet 参考路径生成
# ============================================================
def build_reference_path(num_snaps, dt, vx_ref, road_mode='straight'):
    """
    生成 Frenet 参考路径离散点:
        s_ref: 路径弧长
        x_ref_global: 全局 x
        y_ref_global: 全局 y
        psi_ref: 参考航向
        curvature_ref: 参考曲率

    参数
    ----
    num_snaps : int
        总采样点数
    dt : float
        采样时间
    vx_ref : float
        标称纵向速度，用于生成路径长度
    road_mode : str
        ['straight', 'sin', 'const', 'dlc']

    返回
    ----
    path_dict : dict
        {
            's_ref': ...,
            'x_ref': ...,
            'y_ref': ...,
            'psi_ref': ...,
            'curvature_ref': ...
        }
    """
    tt = np.arange(num_snaps) * dt
    x_long = vx_ref * tt

    if road_mode == 'straight':
        y_ref = np.zeros_like(x_long)

    elif road_mode == 'sin':
        # 小幅正弦道路
        y_ref = 0.6 * np.sin(2 * np.pi * 0.05 * x_long)

    elif road_mode == 'const':
        # 这里用一个近似恒曲率路径：圆弧近似
        # y = R - sqrt(R^2 - x^2)，对小范围可近似常曲率
        kappa_const = 0.004 * np.random.choice([-1, 1])
        R = 1.0 / max(abs(kappa_const), 1e-6)
        x_clip = np.clip(x_long, -0.9 * R, 0.9 * R)
        y_ref = np.sign(kappa_const) * (R - np.sqrt(np.maximum(R**2 - x_clip**2, 1e-8)))

    elif road_mode == 'dlc':
        # 双移线
        A1, A2 = 0.8, -0.8
        x1 = 12.0 + np.random.uniform(-2.0, 2.0)
        x2 = 28.0 + np.random.uniform(-2.0, 2.0)
        sigma1, sigma2 = 4.0, 4.0
        y_ref = (
            A1 * np.exp(-0.5 * ((x_long - x1) / sigma1) ** 2) +
            A2 * np.exp(-0.5 * ((x_long - x2) / sigma2) ** 2)
        )
    else:
        raise ValueError(f"Unsupported road_mode: {road_mode}")

    dx = np.gradient(x_long)
    dy = np.gradient(y_ref)

    ds = np.sqrt(dx**2 + dy**2)
    s_ref = np.cumsum(ds)
    s_ref[0] = 0.0

    psi_ref = np.arctan2(dy, dx)

    # 曲率 κ = dψ/ds
    dpsi = np.gradient(psi_ref)
    curvature_ref = dpsi / np.maximum(np.gradient(s_ref), 1e-8)
    curvature_ref = np.nan_to_num(curvature_ref)

    return {
        's_ref': s_ref,
        'x_ref': x_long,
        'y_ref': y_ref,
        'psi_ref': psi_ref,
        'curvature_ref': curvature_ref
    }


def interp_path_value(s, s_ref, value_ref):
    """
    对路径量做一维插值，超出边界时钳制到端点
    """
    s_clamped = np.clip(s, s_ref[0], s_ref[-1])
    return np.interp(s_clamped, s_ref, value_ref)


# ============================================================
# FK_solver: Frenet 坐标系下真实状态车辆动力学
# 状态: x = [s, e_y, e_psi, v_x, v_y, r]
# 输入: u = [delta, a_x]
# ============================================================
def FK_solver(x, u, pars, sensor_noise=False, SNR_DB=0, i=0):
    dt = pars['dt']

    m = pars['m']
    Iz = pars['Iz']
    lf = pars['lf']
    lr = pars['lr']
    Cf = pars['Cf']
    Cr = pars['Cr']

    x = np.asarray(x, dtype=float).reshape(-1)
    u = np.asarray(u, dtype=float).reshape(-1)

    if x.size != 6:
        raise ValueError(f"FK_solver expects 6-state input [s, e_y, e_psi, v_x, v_y, r], got size {x.size}")

    if u.size != 2:
        raise ValueError(f"FK_solver expects 2-input input [delta, a_x], got size {u.size}")

    # 不确定性设置
    uncertainty_type = pars.get('uncertainty', 'NA')
    amp = pars.get('amp', 0.0)
    freq = pars.get('freq', 1.0)

    if uncertainty_type == 'constant':
        uncertainty_factor = amp
    elif uncertainty_type == 'periodic':
        uncertainty_factor = amp * np.sin(2 * np.pi * freq * i * dt)
    else:
        uncertainty_factor = 0.0

    # 有效控制输入
    delta_eff = u[0] + 0.5 * uncertainty_factor
    ax_eff = u[1] + uncertainty_factor

    # 路径插值数据
    s_ref_arr = pars.get('s_ref', None)
    curvature_ref_arr = pars.get('curvature_ref', None)

    if s_ref_arr is None or curvature_ref_arr is None:
        raise ValueError("pars must contain 's_ref' and 'curvature_ref' for Frenet model.")

    s_ref_arr = np.asarray(s_ref_arr, dtype=float)
    curvature_ref_arr = np.asarray(curvature_ref_arr, dtype=float)

    def f(x_state):
        s, e_y, e_psi, vx, v_y, r = x_state

        vx = max(vx, 0.5)
        kappa = interp_path_value(s, s_ref_arr, curvature_ref_arr)

        denom = max(1.0 - kappa * e_y, 1e-4)

        # Frenet 运动学
        s_dot = (vx * np.cos(e_psi) - v_y * np.sin(e_psi)) / denom
        e_y_dot = vx * np.sin(e_psi) + v_y * np.cos(e_psi)
        e_psi_dot = r - kappa * s_dot

        # 单轨横向动力学
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

        # 真实纵向速度动力学
        # 若想更完整可改成 vx_dot = ax_eff + r * v_y
        vx_dot = ax_eff

        return np.array([s_dot, e_y_dot, e_psi_dot, vx_dot, v_y_dot, r_dot], dtype=float)

    # RK4
    k1 = f(x)
    k2 = f(x + 0.5 * dt * k1)
    k3 = f(x + 0.5 * dt * k2)
    k4 = f(x + dt * k3)

    x_next = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    # 传感器噪声
    if sensor_noise:
        noise = np.random.normal(0.0, 1.0, size=x_next.shape)
        x_next = x_next * (1.0 + noise * 10 ** (-SNR_DB / 20))

    return x_next


# ============================================================
# 批量生成多条 Frenet 真实状态车辆轨迹
# X_1: 标称车辆
# X_2: 变化后车辆
# U  : 输入
# 状态: [s, e_y, e_psi, v_x, v_y, r]
# ============================================================
def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    n = pars['num_states']      # 应为 6
    m = pars['num_inputs']      # 应为 2
    dt = pars['dt']

    if n != 6:
        raise ValueError(f"For Frenet real-state model, pars['num_states'] must be 6, got {n}")

    delta_max = pars.get('delta_max', 0.08)
    ax_max = pars.get('ax_max', 2.0)

    X_1 = np.zeros((num_traj, num_snaps, n))
    X_2 = np.zeros((num_traj, num_snaps, n))
    U = np.zeros((num_traj, num_snaps - 1, m))

    for i in range(num_traj):
        # ---------- 初始状态 ----------
        # x = [s, e_y, e_psi, v_x, v_y, r]
        x0 = np.array([
            0.0,                               # s
            np.random.uniform(-0.5, 0.5),      # e_y
            np.random.uniform(-0.10, 0.10),    # e_psi
            np.random.uniform(
                max(pars['vx_ref'] - 1.0, 0.5),
                pars['vx_ref'] + 1.0
            ),                                 # v_x
            np.random.uniform(-0.4, 0.4),      # v_y
            np.random.uniform(-0.15, 0.15),    # r
        ], dtype=float)

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        u_prev = np.zeros(m)

        seed_1 = np.random.uniform(1, 10)
        seed_2 = np.random.uniform(1, 10)
        u_mode = np.random.choice(['random', 'sinusoidal', 'mixed'])

        road_mode = np.random.choice(['straight', 'sin', 'const', 'dlc'])
        path_data = build_reference_path(
            num_snaps=num_snaps,
            dt=dt,
            vx_ref=float(pars['vx_ref']),
            road_mode=road_mode
        )

        # 为当前轨迹构造 pars_step 基础模板
        pars_base = dict(pars)
        pars_new_base = dict(pars_new)

        pars_base['s_ref'] = path_data['s_ref']
        pars_base['curvature_ref'] = path_data['curvature_ref']

        pars_new_base['s_ref'] = path_data['s_ref']
        pars_new_base['curvature_ref'] = path_data['curvature_ref']

        for j in range(num_snaps - 1):
            x_now = X_1[i, j, :]

            # ---------- 输入前馈 ----------
            if u_mode == "random":
                delta_ff = np.random.uniform(-delta_max, delta_max)
                a_x_ff = np.random.uniform(-ax_max, ax_max)

            elif u_mode == "sinusoidal":
                delta_ff = (
                    delta_max * np.sin(seed_1 * np.pi * j * dt)
                    + 0.15 * delta_max * np.random.randn()
                )
                a_x_ff = (
                    ax_max * np.cos(seed_2 * np.pi * j * dt)
                    + 0.15 * ax_max * np.random.randn()
                )

            else:  # mixed
                delta_ff = (
                    0.5 * delta_max * np.sin(seed_1 * np.pi * j * dt)
                    + np.random.uniform(-0.5 * delta_max, 0.5 * delta_max)
                )
                a_x_ff = (
                    0.5 * ax_max * np.cos(seed_2 * np.pi * j * dt)
                    + np.random.uniform(-0.5 * ax_max, 0.5 * ax_max)
                )

            # ---------- 弱反馈，防止漂移 ----------
            # x = [s, e_y, e_psi, v_x, v_y, r]
            delta_fb = (
                -0.35 * x_now[1]   # e_y
                -0.80 * x_now[2]   # e_psi
                -0.10 * x_now[4]   # v_y
                -0.18 * x_now[5]   # r
            )

            a_x_fb = -0.50 * (x_now[3] - pars['vx_ref'])  # 速度保持到 vx_ref

            delta = np.clip(delta_ff + delta_fb, -delta_max, delta_max)
            a_x = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)

            # ---------- 输入平滑 ----------
            u_raw = np.array([delta, a_x], dtype=float)
            alpha_u = 0.70
            u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
            u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
            u_now[1] = np.clip(u_now[1], -ax_max, ax_max)

            U[i, j, :] = u_now
            u_prev = u_now.copy()

            # ---------- 推进一步 ----------
            x1_next = FK_solver(
                X_1[i, j, :],
                U[i, j, :],
                pars_base,
                sensor_noise=False,
                SNR_DB=SNR_DB,
                i=j
            )

            x2_next = FK_solver(
                X_2[i, j, :],
                U[i, j, :],
                pars_new_base,
                sensor_noise=sensor_noise,
                SNR_DB=SNR_DB,
                i=j
            )

            # ---------- 状态裁剪 ----------
            # 状态: [s, e_y, e_psi, v_x, v_y, r]
            s_max = path_data['s_ref'][-1]
            x1_next[0] = np.clip(x1_next[0], 0.0, s_max)
            x1_next[1] = np.clip(x1_next[1], -3.0, 3.0)
            x1_next[2] = np.clip(x1_next[2], -0.8, 0.8)
            x1_next[3] = np.clip(x1_next[3], 0.5, 20.0)
            x1_next[4] = np.clip(x1_next[4], -5.0, 5.0)
            x1_next[5] = np.clip(x1_next[5], -2.0, 2.0)

            x2_next[0] = np.clip(x2_next[0], 0.0, s_max)
            x2_next[1] = np.clip(x2_next[1], -3.0, 3.0)
            x2_next[2] = np.clip(x2_next[2], -0.8, 0.8)
            x2_next[3] = np.clip(x2_next[3], 0.5, 20.0)
            x2_next[4] = np.clip(x2_next[4], -5.0, 5.0)
            x2_next[5] = np.clip(x2_next[5], -2.0, 2.0)

            X_1[i, j + 1, :] = x1_next
            X_2[i, j + 1, :] = x2_next

    return X_1, X_2, U
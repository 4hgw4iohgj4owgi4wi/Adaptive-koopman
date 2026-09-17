import numpy as np


# ============================================================
# 工具函数
# ============================================================

def interp_path_value(s, s_ref, value_ref):
    """
    对路径量做一维插值，超出边界时钳制到端点
    """
    s_ref = np.asarray(s_ref, dtype=float).reshape(-1)
    value_ref = np.asarray(value_ref, dtype=float).reshape(-1)

    if s_ref.ndim != 1 or value_ref.ndim != 1 or s_ref.size != value_ref.size:
        raise ValueError("s_ref and value_ref must be 1D arrays with the same length.")

    if s_ref.size < 2:
        raise ValueError("s_ref must contain at least 2 points.")

    if np.any(np.diff(s_ref) < 0):
        raise ValueError("s_ref must be nondecreasing for interpolation.")

    s_clamped = np.clip(s, s_ref[0], s_ref[-1])
    return np.interp(s_clamped, s_ref, value_ref)


def _get_rng(pars=None):
    """
    从 pars 中取随机数生成器；若没有则新建一个。
    兼容：
      - pars['rng'] = np.random.Generator
      - pars['seed'] = int
    """
    pars = {} if pars is None else pars

    rng = pars.get('rng', None)
    if rng is not None:
        return rng

    seed = pars.get('seed', None)
    if seed is not None:
        return np.random.default_rng(seed)

    return np.random.default_rng()


def _compute_path_geometry(x_ref, y_ref):
    """
    从离散路径点计算：
      s_ref, psi_ref, curvature_ref

    说明：
    - s_ref 用相邻点距离累计，避免 cumsum(gradient) 的首点误差
    - psi_ref 使用 unwrap，避免角度跳变
    - curvature_ref 使用平面曲线公式，更稳
    """
    x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
    y_ref = np.asarray(y_ref, dtype=float).reshape(-1)

    if x_ref.size != y_ref.size or x_ref.size < 2:
        raise ValueError("x_ref and y_ref must have the same length >= 2.")

    # 弧长
    ds_seg = np.sqrt(np.diff(x_ref)**2 + np.diff(y_ref)**2)
    s_ref = np.concatenate(([0.0], np.cumsum(ds_seg)))

    # 一阶/二阶导
    dx = np.gradient(x_ref)
    dy = np.gradient(y_ref)
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)

    # 航向角
    psi_ref = np.unwrap(np.arctan2(dy, dx))

    # 曲率公式: kappa = (x'y'' - y'x'') / (x'^2 + y'^2)^(3/2)
    den = np.maximum((dx**2 + dy**2)**1.5, 1e-8)
    curvature_ref = (dx * ddy - dy * ddx) / den
    curvature_ref = np.nan_to_num(curvature_ref, nan=0.0, posinf=0.0, neginf=0.0)

    return s_ref, psi_ref, curvature_ref


def _clip_frenet_state(x, s_max):
    """
    状态裁剪
    x = [s, e_y, e_psi, v_x, v_y, r]
    """
    x = np.asarray(x, dtype=float).copy()

    x[0] = np.clip(x[0], 0.0, s_max)
    x[1] = np.clip(x[1], -3.0, 3.0)
    x[2] = np.clip(x[2], -0.8, 0.8)
    x[3] = np.clip(x[3], 0.5, 20.0)
    x[4] = np.clip(x[4], -5.0, 5.0)
    x[5] = np.clip(x[5], -2.0, 2.0)

    return x


def _add_sensor_noise(x, pars, SNR_DB=0, rng=None):
    """
    更合理的加性传感器噪声。

    优先使用 pars['sensor_std']，例如：
        sensor_std = np.array([0.02, 0.01, 0.005, 0.05, 0.02, 0.01])

    若未提供，则根据 SNR_DB 和默认量纲构造一个近似标准差。
    """
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng() if rng is None else rng

    sensor_std = pars.get('sensor_std', None)

    if sensor_std is not None:
        sensor_std = np.asarray(sensor_std, dtype=float).reshape(-1)
        if sensor_std.size != x.size:
            raise ValueError(f"sensor_std size must be {x.size}, got {sensor_std.size}")
        return x + rng.normal(0.0, sensor_std, size=x.shape)

    # 若没给 sensor_std，则用一个默认状态尺度 + SNR_DB 构造
    # 这里只是兜底逻辑，推荐显式给 sensor_std
    state_scale = np.array([10.0, 0.5, 0.1, 8.0, 0.5, 0.2], dtype=float)
    snr_linear = 10 ** (SNR_DB / 20.0)
    std = state_scale / max(snr_linear, 1e-6)

    return x + rng.normal(0.0, std, size=x.shape)


# ============================================================
# Frenet 参考路径生成
# ============================================================
def build_reference_path(num_snaps, dt, vx_ref, road_mode='straight', rng=None):
    if rng is None:
        rng = np.random.default_rng()

    if num_snaps < 2:
        raise ValueError("num_snaps must be >= 2")
    if dt <= 0:
        raise ValueError("dt must be positive")
    if vx_ref <= 0:
        raise ValueError("vx_ref must be positive")

    tt = np.arange(num_snaps, dtype=float) * dt
    s_nominal = vx_ref * tt

    if road_mode == 'straight':
        x_ref = s_nominal
        y_ref = np.zeros_like(x_ref)

    elif road_mode == 'sin':
        x_ref = s_nominal
        amp = 0.4 + rng.uniform(-0.1, 0.1)
        freq = 0.04 + rng.uniform(-0.01, 0.01)
        y_ref = amp * np.sin(2 * np.pi * freq * x_ref)

    elif road_mode == 'const':
        kappa_const = 0.0035 * rng.choice([-1, 1])
        theta = kappa_const * s_nominal
        x_ref = np.sin(theta) / kappa_const
        y_ref = (1.0 - np.cos(theta)) / kappa_const

    elif road_mode == 'dlc':
        x_ref = s_nominal
        # 🔴 修改点 3：丰富双移线的几何参数分布
        # 随机决定是向左变道还是向右变道
        direction = rng.choice([-1.0, 1.0])

        # 侧移幅度：从 0.3 到 1.0 不等，模拟不同车道宽度和避障深度
        A1 = rng.uniform(0.3, 1.0) * direction
        A2 = -A1  # 移回原车道

        # 变道发生的纵向位置点：打乱双移线的长度结构
        x1 = rng.uniform(20.0, 40.0)
        x2 = x1 + rng.uniform(30.0, 50.0)  # 保持回变道的距离随机

        # 变道的急缓程度：sigma 越小越急
        sigma1 = rng.uniform(10.0, 20.0)
        sigma2 = rng.uniform(10.0, 20.0)

        y_ref = (
                A1 * np.exp(-0.5 * ((x_ref - x1) / sigma1) ** 2) +
                A2 * np.exp(-0.5 * ((x_ref - x2) / sigma2) ** 2)
        )

        # # 更贴近你测试时 100m DLC 的形状
        # A1 = 0.4 + rng.uniform(-0.08, 0.08)
        # A2 = -0.4 + rng.uniform(-0.08, 0.08)
        #
        # x1 = 30.0 + rng.uniform(-3.0, 3.0)
        # x2 = 70.0 + rng.uniform(-3.0, 3.0)
        #
        # sigma1 = 16.0 + rng.uniform(-2.0, 2.0)
        # sigma2 = 16.0 + rng.uniform(-2.0, 2.0)
        #
        # y_ref = (
        #     A1 * np.exp(-0.5 * ((x_ref - x1) / sigma1) ** 2) +
        #     A2 * np.exp(-0.5 * ((x_ref - x2) / sigma2) ** 2)
        # )

    else:
        raise ValueError(f"Unsupported road_mode: {road_mode}")

    s_ref, psi_ref, curvature_ref = _compute_path_geometry(x_ref, y_ref)

    return {
        's_ref': s_ref,
        'x_ref': x_ref,
        'y_ref': y_ref,
        'psi_ref': psi_ref,
        'curvature_ref': curvature_ref
    }
# def build_reference_path(num_snaps, dt, vx_ref, road_mode='straight'):
#     """
#     生成 Frenet 参考路径离散点:
#         s_ref: 路径弧长
#         x_ref_global: 全局 x
#         y_ref_global: 全局 y
#         psi_ref: 参考航向
#         curvature_ref: 参考曲率
#
#     参数
#     ----
#     num_snaps : int
#         总采样点数
#     dt : float
#         采样时间
#     vx_ref : float
#         标称纵向速度，用于生成路径长度
#     road_mode : str
#         ['straight', 'sin', 'const', 'dlc']
#
#     返回
#     ----
#     path_dict : dict
#         {
#             's_ref': ...,
#             'x_ref': ...,
#             'y_ref': ...,
#             'psi_ref': ...,
#             'curvature_ref': ...
#         }
#     """
#     if num_snaps < 2:
#         raise ValueError("num_snaps must be >= 2")
#     if dt <= 0:
#         raise ValueError("dt must be positive")
#     if vx_ref <= 0:
#         raise ValueError("vx_ref must be positive")
#
#     # 为保留原接口，这里不新增 rng 参数
#     # 若想完全可复现，可在外部设置 np.random.seed(...)
#     tt = np.arange(num_snaps, dtype=float) * dt
#     s_nominal = vx_ref * tt
#
#     if road_mode == 'straight':
#         x_ref = s_nominal
#         y_ref = np.zeros_like(x_ref)
#
#     elif road_mode == 'sin':
#         x_ref = s_nominal
#         y_ref = 0.6 * np.sin(2 * np.pi * 0.05 * x_ref)
#
#     elif road_mode == 'const':
#         # 更合理的“恒曲率路径”参数化
#         kappa_const = 0.004 * np.random.choice([-1, 1])
#         if abs(kappa_const) < 1e-10:
#             x_ref = s_nominal
#             y_ref = np.zeros_like(s_nominal)
#         else:
#             theta = kappa_const * s_nominal
#             x_ref = np.sin(theta) / kappa_const
#             y_ref = (1.0 - np.cos(theta)) / kappa_const
#
#     elif road_mode == 'dlc':
#         # 双移线：仍使用双高斯，但保持足够平滑
#         x_ref = s_nominal
#         A1, A2 = 0.8, -0.8
#         x1 = 12.0 + np.random.uniform(-2.0, 2.0)
#         x2 = 28.0 + np.random.uniform(-2.0, 2.0)
#         sigma1, sigma2 = 4.0, 4.0
#
#         y_ref = (
#             A1 * np.exp(-0.5 * ((x_ref - x1) / sigma1) ** 2) +
#             A2 * np.exp(-0.5 * ((x_ref - x2) / sigma2) ** 2)
#         )
#     else:
#         raise ValueError(f"Unsupported road_mode: {road_mode}")
#
#     s_ref, psi_ref, curvature_ref = _compute_path_geometry(x_ref, y_ref)
#
#     return {
#         's_ref': s_ref,
#         'x_ref': x_ref,
#         'y_ref': y_ref,
#         'psi_ref': psi_ref,
#         'curvature_ref': curvature_ref
#     }


# ============================================================
# FK_solver: Frenet 坐标系下真实状态车辆动力学
# 状态: x = [s, e_y, e_psi, v_x, v_y, r]
# 输入: u = [delta, a_x]
# ============================================================

def FK_solver(x, u, pars, sensor_noise=False, SNR_DB=0, i=0):
    dt = pars['dt']

    mass = pars['m']
    Iz = pars['Iz']
    lf = pars['lf']
    lr = pars['lr']
    Cf = pars['Cf']
    Cr = pars['Cr']

    rng = _get_rng(pars)

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

        # 避免低速奇异
        vx_safe = max(vx, 0.5)
        kappa = interp_path_value(s, s_ref_arr, curvature_ref_arr)

        # raw_denom = 1.0 - kappa * e_y
        # denom = max(raw_denom, 1e-4)

        raw_denom = 1.0 - kappa * e_y
        if abs(raw_denom) < 1e-3:
            denom = np.sign(raw_denom) * 1e-3 if raw_denom != 0 else 1e-3
        else:
            denom = raw_denom

        # Frenet 运动学
        s_dot = (vx_safe * np.cos(e_psi) - v_y * np.sin(e_psi)) / denom
        e_y_dot = vx_safe * np.sin(e_psi) + v_y * np.cos(e_psi)
        e_psi_dot = r - kappa * s_dot

        # 线性单轨横向动力学
        v_y_dot = (
            -(2 * Cf + 2 * Cr) / (mass * vx_safe) * v_y
            + (-vx_safe - (2 * Cf * lf - 2 * Cr * lr) / (mass * vx_safe)) * r
            + (2 * Cf / mass) * delta_eff
        )

        r_dot = (
            -(2 * Cf * lf - 2 * Cr * lr) / (Iz * vx_safe) * v_y
            - (2 * Cf * lf**2 + 2 * Cr * lr**2) / (Iz * vx_safe) * r
            + (2 * Cf * lf / Iz) * delta_eff
        )

        # 更完整的纵向动力学
        vx_dot = ax_eff + r * v_y

        return np.array([s_dot, e_y_dot, e_psi_dot, vx_dot, v_y_dot, r_dot], dtype=float)

    # RK4
    k1 = f(x)
    k2 = f(x + 0.5 * dt * k1)
    k3 = f(x + 0.5 * dt * k2)
    k4 = f(x + dt * k3)

    x_next = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    # 传感器噪声：改为加性噪声
    if sensor_noise:
        x_next = _add_sensor_noise(x_next, pars, SNR_DB=SNR_DB, rng=rng)

    return x_next


# ============================================================
# 批量生成多条 Frenet 真实状态车辆轨迹
# X_1: 标称车辆
# X_2: 变化后车辆
# U  : 输入
# 状态: [s, e_y, e_psi, v_x, v_y, r]
# ============================================================
def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    """
    批量生成多条 Frenet 真实状态车辆轨迹
    X_1: 标称车辆
    X_2: 参数变化后车辆
    U  : 输入
    状态: [s, e_y, e_psi, v_x, v_y, r]

    相比原版本的改动：
    1. 路径类型按概率采样，重点覆盖 DLC
    2. DLC 路径参数更贴近测试时的 100m 双移线
    3. 初始状态采用“两层采样”：大多数接近闭环工作点，少量覆盖恢复区
    4. 输入模式更接近闭环控制风格
    5. 加入基于路径曲率的 steering feedforward
    6. 允许 s 超过参考路径末端，由插值函数自动钳制路径几何，避免 s 被硬卡死
    7. 支持通过 pars 配置采样分布
    """

    n_states = pars['num_states']
    n_inputs = pars['num_inputs']
    dt = pars['dt']

    if n_states != 6:
        raise ValueError(f"For Frenet real-state model, pars['num_states'] must be 6, got {n_states}")
    if n_inputs != 2:
        raise ValueError(f"For Frenet real-state model, pars['num_inputs'] must be 2, got {n_inputs}")

    rng = _get_rng(pars)

    delta_max = float(pars.get('delta_max', 0.08))
    ax_max = float(pars.get('ax_max', 2.0))
    vx_ref = float(pars['vx_ref'])

    # 路径模式配置：默认偏向 DLC
    road_modes = pars.get('road_modes', ['straight', 'sin', 'const', 'dlc'])
    road_mode_probs = np.asarray(
        pars.get('road_mode_probs', [0.15, 0.15, 0.10, 0.60]),
        dtype=float
    )
    if len(road_modes) != len(road_mode_probs):
        raise ValueError("road_modes and road_mode_probs must have the same length.")
    road_mode_probs = road_mode_probs / np.sum(road_mode_probs)

    # 输入模式配置：更偏向闭环风格
    u_modes = pars.get('u_modes', ['feedback_dominant', 'sinusoidal', 'mixed'])
    u_mode_probs = np.asarray(
        pars.get('u_mode_probs', [0.50, 0.30, 0.20]),
        dtype=float
    )
    if len(u_modes) != len(u_mode_probs):
        raise ValueError("u_modes and u_mode_probs must have the same length.")
    u_mode_probs = u_mode_probs / np.sum(u_mode_probs)

    # 允许 s 超出路径终点一点点，避免轨迹末端因为硬裁剪出现假动态
    s_margin = float(pars.get('s_margin', 15.0))

    # 输入平滑系数
    alpha_u = float(pars.get('alpha_u', 0.70))

    X_1 = np.zeros((num_traj, num_snaps, n_states))
    X_2 = np.zeros((num_traj, num_snaps, n_states))
    U = np.zeros((num_traj, num_snaps - 1, n_inputs))

    for i in range(num_traj):
        # ============================================================
        # 1) 当前轨迹：采样路径类型
        # ============================================================
        road_mode = rng.choice(road_modes, p=road_mode_probs)

        path_data = build_reference_path(
            num_snaps=num_snaps,
            dt=dt,
            vx_ref=vx_ref,
            road_mode=road_mode,
            rng=rng  # 需要你把 build_reference_path 扩展为支持 rng 参数
        )

        s_ref_path = np.asarray(path_data['s_ref'], dtype=float)
        kappa_ref_path = np.asarray(path_data['curvature_ref'], dtype=float)
        s_max = float(s_ref_path[-1])

        # ============================================================
        # 2) 初始状态采样
        #    大多数样本靠近闭环工作点，少部分样本用于覆盖恢复区域
        # ============================================================
        if rng.random() < 0.75:
            # 工作点附近
            x0 = np.array([
                0.0,                                # s
                rng.uniform(-0.20, 0.20),          # e_y
                rng.uniform(-0.05, 0.05),          # e_psi
                rng.uniform(vx_ref - 0.4, vx_ref + 0.4),  # v_x
                rng.uniform(-0.15, 0.15),          # v_y
                rng.uniform(-0.08, 0.08),          # r
            ], dtype=float)
        else:
            # 恢复区覆盖
            x0 = np.array([
                0.0,
                rng.uniform(-0.80, 0.80),
                rng.uniform(-0.15, 0.15),
                rng.uniform(max(vx_ref - 1.0, 0.5), vx_ref + 1.0),
                rng.uniform(-0.50, 0.50),
                rng.uniform(-0.20, 0.20),
            ], dtype=float)

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        # ============================================================
        # 3) 当前轨迹输入模式
        # ============================================================
        u_mode = rng.choice(u_modes, p=u_mode_probs)
        u_prev = np.zeros(n_inputs, dtype=float)

        seed_1 = rng.uniform(0.5, 4.0)
        seed_2 = rng.uniform(0.5, 4.0)

        # ============================================================
        # 4) 每条轨迹各自的车辆参数模板
        # ============================================================
        pars_base = dict(pars)
        pars_new_base = dict(pars_new)

        pars_base['rng'] = rng
        pars_new_base['rng'] = rng

        pars_base['s_ref'] = s_ref_path
        pars_base['curvature_ref'] = kappa_ref_path

        pars_new_base['s_ref'] = s_ref_path
        pars_new_base['curvature_ref'] = kappa_ref_path

        # ============================================================
        # 5) 时间推进
        # ============================================================
        for j in range(num_snaps - 1):
            x_now = X_1[i, j, :]

            # 当前参考曲率
            kappa_now = interp_path_value(x_now[0], s_ref_path, kappa_ref_path)

            # --------------------------------------------------------
            # (a) 路径曲率前馈
            #     让训练数据里的操舵结构更像真实路径跟踪控制
            # --------------------------------------------------------
            delta_path_ff = (pars['lf'] + pars['lr']) * kappa_now

            # --------------------------------------------------------
            # (b) 激励项
            # --------------------------------------------------------
            if u_mode == "feedback_dominant":
                delta_ff = 0.15 * delta_max * rng.normal()
                a_x_ff = 0.15 * ax_max * rng.normal()

            elif u_mode == "sinusoidal":
                delta_ff = (
                    0.70 * delta_max * np.sin(seed_1 * np.pi * j * dt)
                    + 0.10 * delta_max * rng.normal()
                )
                a_x_ff = (
                    0.70 * ax_max * np.cos(seed_2 * np.pi * j * dt)
                    + 0.10 * ax_max * rng.normal()
                )

            elif u_mode == "mixed":
                delta_ff = (
                    0.35 * delta_max * np.sin(seed_1 * np.pi * j * dt)
                    + rng.uniform(-0.30 * delta_max, 0.30 * delta_max)
                )
                a_x_ff = (
                    0.35 * ax_max * np.cos(seed_2 * np.pi * j * dt)
                    + rng.uniform(-0.30 * ax_max, 0.30 * ax_max)
                )

            else:
                raise ValueError(f"Unsupported u_mode: {u_mode}")

            # --------------------------------------------------------
            # (c) 弱反馈
            #     防止轨迹完全漂掉，同时保持足够激励
            # --------------------------------------------------------
            # x = [s, e_y, e_psi, v_x, v_y, r]
            delta_fb = (
                -0.35 * x_now[1]
                -0.90 * x_now[2]
                -0.12 * x_now[4]
                -0.20 * x_now[5]
            )

            a_x_fb = -0.60 * (x_now[3] - vx_ref)

            # --------------------------------------------------------
            # (d) 合成控制
            # --------------------------------------------------------
            delta_cmd = delta_path_ff + delta_ff + delta_fb
            ax_cmd = a_x_ff + a_x_fb

            delta_cmd = np.clip(delta_cmd, -delta_max, delta_max)
            ax_cmd = np.clip(ax_cmd, -ax_max, ax_max)

            # --------------------------------------------------------
            # (e) 输入平滑
            # --------------------------------------------------------
            u_raw = np.array([delta_cmd, ax_cmd], dtype=float)
            u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
            u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
            u_now[1] = np.clip(u_now[1], -ax_max, ax_max)

            U[i, j, :] = u_now
            u_prev = u_now.copy()

            # --------------------------------------------------------
            # (f) 推进一步
            # --------------------------------------------------------
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

            # --------------------------------------------------------
            # (g) 状态裁剪
            #     s 不再卡死到 s_max，只限制不为负、且不过分飙大
            # --------------------------------------------------------
            x1_next = np.asarray(x1_next, dtype=float).copy()
            x2_next = np.asarray(x2_next, dtype=float).copy()

            x1_next[0] = np.clip(x1_next[0], 0.0, s_max + s_margin)
            x2_next[0] = np.clip(x2_next[0], 0.0, s_max + s_margin)

            x1_next[1] = np.clip(x1_next[1], -3.0, 3.0)
            x2_next[1] = np.clip(x2_next[1], -3.0, 3.0)

            x1_next[2] = np.clip(x1_next[2], -0.8, 0.8)
            x2_next[2] = np.clip(x2_next[2], -0.8, 0.8)

            x1_next[3] = np.clip(x1_next[3], 0.5, 20.0)
            x2_next[3] = np.clip(x2_next[3], 0.5, 20.0)

            x1_next[4] = np.clip(x1_next[4], -5.0, 5.0)
            x2_next[4] = np.clip(x2_next[4], -5.0, 5.0)

            x1_next[5] = np.clip(x1_next[5], -2.0, 2.0)
            x2_next[5] = np.clip(x2_next[5], -2.0, 2.0)

            X_1[i, j + 1, :] = x1_next
            X_2[i, j + 1, :] = x2_next

    return X_1, X_2, U
# def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
#     n_states = pars['num_states']   # 应为 6
#     n_inputs = pars['num_inputs']   # 应为 2
#     dt = pars['dt']
#
#     if n_states != 6:
#         raise ValueError(f"For Frenet real-state model, pars['num_states'] must be 6, got {n_states}")
#     if n_inputs != 2:
#         raise ValueError(f"For Frenet real-state model, pars['num_inputs'] must be 2, got {n_inputs}")
#
#     rng = _get_rng(pars)
#
#     delta_max = pars.get('delta_max', 0.08)
#     ax_max = pars.get('ax_max', 2.0)
#
#     X_1 = np.zeros((num_traj, num_snaps, n_states))
#     X_2 = np.zeros((num_traj, num_snaps, n_states))
#     U = np.zeros((num_traj, num_snaps - 1, n_inputs))
#
#     for i in range(num_traj):
#         # ---------- 初始状态 ----------
#         # x = [s, e_y, e_psi, v_x, v_y, r]
#         x0 = np.array([
#             0.0,                                          # s
#             rng.uniform(-0.5, 0.5),                       # e_y
#             rng.uniform(-0.10, 0.10),                     # e_psi
#             rng.uniform(max(pars['vx_ref'] - 1.0, 0.5),
#                         pars['vx_ref'] + 1.0),            # v_x
#             rng.uniform(-0.4, 0.4),                       # v_y
#             rng.uniform(-0.15, 0.15),                     # r
#         ], dtype=float)
#
#         X_1[i, 0, :] = x0
#         X_2[i, 0, :] = x0.copy()
#
#         u_prev = np.zeros(n_inputs)
#
#         seed_1 = rng.uniform(1.0, 10.0)
#         seed_2 = rng.uniform(1.0, 10.0)
#         u_mode = rng.choice(['random', 'sinusoidal', 'mixed'])
#
#         road_mode = rng.choice(['straight', 'sin', 'const', 'dlc'])
#
#         # 为了保留 build_reference_path 接口，这里不传 rng；
#         # 如需完全可复现，建议外部先设 seed，或你后续再把 build_reference_path 扩展一个 rng 参数。
#         path_data = build_reference_path(
#             num_snaps=num_snaps,
#             dt=dt,
#             vx_ref=float(pars['vx_ref']),
#             road_mode=road_mode
#         )
#
#         # 为当前轨迹构造 pars_step 基础模板
#         pars_base = dict(pars)
#         pars_new_base = dict(pars_new)
#
#         # 给 solver 显式塞入同一个 rng，保证内部噪声来源可控
#         pars_base['rng'] = rng
#         pars_new_base['rng'] = rng
#
#         pars_base['s_ref'] = path_data['s_ref']
#         pars_base['curvature_ref'] = path_data['curvature_ref']
#
#         pars_new_base['s_ref'] = path_data['s_ref']
#         pars_new_base['curvature_ref'] = path_data['curvature_ref']
#
#         s_max = float(path_data['s_ref'][-1])
#
#         for j in range(num_snaps - 1):
#             x_now = X_1[i, j, :]
#
#             # ---------- 输入前馈 ----------
#             if u_mode == "random":
#                 delta_ff = rng.uniform(-delta_max, delta_max)
#                 a_x_ff = rng.uniform(-ax_max, ax_max)
#
#             elif u_mode == "sinusoidal":
#                 delta_ff = (
#                     delta_max * np.sin(seed_1 * np.pi * j * dt)
#                     + 0.15 * delta_max * rng.normal()
#                 )
#                 a_x_ff = (
#                     ax_max * np.cos(seed_2 * np.pi * j * dt)
#                     + 0.15 * ax_max * rng.normal()
#                 )
#
#             else:  # mixed
#                 delta_ff = (
#                     0.5 * delta_max * np.sin(seed_1 * np.pi * j * dt)
#                     + rng.uniform(-0.5 * delta_max, 0.5 * delta_max)
#                 )
#                 a_x_ff = (
#                     0.5 * ax_max * np.cos(seed_2 * np.pi * j * dt)
#                     + rng.uniform(-0.5 * ax_max, 0.5 * ax_max)
#                 )
#
#             # ---------- 弱反馈，防止漂移 ----------
#             # x = [s, e_y, e_psi, v_x, v_y, r]
#             delta_fb = (
#                 -0.35 * x_now[1]   # e_y
#                 -0.80 * x_now[2]   # e_psi
#                 -0.10 * x_now[4]   # v_y
#                 -0.18 * x_now[5]   # r
#             )
#
#             a_x_fb = -0.50 * (x_now[3] - pars['vx_ref'])  # 速度保持到 vx_ref
#
#             delta = np.clip(delta_ff + delta_fb, -delta_max, delta_max)
#             a_x = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)
#
#             # ---------- 输入平滑 ----------
#             u_raw = np.array([delta, a_x], dtype=float)
#             alpha_u = 0.70
#             u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
#             u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
#             u_now[1] = np.clip(u_now[1], -ax_max, ax_max)
#
#             U[i, j, :] = u_now
#             u_prev = u_now.copy()
#
#             # ---------- 推进一步 ----------
#             x1_next = FK_solver(
#                 X_1[i, j, :],
#                 U[i, j, :],
#                 pars_base,
#                 sensor_noise=False,
#                 SNR_DB=SNR_DB,
#                 i=j
#             )
#
#             x2_next = FK_solver(
#                 X_2[i, j, :],
#                 U[i, j, :],
#                 pars_new_base,
#                 sensor_noise=sensor_noise,
#                 SNR_DB=SNR_DB,
#                 i=j
#             )
#
#             # ---------- 状态裁剪 ----------
#             x1_next = _clip_frenet_state(x1_next, s_max)
#             x2_next = _clip_frenet_state(x2_next, s_max)
#
#             X_1[i, j + 1, :] = x1_next
#             X_2[i, j + 1, :] = x2_next
#
#     return X_1, X_2, U
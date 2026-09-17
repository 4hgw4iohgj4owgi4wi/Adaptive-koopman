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

# ============================================================
# 修复后的大范围状态采样函数 (替换你原来的同名函数)
# ============================================================
def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    n_states = pars['num_states']
    n_inputs = pars['num_inputs']
    dt = pars['dt']

    rng = _get_rng(pars)
    delta_max = float(pars.get('delta_max', 0.08))
    ax_max = float(pars.get('ax_max', 2.0))
    vx_ref = float(pars['vx_ref'])

    road_modes = pars.get('road_modes', ['straight', 'sin', 'const', 'dlc'])
    road_mode_probs = np.asarray(pars.get('road_mode_probs', [0.15, 0.15, 0.10, 0.60]), dtype=float)
    road_mode_probs = road_mode_probs / np.sum(road_mode_probs)

    u_modes = pars.get('u_modes', ['feedback_dominant', 'sinusoidal', 'mixed'])
    u_mode_probs = np.asarray(pars.get('u_mode_probs', [0.50, 0.30, 0.20]), dtype=float)
    u_mode_probs = u_mode_probs / np.sum(u_mode_probs)

    s_margin = float(pars.get('s_margin', 15.0))
    alpha_u = float(pars.get('alpha_u', 0.70))

    X_1 = np.zeros((num_traj, num_snaps, n_states))
    X_2 = np.zeros((num_traj, num_snaps, n_states))
    U = np.zeros((num_traj, num_snaps - 1, n_inputs))

    for i in range(num_traj):
        road_mode = rng.choice(road_modes, p=road_mode_probs)
        path_data = build_reference_path(num_snaps=num_snaps, dt=dt, vx_ref=vx_ref, road_mode=road_mode, rng=rng)

        s_ref_path = np.asarray(path_data['s_ref'], dtype=float)
        kappa_ref_path = np.asarray(path_data['curvature_ref'], dtype=float)
        s_max = float(s_ref_path[-1])

        # ============================================================
        # 【关键修改】：强行扩大初始状态的采样范围，覆盖 4车编队所需的偏移！
        # ============================================================
        x0 = np.array([
            rng.uniform(-10.0, 50.0),                  # s: 覆盖落后的车辆
            rng.uniform(-8.0, 8.0),                    # e_y: 必须大于4.0m，提供充足泛化裕度
            rng.uniform(-0.2, 0.2),                    # e_psi
            rng.uniform(max(vx_ref - 2.0, 0.5), vx_ref + 2.0), # v_x
            rng.uniform(-0.5, 0.5),                    # v_y
            rng.uniform(-0.2, 0.2),                    # r
        ], dtype=float)

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        u_mode = rng.choice(u_modes, p=u_mode_probs)
        u_prev = np.zeros(n_inputs, dtype=float)

        seed_1 = rng.uniform(0.5, 4.0)
        seed_2 = rng.uniform(0.5, 4.0)

        pars_base, pars_new_base = dict(pars), dict(pars_new)
        pars_base['rng'] = pars_new_base['rng'] = rng
        pars_base['s_ref'] = pars_new_base['s_ref'] = s_ref_path
        pars_base['curvature_ref'] = pars_new_base['curvature_ref'] = kappa_ref_path

        for j in range(num_snaps - 1):
            x_now = X_1[i, j, :]
            kappa_now = interp_path_value(x_now[0], s_ref_path, kappa_ref_path)
            delta_path_ff = (pars['lf'] + pars['lr']) * kappa_now

            if u_mode == "feedback_dominant":
                delta_ff = 0.15 * delta_max * rng.normal()
                a_x_ff = 0.15 * ax_max * rng.normal()
            elif u_mode == "sinusoidal":
                delta_ff = 0.70 * delta_max * np.sin(seed_1 * np.pi * j * dt) + 0.10 * delta_max * rng.normal()
                a_x_ff = 0.70 * ax_max * np.cos(seed_2 * np.pi * j * dt) + 0.10 * ax_max * rng.normal()
            else:
                delta_ff = 0.35 * delta_max * np.sin(seed_1 * np.pi * j * dt) + rng.uniform(-0.30 * delta_max, 0.30 * delta_max)
                a_x_ff = 0.35 * ax_max * np.cos(seed_2 * np.pi * j * dt) + rng.uniform(-0.30 * ax_max, 0.30 * ax_max)

            delta_fb = -0.35 * x_now[1] - 0.90 * x_now[2] - 0.12 * x_now[4] - 0.20 * x_now[5]
            a_x_fb = -0.60 * (x_now[3] - vx_ref)

            delta_cmd = np.clip(delta_path_ff + delta_ff + delta_fb, -delta_max, delta_max)
            ax_cmd = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)

            u_raw = np.array([delta_cmd, ax_cmd], dtype=float)
            u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
            u_now[0], u_now[1] = np.clip(u_now[0], -delta_max, delta_max), np.clip(u_now[1], -ax_max, ax_max)

            U[i, j, :] = u_now
            u_prev = u_now.copy()

            x1_next = FK_solver(X_1[i, j, :], U[i, j, :], pars_base, sensor_noise=False, SNR_DB=SNR_DB, i=j)
            x2_next = FK_solver(X_2[i, j, :], U[i, j, :], pars_new_base, sensor_noise=sensor_noise, SNR_DB=SNR_DB, i=j)

            x1_next[0] = np.clip(x1_next[0], -20.0, s_max + s_margin)  # 允许 s 为负，防截断
            x2_next[0] = np.clip(x2_next[0], -20.0, s_max + s_margin)
            x1_next[1] = np.clip(x1_next[1], -8.0, 8.0)                # 放开横向截断
            x2_next[1] = np.clip(x2_next[1], -8.0, 8.0)

            X_1[i, j + 1, :] = x1_next
            X_2[i, j + 1, :] = x2_next

    return X_1, X_2, U


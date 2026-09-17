# import numpy as np
#
# def cubic_spline_interpolation(q_,t_end, m): # time problem
#     """
#     Cubic Spline Interpolation
#
#     ...
#
#     Parameters
#     ---
#     q_  : Array of Position (n x Dof)
#     t_end : Total time for trajectory
#     m(Optional) : Discrete Time Steps
#
#     Returns
#     ---
#     q, qd, qdd : Position, Velocity and Acceleration (Dof x m)
#     """
#     n = q_.shape[0]
#     dof = q_.shape[1]
#
#     q_ = np.transpose(q_)
#
#     m = m + (m % (n-1))
#     k = int(m / (n-1))
#     timesteps = [np.linspace(0, 1, num = k, endpoint = False) for i in range(n-2)]
#     timesteps.append(np.linspace(0, 1, num = k))
#
#     # Generate A matrix
#     A = np.zeros((dof, n, n))
#     # for zero acceleration
#     A[:, 0, 0] = 2
#     A[:, 0, 1] = 1
#     A[:, n-1, n-2] = 1
#     A[:, n-1, n-1] = 2
#
#     # for zero velocity
#     # A[:, 0, 0] = 1
#     # A[:, n-1, n-1] = 1
#     for i in range(1, n-1):
#         A[:, i, i - 1] = 1
#         A[:, i, i] = 4
#         A[:, i, i + 1] = 1
#
#     # Generate b matrix
#     y = np.zeros((dof, n))
#     y[:, 0] = 3 * (q_[:, 1] - q_[:, 0])
#     y[:, n-1] = 3 * (q_[:, n - 1] - q_[:, n - 2])
#     y[:, 0] = 0
#     # y[:, n-1] = 0
#     for i in range(1, n-1):
#         y[:, i] = 3 * (q_[:, i + 1] - q_[:, i - 1])
#
#     # Solve D
#     D = np.linalg.solve(A, y)
#
#     # Calculate coefficients
#     a = np.copy(q_[:, :n-1])
#     b = np.copy(D[:, :n-1])
#     c = np.zeros((dof, n-1))
#     d = np.zeros((dof, n-1))
#     for i in range(0, n-1):
#         c[:, i] = 3 * (q_[:, i + 1] - q_[:, i]) - 2 * D[:, i] - D[:, i + 1]
#         d[:, i] = 2 * (q_[:, i] - q_[:, i + 1]) + D[:, i] + D[:, i + 1]
#
#
#     # Calculate Trajectories
#     q = np.zeros((dof, m))
#     qd = np.zeros((dof, m))
#     qdd = np.zeros((dof, m))
#
#     for j in range(n - 1):
#         for i in range(len(timesteps[j])):
#             t = timesteps[j][i]
#             t_2 = t * t
#             t_3 = t * t * t
#
#             q[:, i + j * k] = a[:, j] + b[:, j] * t + c[:, j] * t_2 + d[:, j] * t_3
#
#
#     dt = t_end/m
#     for i in range(m-1):
#         if i < 5:
#             qd[:,i] = (q[:,i+1]-q[:,i])/dt
#             qdd[:,i] = (qd[:,i+1]-qd[:,i])/dt
#         else:
#             qd[:,i] = (5*q[:,i+1]-3*q[:,i]-q[:,i-1]-q[:,i-2])/(8*dt)
#             qdd[:,i] = (qd[:,i+1]-3*qd[:,i]-qd[:,i-1]-qd[:,i-2])/(8*dt)
#     # once this is done resample the trajectory to the given time space
#     qd[:,-1] = qd[:,-2]
#     qdd[:,-1] = qdd[:,-2]
#     return q, qd, qdd
#
####
import numpy as np

def cubic_spline_interpolation(q_, t_end, m):
    """
    Cubic Spline Interpolation

    Parameters
    ---
    q_  : 路径点数组，形状应为 (num_dof, num_waypoints)
          num_dof: 自由度数量，num_waypoints: 路径点个数
    t_end : 总轨迹时间
    m    : 离散时间步数（生成的轨迹点数）

    Returns
    ---
    q, qd, qdd : 位置、速度、加速度，形状均为 (num_dof, m)
    """
    # 确保输入为二维数组
    if q_.ndim != 2:
        raise ValueError("q_ must be a 2D array")
    num_dof, num_waypoints = q_.shape

    # 调整 m 使其是 (num_waypoints-1) 的整数倍，确保每段插值点数相同
    m = m + (m % (num_waypoints - 1))
    k = int(m / (num_waypoints - 1))  # 每段插值点数

    # 生成每段的归一化时间步长 [0,1]
    timesteps = []
    for i in range(num_waypoints - 2):
        timesteps.append(np.linspace(0, 1, num=k, endpoint=False))
    timesteps.append(np.linspace(0, 1, num=k))  # 最后一段包含终点

    # 构造三对角矩阵 A (零加速度边界条件)
    A = np.zeros((num_waypoints, num_waypoints))
    A[0, 0] = 2
    A[0, 1] = 1
    A[-1, -2] = 1
    A[-1, -1] = 2
    for i in range(1, num_waypoints - 1):
        A[i, i - 1] = 1
        A[i, i] = 4
        A[i, i + 1] = 1

    # 构造右侧向量 y (每个自由度独立)
    y = np.zeros((num_dof, num_waypoints))
    y[:, 0] = 3 * (q_[:, 1] - q_[:, 0])
    y[:, -1] = 3 * (q_[:, -1] - q_[:, -2])
    for i in range(1, num_waypoints - 1):
        y[:, i] = 3 * (q_[:, i + 1] - q_[:, i - 1])

    # 求解 D (样条二阶导数系数)，对每个自由度分别求解
    D = np.zeros((num_dof, num_waypoints))
    for dof in range(num_dof):
        D[dof, :] = np.linalg.solve(A, y[dof, :])

    # 计算样条系数 a, b, c, d
    a = q_[:, :-1]                     # 位置系数
    b = D[:, :-1]                       # 一阶导数系数
    c = np.zeros((num_dof, num_waypoints - 1))
    d = np.zeros((num_dof, num_waypoints - 1))
    for i in range(num_waypoints - 1):
        c[:, i] = 3 * (q_[:, i + 1] - q_[:, i]) - 2 * D[:, i] - D[:, i + 1]
        d[:, i] = 2 * (q_[:, i] - q_[:, i + 1]) + D[:, i] + D[:, i + 1]

    # 生成位置轨迹
    q = np.zeros((num_dof, m))
    for seg in range(num_waypoints - 1):
        t_seg = timesteps[seg]
        for local_idx, tau in enumerate(t_seg):
            global_idx = seg * k + local_idx
            q[:, global_idx] = a[:, seg] + b[:, seg] * tau + c[:, seg] * tau**2 + d[:, seg] * tau**3

    # 数值差分计算速度和加速度
    dt = t_end / m
    qd = np.zeros((num_dof, m))
    qdd = np.zeros((num_dof, m))

    # 速度 (前向差分，最后一点用前一点值)
    for i in range(m - 1):
        if i < 5:
            qd[:, i] = (q[:, i + 1] - q[:, i]) / dt
        else:
            qd[:, i] = (5 * q[:, i + 1] - 3 * q[:, i] - q[:, i - 1] - q[:, i - 2]) / (8 * dt)
    qd[:, -1] = qd[:, -2]  # 填充最后一点

    # 加速度 (基于速度)
    for i in range(m - 1):
        if i < 5:
            qdd[:, i] = (qd[:, i + 1] - qd[:, i]) / dt
        else:
            qdd[:, i] = (qd[:, i + 1] - 3 * qd[:, i] - qd[:, i - 1] - qd[:, i - 2]) / (8 * dt)
    qdd[:, -1] = qdd[:, -2]

    return q, qd, qdd
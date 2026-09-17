import optuna
import numpy as np
import time
import os
from copy import deepcopy

# 假设你已有的模块（根据你的代码路径调整导入）
from control_files.nmpc_osqp_adapt import NonlinearMPCController
from dynamics.learned_models_control.linear_dynamics import linear_Dynamics


# ... 其他你已有的 import（如 safe_FK_step, frenet_to_global 等）

def objective(trial: optuna.Trial,
              model_koop_dnn_lin,
              standardizer_x_kdnn,
              net_params_lin,
              A_lin_stable,
              B_lin,
              C_lin,
              x_ref_scaled,
              x_ref_mpc,
              s_ref_path,
              x_path,
              y_ref_path,
              psi_ref_path,
              curvature_ref_path,
              sys_pars_new,
              dt=0.02,
              N=80,
              max_iter_lin=5,
              num_trials_in_obj=3):  # 每个 trial 跑多次仿真取平均，降低方差

    # ==================== 建议搜索空间（可根据需要扩大） ====================
    # 侧向误差权重（因为你做了数据增强，需要较大值）
    q_ey = trial.suggest_float("q_ey", 400.0, 2500.0, log=True)
    q_epsi = trial.suggest_float("q_epsi", 100.0, 800.0, log=True)
    q_vx = trial.suggest_float("q_vx", 2.0, 20.0)
    q_vy = trial.suggest_float("q_vy", 0.1, 5.0)
    q_r = trial.suggest_float("q_r", 0.1, 5.0)

    # 终端权重（通常比 Q 大 1.2~2 倍）
    qn_ey = trial.suggest_float("qn_ey", q_ey * 1.2, q_ey * 2.5, log=True)
    qn_epsi = trial.suggest_float("qn_epsi", q_epsi * 1.2, q_epsi * 2.5, log=True)

    # 控制权重
    r_delta = trial.suggest_float("r_delta", 10.0, 200.0, log=True)
    r_ax = trial.suggest_float("r_ax", 3.0, 30.0, log=True)

    # 前馈增益（也可以一起调）
    ff_gain = trial.suggest_float("ff_gain", 0.6, 1.1)

    # 构建权重矩阵
    Q = np.diag([0.0, q_ey, q_epsi, q_vx, q_vy, q_r])
    QN = np.diag([0.0, qn_ey, qn_epsi, q_vx * 1.2, q_vy, q_r])
    R = np.diag([r_delta, r_ax])

    # ==================== 构造控制器 ====================
    linear_model = linear_Dynamics(
        np.array(A_lin_stable),
        np.array(B_lin),
        C_lin
    )

    # 状态约束（scaled space）
    xmin_raw = np.array([-10.0, -5.0, -1.2, 0.5, -4.0, -3.0])
    xmax_raw = np.array([500.0, 5.0, 1.2, 8.0, 4.0, 3.0])
    xmin = standardizer_x_kdnn.transform(xmin_raw.reshape(1, -1)).flatten()
    xmax = standardizer_x_kdnn.transform(xmax_raw.reshape(1, -1)).flatten()

    umax = np.array([0.08, 1.0])
    umin = -umax

    controller = NonlinearMPCController(
        linear_model, N, dt, umin, umax, xmin, xmax,
        scipy.sparse.diags(Q.diagonal()),
        scipy.sparse.diags(R.diagonal()),
        scipy.sparse.diags(QN.diagonal()),
        # =========================
        # Solver settings
        # =========================
        solver_settings={}
        solver_settings["gen_embedded_ctrl"] = False
        solver_settings["warm_start"] = True
        solver_settings["polish"] = True
        solver_settings["polish_refine_iter"] = 5
        solver_settings["scaling"] = True
        solver_settings["adaptive_rho"] = True
        solver_settings["check_termination"] = 25
        solver_settings["max_iter"] = 30000
        solver_settings["eps_abs"] = 5e-4
        solver_settings["eps_rel"] = 5e-4
        solver_settings["eps_prim_inf"] = 1e-3
        solver_settings["eps_dual_inf"] = 1e-3
    # 构造控制器（初始 guess 可复用你之前的代码）
    # ...（复用你原来的 z_init_lin_noadapt 等逻辑）

    # ==================== 闭环仿真（多次取平均） ====================
    costs = []
    max_ey_list = []
    rms_ey_list = []

    for seed in range(num_trials_in_obj):
        np.random.seed(42 + seed)

        xt_actual = np.zeros((len(x_ref_scaled), 6))
        xt_actual[0] = np.array([0.0, 0.0, 0.0, 3.0, 0.0, 0.0])
        u_actual = np.zeros((len(x_ref_scaled) - 1, 2))

        # 运行闭环（复用你原来的 closed-loop 逻辑，封装成函数更佳）
        # 这里简化：你可以把你原来的 for k in range(...) 循环封装成 run_closed_loop() 函数
        # 下面用伪代码表示，实际请替换为你已有的 safe_FK_step 等逻辑

        for k in range(len(x_ref_scaled) - 1):
            # ...（你的 lift_scaled + MPC solve + ff + smoothing + safe_FK_step 逻辑）
            # 这里省略具体步骤，请直接复制你原来的闭环代码块

            pass  # ← 替换为实际仿真代码

        # 计算指标
        ey = xt_actual[:, 1]
        cost = np.sum(ey ** 2) + 0.1 * np.sum(u_actual[:, 0] ** 2) + 0.05 * np.sum(u_actual[:, 1] ** 2)

        costs.append(cost)
        max_ey_list.append(np.max(np.abs(ey)))
        rms_ey_list.append(np.sqrt(np.mean(ey ** 2)))

    mean_cost = np.mean(costs)
    mean_max_ey = np.mean(max_ey_list)
    mean_rms_ey = np.mean(rms_ey_list)

    # 多目标：主要最小化均方误差，同时惩罚过大控制量和失败情况
    if mean_max_ey > 1.5:  # 严重偏离视为失败
        return 1e6 + mean_max_ey * 100

    return mean_cost  # 或返回 mean_rms_ey（更直接）


# ====================== 运行优化 ======================
def tune_mpc_weights(model_koop_dnn_lin, standardizer_x_kdnn, ...):  # 传入所有需要的对象

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner()
    )

    # 把所有固定对象作为 partial 传入，避免重复传递
    from functools import partial
    obj = partial(objective,
                  model_koop_dnn_lin=model_koop_dnn_lin,
                  standardizer_x_kdnn=standardizer_x_kdnn,
                  # ... 传入其他固定参数
                  )

    study.optimize(obj, n_trials=80, timeout=3600 * 2)  # 建议跑 60-100 次 trial

    print("Best trial:")
    print(study.best_trial.params)
    print("Best value:", study.best_value)

    # 可视化
    optuna.visualization.plot_optimization_history(study).show()
    optuna.visualization.plot_param_importances(study).show()

    # 保存最佳权重
    best_params = study.best_trial.params
    np.savez("saved_models/best_mpc_weights.npz", **best_params)

    return best_params
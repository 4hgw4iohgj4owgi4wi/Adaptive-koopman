# 5 m/s 回头弯全路段误差差值与切换诊断

## 结论摘要

- `mse_gain_sum > 0` 表示该路段让 NR-KDCC 相对 AKE-M 降低横向平方误差，是压低总体 RMSE 的正贡献段。
- `role_mse_gain_sum > 0` 表示 full NR-KDCC 相对 w/o role schedule 的额外收益，是角色/相位调度贡献段。
- `strict_all_win=True` 才表示该 5 m 小段内所有采样点均优于 baseline。
- `method_ey_pos_ratio`、`method_epsi_pos_ratio`、`method_delta_pos_ratio` 用于判断横向误差、航向误差和转角命令的符号相位。
- `method_vx_mean/max`、`method_ax_mean/peak_abs` 给出每个空间段的速度和加速度统计。

## 最能压低总体 RMSE 的路段

- seed 2026 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=17.7726, delta_rmse=-0.3751, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.86
- seed 2026 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=16.1239, delta_rmse=-0.2444, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=8.8497, delta_rmse=-0.1624, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=4.2647, delta_rmse=-0.1547, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_45.0_50.0 (45.0-50.0 m): mse_gain_sum=2.3764, delta_rmse=-0.1025, win_ratio=0.710, phase=turn_core, fault=1.00, progress=0.42
- seed 2026 s_70.0_75.0 (70.0-75.0 m): mse_gain_sum=2.1661, delta_rmse=-0.1337, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_30.0_35.0 (30.0-35.0 m): mse_gain_sum=1.4617, delta_rmse=-0.0344, win_ratio=0.830, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_25.0_30.0 (25.0-30.0 m): mse_gain_sum=1.2493, delta_rmse=-0.0842, win_ratio=0.890, phase=turn_core, fault=0.37, progress=1.00

## 最破坏逐点全赢的路段

- seed 2026 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-6.9787, delta_rmse=0.1019, max_gap=0.1520, win_ratio=0.000, phase=turn_core
- seed 2026 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-6.9456, delta_rmse=0.1448, max_gap=0.1622, win_ratio=0.000, phase=turn_core
- seed 2026 s_00.0_05.0 (2.5-5.0 m): mse_gain_sum=0.0102, delta_rmse=-0.0073, max_gap=0.0003, win_ratio=0.725, phase=straight
- seed 2026 s_15.0_20.0 (15.0-20.0 m): mse_gain_sum=0.1258, delta_rmse=-0.0183, max_gap=0.0248, win_ratio=0.730, phase=turn_transition
- seed 2026 s_10.0_15.0 (10.0-15.0 m): mse_gain_sum=0.1279, delta_rmse=-0.0312, max_gap=0.0026, win_ratio=0.950, phase=turn_core
- seed 2026 s_05.0_10.0 (5.0-10.0 m): mse_gain_sum=0.3745, delta_rmse=-0.0487, max_gap=-0.0190, win_ratio=1.000, phase=straight
- seed 2026 s_75.0_80.0 (75.0-78.7 m): mse_gain_sum=0.8415, delta_rmse=-0.0877, max_gap=-0.0585, win_ratio=1.000, phase=straight
- seed 2026 s_20.0_25.0 (20.0-25.0 m): mse_gain_sum=0.9810, delta_rmse=-0.0538, max_gap=-0.0206, win_ratio=1.000, phase=turn_core

## 角色/相位调度带来额外收益的路段


## 文件

- `route_5m_segment_contribution.csv`: 每 5 m 路段对总体误差的贡献。
- `switch_phase_group_contribution.csv`: 按 phase / progress / fault / comm 状态分组的误差贡献。
- `worst_gap_points.csv`: 全路段逐点劣化最大的采样点。
- `role_trim_segment_summary.csv`: 若重跑时保存了 `phase_role.csv`，这里汇总逐车 `delta_trim/ax_trim` 分解。
- `full_route_gap_seed_*.png`: 全路段误差差值曲线。

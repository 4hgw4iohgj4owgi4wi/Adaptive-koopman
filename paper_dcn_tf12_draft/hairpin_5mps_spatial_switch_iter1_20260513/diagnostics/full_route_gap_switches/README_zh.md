# 5 m/s 回头弯全路段误差差值与切换诊断

## 结论摘要

- `mse_gain_sum > 0` 表示该路段让 NR-KDCC 相对 AKE-M 降低横向平方误差，是压低总体 RMSE 的正贡献段。
- `role_mse_gain_sum > 0` 表示 full NR-KDCC 相对 w/o role schedule 的额外收益，是角色/相位调度贡献段。
- `strict_all_win=True` 才表示该 5 m 小段内所有采样点均优于 baseline。

## 最能压低总体 RMSE 的路段

- seed 2026 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=16.7788, delta_rmse=-0.3096, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.18
- seed 2026 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=12.7734, delta_rmse=-0.1867, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.98
- seed 2026 s_45.0_50.0 (45.0-50.0 m): mse_gain_sum=6.7511, delta_rmse=-0.1705, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.68
- seed 2026 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=2.7116, delta_rmse=-0.0433, win_ratio=0.760, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_25.0_30.0 (25.0-30.0 m): mse_gain_sum=1.3455, delta_rmse=-0.0961, win_ratio=0.970, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_20.0_25.0 (20.0-25.0 m): mse_gain_sum=0.6100, delta_rmse=-0.0345, win_ratio=0.670, phase=turn_core, fault=0.21, progress=1.00
- seed 2026 s_75.0_80.0 (75.0-78.7 m): mse_gain_sum=0.5621, delta_rmse=-0.0448, win_ratio=1.000, phase=straight, fault=1.00, progress=1.00
- seed 2026 s_05.0_10.0 (5.0-10.0 m): mse_gain_sum=0.3731, delta_rmse=-0.0445, win_ratio=1.000, phase=straight, fault=0.00, progress=0.00

## 最破坏逐点全赢的路段

- seed 2026 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-15.4902, delta_rmse=0.1964, max_gap=0.2262, win_ratio=0.000, phase=turn_core
- seed 2026 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-7.2455, delta_rmse=0.1228, max_gap=0.2242, win_ratio=0.110, phase=turn_core
- seed 2026 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=-2.6423, delta_rmse=0.0577, max_gap=0.0674, win_ratio=0.000, phase=turn_core
- seed 2026 s_30.0_35.0 (30.0-35.0 m): mse_gain_sum=-2.0964, delta_rmse=0.0416, max_gap=0.1343, win_ratio=0.410, phase=turn_core
- seed 2026 s_70.0_75.0 (70.0-75.0 m): mse_gain_sum=-0.5047, delta_rmse=0.0164, max_gap=0.0487, win_ratio=0.310, phase=turn_core
- seed 2026 s_00.0_05.0 (2.5-5.0 m): mse_gain_sum=0.0085, delta_rmse=-0.0050, max_gap=0.0017, win_ratio=0.510, phase=straight
- seed 2026 s_15.0_20.0 (15.0-20.0 m): mse_gain_sum=0.0086, delta_rmse=-0.0015, max_gap=0.0331, win_ratio=0.530, phase=turn_transition
- seed 2026 s_10.0_15.0 (10.0-15.0 m): mse_gain_sum=0.1488, delta_rmse=-0.0335, max_gap=0.0053, win_ratio=0.900, phase=turn_core

## 角色/相位调度带来额外收益的路段


## 文件

- `route_5m_segment_contribution.csv`: 每 5 m 路段对总体误差的贡献。
- `switch_phase_group_contribution.csv`: 按 phase / progress / fault / comm 状态分组的误差贡献。
- `worst_gap_points.csv`: 全路段逐点劣化最大的采样点。
- `full_route_gap_seed_*.png`: 全路段误差差值曲线。

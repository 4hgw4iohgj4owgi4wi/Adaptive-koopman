# 5 m/s 回头弯全路段误差差值与切换诊断

## 结论摘要

- `mse_gain_sum > 0` 表示该路段让 NR-KDCC 相对 AKE-M 降低横向平方误差，是压低总体 RMSE 的正贡献段。
- `role_mse_gain_sum > 0` 表示 full NR-KDCC 相对 w/o role schedule 的额外收益，是角色/相位调度贡献段。
- `strict_all_win=True` 才表示该 5 m 小段内所有采样点均优于 baseline。

## 最能压低总体 RMSE 的路段

- seed 2026 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=17.3208, delta_rmse=-0.3889, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.99
- seed 2026 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=12.0711, delta_rmse=-0.1673, win_ratio=0.970, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=2.8501, delta_rmse=-0.0800, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_70.0_75.0 (70.0-75.0 m): mse_gain_sum=2.2628, delta_rmse=-0.1273, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_25.0_30.0 (25.0-30.0 m): mse_gain_sum=1.3761, delta_rmse=-0.1015, win_ratio=0.980, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_45.0_50.0 (45.0-50.0 m): mse_gain_sum=1.2903, delta_rmse=-0.0382, win_ratio=0.550, phase=turn_core, fault=1.00, progress=0.39
- seed 2026 s_20.0_25.0 (20.0-25.0 m): mse_gain_sum=0.9103, delta_rmse=-0.0499, win_ratio=1.000, phase=turn_core, fault=0.21, progress=1.00
- seed 2026 s_75.0_80.0 (75.0-78.8 m): mse_gain_sum=0.7831, delta_rmse=-0.0712, win_ratio=1.000, phase=straight, fault=1.00, progress=1.00

## 最破坏逐点全赢的路段

- seed 2026 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-18.6613, delta_rmse=0.2304, max_gap=0.2907, win_ratio=0.000, phase=turn_core
- seed 2026 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-14.8880, delta_rmse=0.2312, max_gap=0.2853, win_ratio=0.000, phase=turn_core
- seed 2026 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=-2.4026, delta_rmse=0.0326, max_gap=0.0452, win_ratio=0.030, phase=turn_core
- seed 2026 s_30.0_35.0 (30.0-35.0 m): mse_gain_sum=-1.5381, delta_rmse=0.0322, max_gap=0.1301, win_ratio=0.490, phase=turn_core
- seed 2026 s_00.0_05.0 (2.5-5.0 m): mse_gain_sum=0.0078, delta_rmse=-0.0059, max_gap=0.0000, win_ratio=1.000, phase=straight
- seed 2026 s_15.0_20.0 (15.0-20.0 m): mse_gain_sum=0.0980, delta_rmse=-0.0142, max_gap=0.0285, win_ratio=0.680, phase=turn_transition
- seed 2026 s_10.0_15.0 (10.0-15.0 m): mse_gain_sum=0.1249, delta_rmse=-0.0311, max_gap=0.0033, win_ratio=0.950, phase=turn_core
- seed 2026 s_05.0_10.0 (5.0-10.0 m): mse_gain_sum=0.3637, delta_rmse=-0.0464, max_gap=-0.0155, win_ratio=1.000, phase=straight

## 角色/相位调度带来额外收益的路段

- seed 2026 s_55.0_60.0 (55.0-60.0 m): role_mse_gain_sum=5.5153, full_minus_main_rmse=-0.0862, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_25.0_30.0 (25.0-30.0 m): role_mse_gain_sum=3.6717, full_minus_main_rmse=-0.1754, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_60.0_65.0 (60.0-65.0 m): role_mse_gain_sum=2.9282, full_minus_main_rmse=-0.0363, role_win_vs_main=0.890, phase=turn_core
- seed 2026 s_75.0_80.0 (75.0-78.8 m): role_mse_gain_sum=2.5315, full_minus_main_rmse=-0.1494, role_win_vs_main=1.000, phase=straight
- seed 2026 s_20.0_25.0 (20.0-25.0 m): role_mse_gain_sum=2.1583, full_minus_main_rmse=-0.0948, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_50.0_55.0 (50.0-55.0 m): role_mse_gain_sum=1.7409, full_minus_main_rmse=-0.1067, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_45.0_50.0 (45.0-50.0 m): role_mse_gain_sum=1.2583, full_minus_main_rmse=-0.0373, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_70.0_75.0 (70.0-75.0 m): role_mse_gain_sum=0.9872, full_minus_main_rmse=-0.0773, role_win_vs_main=0.850, phase=turn_core

## 文件

- `route_5m_segment_contribution.csv`: 每 5 m 路段对总体误差的贡献。
- `switch_phase_group_contribution.csv`: 按 phase / progress / fault / comm 状态分组的误差贡献。
- `worst_gap_points.csv`: 全路段逐点劣化最大的采样点。
- `full_route_gap_seed_*.png`: 全路段误差差值曲线。

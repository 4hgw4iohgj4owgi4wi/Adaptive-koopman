# 5 m/s 回头弯全路段误差差值与切换诊断

## 结论摘要

- `mse_gain_sum > 0` 表示该路段让 NR-KDCC 相对 AKE-M 降低横向平方误差，是压低总体 RMSE 的正贡献段。
- `role_mse_gain_sum > 0` 表示 full NR-KDCC 相对 w/o role schedule 的额外收益，是角色/相位调度贡献段。
- `strict_all_win=True` 才表示该 5 m 小段内所有采样点均优于 baseline。

## 最能压低总体 RMSE 的路段

- seed 2028 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=15.4335, delta_rmse=-0.2282, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2028 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=14.1378, delta_rmse=-0.2805, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2028 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=6.1836, delta_rmse=-0.1225, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=5.4941, delta_rmse=-0.0968, win_ratio=0.870, phase=turn_core, fault=1.00, progress=0.41
- seed 2026 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=3.3689, delta_rmse=-0.1169, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2027 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=2.5411, delta_rmse=-0.0340, win_ratio=0.840, phase=turn_core, fault=1.00, progress=1.00
- seed 2027 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=2.3392, delta_rmse=-0.0694, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.00
- seed 2028 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=2.1883, delta_rmse=-0.0830, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00

## 最破坏逐点全赢的路段

- seed 2028 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-28.3533, delta_rmse=0.4254, max_gap=0.4598, win_ratio=0.000, phase=turn_core
- seed 2028 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-24.7704, delta_rmse=0.2936, max_gap=0.4251, win_ratio=0.000, phase=turn_core
- seed 2026 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-23.8562, delta_rmse=0.3620, max_gap=0.4005, win_ratio=0.000, phase=turn_core
- seed 2027 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-19.5228, delta_rmse=0.3253, max_gap=0.3610, win_ratio=0.000, phase=turn_core
- seed 2027 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-17.4371, delta_rmse=0.2236, max_gap=0.3088, win_ratio=0.000, phase=turn_core
- seed 2026 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-15.3761, delta_rmse=0.2011, max_gap=0.3214, win_ratio=0.000, phase=turn_core
- seed 2026 s_45.0_50.0 (45.0-50.0 m): mse_gain_sum=-13.6796, delta_rmse=0.2653, max_gap=0.3912, win_ratio=0.000, phase=turn_core
- seed 2026 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=-9.9410, delta_rmse=0.0995, max_gap=0.1245, win_ratio=0.000, phase=turn_core

## 角色/相位调度带来额外收益的路段

- seed 2028 s_60.0_65.0 (60.0-65.0 m): role_mse_gain_sum=21.1502, full_minus_main_rmse=-0.3069, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_60.0_65.0 (60.0-65.0 m): role_mse_gain_sum=10.7935, full_minus_main_rmse=-0.1688, role_win_vs_main=0.990, phase=turn_core
- seed 2028 s_55.0_60.0 (55.0-60.0 m): role_mse_gain_sum=8.3249, full_minus_main_rmse=-0.1412, role_win_vs_main=1.000, phase=turn_core
- seed 2027 s_25.0_30.0 (25.0-30.0 m): role_mse_gain_sum=5.0960, full_minus_main_rmse=-0.1997, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_25.0_30.0 (25.0-30.0 m): role_mse_gain_sum=3.7503, full_minus_main_rmse=-0.1733, role_win_vs_main=1.000, phase=turn_core
- seed 2028 s_25.0_30.0 (25.0-30.0 m): role_mse_gain_sum=3.2852, full_minus_main_rmse=-0.1412, role_win_vs_main=1.000, phase=turn_core
- seed 2026 s_35.0_40.0 (35.0-40.0 m): role_mse_gain_sum=2.6745, full_minus_main_rmse=-0.0269, role_win_vs_main=0.880, phase=turn_core
- seed 2028 s_65.0_70.0 (65.0-70.0 m): role_mse_gain_sum=2.6484, full_minus_main_rmse=-0.0958, role_win_vs_main=0.870, phase=turn_core

## 文件

- `route_5m_segment_contribution.csv`: 每 5 m 路段对总体误差的贡献。
- `switch_phase_group_contribution.csv`: 按 phase / progress / fault / comm 状态分组的误差贡献。
- `worst_gap_points.csv`: 全路段逐点劣化最大的采样点。
- `full_route_gap_seed_*.png`: 全路段误差差值曲线。

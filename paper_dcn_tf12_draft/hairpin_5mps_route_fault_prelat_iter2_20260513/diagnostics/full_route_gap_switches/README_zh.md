# 5 m/s 回头弯全路段误差差值与切换诊断

## 结论摘要

- `mse_gain_sum > 0` 表示该路段让 NR-KDCC 相对 AKE-M 降低横向平方误差，是压低总体 RMSE 的正贡献段。
- `role_mse_gain_sum > 0` 表示 full NR-KDCC 相对 w/o role schedule 的额外收益，是角色/相位调度贡献段。
- `strict_all_win=True` 才表示该 5 m 小段内所有采样点均优于 baseline。

## 最能压低总体 RMSE 的路段

- seed 2026 s_50.0_55.0 (50.0-55.0 m): mse_gain_sum=16.5094, delta_rmse=-0.2883, win_ratio=1.000, phase=turn_core, fault=1.00, progress=0.90
- seed 2026 s_55.0_60.0 (55.0-60.0 m): mse_gain_sum=15.0312, delta_rmse=-0.2331, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_60.0_65.0 (60.0-65.0 m): mse_gain_sum=6.2126, delta_rmse=-0.1096, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_45.0_50.0 (45.0-50.0 m): mse_gain_sum=2.6420, delta_rmse=-0.0509, win_ratio=0.670, phase=turn_core, fault=1.00, progress=0.75
- seed 2026 s_65.0_70.0 (65.0-70.0 m): mse_gain_sum=2.4580, delta_rmse=-0.0750, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_70.0_75.0 (70.0-75.0 m): mse_gain_sum=2.2116, delta_rmse=-0.1362, win_ratio=1.000, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_25.0_30.0 (25.0-30.0 m): mse_gain_sum=1.3861, delta_rmse=-0.1049, win_ratio=0.990, phase=turn_core, fault=1.00, progress=1.00
- seed 2026 s_30.0_35.0 (30.0-35.0 m): mse_gain_sum=1.2274, delta_rmse=-0.0294, win_ratio=0.770, phase=turn_core, fault=1.00, progress=1.00

## 最破坏逐点全赢的路段

- seed 2026 s_40.0_45.0 (40.0-45.0 m): mse_gain_sum=-16.1512, delta_rmse=0.2318, max_gap=0.2757, win_ratio=0.000, phase=turn_core
- seed 2026 s_35.0_40.0 (35.0-40.0 m): mse_gain_sum=-12.9702, delta_rmse=0.1718, max_gap=0.2722, win_ratio=0.000, phase=turn_core
- seed 2026 s_00.0_05.0 (2.5-5.0 m): mse_gain_sum=0.0044, delta_rmse=-0.0030, max_gap=0.0024, win_ratio=0.392, phase=straight
- seed 2026 s_15.0_20.0 (15.0-20.0 m): mse_gain_sum=0.0913, delta_rmse=-0.0136, max_gap=0.0269, win_ratio=0.690, phase=turn_transition
- seed 2026 s_10.0_15.0 (10.0-15.0 m): mse_gain_sum=0.1205, delta_rmse=-0.0302, max_gap=0.0023, win_ratio=0.960, phase=turn_core
- seed 2026 s_05.0_10.0 (5.0-10.0 m): mse_gain_sum=0.3609, delta_rmse=-0.0458, max_gap=-0.0133, win_ratio=1.000, phase=straight
- seed 2026 s_20.0_25.0 (20.0-25.0 m): mse_gain_sum=0.9272, delta_rmse=-0.0509, max_gap=-0.0144, win_ratio=1.000, phase=turn_core
- seed 2026 s_75.0_80.0 (75.0-78.8 m): mse_gain_sum=0.9767, delta_rmse=-0.0920, max_gap=-0.0621, win_ratio=1.000, phase=straight

## 角色/相位调度带来额外收益的路段


## 文件

- `route_5m_segment_contribution.csv`: 每 5 m 路段对总体误差的贡献。
- `switch_phase_group_contribution.csv`: 按 phase / progress / fault / comm 状态分组的误差贡献。
- `worst_gap_points.csv`: 全路段逐点劣化最大的采样点。
- `full_route_gap_seed_*.png`: 全路段误差差值曲线。

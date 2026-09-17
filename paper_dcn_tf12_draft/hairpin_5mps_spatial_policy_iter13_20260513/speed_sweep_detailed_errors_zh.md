# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.0237 | 0.2383 | 8.5940 | 15.7855 | 0.4865 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.2977 | 0.1578 | 7.2514 | 5.6954 | 0.4060 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5875 | 1.0379 | 8.9520 | 8.3150 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5807 | 1.0292 | 9.1644 | 9.1823 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2223 | 0.4967 | 8.8701 | 8.4480 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2457 | 0.5332 | 9.1099 | 8.4590 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4437 | 0.9251 | 3.2245 | 7.1714 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4254 | 0.8849 | 3.4166 | 7.3571 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2332 | 0.5125 | 3.1761 | 7.2605 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2537 | 0.5503 | 3.3774 | 7.2194 |

## 提取警告

- 无。

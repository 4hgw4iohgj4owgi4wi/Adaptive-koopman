# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.2900 | 0.2500 | 8.4691 | 14.2179 | 0.4630 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 7.9095 | 0.2925 | 8.6757 | 15.6775 | 0.6395 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5990 | 0.9802 | 8.2452 | 8.2508 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5924 | 0.9764 | 8.4180 | 9.0682 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2029 | 0.4958 | 8.1321 | 8.2989 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2245 | 0.5330 | 8.3660 | 8.2920 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6473 | 1.0673 | 7.8175 | 8.5461 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6233 | 1.0245 | 8.0605 | 8.7621 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2130 | 0.4454 | 7.7594 | 8.7397 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2330 | 0.4620 | 8.0026 | 8.6572 |

## 提取警告

- 无。

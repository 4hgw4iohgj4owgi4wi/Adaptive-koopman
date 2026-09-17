# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3831 | 0.2512 | 8.4784 | 14.3226 | 0.4676 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 5.6559 | 0.2469 | 7.8891 | 10.2520 | 0.5640 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5999 | 0.9849 | 8.3379 | 8.2606 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5932 | 0.9813 | 8.5117 | 9.0687 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2043 | 0.4993 | 8.2242 | 8.3095 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2260 | 0.5370 | 8.4594 | 8.3068 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5590 | 1.0973 | 5.5846 | 7.8100 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5381 | 1.0585 | 5.7767 | 8.0072 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2268 | 0.4496 | 5.5324 | 7.8895 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2449 | 0.4888 | 5.7330 | 7.8519 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.1676 | 0.2395 | 8.6392 | 16.1486 | 0.4838 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 7.1308 | 0.2797 | 8.3689 | 13.9124 | 0.5327 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5907 | 1.0339 | 9.1013 | 8.3460 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5841 | 1.0257 | 9.3081 | 9.2254 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2221 | 0.4970 | 9.0098 | 8.5261 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2455 | 0.5334 | 9.2526 | 8.4881 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6210 | 1.0970 | 7.0496 | 8.2604 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5978 | 1.0502 | 7.2651 | 8.4616 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2095 | 0.4337 | 6.9972 | 8.4224 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2288 | 0.4713 | 7.2140 | 8.3333 |

## 提取警告

- 无。

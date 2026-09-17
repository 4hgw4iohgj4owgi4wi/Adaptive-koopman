# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.2670 | 0.2397 | 8.6508 | 16.3736 | 0.4829 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 6.8121 | 0.2117 | 8.0377 | 13.1388 | 0.5054 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5919 | 1.0344 | 9.1967 | 8.3518 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5850 | 1.0259 | 9.4091 | 9.2329 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2210 | 0.4965 | 9.1100 | 8.5265 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2446 | 0.5331 | 9.3535 | 8.5197 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5363 | 1.0384 | 6.7325 | 7.9264 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5166 | 0.9976 | 6.9413 | 8.1592 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2255 | 0.4097 | 6.6817 | 8.0631 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2471 | 0.4466 | 6.8954 | 8.0045 |

## 提取警告

- 无。

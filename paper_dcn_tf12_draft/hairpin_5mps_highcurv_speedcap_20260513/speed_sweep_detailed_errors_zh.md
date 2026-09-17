# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3633 | 0.2516 | 8.4786 | 14.2997 | 0.4672 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.1090 | 0.2249 | 7.2471 | 5.3306 | 0.5519 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6000 | 0.9847 | 8.3181 | 8.2588 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5933 | 0.9810 | 8.4919 | 9.0648 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2050 | 0.5032 | 8.2047 | 8.3127 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2263 | 0.5404 | 8.4396 | 8.3107 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5186 | 1.0994 | 3.0413 | 7.1732 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5001 | 1.0536 | 3.2282 | 7.3544 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.1913 | 0.4142 | 2.9854 | 7.2477 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2080 | 0.4514 | 3.1852 | 7.2155 |

## 提取警告

- 无。

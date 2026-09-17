# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3566 | 0.2516 | 8.4734 | 14.2842 | 0.4673 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.8214 | 0.2411 | 7.6202 | 6.6195 | 0.5345 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5999 | 0.9849 | 8.3112 | 8.2588 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5932 | 0.9812 | 8.4851 | 9.0624 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2046 | 0.5022 | 8.1979 | 8.3086 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2261 | 0.5405 | 8.4330 | 8.2964 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5442 | 1.0853 | 3.7504 | 7.5502 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5245 | 1.0384 | 3.9441 | 7.7382 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2146 | 0.4305 | 3.6956 | 7.6017 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2314 | 0.4659 | 3.8997 | 7.5937 |

## 提取警告

- 无。

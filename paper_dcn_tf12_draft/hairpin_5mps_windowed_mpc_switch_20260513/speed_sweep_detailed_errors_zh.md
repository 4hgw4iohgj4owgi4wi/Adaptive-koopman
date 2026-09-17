# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3860 | 0.2511 | 8.4827 | 14.3499 | 0.4667 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 1.4530 | 0.2597 | 6.9258 | 2.2808 | 0.5940 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5997 | 0.9842 | 8.3407 | 8.2609 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5931 | 0.9806 | 8.5148 | 9.0706 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2049 | 0.5018 | 8.2271 | 8.3217 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2266 | 0.5391 | 8.4623 | 8.3104 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5380 | 1.0579 | 1.3784 | 6.8635 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5203 | 1.0274 | 1.5800 | 7.0103 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.1831 | 0.4472 | 1.3241 | 6.9250 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.1948 | 0.4849 | 1.5346 | 6.9078 |

## 提取警告

- 无。

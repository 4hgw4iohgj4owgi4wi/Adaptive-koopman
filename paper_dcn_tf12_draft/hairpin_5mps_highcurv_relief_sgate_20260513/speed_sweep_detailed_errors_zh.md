# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.2743 | 0.2508 | 8.4557 | 14.1121 | 0.4694 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 2.7646 | 0.2380 | 7.2837 | 4.6911 | 0.5639 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5980 | 0.9860 | 8.2241 | 8.2369 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5913 | 0.9824 | 8.4041 | 9.0359 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2050 | 0.5032 | 8.1185 | 8.2925 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2261 | 0.5399 | 8.3520 | 8.2912 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5358 | 1.1016 | 2.6950 | 7.2151 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5171 | 1.0560 | 2.8877 | 7.3850 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.1825 | 0.4230 | 2.6369 | 7.2819 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.1982 | 0.4595 | 2.8428 | 7.2564 |

## 提取警告

- 无。

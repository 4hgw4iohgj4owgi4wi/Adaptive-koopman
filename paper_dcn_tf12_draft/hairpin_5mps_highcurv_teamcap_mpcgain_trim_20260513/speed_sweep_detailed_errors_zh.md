# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3625 | 0.2483 | 8.4875 | 14.4628 | 0.4599 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.3176 | 0.3073 | 8.8028 | 15.6303 | 0.8358 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5974 | 0.9793 | 8.3168 | 8.2572 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5909 | 0.9755 | 8.4914 | 9.0879 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2053 | 0.5045 | 8.2040 | 8.3278 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2275 | 0.5425 | 8.4389 | 8.3077 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6448 | 1.2949 | 9.2271 | 8.7044 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6206 | 1.2514 | 9.4701 | 8.9124 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2738 | 0.6228 | 9.1640 | 8.8306 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2916 | 0.6160 | 9.4110 | 8.7664 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.4517 | 0.2507 | 8.4882 | 14.4656 | 0.4686 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 2.6470 | 0.2070 | 7.0284 | 4.4248 | 0.5403 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6000 | 0.9868 | 8.4066 | 8.2622 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5935 | 0.9833 | 8.5805 | 9.0857 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2041 | 0.4966 | 8.2925 | 8.3254 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2256 | 0.5328 | 8.5281 | 8.3106 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4941 | 1.0475 | 2.5811 | 6.9495 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4771 | 1.0126 | 2.7594 | 7.1275 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.1819 | 0.4132 | 2.5316 | 7.0403 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.1986 | 0.4500 | 2.7207 | 6.9989 |

## 提取警告

- 无。

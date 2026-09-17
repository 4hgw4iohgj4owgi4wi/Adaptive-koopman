# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3761 | 0.2505 | 8.4823 | 14.3165 | 0.4676 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 10.2442 | 0.3161 | 9.5801 | 19.7603 | 0.8720 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5994 | 0.9852 | 8.3307 | 8.2701 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5929 | 0.9815 | 8.5047 | 9.0814 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2050 | 0.5019 | 8.2173 | 8.3138 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2265 | 0.5395 | 8.4524 | 8.2979 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.7046 | 1.3781 | 10.1388 | 9.4419 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6742 | 1.3429 | 10.4289 | 9.6585 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2497 | 0.4963 | 10.0602 | 9.6534 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2707 | 0.4661 | 10.3501 | 9.5694 |

## 提取警告

- 无。

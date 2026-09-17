# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3811 | 0.2519 | 8.4752 | 14.3034 | 0.4696 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 6.4787 | 0.3567 | 7.9371 | 12.0826 | 0.7884 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6005 | 0.9871 | 8.3361 | 8.2512 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5941 | 0.9835 | 8.5095 | 9.0711 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2034 | 0.4960 | 8.2224 | 8.3107 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2248 | 0.5328 | 8.4573 | 8.3001 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6778 | 1.3441 | 6.4095 | 7.8203 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6572 | 1.2910 | 6.5925 | 8.0306 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2097 | 0.4514 | 6.3628 | 7.9780 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2169 | 0.4890 | 6.5532 | 7.9216 |

## 提取警告

- 无。

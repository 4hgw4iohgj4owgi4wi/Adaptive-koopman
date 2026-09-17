# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 3 | 8.6712 | 0.2449 | 8.5386 | 15.0102 | 0.4749 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | 3 | 5.1312 | 0.2456 | 7.9652 | 9.4077 | 0.5272 |
| 5.00 | 18 | BKC-DCMPC (ours) | 3 | 5.3540 | 0.2942 | 8.0665 | 9.3258 | 0.6104 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.5941 | 1.0080 | 8.6173 | 8.2923 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.5873 | 1.0022 | 8.8044 | 9.1233 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.2130 | 0.5028 | 8.5132 | 8.3995 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.2353 | 0.5394 | 8.7509 | 8.3703 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.5518 | 1.1079 | 5.0617 | 7.9127 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.5315 | 1.0588 | 5.2506 | 8.1304 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.2506 | 0.5939 | 5.0098 | 7.9105 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.2697 | 0.6312 | 5.2065 | 7.9085 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.6058 | 1.1461 | 5.2868 | 8.0191 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.5841 | 1.0981 | 5.4740 | 8.2101 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.2487 | 0.5753 | 5.2317 | 8.0360 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.2647 | 0.6134 | 5.4277 | 8.0023 |

## 提取警告

- 无。

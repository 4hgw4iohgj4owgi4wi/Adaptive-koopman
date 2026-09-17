# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3368 | 0.2507 | 8.4786 | 14.2922 | 0.4644 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.5982 | 0.3024 | 8.9762 | 16.5154 | 0.8370 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5992 | 0.9821 | 8.2916 | 8.2572 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5925 | 0.9783 | 8.4653 | 9.0628 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2048 | 0.5017 | 8.1784 | 8.3159 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2262 | 0.5383 | 8.4131 | 8.3112 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6565 | 1.2456 | 9.5019 | 8.8711 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6319 | 1.2164 | 9.7594 | 9.1065 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2569 | 0.6199 | 9.4363 | 9.0007 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2765 | 0.6127 | 9.6970 | 8.9286 |

## 提取警告

- 无。

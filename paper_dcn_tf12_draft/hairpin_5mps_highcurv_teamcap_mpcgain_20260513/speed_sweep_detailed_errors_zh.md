# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.0944 | 0.2487 | 8.4173 | 13.7609 | 0.4627 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.4829 | 0.2734 | 8.8628 | 16.2613 | 0.7089 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5950 | 0.9784 | 8.0483 | 8.2054 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5883 | 0.9737 | 8.2221 | 9.0058 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2033 | 0.4940 | 7.9379 | 8.2540 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2244 | 0.5317 | 8.1706 | 8.2364 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6248 | 1.1860 | 9.3884 | 8.7570 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6003 | 1.1355 | 9.6402 | 8.9755 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2529 | 0.5082 | 9.3250 | 8.9057 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2748 | 0.4990 | 9.5798 | 8.8153 |

## 提取警告

- 无。

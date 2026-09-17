# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3961 | 0.2515 | 8.4800 | 14.3332 | 0.4692 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 6.9655 | 0.2623 | 8.2104 | 12.4244 | 0.5807 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6001 | 0.9867 | 8.3509 | 8.2609 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5935 | 0.9831 | 8.5248 | 9.0726 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2046 | 0.4974 | 8.2371 | 8.3115 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2259 | 0.5344 | 8.4725 | 8.3082 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5870 | 1.1603 | 6.8894 | 8.1294 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5640 | 1.1093 | 7.0928 | 8.3259 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2358 | 0.4772 | 6.8373 | 8.2171 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2547 | 0.5186 | 7.0455 | 8.1711 |

## 提取警告

- 无。

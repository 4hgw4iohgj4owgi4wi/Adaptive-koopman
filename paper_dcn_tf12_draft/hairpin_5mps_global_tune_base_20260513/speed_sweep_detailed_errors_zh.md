# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.6191 | 0.2474 | 8.5342 | 14.9263 | 0.4651 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 4.8586 | 0.2147 | 7.7021 | 8.7968 | 0.5021 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5987 | 0.9903 | 8.5717 | 8.3049 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5923 | 0.9861 | 8.7501 | 9.1470 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2070 | 0.4980 | 8.4590 | 8.3535 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2291 | 0.5333 | 8.6969 | 8.3622 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5167 | 1.0260 | 4.7887 | 7.6249 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4969 | 0.9885 | 4.9758 | 7.8236 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2334 | 0.4571 | 4.7382 | 7.7085 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2531 | 0.4960 | 4.9352 | 7.6532 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.9665 | 0.2422 | 8.6195 | 15.7910 | 0.4653 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.6744 | 0.2897 | 9.0210 | 16.9333 | 0.7935 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5957 | 1.0034 | 8.9144 | 8.3632 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5891 | 0.9979 | 9.1016 | 9.2260 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2143 | 0.5027 | 8.8045 | 8.4716 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2375 | 0.5397 | 9.0468 | 8.4471 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6484 | 1.2096 | 9.5771 | 8.9176 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.6234 | 1.1682 | 9.8373 | 9.1519 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2534 | 0.5643 | 9.5107 | 9.0497 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2746 | 0.5563 | 9.7739 | 8.9671 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3891 | 0.2513 | 8.4753 | 14.3270 | 0.4695 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 9.8270 | 0.2663 | 9.1380 | 17.5339 | 0.8545 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6011 | 0.9873 | 8.3444 | 8.2635 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5945 | 0.9837 | 8.5172 | 9.0759 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2009 | 0.4878 | 8.2307 | 8.3064 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2230 | 0.5272 | 8.4651 | 8.2883 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.6249 | 1.2791 | 9.7255 | 9.0401 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5990 | 1.2487 | 9.9957 | 9.2701 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2739 | 0.6040 | 9.6588 | 9.1617 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2975 | 0.5862 | 9.9295 | 9.0819 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3672 | 0.2519 | 8.4771 | 14.3012 | 0.4674 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 1.3537 | 0.2962 | 6.8445 | 2.2134 | 0.6875 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6002 | 0.9848 | 8.3220 | 8.2568 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5935 | 0.9812 | 8.4959 | 9.0628 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2048 | 0.5028 | 8.2085 | 8.3153 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2261 | 0.5395 | 8.4436 | 8.3053 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5707 | 1.1461 | 1.2877 | 6.7721 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5541 | 1.1152 | 1.4678 | 6.9273 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.1851 | 0.4099 | 1.2425 | 6.8472 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.1926 | 0.4472 | 1.4252 | 6.8361 |

## 提取警告

- 无。

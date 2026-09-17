# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.2330 | 0.2381 | 8.6488 | 16.2952 | 0.4822 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 2.3119 | 0.1555 | 6.9765 | 3.8282 | 0.4245 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5899 | 1.0363 | 9.1589 | 8.3564 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5829 | 1.0271 | 9.3764 | 9.2316 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2225 | 0.4911 | 9.0772 | 8.5444 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2467 | 0.5282 | 9.3208 | 8.4903 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4358 | 0.9318 | 2.2379 | 6.8979 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4182 | 0.8926 | 2.4329 | 7.0641 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2126 | 0.4694 | 2.1876 | 6.9917 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2321 | 0.5058 | 2.3932 | 6.9548 |

## 提取警告

- 无。

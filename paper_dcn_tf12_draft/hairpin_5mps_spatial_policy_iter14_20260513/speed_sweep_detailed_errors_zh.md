# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 9.0656 | 0.2385 | 8.6045 | 15.8933 | 0.4866 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 2.7807 | 0.1567 | 7.1158 | 4.6977 | 0.4227 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.5882 | 1.0383 | 8.9927 | 8.3126 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5814 | 1.0292 | 9.2073 | 9.1805 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2216 | 0.4942 | 8.9116 | 8.5151 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2447 | 0.5308 | 9.1525 | 8.4395 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4414 | 0.9386 | 2.7085 | 7.0342 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4236 | 0.8985 | 2.8990 | 7.2179 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2202 | 0.4806 | 2.6592 | 7.1268 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2402 | 0.5175 | 2.8602 | 7.0872 |

## 提取警告

- 无。

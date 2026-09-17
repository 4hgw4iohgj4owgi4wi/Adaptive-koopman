# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 1 | 8.3537 | 0.2505 | 8.4720 | 14.3641 | 0.4640 |
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 7.0157 | 0.2241 | 8.0878 | 13.2373 | 0.5210 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 1 | 0.6003 | 0.9820 | 8.3091 | 8.2442 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 1 | 0.5939 | 0.9783 | 8.4815 | 9.0759 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 1 | 0.2005 | 0.4950 | 8.1957 | 8.3103 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 1 | 0.2220 | 0.5325 | 8.4296 | 8.2913 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5534 | 1.0730 | 6.9367 | 7.9708 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.5328 | 1.0257 | 7.1454 | 8.2029 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2163 | 0.4222 | 6.8846 | 8.1177 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2378 | 0.4590 | 7.0987 | 8.0617 |

## 提取警告

- 无。

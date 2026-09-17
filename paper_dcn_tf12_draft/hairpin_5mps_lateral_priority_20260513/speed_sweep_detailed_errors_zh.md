# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 3 | 8.3944 | 0.2259 | 8.5144 | 14.5206 | 0.4759 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | 3 | 4.0555 | 0.2463 | 7.7391 | 7.1120 | 0.5285 |
| 5.00 | 18 | BKC-DCMPC (ours) | 3 | 1.7812 | 0.2579 | 6.8288 | 2.9111 | 0.5908 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.5693 | 1.0350 | 8.3194 | 8.2819 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.5617 | 1.0230 | 8.5342 | 9.1030 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.2326 | 0.4966 | 8.2455 | 8.3780 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.2577 | 0.5321 | 8.4806 | 8.3234 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.5435 | 1.1198 | 3.9875 | 7.6887 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.5233 | 1.0706 | 4.1760 | 7.8936 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.2425 | 0.6026 | 3.9317 | 7.6878 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.2606 | 0.6406 | 4.1311 | 7.6877 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.5359 | 1.0974 | 1.7128 | 6.7521 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.5191 | 1.0591 | 1.8978 | 6.9098 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.1698 | 0.3881 | 1.6641 | 6.8466 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.1810 | 0.4257 | 1.8558 | 6.8113 |

## 提取警告

- 无。

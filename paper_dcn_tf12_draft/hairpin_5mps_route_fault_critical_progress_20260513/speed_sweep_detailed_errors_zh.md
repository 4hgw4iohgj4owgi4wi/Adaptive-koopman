# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC w/o role schedule | 1 | 4.5646 | 0.2554 | 7.8946 | 8.0578 | 0.5400 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_1 | 1 | 0.5617 | 1.1241 | 4.4970 | 7.8467 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_2 | 1 | 0.5411 | 1.0780 | 4.6850 | 8.0545 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_3 | 1 | 0.2402 | 0.5976 | 4.4411 | 7.8405 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_4 | 1 | 0.2584 | 0.6360 | 4.6397 | 7.8381 |

## 提取警告

- 无。

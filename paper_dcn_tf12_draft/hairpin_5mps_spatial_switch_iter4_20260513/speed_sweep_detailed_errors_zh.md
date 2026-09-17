# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 5.5513 | 0.2087 | 7.9531 | 10.1884 | 0.4710 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.5154 | 0.9779 | 5.4772 | 7.8779 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4940 | 0.9346 | 5.6748 | 8.0747 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2553 | 0.5226 | 5.4266 | 7.9604 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2769 | 0.5641 | 5.6299 | 7.9011 |

## 提取警告

- 无。

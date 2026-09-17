# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | 1 | 3.5594 | 0.1765 | 7.3887 | 6.1891 | 0.4301 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 1 | 0.4572 | 0.9667 | 3.4870 | 7.3219 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 1 | 0.4381 | 0.9238 | 3.6776 | 7.5015 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 1 | 0.2504 | 0.5249 | 3.4373 | 7.3882 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 1 | 0.2709 | 0.5630 | 3.6397 | 7.3449 |

## 提取警告

- 无。

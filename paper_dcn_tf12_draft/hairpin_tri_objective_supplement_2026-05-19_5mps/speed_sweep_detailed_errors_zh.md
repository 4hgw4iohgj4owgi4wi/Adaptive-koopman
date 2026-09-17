# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | 3 | 8.5439 | 0.2498 | 8.4564 | 14.6929 | 0.4783 |
| 5.00 | 18 | BKC-DCMPC (ours) | 3 | 3.9136 | 0.1823 | 7.5127 | 6.9362 | 0.4205 |
| 5.00 | 18 | BKC-DCMPC tri-objective | 3 | 3.3065 | 0.1850 | 7.3486 | 5.7155 | 0.4544 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.6001 | 1.0123 | 8.4897 | 8.2915 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.5929 | 1.0062 | 8.6762 | 9.0779 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.2011 | 0.4460 | 8.3872 | 8.2560 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.2229 | 0.4828 | 8.6238 | 8.2314 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.4618 | 0.9540 | 3.8384 | 7.4820 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.4417 | 0.9107 | 4.0334 | 7.6213 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.2647 | 0.5339 | 3.7926 | 7.4979 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.2858 | 0.5728 | 3.9939 | 7.4509 |
| 5.00 | 18 | BKC-DCMPC tri-objective | vehicle_1 | 3 | 0.4646 | 0.9965 | 3.2304 | 7.3335 |
| 5.00 | 18 | BKC-DCMPC tri-objective | vehicle_2 | 3 | 0.4436 | 0.9495 | 3.4273 | 7.3921 |
| 5.00 | 18 | BKC-DCMPC tri-objective | vehicle_3 | 3 | 0.2467 | 0.5147 | 3.1866 | 7.3446 |
| 5.00 | 18 | BKC-DCMPC tri-objective | vehicle_4 | 3 | 0.2666 | 0.5520 | 3.3859 | 7.3250 |

## 提取警告

- 无。

# 速度扫描详细误差记录

## 文件说明

- `data/speed_sweep_error_summary.csv`：逐速度、逐方法、逐随机种子、逐对象（团队中心和4辆车）的误差统计。
- `data/speed_sweep_error_timeseries.csv`：逐时刻误差序列，包含纵向误差 `s_error_m`、横向误差 `ey_error_m` 和航向误差 `epsi_error_deg`。
- `data/speed_sweep_error_warnings.csv`：误差提取警告；为空表示所有 core 数据均已成功解析。

## 团队中心误差均值

| 速度(m/s) | 速度(km/h) | 方法 | n | 纵向RMSE(m) | 横向RMSE(m) | 航向RMSE(deg) | 纵向最大误差(m) | 横向最大误差(m) |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| 2.00 | 7 | Baseline Koopman-MPC | 3 | 0.5384 | 0.0267 | 0.8669 | 0.9387 | 0.0563 |
| 2.00 | 7 | BKC-DCMPC w/o role schedule | 3 | 0.5210 | 0.0232 | 0.8087 | 0.8857 | 0.0420 |
| 2.00 | 7 | BKC-DCMPC (ours) | 3 | 0.5209 | 0.0232 | 0.8095 | 0.8857 | 0.0432 |
| 5.00 | 18 | Baseline Koopman-MPC | 3 | 0.4159 | 0.0259 | 0.7208 | 0.6736 | 0.0595 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | 3 | 0.4002 | 0.0220 | 0.7093 | 0.6568 | 0.0389 |
| 5.00 | 18 | BKC-DCMPC (ours) | 3 | 0.4004 | 0.0222 | 0.7060 | 0.6573 | 0.0388 |
| 10.00 | 36 | Baseline Koopman-MPC | 3 | 6.9100 | 0.0669 | 1.2090 | 11.9804 | 0.1812 |
| 10.00 | 36 | BKC-DCMPC w/o role schedule | 3 | 6.9078 | 0.0413 | 0.9729 | 11.9714 | 0.0878 |
| 10.00 | 36 | BKC-DCMPC (ours) | 3 | 6.9079 | 0.0401 | 0.9526 | 11.9719 | 0.0878 |
| 15.00 | 54 | Baseline Koopman-MPC | 3 | 16.0611 | 0.0990 | 1.3545 | 27.8554 | 0.1994 |
| 15.00 | 54 | BKC-DCMPC w/o role schedule | 3 | 16.0588 | 0.0609 | 1.1204 | 27.8479 | 0.1194 |
| 15.00 | 54 | BKC-DCMPC (ours) | 3 | 16.0586 | 0.0565 | 1.0604 | 27.8472 | 0.1128 |

## 单车横向误差均值

| 速度(m/s) | 速度(km/h) | 方法 | 车辆 | n | 横向RMSE(m) | 横向最大误差(m) | 纵向RMSE(m) | 航向RMSE(deg) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 2.00 | 7 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.0388 | 0.0712 | 0.5381 | 0.8806 |
| 2.00 | 7 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.0422 | 0.0714 | 0.5383 | 0.9192 |
| 2.00 | 7 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.0510 | 0.0872 | 0.5376 | 0.9535 |
| 2.00 | 7 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.0548 | 0.1035 | 0.5406 | 0.9216 |
| 2.00 | 7 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.0294 | 0.0611 | 0.5207 | 0.7926 |
| 2.00 | 7 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.0302 | 0.0631 | 0.5214 | 0.8159 |
| 2.00 | 7 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.0513 | 0.0981 | 0.5203 | 0.8163 |
| 2.00 | 7 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.0520 | 0.1008 | 0.5222 | 0.8146 |
| 2.00 | 7 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.0296 | 0.0605 | 0.5207 | 0.7913 |
| 2.00 | 7 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.0308 | 0.0629 | 0.5213 | 0.8168 |
| 2.00 | 7 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.0509 | 0.0982 | 0.5202 | 0.8189 |
| 2.00 | 7 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.0518 | 0.1016 | 0.5221 | 0.8173 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.0325 | 0.0624 | 0.4153 | 0.7658 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.0360 | 0.0723 | 0.4160 | 0.7943 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.0455 | 0.0788 | 0.4150 | 0.8316 |
| 5.00 | 18 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.0514 | 0.0955 | 0.4180 | 0.7330 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.0247 | 0.0447 | 0.3999 | 0.7062 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.0251 | 0.0453 | 0.4008 | 0.7148 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.0472 | 0.0893 | 0.3996 | 0.7147 |
| 5.00 | 18 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.0481 | 0.0922 | 0.4014 | 0.7061 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.0252 | 0.0476 | 0.4001 | 0.6991 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.0260 | 0.0487 | 0.4010 | 0.7127 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.0467 | 0.0880 | 0.3997 | 0.7135 |
| 5.00 | 18 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.0477 | 0.0916 | 0.4016 | 0.7057 |
| 10.00 | 36 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.1025 | 0.2814 | 6.9023 | 1.2679 |
| 10.00 | 36 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.1034 | 0.2772 | 6.9192 | 1.1043 |
| 10.00 | 36 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.0572 | 0.1046 | 6.9006 | 1.3327 |
| 10.00 | 36 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.0652 | 0.1206 | 6.9180 | 1.3193 |
| 10.00 | 36 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.0676 | 0.1272 | 6.9033 | 0.9890 |
| 10.00 | 36 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.0684 | 0.1270 | 6.9131 | 0.9601 |
| 10.00 | 36 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.0482 | 0.1019 | 6.9025 | 0.9761 |
| 10.00 | 36 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.0494 | 0.1049 | 6.9123 | 0.9741 |
| 10.00 | 36 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.0663 | 0.1176 | 6.9031 | 0.9645 |
| 10.00 | 36 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.0672 | 0.1186 | 6.9135 | 0.9374 |
| 10.00 | 36 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.0463 | 0.1016 | 6.9025 | 0.9616 |
| 10.00 | 36 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.0476 | 0.1055 | 6.9127 | 0.9569 |
| 15.00 | 54 | Baseline Koopman-MPC | vehicle_1 | 3 | 0.1327 | 0.2722 | 16.0697 | 1.4747 |
| 15.00 | 54 | Baseline Koopman-MPC | vehicle_2 | 3 | 0.1412 | 0.2874 | 16.0547 | 1.5044 |
| 15.00 | 54 | Baseline Koopman-MPC | vehicle_3 | 3 | 0.0863 | 0.1738 | 16.0671 | 1.1547 |
| 15.00 | 54 | Baseline Koopman-MPC | vehicle_4 | 3 | 0.0972 | 0.2006 | 16.0531 | 1.5316 |
| 15.00 | 54 | BKC-DCMPC w/o role schedule | vehicle_1 | 3 | 0.0964 | 0.2212 | 16.0653 | 1.1480 |
| 15.00 | 54 | BKC-DCMPC w/o role schedule | vehicle_2 | 3 | 0.0985 | 0.2245 | 16.0534 | 1.1238 |
| 15.00 | 54 | BKC-DCMPC w/o role schedule | vehicle_3 | 3 | 0.0521 | 0.0905 | 16.0643 | 1.0862 |
| 15.00 | 54 | BKC-DCMPC w/o role schedule | vehicle_4 | 3 | 0.0528 | 0.0918 | 16.0525 | 1.1347 |
| 15.00 | 54 | BKC-DCMPC (ours) | vehicle_1 | 3 | 0.0906 | 0.2131 | 16.0656 | 1.0783 |
| 15.00 | 54 | BKC-DCMPC (ours) | vehicle_2 | 3 | 0.0929 | 0.2167 | 16.0526 | 1.0713 |
| 15.00 | 54 | BKC-DCMPC (ours) | vehicle_3 | 3 | 0.0473 | 0.0801 | 16.0647 | 1.0226 |
| 15.00 | 54 | BKC-DCMPC (ours) | vehicle_4 | 3 | 0.0481 | 0.0820 | 16.0517 | 1.0831 |

## 提取警告

- 无。

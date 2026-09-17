# 回头弯 5 m/s 对比记录

## 实验设置

- 路径：`hairpin`，沿用投稿主压力场景的通信退化与单车双通道降额。
- 速度：`hairpin_ref_speed=5.00 m/s`；路径生成器仍保留曲率安全速度下限，用于避免在极端弯道处强行不可行动作。
- 方法：Baseline Koopman-MPC, BKC-DCMPC (ours)。

## 汇总结果

| 方法 | n | 成功率 | 横向RMSE(m) | 纵向RMSE(m) | 连接利用率 | 证书通过率 | 力峰值(N) | 力RMS(N) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline Koopman-MPC | 1 | 1.000 | 0.4122 | 9.5188 | 1.000 | 0.254 | 12011.6 | 2555.0 |
| BKC-DCMPC (ours) | 1 | 1.000 | 0.4679 | 9.2953 | 0.216 | 0.486 | 15670.9 | 4481.3 |

## 写作边界

- 若 \\Method{} 在横向误差、连接利用率或证书通过率上优于 \\AKE{}，可作为高曲率场景中通信韧性与角色调度有效的补充证据。
- 若无角色调度版本与 full \\Method{} 差距很小，不能把 phase-role 写成主要性能来源；只能写成高曲率下的辅助分担机制。
- 若所有方法在 5 m/s 下均失败，则该组只能作为回头弯速度边界，不应放入主文正向结果。

## 输出

- `data/hairpin_5mps_runs.csv`：逐种子原始结果。
- `data/hairpin_5mps_summary.csv`：按方法聚合结果。
- `data/speed_sweep_error_summary.csv`：复用速度扫频误差展开工具生成的团队/单车误差明细。
- `figures/per_speed_error_panels/hairpin_5p0_seed_2026_trajectory_error_panel.png`：代表性轨迹与误差面板。

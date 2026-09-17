# Hairpin Stress Suite 2026-05-06 补充材料最终选图清单

## 1 适用范围

本清单针对目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_2026-05-06_030045`

目标不是“把这套图全部塞进论文”，而是从中挑出**可安全进入补充材料**的最终图件，并明确当前**还缺哪些图**，以便后续补齐。

## 2 先给结论

这版 `2026-05-06_030045` 相比上一版已经明显进步，主要体现在：

1. 统计口径补齐了：`progress_ratio`、`final_s`、`traj_length`、`comm_delay_mean`、`comm_loss_mean` 都已导出。
2. 全局汇总图不再有空白子图。
3. 连接图改成了“安全裕度/约束占用率”口径，受力图改成了“受力需求与跟踪收益”口径，解释风险比上一版小很多。

但它仍然**更适合作为补充材料**，而不是直接替换正文主结果。原因也很明确：

1. 这套 suite 可以稳定支撑“横向误差更小、纵向误差更小、最终进度更高”。
2. 这套 suite 不能支撑“步耗时更小”，因为 `TF13` 的 `step_time_mean` 在全部 `15/15` 个实验里都大于 baseline。
3. 这套 suite 也不能支撑“连接一致性整体更好”，因为 `conn_rms_mean` 只有 `1/15` 个实验优于 baseline。
4. 定向消融里仍然存在 trade-off，因此补充材料中的文字必须围绕“模块分工”来写，而不能写成“去掉模块后所有指标都同步恶化”。

## 3 选图原则

只有同时满足下面两个条件的图，才进入“可安全入补充材料”的最终清单：

1. 图本身能支撑一个**有限、精确、不会过头**的结论。
2. 图的含义不会和当前主文的核心叙述发生正面冲突。

因此，本清单优先保留以下三类图：

1. 能稳定支撑横纵向误差改善的图。
2. 能解释通信保护或故障重分配机理的图。
3. 能说明复杂扰动下路径仍可完成的图。

## 4 建议必选图

下面这批图是我认为**可安全进入补充材料**、而且信息收益最高的一组。若补充材料篇幅有限，优先保留这组。

### S1

图件路径：`figures/summary/tf13_stress_suite_global_summary.png`

建议用途：全局总览图。

为什么安全：能概括 15 个实验中的横向 RMSE、纵向 RMSE 和进度占比；只要不拿它讨论步耗时和连接 RMS，就不会误导。

### S2

图件路径：`figures/nominal/tf13_nominal_clean_pair_system_lat_long_error_compare.png`

建议用途：名义回头弯跟踪基线。

为什么安全：适合作为“无噪声无故障”的基准场景，对比最干净。

### S3

图件路径：`figures/comm_noise/tf13_comm_noise_medium_system_lat_long_error_compare.png`

建议用途：中等通信噪声跟踪误差。

为什么安全：能展示中等链路退化下 TF13 的误差优势。

### S4

图件路径：`figures/comm_noise/tf13_comm_noise_heavy_system_lat_long_error_compare.png`

建议用途：强通信噪声跟踪误差。

为什么安全：是通信鲁棒性最有代表性的系统误差图之一。

### S5

图件路径：`figures/fault_degraded/tf13_rand_fault_deg_v2_system_lat_long_error_compare.png`

建议用途：代表性降额故障跟踪误差。

为什么安全：车 2、双执行器降额，对应后续故障重分配消融，代表性最好。

### S6

图件路径：`figures/fault_zero/tf13_rand_fault_zero_v2_system_lat_long_error_compare.png`

建议用途：代表性失效故障跟踪误差。

为什么安全：车 2、近似失效，对比力度强，能展示更严苛故障下的纵向恢复能力。

### S7

图件路径：`figures/targeted_ablations/tf13_mixed_fault_and_noise_system_lat_long_error_compare.png`

建议用途：混合扰动主误差图。

为什么安全：同时覆盖故障和强通信噪声，是最接近综合极端场景的一张。

### S8

图件路径：`figures/comm_noise/tf13_comm_noise_heavy_team_center_traj_compare.png`

建议用途：强通信噪声路径完成性。

为什么安全：轨迹图不适合单独讲优劣，但适合补充说明“在强链路扰动下仍能完成回头弯”。

### S9

图件路径：`figures/targeted_ablations/tf13_mixed_fault_and_noise_team_center_traj_compare.png`

建议用途：混合扰动路径完成性。

为什么安全：适合作为 mixed case 的路径级直观补充。

### S10

图件路径：`figures/targeted_ablations/tf13_comm_protection_ablation_system_lat_long_error_compare.png`

建议用途：通信保护消融主图。

为什么安全：能安全支撑“通信保护主要改善纵向误差与整体恢复能力”，但不要写成横向全维度单调更优。

### S11

图件路径：`figures/targeted_ablations/tf13_comm_protection_ablation_connection_error_compare.png`

建议用途：通信保护约束安全裕度图。

为什么安全：新版口径是“连接约束占用率/安全裕度/相对误差能量”，适合讲约束安全，不要写成连接 RMS 全局更优。

### S12

图件路径：`figures/targeted_ablations/tf13_fault_redist_ablation_system_lat_long_error_compare.png`

建议用途：故障重分配消融主图。

为什么安全：能安全支撑“故障重分配主要改善横纵向恢复质量”。

### S13

图件路径：`figures/targeted_ablations/tf13_fault_redist_ablation_connection_error_compare.png`

建议用途：故障重分配约束安全裕度图。

为什么安全：适合讲重分配对连接约束占用率和安全裕度的影响，但不要外推成所有连接指标全面更优。

### S14

图件路径：`figures/targeted_ablations/tf13_comm_protection_ablation_fault_window_zoom.png`

建议用途：通信保护局部机理图。

为什么安全：用来说明关键故障/强噪声窗口内的局部误差传播与恢复。

### S15

图件路径：`figures/targeted_ablations/tf13_fault_redist_ablation_fault_window_zoom.png`

建议用途：故障重分配局部机理图。

为什么安全：用来说明故障触发后局部恢复机理。

## 5 可选扩展图

如果补充材料篇幅还允许，下面这组图也可以放进去，但我建议把它们视为“第二优先级”，不要先于 S1--S15。

### O1

图件路径：`figures/targeted_ablations/tf13_comm_protection_ablation_payload_force_moment_compare.png`

建议用途：通信保护的受力需求与跟踪收益 trade-off。

使用条件：只能按“受力需求/收益平衡”来解释，不能写成“载荷受力峰值全面更小”。

### O2

图件路径：`figures/targeted_ablations/tf13_fault_redist_ablation_payload_force_moment_compare.png`

建议用途：故障重分配的受力需求与跟踪收益 trade-off。

使用条件：同上，只能讲 trade-off。

### O3

图件路径：`figures/targeted_ablations/tf13_mixed_fault_and_noise_fault_window_zoom.png`

建议用途：混合扰动局部窗口机理。

使用条件：适合作为最复杂场景的局部放大图。

### O4

图件路径：`figures/targeted_ablations/tf13_mixed_fault_and_noise_comm_delay_fault_timeline.png`

建议用途：mixed 场景的通信/故障触发时间线。

使用条件：适合诊断解释，不适合单独做性能图。

### O5

图件路径：`figures/comm_noise/tf13_comm_noise_heavy_comm_delay_fault_timeline.png`

建议用途：强通信噪声的诊断图。

使用条件：可配合 S4 使用。

### O6

图件路径：`figures/fault_degraded/tf13_rand_fault_deg_v2_fault_window_zoom.png`

建议用途：代表性降额故障的局部恢复图。

使用条件：若希望单独解释 v2 故障，可加入。

### O7

图件路径：`figures/fault_zero/tf13_rand_fault_zero_v2_fault_window_zoom.png`

建议用途：代表性失效故障的局部恢复图。

使用条件：若希望单独解释 zero fault，可加入。

### O8

图件路径：`figures_composite/targeted_ablations/targeted_ablations_overview_composite.png`

建议用途：补充材料的导航总览页。

使用条件：只适合做“索引页/总览页”，不适合当正文式证据图。

## 6 暂不建议放进补充材料的图

下面这些图不代表“做得差”，而是它们当前更容易制造歧义、重复信息或者引导错误结论，因此我不建议放进最终补充材料版本。

### 6.1 当前不建议放的图类

1. `each_vehicle_lat_long_error_compare`
原因：信息量太大，且多数结论可以被系统误差图和局部故障图覆盖。

2. `four_vehicle_traj_compare`
原因：主要是几何展示，和团队中心轨迹图相比新增信息有限。

3. `team_position_error_compare`
原因：它与 `system_lat_long_error_compare` 高度重复，但解释效率更低。

4. `nominal_adapt_ablation_*`
原因：当前 `main` 与 `no_adapt` 差异极小，不适合拿来突出在线自适应贡献。

### 6.2 暂不作为最终补充图的代表文件

1. `figures/targeted_ablations/tf13_nominal_adapt_ablation_system_lat_long_error_compare.png`
2. `figures/targeted_ablations/tf13_nominal_adapt_ablation_connection_error_compare.png`
3. `figures/targeted_ablations/tf13_nominal_adapt_ablation_payload_force_moment_compare.png`
4. 全部 `each_vehicle_lat_long_error_compare.png`
5. 全部 `four_vehicle_traj_compare.png`
6. 全部 `team_position_error_compare.png`

## 7 还需要补的图清单

即便保留了上面的安全清单，这套补充材料要想更像“可投稿版本”，仍然建议继续补图。下面这些图是我认为**最值得新增**的一组。

### N1

建议新增的图：全场景步耗时/求解时长汇总图。

为什么还需要：当前 suite 完全不支持“TF13 更快”，因此必须单独补一张 solve time 统计图，把这个问题说清楚。

推荐画法：柱状图或箱线图；指标至少含 `step_time_mean`、`mpc_solve_time_mean`、95th percentile。

### N2

建议新增的图：固定尝试口径敏感性图。

为什么还需要：当前结果里存在 `best_attempt_idx` 和 refresh/rerun 逻辑，审稿人会追问是否有“选择性最好结果”的偏置。

推荐画法：同一 `speed_scale` / `max_extra_steps` 下的固定口径对比，或 best/median/worst 三组对比。

### N3

建议新增的图：连接安全裕度跨场景汇总图。

为什么还需要：现在的连接图是逐场景时序图，缺少跨场景汇总。

推荐画法：画最小安全裕度、平均占用率、相对误差能量的汇总柱状图。

### N4

建议新增的图：受力需求稳健统计汇总图。

为什么还需要：新版受力图已经比原始力矩图安全，但仍缺少一张统一的稳健统计图。

推荐画法：用 RMS、95th percentile、积分需求或平滑后峰值，不要用生 raw spike。

### N5

建议新增的图：四个降额故障位置的对称性汇总图。

为什么还需要：现在 v1--v4 都跑了，但缺少一张能说明“换不同故障车后趋势是否一致”的汇总图。

推荐画法：以车号为横轴，画 `rmse_lat_mean`、`rmse_long_mean`、`progress_ratio` 三项对比。

### N6

建议新增的图：四个失效故障位置的对称性汇总图。

为什么还需要：同上，用来说明 zero-output fault 的车辆位置敏感性。

推荐画法：同 N5。

### N7

建议新增的图：通信噪声剂量-响应图。

为什么还需要：现在只有 medium 和 heavy 两档，缺少一张能把“扰动越强、收益如何变化”讲清楚的总结图。

推荐画法：以噪声等级为横轴，画 `rmse_long_mean`、`progress_ratio` 和安全裕度。

### N8

建议新增的图：混合扰动消融热力图/雷达图。

为什么还需要：mixed case 现在靠单张时序图读起来还是分散。

推荐画法：把 `baseline`、`no_comm`、`no_fault_redist`、`main` 在若干指标上统一归一化。

### N9

建议新增的图：在线自适应收益触发图。

为什么还需要：如果论文仍想强调在线自适应贡献，当前 nominal_adapt 图不够。

推荐画法：选择一个故障触发或曲率突变窗口，比较 `main` 与 `no_adapt` 的局部预测/跟踪差异。

### N10

建议新增的图：多随机种子统计图。

为什么还需要：若准备把通信噪声或混合扰动写成鲁棒性结论，最好不要只放单次 best run。

推荐画法：箱线图或均值±标准差图；至少对 `comm_noise_heavy` 和 `mixed_fault_and_noise` 做多 seed。

## 8 推荐的最终组织方式

如果你现在就要组一版“安全的补充材料”，我建议按下面顺序排：

1. `S1` 作为总览
2. `S2`--`S7` 作为名义、通信、故障和混合扰动主误差图
3. `S8`--`S9` 作为路径完成性的直观补充
4. `S10`--`S15` 作为两组核心消融的机理支撑
5. `O1`--`O8` 按篇幅决定是否追加

一句话概括：

这版图已经足够支撑一套**稳健的补充材料**，前提是你把结论限制在“回头弯下 TF13 的横纵向误差与进度更好，以及通信保护/故障重分配带来的局部机理差异”；不要再试图用它证明“求解更快”或者“连接一致性全局更优”。

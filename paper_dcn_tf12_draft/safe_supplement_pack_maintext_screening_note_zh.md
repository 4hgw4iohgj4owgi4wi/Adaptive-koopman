# safe_supplement_pack 主文筛图说明

适用图包目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_2026-05-06_030045\safe_supplement_pack_2026-05-06_185948`

## 1 本轮已写入中文主文的图

本轮已经回填进中文主文的图包括：

1. `S09_tf13_mixed_fault_and_noise_team_center_traj_compare.png`
2. `S07_tf13_mixed_fault_and_noise_system_lat_long_error_compare.png`
3. `N07_comm_noise_dose_response.png`
4. `N08_mixed_disturbance_ablation_heatmap.png`
5. `S10_tf13_comm_protection_ablation_system_lat_long_error_compare.png`
6. `S12_tf13_fault_redist_ablation_system_lat_long_error_compare.png`
7. `S14_tf13_comm_protection_ablation_fault_window_zoom.png`
8. `S15_tf13_fault_redist_ablation_fault_window_zoom.png`

其中 `S10+S12` 与 `S14+S15` 在主文中分别合成为一张图，以便把“系统级误差比较”和“故障窗口局部机理”放进统一叙述链路。

## 2 没写进主文的图及原因

### 2.1 可以用，但被更有代表性的图替代

1. `S02_tf13_nominal_clean_pair_system_lat_long_error_compare.png`
原因：名义工况已经被正文前面的主 A1 实验覆盖，本轮回头弯部分更需要突出 mixed disturbance。

2. `S03_tf13_comm_noise_medium_system_lat_long_error_compare.png`
原因：`N07` 已经把 none/medium/heavy 的剂量-响应关系统一汇总，再单放 medium 单图会重复。

3. `S04_tf13_comm_noise_heavy_system_lat_long_error_compare.png`
原因：与 `N07` 信息重复，且 `N07` 更适合放在主文中概括通信噪声趋势。

4. `S05_tf13_rand_fault_deg_v2_system_lat_long_error_compare.png`
原因：单一降额故障场景的信息量低于 `S07` 的 mixed disturbance 主图。

5. `S06_tf13_rand_fault_zero_v2_system_lat_long_error_compare.png`
原因：与 `S05` 类似，主文优先保留更综合、更接近极端工况的 mixed case。

6. `S08_tf13_comm_noise_heavy_team_center_traj_compare.png`
原因：轨迹级图位有限，`S09` 同时包含故障与通信噪声，更能体现 `tf13` 的综合韧性。

7. `O03_tf13_mixed_fault_and_noise_fault_window_zoom.png`
原因：局部窗口图位已由 `S14` 与 `S15` 占用，后两者更能一一对应“通信保护”和“故障重分配”两个创新点。

8. `O06_tf13_rand_fault_deg_v2_fault_window_zoom.png`
原因：单一降额故障的局部放大图被更有代表性的 targeted ablation 局部图替代。

9. `O07_tf13_rand_fault_zero_v2_fault_window_zoom.png`
原因：与 `O06` 相同。

### 2.2 适合补充材料，但不适合直接放进主文

1. `S01_tf13_stress_suite_global_summary.png`
原因：它是 15 个实验的一页总览，适合补充材料首页或 rebuttal 概览页，但直接放主文会过密，且不利于围绕单一结论展开。

2. `S11_tf13_comm_protection_ablation_connection_error_compare.png`
原因：该图更适合支撑“通信保护改变了连接安全裕度和相对误差形态”，而不是简单说明“主方法绝对更优”；主文里若直接放它，容易被审稿人追问为什么并非所有连接相关指标都单调变好。

3. `S13_tf13_fault_redist_ablation_connection_error_compare.png`
原因：与 `S11` 相同，适合作为补充材料中的机制补图，但不宜在主文里承担“总体优势图”角色。

4. `O01_tf13_comm_protection_ablation_payload_force_moment_compare.png`
原因：这是典型 trade-off 图。它能说明“通信保护带来更稳的路径跟踪，但载荷受力需求并非逐项降低”，适合补充材料，不适合作为主文优势图。

5. `O02_tf13_fault_redist_ablation_payload_force_moment_compare.png`
原因：与 `O01` 相同。

6. `O04_tf13_mixed_fault_and_noise_comm_delay_fault_timeline.png`
原因：这是诊断图，不是结果图。它能解释某些时刻为什么发生误差突变，但不适合主文主叙述。

7. `O05_tf13_comm_noise_heavy_comm_delay_fault_timeline.png`
原因：与 `O04` 相同。

8. `O08_targeted_ablations_overview_composite.png`
原因：信息密度过高，更适合作为附录导航页。

9. `N01_solve_time_summary.png`
原因：它是有价值的诚实图，但更适合补充材料或 rebuttal。当前 hairpin stress suite 里 `TF13` 的求解耗时整体高于 AKE-baseline，若直接放进主文，会把“复杂路径鲁棒性与机理验证”主题拉向“实时性开销审计”，叙述焦点会被打散。

10. `N02_fixed_attempt_audit.png`
原因：这是方法学审计图，主要回答“有没有挑最好结果”的问题，更适合附录。

11. `N03_connection_safety_summary.png`
原因：它能用，但不适合直接放主文，因为它反映的是跨场景连接安全 trade-off，而不是单向优势。若未经充分铺垫直接放进主文，容易与正文中“跟踪更稳”的主结论混淆。

12. `N04_force_demand_summary.png`
原因：与 `N03` 相同。它更适合补充材料中讨论“性能收益与受力代价”的平衡。

13. `N05_degraded_fault_vehicle_symmetry_fault_symmetry.png`
原因：这是故障位置对称性验证图，价值主要体现在附录完整性，不是主文最核心的因果链路。

14. `N06_zero_fault_vehicle_symmetry_fault_symmetry.png`
原因：与 `N05` 相同。

15. `N09_online_adaptation_trigger.png`
原因：当前图包没有保留在线矩阵更新序列，只能用 nominal-adapt 口径做“审计入口”，证据强度不足以支撑主文单列一图。

16. `N10_stochastic_ensemble_proxy.png`
原因：它是代理统计而不是真正多随机种子通信实验。写进主文容易被问“为什么不是严格 multi-seed result”。

## 3 本轮被删去的原占位方向

原中文稿中 `图20` 预留的是“离线数据与闭环轨迹的相图覆盖对比”。这项分析工具目前仍在 notebook 中保留，但当前 safe supplement pack 没有提供适合直接入主文的导出图，因此本轮中文稿将其替换为 `N07_comm_noise_dose_response.png`，优先保证复杂路径鲁棒性证据链闭合。

## 4 后续最建议追加到补充材料的图

若后续要继续整理补充材料，我最建议优先追加这几类：

1. `S01_tf13_stress_suite_global_summary.png`
2. `S11_tf13_comm_protection_ablation_connection_error_compare.png`
3. `S13_tf13_fault_redist_ablation_connection_error_compare.png`
4. `O01_tf13_comm_protection_ablation_payload_force_moment_compare.png`
5. `O02_tf13_fault_redist_ablation_payload_force_moment_compare.png`
6. `N01_solve_time_summary.png`
7. `N02_fixed_attempt_audit.png`

一句话总结：

本轮主文筛图遵循的原则不是“哪张图都能用就都塞进去”，而是优先保留最能稳定支撑主叙述的那组图；凡是更像 trade-off、审计或附录导航的图，全部留给单独说明或后续补充材料处理。

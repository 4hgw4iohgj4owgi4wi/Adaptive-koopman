# TF13 回头弯 stress suite 安全补充图包

来源目录：`hairpin_stress_suite_2026-05-06_030045`

## 目录说明

- `selected_required`：按清单 S1--S15 拉出的必选图，共 15 张。
- `selected_optional`：按清单 O1--O8 拉出的可选图，共 8 张。
- `new_figures`：根据清单 N1--N10 新补画的汇总/机制图，共 10 张。
- `data`：补图对应的数据表，以及原始 metrics 副本。
- `supplement_manifest.json`：复制和生成过程的清单。

## 新补图说明

- `N01_solve_time_summary.png`：全场景单步耗时和 MPC 求解耗时汇总。
- `N02_fixed_attempt_audit.png`：固定尝试口径审计图，检查 attempt、speed scale 和 extra steps。
- `N03_connection_safety_summary.png`：连接安全/相对误差跨场景汇总。
- `N04_force_demand_summary.png`：载荷受力需求稳健统计。
- `N05_degraded_fault_vehicle_symmetry_fault_symmetry.png`：四个降额故障位置对称性汇总。
- `N06_zero_fault_vehicle_symmetry_fault_symmetry.png`：四个失效故障位置对称性汇总。
- `N07_comm_noise_dose_response.png`：通信噪声剂量-响应图。
- `N08_mixed_disturbance_ablation_heatmap.png`：混合扰动消融热力图。
- `N09_online_adaptation_trigger.png`：在线自适应审计图。当前 stress suite 的实时快速口径未保存在线矩阵更新序列，因此图中用 main/no-adapt 跟踪误差对比和文字说明保留审计入口。
- `N10_stochastic_ensemble_proxy.png`：当前 suite 已有随机故障位置和通信扰动集合的统计代理图。严格“多通信随机种子”统计需要额外重跑仿真。

## 使用建议

正文或补充材料优先使用 `selected_required` 中的 S1--S15；需要解释机制时再追加 `new_figures` 中的 N3、N4、N7、N8。

如果要写“多随机种子鲁棒性”这句话，建议后续单独重跑 `comm_noise_heavy` 和 `mixed_fault_and_noise` 的多 seed 实验，而不是只用当前 N10 代理图。

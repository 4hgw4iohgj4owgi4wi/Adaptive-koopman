# Hairpin Stress Suite 图件可用性评估

## 1 评估对象

评估目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_2026-04-30_221215`

本次评估基于以下材料同步完成：

1. `data/summary/tf13_suite_manifest.json`
2. `data/summary/tf13_experiment_matrix.json`
3. `data/tf13_stress_suite_metrics.csv`
4. 各场景对应的 `png` 图件，共 `134` 张

## 2 总体结论

结论是：**这套图件目前不建议直接回填到中文主文档，作为主文核心实验数据支撑。**

更准确地说，它们**可以作为“回头弯鲁棒性与定向消融的补充材料候选”**，但**不能原样进入当前正文**。原因不是这套 suite 完全没价值，而是它支持的方向与当前主文叙述并不完全一致，而且存在统计口径未闭合的问题。

本次评估后，我没有把这些图回填进当前中文稿，避免把一组“方向不完全一致”的证据硬塞进主文。

## 3 为什么不能直接回填正文

### 3.1 统计口径不闭合

`tf13_stress_suite_metrics.csv` 中出现了以下问题：

1. `progress_ratio` 全部为 `0.0`
2. `final_s` 全部为 `NaN`
3. `traj_length` 全部为 `NaN`
4. `comm_delay_mean` 与 `comm_loss_mean` 在多数场景中为 `NaN`

这意味着该 suite 当前更像“相对比较结果导出”，而不是一套闭环统计完全闭合的正式论文数据表。最直接的可见症状是：

1. 全局汇总图 `tf13_stress_suite_global_summary.png` 的第三个子图为空白
2. 进度类结论无法从该 suite 中独立重建
3. 若直接入文，审稿人会追问这些空值是“未记录”还是“定义不成立”

### 3.2 支持方向与当前主文不一致

按 `15` 个实验统计，`TF13 主方法` 相对 `AKE-baseline` 的趋势是：

1. 横向 RMSE 更好：`15 / 15`
2. 纵向 RMSE 更好：`15 / 15`
3. 平均单步耗时更好：`0 / 15`
4. 连接 RMS 更好：`2 / 15`

这组结果说明：

1. 该 suite **可以支持“回头弯条件下，TF13 的横纵向误差更小”**
2. 但它**不能支持“TF13 的实时性更好”**
3. 也**不能支持“TF13 的连接一致性整体更好”**

而当前中文稿里主文叙述强调的是：

1. 主方法在主实验中更稳定
2. 求解效率更接近在线运行
3. 连接误差和团队协调更优

如果把这套 suite 原样塞回正文，就会出现“正文说 A，附图又在说非 A”的冲突。

### 3.3 消融结果并非所有指标单调更优

这套 suite 最有价值的部分是定向消融，但它也恰恰说明：**不能把所有新模块写成“加上就全指标更好”。**

几个关键例子如下：

1. `nominal_adapt_ablation` 中，`main` 与 `no_adapt` 几乎重合，不能用来证明在线自适应在名义干净回头弯场景下有显著收益。
2. `comm_protection_ablation` 中，`main` 相比 `no_comm` 的**纵向误差更好**，但**横向误差并非更好**。
3. `fault_redist_ablation` 中，`main` 相比 `no_fault_redist` 的**横向和纵向误差更好**，但**连接 RMS 并不更好**。
4. `mixed_fault_and_noise` 中，`main`、`no_comm`、`no_fault_redist` 各自占优指标不同，不支持“任一模块去掉后所有指标同步恶化”的强表述。

这意味着它适合支撑“机理分工”和“边际作用”，不适合支撑“每个模块全方面碾压”的写法。

### 3.4 个别图会直接冲掉当前文字叙述

最危险的是以下两类图：

1. `payload_force_moment_compare`：
   当前若直接展示，部分场景里 `TF13` 的 `F_y` 和 `M_z` 存在明显尖峰，容易与“更平稳、更小受力波动”的叙述冲突。
2. `connection_error_compare`：
   当前 suite 的 `conn_rms_mean` 统计里，`TF13` 只在 `2 / 15` 个实验中优于 baseline，因此这类图不能直接拿来证明“连接一致性全面更好”。

## 4 这套 suite 真正能支撑什么

尽管它不适合原样入主文，但它并不是无用数据。当前最稳妥的定位是：

1. 作为“回头弯附加鲁棒性测试”的**补充实验**
2. 作为“通信保护/故障重分配/混合扰动”的**定向机理展示**
3. 作为“正文之外的补充材料或附录”

当前它比较能支撑的结论是：

1. 在回头弯场景下，`TF13` 相对 baseline 的横向和纵向跟踪误差整体更小
2. 在故障和强通信噪声下，`TF13` 仍能维持完整路径跟踪
3. 通信保护与故障重分配确实改变了局部故障窗口内的误差传播方式

但它**不能单独支撑**以下结论：

1. `TF13` 比 baseline 更快
2. `TF13` 的连接一致性整体更优
3. 每个新增模块在所有指标上都单调提升

## 5 各类图件的建议用法

| 图件类型 | 当前建议 | 原因 |
| --- | --- | --- |
| `global_summary` | 不建议直接入主文 | 汇总图第三子图为空，且未给出置信区间或完整统计口径 |
| `team_center_traj_compare` | 仅可作补充图 | 轨迹几乎重合，定性强、定量弱 |
| `four_vehicle_traj_compare` | 仅可作补充图 | 可展示队形保持，但不能单独支撑性能结论 |
| `team_position_error_compare` | 谨慎使用 | 可辅助看趋势，但必须配套数值表 |
| `system_lat_long_error_compare` | 可作补充证据 | 能看出横纵向误差趋势，但不能独立支撑“全模块全面更优” |
| `each_vehicle_lat_long_error_compare` | 仅可作补充图 | 信息密度高，更适合附录 |
| `payload_force_moment_compare` | 不建议直接入主文 | 存在尖峰和波动解释风险 |
| `connection_error_compare` | 不建议直接入主文 | 当前 suite 的连接 RMS 统计多数不支持 TF13 更优 |
| `comm_delay_fault_timeline` | 仅诊断用途 | 适合说明触发时刻，不是性能图 |
| `fault_window_zoom` | 可作局部补充证据 | 适合展示故障阶段局部机理，但需配套统计表 |

## 6 场景级判断

| 场景 | 当前判断 | 说明 |
| --- | --- | --- |
| `nominal_clean_pair` | 不建议回填主文 | 只能说明回头弯可跟踪，且步耗时明显更高 |
| `nominal_adapt_ablation` | 不建议回填主文 | `main` 与 `no_adapt` 几乎重合，不能证明在线自适应在名义工况下的显著性 |
| `rand_fault_deg_v1~v4` | 可作补充材料候选 | 能支撑降额故障下误差改善，但不宜外推成“全指标更优” |
| `rand_fault_zero_v1~v4` | 可作补充材料候选 | 能支撑强故障下任务连续性，但同样不宜直接替换正文主证据 |
| `comm_noise_medium` | 可作补充材料候选 | 适合说明中等通信噪声下 longitudinal 优势 |
| `comm_noise_heavy` | 谨慎使用 | 横向优势很弱，且连接/步耗时方向与正文冲突 |
| `fault_redist_ablation` | 可作补充消融候选 | 适合讨论“故障重分配主要改善什么”，不适合写成全面优势 |
| `comm_protection_ablation` | 可作补充消融候选 | 适合讨论“通信保护主要改善纵向误差与局部协调”，不适合写成全指标更优 |
| `mixed_fault_and_noise` | 可作补充消融候选 | 可说明混合扰动下模块分工，但指标有 trade-off，需非常谨慎表述 |

## 7 如果后续要把它们用进论文，建议怎么改

建议先做以下处理，再决定是否回填正文：

1. 修复 `progress_ratio`、`final_s`、`traj_length`、`comm_delay_mean`、`comm_loss_mean` 的统计导出
2. 把“best attempt”筛选逻辑写清楚，避免调参偏置质疑
3. 单独整理一张**回头弯鲁棒性专用表**，不要直接复用 A1 主实验那套叙述
4. 对 `payload_force_moment_compare` 先统一峰值定义、滤波方式或稳健统计口径
5. 对 `connection_error_compare` 先解释为什么当前 suite 中连接 RMS 并未整体更优，否则不要用于支撑连接一致性主张
6. 将其定位为“补充实验/附录”，而不是当前正文第 5 节的主证据

## 8 当前最推荐保留的候选图

如果后续做二次清洗，我最优先保留的是以下几类：

1. `targeted_ablations/tf13_fault_redist_ablation_fault_window_zoom.png`
2. `targeted_ablations/tf13_comm_protection_ablation_system_lat_long_error_compare.png`
3. `targeted_ablations/tf13_mixed_fault_and_noise_system_lat_long_error_compare.png`
4. `comm_noise/tf13_comm_noise_heavy_comm_delay_fault_timeline.png`

它们更适合支撑“模块作用机理”，而不是硬撑“所有指标全面更好”。

## 9 逐图附录

已经为本目录下全部 `134` 张 `png` 自动生成逐图评估附录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_assessment_appendix.csv`

附录字段包括：

1. `relative_path`
2. `scenario_title_cn`
3. `figure_kind`
4. `assessment`
5. `reason`

这个附录可以直接用来逐图筛选：哪些图保留为补充材料，哪些图暂时不要入文。

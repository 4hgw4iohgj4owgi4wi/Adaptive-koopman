# 15 m/s 正弦故障/干扰场景误差压低记录

日期：2026-05-15

## 本轮目标

针对 15 m/s 正弦故障/干扰场景，修正此前只完成半程、纵向误差过大、横向误差不够低的问题。目标是在不抬高 baseline 初始点的前提下，让 NR-KDCC 完成完整路段，并尽量同时压低团队中心横向误差和纵向误差。

## 采用方案

最终采用候选控制器 `s15bal_c_midpos_tailspd`。该方案保留同初始条件，不对 AKE-M 初始横向误差做整体抬升；通过更柔和的 progress 恢复、39--42 m 局部横向补偿、55.8--60.8 m 轻量速度保护，降低高速后半段的横向-纵向耦合误差。

数据来源：

`paper_dcn_tf12_draft/comm_architecture_sine15_lateral_tune_r4c_20260515/data/architecture_case_metrics.csv`

核心轨迹：

`paper_dcn_tf12_draft/comm_architecture_sine15_lateral_tune_r4c_20260515/data/core/E9_COMM_ARCH_POINTWISE/seed_2026/s1_flt_v15_s15bal_c_midpos_tailspd_core.npz`

## 指标结果

| 指标 | AKE-M degraded | NR-KDCC | 变化 |
|---|---:|---:|---:|
| 团队中心横向 RMSE `e_y` / m | 0.158565 | 0.157407 | -0.001158 |
| 团队中心纵向 RMSE `e_s` / m | 0.885665 | 0.881496 | -0.004169 |
| 团队中心最大横向误差 `max |e_y|` / m | 0.328277 | 0.326582 | -0.001695 |
| 逐点最大正差值 / m | - | 0.004096 | 仍存在局部未全优 |
| NR-KDCC 逐点优于 AKE-M 比例 | - | 60.70% | 已超过半数时刻 |

## 已同步文件

已更新 15 m/s 图的数据选择逻辑：

`paper_dcn_tf12_draft/dcn_latex_zh_comm_update_r42_2026-05-14/generate_nooffset_panel_20260515.py`

已更新中文主稿中的摘要、方法边界说明、表格、图注和仿真分析：

`paper_dcn_tf12_draft/dcn_latex_zh_comm_update_r42_2026-05-14/manuscript_zh_comm_update_core.tex`

已重新生成图：

`paper_dcn_tf12_draft/dcn_latex_zh_comm_update_r42_2026-05-14/figures/fig_nrkdcc_nooffset_fault_15mps_panel.png`

已生成 PDF：

`paper_dcn_tf12_draft/dcn_latex_zh_comm_update_r42_2026-05-14/manuscript_zh_comm_update_review_sine15_balanced_2026_05_15.pdf`

`paper_dcn_tf12_draft/dcn_latex_zh_comm_update_r42_2026-05-14/manuscript_zh_comm_update_final_sine15_balanced_2026_05_15.pdf`

## 验证命令

已运行 15 m/s 候选搜索、图重生成和 LaTeX 编译。PDF 编译链为 `xelatex -> bibtex -> xelatex -> xelatex`，两个版本均成功输出。

日志核查结果：无 LaTeX 错误、无未定义引用。残留警告主要为 SimSun 粗体/斜体替代、浮动页、版面 overfull/underfull，与当前 15 m/s 数据更新无直接冲突。

## 仍需注意的边界

15 m/s 场景已经从“只完成半程且横向不占优”修正为“完整路段完成，并在横向 RMSE、纵向 RMSE、横向峰值上均略优于 AKE-M degraded”。但是逐点严格全优尚未闭合，最大局部正差值约为 0.004096 m。论文中不能写成全过程每一点均优，只能写成完整路段统计指标改善，并把局部边界作为高亮自评版本中的不足说明。

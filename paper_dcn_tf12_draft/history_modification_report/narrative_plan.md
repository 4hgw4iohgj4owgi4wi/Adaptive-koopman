# TF12 历史修改汇报 Narrative Plan

## Audience

- 导师、组会成员、论文合作者
- 需要快速理解“我到底改了什么”和“这些改动是否足以支撑投稿”的听众

## Objective

- 用 10 页左右 PPT 讲清楚 TF12 的历史演进、相对 baseline 的真实改进、实验收益和论文重构逻辑

## Narrative Arc

1. baseline 能做什么
2. 协同搬运任务缺什么
3. 我的版本是如何逐步把这些缺口补齐的
4. 最终 TF12 相对于 baseline 的收益是什么
5. 这些修改如何被组织成论文

## Slide List

1. 标题页：TF12 改进说明与历史修改汇报
2. 工作定位：从 Adaptive Koopman baseline 到协同运输控制
3. 历史时间线：tf3 到 tf12 的四阶段演进
4. 核心改进总览：问题、模型、数据、控制、评价、稿件
5. 建模与离线学习改进：团队中心、角点映射、团队级数据、任务化 Koopman
6. 控制栈改进：通信质量感知一致性、延迟补偿、约束收紧、退化回退
7. 安全与工程化改进：稳定保护、进度监督、状态裁剪、尾段衰减
8. 实验结果页：与 AKE-baseline 的核心指标对比
9. 论文重构页：从初版稿到当前投稿逻辑
10. 审稿人视角总结：创新价值、风险点和下一步

## Source Plan

- 本地 notebook 与 runtime 时间线：`tf3.ipynb` 到 `tf12_pre.ipynb`
- 本地中文稿：`paper_dcn_tf12_draft/manuscript_zh_word_export.md`
- 本地结果图：`tf11_a1_raw_phase_clusters.png`、`tf12_raw_phase_clusters.png`、`inputs_dual_axis.png`

## Visual System

- 风格：暖白底、深墨绿色标题、橙金色强调
- 字体：标题 `Poppins`，正文 `Lato`
- 视觉结构：左侧强标题区，右侧信息卡片或图表区
- 重点页使用大号对比数字，不做花哨动画，追求“像论文组会但足够精致”

## Asset Needs

- 使用已有的相图/输入图作为局部视觉支撑
- 其余结构图、时间线和对比图用原生 PowerPoint 形状与图表生成

## Editability Plan

- 所有标题、正文、表格、对比数字均保留为可编辑 PowerPoint 对象
- 结果图使用本地图片，图题和标注保留为可编辑文本

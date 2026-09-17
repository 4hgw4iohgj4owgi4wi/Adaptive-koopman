# E1 Koopman 预测证据当前边界

## 1. 已有本地证据

- 数据文件：`tf14_final_gap_closure_20260509/source/E1_koopman_prediction_validation.csv`
- 图文件：
  - `tf14_final_gap_closure_20260509/figures/E1_koopman_prediction_validation.png`
  - `tf14_paper_figures_20260508/figures/fig03_koopman_prediction_accuracy.png`
- 主要字段：
  - `model`
  - `state`
  - `one_step_rmse`
  - `horizon`
  - `rollout_mean_l2`
  - `rollout_sem_l2`
  - `spectral_radius_before`
  - `spectral_radius_after`

## 2. 当前可以写什么

- 可以写：当前 TF14 图包已经给出 Koopman 预测误差、rollout 误差随预测步长增长的趋势，以及稳定投影前后的谱半径信息。
- 可以写：稳定投影的作用是限制 lifted dynamics 的谱半径外逸风险，使 MPC 使用的预测器更适合长时域滚动预测。
- 可以把 E1 图作为方法机制证据或补充材料，用于解释为什么 `use_stable_projected_A` 和 bilinear lifted structure 有必要。

## 3. 当前不能写什么

- 不能写：E1 已完成 fresh 多训练 seed。
- 不能写：当前 Koopman 网络在统计意义上显著优于上传 baseline 的 AKE 原文网络。
- 不能写：当前 E1 能完全证明在线自适应收益，因为实时主 preset 默认关闭在线更新。
- 不能写：E1 预测精度已经达到投稿最终水平；现有数据仍应标为 cached screening / mechanism evidence。

## 4. 推到 100% 还需要的 E1 实验规格

| 项目 | 要求 |
|---|---|
| 训练 seed | 至少 5 个 fresh training seeds，推荐 10 个。 |
| 模型组 | `linear Koopman`、`bilinear Koopman`、`bilinear + stable projection`、`bilinear + learnable C`，若可行加入 AKE-M。 |
| 数据划分 | 固定训练/验证/测试划分，测试集不得参与 ridge refit。 |
| 指标 | one-step RMSE、multi-step rollout L2、per-state RMSE、spectral radius、failure/NaN count。 |
| 输出图 | 预测误差箱线图、rollout error vs horizon、spectral radius before/after、per-state error heatmap。 |
| 主文写法 | 只在 fresh seeds 完成后写“统计意义上提升”；否则写“机制验证和筛选结果”。 |

## 5. 当前稿件处理建议

- 中文稿中保留 E1 占位或机制图，但不要把它列为最终统计图。
- 在贡献表中把 Koopman 模块的最终证据状态标为 `pending fresh seeds`。
- 若下一轮时间有限，优先完成 E2 n=20，因为 E2 直接支撑四个方法贡献；E1 fresh 是预测器可信度的 P1 缺口。

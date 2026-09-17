# Koopman Predict V2 开发日志

> 任务书：`koopman_path.md`（SHA256 `08EFC410984FE426FA8B9C9124F5AAD1A48AF4764184765BAC56CE7FF127CE5A`）
> 首次授权边界：P0 → P1 → P2 → P3，随后人工停止（任务书第 12 节）
> 执行机：`DESKTOP-9IUUGEO`（RTX 5080 / Python 3.11.14 / NumPy 2.0.1 / CPU 闭式计算）
> 冻结父代：N6（`koopman_predict_auto`，run `20260901_214725_AUTO_PREDICT_AUTO_R04_R01`）

## 设计决策

- **P0 逐元素复现策略**：`evaluation_v2.py` 忠实重实现 N6 `evaluation.py` 的度量数学
  （相同操作顺序、float64），读取冻结模型（`koopman_predict_auto_models/n6`）、冻结归一化
  （`normalization_train_only.npz`）、冻结 cache（`n5/cache`）与冻结参数解析器
  （只读导入 N6 `generate_data.resolved_params` 与 `internal_force.build_planar_grasp_matrix`），
  使复算表与 N6 记录逐位一致（实测 S0 J20 绝对误差 0.0，主表逐项相对误差 0.0）。
- **隔离**：v2 全部代码位于 `revision_2026/koopman_predict_v2`，从未修改 N6 源码树。
- **P1/P2/P3**：诊断模块在共享评估引擎上构建；oracle 标签仅为上限、不部署；
  双线性诊断严格限定在预注册的 B0/B1/B2/B3 矩阵内。
- **计时字段**（`inference_*`）不参与 1e-9 科学指标回归（依赖机器状态），仅入公平账本。

## 执行期间的 L1 实现级修复（均不改变科学阈值与方法定义）

1. `dev_windows` 计数口径：应为唯一 `(trajectory_id, window_start)` 数 3820，
   初版误用含时域维的 15280 行数 → P0 门 `development_window_identity` 修复。
2. P1 置换评估/分区 CV 手工行缺 `inference_s` → `macro_summary` 容忍缺失（默认 0.0）。
3. P1 `partitioned_linear_cv` 缺 `expert_stats` 初始化 → 补齐。
4. `_principal_angles` 子空间基应取右奇异向量（47 维行空间），初版误用左奇异向量 → 修正。
5. `connector_group_explained`：冻结 split 的 family 为单工况，无法做族内配对 →
   改为按工况分组的族级非配对 bootstrap CI（结果 D7/D9/D10 均值份额 0.79 vs D0 0.49，
   CI [0.152, 0.375] 不跨 0）。
6. P2 oracle 专家拟合口径：任务书要求"共享数据、无样本删除" → 专家使用其窗口内
   **全部行**（而非仅窗口起点行）参与闭式回归；修复后 oracle 由 -89% 改善为 -9.9%。
7. P3 门语义符号：`one_step` 指标实为 improvement（正值=候选更优）；B1 一步误差
   比 S0 **好 27.9%**，初版误判为失败并错误停止 B2/B3 → 修正后 B2/B3 实际运行。
8. P3 `A(u)` 输入盒：从训练 cache 计算冻结归一化控制盒（min/max），修复对归一化
   NPZ 缺原始 `control7` 的 KeyError。

## 最终结果（run `20260902_094727_KOOPMAN_V2_KOOPMAN_V2_P0_R02_R01`）

- P0：12/12 门通过；S0 J20_common 复算 = 0.13023504180689485（绝对误差 0.0）；
  主表逐项相对误差 0.0；3820 个 development 窗口身份一致；confirm 读取 0；33 测试全过。
- P1：审计完成（PASS）。必要信号门满足 2/3：分区线性模型一步误差改善 7.11%
  （5 折同向）；D7/D9/D10 连接变量组残差解释量显著高于 D0（差 0.269，CI 不跨 0）；
  残差子空间主角度中位数 < 15°（不满足）。
- P2：oracle 上限未达门（validation macro -9.9%；D9 +11.8% 但 D7/D10 退化；
  5 个 seed 全部反向）→ 决策 `CANCEL_MULTI_EXPERT_ROUTE`（P4 不授权）。
- P3：B0 复现精确（系数相对误差 0.0）；B1 全双线性一步 +27.9% 但 20 步宏观 -7.6%、
  D5 发散、1/5 seed 同向 → REJECT；B2/B3 联合低秩 20 步严重发散（发散率 62%/18%）、
  A(u) 输入盒谱半径均 > 1（6.87 / 3.09 / 1.29）→ REJECT。
  → 双线性（事后 SVD、全双线性、联合低秩）永久保留为负结果，不进入 P8 组合。

## 停止

首次授权 P0→P1→P2→P3 已执行完毕，按任务书第 12 节人工停止；
P4（因果门控）因 P2 oracle 未过、P5（残差 lift）及其后阶段等待用户另行授权。

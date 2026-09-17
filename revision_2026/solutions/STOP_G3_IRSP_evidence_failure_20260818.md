# G3 停止报告：现有 IRSP 无法支撑连续输入域与稳定性主张

> 日期：2026-08-18  
> 停止节点：T3 / G3  
> 对应审稿意见：AE-1、R1-3、R1-5、R2-1、R2-2、R2-3、R3-4  
> 状态：**已停止继续生成原 IRSP/稳定性支撑证据**

## 1. 为什么停止

任务书规定：遇到核心支撑证据无法成立时停止，不通过继续调参维持预设结论。本轮已用 5080 上原 TF14 环境、原模型、原训练数据和原 projection 实现完成实际矩阵审计，发现现有 IRSP 的理论前提不成立。

这不是“暂时没跑够种子”，而是确定性的数学与实现问题：投影后的 `A+` 自身已经违反所声称的 induced-norm 半径，因此把 bilinear 矩阵缩放到零也不能取得连续域证书。

## 2. 可复核的实际证据

### 2.1 模型与拟合

- 解释器：`E:\anaconda\envs\pytorch_new\python.exe`；
- GPU：NVIDIA GeForce RTX 5080；
- lifted model：31D；
- `A`：31×31；
- bilinear `B`：31×62；
- 拟合样本：805824；
- lifted RMSE：0.0054932026。

### 2.2 原 sampled projection

- 输入采样点：96；
- `r_u=0.998`；
- `r_A=0.992`；
- `gamma_sampled=0.2465812846`；
- sampled maximum spectral radius：0.99799999995；
- sampled P95 spectral radius：0.99289138895；
- 实际配置：`input_aware_enforce_norm_bound=False`。

这些数字说明原 sampled audit 按自身定义运行成功，但它只覆盖有限采样点和谱半径。

### 2.3 连续域审计

- 投影后 `rho(A+)=0.9920000207`；
- 投影后 `||A+||₂=1.0980026543`；
- 连续输入盒的 bilinear norm budget：0.2281104991；
- 三角不等式上界：1.3261131534；
- 重新计算 `gamma_norm=0`；
- `||A+||₂>r_u`，所以 `gamma=0` 后仍不满足 `||A_eff||₂≤r_u`。

结论：现有代码和 Eq. (22) **不能**给出论文声称的 continuous control-input envelope certificate。

### 2.4 独立反例

已用非正规稳定矩阵复现：`rho(A+)=0.9`，但 `||A+||₂=10.0719854`。原公式返回 `gamma=0` 后范数仍远大于 `r_u=0.998`。这证明 spectral-radius projection 与 induced-norm contraction 不能互相替代。

## 3. 受影响的论文主张

在修复并重新验证前，下列主张均不可保留：

1. IRSP certifies all admissible continuous inputs；
2. IRSP provides contraction over the controller input envelope；
3. IRSP 支撑 recursive feasibility；
4. IRSP 支撑 Theorem 1 的 practical ISS/UUB；
5. “certifiable/stability-audited bilinear predictor”；
6. 用 sampled spectral radius below one 推出闭环稳定性。

原论文可以保留的最强陈述仅为：

> A finite sampled spectral-radius regularization was applied to the bilinear lifted matrices. It is a numerical audit and does not certify the continuous input domain or closed-loop stability.

## 4. 解决方案路线

### 方案 A：改为共同二次 Lyapunov/LMI 证书（理论最强，成本最高）

#### 步骤

1. 将输入盒表示为 polytope，并构造所有顶点的 `A_eff(u_v)`。
2. 固定候选投影模型后，求共同 `P≻0`：

   `A_eff(u_v)^T P A_eff(u_v) - r_u²P ⪯ 0`。

3. 若需同时优化模型与 `P`，采用交替优化：固定模型求 P，固定 P 对 gamma/投影量求解。
4. 单独处理 constant observable；不能简单把其 eigenvalue 1 压到 0.992 后仍称原 lifted dynamics 不变。
5. 认证失败时必须返回 infeasible，并执行 freeze/rollback/fallback。
6. 在全部 online update 后重新认证。

#### 通过标准

- 输入盒全部顶点满足共同二次条件；
- 随机输入仅用于反例搜索，不作为证明；
- gamma 不长期接近 0；
- 与 noIRSP 相比，至少在 constraint violation、MPC infeasibility 或闭环鲁棒性上达到 E3 证据。

#### 风险

- 31D 模型和 bilinear 投影可能高度保守；
- constant observable 可能使严格 contraction 形式本身不合适；
- 在线实时认证计算成本可能过高。

### 方案 B：对误差子空间建立增量/误差动力学证书（更符合 constant observable）

#### 思路

不对包含常数观测量的整个 lifted state 强求 `||A_eff||<1`，而是对 tracking-error/incremental lifted state 建模：

`delta z_{k+1}=A_delta(u) delta z_k + w_k`。

#### 步骤

1. 将 constant observable 和 reference-following invariant directions 从待收缩子空间中分离。
2. 在误差子空间拟合或推导 `A_delta(u)`。
3. 对 `A_delta(u)` 做共同 P/LMI 认证。
4. 将 residual、reference change、delay error 显式作为 disturbance。
5. 重新构建 terminal set、constraint tightening 和 ISS/UUB 推导。

#### 优点

- 避免对常数观测量强制严格收缩的结构矛盾；
- 稳定性对象与 tracking error 更一致。

#### 风险

- 相当于重写 IRSP 和 Theorem 1；
- 需要重新训练/验证误差模型，120 天时间风险较高。

### 方案 C：删除 IRSP 理论贡献，保留为数值正则化（推荐的低风险路线）

#### 修改

1. 删除 IRSP 作为核心贡献；
2. 删除 continuous-domain certificate、recursive-feasibility support 和 stability-audited 表述；
3. 将现有 sampled projection 改称 `sampled spectral-radius regularization`；
4. Theorem 1 删除或降级为 empirical decrease/fallback monitor；
5. 论文主线收缩为 communication-quality-aware constrained Koopman MPC；
6. 用强基线、多种子通信压力实验支撑主要贡献。

#### 适用条件

如果 A/B 路线的预实验出现以下任一情况，应直接采用 C：

- gamma 中位数接近 0；
- 预测误差明显恶化；
- MPC 可行率或闭环性能无改善；
- 在线 LMI 不能满足实时性；
- 无法给出非循环的 recursive-feasibility/ISS 推导。

## 5. 推荐决策

建议优先采用 **方案 C** 完成可发表性重构，同时把方案 B 作为后续理论论文方向。理由：

1. 审稿人已经指出 noIRSP 的 lateral RMSE 更低；
2. 当前实际矩阵表明 Euclidean continuous norm certificate 不可行；
3. constant observable 使“整个 lifted matrix 严格收缩”在结构上值得重新审视；
4. 继续强保 IRSP 会同时拖累 novelty、stability、ablation 和可信度四条审稿意见；
5. communication awareness 和 PPC 才是现有证据中相对明确的有效机制。

如果仍希望保留 IRSP，必须先授权进入方案 A/B 的方法重构，不应直接启动 n=20/n=50 大规模实验。

## 6. 同时发现的 delay 预警

在独立 seed 3091 的配对 smoke test 中：

| 指标 | full | noDelay |
|---|---:|---:|
| Lateral RMSE | 0.0461973 | 0.0465514 |
| Longitudinal RMSE | 0.4673333 | 0.4670500 |
| Max connection utilization | 0.0530167 | 0.0540688 |
| Force peak | 1476.6865 | 1429.4239 |

full 仅在 lateral RMSE 和 connection utilization 上略好，同时 longitudinal RMSE 与 force peak 更差。该单种子结果不是最终结论，但延续了原审稿意见中的“几乎无差异”信号。若继续项目，应在新的高 delay/burst-loss 场景做预注册 sweep；仍无稳定效应时，从标题删除 `Delay-Compensated`。

## 7. 文件与复核路径

- `revision_2026/03_irsp/test_eq22_counterexample.py`
- `revision_2026/03_irsp/eq22_counterexample_result.json`
- `revision_2026/03_irsp/extract_actual_irsp_model.py`
- `revision_2026/03_irsp/actual_irsp_matrices.npz`
- `revision_2026/03_irsp/actual_irsp_audit.json`
- `revision_2026/04_theory/irsp_and_theorem_initial_audit.md`
- `revision_2026/06_experiments/smoke_original/`
- `revision_2026/work_log.md`


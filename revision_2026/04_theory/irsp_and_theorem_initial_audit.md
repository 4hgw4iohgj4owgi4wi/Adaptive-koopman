# IRSP 与 Theorem 1 初始审计

## 审计结论

现有代码和实验**不能**支撑连续控制输入域 contraction、recursive feasibility 或闭环 stability guarantee。当前可成立的最强事实是：代码在有限 `u_samples` 上将 `A_eff(u)` 的谱半径压到指定半径以内，并把连续域 induced-norm 数值作为可选审计量；默认主实现并未强制该 norm bound。

因此在 T3 修正、T4 重建和 G3/G4 通过前，应停止以下表述：

- “IRSP certifies the actual continuous control-input domain”；
- “IRSP guarantees contraction for all admissible inputs”；
- “IRSP supports recursive feasibility”；
- “certificate-verified closed-loop stability”。

## 1. 代码事实

### 1.1 主实现

文件：`control_files/tf11_a1/core_utils.py`

- `input_aware_project_bilinear_matrices(..., enforce_norm_bound=False)` 默认不强制连续域 norm bound。
- `A` 通过 eigenvalue clipping 做 spectral projection；这不能控制非正规矩阵的 induced norm 或 transient amplification。
- `gamma_sampled` 只通过有限 `u_samples` 上的最大谱半径二分搜索得到。
- `gamma_norm` 使用三角不等式上界计算，但当 `||A+||₂>radius` 时被截断为 0。
- 最终 `gamma` 仅在显式设置 `enforce_norm_bound=True` 时才使用 `min(gamma_sampled,gamma_norm)`。

### 1.2 调用事实

文件：`control_files/tf11_a1/mpc_helpers.py`

- 初始模型调用默认 `method_cfg.get("input_aware_enforce_norm_bound", False)`。
- 在线更新调用默认 `adapt_cfg.get("input_aware_enforce_norm_bound", False)`。
- fallback helper 完全没有实现 continuous norm certificate，只保留 sampled spectral-radius projection。

### 1.3 Eq. (22) 的逻辑错误

当 `||A+||₂>r_u` 时，原式给出 `gamma_c=0`。此时

`A_eff+(u)=A+ + 0·Σu_l N_l=A+`，

所以仍有 `||A_eff+(u)||₂=||A+||₂>r_u`。`gamma_c=0` 不是可行证书，只能表示“仅缩放 bilinear 项无法使问题可行”。算法必须重新投影 `A+`、改变度量 `P` 或返回 infeasible。

## 2. Theorem 1 的依赖问题

原 theorem 假设：

1. passing step 已满足指定下降不等式；
2. failing step 满足有界增长；
3. failing-step density 满足 average contraction；
4. IRSP 满足 sampled contraction，必要时才启用 norm certificate。

这些条件中的前三项正是闭环控制器应推出或先验保证的性质。论文随后用同一控制器生成的 pass ratio 和日志检查这些条件，形成“将结论性质作为假设，再用结果日志审计假设”的循环。尤其 nominal-clean pass ratio 0.360、single-fault 0.799 与负 minimum margins，不能验证 average contraction。

## 3. 当前停止点

本轮尚未尝试用现有结果继续支撑 IRSP/稳定性贡献，因为证据前提已经不成立。下一步只允许：

1. 运行 Eq. (22) 反例单元测试；
2. 设计连续输入域可行投影及 infeasible 处理；
3. 从 terminal set/cost、constraint tightening 和 fallback invariant set 重建 recursive feasibility；
4. 若无法完成，则按 G3/G4 删除相应核心贡献和稳定性主张。

## 4. 建议解决路线

### 路线 A：共同二次度量/LMI

求 `P≻0` 和投影后的 `A+, N_l+`，使输入盒顶点或 polytopic embedding 上满足

`A_eff(u)^T P A_eff(u) - r_u^2 P ⪯ 0`。

对 affine-in-input 的矩阵族，可先验证输入盒顶点的共同二次条件，并清楚说明充分性与保守性。若双线性决策不可直接求解，固定 `P`/模型后对 `gamma` 二分。

### 路线 B：加权 induced norm

先求一个使 `||A+||_P<r_A<r_u` 的加权范数，再通过

`||A+||_P + gamma Σu_l,max ||N_l||_P ≤ r_u`

求 gamma。第一项不满足时必须返回 infeasible，不能令 gamma=0 冒充证书。

### 路线 C：理论降级

若 A/B 导致 bilinear 项长期接近零或无法实时计算：

- 删除 IRSP 核心贡献；
- 保留 sampled spectral-radius projection 作为数值正则化；
- 删除 continuous-envelope、recursive-feasibility 和 stability 支撑表述；
- 将论文主线收缩为 communication-quality-aware constrained Koopman MPC。


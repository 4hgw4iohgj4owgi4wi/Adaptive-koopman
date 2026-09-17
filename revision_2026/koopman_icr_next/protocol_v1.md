# Koopman 后续执行指导：先闭合转向执行器状态，再决定是否修改共同 ICR

> 文档状态：`PLAN / NOT_RUN`  
> 编写时间：`2026-08-31`  
> 远端主机：`DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 冻结父任务书：`D:\PDxc\Review\koopman_run.md`  
> 父任务书 SHA256：`162077332C44C7430F828B5D8BCB0F248CDD2218653BE39236033AD17575C6E4`  
> 冻结 ICR 任务书：`D:\PDxc\Review\icr_fix.md`  
> ICR 任务书 SHA256：`F64590B02CF3C62B80C6A83EBBC37100AD3A2DC9427DE563E7EF4533108D1564`  
> 最新有效状态：`I0 PASS；I1 BLOCKED；I2–I5/C1/C2/F4/K0–K7 NOT_RUN`  
> 本文性质：针对最新失败证据的新版本执行指导；不得覆盖上述两份已登记 SHA 的任务书。  
> 第一次未来执行停止点：只允许在单独授权后完成 `N0→N1→N2`；`N2` 证据交付后必须人工停止，不能自动进入 F4、训练或 C1/C2。

## 0. 先给结论

下一步不应先改轮胎、连接器、D2 阶跃或执行器参数，也不应立即开发新的共同 ICR 分配器。最短且证据最清楚的路线是：

1. 修正 I1 的判据语义：A0/A1 是反事实归因模式，不是可部署模式；其轮胎、轮角速率等物理门只报告，不阻断归因。A2/A3 仍执行全部物理硬门。
2. 完成 G0/G1/G2 与 A0/A1/A2/A3 归因，确认独立航向反馈、逐车裁剪、执行器滞后和速率限制各自造成什么影响。
3. 默认保留已经通过父实验的 A3 动态执行器，把实际轮角作为动力学状态，而不是把请求轮角当成已经实现的轮角。
4. 在同一 A3 数据上只做 S0/S1/S2 三组输入接口消融，先回答“20 步预测差是否主要来自转向执行器状态缺失”。
5. 只有当完整因果接口仍不能解释切换误差，且误差与请求层独立航向反馈/共同 ICR 不一致显著相关时，才另行授权 C1/C2。

这一路线能避免两个逻辑错误：

- 把 A0 的非物理瞬时跳变误判为 A3 植物失败；
- 把所有基线都共享的物理/接口修正包装成新 Koopman 方法的相对创新。

## 1. 最新证据、推断和未知项

### 1.1 已确认事实

以下数字可从 `D:\PDxc\Review\icr_failure` 中的 JSON、日志和原始证据定位：

| 项目 | 最新结果 | 证据含义 |
|---|---:|---|
| I0 | PASS，运行 `20260831_004011_I0_R01` | 父源码/原始数据身份、线程一致性和测试通过 |
| I1 | BLOCKED，运行 `20260831_004036_I1_R01` | 在第一条 A0 pilot 后按旧判据停止 |
| A0 轮胎原始利用率峰值 | `1.21581526024` | 超过冻结部署门 `0.90` |
| 峰值时刻/车辆 | `13.44 s` / 第 1 车 | 位于 `STEP_REVERSE` 反向阶跃 |
| A0 实际轮角速率峰值 | `164.357482828 rad/s` | A0 瞬时令 `actual=request` 的反事实跳变，不是 A3 的 `1.2 rad/s` 限速 |
| A0 实际 ICR 残差峰值 | `1.076553380 m/s` | 请求层不一致被瞬时传入实际轮角 |
| A0 连接器合力峰值 | `2312.211 N` | 仍低于当前数值极限，但不能据此称材料安全 |
| A0 作用反作用残差 | `0 N` | 平面力传递数值闭合 |
| A0 内力零空间相对残差 | `1.33e-15` | 内力分解数值闭合 |
| G0 请求 ICR 峰值 | `5.55e-17 m/s` | 共同 ICR 几何前馈本身达到机器零量级 |
| 父 F3 原始轨迹 | 24 条，哈希不一致 0 | 可作为只读归因父证据 |

此前对远端父 F3 24 条轨迹归因 CSV 的独立复算记录显示：

- G0 只有共同 ICR 几何前馈，残差近似为零；
- G1 在 G0 上叠加四车独立航向反馈后，请求 ICR 峰值中位数约为 `1.99858 m/s`；
- G2 再做逐车 `±15 deg` 裁剪后，峰值中位数降至约 `1.03442 m/s`；
- 因此，当前请求层不一致的主要来源是四车独立航向反馈；逐车裁剪在现有 D2 中反而抑制了峰值，而不是峰值的首要来源；
- A0 的轮胎超门只出现在三个命令切换采样附近，符合“瞬时轮角跳变触发尖峰”的解释。

上述 G1/G2 中位数目前没有随本地失败副本一起保存完整逐轨迹 CSV，本地只有通过摘要和此前复算记录；因此它们可用于制定下一步，但 N2 必须重新落盘完整 CSV 并独立复算后，才能作为论文数字引用。

### 1.2 有证据支持的推断

1. A0 的失败说明“无执行器动态的瞬时轮角”在冻结阶跃下不具备物理可行性，不说明 A3 植物失败。
2. 旧 I1 同时要求 A0 为无约束理想下界，又要求任何模式都通过部署轮胎门，这两个要求在当前工况中互相冲突。
3. 当前采样间隔为 `0.02 s`，20 步预测只覆盖 `0.4 s`；父 A3 的切换恢复约 `0.68–0.70 s`。因此从阶跃附近开始的 20 步区间全部处在执行器瞬态内。
4. 若模型只看到请求轮角而不知道当前实际轮角，同一请求和相近车辆状态可能对应不同的下一步响应；对学习模型而言，这会形成非 Markov 或隐状态问题。
5. A3 对轮胎峰值有明显保护作用，不能为了让数据更平滑而删掉其滞后、速率或角度限制。

### 1.3 尚未证明的事项

- 尚未在最新植物上完成任何 Koopman 训练，不能声称 S1/S2 会改善 20 步预测。
- 尚未证明实际共同 ICR 不一致会显著恶化货物、连接器或闭环控制。
- 尚未证明 C1/C2 比保留 A3 更好，也未获得其执行授权。
- 当前执行器 `tau_delta=0.12 s`、`rate_max=1.2 rad/s`、`angle_max=15 deg` 是仿真合同，不是实车标定。
- 当前刚体货物和连接器模型只能给出四点力、合力矩及阵列拉伸内力代理，不能直接证明材料不会撕裂或疲劳失效。

## 2. 研究目标、非目标和论文边界

### 2.1 本轮要回答的三个问题

**Q1：归因协议是否正确？**  
能否在不改变 D2、轮胎或执行器的前提下，完整比较 G0/G1/G2 和 A0/A1/A2/A3，而不把非物理反事实模式误当部署方案？

**Q2：Koopman 是否缺少执行器状态？**  
在同一 A3 植物、同一完整轨迹划分和同一训练预算下，加入当前实际轮角及因果执行器侧车是否专门改善切换窗的 10/20 步误差？

**Q3：是否真的需要改共同 ICR 分配器？**  
只有当完整执行器接口仍不足、预测残差与请求层 ICR/独立航向反馈显著相关，或论文必须主张“实际轮角近似共同 ICR”时，才进入候选分配器。

### 2.2 本轮不做

- 不改 D2 的正反阶跃幅值、持续时间和 100 m 合同；
- 不放宽 `raw tire utilization<=0.90`；
- 不调摩擦系数、轮胎限幅、连接器参数、载荷转移或积分器来迎合结果；
- 不把未来真实轮角、未来 mask 或未来事件标签送入模型；
- 不把 A0/A1 描述为可部署控制模式；
- 不提前进入通信干扰、DoS、网络韧性或 MPC 闭环；
- 不把共享的执行器状态接口计入某一个 Koopman 方法的独占创新收益。

### 2.3 允许的论文表述

在 N6 以前，只允许写：

> 在冻结仿真域内，无约束瞬时轮角反事实会在转向切换处产生非物理轮胎尖峰；有限带宽和速率限制是植物动力学的一部分，后续预测器必须使用因果的实际执行器状态。

只有 N6 的输入消融通过后，才允许写：

> 在相同植物、数据与模型骨干下，执行器增强的因果状态表示在操纵切换窗改善了多步预测；该收益是状态闭合收益，不等于最终 Koopman 结构创新已成立。

只有后续 K7 盲确认通过，才允许声明最终 Koopman 方法在定义仿真域内具有多步预测优势。只有 C0 clean 闭环通过，才允许写预测收益转化为控制收益。

## 3. 数学定义和接口原则

### 3.1 三层转向必须分开

每个采样时刻必须分别保存并命名：

1. `delta_geom4_k`：共同 ICR 几何前馈 G0；
2. `delta_req4_k`：加入独立反馈和裁剪后的真实请求 G2；
3. `delta_act4_k`：执行器实际输出 A3。

不得再用目标几何残差替代请求或实际轮角残差。三层 ICR 统一用同一个残差函数：

\[
e_{ICR}(\delta,x)=
\left\|\Pi_\perp(\delta,x)\,v_{wheel}(\delta,x)\right\|,
\]

其中具体几何映射必须调用项目已经测试的 `kinematic_targets()`/现有 ICR 审计函数，不另写未经验证的简化阿克曼公式。

### 3.2 A3 执行器离散模型

令 `delta_req` 在区间 `[t_k,t_{k+1})` 内生效：

\[
a=\exp\!\left(-\frac{\Delta t}{\tau_\delta}\right),\qquad
\bar\delta_{i,k+1}=a\delta^{act}_{i,k}+(1-a)\delta^{req}_{i,k}.
\]

先施加速率限制：

\[
\delta^r_{i,k+1}=\delta^{act}_{i,k}+
\operatorname{clip}\!\left(
\bar\delta_{i,k+1}-\delta^{act}_{i,k},
-\dot\delta_{max}\Delta t,
\dot\delta_{max}\Delta t
\right),
\]

再施加角度限制：

\[
\delta^{act}_{i,k+1}=
\operatorname{clip}(\delta^r_{i,k+1},-\delta_{max},\delta_{max}).
\]

20 步滚动预测时只能从当前 `delta_act4_k` 出发，使用已知/规划的未来请求序列逐步调用同一个冻结映射 `Phi_delta`：

\[
\hat\delta^{act}_{k+h+1}
=\Phi_\delta(\hat\delta^{act}_{k+h},\delta^{req}_{k+h}),
\quad h=0,\ldots,19.
\]

禁止在滚动中读取保存数据里的未来 `delta_act`。

### 3.3 三组最小输入消融

令 `chi_k in R^47` 为现有相对物理状态，`u_k` 为虚拟纵向/转向控制及真实请求量。若源码审计发现维数或字段含义不同，必须以 schema 清单为准更新符号，不得仅改文档数字。

**S0：请求量接口。**

\[
s_k^{S0}=\chi_k,qquad
v_k^{S0}=[u_k,\delta^{req}_{1:4,k}].
\]

它代表模型不知道执行器当前实际位置，只看到命令。

**S1：实际轮角状态闭合。**

\[
s_k^{S1}=[\chi_k,\delta^{act}_{1:4,k}],qquad
v_k^{S1}=v_k^{S0}.
\]

S1 允许模型联合学习实际轮角的一步变化，用于检验“缺失状态”本身是否是主要矛盾。

**S2：冻结解析执行器侧车。**

\[
s_k^{S2}=[\chi_k,\delta^{act}_{1:4,k}],
\]

但 `delta_act` 不由任意神经网络自由外推，而由冻结 `Phi_delta` 递推。模型只预测 `chi`，并使用以下因果上下文：

\[
c_k^\delta=
[\delta^{req}_k-\delta^{act}_k,
(\delta^{act}_k-\delta^{act}_{k-1})/\Delta t,
\delta^{req}_k-\delta^{req}_{k-1},
m_k^{rate},m_k^{angle}].
\]

S2 的目的不是把所有相关量重复拼接，而是隔离“已知执行器方程+饱和工况上下文”的增量作用。现有 `actual_steering4_k`、`hybrid_state51_k`、`actuator_error4_k`、`actuator_sidecar20_k` 和 `actuator_gate8_k` 必须先做字段去重；同一个物理量不能以原始字段和拼接侧车同时送入。

### 3.4 两种模型骨干只用于验证普适性

第一轮只用两种骨干，不启动完整模型动物园：

**M0：固定线性相对 Koopman。**

\[
z_{k+1}=Az_k+Bv_k,qquad z_k=\psi_{fixed}(s_k).
\]

它用于最干净地判断输入状态是否补足信息。

**M1：低秩双线性 Koopman。**

\[
z_{k+1}=Az_k+Bv_k+
\sum_{j=1}^{n_u}v_{k,j}U_jV_j^\top z_k.
\]

它用于检查执行器接口收益是否只在输入—状态耦合结构中出现。rank 只能从原任务书预注册集合 `{1,2,4}` 由 validation 选择，不能看 development/confirm。

若 S1/S2 在 M0 和 M1 上都改善，才可称输入接口具有跨骨干一致性；若只在 M1 改善，应表述为“该接口与双线性交互项互补”，不能称普适。

### 3.5 切换窗必须是因果定义

以虚拟命令而不是抖动的请求反馈检测切换：

\[
q_k=\mathbf 1\left[
\|\Delta\delta_k^{virtual}\|_\infty\ge\epsilon_\delta
\ \lor\ |
\Delta a_k^{cmd}|\ge\epsilon_a
\right].
\]

建议在 N0 冻结 `epsilon_delta=0.5 deg`、`epsilon_a=0.05 m/s^2`，并用 D2 边界单元测试验证。根据父 A3 的 `0.68–0.70 s` 恢复证据，将切换恢复窗预注册为最近一次切换后的 `0–0.8 s`，即 40 个外步。模型 gate 只能使用“距最近过去切换的时间”；评价可另外标记预测区间是否跨越未来切换，但该标签不能入模。

## 4. 新版本目录和不可变边界

后续若获得执行授权，必须新建：

```text
revision_2026\koopman_icr_next
revision_2026\koopman_icr_next_results
```

禁止覆盖：

```text
revision_2026\koopman_focus
revision_2026\koopman_focus_results
revision_2026\koopman_icr_fix
revision_2026\koopman_icr_results
```

新协议至少固定：

- 两份父任务书 SHA；
- 父 F3 manifest SHA `C1D430E4718832A27253C2D7C8290678A186EAD570C3948E6D5AC2463C25533B`；
- 当前 ICR 源 manifest SHA 和 I0 完整证据路径；
- D2/载荷/轮胎/连接器/积分器参数身份；
- A0–A3 模式语义；
- 诊断门与部署门矩阵；
- seed、split、线程、时间预算和停止点；
- S0/S1/S2 字段清单、单位、shape、时间端点和重复字段禁止表；
- 训练/评价 horizon、模型骨干、损失权重和 PASS 阈值。

## 5. 关键修正：把诊断状态和部署状态分开

### 5.1 模式身份不变

| 模式 | 一阶滞后 | 速率限制 | 角度限制 | 身份 |
|---|---:|---:|---:|---|
| A0 | 否 | 否 | 否 | 非物理反事实：`actual=request` |
| A1 | 是 | 否 | 否 | 非物理反事实：只看带宽 |
| A2 | 是 | 是 | 否 | 近物理增量模式；请求已做 15 deg 裁剪 |
| A3 | 是 | 是 | 是 | 当前部署基线 |

### 5.2 两类状态字段

每条轨迹输出两个独立状态：

```text
diagnostic_integrity = PASS | FAIL
deployment_feasibility = PASS | FAIL | NOT_APPLICABLE
```

阶段状态不能再由一个 `passed=all(gates)` 混合计算。

### 5.3 门槛矩阵

| 门 | A0/A1 | A2 | A3 | 说明 |
|---|---|---|---|---|
| 数值有限、时间网格、100 m 完成 | HARD | HARD | HARD | 归因结果必须可读 |
| 重放哈希 | HARD | HARD | HARD | 不一致即停止 |
| G0 几何 ICR、场景合同 | HARD | HARD | HARD | 不得改外部命令 |
| 支承/力矩守恒、作用反作用、内力零空间 | HARD | HARD | HARD | 模型完整性 |
| 父 A3 公共字段逐点身份 | N/A | N/A | HARD | 最大差 `<=1e-12` 或给出确定浮点来源 |
| 轮角速率 `<=1.2 rad/s` | REPORT | HARD | HARD | A0/A1 本来就关闭速率限制 |
| 轮角角度 `<=15 deg` | REPORT | REPORT+AUDIT | HARD | A2 无角度限制，但 G2 请求应使其通常不激活 |
| 轮胎原始利用率 `<=0.90` | REPORT | HARD | HARD | A0/A1 超门标为反事实不可部署，不阻断归因 |
| 连接器数值极限/负支承 | REPORT+DOMAIN | HARD | HARD | A0/A1 若越域，只使用越域前数据；NaN/守恒失败仍 HARD |
| 跟踪、ICR、四点力、阵列拉伸内力 | REPORT | REPORT | REPORT | 用于增量归因和权衡 |

其中 `REPORT+DOMAIN` 表示必须记录首个越界时刻并标记该反事实已离开物理工作域，但不能据此跳过 A2/A3。只有数值完整性、守恒、重放或父身份失败才阻断整个 N2。

### 5.4 调度顺序

旧脚本把 A0 排在第一并在首个物理门失败时终止。新顺序必须是：

1. A3/V1-left pilot：先验证部署基线和父身份；
2. A0/V1-left pilot：验证诊断模式能保存物理超门而不阻断；
3. A3、A2、A1、A0 的剩余成员；
4. 全部完成后统一生成增量归因表。

分析时仍按 A0→A1→A2→A3 计算：

\[
\Delta_{lag}=M(A1)-M(A0),\quad
\Delta_{rate}=M(A2)-M(A1),\quad
\Delta_{angle}=M(A3)-M(A2).
\]

运行顺序和数学差分顺序不得混淆。

## 6. 顺序任务树

### N0 — 新协议冻结与预检

**授权：** 编写本文不等于授权 N0。未来必须由用户明确说“执行 N0–N2”或同等含义。  
**修改：** 只新建版本、复制必要源码、写协议和测试，不改物理方程。  
**预检：**

1. 核对主机名、Python 环境、GPU、磁盘和未知 Python/MATLAB 进程；
2. 复算两份父任务书、父 F3 manifest、24 条原始 NPZ 的 SHA；
3. 核对当前 `koopman_icr_fix` 源码身份和最新失败证据；
4. 新目录若已存在，停止并人工判断，禁止覆盖；
5. 冻结 `OMP_NUM_THREADS/MKL_NUM_THREADS`，运行中不得改变；
6. 运行源测试并保存完整 stdout/stderr。

**PASS：** 身份一致、未知进程为 0、磁盘 `>=40 GiB`、新 manifest 完整、测试全过。  
**FAIL：** 任一身份漂移、原始数据缺失、未知进程无法解释或测试失败，N1/N2 `NOT_RUN`。

### N1 — 判据语义修正与人工故障注入测试

**目标：** 只修审计/调度，不改变 A0–A3 数值结果。  
**必须修改：**

- 将 `audit_icr_fix.py` 中单一 `passed` 拆成 `diagnostic_integrity` 和 `deployment_feasibility`；
- A0/A1 的轮胎/速率/角度门改为 report-only；
- A2/A3 的部署门保持原阈值；
- runner 不得因 A0/A1 物理不可部署而跳过后续模式；
- stage status 增加 `PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD`；
- JSON writer 对 `numpy.bool_`、`numpy.integer`、`numpy.floating` 和 ndarray 做显式安全转换，同时保持 `allow_nan=False`；
- `_require_*()` 在导入前固定隔离 `src`，避免再次出现导入顺序问题。

**必须测试：**

1. 人工构造 A0 `tire=1.2`：诊断完整性 PASS、部署状态 NOT_APPLICABLE、阶段继续；
2. 人工构造 A3 `tire=1.2`：部署 FAIL、阶段立即停止；
3. 人工构造任一模式 NaN、重放不一致或作用反作用失败：诊断完整性 FAIL、阶段停止；
4. A3 公共字段相对父实现最大差 `<=1e-12`；
5. numpy 布尔值写 JSON 成功，JSON 中仍为真正布尔类型；
6. 非法模式、重复 seed、错误时间端点和未来字段角色被拒绝。

**PASS：** 单元测试和人工故障注入全部通过，A3 数值身份不变。  
**FAIL：** 如果必须改变物理方程才能让测试过，立即停止；这超出 N1 授权。

### N2 — 完整请求层与执行器归因

**前置：** N0/N1 PASS。  
**范围：** 仍只使用 D2、L1、seed `910021`，不新增工况、不训练模型。  
**实验矩阵：**

- direction：left/right；
- plant/law：V1-ES/V1、R3-ES/R3；
- actuator mode：A0/A1/A2/A3；
- 合计 16 条保存轨迹，每条一次确定性重放，共 32 次仿真；
- 离线 G0/G1/G2 继续复算父 F3 24 条轨迹，原父 NPZ 只读。

**硬门：**

- A3 所有部署门通过并逐点复现父 F3；
- A2 所有预注册部署门通过；
- 所有模式诊断完整性、重放、场景、守恒通过；
- G0 峰值 `<=1e-8 m/s`；
- 16 条预期身份完整，不得因为 A0/A1 越域删除轨迹；
- 输出每个物理越域的首时刻、车辆、相位和越域前有效区间。

**必须输出：**

- `request_attribution.csv/json`；
- `actuator_attribution.csv/json`；
- `counterfactual_domain_events.csv`；
- 16 条原始 NPZ、16 条重放哈希和 manifest；
- A0–A3 的 ICR、轮角、轮胎、四点 Fx/Fy、支承载荷、单车/系统/货物横摆；
- 前后/左右阵列拉伸内力及四点力方向；禁止再使用含义不清的 `opening`；
- 配对增量表和最坏轨迹图；
- 独立复算脚本及其 SHA。

**状态规则：**

- A3 或 A2 任一部署硬门失败：`BLOCKED_PHYSICAL_BASELINE`，后续全部停止；
- A0/A1 只有物理超门而完整性通过：`PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD`；
- A0/A1 出现 NaN、守恒/重放失败：`BLOCKED_DIAGNOSTIC_INTEGRITY`；
- 证据完整且 A3/A2 可部署：N2 PASS。

**人工停止：** N2 报告落盘后必须停止。N3、F4、训练和 C1/C2 全部 `NOT_RUN`，等待用户查看。

### N3 — 冻结 A3 植物与因果 Koopman 接口

**默认分支：** 若 N2 证实 A3 通过，先保留 A3，不实现 C1/C2。  
**前置：** N2 人工审查后单独授权。  
**动作：**

1. 逐字段审计现有 `build_schema_focus()`、`build_schema_icr()` 和 `build_sample_*()`；
2. 生成字段矩阵：字段名、物理含义、单位、shape、`k/k-1/k+1` 端点、state/control/context/label 角色；
3. 将 `chi47 + delta_act4` 确认为唯一 S1/S2 状态；
4. S2 只保留最小因果上下文，删除与 `actuator_sidecar20`/`actuator_gate8` 的重复拼接；
5. 未来实际轮角只作评价标签，20 步预测由 `Phi_delta` 递推；
6. 将切换、恢复、速率/角度 mask 写成可复算字段；
7. 对所有模型冻结同一个状态/控制接口工厂，模型配置只能选择 S0/S1/S2，不能各自私改数据。

**接口硬测试：**

- 修改保存数据中的未来 `delta_act[k+1:k+20]`，当前样本输入完全不变；
- S2 解析递推逐点复现 A3 `delta_act[k+1]`，误差 `<=1e-12 rad`；
- 左右镜像后轮角、mask、阵列拉伸内力字段符号/索引正确；
- 相同物理量的重复特征计数为 0；
- 归一化统计只读取 train；
- 完整轨迹 split 隔离，任意 base family 不能跨 split。

**PASS：** 接口审计和泄漏测试全部通过。  
**FAIL：** 先修 schema/端点，禁止用更大网络掩盖输入错误。

### N4 — F4：D0–D11 完整物理 pilot

**前置：** N3 PASS并单独授权。  
**植物：** A3；V1-ES/R3-ES、L1 和冻结参数保持原任务书。  
**规模：** 沿用父任务书约 126 条保存轨迹并逐条重放，约 252 次仿真；先做 6 条 smoke 外推时间和磁盘，但 smoke 不能替代完整 F4。

| 展开 | 保存轨迹数 | 说明 |
|---|---:|---|
| 非方向 D0/D1/D7 | 18 | `3工况×3族×2植物` |
| 左右 D2/D3/D4/D5/D6/D8/D10/D11 | 96 | `8×3族×2方向×2植物` |
| D9 对角成员 | 12 | `1×3族×2成员×2植物` |
| 合计 | 126 | 统计单位仍是 base family，不是镜像或双植物 |

**除原 F4 硬门外新增：**

- 每类操纵工况都保存 `delta_req4/delta_act4/tracking/rate/angle mask`；
- 稳态、操纵、切换后 0–0.8 s、连接事件都有非零 20 步窗；
- 切换窗至少来自 D2、D4、D6、D10 中三个自然工况；
- 对每个工况报告 S0/S1/S2 可构造率，必须为 100%；
- 生成执行器状态范围、饱和事件和请求—实际差的覆盖表。

**失败：** 任何工况物理门失败，保存首个失败轨迹并停止。允许新协议下修物理或缩小论文工作域，但禁止删失败轨迹后继续声称 D0–D11 全覆盖。

### N5 — K0：正式数据与覆盖

**前置：** N4 PASS并单独授权。  
**生成：** train/validation/development；confirm 不生成。  
**base family 规模：**

| split | 每工况 base family | 12 工况合计 | 用途 |
|---|---:|---:|---|
| train | 8 | 96 | 拟合、归一化、学习曲线 |
| validation | 4 | 48 | 早停、rank 和模块门 |
| development | 4 | 48 | 组合冻结前封存 |
| confirm | 8 | 96 | N8/K6 冻结后才生成 |

上表是统计独立的 base family 数，不是最终 NPZ 数；方向、成员和双植物展开后的实际轨迹数必须由 `--dry-run` 清单计算，并据此重新冻结时间/磁盘预算。

**新增覆盖门：**

- train 中切换恢复窗至少 2000 个不重叠 20 步窗；
- validation/development 各至少 400 个；
- 至少 3 个自然工况和至少 4 个独立 base family 对切换窗有贡献；
- 左右 base family 数差不超过 20%；
- rate/angle mask 若全为零，不得把 mask 作为所谓创新特征；应保留数值字段但取消相关效果主张；
- `delta_req-delta_act` 的非零样本与 D2/F4 父证据一致，否则检查时间端点。

### N6 — S0/S1/S2 最小 Koopman 输入消融

**前置：** N5 PASS；development/confirm 仍封存。  
**模型顺序：** 先 M0 固定线性，再 M1 低秩双线性。M0 没跑完前不启动 M1。  
**公平性：**

- 同一轨迹、同一窗、同一 train-only 归一化；
- 同一损失、ridge 搜索、rollout horizon、batch 和墙钟/epoch 预算；
- S0/S1/S2 只改变执行器信息接口；
- M1 使用五个初始化 seed，至少四个同向；
- 模型选择只读 validation；development/confirm 不得打开。

**必须报告：**

1. `h=1/5/10/20` 的整体、分工况和最坏 base-family 指标；
2. 稳态、操纵、切换后 0–0.8 s、连接事件四类窗口；
3. `E_core/E_relative/E_force4/E_internal/E_yaw/E_actuator`；
4. 四点 Fx/Fy、货物横摆、系统横摆、单车横摆和前后/左右阵列拉伸内力；
5. 非有限/发散率、参数量、条件数、推理时间；
6. S1/S2 相对 S0 的轨迹级配对差和 base-family bootstrap 95% CI；
7. 改善量与 `|delta_req-delta_act|`、实际 ICR、rate/angle mask 的 Spearman 相关；
8. 最坏切换轨迹真实/预测时序，而不是只给平均柱状图。

沿用父任务书复合指标：

\[
J_{20}=0.25E_{core}+0.20E_{relative}+0.20E_{force4}
+0.15E_{internal}+0.10E_{yaw}+0.10E_{actuator}.
\]

权重必须在训练前冻结，不能根据结果调整。

### N6 通过判据

**S1 证明“实际轮角状态有用”需同时满足：**

- 相对 S0，切换窗 `J20` 中位数改善 `>=8%`；
- 至少一个 D2/D4/D6/D10 操纵工况改善 `>=8%`；
- 整体 macro `J20` 改善 `>=5%`，或若未到 5%，必须明确把结论限定为切换优势域；
- 任一重要工况不得恶化 `>3%`；
- 发散/非有限率不增加；
- validation 的 base-family 配对 95% CI 支持主要方向。

**S2 进入最终公共接口需在 S1 基础上满足：**

- 解析轮角 rollout 逐点合同通过；
- 相对 S1，切换窗 `J20` 再改善 `>=3%`，或推理稳定性/发散率有可量化改善；
- 复杂度与推理时间增加不超过预注册预算；
- 如果 S2 相对 S1 无增益，选择更简单的 S1，不得把多余 sidecar 留作装饰性创新。

**跨骨干解释：**

- M0、M1 都通过：接口收益具有跨两类骨干一致性；
- 只 M1 通过：收益依赖输入—状态双线性交互；
- 只 M0 通过：优先保留简单线性骨干，检查 M1 病态/过拟合；
- 两者都不通过：不能声称执行器增强改善 Koopman；检查数据覆盖、状态是否已经隐含轮角、或瞬态不是主要误差来源。

### N7 — 是否授权 C1/C2 的决策门

默认决策是保留 A3。只有同时满足下列证据链，才建议另行授权共同曲率候选：

1. S2 的因果接口和解析执行器合同均通过，但切换窗 20 步误差仍未达到 N6 门；
2. 残差在独立 base family 上与请求层 ICR 或独立航向反馈贡献显著相关，建议预注册 `|Spearman rho|>=0.4`，并报告置信区间；
3. 高请求 ICR 组的跟踪、货物横摆、轮胎或连接力至少一项有一致退化，而不只是预测器误差；
4. 论文确实需要“实际轮角保持近似共同 ICR”这一物理主张，且不能改写为更准确的“目标几何共同 ICR、实际残差有界”。

若任一条件不满足，不进入 C1/C2，直接保留 A3 并继续 Koopman 方法创新。

若未来授权 C1/C2：

- 只允许阵列层统一曲率可行化和执行器预测补偿；
- 不允许四车继续各自无协调裁剪后再称共同 ICR；
- 必须重跑候选 smoke、完整 D2 配对、F3 等价验收、F4、K0 和 N6；
- 新分配器产生的新植物数据不得与 A3 旧数据混训；
- 如果所有 Koopman 方法在新分配器上等比例改善，这属于植物/控制器简化，不是新 Koopman 的相对创新。

### N8 — 回到论文主线的模型实验

N6 冻结公共输入接口后，继续沿用父任务书而不是重开无边界探索：

1. K1：persistence、absolute linear、relative linear、fixed analytic lift 和学习量曲线；
2. K2：fixed lift、full/low-rank bilinear、IRSP 历史诊断；
3. K3：相对表示和 trainable lift 增量；
4. K4：低秩双线性在强输入—状态耦合工况的优势域；
5. K5：三专家门控，先 oracle、再因果 gate，检查塌缩和事件 PR-AUC；
6. K6：R3 物理解码和只组合单独通过的模块；
7. K7：生成盲 confirm，只运行冻结基线和一个冻结候选；
8. C0：正常通信下 D4 单移线、D5 回头弯、D6 入弯/出弯，只替换预测器；
9. 只有 clean 闭环成立后，再按“先加通信干扰观察误差/受力并证明保护必要性，再做正常单移线/回头弯对比，最后做通信扰动和 DoS”的网络实验顺序。

S0/S1/S2 是公共状态接口消融，不能替代 K3–K7 对最终 Koopman 创新模块的比较。

## 7. 对应代码修改清单

所有修改只发生在 `koopman_icr_next` 或后续明确授权的新版本中。

| 文件 | 函数/入口 | 修改内容 | 验收 |
|---|---|---|---|
| `config/protocol_icr_next.json` | — | 冻结父 SHA、模式语义、双状态门、阶段预算、S0/S1/S2 字段 | schema/非法值/重复 seed 测试 |
| `scripts/audit_icr_next.py` | `audit_trajectory()` | 拆分诊断完整性与部署可行性；保存首个越域 | A0 tire=1.2 不阻断，A3 同值阻断 |
| 同上 | `aggregate_stage()` | 按模式身份汇总，不再 `all(all_gates)` | 混合状态人工测试 |
| `scripts/run_icr_next.py` | `run_n0/run_n1/run_n2` | A3 优先 pilot；阶段前序门；人工停止 | 后续阶段拒绝、状态 JSON 正确 |
| 同上 | `_json_safe()` | 转换 numpy scalar/array；禁止 NaN | numpy bool 回归测试 |
| 同上 | `_require_n0()` | 先固定隔离路径再导入 | 冷启动进程测试 |
| `plant/steering_allocator.py` | `request_variants()` | 保持 G0/G1/G2 数值身份，只补诊断输出 | G2 对父请求逐点 `<=1e-12 rad` |
| `src/steering_actuator.py` | `step_actuator()/predict_actuator()` | A3 物理不变；提供纯解析 rollout | 一步/20 步对 raw A3 |
| `src/causal_schema.py` | `build_schema_icr_next()` | 明确 state/control/context/label 与端点 | 未来泄漏、shape、单位测试 |
| `src/data_adapter.py` | `build_sample_icr_next()` | 配置化构造 S0/S1/S2；去重 | 字段集合快照、未来扰动测试 |
| `src/scenarios.py` | 事件字段 | 保持命令；增加因果 switch/recovery 计数 | D2 三个切换边界 |
| `scripts/audit_coverage.py` | `audit_actuator_windows()` | 按 split/base family 统计切换窗和 mask | 无窗口复制、无 split 泄漏 |
| `models/baselines.py` | fixed relative linear | 接收公共 schema，不私建输入 | S0/S1/S2 仅字段差异 |
| `models/lowrank_bilinear.py` | `LowRankBilinear` | 同一接口与 rank 集合 | zero/control-shuffle/rank 测试 |
| `scripts/train_interface.py` | `train_ablation()` | M0 后 M1；相同预算和 seed | config 差异审计 |
| `scripts/evaluate_interface.py` | `evaluate_horizons()` | 1/5/10/20、分窗、最坏轨迹、CI/相关 | 用合成预测手算 |
| `scripts/plot_interface.py` | — | 从原始 CSV/NPZ 画图并写 source hash | 图—表一致、单位完整 |
| `tests/test_icr_next_gates.py` | — | A0/A3 物理门语义和完整性故障注入 | 全部通过 |
| `tests/test_actuator_schema.py` | — | 端点、解析 rollout、去重、未来泄漏 | 全部通过 |
| `tests/test_split_integrity.py` | — | base family 完整轨迹隔离 | 交叉 split 为 0 |

## 8. 未来执行命令模板

以下只是指导，不代表本次已执行。每个阶段必须单独运行，检查 `complete.json` 和独立复算后才能输入下一条命令。

### 8.1 只读预检

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$ParentRoot = Join-Path $ProjectRoot 'revision_2026\koopman_icr_fix'
$NextRoot = Join-Path $ProjectRoot 'revision_2026\koopman_icr_next'
$NextResults = Join-Path $ProjectRoot 'revision_2026\koopman_icr_next_results'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'

$env:COMPUTERNAME
Get-PSDrive -Name D,E
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python|matlab' } |
  Select-Object ProcessId,Name,CommandLine
Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\PDxc\Review\koopman_run.md','D:\PDxc\Review\icr_fix.md'
```

不得自动结束任何未知进程。存在未知训练/仿真时先写日志并停止。

### 8.2 安全建立新版本

```powershell
if (Test-Path -LiteralPath $NextRoot) {
    throw "目标已存在，禁止覆盖：$NextRoot"
}
Copy-Item -LiteralPath $ParentRoot -Destination $NextRoot -Recurse
```

复制后使用补丁方式逐文件修改；禁止用批量字符串替换覆盖源码。新建结果目录应由 runner 在身份检查后完成。

### 8.3 测试和阶段运行

```powershell
& $PythonExe -m pytest (Join-Path $NextRoot 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'pytest failed; N0/N1/N2 NOT_RUN' }
```

```powershell
& $PythonExe -B (Join-Path $NextRoot 'scripts\run_icr_next.py') `
  --stage N0 `
  --project-root $ProjectRoot `
  --protocol (Join-Path $NextRoot 'config\protocol_icr_next.json') `
  --run-tag ICR_NEXT_R01
```

检查 N0 原始证据和独立 SHA 后，另行运行：

```powershell
& $PythonExe -B (Join-Path $NextRoot 'scripts\run_icr_next.py') `
  --stage N1 `
  --project-root $ProjectRoot `
  --protocol (Join-Path $NextRoot 'config\protocol_icr_next.json') `
  --run-tag ICR_NEXT_R01
```

N1 PASS 后才可运行：

```powershell
& $PythonExe -B (Join-Path $NextRoot 'scripts\run_icr_next.py') `
  --stage N2 `
  --project-root $ProjectRoot `
  --protocol (Join-Path $NextRoot 'config\protocol_icr_next.json') `
  --run-tag ICR_NEXT_R01
```

N2 完成后必须停止。不得把 N3、N4、N5、N6、C1、C2 写成无条件连续批处理。

## 9. 资源预算与停止规则

| 阶段 | 初始预算 | 超预算处理 |
|---|---:|---|
| N0 | 30 min | 保存身份/测试现场并停止 |
| N1 | 1–2 h | 只修审计与测试；源 SHA 变化后重跑 N0 |
| N2 | `<=2.5 h` | 先用 A3/A0 两条含重放计时；不得删成员或回放 |
| N3 | 1–2 h | 保存字段审计；不得先训练 |
| N4 | 6–10 h 初估 | 6 条 smoke 外推后冻结新预算 |
| N5 | 由 N4 实测外推 | 先 `--dry-run` 计算轨迹/磁盘，不盲跑 |
| N6-M0 | 先单配置计时 | 固定线性完成前不启动 M1 |
| N6-M1 | M0 后冻结 GPU 小时 | 可减 batch/梯度累积，不删 seed/工况 |

任一阶段达到预算 150% 且 30 分钟没有新有效产物时，安全结束本任务启动的进程，保留现场并写 `solutions.md`；不得终止其他用户进程。

## 10. 跑不动、失败与允许修正

| 问题 | 最小诊断 | 允许处理 | 禁止行为/重新进入门 |
|---|---|---|---|
| `_require_*` 导入失败 | 保存冷启动调用栈和 `sys.path` | 先加入隔离 `src` 再导入 | 源变后重跑 N0 |
| JSON 再次报 numpy 类型 | 单测 bool/int/float/array/NaN | 统一 `_json_safe()`，保持 `allow_nan=False` | 不把失败字段转字符串规避类型 |
| A0/A1 tire>0.90 | 看模式身份、首峰、速率和切换相位 | 标记 `COUNTERFACTUAL_OOD`，继续 A2/A3 | 不放宽 0.90，不改 D2 |
| A3 tire>0.90 | 分车查 Fz、Fx/Fy、实际轮角、父身份 | 若身份错误修导入；若真实则停止并缩小工作域/新协议 | 不把 A3 降为 report-only |
| A3 不能复现父 F3 | 定位首个字段、时间端点、调用路径 | 只修版本隔离/诊断开关 | 未复现不得继续 N2 |
| A2 与 A3 完全相同 | 检查 angle mask 是否从未激活 | 记录“角度限幅在本域无增量” | 不人为增大命令制造效果 |
| G0 不为机器零 | 合成直线/稳态弯手算 | 修 ICR 指标、坐标或端点 | 不用 C1 掩盖 G0 错误 |
| 切换窗不足 | 按工况/base family 列缺窗 | 只增加新 train family 或预注册自然工况 | 不复制滑窗或跨 split |
| S1 与 S0 无差异 | 检查 `chi47` 是否已含轮角、模型是否真读字段 | 去重并做字段置乱/遮蔽测试 | 不直接增加网络容量 |
| S2 比 S1 差 | 查解析端点、重复特征、条件数和 mask 稀疏 | 修端点；若合同正确则选 S1 | 不保留无增益复杂侧车 |
| 线性改善、双线性退化 | 查 rank、条件数、训练 seed、control shuffle | ridge/低秩或回退线性 | 不删线性有利结果 |
| 双线性改善、线性无效 | 检查输入—状态强耦合工况 | 限定为双线性交互优势 | 不称普适接口收益 |
| 训练 loss 降、20 步恶化 | 查谱半径、递推发散、课程和最坏窗 | 降容量/回退简单骨干 | 不只报一步误差 |
| dt 解析不了转向边界 | 对最坏轨迹做 dt/2、dt/4 峰值和冲量比较 | 新协议下增加事件子步 | 不用平滑图代替收敛性 |
| F4 工况物理失败 | 保存首个失败成员和镜像/双植物 | 修物理或明确缩小工作域并新立协议 | 不删轨迹后称 12 类覆盖 |
| C1/C2 需求不成立 | 看 N6 和相关证据链 | 保留 A3，继续 Koopman 主线 | 不因已经写了代码就强行采用 |
| GPU OOM/过慢 | 记录显存、batch、epoch 和模型 | 减 batch、梯度累积、混合精度、断点恢复 | 不删 baseline/seed/confirm |

任何 HARD 失败都必须保存：首个失败轨迹、配置 SHA、源码 manifest、调用栈、最小复现、图、允许修复、代价和重新进入门槛。没有支撑证据时必须停，不能用推测填充 PASS。

## 11. 必须交付的图、表和原始文件

### N2 图表

1. G0/G1/G2 请求 ICR 峰值、P95、RMS 和 `>0.5 m/s` 占比配对图；
2. A0–A3 实际 ICR 与请求/实际轮角时序；
3. 三个 D2 切换处的四车轮胎利用率和速率；
4. 四点 Fx/Fy 方向矢量和合力方向；
5. 四车单车横摆、系统横摆、货物横摆；
6. 四车支承载荷和轮胎容量；
7. 前后/左右阵列拉伸内力及切换后 1 s 绝对冲量；
8. A0/A1 物理越域事件表，不得隐藏失败值。

### N6 图表

1. `S0/S1/S2 × M0/M1 × h=1/5/10/20` 热图；
2. 稳态与切换窗 20 步误差配对图；
3. 预测时域增长曲线及发散率；
4. 实际轮角误差与 `J20` 改善散点/相关；
5. 最坏 D2/D4/D6/D10 真实—预测时序；
6. 四点力、阵列拉伸内力、货物/系统/单车横摆误差；
7. 参数量、训练时间、推理时间和条件数表；
8. S2 相对 S1 的增量图，防止把 S1 收益重复记到 S2。

所有图必须同时提供 PNG、PDF、源 CSV/NPZ、生成脚本、配置和 SHA256。截图只能用于展示，不能替代原始证据。

## 12. 工作记录模板

每完成一次读取、代码修改、测试或实验，立即追加同一个远端日志：

```text
revision_2026\koopman_icr_next_results\work_log.md
```

每条至少包含：

```markdown
## YYYYMMDD_HHMMSS — 阶段/动作

- 授权范围：
- 主机/项目根：
- 父任务书 SHA/源码 manifest/协议 SHA：
- 读取文件：
- 修改文件与函数：
- 修改原因：
- 完整命令：
- 退出码/墙钟/seed/线程：
- 原始产物与 SHA：
- 关键指标：
- 事实：
- 推断：
- 状态：PASS / PARTIAL / BLOCKED / NOT_RUN
- 停止原因：
- solutions.md：
- 下一允许动作：
```

修复后不得删除旧失败记录；新运行必须使用新 run id，说明旧证据为什么不能直接复用。

## 13. 最终决策表

| 结果 | 决策 | 论文处理 |
|---|---|---|
| N2 中 A3/A2 物理门通过，A0/A1 仅反事实越域 | 保留 A3，进入 N3 | 把瞬态作为真实困难区间 |
| N6 S1/S2 明显改善切换 20 步 | 冻结最简单通过接口，继续 K1–K7 | 可写状态闭合证据，尚不能写最终创新 |
| S1 有效、S2 无额外收益 | 选 S1 | 不保留解析侧车装饰性复杂度 |
| S1/S2 都无效 | 检查覆盖/重复/端点；合同正确则保留负结果 | 不声称执行器增强有效 |
| 完整接口仍差且误差与请求层 ICR 强相关 | 申请 C1/C2 独立阶段 | 修改后全部数据重建 |
| ICR 不一致对受力/控制无材料影响 | 不改分配器 | 改写为目标几何共 ICR、实际残差有界 |
| 最终 K7 不过 | 停止总体优越主张 | 只报告各方法优势域与负结果 |
| K7 过但 C0 不过 | 保留离线预测贡献 | 删除控制性能收益主张 |

## 14. 本文当前状态

本文只完成方案设计，没有修改 5080 源码、没有运行仿真、没有生成新数据、没有训练 Koopman。当前所有 `N0–N8` 均为 `NOT_RUN`。下一次若用户授权执行，首次只允许 `N0→N1→N2`，并在 N2 交付后人工停止。

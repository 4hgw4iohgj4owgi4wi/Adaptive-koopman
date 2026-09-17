# Koopman v2执行书

> 状态：`PLAN_ONLY / NOT_RUN`  
> 生效日期：2026-08-30（Asia/Shanghai）  
> 目标主机：5080 / `DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 历史协议：`koopman_dev.md`及K2-R06保持只读；不得在旧协议下运行第四次K2  
> 本文是下一轮唯一生效任务书；任何执行仍需用户另行明确授权。

## 0. 当前事实、主要矛盾和执行总顺序

### 0.1 已确认事实

| 项目 | 事实 | 证据边界 |
|---|---|---|
| 历史K0/K1 | PASS | `20260829_205447_K0_PREK2_R06`、`20260829_205455_K1_PREK2_R06` |
| 历史K2 | BLOCKED | `20260829_205514_K2_PILOT_R06`；K3–K14均NOT_RUN |
| K2数据合同 | 60条轨迹中，时间网格、参数身份、重放、split、覆盖、镜像和连接器物理均通过 | 可保留为数据生成器证据，不等于正式训练数据合格 |
| 唯一失败门 | D2的12/12条轨迹`raw tire utilization=1.133967–1.152056>0.90` | 独立从`physics_audit.csv`复算 |
| 峰值位置 | 反向阶跃第一个20 ms区间；前车约从`+2.66°`跳至`-15°` | 最坏轨迹ID 20，validation seed 911020，V1-ES |
| 阿克曼/共同ICR | 请求侧最大残差`1.543e-14 m/s`，镜像24/24对通过 | 不能把失败归因于转向几何分配错误 |
| 连接器 | 最坏轨迹四点力峰值约`1.652 kN`；作用反作用和内部零空间通过 | 不能把约16.3 kN前轮横向请求主要归因于连接器 |
| 当前执行层 | `heading_gain=2.0`，只有`±15°`角度限幅，没有转向速率或执行器状态 | `connector_r3_4/src/steering_allocator.py` |
| 轮胎容量限制 | 每车均使用固定四等分货物支承载荷 | 当前利用率是模型内部请求超限比例，不是实车超载比例 |
| 参考执行器 | `Koopman_Train`中存在`tau_delta=0.12 s`、`rate=1.2 rad/s`，另有`1.4 rad/s`配置 | 仅为内部参考参数，没有实车标定来源 |

### 0.2 主要矛盾

当前首要矛盾不是Koopman网络容量，而是：**D2要求请求转向瞬时反向，而物理植物把请求角直接当成实际轮角，没有执行器动态。** 由此生成的数据在进入学习前已经超出注册轮胎包线。

第二个矛盾是数据数量口径不一致：旧任务书为每工况设置`train/validation/development/confirm=6/2/2/3`个base family，却又要求每个非训练split至少10个独立base family。两条规则不能同时成立。

### 0.3 唯一允许的执行顺序

```text
P0 参数来源与新版本冻结
  -> P1 转向执行器实现及合同测试
  -> P2 固定12条D2孤立复验
  -> P2S 执行器参数敏感性边界
  -> P3 新物理协议下完整60条pilot
  -> D0 正式数据生成
  -> D1 数据充分性学习曲线
  -> M0–M6 逐模块Koopman学习
  -> M7 development一次性组合
  -> M8 confirm盲测
  -> M9 论文证据包
```

P2未PASS，不得运行P2S/P3；P3未PASS，不得生成正式数据；D1未判定数据足够，不得启动可训练lift、双线性或多专家。

## 1. 第一阶段：解决物理执行层主要矛盾

### 1.1 解决原则

1. 保留D2“正向5 s、立即反向5 s”的**请求阶跃**，不得靠继续缩小转角、删除低摩擦seed或放宽0.90门槛获得PASS。
2. 区分请求转角`delta_req`与实际转角`delta_act`；轮胎动力学只读取`delta_act`。
3. 首轮只增加转向执行器，不同时修改连接器、轮胎力律、载荷转移、`heading_gain`或场景速度，从而隔离贡献。
4. 使用R04原始D2合同：加速度`0.25 m/s²`，虚拟前/后角`±5°/∓2.5°`。R06的`±3.5°/∓1.75°`属于失败后的降幅诊断，不作为新主工况。
5. `tau_delta=0.12 s`、`rate_max=1.2 rad/s`只能标为“内部参考仿真合同”。没有实车来源时，不得写成硬件标定值。

### 1.2 一阶、限速转向执行器

对第`i`辆车，分配器给出请求角`delta_req_i`，实际执行器状态为`delta_act_i`。植物子步`h=0.002 s`内先计算无速率约束的一阶精确更新：

\[
\delta_{free,i}^{+}
=\delta_{req,i}+\exp(-h/\tau_\delta)
(\delta_{act,i}-\delta_{req,i}).
\]

再施加每个子步的速率与角度约束：

\[
\Delta\delta_i=
\operatorname{clip}
\left(\delta_{free,i}^{+}-\delta_{act,i},
-\dot\delta_{max}h,
+\dot\delta_{max}h\right),
\]

\[
\delta_{act,i}^{+}=
\operatorname{clip}
\left(\delta_{act,i}+\Delta\delta_i,
-\delta_{max},+\delta_{max}\right).
\]

主协议冻结：

- `tau_delta=0.12 s`；
- `dot_delta_max=1.2 rad/s`；
- `delta_max=15°`；
- 初始实际转角为0；
- 请求在一个20 ms控制区间内保持不变；执行器每2 ms更新一次，共10次。

在`1.2 rad/s`下，实际转角每20 ms最多变化`0.024 rad=1.3751°`，不得再出现约`17.66°/20 ms`的非物理跳变。

### 1.3 请求ICR与实际瞬态ICR必须分开

- `requested_icr_residual_mps`继续检查分配器目标，门槛`<=1e-8 m/s`；
- `actual_steering_icr_residual_mps`记录执行器滞后后的瞬态几何误差，但不要求方向反转首个采样仍为机器零；
- 论文只能声明“请求转向满足共同ICR分配，实际轮角受执行器动态约束并在瞬态跟踪”，不得写“整个转向瞬态四车始终严格共ICR”。

### 1.4 参数来源与敏感性

内部参考来源必须记录SHA256和行号：

- `D:\PDxc\Koopman_Train\src\controllers\hierarchical_mpc.py`：`tau=0.12 s`、`rate=1.2 rad/s`；
- `comparison_mpc.py`：`rate=1.2 rad/s`；
- `adaptive_hierarchical_mpc.py`：`rate=1.4 rad/s`。

主参数在查看新D2结果前冻结。主参数通过后，P2S只做边界诊断：

\[
\tau_\delta\in\{0.08,0.12,0.20\}\;s,
\qquad
\dot\delta_{max}\in\{0.8,1.2,1.4\}\;rad/s.
\]

九组参数不用于重新选择“最好看”的主参数；只报告通过域、失败域和性能代价。若未来取得真实车辆规格，必须另立参数身份并从P0重做。

### 1.5 载荷转移的处理边界

本轮不把逐车载荷转移与执行器同时修改。先完成执行器单因素验收。若P2中执行器角度/速率均合法但轮胎门仍失败，则停止并进入二级诊断：

1. 分解`feedforward steering`和`heading_gain*heading_error`的请求贡献；
2. 用当前固定四等分支承载荷与“逐车准静态支承载荷”做离线容量重算；
3. 检查四车垂向载荷非负、总和守恒和左右/前后转移方向；
4. 只有独立载荷模型验收后，才能建立执行器×载荷模型的2×2因子实验。

不得直接把硬门改看饱和后的`applied utilization`，因为这会掩盖原始请求超限。

## 2. 物理阶段代码修改表

所有新实现写入独立目录，不修改历史`koopman_next`和冻结`connector_r3_4`：

```text
revision_2026/
├─ koopman_next_v2/
├─ koopman_next_v2_data/
├─ koopman_next_v2_models/
└─ koopman_next_v2_results/
```

| 文件 | 函数/类 | 修改 | 输入 | 输出 | 必须测试 |
|---|---|---|---|---|---|
| `config/protocol_v2.json` | — | 冻结执行器、D2、数据split、模型和门槛 | 人工协议 | config SHA | schema、单位、seed冲突 |
| `src/steering_actuator.py` | `SteeringActuatorConfig`、`step_actuator()` | 一阶精确更新、速率/角度限制 | req/act/h | act_next/rate/mask | 零误差、单调、限速、限角、镜像、重放 |
| `src/actuator_rollout.py` | `rollout_actuator_interval()` | 10×2 ms解析侧车 | act_k/req_k | act_k1/mean/rate | 与逐子步手算一致 |
| `src/scenarios.py` | `d2_command()` | 恢复R04请求阶跃；请求和执行分开 | time/distance/direction | virtual request | 5 s时段、左右镜像、幅值 |
| `scripts/generate_data.py` | `simulate_trajectory()` | 分配器后加入执行器，plant只读实际角 | plant/params/scenario | raw NPZ | 无未来actual truth、20 ms完整区间 |
| `src/causal_schema.py` | `build_schema_v4()` | 新增请求角、实际角、速率和执行器mask | raw | schema | 时间端点、单位、未来泄漏 |
| `src/data_adapter.py` | `build_sample_v4()` | 构造51维混合状态及解析执行器上下文 | raw/params | sample | round-trip、参数透传 |
| `scripts/audit_physics_v2.py` | `audit_d2()` | 轮胎、执行器、ICR、连接器、镜像审计 | raw/manifest | audit CSV/JSON | 人工坏轨迹故障注入 |
| `scripts/run.py` | P0–M9调度 | 前序门、唯一run、留痕和停止 | stage/protocol | complete/failure | 前序失败拒绝后续 |
| `tests/test_steering_actuator.py` | — | 执行器合同 | 合成序列 | pytest | 全部硬约束 |
| `tests/test_schema_v4.py` | — | 请求/实际控制因果合同 | 合成轨迹 | pytest | 修改未来真值不改当前输入 |

代码修改必须使用可审查补丁；不得用重定向或`Set-Content`覆盖源码。每次修改前后记录SHA256。

## 3. 物理阶段任务树与硬门

### P0 — 新身份和参数来源冻结

- 复制当前已通过的K0/K1/K2实现到`koopman_next_v2`，排除缓存和结果；旧目录只读。
- 保存5080主机、Python/CUDA、进程、磁盘、冻结植物SHA、历史R06证据SHA和三个参考执行器文件SHA。
- 输出：`freeze/environment.json`、`source_hashes.json`、`actuator_parameter_sources.json`、`protocol_snapshot.md`。
- PASS：所有来源可读取且hash稳定；seed块不重叠；磁盘预计足够。
- 允许的声明：若无实车来源，状态写`SIMULATION_ASSUMPTION_TRACEABLE_NOT_HARDWARE_CALIBRATED`。
- FAIL：身份漂移无法解释或参考值抄录不一致时停止。

### P1 — 执行器实现和合同测试

- 只实现第1.2节执行器，不改变`heading_gain`、轮胎、连接器或场景。
- 测试2 ms、20 ms手算；左右镜像；请求恒定；角度/速率饱和；保存重载；未来真值扰动。
- PASS：全部pytest通过；角度越界0；速率越界`<=1e-12 rad/s`数值容差；镜像误差`<=1e-12 rad`；确定性重放逐字节一致。
- FAIL：保存首个反例、输入序列和调用栈，停止P2。

### P2 — 12条D2孤立复验

- 固定base seed：train `910020/910021`，validation `911020`；左右方向；V1-ES/R3-ES，共12条。
- 对照A0：历史瞬时执行；候选A1：只增加主执行器。
- 保持R04的`0.25 m/s²`、`±5°/∓2.5°`请求、两个5 s阶段和100 m终止。
- 主要输出：请求/实际四车角、实际角速率、请求/实际ICR、四车raw tire utilization、四点Fx/Fy、单车/系统/货物横摆、货物合力矩、完整内部力和拉伸载荷代理。
- PASS必须同时满足：
  - 12/12有限并完成100 m；所有记录间隔`0.020±1e-9 s`；
  - `max|delta_act|<=15°`，`max|dot_delta_act|<=1.2 rad/s`；
  - 12/12 `raw tire utilization<=0.90`；
  - 请求ICR、镜像、作用反作用、内部零空间、连接器极限力和重放门继续通过；
  - 不删除任一低`mu`seed，不改变请求场景和0.90门槛。
- 若A1峰值下降但仍大于0.90，状态仍为BLOCKED，不得写“问题已解决”。
- 若执行器合法而轮胎仍失败，按第1.5节停止并写二级解决方案；不得立即调`heading_gain`。

### P2S — 执行器参数边界

- 前置：P2主参数PASS。
- 对固定12条D2运行3×3参数网格；每组保留相同seed、参数、控制和初态。
- 输出每组轮胎峰值、横摆误差、完成时间、连接力、执行器滞后和失败数。
- 不重新选择主参数；将不通过组合标为仿真包线外。
- 若主参数PASS但相邻参数轻微变化即全面失败，P3前标记`ACTUATOR_PARAMETER_FRAGILE`并重新评估是否值得进入学习。

### P3 — 完整60条pilot

- 使用D0/D1/D2/D5/D6/D10；train每工况2个base seed、validation每工况1个；双植物成对。
- 全部使用主执行器参数；P2S数据不得混入clean训练。
- 重做时间、参数、重放、split、覆盖、镜像、ICR、执行器和物理审计。
- PASS：历史K2除物理门外的全部门继续通过，且60/60 `raw tire utilization<=0.90`。
- FAIL：停止正式数据生成；保留最小失败轨迹，不得修改场景规避。

## 4. 第二阶段：根据实际数据设计学习规模

### 4.1 统一统计单位

独立统计单位是`base_family`，不是轨迹文件或滑动窗口。一个base family内的V1/R3、左右镜像、相同seed/参数/初态必须进入同一split。窗口可以用于梯度训练，但bootstrap和置信区间按base family或完整轨迹配对。

### 4.2 修正后的split

共12个工况D0–D11。初始正式数据不再使用旧`6/2/2/3`口径：

| split | 每工况base family | 12工况合计 | 用途 | 生成时点 |
|---|---:|---:|---|---|
| train | 8 | 96 | 拟合和归一化 | P3 PASS后 |
| validation | 4 | 48 | 早停、超参数、数据学习曲线 | 与train一起 |
| development | 4 | 48 | 只用于一次性组合冻结 | 与train一起生成但M7前封存 |
| confirm | 8 | 96 | 最终盲测 | M7冻结模型后才生成 |
| **合计** | **24** | **288** | — | 分两次生成 |

若D1判定训练数据不足，只允许为train每工况增加2个新base family：train由96增至120，总base family由288增至312。validation、development和confirm不得从train移动或重复。

按每个base family展开2–4条双植物/镜像轨迹，理论范围为576–1152条；按当前场景展开比例预计约912条，若补充train预计约988条。该数值是资源估算，不是通过门；实际以manifest和不重叠20步窗为准。

### 4.3 每条轨迹必须包含

- 30维四车+货物状态、47维相对表示；
- 4维实际转角状态、4维请求转角、4维实际角速率；
- 四车加速度请求及20 ms内实际转角均值；
- 四点形变、锚点相对速度、端点力、区间平均力和冲量；
- 单车/系统/货物横摆，货物合力/合力矩，完整内部力和拉伸载荷代理；
- 当前及前一完成区间事件、接触和平滑统计；
- 轮胎raw/applied utilization、请求/实际ICR和执行器饱和mask；
- plant/scenario/direction/split/base family/seed/解析参数及各级SHA256。

### 4.4 数据充分性学习曲线

只用train和validation。对每工况嵌套使用`2/4/6/8`个train base family，固定同一48个validation base family，训练：

1. 相对坐标fixed linear；
2. 小型恒等lift，仅一个冻结容量。

定义：

\[
\Delta_{6\rightarrow8}
=100\frac{J_{20}^{(6)}-J_{20}^{(8)}}{J_{20}^{(6)}}\%.
\]

初始数据可判为足够，必须同时满足：

- 两个诊断模型的macro `|Delta_6to8|<2%`，且成对bootstrap 95% CI包含0；
- 12工况中没有工况在增加最后2个seed后仍改善超过5%；
- 20步非有限率不增加；训练—验证差没有持续缩小趋势；
- 覆盖秩、条件数、事件三类占用和最坏工况没有随数据量发生量级变化。

`2%/5%`是预注册的数据充分性诊断阈值，不是统计定理。若不通过，只补充train至每工况10个并复验一次；若`8->10`仍未平台化，则停止复杂模型，更新数据任务书，不得靠增大网络掩盖数据不足。

### 4.5 D0/D1数据阶段

- D0：生成train/validation/development，confirm不生成；执行全部数据合同和覆盖审计。
- D1：运行学习曲线并冻结最终train数量、归一化统计、窗口规则和数据SHA。
- 每个门控区间不重叠20步窗最低覆盖仍为：train 2000，validation/development 400；confirm生成后400。
- 左右计数差不超过20%；事件必须来自至少三个自然操纵工况，不能只依赖D10。

## 5. 混合物理—Koopman状态与因果合同

### 5.1 51维混合状态

已有相对物理状态记为`s_k in R^47`，四车实际转向状态记为`delta_act_k in R^4`：

\[
\chi_k=\begin{bmatrix}s_k\\delta_{act,k}\end{bmatrix}\in\mathbb R^{51}.
\]

执行器不交给神经网络自由学习，而由第1.2节解析侧车传播：

\[
\delta_{act,k+1}=\Phi_{act}^{10}
(\delta_{act,k},\delta_{req,k}).
\]

20 ms内实际转角均值由10个子步因果计算：

\[
\bar\delta_{act,k}=\frac1{10}\sum_{q=1}^{10}
\frac{\delta_{act,k}^{(q-1)}+\delta_{act,k}^{(q)}}{2}.
\]

植物学习输入使用：

\[
u_{act,k}=[a_{cmd,k}^{1:4},\bar\delta_{act,k}^{1:4}],
\]

而未来已知的外部控制仍是`[a_cmd,delta_req]`。多步滚动时必须从预测时刻的执行器状态计算未来`delta_act`；禁止读取数据中的未来实际转角真值。

### 5.2 Gate可见信息

门控上下文可包含当前可得量：

\[
\rho_k=[v_{p,k},\kappa_{req,k},a_{cmd,k},
\delta_{req,k},\delta_{act,k},
\delta_{req,k}-\delta_{act,k},Q_{prev},e_{prev}].
\]

`Q_prev/e_prev`只能来自`[t_{k-1},t_k]`已完成区间。`t_k`之后的轮胎峰值、接触事件或实际转角真值不得进入当前gate。

### 5.3 物理一致性边界

转向执行器是公共解析模块，所有模型共用，不计作Koopman创新收益。论文的Koopman创新只能来自相对表示、可训练lift、低秩双线性、门控、物理解码或稳定约束的增量证据。

## 6. 第三阶段：Koopman学习顺序

### M0 — 最强合法简单基线

同一数据、输入和执行器侧车下比较：

| ID | 模型 | 目的 |
|---|---|---|
| B0 | persistence | 最低基线 |
| B1 | absolute/raw linear DMDc | 复现旧表示限制 |
| B2 | relative fixed linear DMDc | 新表示的简单骨干 |
| B3 | fixed analytic lift EDMDc | 检查固定升维 |
| B4 | full bilinear | 病态性和局部作用对照 |
| B5 | low-rank bilinear | 样本效率对照 |
| B6 | sampled-IRSP | 旧稳定思路的新接口基线 |

ridge、固定lift和IRSP参数只由validation选择。输出1/5/10/20步误差、秩、条件数、发散率、参数量和推理时间。后续所有增益均相对最强合法简单基线。

### M1 — 相对表示加解析执行器

唯一变化是B1绝对表示改为B2的47维相对表示，执行器侧车对两者完全相同。

- PASS：20步相对几何和四点力至少改善8%，state30不恶化超过3%；
- 若只改善力/连接几何：保留为受力预测骨干；
- 若全部失败：停止，审计坐标、时序和归一化，不进入神经lift。

### M2 — 恒等可训练lift

\[
\eta_k=\Psi_\theta(s_k)
=\begin{bmatrix}s_k\\\phi_\theta(s_k)\end{bmatrix}.
\]

恒等通道不可删除。先一步预训练，再按`1->5->10->20`步课程训练；五个初始化seed；容量只从预注册集合选择。

- PASS：相对M1的macro `J20`改善至少5%，五seed至少4个方向一致，发散率不增加；
- FAIL：保留M1；不得继续增大网络追validation。

### M3 — 低秩双线性

先在共享骨干上运行，不与门控同时增加：

\[
\eta_{k+1}=A\eta_k+B u_{act,k}
+\sum_{j=1}^{8}u_{act,k,j}U_jV_j^T\eta_k,
\]

其中`rank(U_jV_j^T)`从`{1,2,4}`由validation选择。

- 检查D1、D2、D7/D8/D9和执行器滞后区间；
- 必做置零双线性、打乱控制配对和full bilinear对照；
- PASS：至少一个预注册强耦合工况改善8%，总体`J20`不恶化超过3%，五seed至少4个一致；
- FAIL：写明双线性的优势域或不必要性，不进入最终组合。

### M4 — 三专家门控

专家定义为平稳、操纵、连接事件。先训练共享骨干和分工况专家，用真标签做仅诊断的oracle gate：

- oracle相对共享模型在事件/切换区改善不足8%：专家不存在足够互补性，取消门控；
- oracle有效后，才训练因果gate。

\[
\hat\eta_{k+1}=\sum_{m=1}^{3}\alpha_m(\rho_k)
f_m(\eta_k,u_{act,k}),
\quad \alpha_m\ge0,\quad\sum_m\alpha_m=1.
\]

必须做常数gate、打乱gate特征、专家互换和oracle四组消融。专家占用建议5%–90%，任一专家长期占用>95%且无收益视为塌缩。

- PASS：因果gate在事件/转向切换层改善至少8%，显著优于常数gate，事件PR-AUC高于事件基率；
- FAIL：回退共享骨干。oracle有效而因果gate失败时，结论是因果特征不可辨识，不是继续加专家。

### M5 — R3物理解码

对预测锚点形变`d`和相对速度`v`使用冻结R3本构：

\[
r=\|d\|,\quad n=\frac d{\max(r,\epsilon)},\quad
p=\max(r-l_0,0),\quad s=\operatorname{clip}(p/w,0,1),
\]

\[
g=3s^2-2s^3,\qquad
F=\left(kp+c\,g\,\max(v^Tn,0)\right)n.
\]

顺序必须是：真实`d/v` oracle解码→预测`d/v`解码→事件区间平均力头。只有事件区允许小而有界的平均力残差。

- PASS：端点力、区间平均力和完整内部力20步误差至少改善10%，core状态不恶化超过3%，作用反作用、镜像、Q和`Wf_int`通过；
- 真实`d/v`失败：公式/坐标错误，立即停止；
- 真实通过、预测失败：回到M1–M4，不得用自由残差掩盖几何误差。

### M6 — 长时稳定约束

只约束去掉全局位置积分模态后的内部/相对子空间。`q in {0.97,0.99,0.995}`只由validation选择。

- 报告输入盒诱导范数充分界、采样IRSP对照和20/50/100步发散；
- PASS：50/100步发散率下降，20步`J20`恶化不超过3%；
- FAIL：保留无约束模型，删除稳定证书贡献，不把采样谱半径写成连续域保证。

### M7 — development一次性组合

- 前置：M0–M6每个模块均有PASS/FAIL；D1冻结数据充分性结论。
- 只允许组合已单独PASS的模块；最多三个候选加最强简单基线。
- development只读取一次，比较五seed、12工况、事件、退化和成本。
- 冻结唯一主候选、回退模型、模型SHA、阈值、图表表头和论文预期措辞。
- development失败：不生成confirm；论文转为适用域/负结果，不继续堆模块。

### M8 — confirm盲测

- M7冻结后生成每工况8个全新base family，共96个；不训练、不调阈值。
- 最终模型相对最强合法简单基线必须同时满足：
  - confirm轨迹macro `J20`改善至少8%，成对bootstrap 95% CI下界>0；
  - 四点力20步改善至少10%，相对几何改善至少8%；
  - state30、内部力、拉伸载荷任何一项恶化不超过3%；
  - 12工况至少8个不劣于3%，至少3个改善超过8%；
  - D2、D5和事件挑战集任何一个恶化不超过10%；
  - 非有限率不高于基线，20步推理P99<20 ms；
  - 所有执行器、因果和物理合同通过。
- 失败后不得回看同一confirm调参；保存负结果。

### M9 — 论文证据包

生成主表、1/5/10/20步曲线、学习曲线、工况热图、执行器请求/实际角、D2轮胎峰值、门控占用、双线性消融、物理解码、稳定性、成本和最坏轨迹。每张图必须同时保存CSV/NPZ、meta、脚本和SHA。

## 7. 公平性和损失

### 7.1 统一条件

- 相同train/validation/development/confirm；归一化只来自train；
- 相同未来请求控制和公共执行器侧车；禁止某模型读取未来实际角；
- 五个神经初始化seed，相同epoch、有效梯度步、早停和容量选择预算；
- R3与V1分别训练；主结构和超参数冻结后移植，不能加入plant ID混合训练后声称可迁移；
- 同时报参数量、GPU时间、显存和推理P50/P95/P99。

### 7.2 主要指标

至少分工况报告：

- `h=1/5/10/20`的state30、相对状态、执行器状态、d/v、四点力、内部力、拉伸载荷NRMSE；
- 轨迹macro、P95/P99、最坏轨迹；
- 力方向准确率和小力死区外macro-F1；
- 事件PR-AUC/Brier/ECE、门控占用和切换总变差；
- 请求/实际转角误差、速率饱和率、requested/actual ICR；
- 20/50/100步非有限率；
- base-family级成对bootstrap 95% CI和Holm校正。

主复合指标保留：

\[
J_{20}=0.25E_{state30}+0.25E_{relative}
+0.30E_{force}+0.10E_{internal}+0.10E_{tension}.
\]

执行器误差单独作为公共物理合同报告，不加入`J20`制造候选收益。

## 8. 运行命令

### 8.1 当前事实

`koopman_next_v2`及下列stage尚未实现。直接运行命令会失败；必须先按第2节使用补丁实现并通过语法/单元测试。本文不是执行授权。

### 8.2 PowerShell入口

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$V2Root = Join-Path $ProjectRoot 'revision_2026\koopman_next_v2'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Protocol = Join-Path $V2Root 'config\protocol_v2.json'
$RunScript = Join-Path $V2Root 'scripts\run.py'

if ($env:COMPUTERNAME -ne 'DESKTOP-9IUUGEO') { throw 'Wrong host' }
foreach ($Path in @($ProjectRoot,$V2Root,$PythonExe,$Protocol,$RunScript)) {
  if (-not (Test-Path -LiteralPath $Path)) { throw "Missing: $Path" }
}

& $PythonExe -m pytest (Join-Path $V2Root 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'V2 tests failed' }
```

逐阶段命令模板：

```powershell
& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage P0 --run-tag V2_R01
& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage P1 --run-tag V2_R01
& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage P2 --run-tag V2_R01
```

不得把三条命令无条件批量执行。每条完成后读取`complete.json`并从原始CSV独立复算；只有PASS才运行下一阶段。P2通过并再次获得授权后，后续stage依次为：

```text
P2S, P3, D0, D1, M0, M1, M2, M3, M4, M5, M6, M7, M8, M9
```

## 9. 失败处理

| 问题 | 最小诊断 | 允许修复 | 必须停止 |
|---|---|---|---|
| 执行器参数无实车来源 | 记录内部文件SHA和参数敏感性 | 降级为仿真假设 | 冒充硬件标定 |
| 实际角/速率越界 | 单步手算和首个坏子步 | 修正积分/裁剪顺序 | 放宽容差过门 |
| P2轮胎仍超0.90 | 分解前馈、反馈、执行器、支承载荷 | 另立二级物理诊断 | 继续缩角、删seed、调门槛 |
| actual ICR瞬态不为零 | 请求/实际分开报告 | 建立有依据的跟踪指标 | 把请求ICR当实际ICR |
| 数据学习曲线未平台 | 只补新train seed至10 | 一次定向扩充 | 复制窗口或移动split |
| lift训练loss降但20步恶化 | 递推谱、train/val、多seed | 减容量、课程训练 | 无限增大网络 |
| full bilinear病态 | rank/条件数/置零N | 低秩和ridge | 删除不利工况 |
| gate塌缩 | oracle/常数/占用/特征置乱 | 回退共享骨干 | 继续增加专家 |
| 真实d/v解码失败 | 单点手算、坐标和端点语义 | 修decoder | 修改plant真值 |
| confirm失败 | 场景/模块成对分解 | 保留负结果 | 回看confirm调参 |

任何硬门失败均保存配置、日志、首个坏轨迹、调用栈和中间模型；更新`stage_status.json`，追加一个持续的`work_log.md`和`solutions.md`，后续阶段全部标`NOT_RUN`。

## 10. 论文声明边界

### P3之前

只能声明发现并定位了瞬时转向执行假设导致的仿真包线问题；不能声明Koopman已改进。

### D1之后

只能声明数据规模和覆盖达到预注册学习门；不能声明复杂模型有效。

### M0–M6之后

可在validation层说明各模块的作用域，但不得写最终泛化结论。

### M7之后

可写development层的候选选择结果，仍不能称盲确认。

### M8之后

只有第M8节全部硬门通过，才能声明在所定义的低速、执行器参数化仿真域内改善多步预测。执行器参数没有实车来源时，必须保留“simulation-domain”限定。

## 11. 本轮停止点

本轮只编写`koopman_v2.md`，没有修改5080代码、没有创建`koopman_next_v2`、没有运行P0及任何实验。

下一次若用户明确要求执行，只允许先实现P0/P1所需最小代码与测试，再运行P0、P1和P2主参数孤立复验；P2S及以后需要查看P2原始证据后再决定，不能自动连续运行。

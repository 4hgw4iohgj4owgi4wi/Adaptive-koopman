# Koopman创新收敛路线执行书

> 编写时间：2026-08-30 14:24 +08:00  
> 授权状态：仅编写方案；未修改5080代码，未启动实验  
> 执行机器：5080工作站`DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 父任务书：`D:\PDxc\Review\koopman_v2.md`  
> 父任务书SHA256：`0927D1DBAF5BFD69387F3F9F0257F60E13BF4C9A94A2462BF9EA5BE9973A3E2E`  
> 已完成物理基线：`P0/P1/P2 PASS`，有效运行`20260830_024918_P2_V2_R02`  
> 本任务书第一次执行停止点：只允许先完成`F0→F1→F2→F3`；`F3 PASS`且人工查看原始证据后，才能授权`F4`及学习阶段。

## 0. 结论摘要

本任务书把后续路线收敛到一个目标：在可信、统一的四车—货物植物上，以公平多步预测、模块消融、独立确认和最小clean闭环实验，判断新的Koopman结构是否存在可重复的预测优势，并明确优势工况。

物理层不再无限扩张，只处理三项会直接污染Koopman数据的问题：

1. 将共同ICR拆成“目标速度几何、分配后请求轮角、执行后实际轮角”三层指标，修正当前指标命名和解释；
2. 加入转弯时四辆承载车之间的货物垂向支承载荷转移，重新计算每车轮胎容量；
3. 在一套冻结参数下完成D0–D11十二类工况覆盖验收，不允许逐工况调参。

物理层完成并不等于Koopman创新有效。创新声明还必须通过：

- fixed linear、fixed lift、full/low-rank bilinear、IRSP历史思路、三专家和最终组合的公平比较；
- `h=1/5/10/20`分工况误差、最坏工况、五训练seed和盲confirm；
- 相对表示、trainable lift、低秩双线性、门控、R3物理解码逐项消融；
- 只替换预测器的clean闭环实验。

若最终候选不能通过上述门槛，必须保留负结果并停止“Koopman总体优越”主张，不能通过删工况、换confirm或放宽门槛制造优势。

## 1. 当前事实、错误前提与信息缺口

### 1.1 已确认事实

- P2中动态转向执行器将12条D2的轮胎原始利用率峰值由`1.189849–1.210506`降至`0.289379–0.301124`，12/12通过`0.90`门。
- 当前一阶执行器为仿真参数：`tau_delta=0.12 s`、`rate_max=1.2 rad/s`、`angle_max=15 deg`，没有实车标定。
- 当前四点连接器平面`Fx/Fy`进入四辆单车和货物的平动/横摆动力学，作用反作用和内部力分解数值闭合。
- 当前轮胎侧向力采用单轨模型，但四辆车承担的货物支承载荷始终为`m_p g/4`；转弯内外侧车辆之间的垂向载荷转移尚未实现。
- 当前所谓`requested_icr_residual_mps`实际是目标速度方向的几何残差，不是分配、反馈和裁剪后真正请求轮角的ICR残差。
- 对P2原始数据独立重算，分配后请求轮角残差峰值约为`1.026–1.077 m/s`，执行后实际轮角残差为`0.910–0.955 m/s`；二者均不能用目标几何的机器零代替。
- 当前`scenarios.py`只实现D0、D1、D2、D5、D6、D10；D3、D4、D7、D8、D9、D11尚无生成逻辑。
- 当前没有在新植物上训练任何Koopman，也没有新的1/5/10/20步结果或闭环收益。

### 1.2 必须纠正的错误前提

1. **实际轮角全程严格共ICR不是必要条件。** 执行器滞后和速率限制存在时，反转瞬间严格共点通常不可实现。需要证明的是目标几何正确、请求和实际残差可解释且有界，并且跟踪/受力可接受。
2. **D0–D11不是十二套待调参数。** 它们是同一模型和同一参数身份下的覆盖工况。逐工况标定会造成方法泄漏并削弱泛化结论。
3. **平面`Fy`不等于垂向载荷`Fz`。** 当前图中所谓水平/竖直分力是货物平面内`Fx/Fy`；本任务新增的是重力方向支承载荷`Fz`。
4. **物理修正不属于Koopman创新收益。** 执行器侧车、ICR指标和载荷转移必须由所有Koopman基线共享，不能计入最终方法相对增益。
5. **离线20步改善不自动等于控制有效。** 论文若仍是控制论文，至少要做一次只替换预测器的clean闭环隔离。

### 1.3 本任务暂不解决

- 单车四轮悬架、轮胎温度、侧倾刚度和逐轮`Fz`；
- 真实连接件材料应力、疲劳寿命、FEA、HIL和实车试验；
- 10–15 m/s高速域；
- DoS、丢包、FDI/FTC、role、fallback和外部网络强基线；
- 原IRSP连续输入域证书和原Theorem 1的ISS/UUB主张。

若论文保留这些主张，则必须另立任务书补证；本任务的成功不能替代它们。

## 2. 论文目标、假设与可证伪预测

### 2.1 目标

形成一条可以被数据证伪的三步论文逻辑：

1. **比较并定位不足：** 在统一新植物和统一数据上说明固定线性、固定lift、双线性等方法分别在哪里有效、在哪里退化；
2. **逐模块创新：** 分别验证相对表示、trainable lift、低秩双线性、三专家门控和物理解码的增量作用域；
3. **只组合通过模块：** 将存在互补证据的模块组合，并在独立confirm和clean闭环中验证。

### 2.2 主要假设

| ID | 假设 | 可证伪预测 | 失败解释 |
|---|---|---|---|
| H-P1 | 当前ICR主要问题是指标混用，而非目标几何错误 | 目标几何残差继续`<=1e-8 m/s`；请求/实际残差在转向切换出现、稳态回落 | 若目标几何残差失败，先修分配器；不得训练 |
| H-P2 | 准静态逐车载荷转移会改变轮胎余量，但不会破坏当前低速D2可行域 | 载荷守恒/方向正确，D2全部`raw utilization<=0.90` | 若超门，当前D2工作域仍不可信，停止正式数据 |
| H-D1 | D0–D11能提供平稳、操纵、切换和连接事件的不同活跃子空间 | 三类区间均达到不重叠20步窗覆盖门 | 若缺区间，先补数据，不加模型容量 |
| H-M1 | 相对表示对连接几何和四点力优于绝对线性 | 20步相对几何/力改善`>=8%`，核心状态不恶化`>3%` | 失败则新路线不能从相对表示起步 |
| H-M2 | trainable lift改善固定lift不能表达的长时非线性 | macro `J20`改善`>=5%`，五seed至少四个同向 | 失败则保留简单骨干，不扩大网络 |
| H-M3 | 低秩双线性只在强输入—状态耦合工况有优势 | 至少一个D1/D2/D7–D9强耦合工况改善`>=8%`，总体不恶化`>3%` | 失败则双线性只作为负消融，不进入组合 |
| H-M4 | 三专家对平稳/操纵/连接事件存在互补性 | oracle gate在事件/切换层先改善`>=8%`；因果gate显著优于常数gate | oracle失败取消专家；因果失败回退共享骨干 |
| H-M5 | R3物理解码能将相对几何优势转化为受力预测优势 | 20步四点力/内部力改善`>=10%`，核心状态不恶化`>3%` | 真实d/v oracle失败说明坐标或公式错误，立即停止 |
| H-C1 | 离线预测优势对clean控制有实际价值 | 只换预测器后至少一个主要控制指标改善且力/失败率不恶化 | 失败则只能保留离线预测定位 |

## 3. 版本隔离与证据身份

不得修改或覆盖：

- `revision_2026\koopman_next_v2`
- `revision_2026\koopman_next_v2_data`
- `revision_2026\koopman_next_v2_models`
- `revision_2026\koopman_next_v2_results`
- `revision_2026\connector_r3_4`
- 历史R06与P2原始运行。

新版本统一写入：

```text
revision_2026/
├─ koopman_focus/
├─ koopman_focus_data/
├─ koopman_focus_models/
└─ koopman_focus_results/
```

F0复制`koopman_next_v2`作为起点，同时将冻结植物源码复制到`koopman_focus/plant`。新目录中的副本允许修改；历史目录保持逐字节不变。必须保存：

- 父任务书、P2 `complete.json`、P2 manifest和24条NPZ的SHA256；
- 新任务书SHA256；
- 新源码manifest；
- Python、CUDA、GPU、进程、磁盘与依赖；
- 每阶段配置、种子块、命令、退出码和原始产物路径。

任何源码修复改变manifest后，已有的F0/F1合同证据失效，必须重新运行F0/F1；不能让旧测试为新源码背书。

## 4. 物理公式与变量定义

### 4.1 三层ICR指标

#### 目标速度几何残差

虚拟四轮转向给出目标阵列横摆率`r*`、第`i`辆车目标速度`v_i*`和目标航向切向。保留原几何残差，但改名：

\[
e_{icr}^{geom}
=\max_i\left|v_{i,n}^{*}\right|.
\]

该量只回答目标速度方向是否指向共同ICR。

#### 分配后请求轮角残差

对经过前馈、航向反馈和`+/-15 deg`裁剪后真正发给执行器的轮角`delta_req_i`：

\[
e_{icr}^{req}
=\max_i\left|
v_i^*\tan\delta_{req,i}-L_v r^*
\right|.
\]

#### 执行后实际轮角残差

\[
e_{icr}^{act}
=\max_i\left|
v_i^*\tan\delta_{act,i}-L_v r^*
\right|.
\]

同时报告峰值、P95、RMS、超过`0.5 m/s`的时间占比以及每次转向切换后的回落时间。`0.5 m/s`只作为已见P2的诊断分层，不是实车安全阈值。

允许的论文表述是：“目标速度满足共同ICR几何；请求和实际轮角受反馈、裁剪及执行器动态影响，瞬态残差被显式建模和报告。”禁止写“整个瞬态四车轮角始终严格共ICR”。

### 4.2 四车之间的准静态货物支承载荷转移

令四个货物支承点在货物坐标系中的平面坐标为`r_i=[x_i,y_i]`，顺序固定为`FL,FR,RL,RR`。货物质量为`m_p`，质心到支承面的高度为`h_p`，当前因果货物平面加速度为`a_p=[a_x,a_y]`。

静态支承载荷：

\[
N_i^0=\frac{m_pg}{4}.
\]

建立：

\[
A=
\begin{bmatrix}
1&1&1&1\\
x_1&x_2&x_3&x_4\\
y_1&y_2&y_3&y_4
\end{bmatrix},
\qquad
b=
\begin{bmatrix}
m_pg\\
-m_ph_pa_x\\
-m_ph_pa_y
\end{bmatrix}.
\]

在无车轮离地的低速工作域内，使用最小偏离静态分配：

\[
N=N^0+A^T(AA^T)^{-1}(b-AN^0).
\]

它必须满足：

\[
\sum_iN_i=m_pg,
\quad
\sum_ix_iN_i=-m_ph_pa_x,
\quad
\sum_iy_iN_i=-m_ph_pa_y.
\]

坐标约定为`x`向前、`y`向左。若`a_y>0`表示左向加速度，则外侧`y<0`的右侧车辆应增载。若任何`N_i<-1e-9 N`，不得静默裁剪或归一化，应返回`SUPPORT_LIFT_OUTSIDE_ENVELOPE`并停止该轨迹。`[-1e-9,0)`只视为浮点余量并置零后重新检查守恒；若重新检查失败仍停止。

第`i`辆承载车用于轮胎容量和等效驱动质量的总垂向载荷为：

\[
F_{z,i}=m_vg+N_i,
\]

轮胎原始利用率改为：

\[
u_i^{raw}=
\frac{\sqrt{F_{x,i,raw}^2+F_{y,i,raw}^2}}
{\mu F_{z,i}}.
\]

本式只描述四辆承载车之间的货物支承载荷转移，不描述单车左右轮或悬架侧倾。论文必须保留这一范围限定。

### 4.3 因果性与代数闭环处理

载荷转移的`a_x/a_y`必须来自当前时刻以前可计算的植物量：

- 首选当前状态计算得到的连接器货物合力`R_p^T sum(F_payload)/m_p`；
- 多步预测中由预测状态通过冻结连接器诊断重算；
- 禁止读取`t_k`之后记录的真实区间峰值或未来加速度。

由于连接器合力由当前状态决定，支承载荷影响当前轮胎容量但不反向改变当前连接器力，可避免隐式代数环。若实现中出现相互调用，必须重构为“先连接器诊断→再支承载荷→再轮胎力→再状态导数”的固定顺序，不能用上一条轨迹缓存绕过。

### 4.4 Koopman状态和解析物理上下文

继续使用51维混合状态：

\[
\chi_k=[s_{rel,k}^{47},\delta_{act,k}^{4}]\in\mathbb{R}^{51}.
\]

四车支承载荷`N_k in R^4`是由当前物理状态解析计算的上下文，不增加为独立动态状态。数据接口增加：

- `payload_support_load4_k`；
- `vehicle_total_normal_load4_k`；
- `payload_accel_body2_k`；
- `icr_geom_k`、`icr_request_k`、`icr_actual_k`；
- 对应的`t_{k+1}`量只作为标签或诊断，禁止进入`t_k`模型输入。

所有模型共享执行器侧车与载荷转移解析模块。多步滚动时从预测状态重算，不得读取未来真实`delta_act`或`N_i`。

## 5. 代码修改表

所有路径相对`revision_2026\koopman_focus`。

| 文件 | 函数/类 | 修改内容 | 输入 | 输出 | 必须测试 |
|---|---|---|---|---|---|
| `config/protocol_focus.json` | — | 冻结父身份、F0–C0阶段、参数、seed、门槛和资源 | 人工任务书 | config SHA | schema、重复seed、非法stage |
| `src/icr_metrics.py` | `icr_geometry_residual()` | 将旧指标明确命名为目标速度几何残差 | target velocity/heading | 标量/逐车残差 | 直线、左右镜像、人工坏目标 |
| 同上 | `icr_steering_residual()` | 对请求或实际轮角使用同一轮角残差公式 | speed、yaw target、wheel angle | 标量/逐车残差 | feedforward零残差、裁剪非零、镜像 |
| `plant/load_transfer.py` | `SupportLoadConfig` | 质量、质心高度、支承点、容差配置 | params | 冻结配置 | 单位和几何秩 |
| 同上 | `solve_payload_support_loads()` | 最小偏离静载的四车`N_i`解析解和离地检测 | `a_x/a_y`、params | `N4`、守恒残差、状态 | 静态、纯ax、纯ay、组合、镜像、不可行 |
| `plant/four_vehicle_common.py` | `assemble_derivative()` | 先算连接器和货物加速度，再算`N_i`，逐车调用`tire_force(...,support_n=N_i)` | state/control/params | state derivative/audit | load off精确复现V2、load on方向/守恒 |
| `plant/event_substep.py` | `advance_outer_step()` | 审计区间保存`N_i`、容量和载荷残差；使用新plant导数 | substep state/control | endpoint/interval audit | 事件重放、无旧模块串用 |
| `src/scenarios.py` | `SCENARIOS`、`scenario_specs()` | 扩展到D0–D11并增加`submode` | protocol | specs | 数量、方向、持续时间、seed绑定 |
| 同上 | `command_for()` | 实现D3/D4/D7/D8/D9/D11；保留现有六类合同 | time/state/spec | 因果command | 边界时刻、连续性、镜像、零均值偏置 |
| `scripts/generate_data.py` | `simulate_trajectory()` | 保存三层ICR、四车支承载荷、总Fz、载荷残差 | spec/seed/plant | raw NPZ/meta | 无未来泄漏、20 ms完整区间 |
| `src/causal_schema.py` | `build_schema_focus()` | 添加解析物理上下文和标签角色 | raw fields | schema | 时间端点、单位、label隔离 |
| `src/data_adapter.py` | `build_sample_focus()` | 当前输入重算执行器和支承载荷；未来量只作标签 | raw/params/index | sample | 扰动未来真值不改当前输入 |
| `scripts/audit_physics_focus.py` | `audit_trajectory()` | ICR三层、Fz、轮胎、连接器、镜像、作用反作用审计 | raw/manifest | CSV/JSON | 人工故障注入 |
| `scripts/audit_coverage.py` | `audit_windows()` | 十二工况、三门控区间、Fz、事件和20步窗覆盖 | dataset | coverage JSON | 不重叠窗和base family统计 |
| `models/baselines.py` | B0–B6 | persistence、absolute/relative linear、fixed lift、full/low-rank bilinear、历史IRSP诊断 | train/val | checkpoints | 相同输入和预算 |
| `models/trainable_lift.py` | `IdentityLift` | 恒等通道加可训练残差lift | `chi` | `eta` | 恒等保留、inverse/core decode |
| `models/lowrank_bilinear.py` | `LowRankBilinear` | `U_j V_j^T`控制耦合 | eta/u | eta next | rank、置零、打乱控制 |
| `models/mixture.py` | `CausalThreeExpert` | 平稳/操纵/连接事件三专家和因果gate | eta/u/rho | eta next/alpha | 权重和1、常数/打乱/oracle、塌缩 |
| `models/r3_decoder.py` | `decode_force()` | 由预测连接形变/速度调用冻结R3本构 | predicted d/v | 四点力/内部力 | 真实d/v oracle、镜像、作用反作用 |
| `scripts/train.py` | `train_model()` | 统一预算、五seed、课程`1→5→10→20`、恢复/OOM | config/data | model/log | 确定性和断点恢复 |
| `scripts/evaluate.py` | `evaluate_horizons()` | 分工况1/5/10/20、最坏值、发散、推理时间 | frozen model | metrics CSV | 模型选择只读val |
| `scripts/confirm.py` | `blind_confirm()` | 一次性confirm锁和轨迹级配对CI | frozen selection | confirm报告 | 禁止二次选择 |
| `control/run_clean_swap.py` | `run_predictor_swap()` | 同一MPC只替换预测器 | baseline/candidate | clean闭环指标 | 同初态/约束/预算/trace |
| `scripts/plot.py` | — | 由原始CSV/NPZ生成论文图和图哈希 | artifacts | PNG/PDF | 单位、来源和数据hash |
| `scripts/run.py` | F0–C0调度 | 前序门、唯一run、失败停止和工作记录 | `--stage` | complete/failure | 前序失败拒绝后续 |

## 6. D0–D11统一参数工况

现有D0、D1、D2、D5、D6、D10的定义优先保持；新增工况在F4执行前冻结到协议，运行后不得改幅值。

| 工况 | 定义与建议初值 | 方向/成员 | 主要目的 |
|---|---|---|---|
| D0 | 6 s直线匀速，`a=0, delta=0` | none | 平稳骨干与低活跃变量 |
| D1 | 0–2 s `+0.35 m/s^2`；2–5 s匀速；5–7 s `-0.50 m/s^2`；1 s稳定 | none | 纵向与前后载荷转移 |
| D2 | 100 m；前30 m `+0.25 m/s^2`；`+5/-2.5 deg` 5 s后反向5 s；余程减速 | left/right | 转向反转和执行器极限 |
| D3 | 8 s；1 s平滑升到虚拟前/后`+/-4/+/-2 deg`，保持4 s，1 s退出 | left/right | 稳态弯和持续外侧增载 |
| D4 | 8 s；1–5 s使用一周期平滑双向`4 deg`正弦单移线，后轮为前轮`-0.5`倍 | left/right | 过渡横向动力学 |
| D5 | 保留现有9 s回头弯，峰值虚拟前轮`8 deg`、后轮`-4 deg` | left/right | 强持续曲率和lift优势区 |
| D6 | 保留现有7 s入弯—稳态—出弯，峰值`5/-2.5 deg` | left/right | 活跃子空间切换 |
| D7 | 8 s；前两车`+0.20`、后两车`-0.20 m/s^2`保持2 s，再反向2 s，四车偏置和为0 | none | 纵向连接内力和双线性加速度耦合 |
| D8 | 8 s；左侧两车`+0.8 deg`、右侧两车`-0.8 deg`保持2 s，再反向2 s | left/right mirror | 左右内力、方向和横向载荷 |
| D9 | 8 s；成员A为FL/RR与FR/RL相反的`+/-0.15 m/s^2`；成员B使用`+/-0.6 deg`对角转向偏置 | diag-A/diag-B | 完整内部力零空间 |
| D10 | 保留现有8 s边界chirp：虚拟转向包络峰值8 deg，纵向正弦0.12 m/s² | left/right | 接触、平滑区和短驻留事件 |
| D11 | 10 s；`a=0.15 sin(2 pi 0.25t)`，虚拟前轮`4 sin(2 pi 0.18t)` deg，后轮`-0.5`倍；1 s淡入淡出 | left/right | 混合操纵和非单一工况泛化 |

新增D7–D9的单车偏置必须经过现有转向/加速度硬限幅，且同一时刻零均值偏置不得改变阵列平均加速度。若pilot证明某建议幅值直接越过物理门，状态是工况失败；不得在看过结果后偷偷缩小。允许的恢复方式是另立协议版本并把原失败范围记录为工作域外。

## 7. 数据规模、划分和公平性

### 7.1 F4 pilot

每工况使用2个train参数族和1个validation参数族。每个base family同时生成V1-ES/R3-ES；方向/对角成员绑定到同一split。

按本任务展开预计：

- 非方向D0/D1/D7：`3工况×3族×2植物=18`条；
- 左右D2/D3/D4/D5/D6/D8/D10/D11：`8×3×2方向×2植物=96`条；
- D9：`1×3×2成员×2植物=12`条；
- 合计约126条保存轨迹；每条再做一次确定性重放，共约252次仿真。

该数量用于资源预算，不是统计独立样本数。统计单位始终是base family；左右镜像和双植物不能冒充独立随机样本。

### 7.2 正式数据

| split | 每工况base family | 12工况合计 | 用途 | 生成时点 |
|---|---:|---:|---|---|
| train | 8 | 96 | 拟合、归一化和学习曲线 | F4 PASS后 |
| validation | 4 | 48 | 早停、超参数和模块门 | 与train一起 |
| development | 4 | 48 | 一次性组合冻结 | 生成后封存至K6 |
| confirm | 8 | 96 | 最终盲确认 | K6冻结后才生成 |
| 合计 | 24 | 288 | — | 分两批生成 |

训练量学习曲线使用嵌套`2/4/6/8`个train base family；若`6→8`未平台化，只允许增加新的train族到10，禁止移动validation/development/confirm。

不重叠20步窗最低门：

- train每个专家区间至少2000窗；
- validation/development每区间至少400窗；
- confirm生成后每区间至少400窗；
- 左右base family差不超过20%；
- 连接事件必须来自至少三个自然工况，不能只靠D10。

## 8. 顺序任务树和硬门

### F0 — 新版本冻结

**前置：** P2 R02有效证据可读取；无未知训练进程。  
**修改：** 只创建隔离目录、复制源码和写协议，不改变物理。  
**输出：** 环境、来源hash、父运行hash、seed审计、任务书快照。  
**PASS：** 历史hash不变；新manifest完整；磁盘空闲`>=80 GiB`；seed无冲突。  
**FAIL：** 身份漂移、来源缺失或未知进程无法解释时停止。

### F1 — ICR三层指标和因果合同

**前置：** F0 PASS。  
**修改：** 只增加指标，不改变分配器、执行器、轮胎或连接器。  
**试验：** 对P2的24条原始轨迹离线重算；再运行合成直线/稳态弯/裁剪/速率限制测试。  
**PASS：**

- `e_geom<=1e-8 m/s`；
- 新`e_act`对原NPZ逐点复算与已记录actual公式一致，最大绝对差`<=1e-12 m/s`；
- 新`e_req`对A0 instant轨迹应与同公式actual逐点一致，差`<=1e-12 m/s`；
- 左右镜像标量一致、逐车顺序映射正确；
- 未来actual/Fz扰动不改变当前输入。

**注意：** F1不以`e_req/e_act=0`为门。若名称、时序或坐标不能闭合，停止F2并写`koopman_solutions.md`。

### F2 — 四车支承载荷转移单元和植物合同

**前置：** F1 PASS。  
**修改：** 实现第4.2节解析载荷分配；增加`load_transfer_enabled`因子。  
**PASS：**

- 静态四车各为`m_pg/4`，相对误差`<=1e-12`；
- 总载荷和两个力矩约束相对残差`<=1e-10`；
- `a_y>0`时右侧`y<0`总支承载荷大于左侧，镜像后反向；
- `a_x>0`时后侧总载荷大于前侧，制动反向；
- `load_transfer_enabled=false`对冻结P2 A1最小回放的状态、轮胎和连接力复现误差`<=1e-10`相对或记录首个浮点差来源；
- 无NaN/Inf、无静默负载裁剪、无未来量读取。

**FAIL：** 守恒、方向、镜像或回放任一失败立即停止；不得进入D2整车。

### F3 — D2载荷转移孤立复验

**前置：** F2 PASS。  
**矩阵：** 固定P2的3参数族×左右×V1/R3，共12组；每组重跑：

- L0：动态执行器+静态四等分支承；
- L1：动态执行器+逐车载荷转移。

共24条保存轨迹和24次重放。所有外部命令、seed、初态和停止规则相同。

**主要输出：** 四车`N_i/Fz_i`、载荷转移矩、三层ICR、轮胎利用率、四点Fx/Fy、单车/货物横摆、货物合力矩和拉伸载荷。

**PASS：**

- 12/12 L1有限并完成100 m；
- 所有L1 `N_i>=0`，总载荷/矩约束通过；
- 12/12 `raw tire utilization<=0.90`；
- 执行器角度/速率、连接器极限、作用反作用、内部力、镜像和重放继续通过；
- `e_geom<=1e-8 m/s`；`e_req/e_act`必须报告峰值/P95/RMS/占比，不得用`e_geom`替代；
- 相对L0，货物横摆率、惯量加权阵列指标或连接力任何一项恶化超过10%时标记`TRADEOFF_REVIEW`，即使轮胎门通过也必须人工审查后才能F4。

**硬停止：** 任一L1轮胎超0.90、支承离地、守恒失败或连接器极限失败，则F4及以后NOT_RUN。

### F4 — D0–D11完整pilot

**前置：** F3 PASS并获得单独授权。  
**先做：** 冻结六个新增场景及测试；不得直接生成正式数据。  
**规模：** 约126条保存轨迹+逐条重放。  
**PASS：**

- 12类工况均有对应base family，所有预期成员存在；
- 全部有限、时间网格/停止合同/参数/重放/split通过；
- 全部`N_i>=0`、`raw tire utilization<=0.90`、连接力低于数值极限；
- 三层ICR、作用反作用、内部力、镜像和场景连续性通过；
- 平稳/操纵/连接事件三类区间均有非零覆盖；
- 资源外推支持正式数据。

**FAIL：** 保存首个失败工况和最小轨迹。允许选择“修物理”或“缩小论文工作域”，但必须新建协议版本；不得只删失败轨迹后继续声称覆盖D0–D11。

### K0 — 正式train/validation/development数据和覆盖

**前置：** F4 PASS。  
**输出：** train/validation/development；confirm不生成。  
**PASS：** manifest、哈希、base family隔离、归一化仅train、因果接口和覆盖门全部通过。

### K1 — 数据学习曲线和最强简单基线

**模型：** B0 persistence、B1 absolute linear、B2 relative linear、B3 fixed analytic lift。  
**学习量：** 2/4/6/8 train族嵌套。  
**PASS：** 选定训练量平台化，或按规则扩到10后仅复验一次。  
**FAIL：** 8→10仍未平台，停止复杂模型并更新数据协议。

### K2 — 固定基线、full/low-rank bilinear和IRSP历史诊断

统一数据、状态、执行器/Fz侧车、ridge选择、训练预算和五seed，输出B1–B6的1/5/10/20步结果、秩、条件数、参数量、推理时间和发散率。IRSP只作为历史诊断，不允许重新声明连续域稳定证书。

### K3 — 相对表示和trainable lift

- 先验证B2相对B1的20步相对几何/力改善`>=8%`，core状态不恶化`>3%`；
- 再训练恒等lift，macro `J20`相对最强合法简单骨干改善`>=5%`；
- 五seed至少四个方向一致，发散率不增加。

任一前门失败，后续不能靠扩大lift补救。

### K4 — 低秩双线性增量

rank只从`{1,2,4}`由validation选择；必须做置零双线性、打乱控制配对和full bilinear对照。

**PASS：** 至少一个D1/D2/D7/D8/D9强耦合工况20步改善`>=8%`，总体`J20`不恶化`>3%`，五seed至少四个同向。  
**FAIL：** 写明双线性优势域或无必要性，不进入最终组合。

### K5 — 三专家门控

专家固定为平稳、操纵、连接事件。顺序：共享骨干→分区专家→oracle gate→因果gate。

- oracle相对共享模型事件/切换层改善不足8%：取消门控；
- 因果gate必须显著优于常数gate和打乱特征；
- 任一专家长期占用`>95%`且无增益视为塌缩；
- 事件PR-AUC必须高于事件基率。

### K6 — R3物理解码和候选组合冻结

先做真实d/v oracle，再做预测d/v解码。oracle若不能逐点复现冻结R3本构，说明坐标、端点时序或公式错误，立即停止。

只允许组合K3–K5中已经单独通过的模块。development只读取一次，用于在预注册候选中冻结一个最终方法；不得根据development发明新模块。

### K7 — 生成confirm并一次性盲测

生成每工况8个新confirm base family，锁定数据后只运行冻结基线和冻结候选。

最终允许声明“Koopman改进”的门：

- 相对最强简单基线，macro `J20`改善`>=5%`；
- 至少一个预注册强耦合/切换工况改善`>=8%`，四点力/内部力若作为主张则改善`>=10%`；
- 任一重要工况恶化不超过3%；
- 发散和非有限率不增加；
- 轨迹级成对bootstrap 95% CI支持主要增益，报告效应量和最坏轨迹；
- confirm不能用于重新选rank、专家或网络容量。

### C0 — 最小clean闭环预测器替换

**前置：** K7 PASS。  
**工况：** 单移线D4、回头弯D5、入弯/出弯D6；先不加网络干扰。  
**公平性：** 相同MPC结构、约束、权重、初态、求解预算和物理植物，唯一变化是预测器。  
**指标：** 轨迹横/纵向RMSE、货物姿态、四点连接力P95/P99/峰值、拉伸载荷、轮胎利用率、不可行率、完成率、求解时间。  
**成功：** 至少一个预注册主要闭环指标改善，完成率/不可行率不恶化，连接力和拉伸载荷不恶化超过3%。  
**失败：** 离线结果仍可作为预测研究，但删除“改进控制性能”主张。

## 9. 复合预测指标和统计口径

对每个工况和预测时域先按训练集尺度归一化，再按base family求轨迹级误差。禁止把滑动窗口当独立样本。

建议冻结：

\[
J_{20}=0.25E_{core}+0.20E_{relative}
+0.20E_{force4}+0.15E_{internal}
+0.10E_{yaw}+0.10E_{actuator}.
\]

其中：

- `E_core`：30维物理状态或去除全局平移后的核心状态；
- `E_relative`：四车—货物相对位姿/速度；
- `E_force4`：四点端点和区间平均力；
- `E_internal`：完整内部力和前后/左右拉伸载荷；
- `E_yaw`：四车与货物横摆；
- `E_actuator`：四车实际轮角。

`0.25/0.20/...`是预注册论文权重，不是物理定理；K0前必须冻结，之后不得按结果修改。除macro外必须报告每工况、P95/P99、最坏base family、发散率和方向配对。

## 10. 必须生成的图表和原始产物

### 物理图

1. 三层ICR时序：目标几何、请求轮角、实际轮角；标出转向切换；
2. 四车`N_i`和总`Fz_i`，标出左/右、前/后和载荷守恒残差；
3. L0/L1逐轨迹轮胎峰值配对图及0.90门；
4. 最差D2的请求/实际转角、轮胎、四点Fx/Fy、货物/单车横摆和拉伸载荷；
5. D0–D11覆盖矩阵：工况、方向、事件、Fz范围、力范围和20步窗数。

### Koopman图

1. 模型×工况×horizon误差热图；
2. 20步轨迹级配对差和bootstrap CI；
3. 预测时域增长曲线及发散率；
4. 各模块消融瀑布图；
5. 三专家权重、占用和切换图；
6. 最坏工况真实/预测的相对位姿、四点力、货物横摆；
7. 训练量2/4/6/8/10学习曲线；
8. clean闭环只换预测器的跟踪—受力—求解时间对比。

所有图必须附生成脚本、源CSV/NPZ、配置和SHA256，不能只有截图。

## 11. 跑不动、失败和恢复方案

| 问题 | 最小诊断 | 允许修复 | 必须停止/禁止行为 |
|---|---|---|---|
| 新plant导入失败 | 记录主进程/worker `sys.path`和首个调用栈 | 只修隔离目录导入；manifest变化后重跑F0/F1 | 不从历史结果目录临时导入未知模块 |
| ICR三层数值不闭合 | 用合成feedforward、裁剪和instant A0逐点手算 | 修名称、时间端点或公式 | 不把目标几何残差继续冒充请求轮角残差 |
| Fz守恒或方向错误 | 输出A、b、N0、N、坐标顺序和首个坏状态 | 修符号、坐标和矩阵求解 | 不用归一化掩盖力矩不守恒 |
| 出现负支承载荷 | 保存首个状态、加速度和支持多边形 | 判定工作域外；必要时另立低速/曲率协议 | 不静默clip后继续 |
| F3轮胎重新超0.90 | 分车查看Fz、raw Fx/Fy和转向瞬态 | 检查模型错误；若真实则缩小论文工作域并新立协议 | 不调mu、删seed、放宽0.90或改看饱和值 |
| 新场景不连续/镜像失败 | 检查边界前后命令和成员映射 | 修场景函数并重新冻结F4 | 不只删除失败方向 |
| F4单一工况失败 | 保存最小轨迹和同seed双植物/镜像 | 修物理或明确删除该工况及广泛声明，需新协议 | 不在旧协议下跳过后继续正式数据 |
| 数据覆盖不足 | 按工况/专家区间列缺窗来源 | 只增加新train参数族或增强已预注册场景 | 不复制窗口、移动split或使用D10冒充全部事件 |
| GPU OOM | 保存显存、batch、模型和阶段 | 减batch、梯度累积、混合精度；保持模型/seed/预算 | 不因OOM删baseline或减少confirm |
| 训练过慢 | 先测B1/B2每epoch和20步评价外推 | 分阶段缓存、并行seed、合理early stop | 不无条件批量跑K3–K7 |
| train loss下降但20步恶化 | 查递推谱、train/val和五seed | 减容量、课程或回退简单骨干 | 不无限加网络追validation |
| full bilinear病态 | 查条件数、rank、置零项、控制打乱 | ridge或低秩；保留full负对照 | 不删不利强耦合工况 |
| gate塌缩 | oracle、常数、打乱、专家占用 | 回退共享骨干 | 不继续增加专家 |
| R3 oracle解码失败 | 单点手算d/v、坐标、端点/区间定义 | 修decoder和接口 | 不修改plant真值迎合decoder |
| confirm无优势 | 按工况和模块成对分解 | 保留负结果，改为方法适用域论文 | 不回看confirm调参或换confirm seed |
| clean闭环无优势 | 查预测误差是否落在MPC敏感状态/约束 | 降级为离线预测贡献 | 不把离线改善写成闭环改善 |

任一硬门失败必须生成或追加`koopman_focus_results\solutions.md`，包括已确认事实、根因候选、最小诊断、可选修复、代价、风险和重新进入门槛。

## 12. 运行命令模板与资源边界

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$FocusRoot = Join-Path $ProjectRoot 'revision_2026\koopman_focus'
$Protocol = Join-Path $FocusRoot 'config\protocol_focus.json'
$RunScript = Join-Path $FocusRoot 'scripts\run.py'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'

& $PythonExe -m pytest (Join-Path $FocusRoot 'tests') -q
& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage F0 --run-tag FOCUS_R01
```

每个阶段必须单独执行，读取`complete.json`并从原始CSV/NPZ独立复算后才能运行下一阶段。不得把下列命令无条件写成连续批处理：

```text
F0, F1, F2, F3, F4, K0, K1, K2, K3, K4, K5, K6, K7, C0
```

初步资源预算：

- F0–F2：0.5–1 h；
- F3：按现有P2约1–2 h；
- F4：约6–10 h，先以6条smoke外推；
- 正式数据：由F4实测单轨迹成本重新估算，未外推前不得启动；
- K0–K7：先完成B1/B2单seed计时，再冻结GPU小时预算。

任何单阶段超过协议预算150%且无新有效产物，应安全结束本任务进程、保留现场并写解决方案；不得终止其他用户进程。

## 13. 工作记录要求

使用一个持续追加的远端日志：

`revision_2026\koopman_focus_results\work_log.md`

每项完成立即记录：

- 时间、任务ID和授权模式；
- 主机、项目根、源码/config/data SHA；
- 读取、修改文件和函数；
- 完整命令与退出码；
- 原始产物和关键数字；
- 事实/推断/建议/未知；
- PASS/PARTIAL/BLOCKED/NOT_RUN；
- 停止原因和下一允许动作。

失败运行和异常调用栈不得删除；绘图或独立审计脚本修复不得修改原始NPZ、manifest或已完成阶段的源码身份。

## 14. 论文声明边界

### F3之后

只能声明新的低速仿真植物显式区分三层ICR，并加入四承载车间准静态货物支承载荷转移；不能声明Koopman改进。

### F4之后

只能声明D0–D11在冻结仿真参数下通过或暴露了工作域；不能声明实车标定、真实轮胎安全或材料抗撕裂。

### K2–K6之后

可在validation/development层报告各Koopman结构的作用域和负结果；不得称最终泛化。

### K7之后

只有盲confirm全部主要门通过，才允许声明最终候选在定义的低速、四车—刚性货物、执行器参数化仿真域中改善多步预测。

### C0之后

只有clean预测器替换显示闭环增益，才允许写“预测改进转化为控制收益”。网络韧性、DoS和稳定性仍需独立证据。

## 15. 第一次实际停止点

本MD完成后不得自动执行。用户下一次若明确要求运行，只允许：

1. 创建隔离`koopman_focus*`目录；
2. 实现并运行F0、F1、F2；
3. F2 PASS后运行F3 D2载荷转移孤立复验；
4. 保存原始证据、图片、状态、工作日志和解决方案；
5. 在F3结束后停止。

F4、正式数据、Koopman训练和clean闭环均需要在用户查看F3原始结果后另行授权。

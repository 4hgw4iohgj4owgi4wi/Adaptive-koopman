# 连接器R3边界平滑执行书

> 状态：待冻结、待执行。R1与R2均为已查看结果的历史修订，禁止覆盖或回写。  
> 主目标：保持V1在全部穿透范围内的线性弹性刚度和大穿透受力，只平滑阻尼在间隙边界的接入过程，消除接触瞬间的有限力跳；通过植物全门后才重建数据、重训Koopman和恢复MPC。  
> 方法定位：R3是“边界正则化的单边间隙弹簧阻尼连接器”，不是标准Hunt--Crossley模型，也不作为连接器本身的论文创新点。

## 0. R2结果与本轮决策

### 0.1 已冻结事实

R2采用

\[
F_N^{R2}=
\left[K\delta^{1.5}+C_H\delta^{1.5}v_n\right]_+.
\]

它已经完成并通过：

- G1代数、方向、作用--反作用和完整内力分解；
- G2单连接器连续起力、能量和确定性；
- G3低载荷步长收敛；
- G5左右镜像和弯向受力方向。

它在G4失败：

```text
100 m停止距离              75.587 m
触发极限                   15.000 kN
V2/V1峰值力比              7.546
V2/V1 RMS力比              6.151
V2/V1冲量比                2.386
V2完整内部力峰值           20.731 kN
回头弯V2/V1峰值            7.757/0.651 kN
最大2 ms力跳下降           81.83%
原始接触切换               40/12
```

R2的失败目录、源码、图、JSON、hash和停止报告保持只读：

```text
revision_2026/connector_v2_results/r2_energy_match/
revision_2026/connector_v2_results/plant_validation/
D:\PDxc\Review\connector_v2_solutions.md
```

### 0.2 R2失败机理

R2的\(K\)只在冻结V1 train的活动穿透中位数

\[
\delta_{ref}=1.757\ \mathrm{mm}
\]

处做割线匹配，因此

\[
\frac{F_{R2}}{F_{V1}}
=\sqrt{\frac{\delta}{\delta_{ref}}}.
\]

当穿透达到50 mm和75.6 mm时，该比值分别约为5.33和6.56。R2的主要失败不是积分步长或坐标系错误，而是局部匹配的幂律刚度向大穿透区错误外推。

### 0.3 本轮路线选择

R3不继续搜索\(n,K,C_H\)，原因是当前没有实物力--位移、材料、间隙、循环加载或恢复系数数据。继续调幂律参数容易演变成为了通过已经看过的C4而调植物。

R3采用最小物理改动：

1. 弹性力在全域严格保持V1的\(k\delta\)；
2. 仍只在加载阶段提供阻尼，保持V1的耗能方向；
3. 仅在接触建立后的窄穿透区平滑增加阻尼权重；
4. 超出平滑区后严格恢复V1公式；
5. 不增加滞环、摩擦、失效记忆或额外离散模式；
6. 保留已经通过的完整内部力分解模块。

## 1. R3唯一规范公式

### 1.1 几何量与符号

连接点顺序固定为：

```text
FL, FR, RL, RR
```

定义：

\[
\boldsymbol d_i
=\boldsymbol p_{v,i}-\boldsymbol p_{L,i},
\qquad
r_i=\|\boldsymbol d_i\|,
\qquad
\boldsymbol n_i=\frac{\boldsymbol d_i}{\max(r_i,\varepsilon_r)},
\]

\[
\delta_i=[r_i-l_0]_+,
\qquad
v_{n,i}=\dot{\boldsymbol d}_i^\top\boldsymbol n_i.
\]

`vn > 0`表示连接距离增大、穿透量增加，即加载。

### 1.2 阻尼接入函数

令

\[
s_i=\frac{\delta_i}{\delta_s},
\]

采用三次平滑阶跃：

\[
g(\delta_i)=
\begin{cases}
0,&\delta_i\le0,\\
3s_i^2-2s_i^3,&0<\delta_i<\delta_s,\\
1,&\delta_i\ge\delta_s.
\end{cases}
\]

它满足：

\[
g(0)=0,\quad g(\delta_s)=1,
\quad g'(0)=g'(\delta_s)=0.
\]

### 1.3 法向力

R3法向力为

\[
F_{N,i}^{R3}
=k\delta_i+c\,g(\delta_i)[v_{n,i}]_+.
\]

二维作用力为

\[
\boldsymbol F_{L,i}=F_{N,i}^{R3}\boldsymbol n_i,
\qquad
\boldsymbol F_{v,i}=-\boldsymbol F_{L,i}.
\]

该公式具有以下关键性质：

1. `delta=0`时弹性和阻尼力均为零；
2. 接触初始不再产生\(cv_n\)有限跳变；
3. 静态时对任意穿透严格满足

\[
F_N(\delta,v_n=0)=k\delta;
\]

4. 当\(\delta\ge\delta_s\)且\(v_n>0\)时严格恢复V1：

\[
F_N^{R3}=k\delta+cv_n;
\]

5. 卸载\(v_n\le0\)时阻尼项为零，与V1一致；
6. `k`继续使用N/m，`c`继续使用N·s/m，无幂律量纲转换。

### 1.4 能量与耗散

弹性势能：

\[
U_i=\frac12k\delta_i^2.
\]

阻尼耗散率：

\[
P_{d,i}=c\,g(\delta_i)[v_{n,i}]_+^2\ge0.
\]

连接器对车辆与货物的总机械功率：

\[
P_i=-F_{N,i}v_{n,i}.
\]

实现必须逐样本记录`elastic_energy_j`和`damping_power_w`，不得继续使用R2的\(C_H\delta^n v_n^2\)。

### 1.5 当前不加入的机制

本轮明确不加入：

- 接触/脱离双阈值滞环；
- 切向库仑摩擦；
- 预紧；
- 连接器扭转刚度；
- 三维重力方向连接动力学；
- 磨损、疲劳和断裂状态；
- 冲量或互补接触求解。

原因不是这些机制不重要，而是没有实物参数；同时加入会破坏“只验证边界平滑作用”的归因。

## 2. 平滑宽度`delta_s`的冻结方法

### 2.1 数据访问边界

`delta_s`只允许读取已经冻结的V1 train基础轨迹及其控制。禁止读取：

```text
V1 validation
V1 development
任何confirm
R1/R2 C4输出作为参数搜索目标
旧MPC结果作为参数选择指标
```

脚本必须在运行前检查输入路径和split；发现非train输入立即退出。

### 2.2 500 Hz接触建立事件

对256个V1 train基础族使用保存的`initial_state64/control64`在植物层\(dt=0.002\) s精确回放。对每个连接点检测：

\[
\delta_{k-1}=0,\qquad\delta_k>0.
\]

记录首次活动子步的：

```text
delta_on_m
vn_on_mps
old_damping_force_n = c*[vn_on]_+
scenario
trajectory_id
connector_id
```

过滤规则只允许排除：

- 非有限值；
- `vn_on <= 0`，因为没有加载阻尼；
- 重复的解析镜像，不计为独立事件。

不得按C4表现、人为力阈值或某一工况删除事件。

### 2.3 唯一冻结规则

预注册：

\[
\delta_s=Q_{0.99}(\delta_{on}\mid v_{n,on}>0).
\]

选择99%分位的含义是：绝大多数接触建立事件至少经过一段平滑接入，而不是在第一个植物子步直接恢复全部阻尼。

冻结前检查：

\[
0<\delta_s<0.25Q_{0.50}(\delta\mid\delta>0).
\]

如果不满足，停止并报告train数据的时间分辨率或接触事件覆盖不足，不允许裁剪到一个人为上下限。

输出：

```text
connector_r3_results/r0/delta_s_events.csv
connector_r3_results/r0/delta_s_freeze.json
connector_r3_results/r0/input_manifest.json
```

`delta_s_freeze.json`至少保存事件数、各分位数、脚本hash、V1 manifest hash、train文件hash集合和`development_read=false/confirm_read=false`。

## 3. 代码修改方案

### 3.1 目录与版本

5080主目录：

```text
D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\
```

新源码目录：

```text
connector_r3/
├─ src/
├─ tests/
├─ scripts/
├─ protocol.md
└─ README.md
```

新结果目录：

```text
connector_r3_results/
connector_r3_data/
connector_r3_models/
connector_r3_mpc/
```

R1/R2目录只读。禁止在`connector_v2_results/r2_energy_match`下创建R3文件。

### 3.2 唯一受力实现

建议新增：

```text
connector_r3/src/connector_r3.py
```

参数类：

```python
@dataclass(frozen=True)
class ConnectorR3Params:
    law_version: str = "plant_r3_boundary_regularized"
    stiffness_npm: float = 30000.0
    damping_nspm: float = 3500.0
    free_play_m: float = 0.002
    smoothing_width_m: float = ...  # frozen train-only
    rated_force_n: float = 12000.0
    ultimate_force_n: float = 15000.0
```

主接口：

```python
connector_force_r3(
    displacement_world,
    relative_velocity_world,
    params,
) -> ConnectorResult
```

输出字段：

```text
distance_m
penetration_m
normal_world
normal_speed_mps
smoothing_weight
elastic_force_n
damping_force_n
raw_force_n
force_payload_world_n
force_vehicle_world_n
elastic_energy_j
damping_power_w
contact_active_raw
load_active_effective
rated_force_exceeded
ultimate_force_exceeded
```

### 3.3 极限的处理

`12/15 kN`目前没有实物证据，只能保留为数值诊断边界。R3禁止用饱和截断后继续仿真：

1. 正常样本中`applied_force = raw_force`；
2. `raw_force >= ultimate_force`时记录事件并停止轨迹；
3. 不从12/15 kN反算虚构的工作/失效位移；
4. 元数据写明`strength_source = numerical_legacy_unverified`；
5. 论文不得把该阈值称为实物断裂极限。

### 3.4 禁止多份公式

下列文件必须调用统一R3接口，不能复制公式：

```text
revision_2026/model/four_vehicle_coupled_r3.py
revision_2026/koopman/*data_generator_r3*.py
connector_r3/scripts/*
Koopman物理受力头
MPC受力代价与约束适配器
```

重点审计旧硬编码：

```python
30000.0 * penetration + 3500.0 * loading
```

R3正式链中该表达式只能存在于V1基线适配器，不能存在于R3预测或MPC代码。

### 3.5 保留完整内部力模块

复用已经通过G1/G5的：

```text
build_planar_grasp_matrix()
decompose_planar_point_forces()
build_radial_grasp_matrix()
decompose_radial_forces()
legacy_q_fr_q_lr()
```

但要重新保存源码hash和测试结果，不能只引用R2通过结论。

## 4. 审计指标修正

### 4.1 高频指标

R2的`hf_energy_above_20hz`实际是总谱能量中的无量纲占比，名称不准确。R3同时报告绝对量和比例。

对V1/R3使用相同长度的共同时间窗，对每个力分量：

1. 去均值；
2. 使用Hann窗；
3. 计算单边PSD，单位\(N^2/Hz\)；
4. 积分：

\[
E_{HF,20}=\int_{20}^{f_s/2}S_F(f)\,df,
\]

单位为\(N^2\)；

5. 同时报告：

\[
R_{HF,20}=\frac{E_{HF,20}}{\int_0^{f_s/2}S_F(f)df}.
\]

必须用合成5 Hz、30 Hz正弦和白噪声做单元测试，并用Parseval关系验证PSD积分与时域方差一致，误差小于1%。

若任一轨迹提前停止，谱比较只使用共同时间窗，并另行报告停止本身；不能将短轨迹全长谱与完整轨迹全长谱直接相比。

### 4.2 三种切换统计

#### 原始几何切换

\[
a^{raw}_i=\mathbf 1(\delta_i>0).
\]

保存所有零穿越次数，只作诊断，不单独作为抖振门。

#### 有效载荷切换

固定门槛：

\[
a^{load}_i=\mathbf 1(F_{N,i}\ge50\ \mathrm N).
\]

50 N在看R3结果前冻结；另报告25/100 N敏感性，但不得用于改门。

#### 驻留过滤切换

只有新状态持续不少于

\[
T_{dwell}=20\ \mathrm{ms}
\]

才计为一次有效切换。正式抖振门使用50 N加20 ms驻留的有效切换，同时并列展示原始几何切换。

### 4.3 力幅公平性

每个工况分别计算：

```text
peak-force ratio
RMS-force ratio
force-impulse ratio
internal-force RMS/peak ratio
payload-wrench RMS/peak ratio
```

禁止只在100 m汇总，也禁止将四点平均掩盖单点超载。

## 5. R3测试与植物验收

## R1：解析合同门

新增测试：

```text
connector_r3/tests/test_r1_contract.py
```

必须通过：

1. 间隙内力严格为零；
2. `delta -> 0+`时力趋于零；
3. `g(0)=0, g(delta_s)=1`；
4. `g'(0)=g'(delta_s)=0`；
5. `g`在\([0,\delta_s]\)单调且位于\([0,1]\)；
6. 对所有测试穿透，`vn=0`时R3与V1弹性力逐元素一致；
7. `delta >= delta_s, vn>0`时R3与V1总力逐元素一致；
8. 卸载阶段R3与V1均无阻尼力；
9. 四方向、旋转、镜像正确；
10. 作用--反作用残差为数值零；
11. 弹性势能、阻尼耗散非负；
12. 内力零空间和重构门重新通过；
13. `Q_FR/Q_LR`历史定义保持一致。

任一失败立即停止。

## R2：单连接器动态门

新增：

```text
connector_r3/tests/test_r2_single_connector.py
```

工况：

- 间隙内匀速；
- 0.01、0.05、0.25、1.0 m/s接触建立；
- 加载--卸载；
- 无阻尼自由振动；
- `delta_s`上下边界；
- 四方向镜像；
- 额定/极限阈值数值扫查。

硬门：

- 接触起力无有限跳变；
- 相同速度下，R3首次2 ms力步长至少比V1下降50%；
- `delta >= delta_s`后的R3/V1力误差小于浮点容差；
- 无阻尼能量漂移小于0.5%；
- 有阻尼总能量无持续增长；
- 重复hash相同；
- 无NaN/Inf；
- 不出现负法向力。

## R3：步长收敛门

比较：

```text
dt = 2.0 ms
dt = 1.0 ms
dt = 0.5 ms
```

必须包含两组：

1. 常规载荷，峰值约200--500 N；
2. 高载荷数值扫查，单连接器至少覆盖2、8、12、14 kN附近；四车集成至少覆盖V1验收域约2 kN。

高载荷只验证数值收敛，不解释为实物可承受。

以0.5 ms为参考：

- 峰值力差不超过5%；
- 冲量差不超过2%；
- 尺度化末状态差不超过1%；
- 接触建立时刻差不超过一个2 ms子步；
- 内力峰值差不超过5%；
- 无非有限值。

## R4：V1/R3成对植物门

使用相同初值、相同控制、相同积分步长：

```text
staged_100m：左向
single_lane_change：左/右
hairpin：左/右
connector_directional：纵向/横向/对角
```

100 m工况固定：

1. 前30 m，\(a_x=0.35\ \mathrm{m/s^2}\)；
2. 30 m后匀速；
3. 5 s正阶跃转向；
4. 5 s反阶跃转向；
5. 剩余距离闭合减速，绝对值不超过0.45 m/s²。

记录500 Hz原始量，50 Hz仅用于常规图。

### R4硬门

1. 最大2 ms接触起力跳下降至少50%；
2. 每个工况R3/V1 RMS力比位于`[0.80,1.25]`；
3. 每个工况R3/V1冲量比位于`[0.80,1.25]`；
4. 每个工况峰值力比位于`[0.50,1.50]`；
5. 20 Hz以上绝对PSD积分不得增加；
6. 50 N+20 ms有效载荷切换不得增加超过10%加1次；
7. 原始几何切换完整报告但不作为单独否决；
8. 100 m距离不少于99.9 m；
9. 所有状态有限；
10. 轮胎利用率不得比V1增加超过0.02绝对值；
11. 不触发15 kN数值停止边界；
12. 完整内部力RMS不得增加超过25%；
13. 作用--反作用、内力零空间残差通过。

门槛已在R3结果生成前冻结；不得看到结果后修改。

## R5：方向与完整内力门

必须通过：

- 左右弯四点力严格镜像；
- 货物横向合力和合力矩随弯向反转；
- `G @ f_internal`满足容差；
- 完整内力能够展示`Q_FR/Q_LR`漏检样本；
- 径向4标量内力与8维自由点力内力分开报告；
- 合力方向、局部连接方向和内力方向不得混为一个角度指标。

R1--R5全部通过后才冻结R3植物。

## 6. R3结果图与审计文件

必须生成：

```text
01_v1_r3_contact_onset.png
02_smoothing_weight_and_force.png
03_static_force_global_equivalence.png
04_energy_and_dissipation.png
05_dt_convergence_normal_highload.png
06_100m_four_point_force.png
07_100m_force_directions.png
08_vehicle_payload_system_yaw.png
09_q_vs_complete_internal_force.png
10_psd_absolute_and_fraction.png
11_raw_vs_effective_switches.png
12_scenario_force_equivalence.png
```

对应CSV/JSON必须保存原始数值，不得只交图片。

输出机器状态：

```text
connector_r3_results/stage_status.json
```

只有R1--R5全部通过时，状态才允许写为：

```text
PLANT_R3_FROZEN_READY_FOR_D0
```

## 7. 新数据生成

### 7.1 旧数据边界

V1的416族数据、R1/R2轨迹和旧MPC全部保持只读：

- V1数据可作旧植物基线；
- R2数据只作失败本构证据；
- 禁止与R3样本混合训练正式模型；
- 旧Koopman在R3植物上只能称模型失配诊断。

### 7.2 D0 Pilot

R1--R5通过后，先生成32个独立基础族：

| 工况 | 基础族 |
|---|---:|
| staged_100m | 8 |
| single_lane_change | 8 |
| hairpin | 8 |
| connector_directional | 8 |

参数随机化：

```text
payload mass scale       [0.97,1.03]
vehicle mu scale         [0.96,1.04]
connector k scale        [0.92,1.08]
connector c scale        [0.92,1.08]
free-play scale          [0.92,1.08]
smoothing-width scale    固定1.0，不在首批正式数据随机化
```

首批不随机化`delta_s`，避免把尚未验证的正则化宽度不确定性与主模型可学习性混在一起。参数普适性另立扩展实验。

Pilot必须检查：

- 每条轨迹有限；
- 100 m距离门；
- 接触/非接触比例；
- 接触建立/脱离事件；
- 原始与有效切换；
- 四点Fx/Fy正负和方向反转；
- 内部力模式；
- 高受力独立轨迹数量；
- 极限事件；
- 500 Hz和50 Hz字段对齐；
- 相同seed重复hash。

Pilot失败即停止，不生成正式数据。

### 7.3 正式数据

| Split | 基础族 | 每工况 | 访问用途 |
|---|---:|---:|---|
| train | 256 | 64 | 模型拟合 |
| validation | 96 | 24 | 结构/超参数选择 |
| development | 64 | 16 | 预注册失败诊断 |
| confirm | 96 | 24 | 一次性盲确认 |

生成顺序：

1. 扫描整个`revision_2026`的结构化seed/traj_id；
2. 冻结全新连续seed块和hash；
3. 生成train；
4. train审计通过后生成validation；
5. 模型结构冻结后才允许读取development；
6. development全门通过后才生成confirm；
7. confirm只执行一次。

左右镜像只能作为解析增广，不计入独立基础族数量。

### 7.4 数据字段

保留：

```text
state30, state46, control
connector_disp, connector_vel
force_payload, force_vehicle
q, payload_yaw, system_yaw, time_s
initial_state64, control64, metadata_json
```

新增：

```text
penetration[time,4]
normal_speed[time,4]
smoothing_weight[time,4]
elastic_force[time,4]
damping_force[time,4]
raw_force_norm[time,4]
elastic_energy[time,4]
damping_power[time,4]
contact_active_raw[time,4]
load_active_50n[time,4]
force_rate_payload[time,4,2]
generalized_payload_wrench[time,3]
internal_force_vector[time,8]
internal_force_norm[time]
motion_force_vector[time,8]
radial_internal_coordinate[time,*]
grasp_rank, grasp_condition
limit_flags[time,4]
```

元数据必须有：

```text
plant_law_version = plant_r3_boundary_regularized
delta_s_source/hash
formula_hash
code_hash
schema_version
parameter_units
seed/split/scenario/base_family_id
plant_dt/log_dt
development_read/confirm_read
```

## 8. Koopman重训实验

### 8.1 先验证目标是否更可学习

用相同IC、控制、seed、轨迹族数量分别生成V1/R3成对样本。比较目标本身：

- `p95/p99 |Delta F|`；
- 接触事件窗`[-0.2,+0.5] s`的力变化；
- 5/20 Hz以上绝对PSD；
- 局部Lipschitz代理；
- 同状态近邻的下一步力方差；
- 原始/有效接触模式复杂度。

只有目标粗糙度下降且真实力幅保持等效，才进入“更易学习”的模型比较。

### 8.2 同结构消融

使用相同训练预算比较：

```text
fixed linear Koopman
fixed lifted Koopman
bilinear Koopman
three-expert gated Koopman
当前冻结的最优候选
```

统一：

- 46维状态合同；
- 20步未来控制；
- train/validation族数；
- 参数预算；
- epoch、优化器和seed；
- 归一化只用各自train；
- bootstrap和统计门；
- 推理硬件和计时方法。

### 8.3 指标

报告1、5、10、15、20步：

```text
state_core NRMSE
connector displacement/velocity NRMSE
four-point force NRMSE and MAE(N)
complete internal-force NRMSE and MAE(N)
legacy Q error
force direction accuracy
contact/load-mode accuracy
force-rate error
peak-force error
transition-window error
divergence rate
runtime p50/p95/p99
```

### 8.4 声明R3改善Koopman的门

盲confirm同时满足：

1. 10--20步四点力NRMSE改善至少8%，配对95% CI下界大于0；
2. 接触事件窗力MAE改善至少15%；
3. 10--20步核心状态不得恶化超过3%；
4. 完整内部力MAE不得恶化超过5%；
5. 发散率不得增加；
6. 四类工况中至少三类方向一致；
7. 同时报告绝对N误差，排除幅值缩小；
8. 推理p99满足控制周期。

若只改善受力，结论限于“连接力目标可学习性提高”；只有状态和受力均改善才可称“耦合系统多步预测改善”。

## 9. MPC恢复

### 9.1 前置门

只有以下全部成立才恢复MPC：

- R1--R5植物门通过；
- D0和正式数据审计通过；
- Koopman validation/development/confirm通过；
- R3唯一物理受力头冻结；
- 46维模型无关MPC适配器完成；
- 权重、约束、求解预算和fallback冻结。

### 9.2 受力代价

\[
J=J_{track}
+\lambda_uJ_u
+\lambda_{\Delta u}J_{\Delta u}
+\lambda_F\sum_i\|\boldsymbol F_i\|^2
+\lambda_{int}\|\boldsymbol f_{internal}\|^2
+\lambda_{\Delta F}\|\Delta\boldsymbol f\|^2.
\]

完整内部力用于正式代价，`Q_FR/Q_LR`只作解释和历史兼容。

### 9.3 约束

```text
四点连接力软/硬约束
完整内部力约束
连接力变化率约束
转角/转角速率
加速度/加加速度
轮胎利用率
路径和终端距离
```

12/15 kN没有实物来源时只能作为数值保护，不得写成已验证安全边界。所有候选模型使用相同约束和slack。

### 9.4 闭环顺序

1. clean staged-100m；
2. clean单移线；
3. clean回头弯；
4. 正常条件下统一MPC比较；
5. 通信延迟与丢包；
6. 持续通信扰动；
7. DoS攻击；
8. 执行器与网络联合扰动。

clean闭环未通过前不得进入网络实验。

## 10. 失败情形和解决方案

### F1：`delta_s`冻结条件失败

说明V1 train的50 Hz保存状态无法可靠恢复植物级接触建立，或事件覆盖不足。解决：用`initial_state64/control64`精确500 Hz回放；仍失败则补独立train-only校准工况。禁止人工指定一个能通过C4的宽度。

### F2：R3仍出现大幅力放大

先检查是否误用了R2的`K/CH/n`、是否多处公式未替换、坐标系和参数对象是否混用。因为R3静态力严格等于V1，若静态大幅放大，属于实现错误而不是模型差异。

### F3：起力跳没有下降50%

检查植物子步分辨率和`delta_s`事件分位。不得读C4调宽度；应回到train-only事件分布，检查极端接触速度是否超出覆盖。若物理上必须瞬时硬接触，停止“平滑力”路线并改用冲量接触模型。

### F4：原始几何切换增加但有效载荷切换不增加

按预注册规则：原始切换只作边界诊断，50 N+20 ms有效切换用于抖振门。不得隐藏原始次数，也不得把无载荷零穿越直接称为结构抖振。

### F5：高频绝对PSD增加、比例下降

这表示总力幅或低频能量改变掩盖了高频绝对增长。以绝对PSD门为主，比例只辅助。检查共同时间窗和窗函数，不能选择性截窗。

### F6：植物通过但Pilot覆盖不足

增加独立基础轨迹，优先增加`connector_directional`和转向换向，不增加重叠窗口或解析镜像计数。

### F7：Koopman目标更平滑但预测未改善

说明主要瓶颈不是接触力跳，而是锚点相对几何、核心状态误差传播或固定算子平均。按既定顺序检查lifted、bilinear和三专家；离线门失败则停止，不进入MPC。

### F8：MPC不可行率升高

检查单位、归一化、力约束与预测误差；使用所有方法共享的slack。禁止只放宽某个Koopman候选的安全约束。

### F9：获得实物数据且否定当前假设

停止R3物理表述。若实物具有预紧、双向衬套、切向摩擦、扭转或三维载荷，另立连接器R4物理模型，不将R3数值等效结果冒充实物验证。

## 11. 执行任务树

```text
R0 冻结协议与R1/R2只读边界
├─ 扫描正在运行的旧进程
├─ 保存源码/结果hash
└─ train-only回放冻结delta_s
   └─ 失败：停止，写solutions.md

R1 唯一公式与解析合同
├─ connector_r3.py
├─ schema和参数单位
├─ 内力模块回归
└─ G-R1
   └─ 失败：停止

R2 单连接器动态
├─ 起力/卸载/能量/方向
├─ V1全域等效
└─ G-R2
   └─ 失败：停止

R3 步长收敛
├─ 常规载荷
├─ 单连接器2/8/12/14 kN数值扫查
├─ 四车约2 kN验收域
└─ G-R3
   └─ 失败：停止

R4 成对全车工况
├─ staged-100m
├─ single-lane-change L/R
├─ hairpin L/R
├─ connector-directional
├─ 绝对PSD/比例PSD
├─ 原始/有效/驻留切换
└─ G-R4
   └─ 失败：停止

R5 完整内力与弯向
└─ G-R5
   └─ 失败：停止

D0 32族Pilot
└─ 覆盖门失败：停止

D1 train/validation正式生成
├─ 数据审计
└─ 模型与协议冻结

K0 V1/R3目标可学习性
K1 同结构Koopman消融
K2 validation
K3 development
K4 blind confirm一次
└─ 任一硬门失败：不进入MPC

M0 46维模型无关MPC冻结
M1 clean 100m
M2 clean单移线
M3 clean回头弯
└─ 全部通过后
   ├─ M4 delay/loss
   ├─ M5 communication disturbance
   ├─ M6 DoS
   └─ M7 network+actuator
```

## 12. 留痕与停止要求

每个阶段完成后立即追加：

```text
connector_r3_results/work_log.md
```

每条记录包括：

- 时间和阶段；
- 修改文件；
- 修改前后hash；
- 执行命令；
- 输入manifest和seed；
- 输出路径；
- 关键数值；
- 门禁状态；
- development/confirm访问状态；
- 下一允许动作。

任一必要证据无法生成或硬门失败，立即停止并写：

```text
connector_r3_results/solutions.md
```

必须区分：

1. 已核实事实；
2. 推测原因；
3. 尚未排除原因；
4. 可执行方案；
5. 风险和成本；
6. 恢复条件。

## 13. 允许的最终结论

按最终通过阶段限制表述：

- 只通过植物门：R3消除了阻尼接入导致的接触边界有限力跳，并保持V1全域静态刚度；
- 通过Koopman受力门：R3改善了连接力过渡目标的多步可学习性；
- 状态与受力均通过：改善四车--货物耦合系统多步预测；
- MPC也通过：在同一R3植物、同一MPC下改善跟踪、内部力或安全指标；
- 任一阶段失败：保留负结果和适用边界，不跨阶段宣称收益。

无论结果如何，当前没有实物数据，因此不得声明R3是实物连接器的唯一正确本构，也不得用四点载荷直接声明货物发生或不会发生材料撕裂。

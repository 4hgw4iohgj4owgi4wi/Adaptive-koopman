# 连接器R3.2事件感知子步实验执行书

> 日期：2026-08-25  
> 目标机器：5080，`DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前前置状态：`BLOCKED_R3_1_PLANT_STEP_RESOLUTION`  
> 本文件属性：新实验预注册任务书；执行前必须复制到5080并冻结SHA256  
> 本轮边界：只写执行书和本地留痕，不修改5080源码，不启动实验。

## 0. 为什么开展R3.2

### 0.1 已冻结事实

R3.1已经证明：

1. R3连接力公式在高分辨率单连接器试验中满足边界连续、静态V1等效和非负耗散；
2. 修复后的R2.1全部通过；
3. 训练接触速度Q99为

   \[
   v_{Q99}=0.2006325727\ \mathrm{m/s};
   \]

4. 当前平滑宽度为

   \[
   \delta_s=0.177617030506\ \mathrm{mm};
   \]

5. Q99对应名义平滑时间

   \[
   \tau_{Q99}=\frac{\delta_s}{v_{Q99}}
   =0.885285\ \mathrm{ms}<2\ \mathrm{ms};
   \]

6. 固定2 ms植物网格在Q99处的平滑区节点中位数为0；
7. 2 ms相对0.1 ms参考的冲量误差：

```text
Q99          3.085%
0.25 m/s     3.433%
1.0 m/s      4.464%
```

均超过原2%门；
8. 因此前置门失败，四车、数据、Koopman和MPC均未运行。

### 0.2 当前问题的性质

当前问题不是R3连续公式被证明错误，而是：

> 连续时间边界层短于正式离散积分步长，导致固定2 ms RK4可能一步跨过接触建立和平滑区。

因此下一步必须先解决数值积分可解析性，再判断R3是否真的改善整车受力和Koopman数据。

### 0.3 三个必须分开的假设

R3.2不得把以下三件事混成一个结论。

#### H1：积分器假设

事件感知子步可以在保持外部2 ms控制时钟的同时，把高速接触的峰值、冲量和末状态误差降到门槛内。

#### H2：连接力律假设

在V1和R3使用同一事件子步积分器后，R3仍能降低接触起力跳、高频绝对能量或有效切换，同时不显著改变RMS、冲量、车辆横摆和完整内部力。

#### H3：可学习性假设

在物理植物和控制轨迹公平的条件下，R3或事件级特征能提高相同Koopman结构的多步预测性能。

只有H1、H2、H3依次成立，才能写成“R3连接器改进最终提高Koopman预测”。

如果仅H1成立，结论只能是“数值积分更准确”；如果仅事件特征改善预测，结论应归因于“事件感知表示”，不能归因于R3力律。

## 1. 版本隔离和只读边界

### 1.1 新目录

5080只允许新增：

```text
revision_2026/connector_r3_2/
revision_2026/connector_r3_2_results/
revision_2026/connector_r3_2_data/
revision_2026/connector_r3_2_models/
revision_2026/connector_r3_2_mpc/
```

禁止覆盖：

```text
revision_2026/model/
revision_2026/connector_v2/
revision_2026/connector_v2_results/
revision_2026/connector_r3/
revision_2026/connector_r3_results/
revision_2026/connector_r3_1/
revision_2026/connector_r3_1_results/
revision_2026/koopman/frozen/
```

### 1.2 执行前源文件身份

N0必须在5080重新计算，当前现场核实值为：

| 来源 | SHA256 |
|---|---|
| `connector_r3_1/src/connector_r3.py` | `0BD16C4D...310459` |
| `connector_r3_1/src/schema_r3.py` | `BFF45EF3...0A6D562` |
| `connector_v2/src/internal_force.py` | `0A00D298...C28C0` |
| `connector_v2/src/four_vehicle_v2.py` | `7FFC9514...57685` |
| `connector_v2/src/paired_maneuvers.py` | `5C41BD4D...A91E4` |

若现场哈希变化，停止并输出diff，不允许为了匹配本表覆盖5080文件。

### 1.3 数据访问

在植物门N0--N5期间：

- 允许读取R3/R3.1的train-only事件表、冻结参数、历史结果；
- 允许读取冻结V1控制生成器和四车植物源码；
- 禁止读取Koopman development和confirm预测结果；
- 禁止用R4、Koopman或MPC结果反向调`delta_s`、子步参数或门槛。

## 2. R3.2的唯一方法改动

### 2.1 保持不变的物理力律

R3连接力保持：

\[
\delta_i=[\|d_i\|-l_0]_+,
\qquad
v_{n,i}=v_i^\top n_i,
\]

\[
F_{N,i}^{R3}
=k\delta_i+c\,g(\delta_i)[v_{n,i}]_+,
\]

\[
g(\delta)=
\begin{cases}
0,&\delta\le0,\\
3s^2-2s^3,&0<\delta<\delta_s,\\
1,&\delta\ge\delta_s,
\end{cases}
\qquad s=\delta/\delta_s.
\]

以下参数全部冻结：

```text
k = 30000 N/m
c = 3500 N*s/m
l0 = 0.002 m
delta_s = 0.0001776170305060031 m
12/15 kN = 未验证数值诊断/停止阈值
```

### 2.2 外部时钟与内部子步

外部植物/控制时钟保持

\[
H=2\ \mathrm{ms}.
\]

在每个`[t_k,t_k+H]`内保持控制`u_k`不变，只对积分器内部进行事件探测和局部子步。

外部状态仍定义为

\[
x_{k+1}=\Phi_H(x_k,u_k),
\]

但`Phi_H`由若干内部步组成：

\[
H=\sum_{j=1}^{N_k}h_{k,j}.
\]

必须满足

\[
\left|\sum_jh_{k,j}-H\right|<10^{-12}\ \mathrm{s}.
\]

### 2.3 事件面

不能只使用裁剪后的`penetration_m`探测事件，必须保留有符号几何间隙：

\[
q_i=\|d_i\|-l_0.
\]

对每个连接点定义两个事件面：

\[
\phi_i^{(0)}=q_i,
\qquad
\phi_i^{(1)}=q_i-\delta_s.
\]

含义：

- `phi0=0`：进入或退出接触；
- `phi1=0`：进入或退出完整V1阻尼区。

加载、卸载两个方向都必须探测，不能只处理`vn>0`。

### 2.4 事件定位

每个外部步执行：

1. 最大探测步`h_probe=0.5 ms`；
2. 对探测区间起点、中点和终点计算所有`phi0/phi1`；
3. 发现符号变化时，对每个候选事件进行二分定位；
4. 选择全体连接点中最早事件；
5. 事件时间容差：`1 us`；
6. 几何面容差：`1e-8 m`；
7. 多连接点同时事件时间差不超过`1 us`时，作为同一事件组记录；
8. 事件检测器可以使用`1e-9 m`释放容差避免重复报告，但不得修改物理穿透或连接力。

如果起点和终点同号但中点异号，必须识别为区间内双穿越风险，继续细分；不允许只看端点漏掉短接触。

### 2.5 平滑区内部步长

当任一连接点位于`0<q_i<delta_s`，或预计当前探测步将穿越平滑区时：

\[
h_{zone}
=\min\left(
h_{probe},
\frac{\delta_s}{N_{zone}\max_i(|v_{n,i}|,v_{floor})}
\right),
\]

预注册：

```text
N_zone = 8
v_floor = 1e-4 m/s
h_probe = 0.5 ms
h_min = 2 us
max_substeps_per_outer_step = 256
```

若理论需要的`h_zone<h_min`，停止并标记`UNRESOLVED_EVENT_SPEED`，不得静默裁剪到`h_min`后继续声称已解析。

### 2.6 子步状态积分和区间积分

每个接受的内部区间使用两个半步RK4推进，并在区间中点计算诊断量。区间冲量采用中点积分：

\[
J_{i,k}=\sum_j F_{i,k,j+1/2}h_{k,j}.
\]

阻尼耗散：

\[
W_{d,i,k}=\sum_jP_{d,i,k,j+1/2}h_{k,j}.
\]

使用中点而不是在V1接触不连续点直接做端点梯形，避免把`delta=0`的左极限与接触后的右极限平均。固定高分辨率参考也必须采用一致的区间积分定义。

### 2.7 每个2 ms周期的事件特征

必须保存：

```text
state_endpoint[30]
control[4,2]
force_endpoint_world[4,2]
force_endpoint_body[4,2]
force_mean_world[4,2] = impulse_world/H
force_peak_norm[4]
force_impulse_world[4,2]
force_impulse_norm[4]
damping_work[4]
contact_fraction[4]
smoothing_fraction[4]
g_min/g_mean/g_max[4]
delta_min/delta_max[4]
contact_on_count/contact_off_count[4]
smoothing_in_count/smoothing_out_count[4]
substep_count
min_substep_s/max_substep_s
event_time_offsets_s
event_connector_ids
solver_status
```

对学习数据，时刻`k`可用的事件特征只能来自已经完成的区间`(t_{k-1},t_k]`：

\[
e_k=\mathcal E(t_{k-1},t_k].
\]

禁止把`(t_k,t_{k+1]}`内的未来峰值、冲量或接触事件作为预测`x_{k+1}`的输入，否则构成目标泄漏。

## 3. 必须使用四组合因子实验

只比较“旧V1固定步”与“R3事件子步”会把积分器和力律混在一起。必须同时运行：

| 编号 | 力律 | 积分器 | 用途 |
|---|---|---|---|
| V1-F2 | V1 | 固定2 ms | 历史上下文 |
| V1-ES | V1 | 2 ms外时钟+事件子步 | 公平V1基线 |
| R3-F2 | R3 | 固定2 ms | 暴露当前离散缺陷 |
| R3-ES | R3 | 2 ms外时钟+事件子步 | 新候选 |

主力律效应必须比较：

\[
\Delta_{law}^{ES}=M(R3\text{-}ES)-M(V1\text{-}ES).
\]

积分器效应分别为：

\[
\Delta_{int}^{V1}=M(V1\text{-}ES)-M(V1\text{-}F2),
\]

\[
\Delta_{int}^{R3}=M(R3\text{-}ES)-M(R3\text{-}F2).
\]

交互项：

\[
\Delta_{interaction}
=M(R3\text{-}ES)-M(R3\text{-}F2)
-M(V1\text{-}ES)+M(V1\text{-}F2).
\]

如果只有`V1-ES`就已获得全部收益，论文创新应转向事件积分/事件表示，不能继续声称R3力律是主要原因。

## 4. 代码修改清单

### 4.1 新源码树

```text
connector_r3_2/
├─ protocol.md
├─ README.md
├─ src/
│  ├─ connector_r3.py
│  ├─ connector_v1.py
│  ├─ schema_r3.py
│  ├─ internal_force.py
│  ├─ connector_adapter.py
│  ├─ four_vehicle_common.py
│  ├─ event_substep.py
│  ├─ step_features.py
│  ├─ paired_maneuvers_r3.py
│  └─ spectral_metrics.py
├─ tests/
│  ├─ test_n1_event_detector.py
│  ├─ test_n2_single_connector_factorial.py
│  ├─ test_n3_four_vehicle_convergence.py
│  ├─ test_n4_paired_plant.py
│  ├─ test_n5_direction_internal.py
│  └─ test_n6_data_contract.py
└─ scripts/
   ├─ freeze_inputs.py
   ├─ run.py
   ├─ plot_evidence.py
   ├─ build_pilot.py
   ├─ train_compare.py
   └─ finalize_report.py
```

### 4.2 `connector_r3.py`

直接复制R3.1文件，执行初始SHA256检查；不改公式。

### 4.3 `connector_v1.py`

实现独立V1适配器：

\[
F_N^{V1}=k\delta+c[v_n]_+.
\]

它与R3共享几何量、力方向和数值阈值，只用于四因子公平比较。必须回归到冻结`revision_2026/model/four_vehicle_coupled.py`，同一状态/控制下逐元素一致。

### 4.4 `four_vehicle_common.py`

从已核实的`connector_v2/src/four_vehicle_v2.py`复制车辆、货物、轮胎、30维状态和四点力矩结构，改为通过`connector_adapter`注入力律。

必须保留：

- 四车每车6维、货物6维，共30维；
- 连接力对车辆和货物的作用--反作用；
- 车辆连接点力矩；
- 货物四点力矩；
- 轮胎利用率；
- 完整内力SVD分解。

新增：

```python
signed_connector_gaps(state, params) -> ndarray[4]
connector_event_surfaces(state, params) -> ndarray[4,2]
system_derivative(state, controls, params, law) -> (dx, aux)
fixed_rk4_step(state, controls, dt, params, law) -> state_next
```

### 4.5 `event_substep.py`

核心接口：

```python
@dataclass(frozen=True)
class EventSolverConfig:
    outer_dt_s: float = 0.002
    probe_dt_s: float = 0.0005
    zone_nodes: int = 8
    min_dt_s: float = 2e-6
    event_time_tol_s: float = 1e-6
    surface_tol_m: float = 1e-8
    detector_release_tol_m: float = 1e-9
    max_substeps: int = 256

def advance_outer_step(
    state, controls, params, law, config
) -> tuple[state_next, StepAudit]:
    ...
```

`StepAudit`必须包含2.7节全部字段和确定性哈希输入。

### 4.6 `step_features.py`

只负责把子步审计聚合到外部2 ms周期。禁止在此重复计算另一套连接力公式。

### 4.7 `spectral_metrics.py`

现有`paired_maneuvers.py`的高频指标存在两个问题：未加窗、只给高频占总能量比例。新实现必须：

- 使用共同时间窗；
- 去均值；
- Hann窗；
- 50%重叠；
- 输出PSD密度`N^2/Hz`；
- 用数值积分输出20 Hz以上绝对PSD；
- 同时输出无量纲占比；
- Parseval相对误差不超过2%。

若5080缺少SciPy，使用NumPy实现固定Welch，不允许临时联网安装后不记录环境变化。

### 4.8 `paired_maneuvers_r3.py`

不能修改旧`paired_maneuvers.py`。新文件应：

- 用冻结V1控制生成器生成一次控制序列；
- 四个候选复用完全相同的初态、控制、参数和停止规则；
- 主比较使用`V1-ES`与`R3-ES`；
- 保存端点力和区间冲量/峰值；
- 新增`connector_directional`工况；
- 在N0先审计`steering_allocator`和`generate_k2.nominal_command`的单位及接口。若单位无法从源码/文档确定，停止，不得猜测“4”代表角度、角速度或横摆率。

## 5. 顺序任务树

```text
N0 冻结R3.1与代码映射
├─ 现场进程/磁盘/解释器检查
├─ 源码与结果SHA256
├─ 修正报告分位配对说明
├─ 控制生成器单位审计
└─ 失败：停止

N1 事件探测器和聚合器单元测试
├─ 两个事件面
├─ 加载/卸载
├─ 同时事件
├─ 双穿越
├─ 区间时间守恒
└─ 失败：停止

N2 单连接器四因子收敛
├─ Q05/Q50/Q95/Q99
├─ 0.25/1.0 m/s压力测试
├─ 32接触相位
├─ 2 us参考
└─ 失败：停止

N3 四车代表载荷收敛
├─ 四个力律/积分组合
├─ 2/1/0.5 ms外时钟与0.1 ms参考
├─ 作用反作用/力矩/内力
└─ 失败：停止

N4 成对整车工况
├─ staged_100m
├─ single_lane_change
├─ hairpin
├─ connector_directional
└─ 物理公平或平滑收益失败：停止R3力律路线

N5 四点方向与撕裂型内力
└─ 方向/零空间/单车力矩失败：停止

N6 数据可学习性Pilot
├─ 32条成对轨迹
├─ 500 Hz和学习采样率粗糙度
├─ 端点特征/事件特征消融
└─ 无可观察信号：停止，不生成正式数据

N7 正式数据
├─ train 256
├─ validation 96
├─ locked development 64
└─ confirm 96保持锁定

N8 Koopman四因子比较
└─ 多步无稳健提升：不得声明预测创新

N9 MPC恢复
└─ 闭环/通讯/DoS逐级执行
```

## 6. N0：冻结和代码审计

### 6.1 检查项

```text
项目根目录存在
E:\anaconda\envs\pytorch_new\python.exe存在
没有正在运行的connector/Koopman/MPC Python进程
connector_r3_2目录不存在或为空的新目录
R3.1 stage_status保持原SHA256
R3.1 development_read=false
R3.1 confirm_read=false
磁盘剩余空间至少20 GB
```

### 6.2 报告表格修正

旧R3.1英文报告的速度分位与平滑时间同名分位配对错误，禁止覆盖旧报告。新建：

```text
connector_r3_2_results/n0/r3_1_report_correction.md
```

按同一速度直接计算`delta_s/v`，并说明R3a逐速度结果不受该排版错误影响。

### 6.3 控制接口审计

输出：

```text
connector_r3_2_results/n0/control_api.json
```

至少记录：

```text
allocate_controls输入/输出shape
命令三元组每个量的名称和单位
steering输出单位
控制限幅
staged_100m控制逻辑
single_lane_change/hairpin/connector_directional入口
相关源码SHA256
```

## 7. N1：事件探测器验收

### 7.1 解析算例

用常速度一维连接器构造已知事件时刻：

\[
t_0=\frac{-q(0)}{v_n},
\qquad
t_1=\frac{\delta_s-q(0)}{v_n}.
\]

覆盖：

- 四个支持速度；
- 0.25和1.0 m/s；
- 加载、卸载；
- 正负x/y四方向；
- 两个和四个连接点同时接触；
- 一个探测步内进入又退出；
- 恰好落在外部步端点；
- 间隙内不接触；
- 平滑区外不误报。

### 7.2 N1硬门

- 事件时间误差不超过`1 us`；
- 事件面残差不超过`1e-8 m`；
- 无漏检和重复死循环；
- 同时事件分组正确；
- 每个外部步时间和误差小于`1e-12 s`；
- 相同输入重复哈希一致；
- `substep_count<=256`；
- 不修改连接力值；
- 无NaN/Inf。

## 8. N2：单连接器四因子收敛

### 8.1 试验矩阵

```text
速度：Q05/Q50/Q95/Q99/0.25/1.0 m/s
相位：32个，均匀覆盖[0,2 ms)
力律：V1/R3
积分器：固定2 ms/事件子步
参考：固定2 us
时长：覆盖接触前、完整平滑区和接触后至少10 ms
```

### 8.2 指标

- 接触时刻；
- 平滑区进入/退出时刻；
- 平滑区内部节点数；
- 峰值力；
- 区间冲量；
- 末端穿透和速度；
- 弹性势能；
- 阻尼耗散；
- R3能量余额；
- 子步数和最小步长；
- 四因子主效应和交互项。

### 8.3 N2硬门

对`V1-ES`和`R3-ES`相对2 us参考：

- 峰值力误差不超过5%；
- 冲量误差不超过2%；
- 末状态尺度化误差不超过1%；
- 接触时刻误差不超过`2 us`；
- R3支持域及压力域每次平滑区至少8个接受子步；
- Q99、0.25和1.0 m/s原失败冲量门全部转为通过；
- R3边界连续和R2.1能量门重新通过；
- V1/R3均无负法向力、无非有限值、无静默力裁剪；
- 若达到15 kN，立即停止该轨迹并保留原始力。

如果事件子步只能让R3通过而V1不通过，先检查V1不连续点的区间积分定义，不能直接把差异算作R3优势。

## 9. N3：四车代表载荷收敛

### 9.1 状态与输入

沿用：

```text
state shape = (30,)
vehicles = 4 x [x,y,yaw,vx,vy,yaw_rate]
payload = [x,y,yaw,vx,vy,yaw_rate]
control shape = (4,2) = [acceleration, steering]
```

### 9.2 代表工况

先复用历史G3的2 s小转向反转工况，再增加一个train Q99接触事件覆盖工况。所有候选使用完全相同的初态和控制。

参考积分：外部控制仍每2 ms更新，参考植物在每个控制周期内部使用`0.1 ms+事件子步`，不得把控制更新频率也改成0.1 ms。

### 9.3 N3硬门

`2 ms+ES`相对参考：

- 四点峰值力误差不超过5%；
- 四点冲量误差不超过2%；
- 末状态尺度化误差不超过1%；
- 完整内部力峰值误差不超过5%；
- 货物合力矩误差不超过5%；
- 每车连接力矩误差不超过5%；
- 作用--反作用残差小于`1e-10 N`；
- 内力零空间残差小于`1e-8*max(1,internal_norm)`；
- 无15 kN停止、NaN/Inf；
- 所有Q99事件均被记录并具有足够子步。

## 10. N4：成对整车工况

### 10.1 控制公平性

每个工况只生成一份冻结控制序列，四个候选逐元素复用。不得让不同植物各自闭环生成不同输入后直接比较模型本体。

### 10.2 工况

#### staged_100m

- 初始速度2 m/s；
- 前30 m加速度使用现有冻结值`0.35 m/s^2`；
- 30 m后保持纵向加速度0；
- 按冻结控制生成器执行5 s正向转向和5 s反向转向；
- 剩余路段减速，目标100 m；
- 转向命令的实际物理单位以N0代码审计为准，不能在任务书中猜测。

#### single_lane_change

左右镜像各一条。

#### hairpin

左右镜像各一条。

#### connector_directional

使用现有`generate_k2`定向工况；如果当前生成器没有稳定公开接口，停止并先建立适配器，不得临时手写一个有利工况代替。

### 10.3 必须记录的动力学

- 每点世界系和货物体坐标系`Fx/Fy`；
- 每点力方向角；
- 每点弹性力、阻尼力、平滑权重；
- 每车连接反力和连接横摆力矩；
- 每车横摆角速度；
- 货物横摆角速度和合横摆力矩；
- 系统角动量定义的整体横摆率；
- 货物左右侧合力；
- 四点完整内部力、运动力和广义载荷；
- 前后/左右张开内力代理和两条对角扭拧模式；
- 轮胎利用率；
- 接触事件、有效载荷事件和驻留事件；
- 子步统计；
- 端点力、周期平均力、周期峰值和冲量。

### 10.4 公平性硬门

主比较为`R3-ES/V1-ES`，每个工况均要求：

```text
RMS力比       [0.80, 1.25]
冲量比        [0.80, 1.25]
峰值力比      [0.50, 1.50]
完整内力RMS   不增加超过25%
轮胎利用率    不超过V1-ES + 0.02
有限性        全部有限
数值极限      不触发15 kN停止
```

100 m额外要求终端距离至少99.9 m。

### 10.5 平滑收益硬门

如果R3被用于支撑“更平滑、更易预测”，必须同时满足：

- 500 Hz最大2 ms接触起力跳相对`V1-ES`下降至少50%；
- 20 Hz以上绝对PSD积分不增加；
- 50 N+20 ms有效载荷切换不增加超过`10%+1`；
- 学习保存率下的`P99(|Delta F|)`至少下降20%；
- 改善不能仅由整体力幅缩小造成，必须通过公平性门。

如果事件子步提高了冲量精度，但R3相对V1-ES没有上述采样可见收益，则H1通过、H2失败：停止“R3改善可学习性”路线。

## 11. N5：方向和撕裂型内力

四点顺序固定为`FL,FR,RL,RR`，货物体坐标力`f_i=[Fxi,Fyi]`。

货物合载荷：

\[
F_P=\sum_i f_i,
\qquad
M_{z,P}=\sum_i(x_iF_{y,i}-y_iF_{x,i}).
\]

左右侧合力：

\[
F_L=f_{FL}+f_{RL},
\qquad
F_R=f_{FR}+f_{RR}.
\]

左右相互拉开的数值代理：

\[
T_{LR}
=\max\left(0,
\frac{F_{L,y}-F_{R,y}}{2}
\right).
\]

前后相互拉开代理：

\[
T_{FR}
=\max\left(0,
\frac{F_{F,x}-F_{Rr,x}}{2}
\right),
\]

其中`F_F=f_FL+f_FR`，`F_Rr=f_RL+f_RR`。

这些代理必须与SVD完整内力向量同时报告，不能用两个Q值代替完整内部力。

N5硬门：

- 作用--反作用逐点成立；
- 每车横摆力矩按本车质心力臂独立计算；
- 货物合力矩与四点重构一致；
- 左右镜像的力方向和内力模式镜像成立；
- 完整内力零空间残差通过；
- 输出`T_LR/T_FR`峰值、RMS、P95和持续时间；
- 没有实物阈值时只称“撕裂型拉伸载荷代理”，不得称“已撕裂”或“安全”。

## 12. N6：可学习性Pilot

### 12.1 Pilot规模

共32个独立基础轨迹：

```text
staged_100m            8
single_lane_change     8
hairpin                 8
connector_directional   8
```

每条基础轨迹同时生成`V1-ES`与`R3-ES`，控制、随机参数和初态成对一致。

### 12.2 数据表示消融

每个植物生成两种输入表示：

```text
E0 endpoint-only
E1 endpoint + previous-step event features
```

形成：

```text
V1-ES/E0
V1-ES/E1
R3-ES/E0
R3-ES/E1
```

这样可以区分：

- R3力律收益；
- 事件特征收益；
- 两者交互收益。

### 12.3 Pilot硬门

- 所有轨迹有限且通过距离/极限门；
- 四工况均有接触建立、卸载、方向变化和内部力样本；
- R3-ES相对V1-ES在学习采样率下存在预注册的粗糙度改善；
- E1不存在未来区间特征泄漏；
- 事件字段缺失率为0；
- 数据schema、单位、law/integrator版本和源码hash齐全。

若R3-ES/E0没有任何采样可见改善，但E1有效，允许另立“事件感知Koopman”路线；不得继续把收益写成R3连接器贡献。

## 13. N7正式数据

建议规模延续冻结设计：

```text
train        256基础轨迹
validation    96基础轨迹
development   64基础轨迹，生成后锁定
confirm       96基础轨迹，模型冻结前不得生成/读取预测
```

解析镜像只能作为增强，不能计为新的独立基础样本。

每个文件至少保存：

```text
plant_law_version
integrator_version
event_solver_config/hash
delta_s_source/hash
scenario/seed/split/base_family_id
state30/control8
四点端点力/平均力/峰值/冲量
四点delta/vn/g
接触占空比与事件计数
单车横摆/货物横摆/系统横摆
完整内部力与T_LR/T_FR
轮胎利用率
单位和shape合同
```

## 14. N8 Koopman实验

### 14.1 相同训练预算

每个数据/表示组合使用相同：

- train/validation划分；
- 窗口；
- 5个随机种子；
- 优化器、epoch上限、早停和参数预算；
- 一步、5步、10步、20步评价；
- development访问次数；
- confirm一次性规则。

### 14.2 模型集合

至少比较：

```text
fixed linear
fixed lifted
bilinear
three-expert gated Koopman
当前冻结最优组合
```

### 14.3 主要指标

- 20步状态NRMSE；
- 20步四点力NRMSE；
- 20步完整内部力NRMSE；
- `T_LR/T_FR`误差；
- 力方向准确率；
- 峰值误差；
- 接触事件时刻误差；
- 发散率；
- 各工况宏平均；
- 计算时间。

### 14.4 声明改进的门

对同一模型结构、同一表示：

\[
G_{20}=1-\frac{J_{20}^{R3-ES}}{J_{20}^{V1-ES}}.
\]

要求：

- 主20步复合指标点改善至少8%；
- 轨迹成对bootstrap 95%置信区间下界大于0；
- 任一关键工况不恶化超过5%；
- 一步性能不恶化超过5%；
- 发散率不增加超过1个百分点；
- 植物层公平性门已通过。

如果只有E1事件特征带来改善，应单独报告表示收益；如果只有某一种Koopman结构有效，应限定优势场景，不能写成普适提升。

## 15. N9 MPC恢复

只有N8冻结模型后才允许恢复MPC。

### 15.1 必须重新适配

- 植物使用R3-ES，不得使用R3-F2；
- 控制器外部时钟保持冻结值；
- 事件特征只使用上一已完成周期；
- 代价同时考虑路径误差、四点力、完整内部力、力变化率；
- 约束考虑周期峰值而不仅是端点力；
- 12/15 kN仍只能作为未验证数值保护。

### 15.2 顺序

```text
正常单移线：AKE-M vs NR-候选
正常回头弯：AKE-M vs NR-候选
通讯延迟/丢包
DoS攻击
```

每一层通过后再进入下一层。新植物下旧MPC数据只能作为历史上下文，不能作为主结果继续使用。

## 16. 图表清单

至少输出：

```text
01_event_surface_timeline.png
02_substep_count_and_dt.png
03_single_connector_impulse_convergence.png
04_v1_r3_fixed_event_factorial.png
05_four_vehicle_dt_convergence.png
06_100m_force_yaw_overview.png
07_four_point_force_directions.png
08_absolute_psd_and_force_jump.png
09_internal_force_and_tearing_proxy.png
10_pilot_roughness.png
11_koopman_horizon_curves.png
12_method_scenario_advantage_map.png
```

所有图必须有对应CSV/JSON，不能只保存图片。

## 17. 失败情形和解决方案

### F1：事件重复触发/死循环

检查事件面容差、释放容差和事件后剩余时间；保留失败轨迹。只能修改探测器数值逻辑，不能给物理穿透加滞回后伪装为解决。

### F2：一个探测步内漏掉进入又退出

启用中点检测并递归二分；仍漏检则把`h_probe`从0.5 ms预注册改为0.25 ms，另立版本并从N1重跑。

### F3：需要步长小于2 us

停止并报告事件速度；不得静默裁剪。如果属于训练支持域，当前显式RK4方案不够，应考虑更强事件积分器。

### F4：子步超过256

停止该外部步，保存状态、事件面、速度和调用栈。检查连接点在边界附近的反复穿越，不能直接提高上限掩盖抖振。

### F5：V1-ES仍不收敛

优先检查V1接触不连续点的一侧积分和冲量定义；使用相同事件时刻分段。若仍失败，V1需作为混杂系统单独处理，不能把失败计为R3优势。

### F6：H1通过但H2失败

说明事件积分提高准确性，但R3在正式采样率下无平滑优势。停止连接力律创新路线；可另立事件感知数据/Koopman路线。

### F7：高频占比下降但绝对PSD上升

判为失败。占比可能因低频能量增加而下降，必须以绝对PSD为主。

### F8：力跳下降但冲量/RMS偏离

判为物理主动力学被改变，不能称无损平滑。检查力律而不是调公平门。

### F9：方向或完整内力失败

检查世界/体坐标变换、连接点顺序和力臂。不得只保留合力图隐藏单点错误。

### F10：事件特征导致预测异常好

首先检查时间索引和未来信息泄漏；把所有特征向后移一周期重新训练。泄漏未排除前结果作废。

### F11：Pilot无可观察改善

停止正式数据生成，避免数百GB级无效计算。分析是采样率、力律还是状态表示原因。

### F12：运行时间过高

分别报告平均、P95、P99和最大子步数/外部步耗时。只能优化缓存、向量化和事件稀疏执行；任何改变数值结果的近似都要重新过N1--N4。

### F13：控制生成器单位不清楚

停止N4，在`control_api.json`中列出缺失信息。不能根据旧图猜单位。

### F14：12/15 kN被误作实物阈值

报告中统一标记`numerical_legacy_unverified`；没有实物来源不得写安全或破断结论。

## 18. 执行命令模板

解释器固定：

```powershell
$python = 'E:\anaconda\envs\pytorch_new\python.exe'
$project = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$source = Join-Path $project 'revision_2026\connector_r3_2'
```

阶段命令预期为：

```powershell
& $python "$source\scripts\run.py" --project-root $project --stage N0
& $python "$source\scripts\run.py" --project-root $project --stage N1
& $python "$source\scripts\run.py" --project-root $project --stage N2
& $python "$source\scripts\run.py" --project-root $project --stage N3
& $python "$source\scripts\run.py" --project-root $project --stage N4
& $python "$source\scripts\run.py" --project-root $project --stage N5
& $python "$source\scripts\run.py" --project-root $project --stage N6
```

`run.py`必须检查上一阶段`complete.json`和源码hash；前置门失败时只写`NOT_RUN`，不得继续。

## 19. 工作留痕

每次代码、参数、阈值、数据或报告变化，必须同时写入：

```text
connector_r3_2_results/work_log.md
D:\PDxc\Review\connector_r3_log.md
```

每条记录包含：

```text
时间/机器/解释器
任务ID
输入文件和SHA256
修改文件和原因
运行命令
事件求解器配置
数据拆分访问情况
输出文件和SHA256
每个硬门结果
失败/停止原因
下一允许动作
```

若对指标实现做审计修正，必须保存修正前源码和结果，记录“模型/数据/阈值是否改变”。

## 20. 最终允许的结论

### 仅N2/N3通过

允许写：事件感知子步解决了R3边界层的数值可解析性和冲量收敛问题。

不允许写：R3改善整车或Koopman。

### N4/N5通过

允许写：在相同事件积分器下，R3在指定整车工况降低了预注册的力跳/高频/有效切换，并保持主动力学与完整内部力公平。

### N6--N8通过

允许写：在明确的数据表示和模型结构下，R3或事件特征改善了多步预测；必须通过四因子分解说明收益来自力律、积分器还是事件表示。

### N9通过

才允许写新植物和新Koopman模型适用于MPC闭环与网络扰动实验。

## 21. 本轮推荐的实际停止点

第一次执行只推进到N2。

原因：当前最核心的不确定性是事件子步能否把Q99、0.25和1.0 m/s的冲量误差降到2%以内，同时对V1和R3公平。如果N2失败，四车和数据生成没有意义。

N2通过后单独复核结果，再决定是否授权N3--N5。这样计算成本最低，也最能防止实验路线继续偏离审稿人关心的“模型是否真实、预测改进是否可归因”。

# 连接器V2修改与数据重建执行书

> 状态：待执行；本文冻结后才能修改植物、生成新数据或恢复MPC实验。  
> 目标：将当前带间隙的线性加载阻尼连接器改为连续起力、无隐藏状态、可校准的平滑非线性连接器；随后重建数据、重训Koopman，并在离线预测通过后恢复MPC。  
> 证据边界：已经停止的MPC批次属于`plant_v1_linear_gated`，只能作为旧植物基线，不能并入V2正式结论。

## 0. 先核实的前提

### 0.1 当前已知事实

当前四车植物位于：

```text
D:\PDxc\Review\_epd_impl\reference\four_vehicle_coupled.py
```

四点连接器采用相同的二维径向间隙本构。令车辆锚点到货物锚点的相对位移为

\[
\boldsymbol d_i=\boldsymbol p_{v,i}-\boldsymbol p_{L,i},
\qquad
r_i=\|\boldsymbol d_i\|,
\qquad
\boldsymbol n_i=\frac{\boldsymbol d_i}{r_i},
\]

当前穿透量和法向相对速度为

\[
\delta_i=[r_i-l_0]_+,
\qquad
v_{n,i}=\dot{\boldsymbol d}_i^\top\boldsymbol n_i=\dot\delta_i.
\]

旧公式为

\[
F_{N,i}^{\mathrm{V1}}=
\begin{cases}
0,&\delta_i=0,\\
k\delta_i+c[v_{n,i}]_+,&\delta_i>0.
\end{cases}
\]

当前标称参数为：

```text
k       = 30000 N/m
c       = 3500 N*s/m
l0      = 0.002 m
rated   = 12000 N
ultimate= 15000 N
plant_dt= 0.002 s
log_dt  = 0.02 s
```

当前V1公式在`delta -> 0+`且`vn > 0`时满足

\[
\lim_{\delta\to0^+}F_N=cv_n\ne0,
\]

所以连接建立瞬间存在有限力突跳。现有一条61.86 s轨迹经500 Hz回放得到：每点15--27次接触状态切换，仅一次状态驻留不超过20 ms，5 Hz以上连接力能量约0.42%--0.82%，但2 ms内最大力跳约925 N。该轨迹不能证明所有工况均无抖振，只能说明当前温和样本没有持续高频抖振，同时确实存在边界力突跳。

### 0.2 尚未证实的物理前提

执行C1前必须冻结以下结论；任一项无法确定时，记录为建模假设，不得写成实物事实：

1. 实物是销套间隙接触、柔性拉带，还是双向机械衬套；
2. 是否存在预紧；
3. 是否只能传递径向力；
4. 是否存在切向摩擦；
5. 是否限制相对横摆；
6. 文中“垂向力”是车辆平面横向\(y\)力，还是重力方向\(z\)力；
7. 额定力、极限力、最大工作位移和失效位移的实物来源；
8. 是否有实测静态力--位移曲线、自由衰减或碰撞恢复系数。

本文默认V2第一阶段仍采用“二维、径向、带间隙、无切向摩擦、相对横摆自由”的销套等效模型。若上述实物前提与此不一致，停止V2实现，另立双向衬套或三维连接器任务书。

## 1. V2规范公式

### 1.1 主公式

V2采用无隐藏事件状态的Hunt--Crossley型连续接触公式：

\[
\delta_i=[r_i-l_0]_+,
\]

\[
Y_i=K\delta_i^n+C_H\delta_i^n v_{n,i},
\]

\[
F_{N,i}^{\mathrm{V2}}=[Y_i]_+,
\qquad
\boldsymbol F_{L,i}=F_{N,i}^{\mathrm{V2}}\boldsymbol n_i,
\qquad
\boldsymbol F_{v,i}=-\boldsymbol F_{L,i}.
\]

其中：

- `K`单位为\(\mathrm{N/m^n}\)；
- `C_H`单位为\(\mathrm{N\,s/m^{n+1}}\)；
- `n`为接触指数，销套共形接触不能未经论证直接套用Hertz球接触指数；
- `C_H`为固定、可辨识参数，不在每次接触时读取未来或重新估计初始撞击速度；
- `[Y]_+`防止分离阶段出现吸引力；
- V2第一阶段不加入接触滞环、静摩擦模式或损伤记忆，避免产生未进入Koopman状态的隐藏变量。

该公式满足

\[
\delta_i=0\Rightarrow F_{N,i}=0.
\]

当\(n>1\)时还满足

\[
\left.\frac{\partial F_N}{\partial\delta}\right|_{\delta=0}=0,
\]

因而连接力在接触建立处不再出现V1的\(cv_n\)跳变。

### 1.2 功率与能量符号

采用`d = vehicle_anchor - payload_anchor`和`vn = dot(d_dot,n)`。连接力对车辆与货物的合功率为

\[
P_i=\boldsymbol F_{L,i}^\top\boldsymbol v_{L,i}
+\boldsymbol F_{v,i}^\top\boldsymbol v_{v,i}
=-F_{N,i}v_{n,i}.
\]

弹性势能按

\[
U_i(\delta_i)=\frac{K}{n+1}\delta_i^{n+1}
\]

记录。未触发`[Y]_+`时，阻尼耗散率为

\[
P_{d,i}=C_H\delta_i^n v_{n,i}^2\ge0.
\]

实现时不得沿用V1的`c*loading_speed**2`作为V2耗散率。

### 1.3 参数不能直接照搬

旧`k=30000 N/m`和`c=3500 N*s/m`与V2的`K,C_H`量纲不同，禁止直接赋值。参数初始化采用工作点匹配：

1. 只读取V1训练域或实测数据，确定参考穿透量\(\delta_{\mathrm{ref}}\)；
2. 若匹配V1在参考点的割线力，则

\[
K_0=k_{\mathrm{V1}}\delta_{\mathrm{ref}}^{1-n};
\]

3. 若匹配参考点切线刚度，则

\[
K_0=\frac{k_{\mathrm{V1}}}{n\delta_{\mathrm{ref}}^{n-1}};
\]

4. 两种匹配不可混用。优先根据实测力--位移曲线最小二乘辨识`K,n`；没有实测时使用割线匹配，并明确称为数值等效参数；
5. `C_H`通过自由衰减、碰撞恢复系数或V1目标耗能匹配，不以降低预测误差为唯一辨识目标；
6. `rated_force_n`、`ultimate_force_n`、`maximum_working_displacement_m`和`failure_displacement_m`必须形成自洽参数组。

### 1.4 极限与失效

V2至少实现以下诊断：

```text
working_displacement_exceeded
failure_displacement_exceeded
rated_force_exceeded
ultimate_force_exceeded
raw_force_n
applied_force_n
```

正式植物暂定：

\[
F_{\mathrm{applied}}=\min(F_N,F_{\mathrm{ultimate}}).
\]

达到失效位移或极限力时，轨迹立即标记失败并停止，不在同一正式数据集中混合“失效后仍正常连接”的样本。后续如研究断裂，必须把失效模式作为显式离散状态另立实验。

## 2. 系统级内力分解

### 2.1 四点力与货物广义力

货物体坐标系四点力堆叠为

\[
\boldsymbol f=
[F_{1x},F_{1y},\ldots,F_{4x},F_{4y}]^\top\in\mathbb R^8.
\]

货物平面广义力为

\[
\boldsymbol w_L=[F_x,F_y,M_z]^\top=\boldsymbol G\boldsymbol f,
\]

其中

\[
\boldsymbol G=
\begin{bmatrix}
1&0&1&0&1&0&1&0\\
0&1&0&1&0&1&0&1\\
-r_{1y}&r_{1x}&-r_{2y}&r_{2x}&-r_{3y}&r_{3x}&-r_{4y}&r_{4x}
\end{bmatrix}.
\]

### 2.2 运动力与内部力

使用带固定容差的SVD伪逆：

\[
\boldsymbol f_{\mathrm{motion}}=\boldsymbol G^\dagger\boldsymbol w_L,
\]

\[
\boldsymbol f_{\mathrm{internal}}
=(\boldsymbol I-\boldsymbol G^\dagger\boldsymbol G)\boldsymbol f.
\]

必须验证

\[
\|\boldsymbol G\boldsymbol f_{\mathrm{internal}}\|\le\varepsilon_G.
\]

`Q_FR/Q_LR`继续保留以兼容历史图表，但降级为两个可解释投影，不再称为完整撕裂力。正式新增：

```text
internal_force_vector_n[8]
internal_force_norm_n
motion_force_vector_n[8]
generalized_payload_wrench[3]
grasp_rank
grasp_condition
diagonal_tension_modes_n[2]
```

如果坚持每点只沿实时径向受力，还应构造标量径向矩阵\(G_r\in\mathbb R^{3\times4}\)，报告其零空间内力；不得把8维自由力零空间和4维径向力零空间混为一谈。

### 2.3 “撕裂”表述边界

只有连接点载荷，没有货物材料、截面、有限元应力或试验强度时，只能报告：

- 货物内部拉伸载荷代理；
- 内部力范数；
- 对角/前后/左右受拉模式；
- 局部连接点峰值与方向。

不得直接声明货物发生或不会发生材料撕裂。材料结论至少需要将四点载荷映射到货物结构应力\(\sigma\)，并与允许应力或疲劳曲线比较。

## 3. 代码修改清单

### C0：冻结与版本隔离

1. 保存当前代码hash、运行命令、已完成轨迹数和停止时间；
2. 旧植物命名`plant_v1_linear_gated`；
3. 新植物命名`plant_v2_hc_smooth`；
4. 旧数据目录改为只读使用逻辑，禁止覆盖；
5. 新结果必须写入全新目录；
6. 所有NPZ/JSON元数据写入`plant_law_version`和公式参数。

输出：

```text
connector_v2_results/c0_freeze.json
connector_v2_results/work_log.md
```

### C1：建立唯一连接器实现

新增：

```text
_epd_impl/reference/connector_v2.py
```

建议接口：

```python
connector_force_v2(
    displacement_world,
    relative_velocity_world,
    params,
) -> ConnectorResult
```

`ConnectorResult`至少包含：

```text
distance_m
penetration_m
normal_world
normal_speed_mps
raw_force_n
applied_force_n
force_payload_world_n
force_vehicle_world_n
elastic_energy_j
damping_power_w
contact_active
limit_flags
```

以下代码不得再复制连接公式，只允许调用统一函数：

```text
_epd_impl/reference/four_vehicle_coupled.py
_combo_audit/generate_k2.py
_combo_audit/generate_compare.py
_combo_audit/universal_pipeline.py
_combo_audit/universal_v2_modules.py
_combo_audit/universal_v2_closedloop.py
_epd_impl/epd/axial_decoder.py
```

特别删除`universal_v2_modules.py::physics_force()`中的硬编码：

```python
30000.0 * penetration + 3500.0 * loading
```

训练物理头、真实植物和MPC必须读取同一版本化参数对象。

### C2：参数与Schema

扩展`ConnectorParams`：

```text
law_version
contact_exponent_n
contact_stiffness_K
hysteresis_damping_CH
free_play_m
maximum_working_displacement_m
failure_displacement_m
rated_force_n
ultimate_force_n
force_cap_enabled
```

修改：

```text
_epd_impl/reference/schema.py
_epd_impl/epd/data_adapter.py
_epd_impl/epd/core_adapter.py
_combo_audit/transition.py
```

Schema必须记录参数量纲，禁止继续使用含义不明的`k/c`字段读取V2。

### C3：内力模块

新增：

```text
_epd_impl/reference/internal_force.py
```

实现：

```text
build_planar_grasp_matrix()
decompose_planar_point_forces()
build_radial_grasp_matrix()
decompose_radial_forces()
legacy_q_fr_q_lr()
```

SVD容差、点序`FL/FR/RL/RR`、坐标系和力作用侧必须写入schema和单元测试。

### C4：测试文件

新增：

```text
tests/test_connector_v2.py
tests/test_internal_force.py
tests/test_connector_v2_integration.py
```

若仓库当前没有统一`tests`入口，则放入`_epd_impl/tests/`，但不得只写临时脚本而不进入自动测试。

## 4. 连接器模型验收

### G1：解析与单元测试门

全部通过才能进入积分实验：

1. `r < l0`时力严格为零；
2. `delta -> 0+`时力趋于零；
3. 四个基本方向`+x/-x/+y/-y`的力方向正确；
4. 货物力与车辆力逐点满足作用--反作用；
5. 旋转30°、60°后力同步旋转；
6. 左右镜像后点序和力分量正确变换；
7. `raw_force >= 0`且`applied_force <= ultimate`；
8. 弹性势能非负；
9. 阻尼耗散率非负；
10. 内力满足`norm(G @ f_internal) <= 1e-8 * max(1,norm(f))`；
11. `f = f_motion + f_internal`重构误差满足同级容差；
12. `Q_FR/Q_LR`与历史定义逐元素一致。

任一代数门失败：停止，不运行长程仿真。

### G2：单连接器动态门

运行以下可解析或高精度参考算例：

1. 无阻尼自由振动；
2. 有阻尼加载--卸载；
3. 从间隙内以不同速度接触；
4. 正负四方向镜像；
5. 低、中、高三种接触速度；
6. 低、标称、高三种刚度；
7. 接近额定力但不超限；
8. 超极限停止逻辑。

保存500 Hz以上：

```text
delta, vn, Fraw, Fapplied, Uelastic, Pdamping,
contact_active, switching_event, impulse
```

硬门：

- 接触初始力不得出现与速度成正比的有限非零极限；
- 无外力、无阻尼算例总机械能相对漂移小于0.5%；
- 有阻尼算例总机械能不出现持续增长；
- 同一参数和初值重复运行hash一致；
- 无NaN/Inf；
- 不发生未授权的负法向力。

### G3：积分步长收敛门

对相同输入比较：

```text
dt = 0.0020 s
dt = 0.0010 s
dt = 0.0005 s
```

至少比较：

- 峰值连接力；
- 连接冲量；
- 货物位置、速度、横摆；
- 四车横摆；
- 接触切换次数；
- 内部力峰值；
- 总能量残差。

以`dt=0.0005 s`为参考，`dt=0.002 s`的峰值力相对差不得超过5%，冲量相对差不得超过2%，关键状态末值相对/尺度化误差不得超过1%。失败时优先减小植物步长，不得通过调低刚度掩盖数值问题。

### G4：四车100 m验收

继续使用已约定工况，并对V1/V2使用相同初值和控制：

1. 前30 m：\(a_x=0.35\ \mathrm{m/s^2}\)；
2. 30 m后匀速：\(a_x=0\)；
3. 持续5 s正向阶跃转向；
4. 随后持续5 s反向阶跃转向；
5. 剩余路段减速，减速度根据剩余距离闭合但绝对值不超过\(0.45\ \mathrm{m/s^2}\)；
6. 记录频率：植物状态和连接器诊断500 Hz，控制与常规图50 Hz。

必须输出：

```text
四点Fx/Fy及方向箭头
四点力模和力变化率
单车横摆率
货物横摆率
系统横摆率
货物广义合力/合力矩
Q_FR/Q_LR
完整internal-force norm和各模式
左右侧、前后侧和对角受力
接触状态和切换驻留时间
弹性储能和阻尼耗散
轮胎利用率
```

V2相对V1的最低验收：

- 最大2 ms接触起力跳变下降至少50%；
- 20 Hz以上连接力能量不增加；
- 接触切换次数不增加超过10%；
- 100 m距离门通过；
- 车辆/货物状态均有限；
- 峰值轮胎利用率不恶化超过0.02绝对值；
- 作用--反作用残差满足数值容差；
- 不触发极限力或失效位移。

如果力跳下降只是因为V2整体力幅值明显缩小，必须同时报告峰值力比、RMS力比和冲量比，不得把“连接器变软”解释成“平滑公式更优”。

### G5：转弯与内力方向门

在单移线和回头弯分别验证：

1. 左右弯镜像；
2. 四点力方向随弯向正确反转；
3. 合力和合力矩与货物加速度、横摆加速度符号一致；
4. 内部力投影不改变货物广义力；
5. 转向换向前后保存事件窗口；
6. 旧`Q_FR/Q_LR`与完整内力可能不一致时，明确展示漏检案例。

G1--G5全部通过后，V2植物才允许冻结。

## 5. 参数辨识与敏感性

### 5.1 有实测数据时

按优先级使用：

1. 静态力--位移曲线辨识`K,n,l0`；
2. 自由衰减辨识耗能参数；
3. 碰撞实验的恢复系数和初始速度校核`C_H`；
4. 循环加载检查滞回；
5. 扭转和切向加载判断是否需要下一版模型。

训练集、验证集和确认集不得共同参与参数辨识。物理参数应在数据生成前冻结。

### 5.2 没有实测数据时

只能建立“等效数值连接器”，执行：

```text
n  = 固定物理假设值
K  = V1训练域参考穿透量的割线匹配
CH = 训练域耗能/衰减匹配
l0 = 当前几何间隙及制造误差假设
```

并进行参数敏感性：

```text
K  : 0.75, 1.00, 1.25
CH : 0.70, 1.00, 1.30
l0 : 0.70, 1.00, 1.40
```

`n`如果没有实物依据，不进入大网格寻优。最多在开发集比较两个预注册候选，并把选择过程公开；不得用确认集选择指数。

## 6. 新数据生成

### 6.1 旧数据处置

下列旧数据全部保留但标记为V1：

- 已停止的MPC输出；
- 现有416个基础轨迹族；
- 旧Koopman训练、验证和development结果；
- 旧受力图和`Q_FR/Q_LR`结论。

用途仅限：

1. V1基线；
2. 植物本构消融；
3. V1模型在V2植物上的失配鲁棒性诊断。

禁止：

- 将V1和V2样本拼接训练正式V2模型；
- 使用V1力标签监督V2物理头；
- 将V1闭环结果与V2闭环结果称为同一植物下的控制器比较。

### 6.2 V2数据版本

新目录建议：

```text
connector_v2_results/
connector_v2_data/
connector_v2_models/
connector_v2_mpc/
```

正式基础轨迹族：

| Split | 基础轨迹族 | 每工况 | 是否允许调参 |
|---|---:|---:|---|
| train | 256 | 64 | 仅训练 |
| validation | 96 | 24 | 结构和超参数选择 |
| development | 64 | 16 | 只做失败诊断/预注册选择 |
| confirm | 96 | 24 | 一次性盲确认 |

四类基础工况：

```text
staged_100m
single_lane_change
hairpin
connector_directional
```

左右镜像可作为解析增广，但不计入独立样本数。确认集必须使用全新seed块，生成前扫描整个仓库的结构化`seed/traj_id`防碰撞，并冻结seed清单hash。

### 6.3 两阶段生成

#### D0：小样本Pilot

先生成每工况8条，共32个基础族。检查：

- 有限性；
- 距离门；
- 接触/非接触覆盖；
- 建立/脱离事件覆盖；
- 四点正负`Fx/Fy`覆盖；
- 内部力模式覆盖；
- 参数随机化范围；
- 高受力但不超限样本；
- 500 Hz力信号无未解释尖峰；
- NPZ字段、坐标系和时间对齐。

Pilot失败则停止，不允许直接批量生成。

#### D1：正式数据

Pilot通过后生成train和validation。冻结模型结构后才允许生成development；候选通过全部development门后才生成confirm。不得提前查看confirm统计图。

### 6.4 每条轨迹必须保存

保留原字段：

```text
state30
state46
control
connector_disp
connector_vel
force_payload
force_vehicle
q
payload_yaw
system_yaw
time_s
initial_state64
control64
metadata_json
```

新增：

```text
penetration[time,4]
normal_speed[time,4]
raw_force_norm[time,4]
applied_force_norm[time,4]
contact_active[time,4]
elastic_energy[time,4]
damping_power[time,4]
force_rate_payload[time,4,2]
generalized_payload_wrench[time,3]
internal_force_vector[time,8]
internal_force_norm[time]
motion_force_vector[time,8]
grasp_rank[time]
grasp_condition[time]
limit_flags[time,4]
```

元数据新增：

```text
plant_law_version
formula_text/hash
connector_parameter_units
code_commit/hash
schema_version
generation_command
plant_dt/log_dt/substeps
seed/traj_id/base_family_id
split/scenario/mirror flags
```

### 6.5 数据覆盖门

train、validation分别报告且不得合并：

- 每点接触活动比例；
- 每点接触建立和脱离次数；
- 接触速度分位数；
- 穿透量分位数；
- 四点力分量正负计数；
- 力方向反转次数；
- 内部力范数分位数；
- 高受力窗口数；
- 参数范围；
- 工况和转向方向配额；
- 失效/极限事件数；
- 轨迹长度和独立20步窗口数。

若高受力或接触切换仅集中在少数轨迹，必须补充独立基础族，不能靠重叠滑窗制造样本量。

## 7. Koopman重训与“更顺利”的验证

### 7.1 不能直接声明的结论

V2公式理论上消除了接触起点的有限力跳，但这不等价于Koopman一定更准确。必须排除：

1. V2只是整体降低了连接力；
2. 新数据工况更简单；
3. V2训练样本更多；
4. V2归一化尺度不同造成NRMSE假改善；
5. 只改善受力而状态退化；
6. 只改善一步而20步无改善。

### 7.2 成对可学习性消融

用相同IC、控制、seed、参数分位和数据数量生成V1/V2成对轨迹。对每种植物训练完全相同的：

```text
fixed linear Koopman
fixed lifted Koopman
bilinear Koopman
three-expert gated Koopman
当前冻结的最优候选
```

所有模型使用相同：

- 状态合同；
- 训练/验证族数量；
- horizon=20；
- 优化器、epoch和seed；
- 参数预算；
- 早停规则；
- 指标与bootstrap方案。

### 7.3 指标

分别报告1、5、10、15、20步：

```text
state_core NRMSE
connector displacement NRMSE
connector velocity NRMSE
four-point force NRMSE and MAE(N)
internal-force NRMSE and MAE(N)
force-direction accuracy
contact-mode accuracy
force-rate error
peak-force error
transition-window error
divergence rate
runtime p50/p95/p99
```

额外定义接触切换事件窗\([t_e-0.2,t_e+0.5]\) s，单独计算事件窗误差，不得让大量非接触零力样本稀释结果。

同时计算目标可学习性诊断：

- 相邻样本最大力变化；
- `p95/p99 |Delta F|`；
- 5 Hz和20 Hz以上谱能量；
- 局部Lipschitz代理`||Delta y||/||Delta x||`；
- 同状态近邻的下一步输出方差。

### 7.4 声明V2有利于Koopman的最低门

在盲确认集上，V2相对V1必须同时满足：

1. 10--20步四点力NRMSE改善至少8%，配对95% CI下界大于0；
2. 接触切换事件窗力MAE改善至少15%；
3. 10--20步`state_core`不得恶化超过3%；
4. 内部力MAE不得恶化超过5%；
5. 发散率不得增加；
6. 改善至少在四类工况中的三类方向一致；
7. 同时报告绝对N误差，确认并非仅因真实力幅值下降；
8. 推理p99不超过控制预算。

若只满足受力改善，结论限于“提高连接力目标的可学习性”；若状态和受力均改善，才可称“改善多步耦合预测”。

## 8. MPC恢复步骤

### M0：前置条件

只有以下条件全部满足才恢复MPC：

- G1--G5通过；
- V2正式train/validation完成；
- Koopman离线门通过；
- 物理头、状态归一化和力归一化冻结；
- 同一个46维、模型无关MPC适配器完成；
- 权重、约束、求解预算和fallback在confirm前冻结。

### M1：代价函数

统一代价：

\[
J=J_{\mathrm{track}}
+\lambda_uJ_u
+\lambda_{\Delta u}J_{\Delta u}
+\lambda_F\sum_i\|\boldsymbol F_i\|^2
+\lambda_{\mathrm{int}}\|\boldsymbol f_{\mathrm{internal}}\|^2
+\lambda_{\Delta F}\|\Delta\boldsymbol f\|^2.
\]

`Q_FR/Q_LR`可以展示，但正式安全代价优先使用完整内部力。所有方法使用相同权重，不允许为某个Koopman单独调权。

### M2：约束

至少加入：

\[
\|\boldsymbol F_i\|\le F_{\mathrm{rated}},
\]

\[
\|\boldsymbol f_{\mathrm{internal}}\|\le F_{\mathrm{int,max}},
\]

\[
\|\Delta\boldsymbol F_i\|\le \dot F_{\max}\Delta t,
\]

以及既有转角、转角速率、加速度、轮胎利用率和路径边界约束。初期可用软约束和显式slack，但必须单独报告slack使用率。

### M3：实验顺序

1. clean staged-100m；
2. clean单移线；
3. clean回头弯；
4. clean条件下Koopman/MPC方法对比；
5. 通信延迟和丢包；
6. 持续通信干扰；
7. DoS攻击；
8. 执行器与网络联合扰动。

网络实验不得早于clean闭环通过。

### M4：V1旧模型的用途

旧MPC模型只允许进入两个对照：

```text
V1 Koopman + V1 plant：历史基线
V1 Koopman + V2 plant：模型失配鲁棒性诊断
```

正式V2方法比较必须是：

```text
所有候选V2 Koopman + 同一V2 plant + 同一MPC
```

## 9. 可能跑不动的情况与处理

### F1：数值刚性或高频振荡

现象：减小步长后峰值力明显变化、500 Hz仍接近奈奎斯特、高频能量增加。

处理顺序：

1. 检查参数量纲和`K`换算；
2. 降低植物积分步长；
3. 使用自适应/刚性积分器做参考；
4. 检查是否错误直接复制`9.3e6 N/m`；
5. 不允许为了跑通随意减小物理刚度。

若`dt=0.0005 s`仍不收敛，停止并写`solutions.md`。

### F2：力连续但出现负力或能量增长

处理：检查`vn`符号、力作用侧、正部投影和功率公式。禁止通过对输出取绝对值掩盖符号错误。

### F3：V2真实力幅值显著小于V1

处理：重新检查工作点匹配、冲量和储能；报告幅值变化。若无法保持目标载荷域，V2只能称不同参数植物，不能用于证明平滑本构带来学习优势。

### F4：正式数据接触事件不足

处理：增加独立`connector_directional`基础族、扩大合理IC与控制覆盖；不得通过重复窗口或镜像计数补足。

### F5：Koopman一步改善但20步不改善

处理：检查核心状态误差是否通过锚点几何放大、连接形变状态是否可辨识、固定算子是否在接触模式间平均。随后只允许按预注册顺序尝试lifted、bilinear和三专家，不直接进入MPC。

### F6：完整内部力病态

现象：`G`条件数高、伪逆内力剧烈变化。

处理：同时报告rank和condition；采用冻结SVD容差；比较8维自由力与4维径向力分解。不得在每条轨迹上调容差取得好看曲线。

### F7：MPC不可行率增加

处理顺序：

1. 检查预测尺度和单位；
2. 检查额定力约束是否低于正常工况需求；
3. 使用统一slack并报告；
4. 检查预测不确定性和约束收紧；
5. 不允许只给某个模型放宽安全约束。

### F8：没有实测参数

停止实物安全主张；保留数值等效连接器和参数敏感性结论。解决方案应明确列出需要的静态拉压、自由衰减和碰撞试验。

## 10. 执行任务树

```text
C0 冻结V1和停止的MPC批次
├─ 写hash、命令、完成度和旧数据边界
└─ G0 物理连接类型与假设冻结

C1 唯一V2连接器实现
├─ 统一参数与schema
├─ 删除各处硬编码旧公式
├─ 极限/能量诊断
└─ G1 解析与单元测试
   └─ 失败：停止，写solutions.md

C2 单连接器动力学
├─ 加载/卸载/接触/镜像
├─ 参数初值与量纲核查
└─ G2 动态与能量门
   └─ 失败：停止

C3 四车植物集成
├─ 作用反作用
├─ 完整内力分解
├─ 步长收敛
└─ G3 数值门
   └─ 失败：停止

C4 V1/V2成对100 m、单移线、回头弯
├─ 500 Hz力与事件诊断
├─ 力幅值/冲量公平核查
├─ G4 100 m门
└─ G5 弯道内力方向门
   └─ 任一失败：停止

D0 32族Pilot
├─ 字段/时间/坐标系
├─ 接触和高受力覆盖
└─ GD0 数据Pilot门
   └─ 失败：停止

D1 正式train/validation
├─ 数据覆盖报告
├─ hash与只读冻结
└─ GD1 数据门

K0 V1/V2同结构可学习性消融
├─ fixed linear
├─ fixed lifted
├─ bilinear
├─ three-expert
└─ 当前冻结候选

K1 validation选型
└─ 失败：不生成confirm、不进入MPC

K2 development稳定性
└─ 失败：停止并写原因

K3 一次性blind confirm
└─ 失败：保留负结果，不进入MPC

M0 冻结46维模型无关MPC
├─ 完整内力和力变化率代价
├─ 额定力/内力/力率约束
└─ clean闭环

M1 staged-100m
M2 single-lane-change
M3 hairpin
└─ clean全部通过后
   ├─ M4 通信延迟/丢包
   ├─ M5 通信干扰
   └─ M6 DoS与联合扰动
```

## 11. 留痕要求

每完成一个阶段必须立即追加：

```text
connector_v2_results/work_log.md
```

每条记录包括：

- 时间；
- 阶段编号；
- 修改文件；
- 修改前后hash；
- 执行命令；
- seed和数据split；
- 输入/输出路径；
- 关键数值；
- 门禁通过/失败；
- 是否读取development/confirm；
- 下一允许动作。

任何必要证据无法跑出时立即停止，并写：

```text
connector_v2_results/solutions.md
```

`solutions.md`必须区分：

1. 已核实事实；
2. 最可能原因；
3. 尚未排除原因；
4. 可执行解决方案；
5. 每个方案的风险、成本和验证方法；
6. 恢复执行所需的明确条件。

## 12. 最终交付

至少包含：

```text
connector_v2.md
connector_v2_results/work_log.md
connector_v2_results/solutions.md（若发生停止）
connector_v2_results/plant_validation/
connector_v2_results/data_audit/
connector_v2_results/koopman_compare/
connector_v2_results/mpc/（仅通过前置门后存在）
```

图表最低集合：

1. V1/V2接触建立放大图；
2. V1/V2力--穿透和力--速度图；
3. 能量与阻尼耗散图；
4. 100 m四点力和方向图；
5. 单车、货物和系统横摆图；
6. `Q_FR/Q_LR`与完整内部力比较图；
7. V1/V2 1--20步Koopman误差图；
8. 接触事件窗误差图；
9. 通过门后才生成的MPC跟踪--受力--求解时间图。

最终论文只允许按门禁结果选择表述：

- 仅植物通过：平滑非线性连接器改善接触边界的物理与数值连续性；
- Koopman受力通过：改善连接力目标的多步可学习性；
- 状态与受力均通过：改善四车--货物耦合系统多步预测；
- MPC也通过：在同一V2植物、同一MPC下改善跟踪/内部力/安全指标；
- 任一阶段失败：保留负结果和适用边界，不跨阶段宣称收益。

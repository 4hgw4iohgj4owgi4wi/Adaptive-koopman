# EFD-R1执行书：硬等变连接几何Koopman

> 状态：新协议草案，尚未执行；冻结后才能修改代码或生成数据。  
> 5080工程：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码：`revision_2026/koopman/innovation/efd_r1/`  
> 新结果：`revision_2026/koopman/innovation_efd_r1_results/`  
> 历史只读：`innovation/efd/`、`innovation_efd_results/`及旧`direction`目录。  
> 本轮范围：只验证离线20步状态—连接几何—四点力预测；不运行development前的闭环、LPV、多专家、在线更新、通信干扰或DoS。

## 1. 为什么必须新立R1

EFD-v1已经正式在validation失败，不能通过修改旧门或重用旧validation恢复。最新事后诊断给出三个确定事实：

1. H2连接位移方向oracle角度p95为`169.599°`，不能继续把H2几何作为方向基底；
2. G-EFD在validation上相对H2将`J/连接位移/force/货物拉伸载荷`分别改善`33.52%/82.95%/78.44%/58.47%`，说明直接学习连接几何值得保留；
3. EFD-v1的左右镜像对并不严格：208组中同一物理场景为0组，严格镜像为0组；模型也没有实现预注册的等变损失或硬等变投影。

分层等变诊断为：

| 变换 | H2几何p95 | head原始输出p95 | 组合位移p95 | 最终力p95 |
|---|---:|---:|---:|---:|
| 全局旋转30° | 4.12% | `1.32e-8%` | 10.02% | 3.41% |
| 全局旋转60° | 7.76% | `1.37e-8%` | 21.91% | 8.12% |
| 左右镜像 | 28.48% | 128.58% | 188.87% | 153.62% |

因此R1不再研究D-EFD方向残差，也不在H2错误几何上做G残差。R1直接建立**独立、相对坐标、硬等变的30—46维连接几何骨干**，再通过轴向物理解码得到四点力。

## 2. 可证伪问题和允许声明

主问题：

> 在保留H2前30维车辆—货物状态预测的同时，独立预测货物体坐标系下四点连接位移和相对速度，并硬编码旋转/镜像变换及轴向连接器本构，能否在全新盲确认集上同时改善20步状态、连接力、货物拉伸载荷和方向？

只有全新validation、development和confirm全部通过，才允许声明：

> EFD-R1通过硬等变连接几何骨干和轴向物理解码，改善了四车协同搬运系统的20步多物理量预测。

只在validation通过时，只能称“开发阶段有效”；只改善连接位移时，只能称“几何预测改进”；Q代数和作用—反作用残差为零不能单独证明预测改进。

## 3. 方法定义

### 3.1 输入输出

保留因果输入：

```text
x0       [B,46]      当前完整状态
u_future [B,20,8]    已知/规划的20步控制
p_static [B,np]      仅在连接参数跨轨迹变化时使用；k/c/g/m等当前系统已知常量
```

输出：

```text
state_core       [B,20,30]   冻结H2前30维
connector_disp   [B,20,4,2]  R1直接预测，货物体坐标系
connector_vel    [B,20,4,2]  R1直接预测，货物体坐标系
force_payload    [B,20,4,2]
force_vehicle    [B,20,4,2]  = -force_payload
Q_FR/Q_LR        [B,20,2]
force_rate       [B,20,4,2]  因果递推
```

若`p_static`进入R1，E0/K1/H2/E3等所有可接收静态参数的对照也必须获得同一参数，结果表必须注明输入变化；若所有轨迹参数固定，则删除该输入，不能虚构参数变化。

### 3.2 相对坐标特征

`equivariant_features.py`必须从当前状态构造：

- 四车相对货物的位置，旋转到当前货物体坐标系；
- 四车与货物的相对航向，用`sin/cos`表示；
- 车辆/货物体坐标速度和横摆角速度；
- 当前四点连接位移与相对速度；
- 未来控制序列；
- 可选静态连接参数。

不得输入绝对世界坐标`x/y`和未经周期编码的绝对航向。对任意全局旋转`R_gamma`应满足：

\[
\phi(R_\gamma x,u,p)=\phi(x,u,p).
\]

旋转不再依赖H2未来连接几何，因此不能重复EFD-v1的“H2基底破坏旋转等变”问题。

### 3.3 硬镜像线性映射

左右镜像时角点置换：

```text
FL <-> FR
RL <-> RR
x分量不变，y分量取反
```

令列特征满足`phi(Mx,Mu)=R_phi phi(x,u)`，连接几何输出满足`y(Mx,Mu)=R_y y(x,u)`。普通ridge得到`W`后，必须做Reynolds投影：

\[
W_{eq}=\frac{1}{2}\left(W+R_y^{-1}WR_\phi\right),
\]

并以代码单元测试为矩阵左右乘约定的最终依据。要求：

\[
\max\|W_{eq}R_\phi-R_yW_{eq}\|\le10^{-12}.
\]

不能只靠正反弯样本“希望网络自己学会镜像”。

### 3.4 独立连接几何骨干

对每个预测步`h=1...20`：

\[
\begin{bmatrix}\hat d_h\\\hat v_h\end{bmatrix}
=W_{eq,h}\phi_h(x_0,u_{0:h-1},p).
\]

其中`d/v`共16维。最终46维状态为：

\[
\hat x_h=[\hat x^{H2}_{h,0:30},\hat d_h,\hat v_h].
\]

R1几何骨干不得读取H2的`30:46`输出；旧H2连接几何只作为对照指标。主模型采用horizon-wise ridge，固定网格`{1e-8,1e-6,1e-4,1e-2}`，不增加MLP以免把结构改进与容量混在一起。

### 3.5 两种解码器消融

必须使用同一个R1几何骨干比较：

#### R1-L：学习非负幅值

\[
\hat F_{i,h}=\operatorname{softplus}(m_{i,h})
\frac{\hat d_{i,h}}{\|\hat d_{i,h}\|+\epsilon}.
\]

它用于判断“几何结构有效但plant本构读出不足”的情况，不能单独称为完整本构模型。
幅值head同样必须做硬镜像投影：左右镜像时四点幅值只按`FL↔FR、RL↔RR`置换，不改变符号；不能让R1-L重新引入EFD-v1的镜像偏置。

#### R1-P：轴向物理解码，论文主候选

源代码审计后把plant的同一公式只实现一份：

\[
n_i=\frac{d_i}{\|d_i\|+\epsilon},\qquad
e_i=\max(\|d_i\|-g,0),
\]

\[
T_i=\max\left(k e_i+c\,\Gamma(e_i,v_i^\top n_i),0\right),qquad
F_i=T_i n_i.
\]

`Gamma`必须逐行复现plant的加载/卸载和间隙逻辑，不能根据validation结果自行选择“阻尼是否在间隙内生效”。若参数跨轨迹变化，使用该轨迹在预测时已知的`k/c/g`；不能读取未来估计值。

若R1-L通过而R1-P失败，结论是“几何可预测，但当前本构/参数合同不足”；不得选择R1-L后仍声称复现了真实连接器本构。

### 3.6 作用—反作用、Q和力变化率

- `F_vehicle=-F_payload`硬编码；
- `Q_FR/Q_LR`只从最终四点货物侧力统一重构；
- 第1步力变化率使用当前实测四点力，后续使用上一预测步；
- 双侧独立日志只用于plant审计，不把硬重构值冒充独立测量。

## 4. fallback重新定义

EFD-v1最终诊断：全部点fallback=`12.344%`，预测活动点=`5.148%`，当前实测活动点=`7.709%`，均说明问题未完全消失。

R1冻结以下定义：

1. 数值方向有效阈值`epsilon_dir=1e-8 m`，来自浮点与模型尺度，不再用接近2 mm间隙的1%数据分位数定义“方向无效”；
2. `predicted_active`由当前候选自己预测的`T_i`是否超过train-only四点力floor判定；
3. `current_active`由当前实测力和train-only floor判定，只作因果诊断；
4. `truth_active`只作离线归因，不进入选择门；
5. 主门为`predicted_active_fallback<=1%`；同时报告all/current/truth-active四种比率；
6. 活动且方向无效时，先使用当前实测位移方向；当前位移也无效时沿预测时域使用上一有效方向；仍无有效方向则输出零力并记`unresolved_active_fallback`，禁止静默置零。

若降低`epsilon_dir`后活动fallback自然消失，必须报告这是“有效性阈值修正”，不能包装成模型精度提升。

## 5. 严格镜像数据合同

### 5.1 不能重复的错误

EFD-v1用相同随机种子和相反转向符号配对，但成对成员物理场景不同；这只能算正反转向覆盖，不能算镜像。

### 5.2 R1生成方式

每条独立base轨迹生成后，在同一split内产生一个解析镜像副本：

```text
same base_family_id
same physical_scene
same parameters and initial-condition source
same timestamps
mirror_copy = exact M(base arrays)
is_augmented = true
```

镜像副本是数据增强，不计为独立轨迹样本；统计和bootstrap单位为`base_family_id`。禁止把base及其镜像分到不同split。

pilot还必须用变换后的初始状态和控制单独运行至少8组成对仿真，验证plant数值镜像。若当前仿真器无法注入镜像初值，停止并先增加该接口；不能用解析复制冒充独立镜像仿真。

### 5.3 数组级门禁

对解析镜像副本逐字段检查：

- 世界位置、航向、体坐标速度；
- 连接位移与相对速度；
- 四车加速度/转角；
- 货物侧/车辆侧四点力；
- `Q_FR/Q_LR`；
- system/payload yaw。

解析副本最大绝对残差≤`1e-12`；独立镜像仿真归一化p95≤`1e-5`且最大误差≤预注册的积分器容差。任一字段失败即停止R1训练。

## 6. 新数据与证据隔离

### 6.1 seed块

EFD-v1的190xxx—196xxx全部视为已使用。R1在执行R0时，按下列顺序选择第一个完全无碰撞的10,000 seed块：

```text
候选BASE = 201000, 211000, 221000
```

选定`BASE`后：

| split | 独立base数 | seed |
|---|---:|---|
| pilot | 16 | BASE+1—BASE+16 |
| train | 256 | BASE+1001—BASE+1256 |
| validation | 96 | BASE+2001—BASE+2096 |
| development | 64 | BASE+3001—BASE+3064 |
| confirm | 160 | BASE+4001—BASE+4160 |
| bootstrap | 5 | BASE+5001—BASE+5005 |
| 统计 | 1 | BASE+5999 |

碰撞审计必须解析结构化`seed/traj_id`字段；某一seed碰撞时整体换到下一个候选BASE，禁止只替换碰撞项。号段、生成器hash、场景表和参数表在生成pilot前冻结。

### 6.2 场景覆盖

独立base轨迹覆盖：

- R0直线匀速；
- R1加速、制动和间隙加载/卸载；
- R2正反阶跃转向及切换；
- R3单移线、回头弯和直线—弯道过渡；
- 连接器参数/载荷质量变化；
- 高货物拉伸载荷、八分量正负方向和方向反转。

数量门沿用EFD-v1，但全部以独立`base_family_id`和未增强窗口计数。增强副本不得提高覆盖样本数或统计显著性。

### 6.3 数据角色

- EFD-v1全部数据降为`legacy_diagnostic`；
- R1 train只拟合参数、归一化、floor和ridge；
- validation只做有限网格选择；
- 模型和所有阈值冻结后只读一次development；
- development通过后才生成confirm；
- confirm失败后不得回看调参并重新命名盲集。

## 7. 必跑对照和消融

| 编号 | 方法 | 目的 |
|---|---|---|
| B0 | K1 fixed linear | 固定线性基线 |
| B1 | 冻结H2完整输出 | 现有Koopman骨干 |
| B2 | E3直接四点力ridge | 无物理方向限制的可学习性上界 |
| B3 | EFD-v1 G模型只读外推 | 判断旧修正头是否跨新数据泛化 |
| A0 | R1几何骨干，不做硬镜像投影 | 硬等变结构消融 |
| A1 | R1硬等变几何+学习幅值（R1-L） | 几何与本构分离 |
| M | R1硬等变几何+轴向物理解码（R1-P） | 论文主候选 |

A0只能在validation前预注册并一次运行，不能根据M失败再增加。所有方法使用相同20步、相同轨迹、相同归一化和相同统计单位；报告参数量、输入差异与运行时间。

## 8. 指标与硬门

### 8.1 分层指标

状态：`state_core_0_30`、`connector_disp_30_38`、`connector_vel_38_46`、`state_all_0_46`。

力：force/load NRMSE、四点角度MAE/p95、八分量方向、Q方向、反转准确率/恢复步数、力变化率、高载荷误差。

结构：

- 特征旋转不变误差；
- 线性映射镜像交换子残差；
- 几何骨干旋转/镜像误差；
- decoder旋转/镜像误差；
- 完整力路径旋转/镜像误差；
- Q和作用—反作用残差；
- 四类fallback；
- p50/p95/p99和最大时延。

### 8.2 validation门

R1-P必须全部满足：

1. 10—20步`J=(state_all+force+load)/3`相对H2改善≥8%，轨迹级bootstrap 95% CI下界>0；
2. `state_core`相对H2恶化≤1%；
3. connector displacement和velocity相对H2分别改善≥30%和≥10%，CI下界均>0；
4. force和货物拉伸载荷相对H2均改善≥10%，CI下界均>0；
5. 分量/Q/反转准确率均不低于K1减1个百分点，至少两项显著优于K1；
6. 角度p95<K1且≤90°；
7. R1几何骨干镜像交换子≤`1e-12`，合成变换单元测试≤`1e-10`；
8. 未见全局旋转30°/60°和左右镜像的完整力路径误差p95≤2%；
9. predicted-active fallback≤1%，unresolved-active fallback≤0.1%；
10. Q/作用—反作用残差≤`1e-10`，divergence不高于H2；
11. 9窗口20步预测p99≤2 ms、最大<20 ms；
12. 5个bootstrap中至少4个满足第1、3、4、5、6、8、9项。

R1-L使用相同门；若R1-L通过而R1-P失败，只允许保留“几何+结构化经验幅值”结论，不进入主方法盲确认，除非另立本构修订协议。

### 8.3 development和confirm

不重新选参，重复validation全部门，并要求：

- R0—R3任何工况force/load相对H2恶化不超过10%；
- 左右基础工况误差差异≤5%；
- 主要改善方向与validation一致；
- confirm至少160个独立base，统计单位仍为base family；
- confirm执行一次，完整保存失败结果。

## 9. 代码修改清单

新建`innovation/efd_r1/`，不得修改EFD-v1实现：

| 文件 | 必须实现 | 关键验收 |
|---|---|---|
| `config.py` | `EFDR1Config`、候选seed块、全部硬门 | 配置冻结/round-trip |
| `audit.py` | 旧目录hash、结构化seed扫描、split读取权限 | 旧EFD前后hash一致 |
| `schema.py` | 46维/8维/参数/坐标/奇偶合同 | 字段逐项断言 |
| `transforms.py` | `rotate_global`, `mirror_lr`, `transform_output` | 逆变换和二次镜像恢复 |
| `mirror_generator.py` | 解析镜像副本、镜像仿真初值/控制接口 | same scene/params/time；数组门通过 |
| `equivariant_features.py` | 相对货物特征、sin/cos、`R_phi` | 30°/60°旋转误差≤`1e-12` |
| `reynolds.py` | `project_linear_map(W,Rphi,Ry)` | 交换子≤`1e-12` |
| `geometry_backbone.py` | 20个时域的d/v ridge | 不读取H2 30:46；零/镜像单测 |
| `axial_decoder.py` | plant一致的间隙/加载阻尼/轴向力 | 真值d/v输入时力误差接近数值精度 |
| `magnitude_head.py` | R1-L非负幅值消融 | softplus有限/非负 |
| `fallback.py` | 四类rate、因果回退链 | 不读取未来truth；活动门可复算 |
| `baselines.py` | B0—B3只读适配 | H2/K1逐元素回归≤`1e-10` |
| `metrics.py` | 四组状态、力、方向、等变、fallback | base family统计；增强副本不增n |
| `statistics.py` | 轨迹bootstrap、置换、Holm、效应量 | 固定统计seed；小样本手算 |
| `train.py` | 固定ridge网格、5 bootstrap、冻结模型 | 不读取development |
| `evaluate.py` | validation/dev/confirm只读状态机 | 越权读取直接退出码2 |
| `report.py` | horizon、几何、方向、分层等变、fallback、门图 | 单位/n/CI/hash齐全 |
| `run.py` | R0—R10幂等阶段 | 前门失败阻断后续 |

### 9.1 必须增加的测试

```text
test_rotation_invariant_features
test_mirror_state_control_contract
test_mirror_output_corner_parity
test_reynolds_commutator
test_strict_mirror_metadata_and_arrays
test_geometry_head_does_not_read_h2_geometry
test_axial_decoder_truth_oracle
test_fallback_has_no_future_truth
test_augmented_family_not_double_counted
test_development_confirm_access_guard
```

任一测试失败不得生成正式train。

## 10. 阶段任务树

```text
R0 协议/代码/seed/旧结果冻结
└─ 失败：停止，不生成pilot

R1 变换、Reynolds和轴向decoder单元测试
└─ 失败：修实现；不得用数据调门

R2 16组pilot与8组独立镜像仿真
├─ plant镜像、真值本构oracle、资源投影
└─ 失败：停止并写solutions.md

R3 生成新train/validation/development
├─ 独立base覆盖
├─ 解析镜像数组合同
└─ 失败：不训练

R4 B0—B3新数据复现
└─ E3可学习性不复现：停止查数据

R5 训练A0/R1-L/R1-P并做validation
├─ 有限ridge网格
├─ 分层等变与四类fallback
└─ R1-P不过门：停止development

R6 冻结R1-P，一次读取development
└─ 不通过：停止，不生成confirm

R7 冻结confirm manifest并生成160个独立base
└─ 同seed断点重跑，不替换失败轨迹

R8 单次盲confirm
└─ 不通过：保留失败，不回调validation

R9 图表、报告、代码清单和工作记录

R10 只有R8通过后，另立闭环/网络实验MD
```

## 11. 计划命令

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd_r1\run.py'

& $PythonExe -B $Runner --project-root $ProjectRoot --stage r0
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r1
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r2 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r3 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r4
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r5
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r6
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r7 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage r9
```

每个stage必须写输入hash和`complete.json`；输入变化时拒绝覆盖并要求新协议版本。

## 12. 跑不动与证据不足处理

| 情况 | 判断 | 允许处理 | 禁止处理 |
|---|---|---|---|
| 镜像仿真无法注入镜像初值 | 工程接口缺失 | 停止R2，先增加确定性初值/控制接口 | 用相反转角冒充严格镜像 |
| 解析镜像数组不等 | 变换合同错误 | 修transform并重做pilot | 放宽到经验误差 |
| head硬等变但完整力路径失败 | decoder或输入合同错误 | 分层定位geometry/decoder/fallback | 只报head交换子 |
| R1-P不如R1-L | plant本构/参数合同不足 | 报告分歧，查`Gamma/k/c/g` | 把R1-L改名物理本构 |
| 位移好、速度差 | 几何骨干只学到准静态关系 | 判速度门失败；另立动态几何修订 | 用state_core平均掩盖 |
| predicted-active fallback>1% | 活动方向仍不可部署 | 查数值floor、模式和d/v预测；保持原门 | 只报告all或删除活动窗 |
| validation通过、development失败 | 泛化不足 | 停止，不生成confirm | 回看development调ridge |
| confirm失败 | 论文主张不成立 | 完整交付负结果 | 换seed重做盲集 |
| p99>2 ms | 实时门失败 | 预计算投影/向量化，同模型复测 | 改控制周期或减少重复次数 |
| OOM/崩溃 | 资源问题 | 同seed降worker断点重跑 | 丢弃失败轨迹 |

发生任何停止条件时，`solutions.md`必须写：事实、最可能原因、替代解释、修复方案、成本、论文影响和恢复条件。

## 13. 留痕与交付

每次代码修改和每个stage追加`innovation_efd_r1_results/work_log.md`：

```text
编号与时间
协议/代码/输入SHA256
实际命令和环境
修改前后文件hash、函数和原因
测试与数值结果
门禁和停止决定
同seed重跑情况
回滚路径
```

最终交付至少包括：

```text
freeze/
pilot/
data/{train,validation,development,confirm}/
models/
audits/{mirror,seed,readonly,access}/
metrics/
figures/
failure.json
solutions.md
work_log.md
results.json
report.md
delivery.zip
```

图表至少包括四组状态时域曲线、力/载荷、方向/反转、严格镜像审计、H2—geometry—decoder分层等变、四类fallback、分工况包络和门禁总图。

## 14. 对审稿问题的最终对应

R1通过后才能形成以下逻辑：

1. 旧固定H2为什么20步力方向失败：连接几何状态没有被正确预测；
2. 为什么不是任意直接力网络：E3只是上界，R1通过独立几何状态和轴向本构构造力；
3. 改进为什么具有结构性：旋转在相对坐标中不变，镜像由线性约束硬保证，作用—反作用和Q严格闭合；
4. 为什么可用于多工况：在直线、加减速、阶跃转向、单移线和回头弯的新盲集上统一通过；
5. 为什么不能现在进入网络控制：离线development和confirm尚未形成，闭环收益和通信保护仍没有证据。

# EFD实验执行书：Koopman四点力方向与连接几何修正

> 状态：预注册任务书，尚未执行。  
> 目标工程（5080）：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码目录：`revision_2026/koopman/innovation/efd/`  
> 新结果目录：`revision_2026/koopman/innovation_efd_results/`  
> 历史方向实验：`innovation/direction/`与`innovation_direction_results/`只读，不覆盖、不改门。  
> 本轮范围：只做离线20步预测与物理合同验证；不并入LPV、多专家、在线更新、MPC、通信干扰或DoS。

## 1. 本轮只回答什么

本实验只回答一个可证伪问题：

> 在冻结H2直接多时域状态骨干的前提下，能否通过“连接几何修正”或“受限等变方向残差”，恢复四个连接点水平/竖直分力方向和货物拉伸载荷预测，同时保留H2的20步状态预测优势？

若两个候选均不能通过新的development与盲确认门，本轮结论就是：**当前H2状态合同不足以支撑物理一致的连接力方向预测**。此时停止，不继续叠加LPV、多专家、网络或闭环控制。

## 2. 已知事实、待核实前提与不能声称的结论

### 2.1 已知事实

当前D4 validation的10—20步结果为：

| 方法 | state NRMSE | force NRMSE | 货物拉伸载荷 NRMSE | J | 分量方向准确率 | 角度p95 | Q方向准确率 | 反转准确率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| K1/P0 | 0.731216 | 1.340919 | 0.553875 | 0.875337 | 0.835087 | 138.469° | 0.807226 | 0.711851 |
| H2/P1 | 0.273498 | 0.600088 | 0.204377 | 0.359321 | 0.680346 | 158.590° | 0.658032 | 0.620708 |
| P4：非负幅值×H2位移方向 | 0.273498 | 0.502412 | 0.343884 | 0.373265 | 0.695584 | 151.593° | 0.705140 | 0.629843 |
| P5：直接四点力head（归因上界） | 0.273498 | 0.067816 | 0.036783 | 0.126032 | 0.934055 | 43.283° | 0.905540 | 0.835984 |

P4相对P1的四点力误差改善16.277%，但货物拉伸载荷误差恶化68.260%，且方向、Q方向、角度p95和反转门均失败。P5使用同一`x0/u_future`却能学到较好的方向，因此数据中存在可学习的方向信息；这只是归因证据，不等于P5已经物理一致。

### 2.2 当前指标存在的缺口

现有`direction/metrics.py::nrmse_groups()`只计算`state[..., :30]`，没有统计H2输出中真正用于方向解码的：

- `30:38`：四个连接点相对位移；
- `38:46`：四个连接点相对速度。

因此“P4与H2状态误差相同”只说明前30维相同，**不能证明连接几何预测正确**。本轮必须把30—46维拆开评价，不能继续用单一`state`指标掩盖。

### 2.3 执行前必须核实的物理前提

在训练任何新head前，必须从plant源代码和同一步日志核实：

1. `d_i`到底是“车辆连接点指向货物连接点”还是相反；
2. 日志中的`F_i`是货物侧受力还是车辆侧受力；
3. `d_i、v_i、F_i`是否为同一坐标系、同一采样时刻；
4. 连接器是否严格只沿轴向受力，是否含间隙、预紧、滞回、饱和或切向阻尼；
5. 四角点顺序是否始终为`FL, FR, RL, RR`。

若源代码定义和日志不能证明这些前提，停止模型训练，先修数据合同。不能从P4失败直接推断“Koopman学不会方向”。

### 2.4 不能声称的结论

- `Q_FR/Q_LR`是前后向/左右向货物拉伸载荷代理，不是货物裂缝宽度、材料应力或撕裂概率；
- 作用—反作用和Q代数残差为零只证明结构闭合，不证明力预测准确；
- 若只有受限方向残差候选通过，只能称“结构约束的经验力解码器”，不能自动称为真实连接器本构模型；
- 没有车辆侧独立力日志时，作用—反作用只能由代码硬约束，不能称为被双侧测量验证。

## 3. 假设与判伪条件

### H1：连接几何误差是P4方向失败的主因

若用真值连接位移方向解码时方向显著恢复，且H2在`30:38`上的误差/角误差明显大于前30维，则H1得到支持。若真值位移与真值力本身不共线，H1当前形式被否定，应返回连接器本构和日志定义。

### H2：修正几何比任意旋转力向量更适合物理主线

若几何修正候选G-EFD通过全部精度、等变、实时和盲确认门，优先采用G-EFD。它必须把修正后的连接位移作为最终46维状态的一部分输出，不能只在隐藏解码器中偷换几何。

### H3：小角度方向残差可以补偿有限的几何/离散误差

若D-EFD通过全部精度门，且方向修正角中位数不超过15°、p95不超过45°，则说明小残差足以修正。若必须长期大角度旋转才有效，它是在替代错误几何，H3被否定。

### H4：镜像/旋转一致性能够降低工况偏置

若加入结构化坐标变换后，左右弯镜像一致性和未见全局旋转角上的误差同时下降且主任务不退化，则支持H4。只在原始道路朝向上变好、坐标旋转后失效，不算通过。

## 4. 方法合同与对照组

### 4.1 统一输入输出

沿用当前因果合同：

```text
x0       [B, 46]      当前完整状态
u_future [B, 20, 8]   当前时刻已知/规划的未来20步控制
y        [B, 20, 64]
  0:46   S3完整状态
 46:54   四点(Fx,Fy)，顺序FL/FR/RL/RR
 54:56   Q_FR/Q_LR
 56:64   四点力变化率
```

禁止使用未来真值状态、未来真值力、事后工况标签或未来网络状态作为head输入。

### 4.2 必跑方法

| 编号 | 方法 | 用途 | 是否可成为论文主方法 |
|---|---|---|---|
| E0 | 原K1 fixed linear | 线性下限/方向基线 | 否，基线 |
| E1 | 冻结H2/P1 | 当前状态骨干 | 否，骨干 |
| E2 | 新数据重训P4合同 | 复现“非负幅值×冻结几何”失败 | 否，旧方法对照 |
| E3 | 新数据重训P5直接四点力head | 数据可学习性与性能上界 | 否，归因上界 |
| E4 | G-EFD：H2+连接几何修正+非负幅值+物理投影 | 物理优先候选 | 是，优先 |
| E5 | D-EFD：H2+受限方向残差+非负幅值+物理投影 | 性能优先候选 | 有条件 |

旧D4R2上的P0—P5只作为历史参照；所有E0—E5必须在新协议数据上重新评价，E2/E3的head须用新train重训，不能复制旧validation选择结果。

### 4.3 G-EFD：连接几何修正

冻结H2，得到连接位移预测`d_i^H2`。使用相同因果特征预测局部基下的修正量：

\[
n_i^0=\frac{s_i d_i^{H2}}{\|d_i^{H2}\|+\varepsilon},\qquad
t_i^0=J n_i^0,
\]

\[
\Delta d_i=a_i n_i^0+b_i t_i^0,\qquad
\hat d_i=d_i^{H2}+\Delta d_i,
\]

\[
\hat n_i=\frac{s_i\hat d_i}{\|\hat d_i\|+\varepsilon},\qquad
\hat F_i=\operatorname{softplus}(m_i)\hat n_i.
\]

其中`s_i∈{-1,+1}`必须由源代码中的向量定义与货物侧受力方向确定，并在E0冻结，禁止按validation得分选符号。`a_i,b_i,m_i`为20个时域的因果直接多步ridge读出。最终状态输出必须把`30:38`替换为`hat d`；其余状态保持H2。相对速度`38:46`本轮只评价、不修正，避免一次引入第二套本构假设。

G-EFD的主训练目标是连接位移真值和最终四点力，而不是只追求Q：

\[
L_G=L_d+L_F+0.5L_{\cos}+0.2L_Q+0.1L_{eq}.
\]

各项先用train统计量标准化，权重固定，不在validation连续调权。

### 4.4 D-EFD：受限等变方向残差

以H2几何方向构造局部切向基，用一个有界标量残差旋转方向：

\[
\beta_i=\tan(\theta_{max})\tanh(r_i),\qquad
\hat n_i=\frac{n_i^0+\beta_i t_i^0}{\|n_i^0+\beta_i t_i^0\|+\varepsilon},
\]

\[
\hat F_i=\operatorname{softplus}(m_i)\hat n_i.
\]

只允许预注册的`theta_max={15°,30°,45°}`三档；validation按门禁优先选最小角度档，不能增加60°、90°等事后网格。D-EFD不修改H2状态，所以必须额外报告“力方向与自身预测几何不一致角”。

D-EFD的固定损失为：

\[
L_D=L_F+0.5L_{\cos}+0.2L_Q+0.1L_{eq}+0.1L_{corr},
\]

其中`L_corr`惩罚方向修正角；反转准确率只作评价，不能用不可导sign函数直接训练。

### 4.5 统一硬投影

E4/E5共用唯一物理解码函数：

1. 幅值经softplus保证非负；
2. 货物侧四点力为`F_payload,i`；车辆侧为`F_vehicle,i=-F_payload,i`；
3. `Q_FR/Q_LR`只从最终四点货物侧力重构；
4. 力变化率从当前实测力和20步预测力因果递推；
5. 近零位移只允许使用冻结回退规则，不得读取未来方向；
6. 所有预测必须有限，禁止NaN/Inf静默置零。

## 5. 先做物理审计，再训练

### 5.1 E0A：源代码与字段审计

生成`audits/schema_map.json`，逐项记录：

- 46维状态每个索引的名称、单位、坐标系和采样时刻；
- 8维控制的物理含义；
- 四角点顺序；
- `d/v/F`两端定义与符号；
- 连接器间隙、刚度、阻尼、饱和和卸载逻辑；
- 货物侧与车辆侧受力是否均有独立日志。

必须用源文件路径、行号和SHA256支撑，不能只根据变量名猜测。

### 5.2 E0B：真值几何—真值力一致性

只用16条新pilot轨迹，在活动力样本上计算：

\[
\theta_{truth}=\angle(s_i d_i^{truth},F_i^{truth}),\qquad
r_{tan}=\frac{|t_i^\top F_i|}{\|F_i\|+\varepsilon}.
\]

门禁：

- 每个点的角度中位数≤0.5°、p95≤2°；
- 每个点的切向比例p95≤0.02；
- 同一步与`h±1`错位检查必须与日志时序定义一致，不能按最低误差事后选择时移；
- 若双侧力有日志，`max||F_vehicle+F_payload||≤1e-8 N`（或仿真写出精度对应阈值）。

若不通过：停止G-EFD和D-EFD训练，写`solutions.md`。优先排查符号、角点置换、坐标变换、时序错位和plant是否含切向力。只有修正数据合同并重生成pilot后才能继续。

### 5.3 E0C：oracle归因

在pilot上固定真实幅值，分别使用：

1. H2预测位移方向；
2. 真值位移方向；
3. P5预测方向。

若“真值位移方向”仍不能达到真值力的角度p95≤2°，物理前提不成立，停止。若真值位移通过、H2位移失败，才允许把问题归因到H2连接几何。若两者都通过而P4仍失败，优先检查幅值、归一化或点序实现，不训练新方向head掩盖代码错误。

## 6. 新数据协议与证据隔离

### 6.1 数据编号与seed

暂定新协议名`D6-EFD`。请求号段如下，执行E0前必须用结构化`seed/traj_id`字段扫描整个`revision_2026`；若任一碰撞，整段平移到下一未占用连续号段并在生成前冻结，禁止只换碰撞seed。

| split | 轨迹数 | 请求seed | 用途 |
|---|---:|---|---|
| pilot | 16 | 190001—190016 | 字段/物理/资源审计，之后不进入正式指标 |
| train | 256 | 191001—191256 | 拟合归一化、阈值和head |
| validation | 96 | 192001—192096 | 有限网格选择 |
| development | 64 | 193001—193064 | 冻结模型的一次复现门 |
| confirm | 160 | 194001—194160 | 最终盲确认，仅在development通过后生成 |

当前D4R2 train/validation/development均已被用于设计或查看，全部降为`legacy_diagnostic`，不得充当D6-EFD的validation、development或confirm。

### 6.2 轨迹与覆盖

按整条轨迹划分，禁止同一轨迹窗口跨split。每个正式split都必须覆盖：

- R0直线匀速；
- R1加速/制动；
- R2正反阶跃转向与方向切换；
- R3单移线、回头弯及直线—弯道过渡；
- 四点方向反转事件；
- 高货物拉伸载荷窗口；
- 近零连接位移/间隙切换窗口；
- 左右镜像配对轨迹；
- 连接刚度、阻尼、间隙和载荷质量的预注册参数扰动。

最低覆盖门：

- train/validation/development/confirm每个R0—R3至少40/15/10/25条轨迹；
- 每个正式split中8个力分量的正、负活动样本各不少于300个窗口；
- 方向反转事件不少于800/250/160/400个；
- 高载荷窗口不少于200/60/40/100个；
- 每个角点有效方向样本不少于总窗口的20%；
- `ultimate_steps=0`、非有限值=0、shape/单位/时序失败=0。

若某覆盖不足，只允许按预注册追加表整轮追加；不能降低活动力floor、重复切窗或移动split中的轨迹。

### 6.3 必须新增的日志字段

每个仿真步至少保存：

```text
state_s3[46]
control[8]
connector_disp_payload_frame[4,2]
connector_rel_vel_payload_frame[4,2]
force_on_payload[4,2]
force_on_vehicle[4,2]      # 若plant可直接提供，必须保存；不可用则显式标null
payload_yaw, system_yaw
Q_FR, Q_LR
connector_gap, stiffness, damping, saturation flags
scenario, trajectory_id, seed, timestamp
```

不能用`force_on_vehicle=-force_on_payload`生成“独立真值”再宣称双侧验证；该重构值只能用于结构输出。

## 7. 坐标等变合同

### 7.1 左右镜像

镜像`y→-y`时：

- 角点置换`FL↔FR, RL↔RR`；
- 所有二维向量的x分量不变、y分量取反；
- 横摆角、横摆角速度和转角取反；
- 标量速度、纵向加速度、质量和连接参数不变；
- `Q_FR`不因左右镜像换名，`Q_LR`按定义检查符号；最终规则以`contracts.py`的公式单元测试冻结。

### 7.2 全局旋转

把所有位置、位移、速度、力和参考路径同时旋转`{30°,60°,90°}`；航向角同步加旋转角，车辆局部控制量不变。训练仅使用`0°、90°、180°、270°`增强，`30°、60°`留作未见角度等变测试，避免把测试变换泄漏到训练。

### 7.3 等变误差

\[
e_{eq}(T)=\frac{\|f(Tx,Tu)-T f(x,u)\|_2}{\|Tf(x,u)\|_2+\varepsilon}.
\]

硬Q与作用—反作用投影残差应≤`1e-10`；学习部分在未见30°/60°和左右镜像上的等变误差p95必须≤2%。若实现只能对训练过的90°倍数成立，不得声称连续旋转等变。

## 8. 训练、选择和统计规则

### 8.1 特征与模型容量

所有head沿用相同的直接多时域因果特征：

```text
phi_h = [1, x0, u_0, ..., u_(h-1)],  h=1...20
```

新增`feature_builder.py`根据`schema_map.json`完成角度sin/cos编码、向量坐标变换和标准化。主模型只用horizon-wise ridge，不使用任意深层MLP；P5 ridge已经证明该容量足以学习方向，先排除“网络不够大”的混淆。

固定ridge网格：`{1e-8,1e-6,1e-4,1e-2}`。除D-EFD的三档`theta_max`外不增加额外模型网格。所有输出维数、可训练参数量、FLOPs和运行时间单列报告，不能以不同容量做无说明比较。

### 8.2 选择规则

1. 每个网格先用完整train确定性拟合；
2. validation先应用硬门，再在通过者中按`J_force=(force+load+angle_norm)/3`最小选择；
3. 同分时优先更大ridge、更小`theta_max`和更少参数；
4. 选定后做5个轨迹bootstrap seed稳定性检查，但最终模型仍为全train确定性模型，不挑“最好seed”；
5. 模型、阈值、字段合同、代码hash和图表模板冻结后，只读一次development；
6. development通过后保持同一模型不重训，才生成confirm并盲测一次。

### 8.3 统计

- 统计单位是轨迹，不是重叠窗口；
- 主比较为E4/E5相对E0、E1和E2的配对轨迹差；
- 每项给出10,000次轨迹bootstrap 95% CI、配对置换检验和效应量`dz`；
- 多指标p值用Holm校正；
- 报告全部5个bootstrap模型，不只报告代表seed；
- 主结论看10—20步，另报h=1/5/10/15/20和h=10—20误差斜率。

## 9. 指标定义与通过门

### 9.1 必报指标

状态指标拆为：

```text
state_core_0_30
connector_disp_30_38
connector_vel_38_46
state_all_0_46
```

受力指标包括：

```text
four_point_force_NRMSE
Q_FR/Q_LR_NRMSE（货物拉伸载荷）
8分量方向准确率
四点向量角MAE/p95
Q方向准确率
方向反转准确率与反转后恢复步数
高载荷窗口误差
近零位移fallback率
力变化率误差
```

结构/部署指标包括：

```text
作用—反作用残差
Q代数残差
左右镜像/全局旋转等变误差
方向修正角median/p95
divergence率
9窗口批量推理p50/p95/p99
模型参数量与峰值RAM/VRAM
```

### 9.2 validation主门

E4/E5分别判定，必须全部满足：

1. 10—20步综合`J=(state_all+force+load)/3`相对K1改善≥8%，95% CI下界>0；
2. `state_core`相对H2不得恶化>1%；
3. G-EFD的`connector_disp`相对H2改善≥10%，且95% CI下界>0；D-EFD不修改几何，必须如实标记“不适用”，不能拿结构残差替代；
4. force和货物拉伸载荷均不得比H2恶化>5%，且至少一项相对H2改善≥10%；
5. 分量方向、Q方向和反转准确率均不低于K1减1个百分点，且至少两项显著优于K1；
6. 角度p95<K1且绝对值≤90°；
7. E5方向修正角median≤15°、p95≤45°；E4报告修正后的位移方向角，不设隐形放宽；
8. 未见镜像/30°/60°等变误差p95≤2%；
9. Q和作用—反作用代数残差≤`1e-10`，fallback≤1%，divergence不高于H2；
10. 9窗口20步批量预测p99≤2 ms，单次最坏值<20 ms。

### 9.3 development与confirm门

development和confirm不重新选参，重复validation全部硬门，并额外要求：

- 主要改善方向与validation一致；
- `J`改善的95% CI不能跨过预注册的-2%非劣界；
- R0—R3任何单一工况的force或load不得相对H2恶化>10%；
- 左弯与右弯的标准化误差差异≤5%；
- 5个bootstrap模型中至少4个满足方向、force和load的非劣门。

优先级规则：

1. E4通过则优先E4；
2. E4失败、E5通过时，E5只作为结构约束经验候选，论文必须报告几何不一致；
3. 两者都通过且E5明显更优，也不能省略E4；用二者差异解释“物理可解释性—性能”的边界；
4. 两者均失败，停止并保留K1/H2/P5归因，不进入闭环。

## 10. 对应代码修改清单

所有文件均新建于`innovation/efd/`，不得原地修改`innovation/direction/`。

| 文件 | 必须实现的类/函数 | 验收测试 |
|---|---|---|
| `config.py` | `EFDConfig`；目录、seed、网格、门限、预期H2 hash | 配置JSON round-trip，路径不得落入旧结果目录 |
| `schema.py` | `StateField`, `load_schema()`, `validate_corner_order()` | 46/8/64维、单位、坐标系、点序逐项断言 |
| `audit.py` | `hash_tree()`, `audit_seed_collisions()`, `audit_old_readonly()`, `audit_d5_absent()` | 结构化seed扫描；旧目录前后hash一致 |
| `contracts.py` | `EFDPrediction`；完整state、双侧力、Q、rate、方向、修正角 | shape/finite/非负幅值/Q/作用反作用硬断言 |
| `generate_d6efd.py` | `simulate_one()`, `log_connector_truth()` | pilot可复现；同seed hash一致；字段无时移 |
| `coverage.py` | `pilot_contract()`, `formal_contract()` | R0—R3、反转、高载荷、正负方向、近零位移计数 |
| `dataset.py` | `load_split()`, `fit_train_thresholds()`, `trajectory_windows()` | 轨迹不跨split；validation不拟合阈值 |
| `h2_adapter.py` | `load_frozen_h2()`, `predict_h2()` | 与旧H2逐元素误差≤`1e-10`；hash固定为`3828...FDAC` |
| `feature_builder.py` | `causal_feature(h)`, `encode_angles()`, `transform_feature()` | h时域不得出现`u_h`之后控制；角度跨π连续 |
| `transforms.py` | `mirror_lr()`, `rotate_global()`, `inverse_transform()` | 镜像两次/旋转逆变换恢复；角点置换正确 |
| `geometry_audit.py` | `truth_alignment()`, `oracle_ablation()`, `timestamp_audit()` | 手工构造四点case；符号/时移错误可被检出 |
| `magnitude_head.py` | 迁移并修正`DirectAxialMagnitudeHead` | softplus有限、非负；与旧实现回归一致 |
| `geometry_head.py` | `GeometryCorrectionHead.fit/predict()` | 零系数严格退化为H2；输出局部基修正 |
| `direction_head.py` | `BoundedDirectionHead.fit/predict()` | 修正角永不超过`theta_max`；镜像符号测试 |
| `physics_decoder.py` | `decode_forces()`, `reconstruct_load()`, `causal_force_rate()` | Q/作用反作用≤`1e-10`；手工合力与拉伸载荷反例 |
| `predictors.py` | `predict_e0...predict_e5()` | E4/E5统一输出合同；禁止复制Q公式 |
| `train.py` | `fit_grid()`, `bootstrap_stability()`, `freeze_model()` | 不读取development；选择规则可复算 |
| `metrics.py` | 四组状态、受力、方向、反转、等变、修正角和轨迹统计 | 与手算小样本一致；30:46不再遗漏 |
| `evaluate.py` | `evaluate_split_readonly()` | split角色检查；confirm只允许冻结后读取 |
| `report.py` | 自动生成表、horizon曲线、方向角图、镜像图、失败门图 | 图中单位、样本数、CI、split、模型hash齐全 |
| `run.py` | E0—E9阶段状态机 | 前一门失败返回码2并阻止后续stage |

### 10.1 现有代码的已知具体修正

移植旧代码时必须显式处理：

1. 旧`metrics.py::nrmse_groups()`的`px[...,:30]`改成四组状态指标，不能只改标签；
2. 旧`physics_decoder.py::unit_from_displacement()`直接使用`d`，新实现必须使用E0冻结的`s_i`和字段坐标合同；
3. 旧`predictors.py::structured_predictions()`在近零位移时用P0方向回退，新实现必须报告回退来源，且不得让未来基线预测泄漏进E4/E5；
4. 旧`DirectPointHead`继续保留为E3上界，但不得进入E4/E5硬投影后冒充新方法；
5. `Q_FR/Q_LR`只允许`physics_decoder.reconstruct_load()`一份公式；
6. 修正后的`30:38`必须写回E4最终state并参与`state_all`，不能只供force decoder使用。

## 11. 阶段任务树与停止规则

```text
E0 冻结与证据隔离
├─ E0A 源代码/字段/点序/符号审计
├─ E0B seed碰撞、旧目录只读、confirm不存在
└─ 失败：写failure.json+solutions.md，停止

E1 16轨迹pilot
├─ 数据/时序/单位/资源合同
├─ 真值几何—真值力共线审计
├─ oracle方向归因
└─ 失败：先修plant或日志，不训练head

E2 生成D6-EFD train/validation/development
├─ 整轨迹split与覆盖审计
├─ 冻结train阈值/归一化
└─ 失败：只按追加表补覆盖，禁止改floor

E3 冻结H2/K1与旧方法复现
├─ H2逐元素适配回归
├─ 新数据E0/E1/E2/E3基线
└─ P5若明显退化：停止，先查数据/特征，不扩大网络

E4 G-EFD validation
├─ 有限ridge网格
├─ 5 bootstrap稳定性
└─ 不过门：保留负结果，允许独立运行E5

E5 D-EFD validation
├─ theta_max=15/30/45°×ridge
├─ 5 bootstrap稳定性
└─ 不过门：停止，不增加更大角度网格

E6 冻结胜者并一次读取development
└─ 不过门：停止，不生成confirm

E7 生成160条confirm
├─ 使用预冻结seed/场景manifest
└─ 生成失败：同seed断点重跑；不得换失败轨迹

E8 盲确认与统计
└─ 不过门：报告失败，不回到validation调参

E9 图表/报告/代码清单/工作记录交付
└─ 只有E8通过，才另立新MD讨论force observable、LPV或闭环
```

E4和E5互相独立：E4失败不阻止E5，E5失败也不能改变E4的门。只有二者都结束后才按预注册优先级选胜者。

## 12. 计划执行命令

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd\run.py'

& $PythonExe -B $Runner --project-root $ProjectRoot --stage e0
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e1 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e2 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e3
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e4
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e5
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e6
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e7 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage e9
```

每个stage必须幂等：存在`complete.json`且输入hash一致时只读返回；输入hash变化时拒绝覆盖，要求新建协议版本。

## 13. 预计资源与跑不动处理

### 13.1 资源预估

- 数据：pilot后按单轨迹实测字节数投影；正式生成前若投影>20 GiB，停止并只调整日志频率/压缩格式，不删物理字段；
- 内存：单worker峰值目标<2 GiB，8 worker总RAM目标<20 GiB；
- GPU：ridge主流程不依赖GPU；若代码意外调用CUDA，记录原因，不能把GPU差异混入模型比较；
- 时间：pilot必须给出320/576条规模的墙钟时间投影；单stage预计>60 min时分块运行并每50条写`progress.json`。

### 13.2 故障处置表

| 故障 | 事实判断 | 允许处置 | 禁止处置 |
|---|---|---|---|
| 真值力不沿真值位移 | 物理/字段前提错误 | 查plant本构、符号、点序、坐标和时移；修合同后重做pilot | 直接训练大方向head掩盖 |
| P5在新数据上也失效 | 不是结构约束单点问题 | 查输入输出映射、归一化和数据分布；停止E4/E5 | 增大网络、读取development调参 |
| G-EFD几何改善但力不改善 | 幅值或本构不充分 | 报告几何与力解耦；另立显式force observable计划 | 临时改损失权重直到通过 |
| D-EFD只有45°档通过 | 结构修正较大 | 可进development，但必须保留45°风险标签 | 继续加60°/90°网格 |
| D-EFD修正角p95>45° | 在替代错误几何 | 判失败，返回状态/连接本构 | 称为物理一致 |
| 等变测试失败 | 存在坐标偏置 | 修`schema/transforms`并从E1重跑 | 删除未见旋转测试 |
| force好但state_all退化 | 几何修正破坏状态一致性 | 判G失败；保留D候选或拆分新研究问题 | 用前30维state掩盖 |
| confirm失败 | 泛化不成立 | 固化负结果并停止 | 回看confirm调参后重命名为新confirm |
| 推理p99>2 ms | 当前实现部署风险 | 向量化/预计算后同模型重测 | 减少测试重复或改控制周期 |
| OOM/进程崩溃 | 工程资源问题 | 同seed、同配置减worker断点重跑 | 换seed、丢弃失败轨迹 |

任何无法跑出支撑证据的情况，必须立即停止该分支，并在结果目录的`solutions.md`写清：已核实事实、最可能原因、替代解释、可行修复、修复成本、对论文主张的影响和恢复条件。

## 14. 留痕与交付物

每完成一次代码修改或stage，追加`innovation_efd_results/work_log.md`，格式固定：

```text
记录编号、开始/结束时间
任务书SHA256、命令、环境
修改文件
修改前SHA256、修改后SHA256
修改函数/行范围、原因
输入数据manifest/hash
运行测试与数值结果
是否触发门禁/停止
失败是否重跑、重跑是否同seed
回滚路径
```

最终至少交付：

```text
innovation_efd_results/
├── freeze/
│   ├── protocol.json
│   ├── source_hashes.json
│   ├── schema_map.json
│   ├── seed_audit.json
│   └── environment.json
├── pilot/
├── d6efd/
│   ├── train/
│   ├── validation/
│   ├── development/
│   └── confirm/
├── models/
├── metrics/
├── figures/
│   ├── 01_horizon_state4groups.png
│   ├── 02_force_load_horizon.png
│   ├── 03_direction_angle.png
│   ├── 04_reversal_response.png
│   ├── 05_geometry_alignment.png
│   ├── 06_equivariance.png
│   ├── 07_regime_envelope.png
│   └── 08_gate_status.png
├── failure.json
├── solutions.md
├── work_log.md
├── results.json
└── report.md
```

图必须包含单位、split、轨迹数、有效样本数、95% CI、模型hash和门限线；不能只给均值柱状图。

## 15. 与审稿意见的对应关系

本实验可直接回答：

1. 为什么20步H2总体误差改善仍不足：此前没有评价30—46维连接几何，且冻结几何方向导致四点力方向退化；
2. 双线性/复杂模型是否必然更好：本轮固定H2并只改变结构化解码，用相同输入、数据、容量记录来做归因，不预设复杂模型获胜；
3. 改进是否有物理依据：通过真值几何共线审计、非负轴向幅值、作用—反作用、Q代数和等变合同验证；
4. 多步优势是否稳定：给出1/5/10/15/20步、10—20步误差斜率、分工况包络、development和盲confirm；
5. 适用边界是什么：G-EFD优先解释连接几何，D-EFD只允许小角度修正；失败时明确退回数据合同或本构，而不是继续堆模型。

本轮不能回答通信保护、DoS闭环、控制稳定性或真实货物撕裂风险。只有E8盲确认通过，才允许另立后续实验任务书。

# EFD-R1.2执行书：真实基线复现与等变连接预测

> 状态：依据R1.1最新结果修订的新协议草案，尚未执行。  
> 5080工程：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码：`revision_2026/koopman/innovation/efd_r12/`  
> 新结果：`revision_2026/koopman/innovation_efd_r12_results/`  
> 历史只读：`direction`、`efd`、`efd_r1`、`efd_r11`及其全部结果。  
> 本轮范围：真实K1/K2/IRSP/H2复现、物理lift诊断、硬等变连接几何和轴向力解码的离线1—20步验证。盲确认通过前不运行MPC、通信干扰或DoS。

## 1. 为什么不能继续改R1.1

R1.1已经使用`211xxx`数据并多次查看validation。它的任务书、失败结果和代码必须作为历史证据保留，不能在看到S4结果后继续修改门槛或模型并复用同一validation。

因此本文件不是对`efd_r11.md`的覆盖，而是新协议R1.2。R1.1的正式状态保持：S4停止，S5以后未执行，development未读，confirm未生成。

## 2. 最新结果的事实、解释和证据缺口

### 2.1 R1.1 S4数值

10—20步窗口级结果为：

| 方法 | 核心状态 | 连接位移 | 连接速度 | 四点力 | 受拉内力代理 | 综合J |
|---|---:|---:|---:|---:|---:|---:|
| B0线性递推 | 0.027917 | 0.226528 | 0.434827 | 0.246430 | 0.373821 | 0.216056 |
| B1双线性 | 0.100332 | 0.351377 | 2.150102 | 1.171158 | 0.732402 | 0.667964 |
| B2双线性+IRSP | 1.082422 | 1.068685 | 7.802942 | 3.592052 | 2.452046 | 2.375507 |
| B3直接多时域 | 0.183932 | 0.721091 | 1.029606 | 1.070946 | 1.167804 | 0.807560 |
| B4直接四点力 | 沿用B3 | 沿用B3 | 沿用B3 | 0.613696 | 0.321772 | 0.373133 |

可直接确认：

1. 当前简化实现中B0除受拉内力代理外全部最优；
2. B1置零双线性项后J从`0.668`恶化到`6.584`，置换控制后恶化到`11.380`，说明双线性项被使用，但完整B1仍比B0恶化`209%`；
3. B2为满足连续三角界，把`A`缩放到`2.25%`并把双线性项系数缩放为0，J相对B1再恶化约`256%`；
4. B4相对B3的force改善`42.7%`，但相对B0的force仍恶化`149%`；只有受拉内力代理相对B0改善约`13.9%`；
5. A0/A1/A2/M没有训练，因此当前结果不能判断硬等变连接模型是否有效。

### 2.2 R1.1证据链不完整

当前同步的`efd_r11_s2_complete.json`仍显示S2失败：12组局部镜像审计全部因`generate_k2.system_derivative`接口错误没有执行。随后代码中已经增加显式plant RHS绑定，且当前`run.py`按逻辑会阻止S2失败后进入S3；但缺少修复后S2的最终`complete.json`、局部数值和hash。

R1.2的T0必须先从5080同步并核对最终S2证据。若5080也没有修复后通过文件，只能将R1.1 S3/S4降级为`post_hoc_diagnostic`，不能作为正式预注册证据。不能根据“后续阶段已经跑了”反推S2必然通过。

### 2.3 当前B0—B3名称与原论文方法不等价

R1.1代码实际为：

```text
B0: [1, x, u, p] -> x_next                 原始状态线性ARX
B1: [1, x, u, p, u⊗x] -> x_next            原始状态双线性回归
B2: 对上述原始状态矩阵做整体缩放
B3: [1, x0, p, u_0:h] -> x_h               46维直接仿射head
```

它们不是原论文中的固定lift K1、lifted bilinear K2和原IRSP，也没有完整复现历史H2的64维状态—力联合输出、五个轨迹bootstrap和联合选择损失。因此R1.1只能说明这些简化代理模型的优劣，不能直接推翻或证明原K1/K2/K3/H2。

### 2.4 统计与指标缺口

R1.1 S4还存在：

- 以全部窗口micro RMSE为主，长轨迹权重更高，没有按`base_family_id`等权；
- 没有family级CI、效应量、Holm校正和场景等权macro；
- 没有分场景、分horizon、方向、反转和角度指标；
- load尺度由validation真值现算，而不是train-only冻结；
- B0/B1按J选ridge，B3按state_core选ridge，选择目标不统一。

这些缺口不太可能逆转B0相对B3的巨大差距，但会阻止正式论文结论。

## 3. R1.2目的与关键修正

### 3.1 研究目的

R1.2只回答三个问题：

1. 在真实历史实现和完全公平的同数据重训下，linear、bilinear、IRSP和直接多时域方法分别在哪些工况有效或退化？
2. 相对航向周期编码、相对货物几何、连接接触状态和有限控制—状态交互组成的物理lift，能否修复直接多时域映射在弯道和连接切换中的退化？
3. 无论哪个核心状态骨干最好，独立硬等变连接几何和轴向本构能否改善四点力、受拉内力代理和方向？

### 3.2 删除R1.1的错误依赖

R1.1规定“B3必须先优于B0，否则不允许训练连接几何”。这个依赖没有物理必要性：连接几何head不读取B3未来几何，可以和任一有限核心状态骨干组合。

R1.2改为：

- 基线阶段负责找出最强核心状态骨干，不预设必须是H2；
- 物理lift失败时可以使用真实K1或原始状态线性ARX作为核心；
- 同一个独立连接几何骨干分别与候选核心组合，不为不同核心偷偷增加数据或容量；
- 最终主候选必须击败所有合格基线中的最强者，而不是只击败一个较弱B3。

若最终最佳核心是原始状态ARX且完整方法也不能击败它，论文不能继续把Koopman作为核心创新。

## 4. 可证伪假设

### H0：代码适配和数据合同可信

真实历史模型适配器必须在历史D4R缓存上逐元素复现旧预测；新pilot的解析、局部镜像、轴向oracle、角点顺序和坐标合同全部通过。

### H1：原bilinear的实际生效区域可被识别

lifted bilinear相对fixed-lift linear必须在至少两个预注册高控制/转弯工况改善，且置零`N_j`和置换控制会显著破坏性能。否则删除bilinear核心贡献。

### H2：原IRSP提供性能相关的连续输入保护

IRSP必须在连续输入域证书成立时降低发散或最坏误差，而且不能通过几乎清零动力学获得证书。否则删除IRSP贡献。

### H3：相对物理lift改善宽工况直接多时域预测

物理lift直接head必须相对最强公平核心基线改善10—20步状态，并在弯道/切换场景复现，而不是只在总体micro指标上变好。

### H4：硬等变连接几何和轴向解码形成最终有效改进

在选定核心骨干不变时，硬等变几何必须改善连接位移/速度、四点力、受拉内力代理、方向和未见镜像/旋转泛化，并通过development和盲confirm。

H1—H3互相独立；某一项失败不阻止H4。只有数据/物理合同H0失败才阻断全部模型训练。

## 5. 新数据与防污染

### 5.1 seed块

`201xxx`和`211xxx`全部降级为历史或诊断数据。R1.2依次选择第一个结构化字段零碰撞的块：

```text
候选BASE = 221000, 231000, 241000
```

| split | 独立base数 | seed |
|---|---:|---|
| pilot | 24 | BASE+1—BASE+24 |
| train | 256 | BASE+1001—BASE+1256 |
| validation | 96 | BASE+2001—BASE+2096 |
| development | 64 | BASE+3001—BASE+3064 |
| confirm | 160 | BASE+4001—BASE+4160 |
| bootstrap | 5 | BASE+5001—BASE+5005 |
| statistics | 1 | BASE+5999 |

所有base、解析镜像和旋转副本必须同split；增强副本不增加独立n。development生成后由访问守卫锁定，只有validation候选和全部阈值冻结后才能读取。confirm只在development通过后生成。

### 5.2 工况覆盖

每个正式split覆盖：

- 直线匀速；
- 加速、制动、间隙加载/卸载；
- 正反阶跃转向和方向切换；
- 单移线、回头弯、直线—弯道过渡；
- 连接刚度/阻尼/间隙、货物质量和轮胎摩擦变化；
- 四点八分量正负活动、方向反转、高受拉内力代理。

覆盖和统计同时报告：base family数、场景数、互不重叠20步窗、每分量正负活动、反转数和高载荷数。主统计单位为base family，不能用长轨迹更多窗口增加统计权重。

## 6. 方法矩阵与准确命名

### 6.1 历史冻结连续性组

| 编号 | 方法 | 作用 |
|---|---|---|
| C0 | 历史冻结K1 fixed-lift linear | 旧论文接口连续性和新数据外推 |
| C1 | 历史冻结K2 lifted bilinear | 旧bilinear外推 |
| C2 | 历史冻结K3 bilinear+IRSP | 旧IRSP外推 |
| C3 | 历史冻结H2 64维direct head | 旧直接多时域外推 |

C0—C3不重训，不因新数据表现改变旧模型；只报告外推。执行前必须在历史D4R上与保存cache逐元素回归。

### 6.2 同数据公平重训组

| 编号 | 准确名称 | 结构 |
|---|---|---|
| F0 | raw-state linear ARX | `[1,x,u,p]→x+` |
| F1 | fixed-lift linear Koopman | 历史固定basis、线性受控lift递推 |
| F2 | lifted bilinear Koopman | 历史basis、`Az+Bu+Σu_jN_jz` |
| F3 | lifted bilinear+IRSP | F2加原IRSP和连续输入审计 |
| F4 | exact H2 direct multi-horizon | 64维联合输出、五family bootstrap、历史联合损失 |
| F5 | direct force upper bound | 同因果输入直接预测四点力/Q/rate |

F0不是Koopman，必须保留为强简单基线。F1—F4必须复用历史basis、输出切片、decoder和损失定义；仅允许统一加入预测时已知的`p_static`仿射项，并给出无`p_static`消融。

所有方法获得相同train family、`x0`、`u_future`、`p_static`、ridge网格、控制范围和统计预算。若某方法不能接受某字段，必须通过固定适配器消费或明确列为输入劣势，不能静默删除。

### 6.3 物理lift直接多时域组

使用与exact H2相同的64维目标（46维状态、8维四点力、2维Q和8维force-rate）、horizon-wise线性读出、五个family bootstrap和联合选择损失，仅逐组增加预注册特征：

| 编号 | 特征组 | 目的 |
|---|---|---|
| P0 | 原始`x0+p+u_prefix` | 复现R1.1 B3 |
| P1 | P0+相对航向`sin/cos` | 修正角度周期与跨`±pi`问题 |
| P2 | P1+货物体坐标相对位置、当前四点d/v | 增加连接几何可辨识性 |
| P3 | P2+间隙穿透、轴向速度、加载/卸载和活动状态 | 表达分段连接动力学 |
| P4 | P3+冻结低阶控制—状态交互 | 表达弯道输入耦合，主物理lift候选 |

P4只允许以下交互，不使用全量`8×46`任意乘积：

```text
每车: v_x*delta, v_x*a_x, r*delta, v_y*r
每连接点: penetration*normal_speed, active*normal_speed
全系统: mean(v_x)*mean(delta), payload_yaw_rate*steer_difference
```

全部连续特征使用train-only尺度；`active`只由当前已知d/v和参数计算，不使用未来truth或事后场景标签。P0—P4参数量、条件数和运行时间单列。

### 6.4 独立连接几何与解码组

核心状态使用validation冻结的最强有限骨干；连接几何不读取该骨干未来`30:46`输出。

| 编号 | 方法 | 作用 |
|---|---|---|
| G0 | 相对几何head，无增强、无硬投影 | 相对坐标贡献 |
| G1 | G0+解析镜像增强，无硬投影 | 数据增强贡献 |
| G2 | 硬镜像等变几何+学习非负幅值 | 几何与本构分离 |
| M | 硬镜像等变几何+轴向物理解码 | 最终论文候选 |

同一G2/M几何输出分别与F0、F1和选中的最强核心组合，仅改变`state_core`拼接，不重复训练几何head。这样可以判断最终收益来自核心骨干还是连接几何。

## 7. 真实实现复现门

新数据生成前必须完成：

1. C0在历史D4R上与K1保存cache逐元素最大误差`<=1e-10`；
2. C1/C2在历史D4R上与旧K2/K3保存结果逐元素误差`<=1e-10`；
3. C3加载原H2模型，在历史D4R上复现64维输出和旧指标，float64最大误差`<=1e-10`；
4. F1/F2的固定basis和输出decoder与历史实现调用同一代码，不复制一份近似公式；
5. IRSP公式、输入盒、矩阵切片、非正规性和连续证书均与原论文定义对应；
6. 方法清单自动输出实际特征维数、lift维数、参数量和输入字段。

任一不能复现时停止正式比较，只修适配器。禁止用名称相同的简化代理替代后继续。

## 8. 指标与统计修正

### 8.1 train-only冻结量

状态、力、Q、force-rate、活动floor和每个物理lift特征的均值/尺度全部只由train计算。validation/development/confirm真值不得用于重新计算归一化分母。

### 8.2 三种统计口径

每个指标同时报告：

- `micro_window`：全部互不重叠20步窗；
- `family_macro`：先按base family聚合，再等权平均，作为主口径；
- `scenario_macro`：先按场景聚合，再等权平均，防止100 m长轨迹主导。

主要结论使用family级paired bootstrap 95% CI、配对置换检验、效应量和Holm校正。模型选择不能只看micro RMSE。

### 8.3 必报指标

- `h=1/5/10/15/20`及`1—5/10—20`的state_core、d、v、state_all；
- 四点力、Q、force-rate误差；
- 八分量方向准确率、向量角度MAE/p95、Q方向、反转准确率和恢复步数；
- 直线、加减速、阶跃、单移线、回头弯、转弯进出和参数变化分层；
- 非有限、发散、暂态放大、条件数、参数量和p50/p95/p99运行时间；
- 解析镜像、未见30°/60°旋转和左右偏置。

综合指标固定为：

\[
J=(J_{state\_all}+J_{force}+J_{load})/3.
\]

不能因某一候选有利改变权重。

## 9. 阶段与硬门

### T0：R1.1证据链和历史只读冻结

- 同步5080最终S2、S3、S4、work_log和代码hash；
- 若修复后S2通过文件缺失，将R1.1 S3/S4标记为诊断；
- 冻结R1.2协议、代码、环境、候选seed和全部历史树hash。

### T1：真实历史适配器回归

运行第7节全部逐元素门。失败则停止，不生成R1.2 pilot。

### T2：24条新pilot

- 24/24有限、ultimate=0；
- 解析镜像数组`<=1e-12`；
- 12组0.4 s局部镜像至少11组通过R1.1冻结门；
- 轴向oracle最大误差`<=2e-3 N`；
- 8组100 m长时诊断只按局部合同、事件一致性和非有限阻断。

### T3：新train/validation/development

生成`256/96/64`独立base；覆盖、时序、单位、角点、参数范围和family统计全部通过。development只生成并加锁。

### T4：C0—C3外推与F0—F5公平重训

本阶段不因F4失败阻断H4。必须输出：

- 各方法family/scenario/horizon指标；
- F2的`N_j=0`和控制置换；
- F3连续证书、缩放比例和性能Pareto；
- F4五bootstrap和完整64维联合输出；
- F5相对最强基线，而不是只相对较差F4。

H1 bilinear通过门：相对F1的10—20步J改善`>=8%`且CI下界`>0`；至少两个高控制/转弯场景改善`>=10%`；置零N项恶化`>=5%`；安全指标不恶化超过3%。

H2 IRSP通过门：连续输入证书成立；`gamma_A>=0.8`、`gamma_N>=0.5`，避免以删除动力学通过；发散/最坏误差至少一项改善`>=10%`；J和state/force/load均不恶化超过3%。

失败只删除相应论文主张，不阻止T5/T6。

### T5：P0—P4物理lift

按P0→P4逐项运行，选择“满足全部门的最小特征组”，不能只选最低validation误差的最大模型。

H3通过门：

- 10—20步state_core相对F1改善`>=8%`且family CI下界`>0`；
- 相对F0/F1/F2/F4中最优state_core至少非劣，恶化不超过1%；
- 弯道、转向切换、连接加载/卸载至少两类改善`>=10%`；
- 直线和加减速不恶化超过3%；
- divergence不高于最强基线，五bootstrap至少4个复现；
- 9候选×20步p99`<=2 ms`，最大`<20 ms`。

P0—P4全部失败时，核心骨干回退到F0/F1/F2/F4中family-macro state_core最优且有限者，仍允许T6。论文删除“物理lift改善核心状态”主张。

### T6：G0/G1/G2/M连接几何与力

M必须同时满足：

1. 相对选定核心原输出，连接位移/速度分别改善`>=30%/10%`，CI下界`>0`；
2. 相对所有合格基线中综合J最优者，10—20步J改善`>=8%`且CI下界`>0`；
3. 四点力和受拉内力代理相对最强基线均改善`>=10%`，CI下界`>0`；
4. state_core与选定核心逐元素一致，不得因几何head改变；
5. 八分量/Q/反转准确率均不低于最强基线减1个百分点，至少两项显著改善；
6. 角度p95小于最强基线且`<=60°`；
7. 未见镜像/30°/60°的force/load恶化不超过5%；
8. G2相对G1在未见变换至少一项改善`>=5%`且CI下界`>0`，否则只保留结构保证；
9. predicted-active fallback`<=1%`，unresolved-active`<=0.1%`；
10. Q、作用—反作用、Reynolds交换子和合成路径满足代数门；
11. 五bootstrap至少4个通过，运行时间通过实时门。

若G2通过、M失败，只能说明学习幅值结构有效；停止M并另立本构协议，不进入本轮confirm。

### T7：一次读取development

冻结候选、模型、归一化、阈值、代码和报告脚本后读取一次。重复T6全部门，并要求任一场景force/load相对最强基线恶化不超过10%，左右基础误差差异不超过5%。

### T8：新盲confirm

T7通过后才生成160个base。一次性评估全部冻结基线、消融和M；失败后不回调并复用同一confirm。

### T9：交付和论文决策

自动输出：

- 方法真实定义与输入表；
- 各方法优势/退化场景；
- bilinear和IRSP保留/删除决定；
- core、geometry、decoder分层贡献；
- validation/development/confirm统计；
- 失败边界、代码hash、工作记录和图表。

只有T8通过后才能另立闭环与网络实验MD。

## 10. 代码修改清单

新建`innovation/efd_r12/`，不得覆盖R1.1：

| 文件 | 必须实现 | 验收 |
|---|---|---|
| `config.py` | 221xxx候选seed、方法矩阵、门槛和目录 | round-trip、协议hash |
| `history_audit.py` | R1.1证据同步、历史树hash和数据角色 | 缺失证据显式降级 |
| `legacy_adapter.py` | C0—C3真实模型加载 | 历史cache逐元素`<=1e-10` |
| `fixed_lift.py` | 调用历史fixed basis，不复制近似式 | basis逐元素回归 |
| `fair_baselines.py` | F0—F5统一输入和训练预算 | 名称、维度和输入自动审计 |
| `bilinear_audit.py` | N置零、控制置换、条件数和工况贡献 | 机制门可复算 |
| `irsp_audit.py` | 原IRSP、连续输入证书、缩放Pareto | 切片和输入盒单测 |
| `physical_lift.py` | P0—P4特征组、sin/cos、相对几何和有限交互 | 奇偶、周期、无未来truth |
| `core_selector.py` | family-macro词典序选核心 | P失败可合法回退，不读取development |
| `equivariant_features.py` | 货物体相对几何和R_phi | 旋转误差`<=1e-12` |
| `geometry_backbone.py` | G0—G2/M共用20步d/v head | 不读核心未来几何 |
| `reynolds.py` | 硬镜像投影 | 交换子`<=1e-12` |
| `axial_decoder.py` | plant唯一轴向公式、Q和反力 | truth oracle`<=2e-3 N` |
| `fallback.py` | 四类fallback和因果回退 | 不读取未来truth |
| `normalization.py` | train-only状态/力/Q/load尺度 | validation真值不可写尺度 |
| `metrics.py` | micro、family、scenario及方向指标 | 小样本手算 |
| `statistics.py` | family bootstrap、置换、Holm和效应量 | 固定统计seed |
| `access_guard.py` | development/confirm状态机 | 越权退出码2 |
| `run.py` | T0—T9幂等阶段 | 前门失败阻断依赖阶段 |
| `report.py` | 方法定义、horizon、场景、机制和门图 | CSV/图/hash一致 |

必须新增测试：

```text
test_legacy_k1_cache_reproduction
test_legacy_k2_k3_cache_reproduction
test_legacy_h2_64d_reproduction
test_method_names_match_actual_features
test_train_only_normalization
test_family_macro_not_length_weighted
test_scenario_macro_equal_weight
test_angle_sincos_wraparound
test_physical_lift_mirror_parity
test_bilinear_zero_n_and_control_permutation
test_irsp_matrix_slices_and_continuous_box
test_geometry_does_not_read_core_future_geometry
test_axial_decoder_truth_oracle
test_fallback_has_no_future_truth
test_development_confirm_access_guard
```

## 11. 运行命令

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd_r12\run.py'

& $PythonExe -B $Runner --project-root $ProjectRoot --stage t0
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t1
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t2 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t3 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t4
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t5
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t6
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t7
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t8 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage t9
```

## 12. 跑不动和停止处理

| 情况 | 允许处理 | 禁止处理/结论 |
|---|---|---|
| R1.1修复后S2文件缺失 | 标记R1.1后续为诊断，R1.2用新pilot重验 | 不反推“肯定通过” |
| 历史cache不能逐元素复现 | 修适配器、dtype、normalizer和basis路径 | 不用简化代理冒充原模型 |
| F0仍显著最优 | 保留为强基线，继续检验几何head | 最终M不胜F0则删除Koopman核心创新 |
| F2使用N项但总体退化 | 报生效工况与代价 | 不称bilinear总体有效 |
| IRSP需`gamma_A<0.8`或`gamma_N<0.5` | 报告证书—性能Pareto | 不把删动力学称为有效保护 |
| P4只改善micro | 查长轨迹权重和场景分解 | family/scenario门不过即失败 |
| 所有P0—P4失败 | 回退最强核心，继续G/M | 删除物理lift核心收益主张 |
| 几何d改善但v失败 | 查动态特征、时序和阻尼合同 | velocity门不过，M失败 |
| G2通过、M失败 | 另立本构协议 | 不把学习幅值称为真实本构 |
| validation过、development失败 | 停止、保存负结果 | 不生成confirm |
| confirm失败 | 完整交付 | 不换seed复用盲集 |
| OOM/崩溃 | 同seed降worker、分块、断点续跑 | 不删除失败轨迹或缩短20步 |

停止时`solutions.md`必须写事实、最可能原因、替代解释、修复成本、论文影响和恢复条件。每次修改和每个阶段必须追加`work_log.md`，记录协议/代码/输入hash、实际命令、修改函数、测试、同seed重跑、门禁决定和回滚路径。

## 13. 最终论文决策规则

1. F2通过H1，才保留bilinear为贡献；否则它只作为工况边界。
2. F3通过H2，才保留IRSP/证书贡献；否则从标题、摘要和贡献删除。
3. P4通过H3，才称物理lift改善核心多步预测；否则核心回退。
4. M通过T6—T8，才称硬等变连接几何与轴向解码改善多物理20步预测。
5. 最终M必须相对最强简单基线F0也通过综合收益门；只比较差B3好不够。
6. 没有材料、截面、连接区损伤或独立车辆侧传感量时，只报告货物前后/左右受拉内力代理，不能推断真实撕裂、裂纹或安全等级。

R1.2的终点不是证明预设方法正确，而是用真实实现、公平数据和盲确认决定：原bilinear/IRSP是否保留，核心骨干应该选谁，以及硬等变连接预测是否足以成为论文的新Koopman主线。

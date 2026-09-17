# EFD-R1.3执行书：方法身份分离与等变连接预测

> 状态：依据R1.2 T1方法身份审计修订的新协议草案，尚未执行。  
> 5080工程：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码：`revision_2026/koopman/innovation/efd_r13/`  
> 新结果：`revision_2026/koopman/innovation_efd_r13_results/`  
> 历史只读：`efd_r1`、`efd_r11`、`efd_r12`、原`compare`、原`03_irsp`及其结果。  
> 核心原则：原论文31维/2输入IRSP与新四车92维/8输入Koopman是两条独立证据链，禁止再使用同一个“K3”名称或互相替代artifact。

## 1. 最新状态

### 1.1 R1.2执行情况

R1.2只执行到T1：

- T0通过，R1.1修复后S2已核实为`12/12`通过；R1.1 S3/S4可以保留为正式证据；
- R1.2选择的`221000` seed块零碰撞，但没有生成R1.2 pilot、train、validation、development或confirm；
- T1在方法身份门停止，没有继续生成数据。

因此R1.2停止不是预测性能失败，而是发现任务书把两个不同模型错误合并。

### 1.2 方法身份审计事实

原`compare_pipeline.py`中的四车K3是：

```text
名称：structured low-rank fixed-lift bilinear
非恒定lift状态：92
控制输入：8
base_transition: [101,93]
bilinear: [460,93]
IRSP投影：没有
```

原论文实际IRSP artifact是：

```text
来源：revision_2026/03_irsp，TF14
lift状态：31
控制输入：2
raw/projected A: [31,31]
raw/projected B: [31,62]
与四车compare K3直接可迁移：否
```

所以以下等式不成立：

```text
compare K3 ≠ 原论文 bilinear+IRSP K3
```

R1.2要求复现“历史四车K3+IRSP artifact”，但项目中没有这个artifact。按方法身份门停止是正确的。

### 1.3 原论文IRSP新增审计

原TF14 IRSP在96个采样控制点上把有效谱半径最大值压到约`0.998`，采样缩放系数约`0.2466`；但连续输入盒的二范数审计为：

| 指标 | 数值 |
|---|---:|
| `rho(A_projected)` | 0.992000 |
| `||A_projected||_2` | 1.098003 |
| bilinear norm budget | 0.228110 |
| triangle upper bound | 1.326113 |
| target radius | 0.998 |
| continuous certificate feasible | 否 |

因为`A_projected`自身二范数已经大于`0.998`，即使把全部双线性矩阵缩放为0，也不能获得原稿声称的欧氏诱导范数连续域界。

这与审稿人对Eq. (22)、非正规矩阵和有限采样证书的质疑一致。当前只能声称“采样控制集上的谱半径正则化”，不能声称“连续输入域收缩证书”或用它支撑完整闭环ISS/UUB。

## 2. 本轮目的和路线决定

### 2.1 两条证据链彻底分开

#### 证据链A：原论文31维/2输入模型

只核实原论文bilinear和IRSP实际做了什么、能保留什么表述。它不参加新46维四车连接预测器的主性能排名，也不作为新几何模型的核心骨干。

#### 证据链B：新四车46维状态/8输入模型

比较raw linear、fixed-lift linear、full bilinear、structured bilinear、direct multi-horizon、物理lift和硬等变连接几何。它负责选择是否替换原论文Koopman预测部分。

两条链可以同时写入论文讨论，但不能共享模型编号、维度、输入、训练数据或证书结论。

### 2.2 IRSP路线决定

本轮不新造“四车IRSP”作为主线，也不让IRSP身份问题阻断等变连接模型。理由是：

1. 原论文IRSP连续证书已经失败；
2. 给92维/8输入四车lift重新设计IRSP会形成另一项高成本新研究，且可能再次以大幅缩放破坏预测；
3. 审稿人当前最需要的是可信的预测收益、受力结果和方法消融，而不是新增一套未经验证的投影。

因此原IRSP只保留为历史审计/负结果。若以后确实要恢复连续域证书，必须另立独立协议，不能与R1.3共用validation。

### 2.3 本轮唯一主候选

> 选择真实、有限且表现最好的四车核心状态骨干，在不读取其未来连接几何的条件下，独立预测货物体坐标系四点连接位移和相对速度，硬编码左右镜像等变，再用轴向连接器本构重构四点力和货物前后/左右受拉内力代理。

暂称：**硬等变连接几何增强的Koopman多时域预测器**。只有最终核心确属Koopman且盲确认通过时才保留“Koopman”名称；若最终核心是raw-state ARX，则必须换成“物理结构化多时域预测器”。

## 3. 审稿要点对齐矩阵

| 审稿要点 | R1.3动作 | 可关闭证据 |
|---|---|---|
| bilinear优势不明显 | 在真实92维fixed lift上比较linear/full/structured bilinear，并做N项置零和控制置换 | 分场景、分horizon、family CI及机制消融 |
| IRSP连续域证书不足 | 单独审计TF14 31/2 IRSP；承认当前连续证书失败 | 矩阵范数、输入盒、triangle bound和论文删改决定 |
| K2/K3可能不如K1 | 最强简单/线性基线作为必须击败对象 | 不是只和弱模型比较的盲确认 |
| force结果与主张冲突 | 同时评价四点力、Q、方向、反转和峰值，不允许J掩盖force退化 | state—force—load Pareto和安全非劣门 |
| 创新不足 | 新方法只针对已定位的连接几何/方向缺口 | core—geometry—decoder分层消融 |
| 统计不足 | family等权、场景等权、多seed、CI、检验、效应量 | validation/development/confirm三层证据 |
| 仿真证据边界 | 只报告受拉内力代理，不推断真实材料撕裂 | 变量定义、单位和禁止性表述 |

本轮不回答通信保护、delay compensation、DoS和闭环稳定性；只有离线盲确认通过后另立网络控制实验。

## 4. 准确方法注册表

所有代码、CSV、图、日志和论文表格必须使用下列唯一ID，禁止单独写“K1/K2/K3”。

### 4.1 原论文链A

| ID | 准确名称 | 观测/lift/输入 | 角色 |
|---|---|---|---|
| `A-LIN31-U2` | TF14 linear reference | 24/31/2 | 原论文线性对照 |
| `A-BIL31-U2` | TF14 raw bilinear | 24/31/2 | 原论文bilinear项 |
| `A-IRSP31-U2` | TF14 sampled-IRSP bilinear | 24/31/2 | 只作历史采样投影审计 |

`A-IRSP31-U2`不得标记为continuous-certified。报告字段必须同时包含：`sampled_radius_passed`、`continuous_norm_passed`和`paper_claim_allowed`。

### 4.2 四车链B

| ID | 准确名称 | 状态/lift/输入 | 角色 |
|---|---|---|---|
| `V-ARX46-U8` | raw-state linear ARX | 46/46/8 | 强简单基线，不称Koopman |
| `V-FL92-U8` | fixed-lift linear Koopman | 46/92/8 | 默认Koopman基线 |
| `V-FB92-U8` | full fixed-lift bilinear Koopman | 46/92/8 | 全8输入—lift耦合 |
| `V-SB92-U8` | structured low-rank fixed-lift bilinear | 46/92/8 | 原compare K3，明确无IRSP |
| `V-H2-64-U8` | exact direct multi-horizon 64-output | 46输入状态/8控制 | 历史H2完整复现 |
| `V-F5-U8` | direct force upper bound | 46/8 | 可学习性上界，非物理主方法 |
| `V-P0`—`V-P4` | physical-lift direct multi-horizon | 见第7节 | 核心状态候选 |
| `V-G0/G1/G2/M` | connector geometry candidates | d/v/F/Q | 最终结构候选 |

程序启动时必须写`method_registry.json`并断言ID、状态维数、lift维数、控制维数、artifact路径、是否IRSP和是否允许论文证书表述。任何ID与实际shape不一致立即退出码2。

## 5. 数据与证据隔离

### 5.1 seed

R1.2的`221000`只完成seed审计，没有生成任何新数据。为避免协议版本混淆，R1.3不复用该块，依次选择：

```text
候选BASE = 231000, 241000, 251000
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

R1.1的211xxx和R1.2已查看的身份审计全部只作历史设计证据，不参与R1.3模型选择。

### 5.2 工况

四车链B覆盖：直线匀速、加速/制动、间隙加载/卸载、正反阶跃转向、单移线、回头弯、弯道进出、连接参数/货物质量/轮胎摩擦变化、八分量正负活动、方向反转和高受拉内力代理。

原论文链A只在其原生24维观测和2维输入合同上复算历史结果；不得把46维/8输入数据强行裁剪后喂给TF14并称为公平对比。

## 6. 链A：原论文bilinear/IRSP审计

### 6.1 只读复现

从冻结TF14代码和artifact复现：

- linear、bilinear、sampled-IRSP的一步和1—12步预测；
- 96个控制样本的有效谱半径max/p95/mean；
- noIRSP闭环消融的原始指标；
- 31维lift、2输入、normalizer和控制盒；
- 论文Fig. E1和对应表的输入hash。

复现误差应`<=1e-10`或与历史float32二进制一致。复现失败只修链A适配器，不修改原artifact。

### 6.2 连续域审计

必须报告：

\[
\|A^+\|_2,\quad \sum_j \bar u_j\|N_j^+\|_2,
\quad \|A^+\|_2+\sum_j\bar u_j\|N_j^+\|_2.
\]

当前冻结结果为`1.3261>0.998`，因此R1.3预注册的论文处理为：

1. 删除“continuous input-domain contraction certificate”；
2. 删除IRSP对完整闭环ISS/UUB的直接支撑；
3. 将IRSP改写为“sampled spectral-radius regularization”，并明确它只覆盖采样控制集；
4. 若noIRSP没有实质退化，IRSP从标题、摘要和主贡献删除，只在附录/负结果中保留。

本轮不根据新结果重新选择投影半径、控制采样点或gamma。

### 6.3 链A不阻断链B

链A复现失败、IRSP连续证书失败或noIRSP无收益，都不阻止四车连接预测实验。它们只决定原论文IRSP主张是否删除。

阶段状态必须区分`audit_completed`和`scientific_claim_passed`：链A历史输出成功复算但连续证书失败时，U1进程应返回0并写`audit_completed=true, scientific_claim_passed=false`，从而允许U2继续；只有artifact缺失、历史输出无法复算或身份/shape不明时才返回2。

## 7. 链B：四车预测方法

### 7.1 历史实现回归

在历史compare数据/cache上逐元素复现：

- `V-ARX46-U8`和`V-FL92-U8`冻结预测；
- `V-FB92-U8` full bilinear；
- `V-SB92-U8` structured low-rank bilinear；
- `V-H2-64-U8`的64维输出、五bootstrap和历史联合损失。

最大误差`<=1e-10`。不再要求不存在的“四车IRSP artifact”。

### 7.2 公平重训

上述方法使用相同R1.3 train family、`x0[46]`、`u_future[20,8]`、已知`p_static`、ridge预算和统计方法重训。历史冻结版本另列为external transfer，不和公平重训混表。

bilinear机制门：

- `V-FB92-U8/V-SB92-U8`相对`V-FL92-U8`的10—20步J改善`>=8%`且family CI下界`>0`；
- 至少两个高控制/弯道工况改善`>=10%`；
- 推理时N项置零使J恶化`>=5%`；
- 轨迹内控制置换显著破坏预测；
- force/load/方向/发散不得恶化超过3%；
- 至少4/5 bootstrap复现。

不通过则删除bilinear核心贡献，但仍允许选择最强linear/ARX核心继续几何模型。

### 7.3 物理lift直接多时域

使用与exact H2相同的64维目标和联合损失：

| ID | 新增特征 |
|---|---|
| `V-P0` | 原始`x0+p+u_prefix` |
| `V-P1` | 相对航向`sin/cos` |
| `V-P2` | 货物体相对位置、当前四点d/v |
| `V-P3` | 间隙穿透、轴向速度、加载/卸载、当前活动状态 |
| `V-P4` | 冻结低阶控制—状态交互 |

P4只允许：每车`v_x*delta, v_x*a_x, r*delta, v_y*r`；每连接点`penetration*normal_speed, active*normal_speed`；系统级`mean(v_x)*mean(delta), payload_r*steer_difference`。

通过门：相对`V-FL92-U8`的state_core改善`>=8%`且CI下界`>0`；相对全部核心中的最优state_core非劣`<=1%`；至少两个弯道/切换工况改善`>=10%`；直线不恶化超过3%；五bootstrap至少4个通过。

P0—P4失败不阻止连接几何；核心回退到`V-ARX46-U8/V-FL92-U8/V-FB92-U8/V-SB92-U8/V-H2-64-U8`中family-macro state_core最优且有限者。

### 7.4 硬等变连接几何

最终核心只输出前30维车辆—货物核心状态。连接位移/速度由独立head预测：

\[
[\hat d_h,\hat v_h]=W_{eq,h}\phi_h(x_0,u_{0:h-1},p),
\quad h=1,\ldots,20.
\]

其中`phi`使用货物体相对坐标、相对航向sin/cos、当前d/v、控制前缀和已知参数；`W_eq`经Reynolds投影满足左右镜像交换子。

| ID | 方法 |
|---|---|
| `V-G0` | 相对几何，无增强、无硬投影 |
| `V-G1` | G0+解析镜像增强 |
| `V-G2` | 硬等变几何+学习非负幅值 |
| `V-M` | 硬等变几何+plant一致轴向解码 |

同一几何输出分别与`V-ARX46-U8`、`V-FL92-U8`和最强核心拼接，禁止为某核心重新调几何head。

### 7.5 最终主门

`V-M`必须全部满足：

1. 连接位移/速度相对选定核心原输出改善`>=30%/10%`，CI下界`>0`；
2. 10—20步J相对所有合格链B基线中的最优者改善`>=8%`，CI下界`>0`；
3. force和受拉内力代理相对最强基线均改善`>=10%`，CI下界`>0`；
4. state_core与选定核心逐元素一致；
5. 八分量方向、Q方向和反转准确率不低于最强基线减1个百分点，至少两项显著改善；
6. 向量角度p95小于最强基线且`<=60°`；
7. 未见镜像/30°/60°变换的force/load恶化不超过5%；
8. G2相对G1在未见变换至少一项改善`>=5%`且CI下界`>0`，否则只允许结构保证；
9. predicted-active fallback`<=1%`，unresolved-active`<=0.1%`；
10. Q、作用—反作用、Reynolds交换子和完整路径代数误差满足`1e-10`门；
11. divergence不高于最强核心，非有限率为0，五bootstrap至少4个通过；
12. 9候选×20步p99`<=2 ms`、最大`<20 ms`。

G2通过、M失败时，停止M，只能保留经验幅值候选，不得称为plant本构复现。

## 8. 统一统计与数据合同

所有状态、力、Q、load、force-rate、活动floor和物理lift尺度只由train冻结。validation/development/confirm真值不得重新计算归一化分母。

每项同时报告：

- `micro_window`；
- `family_macro`，主口径；
- `scenario_macro`，场景等权；
- `h=1/5/10/15/20`和`1—5/10—20`；
- family级paired bootstrap 95% CI、配对置换、效应量和Holm校正。

解析镜像和旋转副本不增加独立n；长轨迹不能因窗口更多获得更高family权重。

## 9. 新任务树

```text
U0 冻结R1.3协议、231xxx候选seed、历史树和方法注册表
└─ ID/shape/artifact不一致：停止

U1 链A原论文31/2 bilinear与IRSP只读复现
├─ sampled与continuous证书分开报告
└─ 结论只决定原论文IRSP主张，不阻断链B

U2 链B历史四车方法逐元素回归
├─ ARX46/FL92/FB92/SB92/H2-64
└─ 失败：修适配器，不生成pilot

U3 24条新pilot
├─ 24/24有限，ultimate=0
├─ 解析镜像与轴向oracle
├─ 12组0.4 s局部镜像至少11组通过
└─ 失败：停止正式数据

U4 生成train/validation/development=256/96/64
└─ development生成后锁定

U5 链B公平重训和bilinear机制消融
├─ bilinear失败只删除bilinear主张
└─ 保留最强有限核心

U6 P0—P4物理lift
├─ 通过：进入核心候选
└─ 失败：回退最强核心，仍继续U7

U7 G0/G1/G2/M validation
└─ M不过门：停止development

U8 冻结后一次读取development
└─ 不通过：停止，不生成confirm

U9 生成160个base并单次盲confirm
└─ 不通过：保留负结果，不回调

U10 图表、统计、work_log、solutions、论文删改矩阵和delivery.zip
└─ 只有盲确认通过后另立闭环/网络实验MD
```

## 10. 代码修改清单

新建`innovation/efd_r13/`，不得覆盖R1.2：

| 文件 | 必须实现 | 验收 |
|---|---|---|
| `config.py` | 231xxx候选seed、U0—U10门和目录 | 配置round-trip |
| `method_registry.py` | 链A/链B唯一ID、shape、artifact、claim权限 | 名称—shape不符退出2 |
| `paper_claim_map.py` | 原稿每个Koopman/IRSP表述到真实artifact | 不存在artifact的claim标红 |
| `article_irsp_adapter.py` | A-LIN/BIL/IRSP31-U2只读复现 | 历史输出`<=1e-10` |
| `article_irsp_audit.py` | sampled radius与continuous norm分层 | 不能混用passed字段 |
| `vehicle_adapter.py` | V-ARX/FL/FB/SB/H2真实加载 | 历史cache逐元素回归 |
| `fair_vehicle_baselines.py` | 链B同数据公平重训 | 同输入/预算/统计 |
| `bilinear_audit.py` | N置零、控制置换、场景贡献和条件数 | 机制门可复算 |
| `physical_lift.py` | P0—P4和镜像奇偶 | 无未来truth、周期连续 |
| `core_selector.py` | family-macro词典序及合法回退 | 不读取development |
| `equivariant_features.py` | 相对货物几何、R_phi | 旋转误差`<=1e-12` |
| `geometry_backbone.py` | 20步d/v及Reynolds投影 | 不读核心未来几何 |
| `axial_decoder.py` | plant唯一轴向公式、Q和反力 | truth oracle`<=2e-3 N` |
| `fallback.py` | 四类fallback和因果回退 | 不读取未来truth |
| `normalization.py` | train-only尺度 | validation不可写 |
| `metrics.py` | family/scenario/horizon/方向指标 | 小样本手算 |
| `statistics.py` | bootstrap、置换、Holm、效应量 | 固定seed |
| `access_guard.py` | development/confirm状态机 | 越权退出2 |
| `run.py` | U0—U10幂等任务树 | 链A失败不误阻断链B |
| `report.py` | 两条证据链分表、主张删改矩阵 | CSV/图/hash一致 |

必须新增测试：

```text
test_method_registry_unique_ids_and_shapes
test_article_irsp_is_31_state_2_input
test_vehicle_structured_bilinear_is_92_state_8_input_no_irsp
test_no_cross_chain_artifact_substitution
test_article_irsp_sampled_and_continuous_flags_are_distinct
test_vehicle_legacy_cache_reproduction
test_h2_64d_reproduction
test_train_only_normalization
test_family_macro_not_length_weighted
test_physical_lift_wraparound_and_mirror_parity
test_bilinear_zero_n_and_control_permutation
test_geometry_does_not_read_core_future_geometry
test_axial_decoder_truth_oracle
test_fallback_has_no_future_truth
test_development_confirm_access_guard
```

## 11. 运行命令

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd_r13\run.py'

& $PythonExe -B $Runner --project-root $ProjectRoot --stage u0
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u1
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u2
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u3 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u4 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u5
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u6
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u7
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u9 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage u10
```

## 12. 停止和异常处理

| 情况 | 允许处理 | 结论边界 |
|---|---|---|
| 链A历史图表不能复现 | 修只读适配器、环境和dtype | 不改artifact重训冒充历史 |
| A-IRSP采样通过、连续失败 | 分层报告 | 删除continuous-certified表述 |
| noIRSP几乎无退化 | 删除IRSP核心贡献 | 不用谱半径代理闭环收益 |
| 链B方法shape/名称不符 | 修registry和适配器 | 不生成新数据 |
| V-SB92不如V-FL92 | 保留负结果，核心回退 | 删除structured bilinear优势 |
| bilinear N项被使用但总体退化 | 报工况与代价 | 不称总体有效 |
| P0—P4失败 | 回退最强核心，继续几何 | 删除物理lift收益主张 |
| V-M只胜较弱H2、不胜最强基线 | 判主方法失败 | 不能形成论文优势 |
| G2过、M失败 | 另立本构协议 | 不进本轮confirm |
| validation过、development失败 | 停止 | 不生成confirm |
| confirm失败 | 完整交付负结果 | 不换seed复用盲集 |
| OOM/崩溃 | 同seed降worker、分块、断点续跑 | 不删除失败轨迹或缩短20步 |

每次修改和阶段必须追加`work_log.md`；停止时`solutions.md`记录事实、原因、替代解释、成本、论文影响和恢复条件。

## 13. 论文决策规则

1. 原TF14 IRSP当前不得再称连续域可认证；若noIRSP无实质收益，从标题、摘要和贡献删除IRSP。
2. 四车`V-SB92-U8`不是IRSP模型；论文和回复信必须纠正此前混用。
3. 只有链B bilinear机制门通过，才保留bilinear为新预测器贡献。
4. 只有`V-M`通过validation、development和盲confirm，才用它替换原论文Koopman预测部分。
5. 若最终核心是`V-ARX46-U8`，论文不能继续以Koopman作为核心创新。
6. 若`V-M`不胜最强简单基线，停止模型创新主张，不继续叠加多专家、在线适应或网络模块。
7. 本轮力只能解释为货物侧四点力和前后/左右受拉内力代理；没有材料与独立双侧测量时不能判断真实撕裂。

R1.3的核心不是为旧IRSP寻找一个同名替身，而是先纠正方法身份，再用真实四车模型和独立等变连接预测回答审稿人真正关心的20步预测、受力退化、机制贡献和统计复现问题。

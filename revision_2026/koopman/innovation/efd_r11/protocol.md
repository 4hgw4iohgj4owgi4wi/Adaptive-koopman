# EFD-R1.1执行书：20步等变连接动力学预测

> 状态：修正协议草案，尚未执行；协议、代码、seed和门槛冻结后才允许生成新pilot。  
> 5080工程：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码：`revision_2026/koopman/innovation/efd_r11/`  
> 新结果：`revision_2026/koopman/innovation_efd_r11_results/`  
> 历史只读：旧`direction`、`efd`、`efd_r1`代码和结果全部只读。  
> 本轮范围：只完成离线1—20步状态、连接几何、四点力与货物内力代理预测；未通过盲确认前不进入MPC、通信扰动、DoS或闭环稳定性实验。

## 1. 先校正实验目的

### 1.1 审稿意见真正要求回答的问题

审稿人并没有要求证明数值积分器在100 m全程保持机器精度级镜像一致。与Koopman相关的核心问题是：

1. 原双线性Koopman相对线性方法的20步优势没有得到充分证明；
2. IRSP有时降低性能，且没有覆盖连续输入域的可靠证书；
3. 状态误差改善不能掩盖四点力、货物受拉内力代理及方向退化；
4. 需要同数据、同输入、同统计单位和多seed的公平对比，说明每种模型的有效工况和失败工况；
5. 若提出新的Koopman改造，必须在全新数据和盲确认集上同时形成预测收益、结构机理和统计证据。

因此，本轮不是为了挽救旧bilinear或IRSP结论，也不是为了让所有模型都显得有效。目标是通过可证伪实验选择最适合四车—货物刚性连接场景的20步预测结构，并据实决定论文中保留、改写或删除哪些原有主张。

### 1.2 本轮唯一主问题

> 在相同46维当前状态和未来20步已知/规划控制输入下，以重新训练的直接多时域Koopman骨干预测车辆—货物核心状态，再用相对坐标、硬镜像等变的连接几何骨干预测四点连接位移和相对速度，最后通过轴向连接器本构重构四点水平/竖直力，能否在全新validation、development和盲confirm上，同时改善10—20步状态、连接几何、四点力、货物前后/左右受拉内力代理和方向指标？

若答案是否定的，就停止该模型路线。不能继续叠加多专家、注意力、在线适应或网络模块掩盖离线预测证据不足。

### 1.3 名称和论文边界

R1.1的直接1—20步读出不满足单一递归算子的半群关系，不能把整个模型表述成一个新的自治Koopman算子。若最终通过，论文中应称为：

**硬等变连接几何增强的Koopman多时域预测器**，而不是“严格的单算子Koopman线性化”。

若旧bilinear或IRSP未通过本轮机制门，必须从论文标题和核心贡献中删除；可以作为失败边界或对照保留。

## 2. R1失败留下的事实和不能做的解释

### 2.1 已核实事实

1. EFD-v1中，G-EFD相对H2将连接位移、四点力和货物受拉内力代理误差分别改善约`82.95%`、`78.44%`和`58.47%`，说明直接学习连接几何有价值；但其等变和fallback门失败。
2. R1的相对特征、镜像映射、Reynolds投影、轴向解码器和因果fallback单元合同全部通过，数值误差约为`1e-15—1e-14`。
3. R1解析镜像数组残差为0，plant初始微分交换子为0，原轨迹使用捕获的float64初态和控制可以逐元素重放。
4. R1的8组独立长程镜像积分仅6组通过`1e-5`门；最坏seed `201005`的p95为`1.893%`、最大误差为`14.07%`，主要出现在长程`staged_100m`刚性连接工况。
5. R1按冻结协议停止是正确的；R1.1不得把R1改写成“通过”，不得删除失败seed或覆盖旧报告。

### 2.2 独立判断

R1失败证明的是当前RK4浮点积分在长时间刚性连接轨迹上不能维持机器精度级镜像重合；它没有证明R1模型预测失败，因为模型尚未训练。反过来，单元合同通过也不能证明新模型有预测收益。

R1的主要协议错误是把“100 m长时独立镜像轨迹保持`1e-5`重合”设置为模型训练前绝对门禁。该要求比论文的20步、`0.4 s`预测时域严格得多，并把数值敏感性问题错误地提升成了模型有效性的前置条件。

R1.1不事后放宽R1门槛，而是新立问题层级、新seed和新结果目录：局部物理等变与模型硬等变继续作为门禁，100 m独立镜像差异改为长时数值敏感性诊断。

## 3. 可证伪假设

### H0：局部物理与数据合同成立

在与20步预测相同的`0.4 s`时间窗内，镜像初态和镜像控制的独立积分必须保持预注册的局部一致性；轴向本构oracle、角点顺序、坐标系和作用侧必须正确。

H0失败时停止全部训练，先修plant或数据合同。

### H1：独立连接几何是原H2受力方向退化的关键修正

硬等变几何骨干相对同数据重训的H2，必须显著改善10—20步连接位移和相对速度，并由同一预测几何改善四点力与货物受拉内力代理。只改善力head而几何不改善，不支持H1。

### H2：硬等变结构不仅代数正确，而且改善未见变换泛化

Reynolds投影后的模型必须在矩阵层面严格满足镜像交换子；相对“同容量+镜像增强但无硬投影”候选，还应在未见30°/60°全局旋转和左右镜像数据上改善任务误差或显著降低左右偏置。

若只有交换子为零、预测精度没有改善，只能声明“获得结构保证”，不能声明“等变结构提升了精度”。

### H3：轴向物理解码适合当前连接器

使用同一几何骨干时，轴向本构解码R1-P应不劣于学习幅值R1-L。若R1-L通过而R1-P失败，说明几何可预测，但plant本构参数、速度预测或加载/卸载合同不足；不能把R1-L包装成真实本构复现。

### H4：bilinear和IRSP的有效性可以被明确判定

bilinear只有在高控制幅值、弯道或方向切换工况形成可重复增益，且去掉`u_jN_jz`后性能显著下降，才算有效。IRSP只有在连续输入域证书成立，并降低发散/最坏误差且不明显牺牲主预测误差时才算有效。

未通过即删除相应核心贡献，不用“文献中通常有效”替代本项目证据。

## 4. 方法合同

### 4.1 统一因果输入与输出

所有公平对照统一使用：

```text
x0       [B,46]      当前车辆—货物—连接完整状态
u_future [B,20,8]    当前时刻已知或规划的未来20步四车控制
p_static [B,np]      仅当连接参数/货物质量跨轨迹变化且预测时已知时启用
```

统一评价输出：

```text
state_core       [B,20,30]
connector_disp   [B,20,4,2]
connector_vel    [B,20,4,2]
force_payload    [B,20,4,2]
force_vehicle    [B,20,4,2] = -force_payload
Q_FR/Q_LR        [B,20,2]
force_rate       [B,20,4,2]
```

禁止输入未来真值状态、未来真值力、事后场景标签、未来网络状态或由整条轨迹计算的统计量。变量缺失问题不在本轮模拟；不能把缺失值置零后称为工况门控。

### 4.2 公平重训的核心骨干

旧R1直接冻结历史H2，而新几何head使用新数据训练，存在训练数据预算不完全一致的解释空间。R1.1必须在新train上重新训练一个H2式直接多时域骨干：

\[
\hat x^{core}_{1:20}=W^{core}\Phi(x_0,u_{0:19}),
\]

并冻结其前30维输出，作为所有R1候选共享的核心状态预测。历史冻结H2只用于接口回归和旧证据连续性，不作为唯一公平主基线。

### 4.3 相对坐标硬等变连接几何

特征只使用相对货物位置、相对航向的`sin/cos`、车辆/货物体坐标速度、当前四点连接位移与相对速度、未来控制和可选已知静态参数。不得使用未经处理的绝对世界坐标或绝对航向。

对每个时域`h=1...20`直接预测：

\[
\begin{bmatrix}\hat d_h\\\hat v_h\end{bmatrix}
=W_{eq,h}\phi_h(x_0,u_{0:h-1},p),
\]

其中：

\[
W_{eq,h}=\frac{1}{2}\left(W_h+R_y^{-1}W_hR_\phi\right).
\]

最终46维状态为：

\[
\hat x_h=[\hat x^{core}_{h,0:30},\hat d_h,\hat v_h].
\]

几何骨干不得读取公平H2基线的未来`30:46`输出，也不得读取未来真值几何。

### 4.4 两种解码器

R1-L使用学习的非负幅值与预测位移方向：

\[
\hat F_{i,h}=\operatorname{softplus}(m_{i,h})
\frac{\hat d_{i,h}}{\|\hat d_{i,h}\|+\epsilon}.
\]

R1-P使用plant一致的间隙、轴向弹簧和仅加载阻尼：

\[
n_i=\frac{d_i}{\|d_i\|+\epsilon},\quad
e_i=\max(\|d_i\|-g,0),
\]

\[
T_i=\mathbf 1_{e_i>0}\max\!\left(k e_i+c\max(v_i^Tn_i,0),0\right),
\quad F_i=T_i n_i.
\]

阻尼只在`e_i>0`时生效。`F_vehicle=-F_payload`硬编码；`Q_FR/Q_LR`只从最终四点货物侧力重构；第1步力变化率使用当前实测力，后续使用上一预测步。

### 4.5 fallback

固定`epsilon_dir=1e-8 m`。活动状态由候选自身预测幅值和train-only力floor判断，不得读取未来truth。方向无效时依次使用当前实测连接位移方向、同一预测轨迹上一有效方向；仍无有效方向则输出零并记录`unresolved_active_fallback`。

同时报告all、predicted-active、current-active和truth-active四类fallback；truth-active只作离线归因。

## 5. R1.1镜像验证的三层修正

### 5.1 L0：解析变换与模型代数硬门

这是严格门禁，任一失败均停止：

- `mirror(mirror(x))`和`mirror(mirror(u))`最大误差`<=1e-12`；
- 解析镜像数组逐字段最大绝对残差`<=1e-12`；
- 相对特征的30°/60°旋转不变误差`<=1e-12`；
- `max|W_eq R_phi-R_y W_eq|<=1e-12`；
- 几何、decoder、完整力路径的合成镜像误差`<=1e-10`；
- Q重构和作用—反作用代数残差`<=1e-10`。

这些门证明代码和模型结构，不证明预测准确率。

### 5.2 L1：与预测时域一致的局部plant门

使用新pilot的12组独立镜像初态和控制，在同一float64状态、同一控制序列、同一参数下检查：

1. 连续微分交换子；
2. 单个RK4子步`0.002 s`；
3. 一个控制周期`0.02 s`；
4. 20个控制周期`0.4 s`，即论文的20步预测窗口。

每个字段先按预注册物理尺度归一化，不能继续使用“每个字段p95且下限统一为1”的混合尺度。尺度冻结为：

| 字段 | 尺度 |
|---|---:|
| 世界位置 | `100 m` |
| 航向 | `pi rad` |
| 纵/横向速度 | `5 m/s` |
| 横摆角速度 | `1 rad/s` |
| 连接位移 | `0.05 m` |
| 连接相对速度 | `1 m/s` |
| 四点力与Q | `8000 N` |

硬门：

- 连续微分交换子归一化最大值`<=1e-12`；
- `0.002 s`归一化最大值`<=1e-11`；
- `0.02 s`归一化最大值`<=1e-9`；
- `0.4 s`逐字段归一化p95`<=1e-5`且最大值`<=1e-4`；
- 12组至少11组通过，且任何失败组不得出现非有限值、ultimate或单侧物理事件不一致。

若只有1组轻微超过数值门，不允许直接忽略：必须运行同seed的`dt={0.004,0.002,0.001}`收敛审计。半步后误差没有下降，判H0失败；误差随步长下降且无物理事件分叉时，保留为数值敏感性案例，但不得修改正式`0.002 s`数据。

### 5.3 L2：100 m长时镜像敏感性诊断

8组独立长程镜像仿真继续执行，但不再要求全程保持`1e-5`重合。必须报告：

- 各字段误差随时间/距离增长曲线；
- 首次超过`1e-5`、`1e-3`、`1%`的时间和距离；
- 误差最先出现的状态、连接点和力分量；
- 左/右两侧ultimate、rated、控制饱和和路径完成事件是否一致；
- `dt={0.004,0.002,0.001}`下的误差增长和收敛趋势；
- 是否存在固定方向、固定角点或固定场景的系统性单侧偏差。

以下情况仍会阻断训练：连续微分或0.4 s局部门失败；解析镜像不等；长时误差呈系统性单侧偏置且无法由步长收敛解释；一侧频繁触发ultimate而另一侧不触发。单纯的长时相位/轨迹分离不再作为R1.1模型训练的绝对阻断。

## 6. 新数据和证据隔离

### 6.1 seed块

R1的`201xxx`全部视为已使用。R1.1按顺序选择第一个结构化字段零碰撞的块：

```text
候选BASE = 211000, 221000, 231000
```

选定BASE后：

| split | 独立base数 | seed |
|---|---:|---|
| pilot | 24 | BASE+1—BASE+24 |
| train | 256 | BASE+1001—BASE+1256 |
| validation | 96 | BASE+2001—BASE+2096 |
| development | 64 | BASE+3001—BASE+3064 |
| confirm | 160 | BASE+4001—BASE+4160 |
| bootstrap | 5 | BASE+5001—BASE+5005 |
| statistics | 1 | BASE+5999 |

pilot每个主要场景至少6条；其中12条做L1局部独立镜像，8条做L2长程诊断。pilot只验证合同和资源，不选择模型超参数。

### 6.2 工况覆盖

正式split必须覆盖：

- 直线匀速；
- 加速、减速、间隙进入/退出；
- 正反阶跃转向和转向切换；
- 单移线、回头弯、直线进入弯道和退出弯道；
- 连接刚度、阻尼、间隙和货物质量变化；
- 四点`Fx/Fy`正负活动、方向反转和高受拉内力代理窗口。

每个split的覆盖统计以独立`base_family_id`和互不重叠20步窗计算。解析镜像不增加独立样本数、置信区间样本数或bootstrap权重。

### 6.3 变换数据角色

- train保存base和精确解析镜像，但统计单位仍为base family；
- validation同时保留原始、解析镜像、未见30°和60°旋转版本；变换副本只用于成对泛化评价；
- development和confirm不用于选择变换阈值；
- base与其任何变换副本不得跨split。

为了区分“数据增强”和“硬结构”，必须单独比较base-only、镜像增强无投影和硬投影候选。

## 7. 必跑方法与公平性

### 7.1 历史连续性适配器

| 编号 | 方法 | 作用 |
|---|---|---|
| L0 | 历史冻结K1 | 旧论文数值连续性，不作唯一公平基线 |
| L1 | 历史冻结K2 bilinear | 检查旧模型在新数据外推 |
| L2 | 历史冻结K3 bilinear+IRSP | 检查旧IRSP结论是否复现 |
| L3 | 历史冻结H2 | 检查此前直接多时域优势是否跨数据保持 |

### 7.2 同数据公平重训

| 编号 | 方法 | 唯一作用 |
|---|---|---|
| B0 | fixed linear Koopman | 线性递推基线 |
| B1 | full bilinear Koopman | 检验输入—状态耦合 |
| B2 | bilinear+原IRSP | 检验原稳定投影的收益/代价 |
| B3 | H2式直接多时域全状态head | 当前最强公平骨干 |
| B4 | 直接四点力ridge | 可学习性上界，不作为物理主方法 |
| A0 | 相对几何head，base-only，无硬投影 | 坐标特征本身的贡献 |
| A1 | A0+解析镜像增强，无硬投影 | 数据增强贡献 |
| A2 | 硬等变几何+学习幅值R1-L | 几何与本构分离 |
| M | 硬等变几何+轴向物理解码R1-P | 论文主候选 |

B0—B3使用相同新train、相同输入、相同20步、相同归一化和相同超参数预算。B1/B2必须报告设计矩阵条件数、双线性项系数范数、输入范围外推和非有限/发散率。

B1还必须运行两个机制消融：

1. 推理时令全部`N_j=0`；
2. 在轨迹内置换`u_future`但保持状态不变。

若完整B1与两个消融没有稳定差异，不能声称bilinear项捕获了有效输入—状态耦合。

B2除旧采样谱半径外，必须检查连续输入盒上的诱导范数/LMI证书。只有采样谱半径通过，不算连续域IRSP证书。

## 8. 指标和通过门

### 8.1 必报指标

预测指标按`h=1/5/10/15/20`、`1—5`和`10—20`分别报告：

- `state_core_0_30`、`connector_disp_30_38`、`connector_vel_38_46`、`state_all_0_46` NRMSE；
- 四点力、八个`Fx/Fy`分量、`Q_FR/Q_LR`和force-rate NRMSE；
- 八分量方向准确率、四点向量角度MAE/p95、Q方向准确率；
- 方向反转准确率、反转后恢复步数；
- 高受拉内力代理、转向切换和间隙切换分层误差；
- 发散率、非有限率、p50/p95/p99和最大推理时间；
- 参数量、训练时间、峰值内存和设计矩阵条件数。

综合指标固定为：

\[
J=(J_{state\_all}+J_{force}+J_{load})/3.
\]

不得因某候选有利而改权。统计单位为base family，使用轨迹级paired bootstrap、95% CI、配对检验、Holm校正和效应量。

### 8.2 R1-P validation主门

M必须全部满足：

1. 10—20步`J`相对B3和B0均改善`>=8%`，轨迹级95% CI下界均`>0`；
2. `state_core`相对B3恶化`<=1%`；
3. 连接位移和相对速度相对B3分别改善`>=30%`和`>=10%`，CI下界均`>0`；
4. 四点力和货物受拉内力代理相对B3均改善`>=10%`，CI下界均`>0`；
5. 八分量方向、Q方向和反转准确率均不低于B0减1个百分点，至少两项显著优于B0；
6. 四点向量角度p95小于B0且`<=60°`；
7. R1-P未见镜像/30°/60°变换的force/load误差相对原始方向恶化不超过5%；
8. A2相对A1在未见变换的force/load或方向主指标中至少一项改善`>=5%`且CI下界`>0`，否则H2只保留结构保证；
9. predicted-active fallback`<=1%`，unresolved-active fallback`<=0.1%`；
10. Q、作用—反作用和模型镜像交换子满足第5节代数门；
11. divergence不高于B3，非有限率为0；
12. 9候选×20步批量预测p99`<=2 ms`、最大值`<20 ms`；
13. 5个bootstrap模型至少4个满足第1—9项。

R1-L使用同一门。若R1-L通过而R1-P失败，停止主候选M，只保留“硬等变几何+经验非负幅值”候选，并另立本构修订协议；不得直接进入confirm。

### 8.3 bilinear和IRSP机制门

B1只有同时满足以下条件才允许保留“bilinear有效”结论：

- 相对B0的10—20步`J`改善`>=8%`且CI下界`>0`；
- 正反阶跃、回头弯或高控制幅值工况至少两类改善`>=10%`；
- `N_j=0`消融使主指标恶化`>=5%`；
- 输入置换显著破坏预测，说明模型实际使用了控制—状态耦合；
- 发散、方向和受力安全指标不劣于B0超过3%。

B2只有同时满足以下条件才允许保留“IRSP有效”结论：

- 连续输入盒证书成立，而非只有有限控制点采样谱半径；
- 相对B1的发散率、最坏20步误差或暂态放大p99至少一项改善`>=10%`；
- 10—20步`J`和state/force/load均不得恶化超过3%；
- 至少4/5 bootstrap复现。

若B1或B2失败，不阻止M继续验证，但论文必须删除相应核心贡献，不能把M的收益归因于bilinear或IRSP。

### 8.4 development和盲confirm

validation只按冻结词典序选择ridge和候选。选择完成后冻结模型、归一化、阈值、代码和报告脚本，一次性读取development。development重复全部主门，并增加：

- 任一R0—R3工况的force/load相对B3恶化不超过10%；
- 左右基础工况误差差异不超过5%；
- 主要改善方向与validation一致。

development通过后才生成160个独立base的confirm。confirm只运行一次，门与development相同。confirm失败后不得回到validation调参并复用同一confirm。

## 9. 分阶段任务树

```text
S0 新协议、代码、seed、数据角色和历史只读hash冻结
└─ 失败：停止，不生成pilot

S1 变换、Reynolds、decoder、fallback和访问权限单元测试
└─ 失败：只修确定性合同，不改性能门

S2 24条新pilot
├─ L0解析与代数硬门
├─ L1 12组0—0.4 s局部独立镜像门
├─ L2 8组100 m长时数值敏感性诊断
└─ H0失败：停止训练并写solutions.md

S3 生成train/validation/development
├─ base family与解析变换同split
├─ 覆盖、单位、角点和时序审计
└─ 失败：只按预注册追加表补数据

S4 同数据重训B0—B4并运行旧L0—L3外推
├─ H2式B3不复现：停止R1，先查数据和接口
└─ B4不可学习：停止，说明当前输入不含足够力信息

S5 训练A0/A1/A2/M并只读validation
├─ 分层几何—decoder—力误差定位
├─ bilinear/IRSP机制消融
└─ M不过门：停止development

S6 冻结候选，一次性读取development
└─ 不通过：停止，不生成confirm

S7 冻结confirm manifest并生成160个独立base
└─ 只允许同seed断点续跑，不替换失败轨迹

S8 单次盲confirm
└─ 不通过：保留负结果，不回调

S9 报告、图、统计表、代码清单、work_log和delivery.zip

S10 只有S8通过后另立闭环与网络实验MD
```

## 10. 对应代码修改

不得修改`innovation/efd_r1/`。新建`innovation/efd_r11/`：

| 文件 | 必须修改/实现 | 关键验收 |
|---|---|---|
| `config.py` | 新目录、211xxx候选seed、三层镜像门、全部性能门 | 配置round-trip；协议hash一致 |
| `audit.py` | 旧目录hash、结构化seed扫描、split访问记录 | 历史前后hash一致 |
| `schema.py` | 46维/8维、角点、坐标、单位、物理尺度 | 字段逐项断言 |
| `transforms.py` | 状态、控制、d/v/F/Q的镜像与旋转 | 二次镜像恢复；Q奇偶手算反例 |
| `integrator_equivariance.py` | 微分、0.002/0.02/0.4 s局部门和dt收敛审计 | 输出逐字段、逐时刻残差，不混用尺度 |
| `mirror_generator.py` | 解析镜像、局部独立镜像、长程诊断接口 | 初态/control64可复现；不得每步投影 |
| `data_protocol.py` | 新split、base family、变换副本和覆盖 | 变换副本不跨split、不增加n |
| `dataset.py` | teacher-free 20步窗、train-only归一化 | 无未来truth和split泄漏 |
| `legacy_adapter.py` | L0—L3逐元素回归 | 与历史模型float64误差`<=1e-10` |
| `baselines.py` | 公平重训B0—B4、bilinear消融、IRSP证书接口 | 同输入、同预算、同数据 |
| `core_multihorizon.py` | 新train重训B3并冻结0—30维 | 不读取development |
| `equivariant_features.py` | 相对货物特征、控制序列、`R_phi` | 30°/60°误差`<=1e-12` |
| `reynolds.py` | horizon-wise线性映射投影 | 交换子`<=1e-12` |
| `geometry_backbone.py` | A0/A1/A2/M共用几何结构 | M/A2不读取B3未来几何 |
| `magnitude_head.py` | R1-L非负幅值 | 有限、非负、镜像置换正确 |
| `axial_decoder.py` | plant唯一公式、Q和反力重构 | truth d/v oracle`<=2e-3 N` |
| `fallback.py` | 四类fallback和因果回退链 | 函数签名与运行轨迹均无未来truth |
| `metrics.py` | 状态、几何、力、方向、变换、工况和资源指标 | 小样本手算一致 |
| `statistics.py` | family级bootstrap、CI、检验、Holm、效应量 | 固定统计seed |
| `access_guard.py` | development/confirm读取状态机 | 越权读取退出码2并留痕 |
| `train.py` | 五bootstrap、固定ridge网格和冻结模型 | validation前不读development |
| `evaluate.py` | validation/dev/confirm只读评估 | 一次性访问记录 |
| `report.py` | 自动生成主表、机制图、失败图和审稿对应表 | 图表与CSV hash一致 |
| `run.py` | S0—S9幂等状态机 | 前门失败阻断后续 |

必须新增或改写测试：

```text
test_rotation_invariant_features
test_mirror_involution_state_control
test_q_mirror_parity_manual_counterexample
test_reynolds_commutator_and_prediction
test_local_derivative_equivariance
test_local_rk4_equivariance_002_02_04
test_long_horizon_is_diagnostic_not_silent
test_geometry_does_not_read_future_or_h2_geometry
test_axial_decoder_truth_oracle
test_fallback_has_no_future_truth
test_augmented_family_not_double_counted
test_fair_baselines_share_inputs_and_splits
test_development_confirm_access_guard
```

## 11. 计划命令

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Runner = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd_r11\run.py'

& $PythonExe -B $Runner --project-root $ProjectRoot --stage s0
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s1
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s2 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s3 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s4
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s5
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s6
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s7 --workers 8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s8
& $PythonExe -B $Runner --project-root $ProjectRoot --stage s9
```

每个stage必须保存输入hash、实际命令、环境、资源、`complete.json`和停止决定。输入变化时拒绝覆盖，必须建立新协议版本。

## 12. 跑不动和证据不足处理

| 情况 | 判断 | 允许处理 | 停止边界 |
|---|---|---|---|
| 解析镜像数组不等 | 变换合同错误 | 修角点/奇偶/坐标后重做S1/S2 | 不得放宽误差 |
| 0.4 s局部门失败 | 与20步任务直接相关的plant合同不足 | 同seed做dt收敛、定位首个字段 | 不通过则不训练 |
| 100 m镜像分离但局部门通过 | 长时刚性数值敏感性 | 完整报告增长曲线和事件一致性 | 不单独阻断训练 |
| 同数据B3不复现H2优势 | 旧收益可能数据特定或适配错误 | 查接口、归一化和窗口 | 不能继续R1主模型 |
| B4直接力也不可学习 | 当前因果输入信息不足 | 查状态可辨识性和日志时序 | 停止增加head容量 |
| 几何改善、速度不改善 | 模型只学到准静态关系 | 报告d/v分离，检查动态特征 | velocity门不过即失败 |
| R1-L通过、R1-P失败 | 本构或速度合同不足 | 另立本构修订协议 | M不得进confirm |
| A2交换子为零但任务误差不降 | 结构保证无精度收益 | 保留结构事实 | 不声称等变提升精度 |
| bilinear优于linear但消融无差异 | 容量/正则而非耦合收益 | 报告条件数与消融 | 不保留bilinear机理主张 |
| IRSP只改善谱半径 | 代理指标无部署收益 | 报完整Pareto | 删除IRSP贡献 |
| validation过、development失败 | 泛化不足 | 停止并保存模型 | 不生成confirm |
| confirm失败 | 主张未复现 | 完整交付负结果 | 不换seed重做盲集 |
| OOM/崩溃 | 工程资源问题 | 同seed降worker、分块、断点续跑 | 不丢弃失败轨迹 |
| p99超时 | 实时性不足 | 批量化、缓存、同模型复测 | 仍超门则不可部署 |

发生停止时，`solutions.md`必须记录事实、最可能原因、替代解释、修复方案、预计成本、论文影响和恢复条件。

## 13. 留痕和交付

每次代码修改、同seed重跑和stage完成都追加：

`revision_2026/koopman/innovation_efd_r11_results/work_log.md`

至少记录：

```text
编号与时间
协议/代码/输入SHA256
实际命令和环境
修改前后文件hash、函数、原因
测试和数值结果
门禁、停止或降级决定
同seed重跑及其合法性
回滚路径
```

最终至少交付：

```text
freeze/
pilot/{local_equivariance,long_horizon_diagnostic}/
data/{train,validation,development,confirm}/
models/{legacy,fair_baselines,ablations,main}/
audits/{mirror,rotation,seed,readonly,access,fairness}/
metrics/
figures/
failure.json
solutions.md
work_log.md
results.json
report.md
delivery.zip
```

## 14. 本轮如何关闭审稿人的Koopman问题

只有S8盲确认通过，才能形成以下行文：

1. 先用同数据实验说明fixed linear、bilinear、bilinear+IRSP和直接多时域方法各自在直线、加减速、弯道、切换和参数变化中的优势与退化；
2. 用bilinear置零和输入置换证明其增益是否真正来自输入—状态耦合；不能只看模型名称；
3. 指出原直接多时域H2虽显著降低长时幅值误差，但连接几何和力方向不足；
4. 新方法通过独立预测相对连接几何、硬镜像等变和轴向本构，针对该不足完成修正；
5. 用validation、development和盲confirm证明改善不是单seed、单场景或事后选择；
6. 若bilinear或IRSP失败，论文明确删除对应贡献，把主线改为“硬等变连接几何增强的Koopman多时域预测”；
7. 本轮仍只证明货物前后/左右受拉内力代理，不能推断真实材料撕裂、裂缝或安全等级。

本轮的成功标准不是“所有模块都有提升”，而是得到一个经过公平对比、机理消融和盲确认的最合适预测器，并能清楚说明其生效区域、失败区域和论文允许主张。

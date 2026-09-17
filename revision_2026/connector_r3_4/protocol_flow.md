# 连接器连续修正任务书

> 编制时间：2026-08-28（Asia/Shanghai）  
> 本地文件：`D:\PDxc\Review\connector_flow.md`  
> 目标主机：5080（`DESKTOP-9IUUGEO`）  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前源码：`revision_2026\connector_r3_4`  
> 当前结果：`revision_2026\connector_r3_4_results`  
> Python：`E:\anaconda\envs\pytorch_new\python.exe`  
> 授权边界：本文件是方案编写；只有用户再次明确要求执行时，才修改5080或启动实验  
> 接续关系：保留`protocol.md`和`protocol_finish.md`及其历史证据；本文件同步后命名为`protocol_flow.md`，负责C1修正至数据和训练就绪

## 0. 本任务书与旧任务书的区别

本任务书不设置“某项不通过便把全部后续永久标记为NOT_RUN”的终止性任务门。原来的失败节点全部改写为：

```text
保存原始失败数据
→ 判断失败属于测试合同、物理接线、数值积分、工况、数据或学习层
→ 依据误差特征选择修改方向
→ 只运行最小复现实验
→ 复跑受影响回归
→ 返回原任务节点
→ 完成后继续下一节点
```

但“不设置终止门”不等于让无效数据流入训练。NaN/Inf、事件死循环、作用反作用错误、坐标不明或未来信息泄漏出现时，只隔离当前病例并进入修复回路；其产物标记为`DIAGNOSTIC_ONLY`，不进入后续正式数据。

主要阈值保持为验收目标，不允许根据结果临时放宽。若修改使用了某条确认轨迹，该轨迹从此转为开发数据，并在修改前冻结新的未见确认轨迹，防止对最终数据反复调参。

### 0.1 “全部搞定”的三级定义

不要再用一个“连接器完成”同时表示三个不同层级：

1. **核心力律完成**：S0--S4已达到，说明单连接器力律、事件积分和参考解证书成立；这部分已经完成。
2. **四车连接器系统完成**：F0--F6全部形成可复算产物，四点连接力真实进入四车和货物动力学，系统收敛、完整工况和植物选择均有证据；完成后才能冻结正式植物。
3. **全链路完成**：在第二级基础上完成F7--F9，正式数据、Koopman训练冒烟、MPC接口、图片、报告和清单都能从原始数据复算。

只有第三级完成后才生成`READY_FOR_KOOPMAN_TRAINING.json`。某个阶段进入修正循环不改变最终目标，也不允许用诊断产物冒充已完成产物。

### 0.2 剩余十步总表

| 步骤 | 当前状态 | 必须完成的做法 | 完成标志 | 异常后的预计修改方向 |
|---|---|---|---|---|
| F0 C1最小修正 | 待执行 | 修镜像角点置换；把字符串扫描改成AST真实导入扫描 | 镜像单测、扫描器自检、旧18项和全量测试均通过 | 按角点顺序、ICR符号、速度映射或AST节点类型逐项修，不动已被数据支持的力律 |
| F1 接口补齐 | 待执行 | 修Schema；增加四类差动激励；补真实步来源、段起点峰值和区间力特征 | 维数/单位清单一致，四类激励产生可区分内力响应，事件记录可追溯 | 维数错就修构造器；响应相同就查差动命令接线；峰值漏失就修区间采样，不靠调阈值 |
| F2 执行器补全 | 待执行 | 把N2--FINAL阶段加入`run_finish.py`，生成`flow_status.json`和`next_action.json` | 每个stage可独立运行、恢复、留痕且不覆盖历史 | 缺stage补调度；缺产物补合同；哈希不一致另开修订号 |
| F3 N2全相位 | 未运行 | 先Q95 pilot，再做768组全相位矩阵 | 峰值、冲量、终态和接触时刻均有oracle对照，所有首败已修正复验 | 根据“峰值/冲量/终态/时刻/相位周期”误差形态分别修采样、求积、状态重启或事件根 |
| F4 四车物理 | 未运行 | 做静态接线、共同ICR、定向内力和多步长动态收敛 | 作用反作用、共同原点力矩、单车/货物导数、内力零空间及收敛均可复算 | 按残差落在Fx、Fy、横摆、力矩臂、W矩阵或积分层的位置修改对应单模块 |
| F5 完整工况 | 未运行 | 完成100 m、阶跃、单移线、回头弯和直弯过渡四因素实验 | 四点力、方向、横摆、合力矩、`T_x/T_y`、平滑暴露和频谱证据齐全 | 按饱和、暴露不足、卸载退化或积分器交互分别改控制幅值、开发工况、R3.5支路或数值配置 |
| F6 植物冻结 | 未运行 | 根据四因素证据选择R3-ES、R3/V1双数据、V1-ES基线或积分器主效应分支 | 植物身份、适用域、限制和哈希写入冻结清单 | R3优势不足不强行判优；保留可信基线并继续R3.5支路 |
| F7 正式数据 | 未运行 | 先10条pilot，再按轨迹级划分生成正式清洁数据和独立外测数据 | 因果、覆盖、重放、Schema、split和归一化来源全部通过复算 | 根据覆盖矩阵增补物理轨迹；索引错则重建数据；不得移动测试轨迹补训练 |
| F8 训练与MPC接口 | 未运行 | fixed linear和bilinear完成1/5/10/20步冒烟；检查MPC维数、周期和字段 | 模型可训练、保存、重载和滚动；MPC接口清单与新植物一致 | 按错位、尺度、谱半径、病态矩阵或接口维数分别修数据、正则、加载器或映射 |
| F9 证据交付 | 未运行 | 固化原始数据、图、统计、报告、审稿回答和最终manifest | 所有图和结论可由冻结命令从原始数据重建 | 统计不一致就修统计脚本；图与CSV不一致就重绘；声明超出证据就收缩文字 |

执行顺序保持F0→F9。这里的顺序是为了保持因果和证据身份，不是永久停止门：任一步出现异常，保存该次运行并在原节点按数据修正；完成复验后继续。

## 1. 5080最新事实

### 1.1 当前状态

| 对象 | 最新事实 | 来源 | 结论类型 |
|---|---|---|---|
| 主机 | `DESKTOP-9IUUGEO`，2026-08-28 08:56 +08:00 | 现场命令 | 事实 |
| 运行任务 | 无Python/MATLAB进程 | 现场进程表 | 事实 |
| 磁盘 | D盘空闲约`304.994 GiB` | 现场磁盘 | 事实 |
| C0 | `PASS`，S4已正式人工放行 | `s4_review/release.json` | 已复算 |
| C1 | 旧测试18/18；全量28/29；另有1个静态扫描误报 | `implementation/complete.json`和现场复跑 | 已复算 |
| C2--C9 | 尚未运行 | `stage_status.json` | 事实 |
| 数据/模型/MPC | 三个目录文件数均为0 | 现场目录 | 事实 |
| 运行器 | `run_finish.py`目前只实现C0、C1，其他stage直接退出 | 源码 | 事实 |

### 1.2 C0已经解决

- 历史协议SHA256：`31cc68ec...175eb`；
- `protocol_finish.md` SHA256：`b26e8075...29630`；
- 历史源码漂移：0；
- 旧测试：18/18；
- S4：12/12速度—力律组合通过；
- 48行固定参考、24行DOP853 oracle均可复算；
- 0.5 μs相对oracle最坏归一化峰值/冲量/终态误差：
  `2.877e-7 / 9.722e-7 / 9.721e-7`；
- 最大事件面残差：`4.432e-17 m`；
- `release.json.approved=true`。

因此单连接器数值证书不需要重跑，只需在后续修改影响事件积分器时做回归。

### 1.3 C1当前失败的真实原因

#### 左右转镜像测试

当前测试直接比较同一角点：

```python
a['relative_heading_rad'] == -b['relative_heading_rad']
```

但平面镜像会交换左右角点，必须使用：

```python
mirror_index = [1, 0, 3, 2]  # FL↔FR, RL↔RR
a['relative_heading_rad'] == -b['relative_heading_rad'][mirror_index]
```

独立复算结果：

- 不做角点置换，最大差`0.003269037 rad`；
- 做`[1,0,3,2]`置换，最大差为`0`；
- 两侧共同ICR法向速度残差最大`3.525e-15 m/s`。

这说明现有数据更支持“测试合同错误”，暂不支持“转向分配算法错误”。

#### 旧植物扫描

当前扫描器对源码全文搜索禁用字符串，结果匹配到了`run_finish.py`内部用于扫描的字符串本身。独立AST检查实际`Import/ImportFrom`节点数量为0。因此应修改扫描器，不应修改已通过的植物导入。

### 1.4 自动报告没有列出的新增问题

这些问题应在C1修复时一并处理，避免刚把29/29修好便在C2以后再次返工：

1. `build_schema('S1_team')`当前返回64维，不是登记的12维；独立复算维数为：
   `S1=64, S2=30, S3=46, S4=64`。
2. `scenario_command`的纵向、横向和两条对角连接器激励目前给出完全相同的全局加速度，不能激发四种不同内部力模态。
3. `run_finish.py`尚未实现N2、N3、完整工况、数据、训练和最终报告入口。
4. `_vehicle_step_size`仍只返回`dt, unresolved`，后续审计按剩余时间猜测`selection_cause`，会丢失真实`ZONE_RESOLUTION`来源。
5. 四车峰值只综合中点和终点，未显式包含段起点；卸载段可能漏峰。
6. 非活动连接点的方向角用`NaN`表示，后续JSON和统计容易失败；应使用数值占位加活动mask。
7. 区间段尚未保存内部力、`T_x/T_y`、轮胎原始利用率和饱和状态，正式数据无法从区间审计完整重建。
8. `S4_force_event`当前没有事件字段，命名与实际64维内容不一致。
9. 回头弯命令为突然出现的8°矩形输入，既会激发连接器瞬态，也会把输入不连续引入的高频混进“连接器抖振”。阶跃验收与路径工况需要拆开。

## 2. 连续修正的版本和数据纪律

### 2.1 修正循环编号

每轮修改使用：

```text
flow_revision = F01, F02, F03, ...
run_id = YYYYMMDD_HHMMSS_<stage>_<flow_revision>
```

不覆盖失败产物。每轮保存：

- `diagnosis.json`：观测到的数据特征；
- `repair_plan.json`：由什么数据触发什么修改；
- `source_diff.json`：修改前后SHA256；
- `minimal_retest.json`：最小复验；
- `regression.json`：受影响层及旧测试；
- `next_action.json`：继续原节点还是进入下一节点。

### 2.2 三类数据

| 数据层 | 用途 | 可否据此修改 | 修改后的身份 |
|---|---|---|---|
| `diagnostic` | 首败、最坏相位、最小复现 | 可以 | 仍为诊断数据 |
| `development` | 参数、控制和算法选择 | 可以 | 保留全部版本 |
| `confirmation` | 一次性确认论文结论 | 原则上不可以 | 若用于修改，立即转为development并冻结新confirmation |

不得对同一批confirmation反复修改后仍将其称为未见测试集。

### 2.3 阈值的处理

阈值不作为终止任务的开关，而作为误差诊断目标：

- 达到目标：记录当前版本并进入下一任务；
- 未达到目标：根据误差形态进入对应修复分支；
- 修改后：先复跑首败，再复跑同类样本和旧回归；
- 目标值不随结果放宽；需要改目标时必须说明物理依据并建立新版本，旧结果原样保留。

## 3. 模型和评价公式

### 3.1 连接器

\[
d_i=p_i^v-p_i^p,\quad
n_i=\frac{d_i}{\max(\|d_i\|,\epsilon)},\quad
\delta_i=\max(\|d_i\|-l_0,0),
\]

\[
v_{n,i}=(\dot p_i^v-\dot p_i^p)^Tn_i.
\]

R3平滑权重：

\[
g(\delta)=
\begin{cases}
0,&\delta\le0,\\
3s^2-2s^3,&0<\delta<\delta_s,\ s=\delta/\delta_s,\\
1,&\delta\ge\delta_s.
\end{cases}
\]

\[
f_i=k\delta_i+c\,g(\delta_i)\max(v_{n,i},0),
\quad F_i^p=f_in_i,\quad F_i^v=-F_i^p.
\]

本轮先保持力律和参数哈希不变。只有数据证明卸载侧或物理结构假设本身不足时，才另建R3.5，不在R3.4内悄悄调参。

### 3.2 动力学接线

对车辆：

\[
\dot v_x=(F_x^{tire}+F_x^c)/m+r v_y,
\]

\[
\dot v_y=(F_y^{tire}+F_y^c)/m-r v_x,
\]

\[
\dot r=(M_z^{tire}+M_z^c)/I_z,
\quad M_z^c=r_xF_y^c-r_yF_x^c.
\]

货物使用四点合力和合力矩。连接器接线复验采用：

\[
dx_{with}-dx_{without}=dx_{connector,formula}.
\]

### 3.3 内部力和货物拉伸载荷代理

\[
w=Wf,\qquad f_{int}=(I-W^\dagger W)f.
\]

\[
\|Wf_{int}\|_2<10^{-8}\max(1\ \mathrm N,\|f_{int}\|_2).
\]

\[
T_x=\tfrac12\max(0,(F_F-F_R)^Te_x),
\]

\[
T_y=\tfrac12\max(0,(F_L-F_{Rt})^Te_y).
\]

统一字段：`tension_x_n`和`tension_y_n`。它们是拉伸载荷代理，不是货物材料破坏阈值。

### 3.4 R3生效暴露量

为判断“R3没有优势”究竟是方法失败还是工况没有进入平滑区，新增：

\[
E_{smooth}=\frac{\sum_j\Delta t_j\mathbf1(0<\delta_j<\delta_s)}{T},
\]

\[
R_{damp}=\frac{\int|F_{damping}|dt}{\int|F_{total}|dt+\epsilon}.
\]

每条轨迹、每个连接点分别保存`E_smooth`和`R_damp`。

## 4. 代码修改清单

| 文件 | 函数/类 | 修改内容 | 数据触发条件 | 验证 |
|---|---|---|---|---|
| `tests/test_finish_steering.py` | 镜像测试 | 加角点置换`[1,0,3,2]`；同时验证航向、速度、前馈转角、车辆中心和ICR镜像 | 当前唯一pytest失败 | 置换后误差0、ICR残差`<=1e-8 m/s` |
| `scripts/run_finish.py` | 旧import扫描 | 使用AST检查`Import`、`ImportFrom`及动态`import_module/__import__`，不扫描普通字符串 | 当前自匹配误报 | 实际禁用import=0；故障注入能识别 |
| `src/schema_r3.py` | `build_schema` | 显式分支S1/S2/S3；未知名称抛错；逐字段单位；把事件上下文拆成独立数组 | S1当前错误64维 | S1=12、S2=30、S3=46 |
| 同上 | schema兼容层 | 保留旧`s4_force_in=64`用于历史公平比较；新内部力、拉伸和事件分别存数组 | 旧Koopman接口需要64维 | 旧管线可读，新字段不丢失 |
| `src/paired_maneuvers_r3.py` | `ManeuverCommand` | 增加四车差动加速度和差动转角；seed真正参与开发工况 | 四种定向命令目前完全相同 | 四种控制向量和内力响应可区分 |
| `src/event_substep.py` | `_vehicle_step_size` | 返回`dt,candidate_origin,unresolved`；StepRecord不再猜来源 | 当前审计来源丢失 | 逐记录来源复算一致 |
| 同上 | 区间审计 | 每段保存起点/中点/终点峰值，内部力、T_x/T_y、轮胎利用率和饱和 | 后续数据字段缺失 | 解析积分和重绘一致 |
| `src/four_vehicle_common.py` | 方向字段 | 非活动角设0并另存`force_active_mask`，JSON中不存NaN | 当前使用NaN | JSON严格序列化通过 |
| `src/spectral_metrics.py` | Welch输出 | 保存窗、重叠、去均值、频带、采样率；短序列返回诊断而不是假PSD | 长短工况长度不同 | Parseval和单频测试 |
| `scripts/run_n2_flow.py` | 新增 | 读取S4 tight oracle，执行32相位四因素矩阵和误差特征诊断 | C1修复完成 | 768行和最坏trace |
| `scripts/run_n3_flow.py` | 新增 | 静态接线、共同ICR控制、2/1/0.5 ms收敛和参考 | N2结果可用 | 四车原始时序 |
| `scripts/run_maneuvers_flow.py` | 新增 | 100m、单移线、回头弯、过渡、定向激励 | N3结果可用 | 成对工况 |
| `scripts/generate_data_flow.py` | 新增 | 20 ms因果数据唯一入口 | 植物版本冻结 | pilot/full NPZ |
| `scripts/verify_data_flow.py` | 新增 | 因果、覆盖、split、重放和schema复算 | 每次数据生成 | 数据证书 |
| `scripts/train_smoke_flow.py` | 新增 | fixed linear和bilinear冒烟 | 正式数据证书 | 1/5/10/20步 |
| `scripts/plot_flow.py` | 新增/扩展 | 原始数据到图和figure_data | 每阶段 | PNG+CSV |

## 5. 连续任务树

```text
F0  修复当前C1的测试合同和扫描器
 └─ 仍有差异 → 自动生成C1 diagnosis → 按差异类型修改 → 回到F0

F1  补齐C1未覆盖的schema、定向激励、步来源和区间审计
 └─ 任一解析测试不符 → 修相应单模块 → 回到F1

F2  扩展run_finish调度器并建立连续修复账本
 └─ stage未实现/产物不完整 → 补调度或产物合同 → 回到F2

F3  N2 pilot与768行全相位矩阵
 └─ 误差未达目标 → 按相位/指标特征选择数值修复 → 回到F3首败和同类子集

F4  四车静态接线与动态收敛
 └─ 物理/转向/数值差异 → 按残差位置修改 → 回到F4最小工况

F5  100m和完整工况四因素比较
 └─ 工况/饱和/优势不足 → 按暴露量和退化类型修改 → 回到对应development工况

F6  植物冻结与R3解释
 ├─ R3优势清楚 → 冻结R3-ES
 ├─ R3可用但优势不清楚 → 保留R3/V1双数据并限制论文结论
 └─ R3物理不足 → V1-ES基线支路继续，R3.5修正支路并行

F7  pilot与正式数据
 └─ 覆盖/因果/schema问题 → 根据覆盖矩阵增补物理轨迹或修索引 → 回到F7

F8  训练冒烟与MPC接口
 └─ 数值/归一化/接口问题 → 修数据或加载器 → 回到F8最小batch

F9  图、报告、审稿回答和清单
 └─ 报告无法从原始数据复算 → 修统计/绘图 → 回到F9
```

没有永久停止节点；每个异常都必须产出下一修改动作。禁止的只是让无效产物跨层传播。

## 6. F0：立即修复当前C1

### 6.1 镜像测试具体写法

```python
mirror = np.array([1, 0, 3, 2])
np.testing.assert_allclose(
    left["relative_heading_rad"],
    -right["relative_heading_rad"][mirror],
    atol=1e-12,
)
np.testing.assert_allclose(left["speed_mps"], right["speed_mps"][mirror], atol=1e-12)
np.testing.assert_allclose(
    left["feedforward_steering_rad"],
    -right["feedforward_steering_rad"][mirror],
    atol=1e-12,
)
np.testing.assert_allclose(left["icr_payload_body_m"][0], right["icr_payload_body_m"][0], atol=1e-12)
np.testing.assert_allclose(left["icr_payload_body_m"][1], -right["icr_payload_body_m"][1], atol=1e-12)
```

车辆中心位置还应验证`x`保持、`y`变号并交换角点。只修改测试，不修改当前已满足镜像关系的分配公式。

### 6.2 AST扫描器

扫描：

- `ast.Import`；
- `ast.ImportFrom`；
- `__import__('four_vehicle_coupled')`；
- `importlib.import_module('four_vehicle_coupled')`；
- 已知旧类名的真实Name/Attribute引用。

普通字符串、说明文字和测试故障注入不计为生产导入。增加两个自检：一个含真实旧import必须被识别，一个只含字符串不得被识别。

### 6.3 当前C1复验顺序

1. 单跑镜像测试；
2. 单跑AST扫描器自检；
3. 旧18项；
4. 当前全部29项；
5. 完成F1新增测试后再冻结新的测试ID清单。

若镜像置换后仍有误差：

- 只有角点顺序错误：检查`payload_anchor_body_m`和`CORNER_ORDER`；
- ICR的`x`不相等或`y`不反号：检查前后虚拟角符号；
- 速度不置换：检查车辆中心迭代；
- 前馈转角不反号：检查`yaw_rate`和有符号速度；
- 法向残差大：增加迭代收敛诊断，不直接增加转角补偿。

## 7. F1：补齐C1的隐藏缺口

### 7.1 Schema

保留历史兼容数组：

| 数组 | 维数 | 内容 |
|---|---:|---|
| `s1_team` | 12 | 货物6状态 + 四车位置/航向/速度的6个聚合量 |
| `s2_four` | 30 | 四车24 + 货物6 |
| `s3_deform` | 46 | s2 + 四点二维形变8 + 四点二维相对速度8 |
| `s4_force_in` | 64 | 历史s3 + force_body8 + q2 + causal force_rate8 |

新增独立数组，不强行塞入旧64维：

- `internal_force8`；
- `tension_proxy2`；
- `force_interval_mean8`；
- `force_interval_impulse8`；
- `contact_fraction4`；
- `smoothing_fraction4`；
- `smoothing_weight_mean4`；
- `event_counts16`；
- `force_active_mask4`；
- `network_mask`、`network_aoi`仅在网络阶段使用。

逐字段写单位和坐标，禁止`mixed_si`作为正式单位。

### 7.2 四种定向激励

扩展命令为：

```python
vehicle_accel_offset_mps2: tuple[float, float, float, float]
vehicle_steer_offset_deg: tuple[float, float, float, float]
```

初始开发模式：

| 模式 | 加速度偏置 | 转角偏置 | 目标 |
|---|---|---|---|
| longitudinal | `[+a,+a,-a,-a]` | `[0,0,0,0]` | 提高`T_x` |
| lateral | `[0,0,0,0]` | `[+d,-d,+d,-d]` | 提高`T_y` |
| diagonal_1 | `[+a,-a,-a,+a]` | `[+d,-d,-d,+d]` | FL/RR模态 |
| diagonal_2 | `[-a,+a,+a,-a]` | `[-d,+d,+d,-d]` | FR/RL模态 |

偏置先去均值，避免把整体加速误当内部力。开发初值`a=0.05 m/s²`、`d=0.25°`，只用于0.5--1 s短脉冲。

根据短脉冲数据修改：

- 目标内力低于50 N且无饱和：幅值增加25%；
- 货物合力/合力矩相对内部力过大：降低幅值并用有限差分响应矩阵做约束最小二乘；
- 轮胎原始利用率超过0.9：优先降低速度，再降低转角；
- 任一连接点超过数值告警：缩短脉冲，不做力裁剪；
- 四种响应仍相同：检查差动偏置是否真正进入`controls[4,2]`。

有限差分响应矩阵：

\[
H=\frac{\partial[w;f_{int}]}{\partial u}.
\]

求解小扰动：

\[
\min_{\Delta u}\|H_w\Delta u\|_2^2+
\lambda\|H_{int}\Delta u-f_{target}\|_2^2,
\]

同时满足加速度、转角和轮胎利用率约束。这样按数据形成内部力模式，不靠反复手调。

### 7.3 事件审计

修改`_vehicle_step_size`返回真实`candidate_origin`。事件根截断时：

- `selection_cause=EVENT_ROOT`；
- `candidate_origin`保留根前候选来源；
- 根后余量重新计算；
- 常规`ZONE_RESOLUTION`微步不能被写成`PROBE_LIMIT`。

每段峰值取起点、中点和终点三者最大；区间积分仍用中点或已验证求积。若峰值三点结果与细参考差异集中在卸载段，再加入局部有界极值搜索，不修改力律。

## 8. F2：连续调度器

扩展`run_finish.py`支持：

```text
FLOW_C1
N2_PILOT / N2_FULL
PHYSICS_STATIC
N3_PILOT / N3_FULL
N4_PILOT / N4_FULL
SELECT_PLANT
DATA_PILOT / DATA_FULL
TRAIN_SMOKE / MPC_INTERFACE
FINAL
```

阶段状态使用：

- `VERIFIED`；
- `NEEDS_REPAIR`；
- `REPAIRING`；
- `RETESTED`；
- `READY_NEXT`。

历史`BLOCKED_WITH_EVIDENCE`不覆盖，另建`flow_status.json`。每个`NEEDS_REPAIR`必须带`repair_code`和`next_action`，调度器不得只打印失败后结束说明。

调度器不会自动改源码；它负责生成数据诊断和下一动作。源码修改仍由执行者使用`apply_patch`完成并留痕。

## 9. F3：N2单连接器全相位

### 9.1 实验

```text
6速度 × 32相位 × 2力律 × 2积分器 = 768行
速度：Q05/Q50/Q95/Q99/0.25/1.0 m/s
积分器：F2与ES
参考：S4 tight DOP853 oracle
```

先跑Q95的32相位pilot，再跑全部。

验收目标：ES峰值`<=5%`、冲量`<=2%`、终态`<=1%`、接触时刻`<=2 μs`；R3平滑区每次穿越至少8个常规区间。

### 9.2 按数据修改

| 数据形态 | 优先解释 | 修改方向 |
|---|---|---|
| 所有相位近似同偏差 | 参考映射、尺度或力律接口错误 | 核对tight oracle键、时长和平移等价性 |
| 误差随2 ms相位周期变化 | 固定网格/事件分段问题 | 检查事件根、根后余量和candidate_origin |
| 峰值失败，冲量/终态通过 | 峰值采样遗漏 | 加起点/中点/终点或局部连续极值 |
| 冲量失败，峰值通过 | 求积或事件重启问题 | 核对分段冲量和时间守恒 |
| 终态失败，力指标通过 | 状态推进或符号问题 | 检查根后状态重启和质量尺度 |
| 接触时刻失败 | 根包围区间/容差 | 保存事件面三点，修bracket，不调力参数 |
| 只有高速平滑区不足8段 | 区域分辨率不足 | 提高`N_zone`或降低常规最大步，不扩大`delta_s` |
| 仅F2失败 | 固定步离散误差 | 作为积分器效应保留，不强修F2 |
| 15 kN数值告警 | 初态/单位/合法高载荷需区分 | 查单位与初态；合法高载荷转诊断工况，不做截断 |

修改后先复跑首败相位、相邻两相位、同速度其他力律和Q95回归，再恢复完整矩阵。

## 10. F4：四车物理和收敛

### 10.1 工况

- 四点依次接触；
- 两点和四点同时接触；
- 共同ICR正反转向；
- 直线进入弯道再退出；
- 四种定向内部力短脉冲。

候选为2 ms外层ES；比较1 ms、0.5 ms及0.1 ms常规步参考，控制统一20 ms保持。

### 10.2 按残差位置修改

| 现象 | 修改方向 |
|---|---|
| `F_payload+F_vehicle`不为0 | 查法向定义和两端符号 |
| 作用反作用过、共同原点力矩不过 | 查两端锚点和施力位置是否共线 |
| 车辆`vx`导数错 | 查世界/车体系旋转和质量 |
| 车辆`vy`导数错 | 查横向符号和科氏项 |
| 单车横摆错 | 查车辆连接点力臂 |
| 货物横摆错 | 查角点顺序和货物体坐标力臂 |
| 内力零空间错 | 查W矩阵、SVD容差和角点顺序 |
| 左右转镜像错但ICR残差小 | 先查镜像置换和报告索引，不改分配公式 |
| ICR残差大 | 查车辆中心迭代和有符号速度 |
| 只有连接力收敛慢 | 缩小事件常规步，保持20 ms控制不变 |
| 轮胎饱和 | 先降速度；若仍饱和再降虚拟转角并记录曲率变化 |

每次只改一个层，避免同时改坐标、控制和积分器后无法归因。

## 11. F5：完整工况与R3生效区

### 11.1 100 m工况

- 前30 m：初速2.0 m/s，`+0.40 m/s²`；
- 随后正阶跃5 s：虚拟前/后`+4°/-2°`；
- 随后反阶跃5 s：`-4°/+2°`；
- 剩余路段减速至0.7 m/s；
- 加速度、速度锁定反馈和最终施加量分别保存。

若匀速段速度误差偏大：先根据速度误差增加小幅PI，保持转向命令不变；若PI导致四车差动加速度增大，则分别限制共同量和零和量。

### 11.2 路径工况

- 阶跃转向保留为瞬态受力实验；
- 单移线使用连续S形命令；
- 回头弯使用1--2 s转角斜坡、恒曲率段和退出斜坡；
- 直线—弯道—直线单独报告过渡；
- 四种定向激励使用F1辨识后的差动控制。

### 11.3 R3优势不足时怎么修改

| 数据 | 解释 | 修改方向 |
|---|---|---|
| `E_smooth<5%`且R3≈V1 | 工况几乎没进入平滑区 | 增加开发集中的小形变/低幅脉冲覆盖；正常工况结论仍写“差异小” |
| `E_smooth`足够但`R_damp`很低 | 阻尼项不是主要载荷 | 分开报告弹簧/阻尼贡献；不夸大平滑权重作用 |
| 力跳下降但冲量/RMS同步大降 | 可能只是削弱力 | 检查轨迹和终态；不单凭平滑曲线判优 |
| 转向切换时R3更差且`v_n<0`集中 | 单边卸载阻尼可能不足 | 建立R3.5卸载/迟滞候选；R3.4原结果保留 |
| 只有F2下R3变差、ES正常 | 数值分辨率与力律交互 | 归因给积分器，不修改R3力律 |
| 单移线好、回头弯差 | 方法存在适用域 | 检查持续横摆、轮胎饱和和内力模态；分工况陈述 |
| 所有工况R3无优势 | 新力律贡献不足 | V1-ES继续形成可信基线；R3.5研究支路重新建模 |

平滑改善继续使用P99力跳、Welch绝对高频能量、冲量、RMS、轨迹误差和`T_x/T_y`联合判断。

## 12. F6：植物选择不阻断主线

选择结果不是“通过/永久停止”，而是分支：

1. `R3-ES_ADVANTAGE`：正式数据以R3-ES为主，同时保留V1-ES对照；
2. `R3-ES_VALID_NO_CLEAR_ADVANTAGE`：R3和V1各生成相同清洁数据，用后续预测实验判断可学习性；论文不写R3物理优势；
3. `R3-ES_NEEDS_R3_5`：V1-ES基线数据继续生成，R3.5按卸载、迟滞或参数辨识结果并行修正；
4. `INTEGRATOR_DOMINANT`：创新归因给事件积分/事件表示，而不是平滑力律。

无论哪一分支，都保留四因素数据，不能只保存表现最好的一组。

## 13. F7：数据生成和按覆盖修改

### 13.1 数据时钟

```text
20 ms控制保持
└─ 10 × 2 ms植物外步
   └─ 事件感知内部子步
```

区间`(t_{k-1},t_k]`的特征记为`e_k`：

\[
(x_k,u_k,e_k)\rightarrow x_{k+1}.
\]

未来区间`e_{k+1}`不能进入当前输入。

### 13.2 pilot

- 100m、直线、单移线、回头弯、过渡/定向五个场景族；
- 每族2条清洁轨迹，共10条；
- 2条mask/AoI接口轨迹，不进入清洁训练；
- 同seed至少重放1条。

### 13.3 根据覆盖修改

| 覆盖数据 | 修改方向 |
|---|---|
| 某连接点从未接触 | 增加对应角点的小幅定向轨迹 |
| 平滑区占比接近0 | 增加小形变、低速接触轨迹，不重复切窗口 |
| `T_x`有覆盖而`T_y`无覆盖 | 用F1横向响应矩阵更新差动转角 |
| 回头弯占比过高 | 增加直线和过渡轨迹，防止训练分布偏置 |
| 某字段训练集方差为0 | 从模型输入移除，但保留原始数据 |
| 验证/测试分布超出训练过多 | 只扩充训练development场景；不移动测试轨迹 |
| 因果扰动测试失败 | 修`e_k`索引并重建数据，不在加载器里临时移位 |
| 重放不一致 | 查随机源、线程和配置；保存数组差异位置 |

正式数据建议5族×20条清洁轨迹，另有每族5条external。轨迹级split固定为0--13训练、14--16验证、17--19测试。只有训练轨迹参与归一化。

## 14. F8：训练冒烟和接口修正

### 14.1 模型

固定线性：

\[
\hat x_{k+1}=Ax_k+Bu_k+b.
\]

双线性：

\[
\hat x_{k+1}=Ax_k+Bu_k+\sum_j u_{k,j}N_jx_k+b.
\]

只进行数据入口冒烟，报告1/5/10/20步，不宣称正式Koopman创新。

### 14.2 根据结果修正

| 现象 | 修改方向 |
|---|---|
| 一步就不如持久性基线 | 查`x_k/x_{k+1}`错位、单位和归一化 |
| 一步正常、20步爆炸 | 查谱半径、滚动时控制索引和状态反归一化 |
| bilinear出现病态矩阵 | 检查特征尺度，增加ridge，不删除不利轨迹 |
| 连接力预测差、状态正常 | 增加形变/相对速度或因果事件，不使用未来力 |
| 只在回头弯退化 | 保留工况结论，检查训练覆盖和活跃子空间 |
| 模型重载不一致 | 固定dtype、随机源和序列化字段 |
| MPC维数不匹配 | 更新接口映射和约束字段，旧MPC仍标历史 |

## 15. F9：证据、报告与审稿回答

新增或补全：

| 文件/目录 | 修改内容 | 输入 | 输出与复验 |
|---|---|---|---|
| `scripts/build_finish_report.py` | 从各stage的manifest汇总事实，不读取聊天结论 | F0--F8原始JSON/CSV/NPZ | `final/report.md`；随机抽取三项指标与原始数据手算一致 |
| `scripts/plot_finish.py` | 统一单位、图例、阶段阴影和四点颜色顺序 | 冻结的`figure_data` | PNG/PDF及同名CSV；无屏幕截图替代原始数据 |
| `scripts/build_review_matrix.py` | 把审稿意见映射到代码修改、实验和证据路径 | 审稿意见、work log、final manifest | `final/review_response_matrix.md`；每条意见标记已回答/部分回答/未回答 |
| `scripts/verify_repro.py` | 在空输出目录按manifest重建统计和图 | 冻结配置、源码和数据哈希 | `final/reproduce.json`；记录命令、退出码、耗时和差异 |
| `final/manifest.json` | 固化植物、Schema、数据split、模型、图和报告身份 | 所有冻结清单 | SHA256无缺失、无重复身份、无未解释文件 |

最终报告必须分开声明：

- 数值层：事件积分器是否收敛；
- 物理层：连接力是否进入四车与货物动力学；
- 力律层：R3相对V1在哪些暴露区有无优势；
- 学习层：当前只完成数据入口和预测冒烟，还是已经完成正式Koopman比较；
- 控制层：仅接口兼容，还是已有新植物上的闭环MPC证据。

若自动报告与原始数据不一致，以原始数据和生成代码为准，修报告后重新生成；不得手工改最终数值。若某项审稿意见仍无证据，保留“未回答”和最低成本补证，不用相邻指标替代。

## 16. 执行命令骨架

### 16.1 同步任务书

```powershell
$localPlan = 'D:\PDxc\Review\connector_flow.md'
$remotePlan = 'D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/revision_2026/connector_r3_4/protocol_flow.md'
scp $localPlan "5080:$remotePlan"
if ($LASTEXITCODE -ne 0) { throw 'protocol_flow sync failed' }
```

同步后本地和远端SHA256必须一致，并把旧`protocol_finish.md`保持只读。

### 16.2 当前C1修复

```powershell
$taskPython = 'E:\anaconda\envs\pytorch_new\python.exe'
$taskRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$taskR34 = Join-Path $taskRoot 'revision_2026\connector_r3_4'

$env:PYTHONDONTWRITEBYTECODE = '1'
& $taskPython -B -m pytest "$taskR34\tests\test_finish_steering.py" -q -p no:cacheprovider
& $taskPython -B -m pytest "$taskR34\tests" -q -p no:cacheprovider
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage FLOW_C1
```

每条命令的退出码都写工作记录。非0时不把无效产物交给下一层，而是读取`next_action.json`执行修正，再回到同一命令。

### 16.3 后续统一入口

```powershell
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N2_PILOT
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N2_FULL
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage PHYSICS_STATIC
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N3_PILOT
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N3_FULL
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N4_PILOT
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage N4_FULL
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage SELECT_PLANT
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage DATA_PILOT
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage DATA_FULL
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage TRAIN_SMOKE
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage MPC_INTERFACE
& $taskPython -B "$taskR34\scripts\run_finish.py" --project-root $taskRoot --stage FINAL
```

运行器应支持`--repair-revision Fxx`和`--resume-run-id`，但只允许恢复同一配置和源码哈希的未完成批次。

## 17. 工作记录

每次修改和每个实验立即追加同一个`work_log.md`：

```markdown
## R34-FLOW-XXX — YYYY-MM-DD HH:mm — 任务标题

- 请求/任务编号：
- 授权模式：执行实验
- flow_revision / run_id：
- 协议与源码SHA256：
- 使用的数据层：diagnostic / development / confirmation
- 读取的原始数据：
- 观测到的误差形态：
- 根因候选与反证：
- 根据数据选择的修改方向：
- 修改文件与函数：
- 修改前后SHA256：
- 最小复验命令与结果：
- 回归命令与结果：
- 原始产物：
- 结论类型：事实 / 推断 / 建议 / 未知
- 当前状态：NEEDS_REPAIR / REPAIRING / RETESTED / READY_NEXT
- next_action：
```

不得把修改方向写成已经达成的效果；原失败数据和原确认数据永久保留。

## 18. 图片和最终输出

最终至少交付：

1. C1镜像置换和共同ICR示意数据；
2. N2相位—误差热图；
3. N3四点峰值/冲量/终态收敛；
4. 100m阶段、速度、加速度和转向；
5. 四点`Fx/Fy`和方向箭头；
6. 四车横摆与货物/阵列参考横摆；
7. 货物合力/合力矩、完整内部力、`T_x/T_y`；
8. `E_smooth`和`R_damp`暴露图；
9. 四因素力跳、Welch绝对高频能量、RMS和冲量；
10. 数据事件/形变/力/轮胎利用率覆盖；
11. fixed linear/bilinear 1/5/10/20步冒烟结果；
12. 每轮修正前后首败对比。

每张图必须有同名`figure_data/*.csv`、单位、采样率、源NPZ和绘图脚本哈希。

## 19. 最终状态

连续任务书允许以下科学结论分支：

- `READY_R3_ES_WITH_ADVANTAGE`；
- `READY_R3_ES_NO_CLEAR_ADVANTAGE`；
- `READY_V1_ES_BASELINE_R3_5_CONTINUES`；
- `INTEGRATOR_DOMINANT_CONTINUE_KOOPMAN`。

它们都不是“实验白跑”。区别在于论文能够把创新归因给R3力律、事件积分器、可学习性，还是只保留可信物理基线。

当数据、训练冒烟和报告全部完成时再生成`READY_FOR_KOOPMAN_TRAINING.json`；其中必须写明所选植物、适用工况、未解决退化和确认数据身份。

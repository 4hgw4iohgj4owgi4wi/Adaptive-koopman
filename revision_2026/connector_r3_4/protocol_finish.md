# 连接器系统完整收尾执行书

> 编制时间：2026-08-27（Asia/Shanghai）  
> 本地交付：`D:\PDxc\Review\connector_finish.md`  
> 目标主机：5080（`DESKTOP-9IUUGEO`）  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 当前隔离源码：`revision_2026\connector_r3_4`  
> 当前隔离结果：`revision_2026\connector_r3_4_results`  
> 冻结解释器：`E:\anaconda\envs\pytorch_new\python.exe`  
> 授权模式：本文件仅是方案编写；用户再次明确要求执行后，才允许修改5080和启动实验  
> 接续关系：保留旧`connector_fix.md`及其S0--S4证据；本文件是S4人工复核之后的唯一后续执行依据

## 0. 先给结论

当前不能写“连接器已经完全完成”。已经完成的是单连接器数值层，尚缺四车系统接线、转向分配接入、完整工况、数据链和训练入口证据。

只有本执行书C0--C9全部通过，才允许写：

```text
COMPLETE_READY_FOR_KOOPMAN_TRAINING
```

本执行书的终点不是“曲线看起来平滑”，而是同时具备：

1. 单连接器数值可信；
2. 四点连接力真实作用于四辆车和货物；
3. 力、力矩、作用反作用和内部力一致；
4. Ackermann/共同ICR转向分配真实进入全部四车工况；
5. 直线、加减速、正反转向、单移线、回头弯和转弯过渡均通过；
6. R3相对V1的作用与适用范围被公平实验说明；
7. 新植物生成的数据无旧模型混入、无未来信息泄漏并可用于训练；
8. 固定线性和双线性训练冒烟可完成并可重复加载；
9. 原始数据、图、报告、代码和工作记录能够互相追溯。

## 1. 当前事实、错误前提和缺失信息

### 1.1 已确认事实

| 对象 | 当前事实 | 证据位置 | 判断 |
|---|---|---|---|
| 阶段状态 | S0--S3=`PASS`；S4=`PASS_AWAITING_MANDATORY_MANUAL_REVIEW`；S5--S10=`NOT_RUN` | `connector_r3_4_results/stage_status.json` | 已复核 |
| 单元测试 | 冻结解释器下`18 passed in 2.40 s` | 现场无缓存复跑 | 已复核 |
| N2A-v2 | 12个速度/力律对全部通过；48行固定参考、24行DOP853 oracle | `connector_r3_4_results/n2a` | 已复算 |
| 0.5 μs对oracle | 最坏归一化峰值/冲量/终态误差为`2.877e-7 / 9.722e-7 / 9.721e-7` | `n2a/checks.json` | 已复算 |
| 当前任务 | 无Python、MATLAB或训练进程 | 5080进程表 | 已确认 |
| 后续产物 | `connector_r3_4_data/models/mpc`文件数均为0 | 5080目录 | 已确认 |
| R3力律 | 本轮没有改R3力学代数或参数；`connector_r3.py`哈希仍为`0bd16c...0459` | S2源清单和工作记录 | 已确认 |
| 最新改动性质 | 最新改动主要是事件子步、参考求解和测试，不是新的连接器参数辨识 | 源码diff与工作记录 | 已确认 |

### 1.2 必须先处理的协议身份问题

远端S4结果冻结的`protocol.md`哈希为`31cc68ec...175eb`，本地较新的`connector_fix.md`哈希为`0A957AA5...EF462`，两者不同。不能把S4结果倒签为执行了最新本地任务书。

处理方法：

- 原远端`protocol.md`保持只读，继续作为S0--S4历史协议；
- 本文件同步成远端`protocol_finish.md`，只支配C0及以后任务；
- `r0_post_s4/provenance.json`同时登记两个协议的路径、大小、时间和SHA256；
- C0人工复核确认S4主要门没有被事后放宽后，生成正式`release.json`；
- 以后所有产物同时记录`historical_protocol_sha256`和`finish_protocol_sha256`。

### 1.3 现有后续代码不能直接运行

以下是源码事实，不是推测：

1. `scripts/run.py::run_n2`读取不存在的`n2a/reference_state_0p5us.json`，而当前N2A-v2实际输出为`fixed_reference.csv`、`oracle.csv`和`checks.json`；直接运行N2会在入口失败。
2. `run.py::scenario_control`给四辆车相同转角，没有调用共同ICR分配器，不能用于验证“已经完成的四车转向分配”。
3. `src/steering_allocator.py`仍导入旧`four_vehicle_coupled`，没有绑定R3.4的`four_vehicle_common`。
4. `paired_maneuvers_r3.py`、`spectral_metrics.py`、`build_pilot.py`和`train_compare.py`仍是占位文件。
5. `step_features.py`把端点接触布尔量写成区间占比，把端点平滑权重同时写成最小值、均值和最大值；不能用于正式训练数据。
6. 现有N3仅检查诊断量和简化轨迹，没有完成“连接力置零前后状态导数差分”证书。
7. `tire_force`当前返回缩放后的利用率，原始轮胎需求和饱和比例没有完整保存，可能掩盖转向工况被轮胎限幅的事实。

因此，C0放行后不能直接跳到`run.py --stage N2`，必须先完成C1代码接线和测试。

### 1.4 术语边界

- 当前30状态模型是地面平面模型；`Fx`为纵向分力，`Fy`为横向分力。
- 图纸平面中的“竖直方向”在本文统一写成“横向”，不能称为重力方向`Fz`。
- 当前模型没有悬架、俯仰、侧倾和真实竖向载荷传递，不能用本实验回答真实`Fz`问题。
- `rated_force_n=12 kN`、`ultimate_force_n=15 kN`的来源字段是`numerical_legacy_unverified`；它们只能作为数值告警/停止边界，不是实物额定或破断安全值。
- `tension_x_n/tension_y_n`是货物纵向/横向拉伸载荷代理，不是货物撕裂判据。

## 2. 完成定义和论文声明层级

### 2.1 技术完成

必须同时满足：

- C0：S4证据正式人工放行；
- C1：后续代码、旧18项测试和新增测试全部通过；
- C2：N2 768行单连接器全相位矩阵通过；
- C3：四车静态接线与动态收敛通过；
- C4：完整工况与四因素比较通过物理门；
- C5：植物选择有冻结文件；
- C6：pilot数据、因果、覆盖和确定性通过；
- C7：正式数据及轨迹级划分通过；
- C8：训练冒烟和MPC接口检查通过；
- C9：报告、图、清单和独立复核通过。

### 2.2 R3优势声明

技术完成不自动等于R3优于V1。只有C4优势门通过，才能写“R3在注册工况中降低连接力突变/高频能量，且没有造成超过预注册上限的冲量、轨迹或拉伸载荷代理退化”。

若物理门通过但优势门失败，允许生成可信数据，但最终状态必须区分：

```text
COMPLETE_READY_FOR_KOOPMAN_TRAINING_R3_ADVANTAGE
COMPLETE_READY_FOR_KOOPMAN_TRAINING_NO_R3_ADVANTAGE
```

第二种状态不得把R3平滑公式写成已证实的论文创新。

### 2.3 不在本执行书内的声明

- 不证明货物不会损坏或撕裂；
- 不证明参数对应真实连接器；
- 不完成正式Koopman创新比较；
- 不恢复旧MPC结论；
- 不进入通信扰动、DoS或网络保护实验。

这些任务必须在新数据和新预测模型完成后另立执行书。

## 3. 模型与验收公式

### 3.1 状态

第`i`辆车：

\[
x_i=[X_i,Y_i,\psi_i,v_{x,i},v_{y,i},r_i]^T.
\]

货物：

\[
x_p=[X_p,Y_p,\psi_p,v_{x,p},v_{y,p},r_p]^T.
\]

完整状态为4辆车加货物，共30维。`\psi_p,r_p`作为货物/阵列参考横摆；四车横摆分别报告。禁止用四车横摆的算术平均冒充系统横摆。

### 3.2 连接器几何和力律

第`i`个连接点，以“货物连接点指向车辆连接点”为正方向：

\[
d_i=p_i^v-p_i^p,\quad
v_i=\dot p_i^v-\dot p_i^p,
\]

\[
n_i=\frac{d_i}{\max(\lVert d_i\rVert,\epsilon)},\quad
q_i=\lVert d_i\rVert-l_0,\quad
\delta_i=\max(q_i,0),\quad
v_{n,i}=v_i^Tn_i.
\]

令`z_i=clip(\delta_i/\delta_s,0,1)`：

\[
g(\delta_i)=
\begin{cases}
0,&\delta_i\le0,\\
3z_i^2-2z_i^3,&0<\delta_i<\delta_s,\\
1,&\delta_i\ge\delta_s.
\end{cases}
\]

R3拉力：

\[
f_i=k\delta_i+c\,g(\delta_i)\max(v_{n,i},0).
\]

\[
F_i^p=f_i n_i,\qquad F_i^v=-F_i^p.
\]

阻尼只在加载阶段生效是当前单边连接器建模假设。若实验显示卸载振荡无法解释，必须停止并另立R3.5，不得在本版本中临时加入回程阻尼。

### 3.3 单车和货物动力学中的连接力

对每辆车：

\[
\dot X_i=v_{x,i}\cos\psi_i-v_{y,i}\sin\psi_i,
\]

\[
\dot Y_i=v_{x,i}\sin\psi_i+v_{y,i}\cos\psi_i,
\]

\[
\dot v_{x,i}=\frac{F_{x,i}^{tire}+F_{x,i}^{v}}{m_i}+r_i v_{y,i},
\]

\[
\dot v_{y,i}=\frac{F_{y,i}^{tire}+F_{y,i}^{v}}{m_i}-r_i v_{x,i},
\]

\[
\dot r_i=\frac{M_{z,i}^{tire}+M_{z,i}^{v}}{I_{z,i}}.
\]

连接点横摆力矩：

\[
M_{z,i}=r_{x,i}F_{y,i}-r_{y,i}F_{x,i}.
\]

货物采用同样的体坐标速度形式，其平面合力和合力矩只由四个货物端连接力构成。代码差分验收必须证明`F_x`、`F_y`和`M_z`分别改变对应状态导数。

### 3.4 作用反作用和共同原点力矩

每点：

\[
F_i^p+F_i^v=0.
\]

因为两端力共线，关于任意共同世界原点的该连接器内力矩应满足：

\[
\tau_i=p_i^p\times F_i^p+p_i^v\times F_i^v\approx0.
\]

验收采用：

\[
\max_i\lVert F_i^p+F_i^v\rVert<10^{-10}\ \mathrm{N},
\]

\[
\max_i|\tau_i|<10^{-8}\max(1\ \mathrm{N\,m},|p_i^p\times F_i^p|).
\]

### 3.5 完整内部力

将货物体坐标四点力按`FL,FR,RL,RR`堆叠：

\[
f=[F_{x,FL},F_{y,FL},\ldots,F_{x,RR},F_{y,RR}]^T.
\]

\[
w=Wf=[F_x,F_y,M_z]^T,
\]

\[
f_{motion}=W^\dagger w,\qquad
f_{int}=(I-W^\dagger W)f.
\]

硬门：

\[
\lVert Wf_{int}\rVert_2<10^{-8}\max(1\ \mathrm{N},\lVert f_{int}\rVert_2).
\]

### 3.6 货物拉伸载荷代理

定义前、后、左、右两点合力：

\[
F_F=F_{FL}+F_{FR},\quad F_R=F_{RL}+F_{RR},
\]

\[
F_L=F_{FL}+F_{RL},\quad F_{Rt}=F_{FR}+F_{RR}.
\]

\[
T_x=\frac12\max\left(0,(F_F-F_R)^Te_x\right),
\]

\[
T_y=\frac12\max\left(0,(F_L-F_{Rt})^Te_y\right).
\]

字段固定为：

- `tension_x_n`：货物纵向拉伸载荷代理；
- `tension_y_n`：货物横向拉伸载荷代理。

禁止再使用`opening`，也禁止把`T_x/T_y`与材料破坏阈值比较。

### 3.7 数值分辨率

\[
\tau_s=\frac{\delta_s}{\max(|v_n|,\epsilon)}.
\]

事件步可小于2 μs；只有常规区域分辨率主动要求小于2 μs才算不可解析。每个2 ms外层周期必须满足：

\[
\left|H-\sum_jh_j^{advanced}-r_{floating}\right|\le10^{-12}\ \mathrm{s}.
\]

## 4. 版本隔离和目录

禁止覆盖S0--S4产物。新增：

```text
revision_2026/
├─ connector_r3_4/
│  ├─ protocol.md                 # S0--S4历史协议，只读
│  ├─ protocol_finish.md          # 本执行书
│  ├─ configs/
│  │  ├─ n2_finish.json
│  │  ├─ n3_finish.json
│  │  ├─ maneuvers_finish.json
│  │  ├─ data_pilot.json
│  │  └─ data_full.json
│  ├─ scripts/run_finish.py
│  └─ tests/...
├─ connector_r3_4_results/
│  ├─ r0/ ... n2a/                # 已有，只读
│  ├─ r0_post_s4/
│  ├─ s4_review/
│  ├─ implementation/
│  ├─ n2_pilot/  n2/
│  ├─ physics_static/
│  ├─ n3_pilot/  n3/
│  ├─ n4_pilot/  n4/
│  ├─ plant_selection/
│  ├─ data_audit/
│  ├─ figures/  figure_data/
│  ├─ report.md
│  ├─ solutions.md
│  ├─ work_log.md
│  └─ artifact_manifest.json
├─ connector_r3_4_data/
│  ├─ pilot/<run_id>/
│  └─ full/<run_id>/
├─ connector_r3_4_models/smoke/<run_id>/
└─ connector_r3_4_mpc/interface/<run_id>/
```

所有高成本阶段使用`run_id=YYYYMMDD_HHMMSS_<stage>`。若目标目录非空且没有相同`run_id`恢复令牌，入口必须拒绝运行，禁止覆盖。

## 5. 代码修改表

| 文件 | 函数/类 | 必须修改 | 输入 | 输出/测试 |
|---|---|---|---|---|
| `protocol_finish.md` | 全文 | 同步本文件；保留历史协议 | 本地MD | 双协议哈希 |
| `scripts/run_finish.py` | 新增后扩展 | 引导时只实现C0；C0放行后扩展为C0--C9唯一调度器；前置门、run_id、失败即停、状态原子更新 | stage/config | 每阶段`complete.json` |
| `scripts/release_s4.py` | 新增 | 复算N2A CSV/JSON、核对源哈希、测试和阈值，生成正式人工放行文件 | S0--S4证据 | `s4_review/release.json` |
| `scripts/run_n2_finish.py` | 新增 | 从N2A-v2的`tight oracle`生成参考映射；执行32相位四因素矩阵 | N2配置 | 768行CSV、最坏trace |
| `scripts/run_n3_finish.py` | 新增 | 四车收敛、接线、共同控制时钟和参考比较 | N3配置 | 时序、比较、证书 |
| `scripts/run_maneuvers.py` | 新增 | 100m、直线、单移线、回头弯、定向激励 | 工况配置 | 成对时序 |
| `scripts/select_plant.py` | 新增 | 按预注册门选择V1/R3与F2/ES，不按主观挑图 | N2--N4 | `plant_selection.json` |
| `scripts/generate_data.py` | 新增 | 新植物唯一数据入口；轨迹级切分和清单 | 数据配置 | NPZ、manifest |
| `scripts/verify_data.py` | 新增 | schema、因果、确定性、覆盖、旧import和重绘复核 | 数据目录 | `data_certificate.json` |
| `scripts/train_smoke.py` | 新增 | fixed linear和bilinear闭式/小预算冒烟 | 冻结数据 | 模型、滚动误差 |
| `scripts/check_mpc_interface.py` | 新增 | 只检查20 ms周期、状态/控制维数、模型加载和约束字段；不运行旧闭环 | 数据证书/冒烟模型 | `READY_FOR_MPC_RETUNING.json` |
| `scripts/plot_evidence.py` | 扩展 | 只从原始数据生成图和figure_data | 原始NPZ/CSV | PNG+CSV |
| `scripts/finalize_report.py` | 扩展 | 汇总事实、限制、失败与论文声明边界 | 全阶段 | report/status |
| `src/steering_allocator.py` | imports/`allocate_controls` | 改导入R3.4植物；输出未裁剪/已施加转角、裁剪标志、ICR残差 | state/虚拟4WS | 镜像和ICR测试 |
| `src/four_vehicle_common.py` | `connector_diagnostics` | 增加世界/货物体/车辆体坐标、共同原点内力矩、`T_x/T_y` | state/law | 物理诊断 |
| 同上 | `assemble_derivative`新增 | 将轮胎项、连接项和运动学项显式分解，便于置零差分 | state/control/diag | 导数分解 |
| 同上 | `system_derivative` | 调用统一组装；保存原始轮胎利用率、缩放比和饱和标志 | state/control | dx30+诊断 |
| `src/internal_force.py` | `tension_load_proxies`新增 | 固定角点顺序，输出`T_x/T_y`；保留完整零空间 | 四点体坐标力 | 解析模式测试 |
| `src/event_substep.py` | `advance_outer_step`审计 | 保存每个接受段的dt、力积分、接触/平滑时长、权重与形变极值 | 外层步 | interval audit |
| `src/step_features.py` | `aggregate_step_audit` | 用真实dt加权，不能用端点冒充区间统计；支持10个外步聚合为20 ms | audit列表 | 因果特征 |
| `src/paired_maneuvers_r3.py` | 实现 | 所有工况只调用共同ICR分配器和R3.4事件植物 | 场景配置 | 控制时钟/轨迹 |
| `src/spectral_metrics.py` | 实现 | Hann-Welch、Parseval、跳变量、RMS和冲量 | 2 ms时序 | 光谱指标 |
| `src/schema_r3.py` | 扩展 | 字段、维数、单位、坐标、时刻、mask/AoI权限和版本 | 配置 | `schema.json` |
| `control_source_generate_k2.py` | 标记弃用 | 顶部明确拒绝正式R3.4数据；禁止旧植物导入 | 任意调用 | 非0退出和说明 |
| `run.py` | N2/N3入口 | 标记为历史入口并拒绝继续阶段，指向`run_finish.py` | N2/N3 | 防误执行测试 |

## 6. 新增测试合同

### 6.1 旧测试

- 当前18项测试必须继续全部通过；
- 测试ID和源码哈希写入`implementation/test_contract.json`；
- 新增测试后以ID清单为准，不用模糊的“至少若干项”。

### 6.2 物理测试

必须至少覆盖：

1. 四点世界坐标作用反作用；
2. 四点共同原点内力矩平衡；
3. 世界系到货物/车辆体系旋转往返；
4. 纯`Fx`只改变预期纵向导数；
5. 纯`Fy`只改变预期横向导数；
6. 偏置力只按`r_xF_y-r_yF_x`改变横摆导数；
7. 每辆车四个连接点逐一置零/恢复差分；
8. 货物四点逐一置零/恢复差分；
9. 完整内部力零空间；
10. 纯纵向、纯横向、纯力矩和纯内部力解析构造；
11. `tension_x_n/tension_y_n`的纵向、横向和镜像构造；
12. 小于50 N时方向标记为`INACTIVE`。

### 6.3 转向分配测试

必须覆盖：

- 直线：四车目标相对航向、转角和法向速度残差为0；
- 左/右镜像：转角、ICR和车辆目标航向镜像；
- 前后轮同相接近蟹行时的有限解；
- 共同ICR法向速度残差`<=1e-8 m/s`；
- 未裁剪值、裁剪后值、裁剪标志和裁剪比例均可追溯；
- R3.4源码静态扫描不再导入`four_vehicle_coupled`。

### 6.4 区间特征和数据测试

必须覆盖：

- 常力解析冲量；
- 单一接触事件的接触占空比；
- 平滑区`g_min/g_mean/g_max`；
- 10个2 ms外步聚合为20 ms且总时长精确；
- 将未来区间事件任意改变，不得改变当前`e_k`；
- 轨迹窗口不跨轨迹或split；
- 训练归一化统计不读取验证、测试或external；
- 保存重载后数组和元数据一致。

### 6.5 光谱测试

- 单频正弦的主频位置；
- 常值信号去均值后高频能量接近0；
- Parseval相对误差`<=1%`；
- 相同2 ms采样率和相同窗配置才允许配对比较。

## 7. 顺序任务树

```text
C0  双协议冻结 + S4正式人工放行
 └─ FAIL：停止，S5以后NOT_RUN

C1  后续代码接线 + 旧测试回归 + 新测试合同
 └─ FAIL：停止，不运行N2

C2  N2 pilot → N2 768行全相位矩阵
 └─ FAIL：停止，不运行四车

C3  静态物理证书 → N3 pilot → N3完整动态收敛
 └─ FAIL：停止，不运行长工况

C4  100m pilot → 完整工况四因素公平比较
 └─ FAIL：停止，不生成数据

C5  预注册植物选择
 ├─ R3优势PASS：冻结R3-ES
 ├─ 物理PASS但R3优势FAIL：冻结可用植物并限制论文声明
 └─ 物理FAIL：停止，另立R3.5

C6  数据代码/因果测试 → 10条清洁pilot + 2条接口轨迹
 └─ FAIL：删除“可训练”声明，保留失败pilot并停止

C7  正式清洁数据 + external覆盖 + 独立数据证书
 └─ FAIL：停止，不训练

C8  fixed linear/bilinear冒烟 → MPC接口检查
 └─ FAIL：停止在学习/接口层

C9  图片、报告、工作记录、清单和最终状态
 └─ FAIL：不得标记完成
```

## 8. 分阶段执行细节

### C0：双协议冻结与S4人工放行

#### 前置

- 用户明确授权执行；
- 无其他任务写入R3.4目录；
- S4原始CSV、JSON和源清单存在；
- 旧S0--S4目录只读。

#### C0.0 引导边界

`run_finish.py`在当前源码中尚不存在，不能假定调度器已经可用。引导阶段只允许用`apply_patch`新增三个文件：

1. `protocol_finish.md`；
2. 只支持`--stage C0`的最小`run_finish.py`；
3. `release_s4.py`。

此时禁止修改`src/`、`tests/`、旧`run.py`和任何S0--S4产物。最小C0入口必须先用`r0/source_manifest_s2.json`逐项核对所有既有源码；只允许上述三个新增文件不在历史清单内。若任一历史文件哈希漂移，C0立即FAIL。C0放行后才按C1扩展调度器和后续源码。

#### 操作

1. 将本文件同步为远端`protocol_finish.md`；
2. 创建`r0_post_s4`，保存环境、进程、磁盘、两个协议哈希、当前源码哈希和S0--S4产物哈希；
3. 用冻结解释器执行旧18项测试，设置`PYTHONDONTWRITEBYTECODE=1`并关闭pytest缓存；
4. 从CSV/JSON独立复算S4全部12对；
5. 检查`run_n2a_v2.py`门槛仍为运行前登记值；
6. 核对Q05/V1、Q95/V1、Q95/R3、stress1.0/R3的事件序列；
7. 生成`s4_review/release.json`，明确“结果属于历史协议，人工复核后获准用于新协议后续阶段”。

#### 硬门

- 18/18测试通过；
- 12/12 S4对通过；
- oracle/固定参考最大误差与现有原始数据一致；
- 力律哈希未漂移；
- 两协议身份均已登记；
- S4主要阈值未事后放宽；
- `release.json.approved=true`。

#### 失败

状态`BLOCKED_C0_S4_RELEASE`。不得重写旧S4报告凑PASS；根据源漂移、数据缺失或复算不一致分别保存最小复现。

### C1：后续代码实现和测试冻结

#### 实现顺序

1. 先修`steering_allocator.py`旧导入并添加分配审计；
2. 再拆分`system_derivative`并补充物理诊断；
3. 实现内部力和拉伸载荷代理；
4. 实现事件区间统计和20 ms聚合；
5. 实现N2/N3/工况/数据/报告脚本；
6. 标记旧N2/N3和旧数据入口为禁止使用；
7. 新增测试，冻结测试ID清单；
8. 先跑旧18项，再跑全部测试。

#### 硬门

- 旧18项仍全部通过；
- 新测试ID与`test_contract.json`完全一致并全部通过；
- 无skip、xfail或根据结果修改阈值；
- 静态扫描确认后续入口不导入旧植物；
- 所有新增JSON禁止NaN/Infinity；
- 每个修改文件有前后SHA256和diff摘要；
- 生成`implementation/complete.json`。

#### 失败

首败后停止，不同时修多个层。物理测试失败只修物理接线；数据测试失败不能通过放宽物理门解决。

### C2：N2全相位单连接器矩阵

#### 参考修正

现有`run_n2`引用文件不存在，必须改为读取`n2a/oracle.csv`中`tier=tight`的12条记录。对每个相位，接触前连接力为0，因此相位只平移接触时刻；接触后的参考时长与S4一致。另选每个速度/力律一个非零相位，直接调用oracle包含接触前自由段，验证时间平移等价性。

#### 矩阵

```text
速度：Q05/Q50/Q95/Q99/0.25/1.0 m/s
相位：32个，均匀覆盖2 ms外层网格
力律：V1/R3
积分器：F2/ES
总行数：6 × 32 × 2 × 2 = 768
```

先运行Q95全32相位pilot；pilot通过才运行完整矩阵。

#### 尺度

- 峰值：`max(|F_ref|,50 N)`；
- 冲量：`max(|J_ref|,50 N*T_post)`；
- 位移：`max(delta_s,|q_ref|,v*0.002,1e-6 m)`；
- 速度：`max(v,|v_ref|,1e-4 m/s)`。

#### ES硬门

- 峰值尺度化误差`<=5%`；
- 冲量尺度化误差`<=2%`；
- 终态尺度化误差`<=1%`；
- 接触时刻绝对误差`<=2 μs`；
- R3每次完整平滑穿越至少8个常规有效区间，事件根段单列；
- 所有亚2 μs真实推进只允许由`EVENT_ROOT`或`OUTER_REMAINDER`产生；
- 无负拉力、NaN/Inf、事件循环、静默力裁剪；
- 15 kN只触发数值停止并使该用例FAIL；
- 全部32相位保留，报告均值、P95/P99和最坏相位。

F2结果是离散误差诊断，不用ES门强制F2通过。

#### 产物

- `n2/single_connector_factorial.csv`；
- `n2/reference_map.json`；
- `n2/time_shift_checks.json`；
- 每个速度/力律最坏相位完整trace；
- `n2/complete.json`。

### C3：四车静态物理和动态收敛

#### C3.1 静态接线证书

对同一状态和控制分别计算：

- 正常连接器`dx_total`；
- 将连接器动力学贡献置零的`dx_zero`；
- 理论连接贡献`dx_formula`。

验证：

\[
dx_{total}-dx_{zero}=dx_{formula}.
\]

车辆和货物的`vx/vy/r`通道均使用：

\[
\frac{|\Delta\dot x_{code}-\Delta\dot x_{formula}|}
{\max(10^{-12},|\Delta\dot x_{formula}|)}\le10^{-10},
\]

对理论值接近0的通道改用绝对误差`<=1e-12`。四个连接点逐点激活，不能只测全部同时激活。

#### C3.2 动态矩阵

工况：

1. Q99四点不同接触时刻；
2. 2 s共同ICR正反转向；
3. 直线进入弯道再退出的过渡片段。

每工况：

```text
V1-F2, V1-ES, R3-F2, R3-ES：外层2 ms
V1/R3-ES：外层1 ms、0.5 ms
V1/R3参考：控制仍20 ms保持，事件步最大常规步0.1 ms
```

候选、减半步和参考必须使用同一20 ms控制序列，禁止参考解更新控制更频繁。

#### 动态硬门

- 四点峰值误差`<=5%`；
- 四点冲量误差`<=2%`；
- 终态尺度化误差`<=1%`；
- 完整内部力、货物合力矩和单车连接力矩误差`<=5%`；
- 作用反作用、共同原点力矩和内部力零空间门通过；
- 2/1/0.5 ms差异未到数值地板时单调下降且`p_obs>=0.9`；
- Ackermann/ICR残差`<=1e-8 m/s`；
- 无未登记转角/轮胎限幅；
- 无NaN/Inf、事件循环和15 kN停止。

### C4：完整工况和四因素比较

#### C4.1 100 m分阶段工况

以货物质心累计路程`s_p`切换：

| 阶段 | 条件 | 纵向命令 | 虚拟4WS命令 |
|---|---|---|---|
| A加速 | `0<=s_p<30 m` | 初速`2.0 m/s`，`a=+0.40 m/s²` | `0°/0°` |
| B正阶跃 | 从30 m起5.00 s | 锁定30 m处实际速度`v30` | 前/后`+4°/-2°` |
| C反阶跃 | 随后5.00 s | 继续锁定`v30` | 前/后`-4°/+2°` |
| D减速 | 剩余路段 | 目标`0.7 m/s` | `0°/0°` |

D段前馈：

\[
a_D=\frac{0.7^2-v_D^2}{2(100-s_D)}.
\]

若`a_D`不在`[-1.4,0) m/s²`，配置直接FAIL，不得静默裁剪。

硬门：终点`100.00±0.05 m`；两个阶跃各`5.00±0.02 s`；匀速P95误差`<=max(0.10 m/s,0.03v30)`；终速`0.7±0.2 m/s`；无转角或轮胎未登记饱和。

#### C4.2 其他注册工况

- `straight_constant`：直线匀速，检查噪声底和无转向基线；
- `single_lane_change_left/right`：左右镜像各5个冻结种子；
- `hairpin_left/right`：入弯、持续弯道、出弯，左右镜像各5个种子；
- `connector_longitudinal`：前后零和差动激励；
- `connector_lateral`：左右零和差动激励；
- `connector_diagonal_1/2`：两条对角差动激励；
- `line_curve_transition_left/right`：直线—弯道—直线过渡。

每个成对实验使用相同初态、参数、控制、随机种子和停止条件。

#### C4.3 四因素

| 组 | 力律 | 积分器 | 用途 |
|---|---|---|---|
| V1-F2 | V1 | 固定2 ms | 历史离散基线 |
| V1-ES | V1 | 事件步 | 积分器主效应 |
| R3-F2 | R3 | 固定2 ms | R3离散敏感性 |
| R3-ES | R3 | 事件步 | 新候选 |

#### C4.4 必报量

- 四点世界系和货物体系`Fx/Fy`、模长和方向角；
- `||F||<50 N`时方向=`INACTIVE`；
- 四车`psi_i/r_i`与货物/阵列参考`psi_p/r_p`；
- 每车连接力矩、货物合力/合力矩；
- 完整`f_int`、`tension_x_n/tension_y_n`；
- 原始和施加轮胎利用率、缩放比、饱和比例；
- 接触/平滑事件、区间冲量、能量和计算成本；
- 转向开始、正反切换、结束各±1 s放大窗。

#### C4.5 平滑与优势门

共同2 ms网格，Hann-Welch，50%重叠，去均值，高频带`>25 Hz`，Parseval误差`<=1%`。同时报告最大/P95/P99力跳、高频绝对能量、高频占比、RMS和冲量。

R3优势目标：

- R3-ES相对V1-ES的事件窗P99力跳和高频绝对能量中位改善均`>=10%`；
- 轨迹级成对bootstrap，固定种子`20260827`、重采样`10,000`次，95%区间下界`>0`；
- 任一注册场景的冲量、轨迹误差、`T_x/T_y` P95不得退化超过`5%`；
- 不能靠平均值掩盖单移线、回头弯或转向切换退化。

物理门失败则停止；只有优势门失败时才进入C5的限制性选择。

### C5：植物选择

`select_plant.py`只能按预注册规则输出：

1. R3-ES物理门和优势门均过：选择`R3-ES`；
2. R3-ES物理门过、优势门不过：可选`R3-ES`作为可微/连续候选，或选`V1-ES`作为预测基线，但必须写`NO_R3_ADVANTAGE`；
3. R3-ES物理门失败而V1-ES通过：R3.4连接器创新停止，不能偷偷用V1数据声称R3完成；
4. 两者均失败：回到物理/数值层，禁止生成数据。

输出必须包含选择理由、失败场景、适用域、代码哈希、参数、积分器配置和论文可写声明。

### C6：数据入口和pilot

#### 时钟

```text
20 ms控制保持
└─ 10 × 2 ms外层植物审计
   └─ 每个外层步内部事件分段
```

#### 因果特征

区间`(t_{k-1},t_k]`的已完成统计记作`e_k`：

\[
(x_k,u_k,e_k)\rightarrow x_{k+1}.
\]

禁止使用`(t_k,t_{k+1}]`内才可获得的`e_{k+1}`。

区间均值和占比：

\[
\bar F_k=\frac1{T_c}\sum_jF_{mid,j}\Delta t_j,
\quad
J_k=\sum_jF_{mid,j}\Delta t_j,
\]

\[
c_k=\frac1{T_c}\sum_j\mathbf 1_{contact,j}\Delta t_j.
\]

`g_mean`按真实dt加权；极值从全部真实子段取，不能由端点替代。

#### 状态集合

- `S1_team`：论文原低信息基线，只作消融；
- `S2_four`：30维完整物理状态；
- `S3_deform`：30状态+4点二维形变+4点二维相对速度，共46维；
- `S4_force_event`：S3加四点力、完整内部力、`T_x/T_y`和因果事件统计，维数由schema生成，禁止手写。

控制主输入是四车实际8维`[a_i,delta_i]`；虚拟前后转角、分配器状态和系统2维等效输入仅作为消融，不替代实际控制。

#### pilot

- 5个清洁场景族：100m、直线、单移线、回头弯、定向/过渡；每族2条，共10条；
- 另生成2条network接口轨迹，只验证mask/AoI字段，不进入清洁训练；
- 固定种子；至少一条清洁轨迹重复生成验证SHA256一致；
- pilot通过前禁止正式数据。

#### pilot硬门

- 数组有限、时间严格递增、长度合同正确；
- `plant_id/law_id/integrator_id/schema_id`齐全；
- 无旧植物import；
- 因果测试通过；
- 100m合同和全部物理门通过；
- 每个注册接触/平滑/内力模态至少在一个清洁场景出现；
- 原始轮胎利用率、限幅、四点力和事件均保存；
- 原始NPZ可重绘全部验收图。

### C7：正式数据

pilot通过后冻结`data_full.json`：

- 5个清洁场景族，每族20条，共100条；
- 每族5条参数外推，共25条external；
- 清洁种子固定为`64000 + 1000*scenario_index + traj_id`；external在此基础上加`9000`；
- 每族轨迹ID `0--13`训练、`14--16`验证、`17--19`测试；
- external不参与归一化、调参或选择；
- 窗口不得跨轨迹；
- 归一化只用训练轨迹；
- 场景、参数和种子清单在运行前冻结。

数据硬门：

- 所有轨迹通过物理停止条件；
- 同seed重放哈希一致，若浮点库导致字节不同，则数组最大绝对差`<=1e-12`并说明；
- split无轨迹或窗口泄漏；
- 每个训练输入字段在训练集有有效方差，常量字段必须从训练输入删除但保留在原始数据；
- 测试/external覆盖不用于修改模型或归一化；
- 输出`data_certificate.json`和文件级SHA256清单。

### C8：训练冒烟和MPC接口

训练冒烟只证明数据入口可用，不证明Koopman方法创新。

#### fixed linear

对归一化状态和控制：

\[
\hat x_{k+1}=Ax_k+Bu_k+b.
\]

#### bilinear

\[
\hat x_{k+1}=Ax_k+Bu_k+\sum_{j=1}^{8}u_{k,j}N_jx_k+b.
\]

使用同一训练轨迹、归一化、ridge系数候选和验证选择；external完全不可见。闭式特征矩阵为`[x,u,vec(xu^T),1]`，禁止使用未来事件。

训练冒烟固定随机种子`3407`；ridge候选`{1e-8,1e-6,1e-4,1e-2}`只用验证集选择，测试集只在模型冻结后评估一次。

#### 冒烟硬门

- 训练、验证、1/5/10/20步滚动全部有限；
- fixed linear一步验证NRMSE不劣于持久性基线超过5%；
- 保存、重载后同批输出最大绝对差`<=1e-10`；
- 记录参数量、训练时间、推理时间、每工况误差；
- 不要求bilinear全局优于linear；退化必须保留；
- 生成`READY_FOR_KOOPMAN_TRAINING.json`。

MPC只做接口检查：20 ms控制周期、状态/控制维数、模型加载和约束字段可读取。生成`READY_FOR_MPC_RETUNING.json`，不得写“旧MPC仍有效”。

### C9：图、报告和最终证书

必须生成以下可复绘图片：

1. N2四级参考和相位误差；
2. N3四点峰值/冲量/终态收敛；
3. 100m距离、速度、加速度和虚拟/实际转向；
4. 四点货物体坐标`Fx`；
5. 四点货物体坐标`Fy`；
6. 关键时刻四点力方向箭头；
7. 四车横摆与货物/阵列参考横摆；
8. 货物合力、合力矩和每车连接力矩；
9. 完整内部力、`tension_x_n/tension_y_n`；
10. 力跳、Welch绝对高频能量、RMS和冲量四因素对比；
11. 场景/事件/形变/力/轮胎利用率数据覆盖；
12. 冒烟模型1/5/10/20步误差。

每张PNG必须有同名`figure_data/*.csv`、单位、采样率、配置、源NPZ和绘图脚本哈希。

最终清单生成顺序：先报告和图，后`artifact_manifest.json`，最后用独立脚本核验；清单不包含自身哈希，避免循环。

## 9. 运行命令

### 9.1 本地同步新协议

```powershell
$localPlan = 'D:\PDxc\Review\connector_finish.md'
$remotePlan = 'D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/revision_2026/connector_r3_4/protocol_finish.md'
Get-FileHash -LiteralPath $localPlan -Algorithm SHA256
scp $localPlan "5080:$remotePlan"
if ($LASTEXITCODE -ne 0) { throw 'protocol sync failed' }
```

同步后必须在5080再次计算哈希并与本地逐字符一致。

### 9.2 5080执行骨架

以下命令只能在C1代码完成并经用户授权后使用：

```powershell
$ErrorActionPreference = 'Stop'
$taskPython = 'E:\anaconda\envs\pytorch_new\python.exe'
$taskRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$taskRunner = Join-Path $taskRoot 'revision_2026\connector_r3_4\scripts\run_finish.py'

function Invoke-ConnectorStage([string]$stage, [string]$config = '') {
    $args = @('--project-root', $taskRoot, '--stage', $stage)
    if ($config) { $args += @('--config', $config) }
    & $taskPython $taskRunner @args
    if ($LASTEXITCODE -ne 0) { throw "$stage failed with exit code $LASTEXITCODE" }
}

Invoke-ConnectorStage 'C0'
# C0结束后必须读取s4_review/release.json；approved不为true则退出当前终端。

Invoke-ConnectorStage 'C1'
Invoke-ConnectorStage 'N2_PILOT' (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\n2_finish.json')
Invoke-ConnectorStage 'N2'       (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\n2_finish.json')
Invoke-ConnectorStage 'PHYSICS_STATIC'
Invoke-ConnectorStage 'N3_PILOT' (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\n3_finish.json')
Invoke-ConnectorStage 'N3'       (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\n3_finish.json')
Invoke-ConnectorStage 'N4_PILOT' (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\maneuvers_finish.json')
Invoke-ConnectorStage 'N4'       (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\maneuvers_finish.json')
Invoke-ConnectorStage 'SELECT_PLANT'
Invoke-ConnectorStage 'DATA_PILOT' (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\data_pilot.json')
Invoke-ConnectorStage 'DATA_FULL'  (Join-Path $taskRoot 'revision_2026\connector_r3_4\configs\data_full.json')
Invoke-ConnectorStage 'TRAIN_SMOKE'
Invoke-ConnectorStage 'MPC_INTERFACE'
Invoke-ConnectorStage 'FINAL'
```

每个阶段结束后调度器必须读取上一阶段`complete.json.passed`和哈希，不允许只按退出码继续。

## 10. 资源控制和计划停止点

| 阶段 | 先跑pilot | 计划性停止条件 |
|---|---|---|
| C2 | Q95 32相位完整四因素 | 估算全矩阵超过4 h则保存估算并请求确认 |
| C3 | Q99/R3-ES及参考 | 单代表工况超过30 min或事件数异常增长则停 |
| C4 | 100m名义R3-ES | 单轨迹超过60 min、输出超过1 GB或15 kN则停 |
| C6 | 10条清洁+2条接口 | 任一旧import、因果失败或无法重绘则停 |
| C7 | 每场景先1条 | 预计新增超过20 GB则保存资源估算并停 |
| C8 | 一个训练seed | NaN/Inf或数据归一化异常立即停 |

不得通过减少关键场景、删除不利轨迹、降低保存字段或放宽采样率来绕过资源门。

## 11. 失败代码与恢复

| 编号 | 失败 | 立即保存 | 允许修复 | 重新进入门 |
|---|---|---|---|---|
| F001 | 双协议或源码身份不一致 | 哈希、时间、diff | 查明来源，建立新冻结 | C0重新PASS |
| F002 | S4复算与报告不一致 | 原始行、复算脚本、差异 | 修报告或代码；禁止改原始数据 | 12/12重新确认 |
| F003 | 旧18项测试退化 | 首败trace、源码diff | 只修引入退化的模块 | 18/18 |
| F004 | 旧植物仍被导入 | import链和入口 | 改唯一入口/静态拒绝 | 扫描与运行均PASS |
| F005 | N2缺参考或时间平移失败 | 相位、oracle、配置 | 修参考映射，不造伪JSON | 等价性门PASS |
| F006 | N2最坏相位失败 | 最坏trace和全部相位表 | 修事件积分或停止力律 | 全32相位PASS |
| F007 | 作用反作用失败 | 两端坐标、力、符号 | 修方向/旋转 | `<1e-10 N` |
| F008 | 共同原点力矩失败 | 两锚点、力臂、逐项力矩 | 修施力点/坐标 | 力矩门PASS |
| F009 | 力未进入导数 | `dx_total/dx_zero/formula` | 修组装入口 | 全30通道合同PASS |
| F010 | 内力或拉伸代理失败 | W/SVD/角点顺序 | 修点序与坐标 | 解析构造PASS |
| F011 | Ackermann/ICR失败 | 虚拟角、四车角、ICR、裁剪 | 修分配器，不怪连接器 | 镜像/残差门PASS |
| F012 | 四车不收敛 | 三层步长、事件和控制序列 | 最小工况诊断 | C3全部门PASS |
| F013 | 轮胎/转角饱和 | 原始需求、缩放比、时段 | 降低预注册输入并重立配置版本 | pilot重新通过 |
| F014 | 15 kN触发 | 首个时刻完整状态和控制 | 查工况/参数/接线；禁止截断 | 新版本物理门PASS |
| F015 | R3无优势 | 全部成对结果和CI | 限制声明或另立R3.5 | 不得在R3.4调参硬过 |
| F016 | 区间统计仍是端点量 | 解析例和audit | 修真实dt聚合 | 区间测试PASS |
| F017 | 未来事件泄漏 | 人工扰动前后输入 | 修`e_k`索引 | 因果测试PASS |
| F018 | pilot覆盖不足 | 覆盖矩阵 | 增加物理轨迹，不增加重叠窗口 | 覆盖门PASS |
| F019 | split/归一化泄漏 | 轨迹ID和统计来源 | 重建未冻结数据 | 数据证书PASS |
| F020 | 训练冒烟NaN或发散 | batch、缩放、矩阵条件数 | 修数据/正则，不换测试集 | C8 PASS |
| F021 | MPC接口不匹配 | 状态/控制/周期diff | 只修接口并标记需重调 | 接口证书PASS |
| F022 | 图/报告无法复算 | 图数据、源NPZ、脚本 | 从原始数据重算 | 清单独立PASS |

任一失败后：

1. 后续阶段立即写`NOT_RUN_PRECONDITION_FAILED`；
2. 保留首败和全部失败列表；
3. 在同一个`solutions.md`追加根因候选、反证、最小诊断、方案成本和重新进入门；
4. 在同一个`work_log.md`追加记录；
5. 不得自动切换力律、数据或阈值继续跑。

## 12. 工作记录

每完成一个代码修改或实验节点，立即追加：

```markdown
## R34-FIN-XXX — YYYY-MM-DD HH:mm — 任务标题

- 请求/任务编号：
- 授权模式：执行实验
- 主机与项目根目录：
- historical_protocol_sha256：
- finish_protocol_sha256：
- 基线源码/数据SHA256：
- 读取：
- 修改文件与函数：
- 修改前后SHA256：
- 运行命令：
- 退出码与运行时间：
- 配置、run_id和随机种子：
- 原始产物：
- 关键指标、单位、样本范围：
- 自动报告的独立复算：
- 结论类型：事实 / 推断 / 建议 / 未知
- 状态：PASS / BLOCKED / NOT_RUN
- 停止原因：
- 下一允许动作：
```

计划中的任务不能提前写成完成。失败代码、失败轨迹和失败图不得删除。

## 13. 最终完成清单

以下项目必须逐项为`YES`：

- [ ] 双协议身份和S4正式放行文件齐全；
- [ ] 旧18项和新增测试全部通过；
- [ ] N2 768行完整，无删除相位；
- [ ] 四点作用反作用和共同原点力矩通过；
- [ ] 四辆车及货物`vx/vy/r`连接力导数接线通过；
- [ ] 完整内部力与`T_x/T_y`通过；
- [ ] 共同ICR/Ackermann分配在实际工况入口生效；
- [ ] 100m、直线、单移线、回头弯、定向激励和过渡工况通过；
- [ ] 四因素结果说明了积分器效应、力律效应和交互作用；
- [ ] 植物选择及R3优势/无优势状态已冻结；
- [ ] pilot和正式数据无旧模型、无泄漏且可确定重放；
- [ ] fixed linear/bilinear冒烟与重载通过；
- [ ] MPC接口检查通过且旧MPC仍被标记为历史结果；
- [ ] 12类图片均可从figure_data和原始数据重绘；
- [ ] report、solutions、work_log、stage_status和manifest一致；
- [ ] `READY_FOR_KOOPMAN_TRAINING.json`存在并经独立核验。

只有全部勾选，才能把`stage_status.json.status`写成最终完成状态。任何一项未知或未运行，都不能用`PARTIAL`冒充完成。

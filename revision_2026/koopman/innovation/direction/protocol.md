# Koopman方向保持实验

> 项目：VT-2026-05393 Koopman预测部分最后一轮收缩实验  
> 状态：预注册任务书；本轮只写MD，尚未启动5080代码修改或新数据生成  
> 5080项目：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 旧实验只读目录：`revision_2026\koopman\innovation\`、`innovation_results\`  
> 新代码目录：`revision_2026\koopman\innovation\direction\`  
> 新结果目录：`revision_2026\koopman\innovation_direction_results\`  

## 1. 本轮为什么继续、为什么只走这一条路

### 1.1 已确认事实

1. 原H1物理工况低秩残差已经明确失败：development综合误差相对K1恶化`126.99%`，发散率由`28.75%`升至`75%`。
2. 原H2直接多时域映射在development上有强信号：10–20步状态、四点力和左右载荷分别改善约`76.1%/76.2%/77.4%`，综合`J_pred`改善`76.42%`，发散率降至0。
3. H2失败点集中在方向：四点力全时域方向准确率由K1的`81.58%`降至`69.75%`；左右载荷全时域由`69.53%`降至`66.68%`。
4. H2五seed validation `J`位于`0.1955–0.2145`，80条development轨迹配对统计通过，9候选×20步p99为`0.411 ms`，teacher-free合同通过。
5. 当前`horizon_training.py:34–38`把30维主状态、四点力和左右载荷作为独立连续量评价；`horizon_training.py:45–55`对完整64维输出逐时域做ridge；方向损失只参与ridge选择，不能从模型结构上保证方向。
6. `universal_v2_modules.py:116–133`已经定义了冻结物理关系：四点力沿连接位移方向，`Q_FR/Q_LR`由四点力代数重构，力变化率由当前可用上一时刻四点力因果差分得到。
7. 当前保存合同没有车辆侧独立施力日志，因此本轮只能验证货物侧四点力方向和左右拉伸载荷代理，不能独立证明作用—反作用，也不能判断真实材料撕裂。
8. D5尚未创建，可以在新方法和全部阈值冻结后保留一次真正的盲确认。

### 1.2 本轮唯一研究假设

> 在保留H2直接1–20步状态预测的前提下，不再独立回归`Fx/Fy/Q_FR/Q_LR`，而是直接预测四点非负轴向幅值，由预测的连接位移确定方向，并从四点力统一重构左右载荷和力变化率，可以保留H2的长时域幅值收益，同时消除受力方向退化。

这是一条可证伪假设，不预设一定成功。

### 1.3 明确停止的路线

本轮不再执行或恢复：

- H1低秩工况递归残差；
- H3基于H1的共同`P`证书；
- 原IRSP或完整状态谱投影；
- C9多专家通用门控；
- 扩大H1 rank/ridge网格；
- 原K2/K3双线性结构；
- 新神经lift；
- 在当前已查看D4R上增加符号投影后重新宣称预注册成功。

如果本任务书的方向保持主候选在新开发集失败，停止Koopman结构创新，不再产生第五、第六条模型分支。

## 2. 当前代码问题的精确定位

### 2.1 当前H2的数据和输出

`horizon_training.py:17–25`构造：

```text
x0:       [B,46]
u_future: [B,20,8]
y:        [B,20,64]
```

64维输出布局为：

```text
0:46    S3状态
46:54   FL/FR/RL/RR四点Fx/Fy
54:56   Q_FR/Q_LR
56:64   四点dFx/dFy
```

现有`DirectMultiHorizonHead`对每个`h=1…20`建立：

\[
\hat y_{k+h}=W_h[1,x_k,u_k,\ldots,u_{k+h-1}],
\]

它能降低均方误差，但`Fx/Fy/Q_FR/Q_LR`彼此独立，无法保证：

- `F_i`沿连接点位移方向；
- 轴向幅值非负；
- `Q_FR/Q_LR`与四点力代数一致；
- 力变化率来自因果相邻力；
- 转向反转时各分量符号同步变化。

### 2.2 冻结物理重构关系

对预测连接位移`d_i=[dx_i,dy_i]`：

\[
n_i=\frac{d_i}{\max(\|d_i\|,\epsilon)},\qquad
F_i=T_i n_i,\qquad T_i\ge0.
\]

四点顺序固定为`FL/FR/RL/RR`。左右拉伸载荷统一重构：

\[
Q_{FR}=\frac12[(F_{FL,x}+F_{FR,x})-(F_{RL,x}+F_{RR,x})],
\]

\[
Q_{LR}=\frac12[(F_{FL,y}+F_{RL,y})-(F_{FR,y}+F_{RR,y})].
\]

力变化率：

\[
\dot F_i(k+h)=\frac{F_i(k+h)-F_i(k+h-1)}{0.02}.
\]

`h=1`的上一时刻力只能读取预测起点`k`当前可用观测；禁止读取`k+1`及之后真实力。

### 2.3 非负轴向幅值参数化

训练目标不直接使用`Fx/Fy`，而是：

\[
T_i^{true}=\max(F_i^{true}\cdot n_i^{true},0).
\]

使用训练集冻结的`F_scale`进行逆softplus变换：

\[
a_i^{true}=\log\left(\exp(T_i^{true}/F_{scale})-1+\epsilon\right),
\]

预测后：

\[
\hat T_i=F_{scale}\operatorname{softplus}(\hat a_i)\ge0.
\]

`F_scale`只用新D4R2 train每点活动力幅值中位数拟合；validation只允许在`{0.5,1,2}×F_scale`中选择一次。不得按development逐点调整。

## 3. 新方法和对照

### 3.1 统一名称

暂称：**方向保持直接多时域Koopman**，英文工作名`DP-MHK`（Direction-Preserving Multi-Horizon Koopman）。只有D5和闭环均通过后才能进入论文标题或贡献列表。

### 3.2 候选矩阵

| 编号 | 状态预测 | 四点力 | Q与力变化率 | 用途 |
|---|---|---|---|---|
| `P0` | K1递推 | K1 | K1 | 主基线 |
| `P1` | 冻结原H2 | 原H2独立Fx/Fy | 原H2独立输出 | 已知幅值强、方向失败边界 |
| `P2` | 冻结原H2 | 原H2幅值+K1方向 | 从四点力重构 | 最小混合对照，不作为默认创新 |
| `P3` | 冻结原H2 | 冻结名义物理公式从H2位移/速度计算 | 从四点力重构 | 纯物理decoder对照 |
| `P4` | 冻结原H2 | 新的四点非负轴向幅值+H2几何方向 | 从四点力重构 | 主候选DP-MHK |
| `P5` | 冻结原H2 | P4但取消非负/几何约束 | 独立回归 | 归因消融 |

`P2`只能说明“方向来自K1是否足够”。如果P2最好而P4不通过，不能把P2包装为新的物理Koopman；它只是工程混合基线。

### 3.3 P3名义物理decoder

P3严格复用冻结`physics_force()`的名义参数和公式，不读取轨迹真实连接刚度、阻尼或自由间隙。外部参数测试中不得把真实未知参数输入P3，否则构成oracle。

### 3.4 P4主候选输入和输出

P4每个时域使用：

```text
输入：1 + x0(46) + u[0:h](h×8)
直接状态：冻结P1的S3预测 [B,h,46]
幅值head：四点a_hat [B,h,4]
几何方向：S3预测的30:38重构 [B,h,4,2]
四点力：T_hat * n_hat [B,h,4,2]
载荷：Q_FR/Q_LR代数重构 [B,h,2]
力变化率：当前起点力+预测序列因果差分 [B,h,4,2]
```

若预测位移范数小于训练集冻结的`direction_floor`：

- 同时预测幅值低于`force_floor`：输出零力；
- 幅值处于活动区：该点标记`direction_invalid`并回退K1方向；
- 报告回退率，development不得超过1%，D5不得高于K1非有限/无方向率。

不能把方向无效样本从统计中删除。

## 4. 代码修改任务书

### 4.1 旧代码只读边界

以下现有文件和结果保持只读，不直接修改：

- `innovation\horizon_training.py`；
- `innovation\multihorizon.py`；
- `innovation\baseline_cache.py`；
- `innovation\data_protocol.py`；
- `innovation_results\t4_h2\models\N2-seed-151002.npz`，当前SHA256=`3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC`；
- 原D4R、H1/H2结果、final report和work log；
- `universal_v2_modules.py:116–133`冻结物理关系。

新实现通过适配器读取旧H2，避免覆盖当前负结果证据。

### 4.2 新目录

```text
revision_2026/koopman/innovation/direction/
├── __init__.py
├── config.py
├── contracts.py
├── audit.py
├── data_protocol.py
├── generate_d4r2.py
├── dataset.py
├── h2_adapter.py
├── physics_decoder.py
├── magnitude_head.py
├── predictors.py
├── metrics.py
├── train.py
├── evaluate.py
├── generate_d5.py
├── closed_loop_adapter.py
├── report.py
├── run.py
└── tests/
    ├── test_frozen_h2.py
    ├── test_no_old_result_write.py
    ├── test_no_future_truth.py
    ├── test_force_direction.py
    ├── test_load_reconstruction.py
    ├── test_force_rate_causal.py
    ├── test_units_and_order.py
    ├── test_d5_absent.py
    └── test_closed_loop_contract.py
```

新结果：

```text
revision_2026/koopman/innovation_direction_results/
├── freeze/
├── audits/
├── d4r2/
├── models/
├── development/
├── d5/
├── closed_loop/
├── figures/
├── work_log.md
├── solutions.md
├── gates.json
└── final_report.md
```

### 4.3 `direction/config.py`

```python
@dataclass(frozen=True)
class DirectionConfig:
    horizon: int = 20
    control_dt_s: float = 0.02
    state_dim: int = 46
    control_dim: int = 8
    point_count: int = 4
    ridge_grid: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2)
    scale_grid: tuple[float, ...] = (0.5, 1.0, 2.0)
    train_seeds: tuple[int, ...] = (181001,181002,181003,181004,181005)
    max_direction_fallback_rate: float = 0.01
    prediction_p99_ms: float = 8.0
```

额定/极限力、归一化和force floor必须从冻结plant/normalizer读取，不硬编码。

### 4.4 `direction/contracts.py`

```python
@dataclass
class DirectionPrediction:
    state_s3: np.ndarray             # [B,20,46]
    axial_magnitude: np.ndarray      # [B,20,4]
    point_force: np.ndarray          # [B,20,4,2]
    payload_load: np.ndarray         # [B,20,2]
    force_rate: np.ndarray           # [B,20,4,2]
    direction_valid: np.ndarray      # [B,20,4]
    fallback_mask: np.ndarray        # [B,20,4]
```

`validate_direction_prediction()`必须检查shape、有限性、单位、车辆顺序、`Fx/Fy`顺序、轴向幅值非负和Q代数残差。

### 4.5 `direction/audit.py`

实现：

```python
def freeze_source_hashes(project_root: Path) -> dict: ...
def assert_old_results_read_only(before: dict, after: dict) -> None: ...
def assert_d5_absent(results_root: Path) -> None: ...
def audit_seed_collisions(manifests: list[Path], requested: list[int]) -> None: ...
def record_change_manifest(paths: list[Path], output: Path) -> None: ...
```

任何训练前冻结：任务书、本轮代码、原H2模型、K1模型、normalizer、数据生成器和物理decoder SHA256。

### 4.6 `direction/data_protocol.py`

新D4R2不得复用`130001–133080`及旧D1–D4/D5保留seed。固定：

- pilot：`180001–180016`；
- train：`161001–161192`；
- validation：`162001–162064`；
- development：`163001–163064`；
- 模型训练seed：`181001–181005`；
- bootstrap：`182999`；
- D5：`171001–171160`。

任何碰撞发生在生成前，则整体更换号段并更新协议hash；不能只替换冲突seed。

### 4.7 `direction/generate_d4r2.py`

新D4R2共320条：

| 组 | train | validation | development | 重点 |
|---|---:|---:|---:|---|
| G0直线/缓弯 | 48 | 16 | 16 | 低载荷和近零分量 |
| G1加速/制动/持续加载 | 48 | 16 | 16 | 幅值和加载方向 |
| G2稳态弯/高载荷 | 48 | 16 | 16 | 四点方向与Q |
| G3正反阶跃/弯道进出 | 48 | 16 | 16 | 符号反转和过渡 |

每条轨迹的速度、转角和前后转向比从冻结离散表按seed确定，不允许按运行结果临时增强：

```text
speed_mps  = {2.0, 2.5, 3.0, 4.0}
front_deg  = {8, 10, 12, 15}
rear_ratio = {-0.3, -0.5, -1.0}
profile    = {hold, reversal}
```

先运行16条pilot检查finite、ultimate和方向事件数；pilot只决定整套表是否安全，不参与训练或统计。

覆盖门：

- train每个R0–R3至少1500个不重叠20步窗；
- validation每类至少400窗；
- development每类至少400窗；
- 每个split至少200个有效四点方向反转事件；
- 高载荷窗`>=200`；
- ultimate触发为0。

不达门时只允许在训练前按预先冻结的追加表每组增加8条；最多追加两轮。两轮仍不足则停止，不通过重叠窗口或降低方向阈值凑数。

### 4.8 `direction/dataset.py`

复用当前`horizon_training.py:17–31`的数据逻辑，但新增：

```python
def load_direction_dataset(...) -> dict:
    # x0 [B,46], u [B,20,8], truth_state [B,20,46]
    # truth_points [B,20,4,2], truth_load [B,20,2]
    # current_points [B,4,2], trajectory, origin

def axial_targets(truth_state, truth_points, normalizers) -> dict:
    # unit_direction, magnitude, transformed_magnitude, active_mask
```

所有方向指标在物理单位计算。归一化分量不能直接用于向量角度。

### 4.9 `direction/h2_adapter.py`

```python
class FrozenH2StateAdapter:
    def __init__(self, model_path: Path, expected_sha256: str): ...
    def predict_s3(self, x0: np.ndarray, u_future: np.ndarray) -> np.ndarray: ...  # [B,20,46]
```

与原`DirectMultiHorizonHead`逐元素回归，float64最大差`<=1e-10`或float32二进制一致。只读取原H2的前46维系数，不能重新选择ridge或seed。

### 4.10 `direction/physics_decoder.py`

```python
def unit_from_displacement(state_s3_physical, direction_floor): ...
def reconstruct_points(magnitude, unit_direction): ...
def reconstruct_load(points): ...
def causal_force_rate(points, current_points, dt=0.02): ...
def nominal_physics_decoder(state_s3, current_points, frozen_params): ...
```

单元测试必须用手工四点反例验证：总合力为0时`Q_FR/Q_LR`仍可非0，防止把合力为0误判为无拉伸趋势。

### 4.11 `direction/magnitude_head.py`

```python
class DirectAxialMagnitudeHead:
    def fit(self, x0, u_future, transformed_targets, trajectory_ids): ...
    def predict_latent(self, x0, u_future): ...          # [B,20,4]
    def predict_magnitude(self, x0, u_future): ...       # softplus, >=0
```

每个`h=1…20`使用与原H2相同的直接输入和ridge网格。五seed按整轨迹bootstrap；validation按以下词典序选择：

1. 非有限/发散率；
2. 四点向量方向和Q方向；
3. force/load NRMSE；
4. state和总`J_pred`；
5. 计算时间。

不得再以单纯NRMSE最低选择一个方向失败候选。

### 4.12 `direction/predictors.py`

分别实现`P0Predictor`至`P5Predictor`。所有预测器统一：

```python
def predict(x0_s3, u_future, current_point_force) -> DirectionPrediction:
    ...
```

P2、P3、P4的`Q`和force rate必须统一调用`physics_decoder.py`，不能复制三套略有差异的公式。

### 4.13 `direction/metrics.py`

除原分量符号准确率外，新增：

```python
def component_sign_accuracy(pred, truth, floor): ...
def vector_angle_error_deg(pred, truth, floor): ...
def reversal_event_metrics(pred, truth, event_mask, radius_steps=10): ...
def q_sign_accuracy(pred_q, truth_q, floor): ...
def algebraic_residual(points, q): ...
def trajectory_metrics(...) -> dict: ...
```

方向活动门`force_floor`只用train分布拟合，validation冻结；development和D5不得更改。必须同时报告：

- 四点分量符号准确率；
- 向量夹角MAE/p95；
- 方向反转前后±0.2 s准确率；
- Q_FR/Q_LR符号准确率；
- 方向无效率和回退率。

### 4.14 `direction/train.py`

五seed训练P4/P5，P0–P3不训练。每seed写：

- 数据、代码、原H2和K1 hash；
- 轨迹bootstrap样本；
- 每个h的ridge和scale；
- validation全部幅值/方向指标；
- 模型hash、wall time、RAM和磁盘；
- 候选淘汰原因。

代表seed按validation总门的中位模型选择，不按development最好模型选择。

### 4.15 `direction/evaluate.py`

统一运行P0–P5，输出1/5/10/15/20步、1–5步、10–20步和全时域结果；同时按G0–G3、R0–R3、高载荷和方向反转事件分层。

统计单位为轨迹，10,000次配对bootstrap、配对置换检验、Holm校正和效应量。窗口不得当作独立样本。

### 4.16 `direction/generate_d5.py`

只有D4R2 development主门全部通过并冻结代码/模型/阈值后才允许导入或执行。D5共160条：

| 子集 | 数量 | 作用 |
|---|---:|---|
| 常规直线/加减速/稳态弯 | 48 | 基础确认 |
| 单移线/回头弯 | 32 | 横向与高曲率 |
| 正反阶跃/方向反转 | 32 | 方向保持核心 |
| 高载荷 | 24 | 0.8 rated以上 |
| 参数变化 | 24 | 外推边界 |

seed固定为`171001–171160`。生成后立即写只读manifest和SHA256，一次性运行P0–P5。查看D5后任何算法、阈值、归一化或样本改变都会使整批D5失效。

### 4.17 `direction/closed_loop_adapter.py`

只有D5通过后实现。新预测器接入现有9候选有限控制集MPC：

```python
def predict_candidates(
    x_now: np.ndarray,
    candidate_u: np.ndarray,       # [9,20,8]
    current_point_force: np.ndarray,
) -> DirectionPrediction:
    ...
```

第一轮闭环比较冻结候选集、控制代价、约束、控制周期和安全层。不得修改MPC后把收益归因于Koopman。

### 4.18 `direction/run.py`

阶段命令：

```text
d0  冻结/污染/seed审计
d1  16条安全与方向事件pilot
d2  D4R2生成、缓存和覆盖审计
d3  冻结原H2在D4R2上的泛化复核
d4  P2/P3构造及P4/P5五seed训练
d5  D4R2 development一次性门禁
d6  冻结并生成D5
d7  D5一次性确认
d8  clean 100 m闭环验收
d9  单移线和回头弯闭环
d10 通信必要性、扰动和DoS
d11 图表、报告和交付
```

任何门失败返回非零退出码，写`failure.json`和`solutions.md`，依赖阶段拒绝启动。

## 5. 分阶段实验门

### D0—冻结和污染审计

必须通过：

- 原H2/K1/normalizer/physics decoder hash一致；
- 原D4R、H1/H2结果只读；
- D5不存在；
- 所有新seed无碰撞；
- 新任务书hash写入freeze；
- Python解释器和包版本冻结。

失败即停止。

### D1—安全pilot

16条全部finite、ultimate触发为0；方向反转事件至少40个；点力与位移轴向反号样本为0。否则只允许调整尚未生成正式数据的配置表，并完整重跑pilot。最多两轮。

### D2—D4R2生成和缓存

320/320条必须完成；失败seed不替换。满足工况、方向事件和高载荷覆盖门；shape、时间轴、单位和四点顺序全部通过。

### D3—原H2新数据泛化门

先不训练任何方向头，在全新D4R2 development检查冻结P1：

- 10–20步`J_pred`相对K1改善至少8%；
- state/force/load任一不恶化超过3%；
- 发散率不高于K1；
- 轨迹级95% CI不跨0，Holm通过。

方向允许按已知负结果报告，但不作为D3停止项。如果P1的幅值收益在新数据上不复现，立即停止整个方向头实验：这说明原76%收益本身过拟合，修方向没有意义。

### D4—方向头训练和validation选择

P4必须在validation满足：

- 相对K1，10–20步总`J_pred`改善至少8%；
- 相对P1，state保持二进制一致，force/load NRMSE恶化不超过5%；
- 四点分量方向准确率不低于K1减1个百分点；
- Q_FR/Q_LR方向准确率不低于K1减1个百分点；
- 向量角度p95不高于K1；
- 方向反转±0.2 s准确率不低于K1；
- Q代数残差`<=1e-10 N`或float32 ULP等价；
- 方向回退率`<=1%`；
- 发散率不高于K1；
- 9候选×20步p99`<8 ms`。

### D5—development一次性主门

代表seed在64条development轨迹一次性运行P0–P5。P4必须重复D4全部门，并满足：

- 轨迹级配对95% CI为正；
- Holm校正`p<0.05`；
- 效应量`|dz|>=0.5`；
- G3反转和高载荷两个子集均不退化超过3%；
- 没有通过牺牲单车横摆/货物横摆状态取得force收益。

失败则停止，不生成D5，不再调P4后复用当前development。

### D6/D7—D5盲确认

D5一次性运行P0–P5。P4通过条件与development完全相同，且五个子集至少四个满足8%总体改善；未通过子集不得安全关键退化超过5%。

D5失败后不回到D4R2调参并复用同一D5。

### D8—clean 100 m验收

仅D5通过后运行。沿用已冻结工况：

- 前30 m以`0.4 m/s²`加速；
- 随后匀速，正向5 s阶跃转向；
- 再反向5 s阶跃转向；
- 剩余距离减速。

比较P0、P1、P3、P4接入同一FCS-MPC，10个配对seed。全部方法先通过10/10距离门，否则停止后续网络闭环并分析控制合同。

记录：四车水平/竖直分力、单车横摆、系统横摆、货物左右拉伸载荷、四点水平受力方向、Q_FR/Q_LR、前后/左右/对角内力代理、跟踪、控制和MPC可行率。

### D9—单移线和回头弯

比较：

- AKE-M；
- P0-K1；
- P1原H2；
- P4-DP-MHK。

先5个pilot seed，全部可行再扩展20个配对seed。单移线和回头弯分别报告入口、稳态、方向反转和出口阶段。

P4必须相对P0在跟踪、受力约束或MPC可行率至少一个主要指标改善8%，同时峰值力、Q、横摆和完成率不恶化超过5%。否则离线创新不升级为控制贡献。

### D10—通信和DoS

只有D9通过才运行：

1. 在100 m工况给P0无保护控制加入iid/burst/delay/DoS，验证通信确实造成误差或受力退化；
2. 比较无保护P0、相同观测管理P0、delay-aware强基线、无网络保护P4、带冻结网络保护P4；
3. 每类20个配对seed；
4. 分离预测器收益和通信保护收益。

如果通信扰动没有造成实际退化，只能报告当前工况不敏感，不能写“实验得出必须通信保护”。

## 6. 评价指标

### 6.1 离线

- 1/5/10/15/20步状态、四点力、Q和force-rate NRMSE；
- 四点分量符号准确率；
- 四点向量夹角MAE/p95；
- Q_FR/Q_LR符号准确率；
- 反转事件±0.2 s方向准确率和恢复时间；
- 高载荷幅值、方向和持续时间；
- Q代数残差；
- 非有限率、发散率和最坏轨迹；
- p50/p95/p99端到端预测时间。

### 6.2 闭环

- 路径纵横向/航向RMSE和最大误差；
- 100 m距离、终端速度和任务完成率；
- 单车横摆、系统横摆和共同ICR残差；
- 四点水平/竖直分力、方向角、变化率；
- Q_FR/Q_LR及前后、左右、对角内力代理；
- 峰值、RMS、p95、p99和超限时间；
- MPC不可行率、fallback率、能耗和控制周期p99。

没有材料和连接区破坏参数时，不计算或声称真实撕裂概率。

## 7. 运行命令

5080 PowerShell：

```powershell
$projectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$runner = Join-Path $projectRoot 'revision_2026\koopman\innovation\direction\run.py'
$pythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'

& $pythonExe $runner --stage d0 --project-root $projectRoot
& $pythonExe $runner --stage d1 --project-root $projectRoot
& $pythonExe $runner --stage d2 --project-root $projectRoot
& $pythonExe $runner --stage d3 --project-root $projectRoot
& $pythonExe $runner --stage d4 --project-root $projectRoot
& $pythonExe $runner --stage d5 --project-root $projectRoot
& $pythonExe $runner --stage d6 --project-root $projectRoot --confirm-create
& $pythonExe $runner --stage d7 --project-root $projectRoot --confirm-once
& $pythonExe $runner --stage d8 --project-root $projectRoot
& $pythonExe $runner --stage d9 --project-root $projectRoot
& $pythonExe $runner --stage d10 --project-root $projectRoot
& $pythonExe $runner --stage d11 --project-root $projectRoot
```

每阶段读取上一阶段`complete.json`和hash；门失败后后续阶段必须拒绝启动。

## 8. 资源预算

| 项目 | 计划预算 | 超限处理 |
|---|---:|---|
| 16条pilot | <5 min | 查plant子步和I/O，不换seed |
| D4R2 320条 | <20 min，<1 GB原始数据 | 8 workers；失败保留日志 |
| D4R2基线缓存 | <30 min，<8 GB | 分区缓存和断点续算 |
| P4/P5五seed | <2 h | CPU ridge分h执行；不缩短20步 |
| RAM | <16 GB | memmap、轨迹batch、按h释放矩阵 |
| VRAM | 不要求 | 当前方法优先CPU闭式求解 |
| 9候选20步p99 | <8 ms | 批量矩阵乘、缓存H2状态 |
| D5生成+一次评估 | <4 h | 不允许查看中间结果改算法 |
| 单移线/回头弯 | 5-seed pilot后<12 h | 失败不替换seed |
| 网络/DoS | <24 h | 仅D9通过后运行 |

pilot结束后必须用实测生成`resource_budget.json`覆盖上述估计。

## 9. 可能跑不动或证据不成立的情况

| 编号 | 现象 | 判断与处理 | 停止条件 |
|---|---|---|---|
| `R01` | 原H2 hash变化 | 恢复交付包中的冻结模型 | 无法恢复则整轮停止 |
| `R02` | D5已经存在 | 审计是否被读取 | 已查看则原D5作废并新建完整确认批次 |
| `R03` | seed碰撞 | 生成前整体更换号段 | 已生成后发现则整批作废 |
| `R04` | pilot ultimate触发 | 使用冻结安全降级表重跑整轮pilot | 两轮仍触发则停止高载荷分支 |
| `R05` | 方向反转事件不足 | 按预注册追加表每组增加8条 | 两轮仍不足则停止，不降floor凑数 |
| `R06` | D4R2生成非有限 | 保留seed和failure，定位plant | 无法修复同一确定性bug则停止 |
| `R07` | H2在D4R2幅值收益不复现 | 判定旧76%为开发集特定 | 立即停止方向头，不进入训练 |
| `R08` | H2适配输出不一致 | 比较feature维数、normalizer和float dtype | 无法逐元素回归则停止 |
| `R09` | 轴向真实样本出现反号 | 检查d定义和力作用对象 | 方向合同不能确定则停止P4 |
| `R10` | 位移方向接近零 | 使用活动力floor和direction_invalid | 回退率>1%则P4失败 |
| `R11` | softplus上溢/下溢 | 使用稳定实现和训练分位裁剪 | 仍有非有限则候选失败 |
| `R12` | P4幅值好但方向仍差 | 检查H2连接位移方向误差 | 方向门失败即停止，不改development阈值 |
| `R13` | P4方向好但force误差显著变差 | 比较P3和P5定位幅值head | 相对P1恶化>5%则失败 |
| `R14` | Q与四点力不一致 | 统一调用单一重构函数 | 残差不过ULP门则停止 |
| `R15` | force-rate异常尖峰 | 检查起点current force和dt | 不得使用未来真值平滑；无法因果修复则失败 |
| `R16` | P2最好、P4失败 | 只认定混合基线有效 | 不把P2写成新Koopman贡献 |
| `R17` | 五seed结果分散 | 查bootstrap、病态设计矩阵 | 中位通过但最坏seed安全退化>5%则不通过 |
| `R18` | micro改善、macro恶化 | 同时报场景等权和逐轨迹 | 任一主口径安全退化>5%则失败 |
| `R19` | D5未复现 | 原样报告 | 不回调后复用同一D5 |
| `R20` | 100 m距离失败 | 分解预测、候选可行性和输入饱和 | `<10/10`则停止闭环扩展 |
| `R21` | 离线好、闭环无收益 | 保留预测结果但降级论文贡献 | 不进入网络实验 |
| `R22` | p99超过20 ms控制周期 | 批量化和缓存H2 | 优化后仍超限则不可部署 |
| `R23` | 通信扰动没有影响 | 核对实际AoI/丢包日志 | 不声称保护必要性 |
| `R24` | 网络保护改善跟踪却放大受力 | 报Pareto和ultimate | 安全量退化>5%则保护失败 |
| `R25` | 车辆侧反力未记录 | 标记not identifiable | 禁止作用—反作用和真实撕裂主张 |
| `R26` | 代码修改旧H2结果 | 用hash检测并回滚 | 无法恢复只读证据则停止 |
| `R27` | 图与CSV冲突 | 从冻结CSV重生成 | 以可复算数据为准并留痕 |

同一阻塞连续三次且安全替代均失败时，停止对应分支并写`solutions.md`：事实、原因假设、尝试、资源、证据边界和下一次所需条件。

## 10. 工作记录

每次代码改动或实验完成后立即追加：

`revision_2026\koopman\innovation_direction_results\work_log.md`

固定格式：

```markdown
## Dxxxx — 工作名称

- 开始/结束时间：
- 任务书SHA256：
- 修改文件和函数：
- 修改前/后SHA256：
- 实际命令与退出码：
- 输入模型/数据/config hash：
- seed、样本数、失败数、是否替换：
- 关键结果与门禁：
- wall time、RAM、VRAM、磁盘：
- 输出文件SHA256：
- 事实、推测、未解决问题：
- 结论：通过 / 停止 / 降级：
```

同时写`audits/change_manifest.json`，记录每个文件的`before_sha256`、`after_sha256`、`functions_changed`、`reason`、`tests_run`和`rollback_path`。

## 11. 审稿意见关闭边界

本实验只负责关闭：

- 原双线性/递推模型20步性能证据不足；
- 新Koopman预测创新是否成立；
- 四点力/左右载荷方向是否与幅值预测一致；
- 离线预测改善能否转化成闭环收益。

本实验不负责通过继续加Koopman模块解决：

- 原IRSP连续域证书；
- 原稳定性定理的循环论证；
- 实车/高保真验证；
- 材料撕裂和结构破坏；
- 引用错误和防御性写作。

这些问题分别通过删除原主张、重写理论、限制工作域和修改论文处理。

## 12. 最终任务树

```text
D0 冻结/污染/seed审计
└─ D1 16条pilot
   └─ D2 新D4R2 320条与覆盖
      └─ D3 冻结原H2新数据泛化
         ├─ 不复现：停止全部Koopman创新
         └─ 复现
            └─ D4 P2/P3/P4/P5
               └─ D5 development一次性门
                  ├─ 失败：停止，不生成D5
                  └─ 通过
                     └─ D6/D7 D5盲确认
                        ├─ 失败：停止，不复用D5
                        └─ 通过
                           └─ D8 clean 100 m
                              ├─ 距离失败：停止闭环扩展
                              └─ 通过
                                 └─ D9 单移线/回头弯
                                    ├─ 无闭环收益：降级预测贡献，停止网络
                                    └─ 通过
                                       └─ D10 通信/DoS
                                          └─ D11 报告与论文证据
```

本轮只有一个终点：**H2在全新数据上保持显著多步收益，并通过物理结构同时保住四点力和左右载荷方向。做不到就停，不再扩展模型树。**

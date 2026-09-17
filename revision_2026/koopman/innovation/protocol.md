# Koopman针对性创新实验

> 项目：VT-2026-05393 Koopman预测部分重构  
> 状态：预注册执行任务书，尚未启动5080代码修改和训练  
> 目标：把现有比较得到的失效机理转化为一个因果、可部署、可证明边界明确的多步Koopman预测器，而不是继续叠加未通过的模块。  
> 5080项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 新代码目录：`revision_2026\koopman\innovation\`  
> 新结果目录：`revision_2026\koopman\innovation_results\`  
> 本地报告副本：`D:\PDxc\Review\koopman_innovation_results\`  

## 1. 先固定事实、推测与本轮边界

### 1.1 已确认事实

1. 最新D4 internal共288条轨迹，生成与四专家缓存均无失败；不重叠20步窗为train `9440`、validation `3776`、development `3776`。
2. C9相对逐轨迹`min(K0,K1)`事后包络恶化`2.058%`，配对95% CI为`[-0.00122909,-0.000500075]`。
3. C9拒绝/回退率为`92.08%`；预测占用率K1 `96.02%`、K4 `3.18%`、K0 `0.80%`、K5-F2 `0%`，已经实质退化为K1。
4. C5全局凸组合相对K1只改善约`1.21%`，没有达到预注册的8%实际意义门。
5. C10窗口级oracle相对K0/K1包络仍有约`15.17%`余量。这只说明专家存在事后互补性，不说明互补性能够由当前因果信息实现。
6. 现有D4中峰值连接力达到`0.8 rated`的不重叠20步窗为0，不能支持高载荷选择器或高载荷安全主张。
7. 旧双线性K2确实使用输入—状态乘积，但回归条件数约`9.49×10^7`，总体20步、外推和网络结果显著差于K0/K1。
8. K1 fixed lifted linear是当前较稳健的默认骨干，但从内部域到外部参数域时，状态和连接力误差分别增加约`93.17%`和`81.43%`。
9. 现有物理输出合同能够报告四点`Fx/Fy`和货物左右侧拉伸载荷代理，但是否保存了车辆侧独立施力日志，必须在5080 T0代码审计中确认。不得把货物侧同一力简单取负后称为独立作用—反作用验证。
10. 当前Review环境未挂载5080源码。本任务书中的新文件和接口是待实现合同；现有源码的实际函数名、行号和调用关系必须由T0在5080生成`code_map.md`后填写，不能猜测。

### 1.2 当前强推断

1. 单一全局`A/B`把直线、转弯、加载、卸载和接触切换平均在一起，是参数外推和工况过渡退化的重要原因。
2. 四点连接力包含间隙、方向归一化、加载/卸载不对称和接触切换，平滑全局线性decoder难以统一表达。
3. C9失败的主要问题不是专家完全没有互补性，而是以未来误差训练的通用选择目标不能由当前低容量因果特征稳定恢复；物理合同门又过度拒绝。
4. 原IRSP把中性/积分状态和瞬态误差状态一起收缩，破坏了路径进度等真实动力学。若保留稳定性约束，应只作用于明确定义的误差子空间。

### 1.3 尚未确认的假设

本轮只检验以下三个假设，不预设它们一定成立：

- **H1—物理工况残差：**共享K1骨干上增加由当前物理变量调度的低秩局部残差，可以改善接触切换、弯道和参数变化，同时避免完整多专家的数据碎片化。
- **H2—直接多时域输出：**直接拟合`h=1…20`的状态/四点力/拉伸载荷压缩映射，可以减少一步算子反复递推和非光滑force decoder造成的远时域误差。
- **H3—误差子空间证书：**只对跟踪误差和连接器瞬态子空间施加共同诱导范数/Lyapunov约束，可以降低发散而不收缩位置、航向和路径进度等中性方向。

任何一个假设失败，都必须原样保留负结果。不得在D5查看后改变定义、阈值或主指标。

## 2. 论文问题和拟议方法

### 2.1 研究问题

- `RQ1`：全局线性、双线性和普通专家门控分别在哪些物理工况退化，退化是否能由接触状态、加载方向、曲率、加速度和参数失配解释？
- `RQ2`：物理工况低秩残差是否比通用误差标签门控更容易因果识别，并在工况切换处形成可重复收益？
- `RQ3`：直接多时域映射能否同时改善10–20步状态、四点力和货物左右侧拉伸载荷，而不是以状态退化换受力改善？
- `RQ4`：误差子空间证书能否给出连续工况凸组合下的预测误差有界性，同时避免原IRSP破坏积分状态？
- `RQ5`：离线改善能否在相同FCS-MPC/控制权重下转化成跟踪、受力约束、可行率或通信扰动恢复的闭环收益？

### 2.2 暂定名称

方法暂称：**接触工况调度的共享骨干多时域Koopman**，英文工作名`CRMH-Koopman`（Contact-Regime Multi-Horizon Koopman）。名称只有在H1、H2和最终组合均通过后才进入论文；否则按实际通过模块重新命名。

### 2.3 统一模型结构

冻结K1得到公共骨干：

\[
z_{k+1}=A_0z_k+B_0u_k.
\]

物理工况残差候选为：

\[
z_{k+1}=A_0z_k+B_0u_k+
\sum_{m=1}^{M}\alpha_m(\rho_k)
\left(U_mV_m^Tz_k+G_mu_k\right),
\]

其中：

- `A0/B0`来自冻结K1，不参与第一轮训练；
- `U_m,V_m,G_m`为低秩残差，初始rank网格固定为`{1,2,4,8}`；
- `alpha_m>=0`且`sum(alpha_m)=1`；
- `rho_k`只包含当前/历史可用物理量和通信元数据，不含场景名、未来真值或窗口事后误差；
- 所有归一化只由development训练部分拟合。

直接多时域候选为：

\[
\hat y_{k+h}=D_hz_k+
\sum_{j=0}^{h-1}E_{h,j}u_{k+j}+R_h\alpha(\rho_k),
\quad h=1,\ldots,20,
\]

其中`y`必须同时包含30维主状态、四点`Fx/Fy`、左右拉伸载荷和必要的物理审计量。MPC未来输入未知时，`E_{h,j}`直接作用于候选控制序列；离线teacher-free评价不得读取中间真实状态。

### 2.4 物理工况定义

四个连接点分别计算：

\[
p_i=\max(\|d_i\|-g_i,0),\qquad
v_{n,i}=\dot d_i^T\frac{d_i}{\|d_i\|+\epsilon}.
\]

初始候选工况为：

| 工况 | 因果判据 | 物理含义 |
|---|---|---|
| `R0_slack` | 四点`p_i`均接近0 | 松弛/未加载 |
| `R1_loading` | 任一点`p_i>eps_p`且`v_n>eps_v` | 拉伸载荷上升 |
| `R2_sustained` | 已加载且`abs(v_n)<=eps_v` | 稳态承载/稳态弯 |
| `R3_unload_transition` | `v_n<-eps_v`、力方向反转或转向符号切换 | 卸载、转向切换和过渡 |

`eps_p/eps_v`只能在D4R validation上选择一次。若任一工况达不到样本门，必须先合并相邻物理工况，不能用重复窗口或过采样伪造独立样本。

### 2.5 误差子空间

不得对完整46维状态直接声称收缩。T0需从状态schema中显式分出：

- 中性/积分量：绝对位置、绝对航向、路径进度及常数observable；
- 可收缩误差量：横纵向跟踪误差、速度误差、横摆率误差、车辆间相对状态、连接形变和相对速度。

用选择矩阵`T_e`定义`e_z=T_e z`。若每个工况满足：

\[
\|T_e(A_0+U_mV_m^T)T_e^\dagger\|_P\le\gamma<1,
\]

则其凸组合在同一`P`范数下保持相同上界。该结论只覆盖齐次预测误差子系统；输入、残差、模式估计错误和闭环稳定性必须分别给出有界项，不能把它扩大为完整控制系统稳定性定理。

## 3. 冻结边界和代码修改原则

### 3.1 只读证据

以下文件和产物不得修改：

- `revision_2026\koopman\universal_v2_modules.py`；
- `revision_2026\koopman\universal_v2\t3\models\K0.npz`；
- `revision_2026\koopman\universal_v2\t3\models\K1.npz`；
- `revision_2026\koopman\universal_v2\t3\models\K4.npz`；
- `revision_2026\koopman\universal_v2\t3\models\K5-linear.npz`；
- 现有D3、D4、`composer_results`、`koopman_combo_results`及其冻结hash；
- 已查看的D4 development结果。

如果hash与已有freeze不一致，T0立即停止并写`solutions.md`。不得用“文件名相同”代替内容一致。

### 3.2 新代码目录

所有新实现放在：

```text
revision_2026/koopman/innovation/
├── __init__.py
├── config.py
├── contracts.py
├── audit_inputs.py
├── legacy_adapter.py
├── data_protocol.py
├── generate_d4r.py
├── generate_d5.py
├── regime_features.py
├── regime_coverage.py
├── shared_backbone.py
├── low_rank_regime.py
├── multihorizon.py
├── temporal_consistency.py
├── error_subspace.py
├── certificate.py
├── train_component.py
├── compose_model.py
├── evaluate_offline.py
├── closed_loop_adapter.py
├── run_closed_loop.py
├── statistics.py
├── make_report.py
├── run_stage.py
└── tests/
    ├── test_freeze.py
    ├── test_shapes.py
    ├── test_causality.py
    ├── test_regime_labels.py
    ├── test_no_d5_access.py
    ├── test_force_balance.py
    ├── test_neutral_state_exclusion.py
    ├── test_direct_horizon.py
    ├── test_certificate.py
    └── test_closed_loop_adapter.py
```

结果统一写入：

```text
revision_2026/koopman/innovation_results/
├── freeze/
├── audits/
├── d4r/
├── models/
├── offline/
├── d5/
├── closed_loop/
├── figures/
├── work_log.md
├── solutions.md
├── gates.json
└── final_report.md
```

### 3.3 现有源码行号处理

当前不能访问5080源码，因此不在本文件伪造旧函数名和行号。T0必须生成：

- `audits/code_map.md`：实际文件、类/函数、起止行、用途、调用者；
- `audits/legacy_api.json`：K1加载、状态lift、一步预测、20步rollout、force decoder、plant step、控制器入口；
- `audits/schema.json`：46维S3、30维主状态、8维U1、四点力和左右拉伸载荷的索引、单位、顺序；
- `audits/source_hashes.json`：所有读取源文件和模型的SHA256。

若旧代码没有稳定公共接口，只允许在`legacy_adapter.py`中复制最小必要逻辑，并记录原文件hash和原行号；不得修改冻结文件。

## 4. 文件级实现合同

### 4.1 `config.py`

新增不可变配置`InnovationConfig`，至少包含：

```python
@dataclass(frozen=True)
class InnovationConfig:
    horizon: int = 20
    control_dt_s: float = 0.02
    plant_dt_s: float = 0.002
    state_s3_dim: int = 46
    state_main_dim: int = 30
    control_dim: int = 8
    point_force_shape: tuple[int, int] = (4, 2)
    load_dim: int = 2
    ranks: tuple[int, ...] = (1, 2, 4, 8)
    ridge_grid: tuple[float, ...] = (1e-8, 1e-6, 1e-4, 1e-2)
    min_mode_train_windows: int = 2000
    min_mode_validation_windows: int = 500
    min_mode_development_windows: int = 500
    max_switch_hz: float = 0.5
    min_dwell_s: float = 1.0
    force_warning_ratio: float = 0.8
    component_seeds: tuple[int, ...] = (151001, 151002, 151003, 151004, 151005)
```

`rated_force_n`和`ultimate_force_n`必须从plant配置读取并冻结，禁止在本类中凭报告数字硬编码。

### 4.2 `contracts.py`

定义：

```python
@dataclass
class HorizonBatch:
    x0_s3: np.ndarray            # [B, 46]
    u_future: np.ndarray          # [B, 20, 8]
    y_state: np.ndarray           # [B, 20, 30]
    y_force: np.ndarray           # [B, 20, 4, 2]
    y_load: np.ndarray            # [B, 20, 2]
    mask: np.ndarray              # [B, 20]
    trajectory_id: np.ndarray     # [B]
    start_index: np.ndarray       # [B]

@dataclass
class InnovationPrediction:
    state: np.ndarray             # [B, 20, 30]
    point_force: np.ndarray       # [B, 20, 4, 2]
    payload_load: np.ndarray      # [B, 20, 2]
    regime_weight: np.ndarray     # [B, 20, M]
    uncertainty: np.ndarray       # [B, 20, 3]
    finite_mask: np.ndarray       # [B, 20]
```

`validate_*()`必须检查dtype、维数、时间轴、单位、车辆顺序`FL/FR/RL/RR`、分力顺序`Fx/Fy`、左右载荷符号、归一化逆变换和有限性。任何不一致立即停止，禁止用reshape凑维数。

### 4.3 `audit_inputs.py`

实现：

```python
def hash_frozen_inputs(project_root: Path) -> dict: ...
def locate_legacy_by_hash(project_root: Path, sha256: str) -> Path: ...
def audit_seed_collisions(manifest_paths: list[Path], requested: list[int]) -> None: ...
def audit_d5_absent(results_root: Path) -> None: ...
def write_code_map(paths: list[Path], output: Path) -> None: ...
```

审计必须在任何训练和D5生成前完成。

### 4.4 `legacy_adapter.py`和`shared_backbone.py`

唯一允许调用冻结K1的入口：

```python
class FrozenK1Adapter:
    def lift(self, x_s3: np.ndarray) -> np.ndarray: ...
    def step(self, z: np.ndarray, u: np.ndarray) -> np.ndarray: ...
    def decode_state(self, z: np.ndarray) -> np.ndarray: ...
    def decode_force(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...
    def rollout(self, x0_s3: np.ndarray, u_future: np.ndarray) -> InnovationPrediction: ...
```

必须用旧D3/D4缓存做逐元素回归：最大绝对差`<=1e-10`或与原输出二进制一致。达不到则停止，不允许在新实验中使用“近似K1”。

### 4.5 `regime_features.py`

实现纯因果特征：

```python
def connector_kinematics(x_s3: np.ndarray, schema: dict) -> dict: ...
def causal_regime_features(history: np.ndarray, aoi: np.ndarray | None) -> np.ndarray: ...
def regime_weights(features: np.ndarray, thresholds: dict) -> np.ndarray: ...
def apply_hysteresis(weights: np.ndarray, previous: np.ndarray, dwell_steps: int) -> np.ndarray: ...
```

允许特征：当前/历史`vx,vy,r,kappa,ax,delta,p_i,v_n_i,Fx_i,Fy_i`、连接形变、相对速度、mask、AoI及其因果差分。禁止特征：场景编号、轨迹最终类别、未来真值、未来误差、oracle专家标签和D5统计量。

### 4.6 `low_rank_regime.py`

实现：

```python
class SharedBackboneRegimeResidual:
    def __init__(self, A0, B0, rank: int, n_modes: int): ...
    def residual_step(self, z, u, alpha): ...
    def step(self, z, u, alpha): ...
    def rollout(self, z0, u_future, alpha_future=None): ...
    def residual_ratio(self, z, u, alpha) -> np.ndarray: ...
```

约束：

- `U/V/G`零初始化或小量初始化，初始输出必须回归K1；
- 报告残差范数与K1名义步进范数之比；validation p99默认不得超过`0.25`，否则候选拒绝；
- 每个工况均报告有效秩、奇异值、样本量和条件数；
- 如果最优rank为0或所有残差被保护门清零，如实判定H1失败。

### 4.7 `multihorizon.py`

实现直接`h=1…20`映射，不允许用真实中间状态刷新：

```python
class DirectMultiHorizonHead:
    def fit(self, z0, u_future, alpha0, targets, sample_weight): ...
    def predict(self, z0, u_future, alpha0) -> InnovationPrediction: ...
    def predict_horizon(self, h: int, z0, u_prefix, alpha0): ...
```

训练优先使用分时域ridge/低秩最小二乘，避免再次训练不受控的大网络。每个`h`独立选择ridge但必须共享预注册网格；不得按D4 development逐时域手工选最好模型。

损失固定为：

\[
L=L_{state}+L_{force}+L_{load}+0.1L_{direction}+0.05L_{consistency}.
\]

前三项使用各组归一化NRMSE后等权；方向项只在真实力幅值超过validation噪声门时计算；一致性项比较直接`h+1`预测与工况残差模型从直接`h`预测继续一步的结果。权重只能在D4R validation小网格`{0,0.05,0.1}`内选择一次。

### 4.8 `error_subspace.py`和`certificate.py`

实现：

```python
def build_error_projection(schema: dict) -> tuple[np.ndarray, list[str]]: ...
def audit_neutral_exclusion(schema: dict, selected_names: list[str]) -> None: ...
def solve_common_p(mode_matrices, projection, gamma_grid) -> CertificateResult: ...
def verify_simplex_bound(result: CertificateResult, random_weights: np.ndarray) -> dict: ...
```

要求：

- `P=P.T`且`P>=1e-6 I`；
- 每个模式在误差子空间满足相同`P`和`gamma<1`；
- 用解析不等式报告连续单纯形凸组合边界，随机权重扫描只能作为数值审计，不能替代理论条件；
- CLARABEL/MOSEK等可靠求解器不可用或残差超限时，证书记为`not_established`；不得用SCS的`optimal_inaccurate`冒充定理成立；
- 若证书使D4R预测恶化超过3%，H3停止，方法保留无证书版本并删除稳定性核心主张。

### 4.9 `train_component.py`

命令行接口：

```text
python train_component.py --component regime --seed 151001
python train_component.py --component horizon --seed 151001
python train_component.py --component certificate --seed 151001
python train_component.py --component combined --seed 151001
```

每次训练必须写：配置、输入hash、代码hash、随机种子、轨迹ID、归一化参数、学习曲线、候选淘汰原因、最佳模型hash和资源用量。五seed全部完成，代表seed按validation中位数选择，不能按development最好值选择。

### 4.10 `evaluate_offline.py`

统一评估接口：

```python
def evaluate_model(model, dataset, horizons=range(1, 21)) -> dict: ...
def evaluate_by_regime(prediction, truth, regime) -> pd.DataFrame: ...
def evaluate_transition_windows(..., radius_s: float = 0.2) -> pd.DataFrame: ...
def evaluate_parameter_tasks(...) -> pd.DataFrame: ...
def evaluate_network_observation_stress(...) -> pd.DataFrame: ...
```

必须同时输出micro、场景等权macro、逐轨迹均值和逐时域曲线。`J_pred=(J_state+J_force+J_load)/3`，不得因某个候选有利而改权。

### 4.11 `closed_loop_adapter.py`

新预测器必须通过统一接口接入冻结控制器：

```python
class PredictorForFCSMPC:
    def predict_candidates(
        self,
        x_now: np.ndarray,
        candidate_u: np.ndarray,   # [9, 20, 8]
        network_state: dict,
    ) -> InnovationPrediction: ...
```

现有控制器是9候选有限控制集MPC，不得改称一般连续MPC。第一轮预测器比较中候选集、代价权重、约束、更新周期和安全层全部冻结；如果必须修改控制器才能让某个预测器工作，该结果另列为协同设计，不得归因于Koopman预测器。

### 4.12 `statistics.py`和`make_report.py`

实现轨迹为统计单位的10,000次配对bootstrap、双侧配对置换检验、Holm校正和效应量。窗口只用于曲线和机理诊断，不能把同一轨迹内窗口当成独立样本扩大显著性。

所有主图必须由CSV/JSON自动生成，图中标注样本数、CI和失败轨迹；极端值不得裁掉，只允许另加对数轴或放大图。

## 5. 数据协议与防污染

### 5.1 数据角色

| 数据 | 角色 | 允许用途 |
|---|---|---|
| 旧D1/D3 | `hypothesis_only` | 定位失败机理，不选新参数 |
| 已查看D4 | `development` | 训练/选择/消融和代码调试 |
| 新D4R | `targeted_development` | 补足物理工况与接触切换覆盖 |
| D5 | `blind_confirm` | 冻结后一次性确认，查看后禁止改规则 |

当前D5尚未创建，这是本轮仍能建立独立证据的关键条件。`test_no_d5_access.py`必须在T0–T6持续通过。

### 5.2 D4R定向开发集

先生成48条pilot，seed=`130001–130048`，只用于测量覆盖、运行时间和安全边界，不进入最终统计。

正式D4R共400条：

| 任务组 | train | validation | development | 目的 |
|---|---:|---:|---:|---|
| 松弛/低载荷直线与缓弯 | 60 | 20 | 20 | R0与简单骨干锚点 |
| 加速、制动和持续加载 | 60 | 20 | 20 | R1加载模式 |
| 稳态弯、单移线稳态段 | 60 | 20 | 20 | R2持续承载 |
| 正反阶跃、弯道进出、卸载/方向反转 | 60 | 20 | 20 | R3过渡模式 |

种子范围固定为：

- train：`131001–131240`；
- validation：`132001–132080`；
- development：`133001–133080`。

T0先审计与所有既有manifest的seed冲突。只要发生一处冲突，就在生成任何新数据前整体更换号段并更新冻结配置，不能只替换冲突seed。

窗口长度20、stride 20，按轨迹划分后再切窗。每个工况至少满足train 2000、validation 500、development 500个不重叠窗。达不到时允许增加对应任务组轨迹，但增加方案必须在训练模型前完成并记录；不得通过窗口重叠达到样本门。

### 5.3 高载荷覆盖

pilot只允许在plant额定、轮胎、连接器ultimate和车辆控制边界内调整质量、加速度、曲率、连接间隙与刚度。目标为`peak_force>=0.8 rated`且不触发ultimate。

如果三轮pilot仍无法安全产生至少200个不重叠高载荷窗，立即停止高载荷分支，并在论文删除以下主张：

- 高载荷安全泛化；
- 接近额定载荷的撕裂抑制；
- 高载荷UCB或高载荷门控有效。

不得降低`0.8 rated`定义后继续使用“高载荷”名称。仍可报告普通工作域的力、方向和左右拉伸载荷代理。

### 5.4 D5盲确认

只有T0–T6代码、模型、阈值、基线和hash全部冻结后才能执行`generate_d5.py`：

| 子集 | 数量 | seed |
|---|---:|---|
| internal E0–E6/E9 | 160 | `141001–141160` |
| 接触切换/方向反转 | 32 | `142001–142032` |
| external参数任务 | 24 | `143001–143024` |
| iid/burst/delay/DoS观测压力 | 40 | `144001–144040` |
| 高载荷（仅开发分支成立时） | 40 | `145001–145040` |

D5生成后立即写只读manifest和SHA256。一次性运行全部冻结候选；任何代码、阈值、归一化或样本变更都使整批D5确认失效。

## 6. 方法和消融矩阵

### 6.1 冻结基线

| 编号 | 方法 | 角色 |
|---|---|---|
| `B0` | K0 raw linear | 最简精度/成本基线 |
| `B1` | K1 fixed lifted linear | 主要可部署基线/公共骨干 |
| `B2` | K2 full bilinear | 输入—状态耦合失败边界 |
| `B3` | K5-linear multi-step | 旧多步训练边界 |
| `B4` | C5全局凸组合 | 无工况调度容量对照 |
| `B5` | C9原SHKC | 通用因果门控失败边界 |
| `B6` | D4窗口oracle/C10 | 不可部署上限，只作差距分析 |

### 6.2 新候选

| 编号 | 方法 | 唯一新增机制 |
|---|---|---|
| `N0` | K1+物理工况标签但无残差 | 检查标签本身是否改变统计，不应改变预测 |
| `N1` | K1+共享骨干低秩工况残差 | 只检验H1 |
| `N2` | K1+直接多时域head | 只检验H2 |
| `N3` | N1+误差子空间证书 | 只检验证书相对N1的代价和发散作用 |
| `N4` | N1+N2 | 只在N1、N2均过门后运行 |
| `N5` | N4+误差子空间证书 | 只在N3和N4均过门后作为最终候选 |

不得直接从B1跳到N5后把全部收益归于“统一创新”。

### 6.3 关键消融

- 物理工况权重 vs 同容量MLP通用门控；
- 真实因果`rho_k` vs 轨迹内打乱`rho_k`；
- 全局残差 vs 工况低秩残差；
- 一步递推20次 vs 直接`h=1…20`；
- 只状态head、只force/load head、完整head；
- 完整状态IRSP式投影 vs 误差子空间证书，仅作反例审计；
- 有/无滞回与最短驻留；
- clean、参数变化、接触切换和网络观测压力分层。

## 7. 分阶段任务树和停止门

### T0—源码、接口和污染审计

代码：实现`audit_inputs.py`、`legacy_adapter.py`、`test_freeze.py`和`test_no_d5_access.py`。

产物：`code_map.md`、`legacy_api.json`、`schema.json`、`source_hashes.json`、`seed_audit.json`、`t0_gate.json`。

通过条件：

- 冻结源和模型hash一致；
- K5-F2/F0身份不混淆；
- K1逐元素回归通过；
- D5不存在且未被任何import读取；
- plant和闭环入口能够精确定位。

任一失败立即停，不生成数据。

### T1—D4R pilot和资源测量

代码：实现`generate_d4r.py`、`data_protocol.py`、`regime_coverage.py`。

运行48条pilot，记录每轨迹wall time、峰值RAM/VRAM、磁盘增量、峰值力、ultimate触发、各工况窗数。

通过条件：无物理状态非有限、无无解释的ultimate越界，预计完整D4R磁盘不超过40 GB，单任务内存不超过16 GB。

若高载荷不可安全产生，只停止高载荷分支，不阻断普通工况创新实验。

### T2—D4R正式生成和合同审计

生成400条D4R并缓存冻结K0/K1/K2/K5和B4/B5输出。每条失败都保留`failure.json`，禁止替换seed。

通过条件：轨迹生成成功率100%；若plant自身数值失败，允许整项停止并分析，不允许静默丢弃；四工况覆盖满足2000/500/500窗；shape、时间和力方向合同全部通过。

### T3—H1物理工况低秩残差

代码：实现`regime_features.py`、`low_rank_regime.py`和`train_component.py --component regime`。

五seed训练rank `{1,2,4,8}`，只用train拟合、validation选择；development只运行一次。

H1通过条件必须同时满足：

- N1相对B1的D4R development总体`J_pred`改善至少8%；
- R1/R3受影响工况至少一个改善12%，另一个不恶化超过3%；
- state/force/load任何一组不恶化超过3%；
- 方向准确率不恶化超过1个百分点；
- 发散率不高于B1；
- 任一工况长期占用不得超过90%，有效工况数至少3；
- 切换率不超过0.5 Hz，最短驻留至少1 s；
- 轨迹级配对95% CI不跨0且Holm通过。

失败则停止N1/N3/N4/N5，只允许继续独立检验N2。

### T4—H2直接多时域输出

代码：实现`multihorizon.py`和`temporal_consistency.py`。

H2通过条件：

- N2相对B1的10–20步`J_pred`改善至少8%；
- 10–20步force和load至少一项改善10%，另一项不恶化超过3%；
- 1–5步状态不恶化超过3%，10–20步状态不恶化超过3%；
- 四点水平力方向和左右拉伸方向准确率均不恶化超过1个百分点；
- teacher-free测试和直接head均不读取真实中间状态；
- p99端到端20步预测小于8 ms，为9候选FCS-MPC留下计算预算；
- 轨迹级CI和Holm通过。

失败则停止N2/N4/N5；N1若已通过仍可独立进入确认。

### T5—H3误差子空间证书

代码：实现`error_subspace.py`、`certificate.py`及两个证书测试。

通过条件：

- 中性/积分状态全部排除并由测试锁定；
- 所有启用工况存在共同`P`和`gamma<1`；
- 求解残差满足冻结精度，连续凸组合界有解析推导；
- 相对未认证N1，development `J_pred`恶化不超过3%；
- 暂态放大p99、发散率或最坏20步误差至少一项改善8%。

证书不可行或只改善谱指标而不改善任何预测风险指标，则H3失败，删除“stable/certified Koopman”贡献，不影响已通过的N1/N2。

### T6—只组合通过项并冻结

组合逻辑：

- H1、H2都通过：训练N4；
- H1通过且H3通过：保留N3；
- H1、H2、H3全通过：训练N5；
- 只有一个假设通过：该单项就是最终候选，不人为补齐完整名称；
- 全部失败：正式回退B1，停止D5和闭环创新主张。

最终候选相对B1和B4必须都满足总体`J_pred>=8%`改善；相对B6 oracle差距至少闭合50%；安全关键组不退化；五seed结果稳定。随后冻结代码、模型、配置、归一化、阈值、基线、报告脚本和hash。

### T7—D5一次性盲确认

代码：`generate_d5.py`和`evaluate_offline.py --split d5`。

必须一次性运行B0–B6及所有冻结新候选。D5通过条件与T6相同，并额外要求：

- internal、接触切换、external三个子集至少两个独立通过8%门；
- 未通过的子集不允许恶化超过5%；
- network观测压力下非有限率和发散率不高于B1；
- high-load分支存在时，force/load p95和p99不恶化超过5%。

D5失败后不得返回D4调参并再次使用同一D5。失败结果直接进入论文边界或停止该方法。

### T8—闭环入口恢复和clean 100 m可行性

代码：实现`closed_loop_adapter.py`、`run_closed_loop.py`。先恢复历史闭环源精确hash；若找不到，则基于冻结plant建立新适配器，并与历史D3逐元素回归。

clean 100 m按用户指定工况运行：前30 m加速、随后匀速并进行正向5 s阶跃转向和反向5 s阶跃转向、剩余路段减速。加速度初值建议`0.4 m/s²`，但必须在pilot按轮胎和连接器约束冻结。

记录：

- 四车水平/竖直分力；
- 四车单车横摆和系统横摆；
- 货物左右侧拉伸载荷；
- 四点水平受力方向；
- 前后、左右、对角内力代理；
- 合力和合力矩；
- 100 m距离、终端速度、路径误差、控制输入和MPC可行率。

必须先让B1和最终候选在相同10个seed上全部完成距离门。任一方法`<10/10`完成时，停止正式网络闭环；先写`solutions.md`分析预测误差、控制合同、候选集、输入饱和或终端约束，不能靠修改评价距离掩盖。

### T9—控制实验顺序

严格按以下顺序运行，每次只增加一个因素。

#### T9.1 通信保护必要性诊断

在T8同一100 m工况中，对冻结B1控制器加入iid丢包、burst、delay和DoS，但暂不启用新通信保护。每类10个配对seed，比较clean下的受力、误差、完成率和不可行率。

只有通信扰动相对clean在至少一个主要指标上产生统计和实际意义明确的退化，才能写“实验显示需要通信保护”。如果没有退化，只能说明当前工况不敏感，不能人为增强攻击后仍沿用原协议。

#### T9.2 正常单移线

在无网络扰动下比较：

- AKE-M；
- B1-K1+相同FCS-MPC；
- B4-C5+相同FCS-MPC；
- 最终新Koopman+相同FCS-MPC。

先5个pilot seed，所有方法可行后扩展到20个配对seed。报告预测误差、横向/航向跟踪、四点力、左右拉伸载荷、控制能耗、MPC不可行率和计算时间。

#### T9.3 回头弯

沿用T9.2四种方法、同样20个seed和相同调参预算。重点报告入口、稳态弯中、出口三个阶段的10–20步误差，系统横摆、单车横摆、四点力方向和跟踪—受力Pareto。

#### T9.4 通信扰动和DoS

比较：

- 无保护B1；
- 具有相同观测管理的B1；
- delay/packet-loss-aware强基线；
- 最终新Koopman但无网络监督器；
- 最终新Koopman+冻结网络监督器。

iid、burst、delay和DoS各20个配对seed。必须分离“预测器收益”和“通信保护收益”，不能只比较最弱基线与完整方法。

### T10—统计、图表和论文证据收口

代码：`statistics.py`、`make_report.py`。

输出至少包括：

- `horizon_state.csv/png`；
- `horizon_force_load.csv/png`；
- `regime_performance.csv/png`；
- `regime_occupancy.csv/png`；
- `transition_error.csv/png`；
- `parameter_generalization.csv/png`；
- `certificate_audit.json/png`；
- `prediction_pareto.csv/png`；
- `closed_loop_100m.csv/png`；
- `lane_change.csv/png`；
- `hairpin.csv/png`；
- `network_dos.csv/png`；
- `force_direction.csv/png`；
- `paired_statistics.json`；
- `gates.json`；
- `final_report.md`；
- `solutions.md`和`work_log.md`。

## 8. 主指标和判定口径

### 8.1 离线预测

- 1、5、10、15、20步状态NRMSE；
- 10–20步平均状态NRMSE；
- 四点`Fx/Fy` NRMSE和方向准确率；
- 左右货物拉伸载荷NRMSE和符号准确率；
- 接触切换前后±0.2 s峰值误差；
- 参数外推误差；
- 非有限率、发散率和最坏轨迹；
- 残差比、工况占用率、切换率和置信度校准；
- 端到端20步预测p50/p95/p99，而不是只测门控器本身。

### 8.2 闭环

- 路径纵横向RMSE、航向RMSE和最大误差；
- 任务完成率、100 m终端距离/速度；
- 四车单车横摆、系统横摆和共同ICR残差；
- 四点水平/竖直分力、方向角和变化率；
- 货物左右拉伸载荷、前后/左右/对角内力代理；
- 峰值、RMS、p95、p99和超限持续时间；
- MPC不可行率、fallback率、控制能耗和切换率；
- 端到端控制周期p99。

没有材料、截面和连接区破坏参数时，结论只能写“受拉撕裂趋势/内力代理”，不得判断真实货物是否开裂。

### 8.3 统计

- 主单位为完整轨迹，不是窗口；
- 核心场景20个配对seed；
- 10,000次轨迹级配对bootstrap；
- 配对置换检验和Holm校正；
- 同时报均值、中位数、标准差、95% CI、效应量和失败率；
- 预注册8%为预测实际意义门、5%为安全关键退化上限；
- micro和场景等权macro同时报告，二者冲突时不得只选有利口径。

## 9. 运行命令

在5080 PowerShell中执行：

```powershell
$projectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$innovationRoot = Join-Path $projectRoot 'revision_2026\koopman\innovation'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { $pythonExe = 'python' }

& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t0 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t1 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t2 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t3 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t4 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t5 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t6 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t7 --project-root $projectRoot --confirm-once
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t8 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t9 --project-root $projectRoot
& $pythonExe (Join-Path $innovationRoot 'run_stage.py') --stage t10 --project-root $projectRoot
```

`run_stage.py`每阶段开始前必须读取上一阶段`complete.json`和hash，结束时原子写入新的`complete.json`。任何门失败时返回非零退出码、写`failure.json`和`solutions.md`，且后续依赖阶段拒绝启动。

## 10. 资源预算

以下为计划值，T1 pilot后必须用实测覆盖：

| 项目 | 初始预算 | 超限处置 |
|---|---:|---|
| D4R 400条生成 | 1–3 h | 先检查plant子步、并行和I/O，不替换失败seed |
| D4R原始数据+缓存 | 15–35 GB | 需要运行前至少60 GB空闲；分块压缩，不删原始manifest |
| 单个低秩候选训练 | <45 min/seed | 分rank串行、窗口chunk化；不得缩短20步冒充完成 |
| 五seed完整组件训练 | <8 h/组件 | 记录wall time；超时先profile再决定是否停止 |
| RAM | <16 GB | memmap、trajectory batch、chunk 128窗口 |
| VRAM | <8 GB | AMP仅在数值审计通过后使用；优先CPU闭式最小二乘 |
| 单候选20步预测p99 | <8 ms | 批量化9候选，缓存lift和工况特征 |
| 完整FCS-MPC周期p99 | <20 ms | 不能只报门控器时间；超限则方法不可实时部署 |
| D5生成和一次评估 | 2–5 h | 不允许中途查看后改规则重跑 |
| 全闭环统计 | 8–24 h | 5-seed pilot后再扩20 seed；失败保留日志 |

## 11. 可能跑不动或证据不成立的情况

| 编号 | 现象 | 可能原因 | 先做什么 | 停止/降级条件 |
|---|---|---|---|---|
| `F01` | 5080项目根目录不存在 | 盘符/远程连接错误 | 只读检查绝对路径和主机 | 不得在Review目录伪造项目后继续 |
| `F02` | 冻结hash变化 | 旧证据被修改或复制错误 | 对照freeze和备份定位 | 无法恢复精确输入则整轮停止 |
| `F03` | 历史闭环hash找不到 | 旧脚本覆盖 | 按SHA256递归定位、查备份 | 只能新建适配器并完成D3逐元素回归，否则闭环停止 |
| `F04` | K1适配输出不一致 | lift、归一化或decoder选错 | 逐字段比较第一个偏差时刻 | 最大差仍>`1e-10`则停止 |
| `F05` | D5已经存在/被读取 | 确认污染 | 检查访问与manifest | 当前D5作废，必须建立全新编号确认集 |
| `F06` | seed碰撞 | 与D1–D4已有seed重合 | 审计所有manifest | 生成前整体换号段；生成后发现则该数据作废 |
| `F07` | 工况窗不足 | 物理阈值不匹配/任务激励不足 | 看连续`p_i/v_n_i`分布 | 合并相邻工况或补轨迹；禁止重叠采样凑数 |
| `F08` | 完全没有高载荷窗 | 当前工作域远低于rated | 合法参数pilot | 三轮仍不足则删除高载荷分支，不降阈值改名 |
| `F09` | 高载荷pilot触发ultimate | 激励不安全 | 降低单项激励并查受力来源 | 无安全可行域则停止高载荷实验 |
| `F10` | 四点力顺序或符号异常 | FL/FR/RL/RR、Fx/Fy映射错误 | 用直线/纯转向单元测试 | 不能确定方向合同则所有受力结论停止 |
| `F11` | 作用—反作用残差“恒为0” | 把同一货物侧力直接取负 | 审计plant实际施力日志 | 没有车辆侧独立应用量则只报告not identifiable |
| `F12` | 五seed完全相同 | 随机种子未接入或闭式解唯一 | 检查random_state和参数hash | seed未生效则修复并重跑全部开发模型 |
| `F13` | 低秩残差始终为0 | K1已是局部最优或正则过强 | 查梯度、设计矩阵秩和validation路径 | 所有rank为0则H1失败，不继续包装 |
| `F14` | 残差过大/数值爆炸 | 病态回归、归一化错误 | SVD、条件数、ridge路径 | p99残差比>0.25且无法通过validation门则拒绝 |
| `F15` | 门控长期单一模式 | 物理阈值失衡或工况不可分 | 看占用率和混淆矩阵 | 最大模式>90%则退化为无门控模型 |
| `F16` | 模式切换抖振 | 阈值边界噪声 | 滞回、低通和1 s驻留 | validation仍>0.5 Hz则H1失败 |
| `F17` | 因果特征测试失败 | 泄漏未来值/场景标签 | 特征provenance逐列审计 | 未消除泄漏不得训练/确认 |
| `F18` | 直接head内存爆炸 | 显式展开全部未来输入矩阵 | 按h分块、低秩/SVD、memmap | 仍>16 GB则缩减参数化，不缩短horizon |
| `F19` | h越大误差突增 | 直接映射病态/数据不足 | 看逐h条件数和ridge | 10–20步不过门则H2失败 |
| `F20` | force改善但state恶化 | 多任务梯度/目标冲突 | 独立head和固定等权消融 | state恶化>3%则不得通过 |
| `F21` | 时间一致性很差 | 各h独立拟合互相矛盾 | 启用冻结一致性权重网格 | 性能和一致性不能同时过门则H2失败 |
| `F22` | cvxpy/求解器不可用 | 环境缺依赖 | 记录版本，尝试可靠已安装求解器 | 不得把采样谱半径代替证书，H3降级 |
| `F23` | SDP为infeasible | 共同P不存在 | 检查误差子空间、rank和gamma网格 | 预注册网格均不可行则H3失败 |
| `F24` | `optimal_inaccurate` | 数值尺度/求解器精度 | 归一化、提高精度、换可靠求解器 | 残差不过门则证书不成立 |
| `F25` | 中性状态误入证书 | schema选择错误 | 自动检查名称和单位 | 测试失败立即停止理论分支 |
| `F26` | 证书成立但预测变差 | 约束过强 | 与未认证N1配对比较 | 恶化>3%或无风险指标改善则删除证书贡献 |
| `F27` | micro改善、macro恶化 | 长轨迹主导 | 同时报场景等权和逐轨迹 | 任一主口径恶化>5%则不能称总体提升 |
| `F28` | D5未复现 | development过拟合 | 原样报告子集和最坏轨迹 | 不得回D4调参后复用同一D5 |
| `F29` | clean 100 m距离失败 | 控制合同、输入饱和或预测偏差 | 分解终端距离/速度/候选可行性 | `<10/10`完成则网络闭环停止 |
| `F30` | p99超过20 ms | 9候选×20步重复计算 | 批量化、缓存lift、profile | 优化后仍超限则不可部署 |
| `F31` | 通信扰动没有造成退化 | 工况/攻击强度不敏感 | 检查实际AoI、丢包和控制日志 | 不得声称实验得出需要保护 |
| `F32` | 通信保护降低误差但放大受力 | 状态传播过激/约束遗漏 | 报tracking–force Pareto和ultimate触发 | force/load退化>5%则保护不通过 |
| `F33` | DoS检测晚或误报多 | 阈值/窗口不当 | 报FPR/FNR/检测延迟 | 不得只报最终跟踪曲线 |
| `F34` | AKE-M比较不公平 | 状态、约束或调参预算不同 | 统一接口和预算表 | 无法公平对齐则不作优越性结论 |
| `F35` | 图片看似改善但CSV不支持 | 轴裁剪/聚合口径错误 | 图表从冻结CSV自动生成 | 数值冲突时以可复算CSV为准并修图 |

同一阻塞连续出现三次且安全替代均失败时，停止对应分支并更新`innovation_results\solutions.md`，必须写清：事实、可能原因、已尝试方案、资源消耗、证据边界和下一次需要的新条件。

## 12. 工作记录和留痕

每完成一个代码或实验阶段，立即追加`innovation_results\work_log.md`，禁止等全部结束后回忆补写。格式固定为：

```markdown
## Ixxxx — 阶段名称

- 开始/结束时间：
- 5080主机与项目根目录：
- 用户任务书SHA256：
- 修改文件、函数和修改前后SHA256：
- 实际执行命令与退出码：
- 输入数据/模型/配置hash：
- seed、样本数、失败数和是否替换：
- 关键指标和验收门：
- 资源：wall time、RAM、VRAM、磁盘：
- 生成文件及SHA256：
- 事实、推测和未解决问题：
- 结论：通过 / 停止 / 降级：
```

代码修改还必须生成`audits/change_manifest.json`，逐文件记录：

- `path`；
- `before_sha256`；
- `after_sha256`；
- `functions_changed`；
- `reason`；
- `tests_run`；
- `rollback_path`。

不允许覆盖用户既有改动。若目标文件已有未记录修改，新实现转移到`innovation/`适配层；确需修改plant时必须先冻结原文件，并说明是“仅日志插桩”还是“动力学方程变化”。只要动力学方程发生变化，旧训练数据与旧基线不能直接公平比较，必须在新plant上重训所有基线。

## 13. 论文行文和允许结论

### 13.1 推荐结构

1. **Motivating diagnosis**：用K0–K5、C5、C9和oracle证明全局平均、病态双线性、远时域递推和通用门控失效。
2. **Method derivation**：从接触工况、共享骨干和多时域预测三个问题推导CRMH-Koopman，而不是按试验时间顺序讲“尝试了很多模型”。
3. **Theoretical boundary**：只证明误差子空间和连续凸组合的条件结论；不冒充完整闭环稳定性。
4. **Component experiments**：N1、N2、N3逐项验证生效区域。
5. **Combined blind confirmation**：N4/N5只组合已通过模块，D5一次性确认。
6. **Closed-loop value**：相同FCS-MPC下验证预测收益是否转化为控制收益，再独立加入通信保护。
7. **Limitations**：高载荷、材料撕裂、实车/高保真和未建模参数边界。

### 13.2 允许使用“创新Koopman”的最低条件

- 至少H1或H2形成清晰、非平凡且可复现的结构创新；
- 最终候选在D5相对K1和C5均达到实际与统计意义门；
- 至少一个关键工况的闭环约束、跟踪或受力指标改善，且其他安全量不退化；
- 消融能够隔离每个新增机制；
- 计算满足实时预算；
- 标题、摘要和贡献不超过证据等级。

若只得到“比较发现K1最好”，比较结果可以进入论文作为模型选择依据，但不能把Koopman预测器写成核心算法创新。若只有离线收益、没有闭环收益，只能把预测创新放在次要贡献或补充材料，TVT主线仍需依赖经过强基线验证的控制/网络创新。

## 14. 最终任务树

```text
T0 冻结/接口/污染审计
├─ 失败：停止全部，写solutions
└─ 通过
   └─ T1 D4R pilot、覆盖和资源测量
      ├─ 高载荷不可行：只删除高载荷分支
      └─ T2 D4R正式生成与缓存
         ├─ T3 H1物理工况低秩残差
         ├─ T4 H2直接多时域输出
         └─ T5 H3误差子空间证书
            └─ T6只组合已通过项并冻结
               ├─ 无候选：回退K1，停止创新主张
               └─ 有候选
                  └─ T7 D5一次性盲确认
                     ├─ 失败：原样收口，不复用D5
                     └─ 通过
                        └─ T8 clean 100 m距离与动力学验收
                           ├─ 失败：停止网络闭环，分析控制合同
                           └─ 通过
                              └─ T9 通信必要性→单移线→回头弯→网络/DoS
                                 └─ T10 统计、图片、报告和论文证据收口
```

本任务书的核心停止原则是：**拿不到支撑证据就停在对应分支，保留负结果和解决方案；不靠降低阈值、更换口径、删除失败seed或复用确认集把方法“跑成功”。**

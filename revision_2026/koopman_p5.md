# Koopman长时预测改进执行书

> 文档用途：承接`koopman_path.md`完成的P0—P3诊断，指导AI继续开发、训练、验收并形成论文证据。  
> 编写日期：2026-09-02  
> 5080项目根：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 父任务书：`revision_2026\koopman_path.md`，SHA256 `08EFC410984FE426FA8B9C9124F5AAD1A48AF4764184765BAC56CE7FF127CE5A`  
> 父正式运行：`20260902_094727_KOOPMAN_V2_KOOPMAN_V2_P0_R02_R01`  
> 授权边界：本文是方案编写，不授权立即修改源码、训练、读取confirm、运行MPC或网络实验。以后用户明确要求“按koopman_p5.md执行”时，第一轮只执行S0—P5C并人工停止。

## 0. 当前事实、错误前提和路线裁决

### 0.1 已由原始CSV复算的事实

| 项目 | 数值/状态 | 证据位置 | 结论 |
|---|---:|---|---|
| 数据规模 | 672条轨迹、192个base family、12类工况 | N5 `data_manifest.csv` | train/validation/development为336/168/168条，family为96/48/48 |
| confirm | 读取计数0 | P0 `complete.json` | 仍保持隐藏，不得提前读取 |
| S0复现 | `J20=0.13023504180689485`，误差0 | P0 `n6_regression_report.json` | N6基线可复现 |
| P1分区线性 | 一步改善7.1146%，5折均为正 | P1 `partitioned_cv.json` | 有工况差异信号，但只证明一步局部差异 |
| P1残差子空间 | 全部两两中位主角10.0087° | P1 `subspace_test.json` | 未达到15°，不能声称三类活跃子空间已被证明 |
| P2三专家oracle | 20步macro退化9.9133% | P2 `comparison.json` | 取消P4多专家/因果门控路线 |
| B1完整双线性 | 1/5/10步改善27.87%/28.89%/23.60%，20步退化7.57% | P3 `b1_rows_validation.csv` | 双线性项有效，但长时传播不合格 |
| B1场景 | 12类中10类20步改善；D5退化316.27% | P3 `diagnosis.json` | 总退化主要由回头弯拖累 |
| B1实际发散 | 20步发散率0.15496%，6个发散窗全部来自D5 | P3逐窗CSV | 不只是输入盒的保守理论警告 |
| B2/B3 | `J20=44.3478/3.3463`，发散62.09%/18.29% | P3 `diagnosis.json` | 当前低秩双线性永久作为负结果，不再调rank |

验证集S0的冻结比较数值如下；这些数值只用于P5—P8验证门，不得与development的`0.130235`混用：

| 时域 | `J_common` |
|---:|---:|
| 1步 | 0.009915459725118926 |
| 5步 | 0.04032479477345827 |
| 10步 | 0.06750430020515748 |
| 20步 | 0.12783742731971484 |

D5的验证集S0边界：整体`J20=0.11801456363530423`；`window_start=100/120`共32个困难窗口的均值/P95/最大值为`0.16485749568851826 / 0.23267382347348983 / 0.2331185286479644`。

### 0.2 必须纠正的四个前提

1. **P3的`machine_state=PASS`只代表诊断完整，不代表候选通过。** B1/B2/B3都为`REJECT`。
2. **双线性不是“没有用”。** 置零双线性项使`J20`从0.1375恶化到1.3172，打乱控制使其恶化到1.9864；它学到了有效耦合，失败在长时传播和D5，不在输入—状态作用不存在。
3. **不能再训练三个独立专家。** 即使使用未来真实窗口标签的oracle上限仍退化，增加门控网络不能超过这个上限。
4. **不能预先宣称新模型整体渐近稳定。** S0矩阵本身的谱半径约1.004885。本文只能设计“残差模态按构造Schur稳定，且不改变S0主干特征值”，再用有限时域压力滚动证明没有新增失稳。

### 0.3 当前总裁决

```text
保留：S0公共骨干、完整47维状态、7维因果控制、R3统一解析读出
取消：P4三专家门控、当前B1/B2/B3作为最终候选、扩大双线性rank
主攻：物理分组的阻尼模态残差升维 + 多时域训练 + 尾部风险约束
后续：相对状态通过后再加R3物理损失；预测通过后再判断稳定性模块
```

## 1. 目标、非目标和论文声明边界

### 1.1 主要目标

开发工作名为“物理分组阻尼模态残差Koopman”（Grouped Damped-Mode Residual Koopman，简称`GDM-RK`）的候选，回答：

1. 能否保留S0不发散、接口简单和可解释的优点；
2. 能否吸收B1在1—10步暴露出的有效输入—状态耦合；
3. 能否避免B1在D5转向爬升结束至持续大曲率初段的误差放大；
4. 能否在20步、连接力和完整内部力上形成可重复、跨family的改善。

### 1.2 本任务不做

- 不改变四车植物、连接器、轮胎、载荷转移、共同ICR或转向分配；
- 不重新生成672条正式轨迹，不删除D5、D7、D9、D10等不利工况；
- 不使用场景编号、未来窗口类别、未来实测轮角或预测区间内未来事件作为输入；
- 不进入MPC、通信扰动、丢包、AoI或DoS；
- 不把“残差模态稳定”扩大为车辆阵列闭环全域稳定。

### 1.3 可证伪假设

| 假设 | 数据预测 | 反证条件 |
|---|---|---|
| H1：S0缺少有限维非线性残差模态 | L16/L32多时域模型在20步显著优于S0 | 两种维数都未改善5%，或CI跨0 |
| H2：B1退化来自不受约束的递推，而非耦合信息无效 | 阻尼模态模型保留1—10步收益且D5不再爆发 | D5困难窗仍退化超过3%或出现发散 |
| H3：均值损失掩盖少数高风险窗口 | 加CVaR后P95/P99和D5困难窗改善，macro代价不超过2% | 只降低均值、不降低尾部；或总体明显恶化 |
| H4：连接相对状态改善可转化为力和内部力改善 | P6物理损失使四点力/内部力各改善至少10% | 相对状态未改善，或R3误差放大重现 |
| H5：阻尼模态不新增特征值失稳 | 残差块谱半径不大于0.995，整体谱为S0与残差谱并集 | 数值谱不满足、40/80步出现新增发散 |

任何一个假设失败都原样保留为结果，不用下一模块掩盖。

## 2. 版本隔离、数据边界和证据链

### 2.1 新版本目录

不得直接把P5实现写入已经产生P0—P3证据的`koopman_predict_v2`。首次执行时先复制为新版本：

```text
revision_2026\koopman_predict_v3
revision_2026\koopman_predict_v3_results
revision_2026\koopman_predict_v3_models
```

父V2保持只读。新协议为：

```text
revision_2026\koopman_predict_v3\config\protocol_v3.json
```

协议必须登记：本文SHA、父任务书SHA、父V2源码当前manifest、父run ID、P0/P1/P2/P3关键结果SHA、N5 manifest、归一化和672个cache身份。

### 2.2 数据用途

| 数据 | 数量 | 本轮用途 |
|---|---:|---|
| train | 336轨迹/96 family | 5折family-CV、超参数选择、完整训练、train-family bootstrap |
| validation | 168轨迹/48 family | P5/P6/P7每阶段冻结后一次门禁；不得早停或反复挑checkpoint |
| development | 168轨迹/48 family | P9一次性评价；基线已见，因此不称盲测 |
| confirm | 96 family | P10唯一候选最终一次读取；P9未过不得生成/读取 |

归一化继续只使用N5冻结train统计。窗口必须按完整轨迹和base family划分，禁止把同一family的不同车辆植物或左右方向拆入训练折和验证折两侧。

### 2.3 证据身份

每个阶段目录必须生成：

```text
source_manifest.json
data_identity.json
protocol_snapshot.json
taskbook_snapshot.md
environment_manifest.json
command.txt
stdout.log
complete.json
gate_report.json
figure_manifest.json
```

模型同时保存`*.pt`、只含数值矩阵的`*.npz`、超参数JSON和SHA256。图必须能由CSV/JSON重新生成。

## 3. 方法定义

### 3.1 冻结S0主干

在train-only归一化坐标中，S0写为：

\[
\bar x_{k+1}=A_0\bar x_k+B_0\bar u_k+b_0,
\qquad \bar x_k\in\mathbb R^{47},\quad \bar u_k\in\mathbb R^7.
\]

`A0/B0/b0`从冻结S0系数精确拆出。GDM-RK主实验中它们始终冻结，不允许用validation解冻；这样性能变化可归因于残差升维，而不是重新训练一个任意大网络。

### 3.2 物理分组编码器

沿用P1已经审计的变量组：

```text
g0 = x[0:3]    货物速度/横摆角速度
g1 = x[3:19]   相对位置与航向
g2 = x[19:31]  逐车相对速度/横摆角速度
g3 = x[31:47]  四连接点位移和相对速度
```

不删除任何组。残差observable由两个支路组成：

\[
\eta_k=\phi_\theta(\bar x_k,\bar u_k)
=\begin{bmatrix}
\phi_d([g_0,g_1,g_2,\bar u_k])\\
\phi_c([g_2,g_3,\bar u_k])
\end{bmatrix}\in\mathbb R^r,
\qquad r\in\{16,32\}.
\]

`g2`同时进入车辆动力学支路和连接支路，因为它是两者之间的因果耦合量。两个支路均使用两层MLP、SiLU隐藏激活和`tanh`输出：

| 模型 | 每支路输出 | 隐藏宽度 |
|---|---:|---:|
| L16 | 8 | 16 |
| L32 | 16 | 32 |

不使用注意力、场景标签或专家softmax。必须报告每个支路的输出方差、有效秩和梯度范数，防止observable塌缩。

### 3.3 阻尼模态残差传播

预测器定义为：

\[
\begin{aligned}
\bar x_{k+1}&=A_0\bar x_k+B_0\bar u_k+b_0+E\eta_k,\\
\eta_{k+1}&=F\eta_k+G_\eta\bar u_k+c_\eta.
\end{aligned}
\]

其线性部分为块上三角形式：

\[
K=\begin{bmatrix}A_0&E\\0&F\end{bmatrix},
\qquad C=[I_{47}\;0].
\]

因此：

\[
\sigma(K)=\sigma(A_0)\cup\sigma(F).
\]

`F`不使用任意稠密矩阵，而由二维阻尼旋转块组成。对第`j`对模态：

\[
F_j=r_j
\begin{bmatrix}
\cos\omega_j&-\sin\omega_j\\
\sin\omega_j& \cos\omega_j
\end{bmatrix},
\qquad
r_j=0.995\,\sigma(a_j),\quad
\omega_j=\pi\sigma(b_j).
\]

其中`σ`是Sigmoid，所以`0<r_j<0.995`，残差模态按构造Schur稳定，并能表达连接弹簧—阻尼系统的衰减振荡。若`r`为奇数则禁止静默丢维；当前只允许16/32两个偶数维数。

注意：块三角结构只能保证新增残差模态不引入更大的特征值，不能消除`A0`已有的`ρ(A0)≈1.004885`，也不能单凭特征值排除非正规瞬态放大。因此还必须做D5和40/80步压力滚动。

### 3.4 Koopman闭合与多时域训练

从真实`x_k`编码`η_k`后，在预测区间内只传播`η`，不每步用真实状态重新编码。用闭合损失约束传播后的observable接近真实未来状态的编码：

\[
\mathcal L_{inv}=\sum_{h\in\{1,5,10,20\}}
\left\|\hat\eta_{k+h}-
\operatorname{sg}\!\left[\phi_\theta(\bar x_{k+h},\bar u_{k+h})\right]
\right\|_2^2,
\]

其中`sg`表示stop-gradient，避免编码器与传播器同时任意缩放。另报告不使用stop-gradient的诊断，但不得在validation后切换定义。

状态训练损失按物理组归一化：

\[
\ell_h=
0.30\,\mathrm{RMSE}(g_0)+
0.20\,\mathrm{RMSE}(g_1)+
0.20\,\mathrm{RMSE}(g_2)+
0.30\,\mathrm{RMSE}(g_3).
\]

多时域损失为：

\[
\mathcal L_{multi}=0.10\ell_1+0.20\ell_5+0.25\ell_{10}+0.45\ell_{20}.
\]

为了防止D5这类少数窗口被均值掩盖，对batch内20步误差使用90%尾部条件均值：

\[
\operatorname{CVaR}_{0.90}(\ell_{20})
=\frac{1}{|\mathcal I_{0.90}|}
\sum_{i\in\mathcal I_{0.90}}\ell_{20}^{(i)},
\]

其中`I0.90`是当前batch误差最高10%的样本，至少保留4个样本。主模型总损失：

\[
\mathcal L=
\mathcal L_{multi}
+0.25\widetilde{\mathcal L}_{tail}
+0.10\widetilde{\mathcal L}_{inv}
+10^{-4}\|E\|_F^2
+10^{-5}\|\theta\|_2^2.
\]

辅助损失先除以训练开始前256个train窗口的冻结中位数，记为`~L`；标定后保存到协议，不能看validation再修改。

### 3.5 P6物理一致损失

P5只在相对状态通过后，才用可微R3解码器加入：

\[
\hat f_{k+h}=\mathcal H_{R3}(\hat d_{k+h},\hat v_{k+h};p),
\]

\[
\hat f_{int,k+h}=(I-W^\dagger W)\hat f_{k+h},
\]

\[
\mathcal L_{phy}=\sum_h\omega_h\left[
\mathrm{RMSE}\!\left(\frac{\hat f-f}{s_f}\right)
+0.75\,\mathrm{RMSE}\!\left(\frac{\hat f_{int}-f_{int}}{s_{int}}\right)
+0.10\frac{\|W\hat f_{int}\|_2}{\|\hat f_{int}\|_2+\epsilon}
\right].
\]

`sf/sint`只读冻结train归一化。`λphy`只允许`0.05`和`0.20`两个预注册值，用train-family CV选择。不得学习独立力head；否则无法区分状态改善与力头拟合。

## 4. 代码修改表

新代码只写入`koopman_predict_v3`：

| 文件 | 函数/类 | 具体修改 | 输入 | 输出 | 必须测试 |
|---|---|---|---|---|---|
| `config/protocol_v3.json` | 协议 | 登记父身份、阶段、模型矩阵、损失、seed、门槛、资源和停止点 | 本文与父run | 冻结JSON | SHA、非法阶段、confirm禁读 |
| `src/data_contract.py` | `FrozenSequenceDataset` | 基于N5 cache按family产生连续20/40/80步样本，family-balanced sampler | manifest/cache | tensor batch | 跨轨迹、跨family、归一化泄漏测试 |
| `src/lift.py` | `GroupedResidualEncoder` | 实现L16/L32双支路编码 | `x47,u7` | `eta16/32` | 维数、全部变量可达、有限梯度、无future输入 |
| `src/lift.py` | `DampedModeMatrix` | 生成二维阻尼旋转块 | `a,b` | `F` | 每个块谱半径`<0.995`、奇数维拒绝 |
| `src/lift.py` | `TriangularResidualKoopman` | 冻结A0/B0/b0，传播x/eta，C直读物理状态 | `x,u序列` | 多时域预测 | `E=0`逐元素回归S0、块三角谱测试 |
| `src/losses.py` | `group_rmse()`、`cvar_tail()`、`koopman_closure()` | 实现公式和初始尺度标定 | rollout/target | 分项loss | 手工小样本、CVaR样本数、stop-gradient |
| `src/train.py` | `warm_start()` | 一步暖启动，只训练encoder/E/G/F参数 | train fold | warm checkpoint | seed复现、S0参数无梯度 |
| `src/train.py` | `train_multihorizon()` | 多时域、梯度裁剪、早停、断点恢复 | train/CV | checkpoint/curve | resume幂等、OOM等效batch |
| `src/evaluation_v3.py` | `rollout_torch_model()` | 与V2同一窗口、控制序列、1/5/10/20步口径 | checkpoint/cache | 逐窗CSV | S0包装器与V2逐元素一致 |
| `src/evaluation_v3.py` | `stress_rollout()` | D5 2.0—2.4 s、40/80步和最坏family压力测试 | 模型/缓存 | tail/stability表 | 不越过轨迹末端 |
| `src/physics_decoder_torch.py` | `TorchR3Decoder` | float64可微R3/V1、完整内部力 | 预测d/v、参数 | force8/internal8 | 与NumPy R3逐元素、梯度检查、零空间残差 |
| `src/stability.py` | `triangular_spectrum()` | 核对`spec(K)=spec(A0)∪spec(F)` | 冻结矩阵 | 谱与容差 | 已知块矩阵故障注入 |
| `src/stability.py` | `finite_horizon_gain()` | 1/5/10/20/40/80步实际输入增益和P99 | 模型/实际控制 | 压力表 | B1失败轨迹回归 |
| `scripts/run_v3.py` | 阶段runner | S0、S1、R0、P5A—P10硬门和断点 | CLI | 唯一run目录 | 越阶段、重复run、硬门停止 |
| `scripts/plot_v3.py` | 绘图 | 误差增长、D5、连接力、latent模态、CI和Pareto | 原始CSV | PNG/PDF | 图manifest、单位、数据SHA |
| `tests/test_no_future_leakage.py` | 篡改测试 | 改未来真实量，当前输入与预测前缀digest不变 | cache | PASS | x/u/eta/physics全覆盖 |
| `tests/test_p5_gates.py` | 门禁故障注入 | 人工制造D5退化、CI跨0和发散 | 假数据 | 必须拒绝 | 防止`stage PASS`与候选PASS混淆 |

## 5. 实验矩阵与公平性

### 5.1 主矩阵

| 编号 | 模型 | 作用 | 是否有资格成为最终候选 |
|---|---|---|---|
| M0 | S0固定线性 | 永久骨干 | 是，基线 |
| M1 | B1完整双线性 | 复用P3机制证据 | 否，只作短期有效/长时失败对照 |
| A1 | L16一步训练 | 证明只做一步是否会重现时域衰减 | 否，消融 |
| A2 | L16多时域、无CVaR | 隔离多时域损失 | 否，消融 |
| C16 | L16多时域+CVaR+阻尼模态 | 主候选 | 是 |
| C32 | L32多时域+CVaR+阻尼模态 | 容量对照 | 是 |
| AF | 与C16同容量、自由稠密F | 隔离阻尼模态作用；中央seed先行，发散即停 | 否，消融 |
| CP | P5最佳候选+物理损失 | P6候选 | 通过P6后是 |
| CS | CP或P5最佳+必要稳定性处理 | P7候选 | 通过P7后是 |

最终模型选择只能在C16/C32/CP/CS中进行；M1和消融项不能因某一局部工况漂亮被重新选回。

### 5.2 统一条件

- 输入均为相同47维状态和7维当前/已知控制；
- 同一train/validation/development轨迹、同一20 ms周期、同一窗口起点；
- S0和所有候选使用同一R3解析力读出；
- 所有模型同时报告总参数、可训练参数、训练时间、显存、CPU/GPU推理时间；
- 5个主seed为`990101—990105`，每个seed同时固定family bootstrap和网络初始化，明确这是联合稳健性而非单一随机源；
- 中央模型seed固定`990100`；消融只用中央seed时不得据此声明统计显著；
- float32训练、float64最终评估；禁止混用不同精度的门禁数值；
- validation checkpoint由train-family CV确定的固定训练步数生成，不允许validation早停。

### 5.3 train-CV选择规则

96个train family按seed `990700`固定为5折。C16/C32按以下字典序选择：

1. 五折均无NaN/Inf和发散；
2. 五折D5困难窗相对各折S0不退化超过3%；
3. 20步macro改善方向至少4/5折为正；
4. 选择五折平均`J20`更小者；
5. 若两者差异不足1%，选择L16；
6. 选定后冻结维数、训练步数、损失尺度和全部超参数，再训练5个full-train bootstrap模型。

validation只对这一唯一选定维数做P5主门。C16/C32可同时保存CV结果，但不得看validation后改选。

## 6. 顺序任务树

### S0：现场检查与不可变快照

**前置：** 用户明确授权执行；5080无其他训练；D/E盘各剩余至少40 GiB。

**工作：**

1. 核对hostname、Python 3.11.14、PyTorch/CUDA、进程和磁盘；
2. 计算父V2源码当前manifest和父run的P0—P3关键SHA；
3. 确认`koopman_predict_v3`不存在；存在时不得覆盖，核对它是否属于同一任务；
4. 复制V2源码到V3，不复制结果和模型；
5. 在V3创建`development_log.md`，登记复制前后manifest。

**通过门：** 父目录未改、复制文件逐项哈希一致、confirm读取0。

**失败：** 停止并写`koopman_predict_v3_results\solutions.md`，不得边复制边覆盖已有V3。

### S1：实现代码与单元测试，不训练

**工作：** 按第4节实现协议、模型、损失、数据集、评估和runner；先只用合成张量和2条train轨迹。

**硬门：**

- 所有V2原测试和V3新测试通过；
- `E=0`时S0的1/5/10/20步逐元素误差`<=1e-10`；
- `rho(F)<0.995`，块三角谱并集最大误差`<=1e-8`；
- 篡改未来状态不改变当前输入digest；
- 任意一个batch不跨轨迹、不跨family、不越界；
- A0/B0/b0的`requires_grad=False`且训练后SHA不变。

**允许小修：** 路径、导入、dtype、张量维度、JSON序列化、测试夹具；每个根因最多2轮。不得为通过测试修改科学公式。

### R0：最终源码冻结与P0闭环复现

S1通过后冻结V3源码manifest，再运行完整P0回归。必须重新得到：

- development S0 `J20=0.13023504180689485±1e-10`；
- N6主表最大相对误差`<=1e-9`；
- 3820个development窗口身份一致；
- 672个cache哈希一致；
- confirm读取0；
- 全部测试通过。

R0失败立即停止；不能在评估器身份不闭合时训练神经模型。

### P5A：单seed smoke和损失尺度冻结

**输入：** train的2个family，每类工况至少1条可用轨迹；seed `990100`。

**运行：** L16执行200个warm步骤和500个multi步骤，只检查实现，不判断科学收益。记录初始256窗的各loss中位数到本run的`p5a/loss_scale.json`，后续阶段snapshot登记该文件SHA；不修改已经冻结的协议，且正式训练开始后不再重标定。

**硬门：**

- loss、梯度、参数、预测全部有限；
- A0/B0/b0位级不变；
- `rho(F)<0.995`全过程满足；
- checkpoint恢复后的下一批loss相对误差`<=1e-6`；
- 训练吞吐和显存可记录；
- 未读取validation/development/confirm。

OOM时只允许降低micro-batch并梯度累积，使有效batch保持256个窗口；优化步数、seed、损失权重不变。

### P5B：train-family CV与结构冻结

依次运行A1、A2、C16、C32；AF先只运行中央seed，若10/20/40步任一发散立即终止AF，不影响主候选。

训练顺序固定：

1. 一步暖启动2000步，AdamW，学习率`1e-3`；
2. 多时域训练最多15000步，学习率`3e-4`；
3. 梯度全局范数裁剪1.0；
4. 每250步保存训练曲线，每1000步保存checkpoint；
5. 早停只看train-CV折，耐心2000步；
6. 用5折最佳步数的中位数作为full-train固定步数。

允许学习率仅使用预注册集合`{3e-4,1e-4}`；若`3e-4`在smoke出现非有限梯度，必须保存首个失败batch，经确认是优化数值问题后才可自动改用`1e-4`。不得因验证结果差再改学习率。

**P5B通过门：** 满足第5.3节全部train-CV规则。两个主候选都失败时停止，不扩大到64/96/128维。

### P5C：5-seed完整训练和validation一次性门禁

先冻结选中的L16或L32，再用96个train family训练5个bootstrap模型，一次性评价48个validation family。

主门：

| 指标 | 通过条件 |
|---|---|
| validation macro 20步 | 相对S0改善`>=5%`，即`J20<=0.1214455559537291` |
| 成对family CI | 2000次bootstrap的95%CI下界`>0` |
| seed方向 | 至少4/5个seed改善 |
| 1/5/10步 | 任一不比S0恶化超过3% |
| 发散 | 1/5/10/20步均为0 |
| D7/D10 | 至少一个20步改善`>=8%`；对应目标分别为`<=0.3067896`或`<=0.2891974`（最终由脚本保存全精度） |
| D5整体 | 不比S0恶化超过3%，即`J20<=0.12155500054436336` |
| D5起点100/120 | 均值/P95/最大值均不比S0恶化超过3%；约为`<=0.16980322 / 0.23965404 / 0.24011208` |
| 其余工况 | 使用`max(J_s^S0,0.02)`作分母，任一相对退化不超过3% |
| 四点力/内部力 | 任一20步macro不恶化超过5% |
| 部署时间 | 预热1000次后，单窗口20步GPU中位数`<1 ms`、P99`<2 ms`；CPU中位数`<5 ms` |

同时跑D5的40步压力滚动；允许误差增加，但不得出现NaN/Inf或相对S0新增发散。

**第一次实际停止点：** P5C完成后无论通过与否都人工停止，交付报告、CSV、图、模型SHA和失败解释。未经用户再次授权不进入P6。

### P6：R3物理一致损失

**前置：** P5C通过，且g3相对位移/速度20步误差相对S0确有改善。

1. 用真实`d/v`检查Torch R3Decoder与冻结plant/NumPy解码逐元素一致；
2. 在同一P5 checkpoint上比较`λphy=0/0.05/0.20`，只用train-CV选择；
3. 冻结选择后训练5个seed并一次评价validation；
4. 所有方法继续使用同一个解析读出，不增加力head。

**硬门：**

- float64 oracle force/internal最大相对误差`<=1e-8`；
- 四点力20步macro相对P5改善`>=10%`；
- 完整内部力20步macro相对P5改善`>=10%`；
- `J20_common`不恶化超过2%；
- core和yaw任一不恶化超过3%；
- `||W f_int||/(||f_int||+eps)<=1e-8`；
- D5与发散门继续满足。

若R3 oracle不一致立即停止；若物理损失未过预测门，删除“物理损失提高预测”的贡献，但保留解析读出，允许P7继续使用P5候选。

### P7：有限时域稳定性和稳定模块必要性

**前置：** 至少有一个P5预测候选通过。

必须报告：

1. `rho(A0)`、每个残差模态`r_j`、完整K数值谱；
2. 1/5/10/20/40/80步误差增长和latent范数；
3. D5 `t=1.6—3.0 s`的`Eη`修正量、P95/P99、左右方向和V1/R3植物；
4. 与B1在`window_start=80/100/120/140`的逐窗对比；
5. 非正规瞬态增益，而不是只画谱半径。

如果P5/P6候选20/40/80步均无新增发散，且P99不高于S0，则不再做IRSP，结论为“当前工作域不需要额外投影”。

只有出现有限时域尾部放大时，才允许在train-CV上试`E`整体缩放`α∈{0.75,0.50}`；A0/B0/F和其他参数不变。保留条件：消除新增发散、P99下降、20步macro代价不超过3%。不得投影或改写A0来制造稳定证书。

### P8：有限组合与完整消融

最终主表最多保留四个候选：

| 候选 | 组成 | 进入条件 |
|---|---|---|
| C0 | S0 | 永久基线 |
| C1 | P5最佳GDM-RK | P5C通过 |
| C2 | C1+R3物理损失 | P6通过 |
| C3 | C2或C1+必要稳定处理 | P7证明有必要且通过 |

B1、A1、A2、AF放入机制消融表，不进入最终候选。组合相对最佳单模块需要再改善至少3%；否则选择更简单模型。参数超过S0三倍而收益不足8%时，论文必须报告代价并优先简单候选。

### P9：development一次性评价

P8完成后冻结源码、协议、模型、seed、阈值、绘图脚本和论文主表，然后只读一次development。

最终创新进入门：

- `J20_common`相对S0改善`>=8%`；
- 95%CI下界`>0`，5个seed至少4个同向；
- D2/D4/D5/D6/D11至少一个改善`>=8%`；
- D7/D9/D10至少一个改善`>=10%`；
- 任一重要工况退化不超过3%，D5困难窗门继续满足；
- 四点力和完整内部力至少各改善8%；
- 1/5/10步不明显反向，发散率不增加；
- 参数和推理预算合格。

改善5%—8%且CI为正，只能写“中等改善”；低于5%或CI跨0不得生成confirm。

### P10：一次性盲confirm

只比较冻结S0和唯一冻结候选。confirm读取后不允许调整任何模型、阈值、归一化、后处理或图表筛选。主门沿用P9；若失败，停止“总体优于现有方法”的主张，不能回看confirm继续调参。

## 7. 运行命令

以下命令只在以后明确授权执行时使用。

### 7.1 环境与隔离

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$ParentSource = Join-Path $ProjectRoot 'revision_2026\koopman_predict_v2'
$SourceRoot = Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Taskbook = Join-Path $ProjectRoot 'revision_2026\koopman_p5.md'

hostname
Get-Process python,pythonw,matlab -ErrorAction SilentlyContinue
Get-PSDrive D,E | Select-Object Name,@{N='FreeGiB';E={[math]::Round($_.Free/1GB,2)}}
& $PythonExe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"

if (Test-Path -LiteralPath $SourceRoot) {
    throw "目标目录已存在，必须先核对身份，禁止覆盖：$SourceRoot"
}
Copy-Item -LiteralPath $ParentSource -Destination $SourceRoot -Recurse
```

### 7.2 测试和阶段运行

```powershell
$Protocol = Join-Path $SourceRoot 'config\protocol_v3.json'
$Runner = Join-Path $SourceRoot 'scripts\run_v3.py'

& $PythonExe -B -m pytest $SourceRoot -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "单元测试失败，停止" }

& $PythonExe -B $Runner --stage R0 --project-root $ProjectRoot `
  --protocol $Protocol --taskbook $Taskbook --run-tag GDM_RK_R0

& $PythonExe -B $Runner --stage P5A --project-root $ProjectRoot `
  --protocol $Protocol --taskbook $Taskbook --run-tag GDM_RK_P5 `
  --resume-run '<RUN_ID>'
```

runner必须逐阶段执行；任何硬门失败时返回非零退出码并生成`complete.json`和`solutions.md`。禁止使用一条命令绕过P5C人工停止。

### 7.3 允许的修正命令

仅限L1实现问题：

```powershell
# 修改后先跑定向测试，再跑全量测试
& $PythonExe -B -m pytest (Join-Path $SourceRoot 'tests\test_p5_gates.py') -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "门禁测试仍失败" }

& $PythonExe -B -m pytest $SourceRoot -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "回归测试失败" }

# 核对失败run，而不是新建同名run覆盖
Get-ChildItem (Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3_results\runs') `
  -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 3
```

OOM恢复只能在协议记录`micro_batch_new × accumulation_new = effective_batch_frozen`后使用同一run和checkpoint恢复；不得重新抽seed。

## 8. 自动判断、允许自修和必须停止

### 8.1 AI可自主处理

| 问题 | 允许动作 | 不允许动作 |
|---|---|---|
| Windows路径、导入、JSON/NumPy/PyTorch类型 | 单根因补丁、补测试、更新source SHA | 改指标、删工况 |
| OOM | 降micro-batch、等效梯度累积、从完整checkpoint恢复 | 减少有效batch、seed或训练步数 |
| CUDA非确定算子 | 换等价确定实现或仅将该算子放CPU | 全局关闭可复现要求且不记录 |
| 绘图乱码/漏单位 | 只重跑绘图报告 | 重算或筛选原始结果 |
| 日志短暂停止 | 查PID、GPU、checkpoint和文件增长 | 未确认前重复提交run |
| 学习率首轮数值爆炸 | 保存失败batch，确认纯优化问题后按预注册降至`1e-4` | 看validation后调学习率 |
| checkpoint损坏 | 从最近完整checkpoint恢复并登记SHA | 覆盖首个失败证据 |

每个阶段最多两轮L1修复。第三次同根因，或需要改变模型定义，停止并请求人工决策。

### 8.2 必须停止并写解决方案

- 父V2、N5 manifest、归一化或cache身份漂移；
- R0无法复现S0和N6评价；
- future leakage、split/family泄漏或窗口越界；
- A0/B0/b0在训练中改变；
- `rho(F)>=0.995`、块三角谱不成立或出现NaN/Inf；
- P5B两个维数都失败；
- P5C macro通过但D5、尾部、CI、seed或发散门失败；
- 需要扩大到64/96维、增加专家、恢复双线性或删除D5才能通过；
- Torch R3与冻结plant/NumPy读出不一致；
- P9失败后仍准备生成confirm；
- confirm失败后企图回看调参；
- 需要修改车辆、连接器、转向或数据生成器。

解决方案必须包含：首个失败checkpoint和batch、根因候选、支持/反对证据、最小诊断、修复代价、风险和重新进入门槛。科学硬门失败不能由“多跑几个seed”自动修复。

## 9. 必须生成的数据、表和图

### 9.1 原始数据表

1. `rows_{split}_{model}_{seed}.csv`：逐轨迹、family、工况、窗口、起点、时域的全部误差；
2. `scenario_summary.csv`：D0—D11均值、P95、P99、最大值；
3. `horizon_summary.csv`：1/5/10/20/40/80步误差和发散率；
4. `d5_transition.csv`：D5起点80/100/120/140，左右方向、V1/R3、5 seed；
5. `force_internal.csv`：四点Fx/Fy、完整8维内部力、`W f_int`残差；
6. `latent_modes.csv`：每个`r_j/omega_j`、latent范数、`Eη`修正量；
7. `paired_bootstrap.csv`：family成对改善和2000次bootstrap；
8. `fairness_ledger.csv`：数据、输入、seed、步数、参数、时间和信息接口。

### 9.2 主图

1. S0、B1、A1、A2、GDM-RK的1/5/10/20步误差增长；
2. D0—D11改善热图，并单独标出退化；
3. D5 1.6—3.0 s真实/预测、控制输入、`Eη`、latent范数和发散阈值；
4. D7/D10四点力及内部力真实—预测；
5. CVaR前后P95/P99和最坏family；
6. 阻尼模态`r_j/omega_j`与自由F消融；
7. 40/80步压力滚动与精度—稳定性Pareto；
8. 5 seed及family配对改善分布。

所有图带单位、时域、样本数、误差带、数据SHA和脚本SHA。失败曲线不得删除。

## 10. 论文行文与审稿意见对应

只有相应门通过后才能写：

1. **诊断：** 固定线性在长时传播稳定但遗漏输入—状态非线性；完整双线性在1—10步有效，却在持续回头弯早段产生递推放大；独立多专家在稳态有效但破坏切换和连接事件。
2. **方法：** 提出共享S0骨干的物理分组残差observable，以阻尼旋转模态表达连接/车辆衰减动态，用块三角传播避免新增残差特征值失稳，并用多时域与CVaR直接约束20步和最坏窗口。
3. **物理解释：** 连接支路由`g2/g3`驱动，四点力和完整内部力统一由R3解析读出，不使用不可解释的独立力head。
4. **证据：** 同一D0—D11、同一数据划分、5 seed、family配对CI、D5困难窗、40/80步压力滚动和一次confirm共同支撑。

如果只P5通过而P6失败，只能声明状态预测和长时稳定性改善，不能声明力预测创新。若P9/P10未过，只能写“系统比较定位了各类Koopman的优势域和退化机理”，不能写新方法总体优越。

## 11. 工作记录要求

每完成一个子任务立即追加：

```text
revision_2026\koopman_predict_v3\development_log.md
revision_2026\koopman_predict_v3_results\work_log.md
revision_2026\koopman_predict_v3_results\solutions.md
revision_2026\koopman_predict_v3_results\decision_log.jsonl
```

每条记录必须包含：时间、任务编号、授权模式、主机、父/当前SHA、读取、修改、完整命令、退出码、seed、运行时间、原始产物、关键指标、事实/推断、状态、停止原因和下一允许动作。计划中的任务必须标`NOT_RUN`，不能提前写成已完成。

## 12. 第一次执行交付

用户以后明确授权执行本文时，第一批只交付：

1. S0/S1/R0身份和回归报告；
2. P5A smoke和损失尺度；
3. P5B五折选择及消融；
4. P5C五seed validation结果；
5. D5困难窗、1/5/10/20/40步、力/内部力和稳定性图；
6. `work_log.md`、`solutions.md`、模型和全部SHA；
7. 明确的`PASS / PARTIAL / BLOCKED`裁决。

随后人工停止。只有P5C通过并经用户再次授权，才进入P6—P8；只有P9通过才允许读取confirm。

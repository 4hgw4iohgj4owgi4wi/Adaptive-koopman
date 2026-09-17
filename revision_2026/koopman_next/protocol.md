# 新连接器下 Koopman 创新开发执行书

> 文档状态：`PLAN_ONLY / NOT_RUN`  
> 编写日期：2026-08-29（Asia/Shanghai）  
> 目标主机：5080 / `DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 冻结植物：`revision_2026\connector_r3_4`  
> 本文候选内部代号：`RGE-PK`（relative-geometry, gated, event-aware, physics-decoded Koopman）  
> 重要：内部代号不是论文方法名；只有盲确认通过后才能冻结投稿名称。

## 0. 执行摘要与前提纠正

### 0.1 当前可确认的事实

| 项目 | 现场事实 | 证据与边界 |
|---|---:|---|
| 5080环境 | Python 3.11.14；PyTorch 2.12.0.dev+cu128；CUDA可用；RTX 5080 | 2026-08-29现场只读检查 |
| 正在运行的训练 | 无 | 现场进程表；本次没有启动实验 |
| 项目版本管理 | 项目根目录没有`.git` | 后续必须依靠逐文件SHA256，不得写“Git commit” |
| 植物状态 | `ready_for_next_koopman_development=true` | 只表示可以开发，不表示已有论文级预测模型 |
| 论文模型状态 | `ready_for_final_paper_model_claim=false` | 连接器完成不等于Koopman创新完成 |
| 植物选择 | 保留`V1-ES`与`R3-ES` | R3高频能量常下降，但P99力跳常上升；没有全局优势 |
| 最新数据 | 两种植物合计26条轨迹；每种植物13条 | 每种植物train/validation/test为10/1/2条 |
| 每种植物样本 | 3858行；train/validation/test为3564/98/196行 | 轨迹级划分，但验证和测试工况过窄 |
| 当前split内容 | validation只有`connector_diagonal_1`；test只有`connector_lateral/diagonal_2` | 100 m、单移线、回头弯和直弯过渡全部只在train，不能据现有test判断这些工况的泛化 |
| 当前受力覆盖 | R3最大单点力约1.025 kN；额定参考值12 kN | 只覆盖低载荷仿真域，不支持额定载荷附近结论 |
| 事件覆盖 | R3只有约4.80%的控制区间包含事件；平滑区占比约1.46% | 不足以直接训练可靠的事件专家 |
| 当前20步冒烟 | R3 fixed linear `0.171599`；bilinear `0.194942` | NRMSE口径；测试只有两条定向激励，不能泛化 |
| 当前回归病态性 | R3 fixed linear正则化条件数约`6.706e10`；bilinear在ridge=10时约`8.743e4` | bilinear只有3554个训练相邻对和585维回归特征；低ridge曾出现20步数量级爆炸 |
| 旧EPD结果 | 精确物理公式通过，但由预测绝对状态重建连接形变后，力和拉伸载荷误差显著放大 | 说明“公式正确”不等于“预测链有效” |
| 旧复杂模型结果 | raw/fixed linear通常最稳；双线性只在局部有信号；门控与组合曾因样本和因果选择失败 | 新路线必须逐模块验收，不能默认复杂模型获胜 |

### 0.2 必须纠正的逻辑跳跃

1. **连接器开发完成，不等于旧数据仍可用于最终训练。** 旧Koopman数据属于旧植物；当前26条新植物数据只能用于接口冒烟和初步诊断。
2. **R3不是唯一“更好植物”。** 当前选择结论是`R3-ES_VALID_NO_CLEAR_ADVANTAGE`，因此保留V1-ES/R3-ES成对数据。R3作为论文候选植物，V1作为力律可迁移性和归因对照。
3. **20步总体误差下降，不自动证明物理预测改善。** 必须分别检查相对几何、四点力、完整内部力、货物拉伸载荷代理、事件区间和最坏工况。
4. **门控权重不等于变量重要性。** 必须用组消融、Jacobian敏感度和反事实置换验证活跃变量集合。
5. **谱半径采样约束不等于连续输入证书。** 旧IRSP只能作为采样正则化基线；新稳定性声明必须给出输入盒上的诱导范数充分条件，或者明确降级为经验稳定性。
6. **连接力是仿真力，不是材料撕裂判据。** 全文使用“货物拉伸载荷代理”或“分离型内部载荷”，不得写“防止撕裂”或“安全”。

### 0.3 本路线的核心判断

旧EPD失败的主要结构性风险是：先预测四车和货物的绝对位置/航向，再由多个预测量相减，恢复毫米级连接形变；小的非共模误差经过锚臂、间隙边界和刚度/阻尼放大后，形成很大的力误差。

本路线不再把物理解码直接接在旧绝对状态预测器后面，而采用以下顺序：

1. 保留完整物理信息，但把学习坐标改成货物坐标系下的四车相对位姿、相对速度、四点锚点形变和相对锚点速度；
2. 使用完整状态加平滑三专家门控，不按工况删除变量；
3. 使用已验收R3本构由预测相对几何解码端点力；对控制区间平均力只允许小而有界的事件残差；
4. 双线性只作为低秩可选模块，先证明其局部作用区，再决定是否进入最终模型；
5. 稳定约束只作用于去掉全局位姿积分模态后的内部误差/相对状态子空间；
6. 所有模块按增量消融过门，最终模型是“通过模块的组合”，不是预先指定的全模块堆叠。

## 1. 目标、非目标与论文声明边界

### 1.1 主要目标

本执行书必须产生足以回答下列问题的证据：

1. 为什么固定线性、固定升维、可训练升维、双线性和门控模型在不同工况下表现不同；
2. 相对坐标是否解决旧EPD的锚点误差放大问题；
3. 三专家门控是否在直线、操纵和接触切换区间形成可解释分工，而非专家塌缩；
4. 双线性项是否只在强输入—状态耦合区间有效，或者在新植物上仍然没有必要；
5. 物理解码是否提高四点力和内部载荷的多步预测，同时保持作用反作用、方向和代数一致性；
6. 最终候选在1/5/10/20步，尤其20步预测上，能否稳定超过最强简单基线；
7. 约束算子是否降低长时滚动发散，并能形成不循环的、限定范围的数学结论；
8. 最终模型是否保留20 ms MPC接口所需的状态、控制、线性化/求导和约束侧通道。

### 1.2 非目标

本轮不得顺带声称：

- 已证明闭环MPC稳定、递归可行或控制更优；
- 已证明通信延迟、丢包或DoS保护有效；
- 已证明连接器或货物材料安全；
- 已覆盖10–15 m/s高速域；
- 已证明R3物理上普遍优于V1；
- 已证明神经门控或注意力权重就是因果变量重要性。

这些问题只有在Koopman盲确认通过后，另立控制和网络协议。

### 1.3 论文声明等级

| 等级 | 最低证据 | 允许措辞 |
|---|---|---|
| L0 接口 | 单元测试、保存/重载、有限滚动 | “实现并验证接口” |
| L1 机理 | train/validation消融、敏感度、事件分层 | “观察到作用机制” |
| L2 预测 | 独立development、多seed、成对CI、退化门 | “在开发集上改善” |
| L3 盲确认 | 冻结模型和阈值后一次性confirm通过 | “在所定义低速仿真域内改善” |
| L4 控制 | 新植物上重新适配并完成闭环强基线 | “改善闭环指标” |
| L5 实物 | 多体/HIL/硬件或实测力 | “具有工程实物支持” |

本执行书最多直接完成L3和MPC接口检查；L4/L5不在本轮授权内。

## 2. 冻结身份、证据账本与目录隔离

### 2.1 当前冻结输入

| 对象 | 路径 | SHA256 |
|---|---|---|
| R3力律 | `revision_2026\connector_r3_4\src\connector_r3.py` | `0BD16C4D...F310459` |
| 四车植物 | `revision_2026\connector_r3_4\src\four_vehicle_common.py` | `8DFEF4F4...500A7C3` |
| 事件积分器 | `revision_2026\connector_r3_4\src\event_substep.py` | `CB7A5BC8...5E139F3` |
| 现有Schema | `revision_2026\connector_r3_4\src\schema_r3.py` | `18E1F343...9307DDA` |
| 现有数据脚本 | `revision_2026\connector_r3_4\scripts\generate_data_flow.py` | `602E2249...6412D9` |
| 现有冒烟训练 | `revision_2026\connector_r3_4\scripts\train_smoke_flow.py` | `93459855...81F2DE` |
| 26条轨迹清单 | `...\20260828_154602_DATA_FULL_F23\trajectory_manifest.csv` | `6D9E0BCD...5BC4B39` |
| V1数据 | `dataset_v1_es.npz` | `35A7554E...CB63A8E` |
| R3数据 | `dataset_r3_es.npz` | `9F978763...FAD160B` |
| 最终连接器manifest | `...\20260828_214001_FINAL_F36\final\manifest.json` | `77A923D5...FECD4ED` |
| Koopman就绪合同 | `READY_FOR_KOOPMAN_TRAINING.json` | `432885D4...E7294E` |

执行K0时必须复算完整64位SHA256并写入新冻结清单。上表缩写仅用于阅读，不能作为机器校验值。

### 2.2 新目录

不得修改或覆盖`connector_r3_4*`、旧`revision_2026\koopman`、EFD、EPD和历史结果。新建：

```text
revision_2026/
├─ koopman_next/
│  ├─ protocol.md
│  ├─ config/
│  ├─ src/
│  ├─ scripts/
│  └─ tests/
├─ koopman_next_data/
│  ├─ pilot/
│  ├─ full/
│  └─ confirm/
├─ koopman_next_models/
├─ koopman_next_results/
└─ koopman_next_mpc/
```

每次运行目录必须是：

```text
YYYYMMDD_HHMMSS_<STAGE>_<RUN_ID>/
├─ resolved_config.json
├─ input_manifest.json
├─ stdout.txt
├─ stderr.txt
├─ metrics.*
├─ complete.json
└─ failure/                 # 只有失败时出现
```

### 2.3 不可变规则

- 5080项目无Git，K0必须建立源码树SHA256清单和只读副本；
- confirm数据在K11模型冻结前不得生成或读取；
- 任何窗口、镜像、左右转和同一参数族必须跟随`base_family_id`进入同一split；
- 不得把镜像轨迹计为独立随机样本；
- 不得根据development或confirm结果修改主要门槛；
- 失败产物不得删除或覆盖。

## 3. 数据、时序与因果合同

### 3.1 当前S4的真实含义

当前`S4_force_in`为64维：

```text
[0:30]   四车+货物绝对物理状态
[30:46]  四点世界坐标形变d和相对锚点速度v
[46:54]  已完成控制区间的货物体系平均连接力
[54:56]  已完成区间的Q_FR/Q_LR
[56:64]  已完成区间平均力的一阶差分
```

必须区分：端点力、区间平均力和冲量。新的Schema不得继续用一个`force`名称混写三者。

### 3.2 新样本时间合同

对从`k`到`k+1`的样本统一定义：

| 名称 | 时间 | 是否可作为输入 |
|---|---|---|
| `physical_state30_k` | `t_k` | 是 |
| `relative_state_k` | `t_k` | 是 |
| `force_endpoint8_k` | `t_k` | 是 |
| `force_mean8_prev` | `[t_{k-1},t_k]` | 是 |
| `event_counts16_prev` | `[t_{k-1},t_k]` | 是 |
| `contact_fraction4_prev` | `[t_{k-1},t_k]` | 是 |
| `u8_k` | 将施加于`[t_k,t_{k+1}]` | 是 |
| `delta_u8_k=u8_k-u8_{k-1}` | `t_k`可得 | 是 |
| `physical_state30_k1` | `t_{k+1}` | 仅标签 |
| `force_endpoint8_k1` | `t_{k+1}` | 仅标签 |
| `force_mean8_next` | `[t_k,t_{k+1}]` | 仅标签 |
| `event_counts16_next` | `[t_k,t_{k+1}]` | 仅标签/门控监督 |

必须新增“未来区间扰动测试”：只修改`k+1`之后的真值，验证`x_k/u_k/gate_input_k`逐字节不变。出现任何变化立即按数据泄漏停止。

### 3.3 相对坐标

车辆与货物平面状态记为：

\[
x_i=[p_i^w,\psi_i,v_i^b,r_i],\qquad
x_p=[p_p^w,\psi_p,v_p^b,r_p].
\]

其中`i=1,...,4`，`R(ψ)`为二维旋转矩阵，`J=[[0,-1],[1,0]]`。定义：

\[
v_i^w=R(\psi_i)v_i^b,\qquad v_p^w=R(\psi_p)v_p^b,
\]

\[
\rho_i=R(\psi_p)^T(p_i^w-p_p^w),
\]

\[
\Delta\psi_i=\operatorname{wrap}(\psi_i-\psi_p),\qquad
s_i=\sin\Delta\psi_i,\quad c_i=\cos\Delta\psi_i,
\]

\[
v_{rel,i}^{p}=R(\psi_p)^T(v_i^w-v_p^w),\qquad
\Delta r_i=r_i-r_p.
\]

若需要`ρ_i`在旋转货物坐标中的时间导数，必须使用：

\[
\dot\rho_i=R(\psi_p)^T(v_i^w-v_p^w)-r_pJ\rho_i.
\]

不能把`R_p^T(v_i^w-v_p^w)`错误命名为`dot_rho`。

四点锚点形变和本构使用的相对锚点速度定义为：

\[
d_i^p=R(\psi_p)^T(p_{a,i}^{v,w}-p_{a,i}^{p,w}),
\]

\[
v_{a,i}^{p}=R(\psi_p)^T(v_{a,i}^{v,w}-v_{a,i}^{p,w}).
\]

点积和长度在旋转下不变，因此R3本构可以直接在货物体系计算。

### 3.4 学习状态分组

完整信息保留，但分成可解释变量组：

| 组 | 内容 | 作用 |
|---|---|---|
| G0 全局运输 | 货物速度、横摆率；全局位置和航向只通过运动学积分更新 | 避免绝对位置主导回归 |
| G1 四车相对位姿 | `rho_i, sinΔψ_i, cosΔψ_i` | 阵列几何与转向 |
| G2 四车相对运动 | `v_rel_i^p, Δr_i` | 相对动力学 |
| G3 连接几何 | `d_i^p, v_a_i^p` | 毫米级力律输入 |
| G4 力历史 | 端点力、上一控制区间平均力、力率 | 接触记忆与事件前兆 |
| G5 事件历史 | 当前活动mask、上一控制区间事件/接触/平滑统计 | 只使用已完成区间 |
| G6 控制上下文 | `u_k, Δu_k`、由当前四车转角构造的曲率代理 | 强输入—状态耦合 |

全局位置与航向由预测速度按梯形运动学恢复：

\[
\hat\psi_{p,k+1}=\psi_{p,k}+\frac{T}{2}(r_{p,k}+\hat r_{p,k+1}),
\]

\[
\hat p_{p,k+1}=p_{p,k}+\frac{T}{2}
\left(R(\psi_{p,k})v_{p,k}^b+R(\hat\psi_{p,k+1})\hat v_{p,k+1}^b\right).
\]

四车绝对位姿由货物位姿和相对位姿重构。必须验证变换—逆变换float64最大绝对误差不超过`1e-10`，float32不超过`1e-5`。

### 3.5 参数与网络变量

- 主模型不得读取只有仿真器知道、实车不可获得的随机真参数；
- `payload_mass/k/c/free_play/mu`作为`PARAM_KNOWN`上界消融时必须单独标记；
- 主模型`PARAM_HIDDEN`只使用可测状态、控制和历史事件；
- `network_mask/AoI`本轮保留Schema接口，但不得混入清洁物理训练或被写成网络实验。

## 4. 模型族、公式与模块归因

### 4.1 公平基线

| ID | 模型 | 作用 |
|---|---|---|
| B0 | persistence | 检查模型是否至少超过保持不变 |
| B1 | raw linear DMDc，基于当前S4 | 当前最简单公平基线 |
| B2 | fixed analytic lift EDMDc | 检查固定物理/多项式升维是否帮助曲线和回头弯 |
| B3 | full bilinear | 检查完整`u_j*x`耦合；必须报告秩、条件数和发散率 |
| B4 | structured/low-rank bilinear | 降低B3样本需求，验证输入—状态耦合是否局部有效 |
| B5 | trainable identity lift | 检查可训练升维；保持原状态恒等通道 |
| B6 | sampled-IRSP baseline | 复现旧思想，但明确只是在冻结采样控制集上约束谱半径 |

旧31维/2输入论文模型与新64维/8输入植物不兼容，只能作为`HISTORICAL_ARTICLE_MODEL`。B6是同原则的新接口适配，不得声称为原模型直接公平复跑。

### 4.2 候选模块

| ID | 模块 | 必须回答的问题 |
|---|---|---|
| C1-R | 相对坐标固定线性 | 仅改变表示，是否已经解决绝对差分放大 |
| C2-RL | 相对坐标+恒等可训练lift | 非线性升维是否在新表示上有净收益 |
| C3-RG | C2+三专家平滑门控+变量组权重 | 不同工况的活跃子空间是否可辨识 |
| C4-RGB | C3+每专家低秩双线性 | 双线性是否只在强操纵/切换区有效 |
| C5-RGP | C3或C4+R3物理解码与事件区间力头 | 四点力、内部力和拉伸载荷是否改善且一致 |
| C6-RGPS | C5+内部子空间范数约束 | 是否降低长时发散且不破坏20步精度 |

只有增量模块通过门才保留。例如C4失败时，C5从C3继续，不得为了形成“全功能方法”强留双线性。

### 4.3 恒等升维

对归一化相对状态`ξ_k`定义：

\[
\eta_k=\Psi_\theta(\xi_k)=
\begin{bmatrix}\xi_k\\\phi_\theta(\xi_k)\end{bmatrix}.
\]

恒等部分不得被神经网络替代。解码器直接读取恒等通道，附加lift只补充非线性观测量。初始化时令附加通道小幅输出，避免第一轮递推爆炸。

固定lift B2至少包含：角度正余弦、速度二次项、`v*r`耦合、连接间隙正部、法向速度、四点力范数和前后/左右成对载荷；特征表必须预先冻结，禁止根据测试表现临时加特征。

### 4.4 三专家平滑门控

专家内部候选解释为：

1. E0：平稳/低激励区间；
2. E1：持续操纵但无接触切换的区间；
3. E2：转向切换、接触/平滑边界和强相对运动区间。

门控只使用当前可得变量：

\[
\rho_k=[v_{p,k},r_{p,k},u_k,\Delta u_k,
\operatorname{gap}_k,v_{n,k},a_k,
e_{k-1},c_{k-1},s_{k-1}],
\]

\[
\alpha_k=\operatorname{softmax}(g_\theta(\rho_k)/\tau),qquad
\alpha_{m,k}\ge0,\quad\sum_m\alpha_{m,k}=1.
\]

`event_counts_next`只能作为事件头监督标签，不能进入`ρ_k`。

每个专家使用变量组权重`h_{m,g}∈[0,1]`，但完整状态仍保留：

\[
\tilde\xi_{m,k}=\operatorname{concat}_g(h_{m,g}\xi_k^{(g)}).
\]

权重只用于调节作用强度，不执行硬删除。解释必须由以下三项共同支持：

- `h_{m,g}`；
- `∂x_hat/∂x_g`的Jacobian敏感度；
- 变量组置换/屏蔽后的性能变化。

### 4.5 专家Koopman与低秩双线性

第`m`个专家为：

\[
\eta_{k+1}^{(m)}=
A_m\eta_k+B_m\bar u_k+c_m+
\sum_{j=1}^{8}\bar u_{k,j}N_{m,j}\eta_k,
\]

\[
\hat\eta_{k+1}=\sum_{m=1}^{3}\alpha_{m,k}\eta_{k+1}^{(m)}.
\]

其中`u_bar`由训练集统计归一化。C3令`N=0`；C4使用：

\[
N_{m,j}=U_{m,j}V_{m,j}^{T},\qquad \operatorname{rank}(N_{m,j})=r_b,
\]

`r_b`只从预注册集合`{1,2,4}`中用validation选择。必须报告双线性贡献：

\[
r_{bil}(k)=\frac{\left\|\sum_j\bar u_{k,j}N_j\eta_k\right\|_2}
{\|A\eta_k+B\bar u_k+c\|_2+\epsilon}.
\]

还要做完整、置零`N`和轨迹内打乱`u-x`配对三组消融。`r_bil`非零只能证明模型使用了双线性项，不能证明它更好。

### 4.6 R3端点力物理解码

对预测的`d_i^p,v_{a,i}^p`：

\[
\ell_i=\|d_i^p\|,\quad
n_i^p=\frac{d_i^p}{\max(\ell_i,\epsilon)},\quad
\Delta_i=[\ell_i-\ell_0]_+,
\]

\[
s_i=\operatorname{clip}(\Delta_i/\delta_s,0,1),\qquad
g_i=3s_i^2-2s_i^3,
\]

\[
v_{n,i}=v_{a,i}^{pT}n_i^p,
\]

\[
T_i=k\Delta_i+c g_i[v_{n,i}]_+,qquad
F_{i,end}^{p}=T_i n_i^p.
\]

冻结参数为`k=30000 N/m`、`c=3500 N·s/m`、`ell0=0.002 m`、`delta_s=0.0001776170305060031 m`。额定/极限值仅是未实测的数值参考边界。

端点力由本构直接给出，不训练一个自由8维力头取代它。区间平均力不能由单个端点精确决定，因此使用两端梯形基线和事件残差：

当前数据把世界系区间冲量除以区间长度后，再旋转到区间末端的货物坐标系。因此两端力不能在各自货物坐标系中直接相加。梯形基线必须先对齐到`k+1`货物坐标系：

\[
\bar F_{i,k+1}^{base,p_{k+1}}
=\frac12\left[
R(\hat\psi_{p,k+1})^TR(\psi_{p,k})F_{i,end,k}^{p_k}
+\hat F_{i,end,k+1}^{p_{k+1}}
\right].
\]

\[
\hat{\bar F}_{i,k+1}^{p_{k+1}}=\bar F_{i,k+1}^{base,p_{k+1}}
+\alpha_{E2,k}\,R_{i,k}^{event}.
\]

事件残差必须有界，并记录：

\[
r_F=\frac{\|R^{event}\|_2}
{\|\bar F^{base}\|_2+F_{scale}}.
\]

如果残差在大部分样本中主导输出，则不能将C5描述为“物理解码模型”；应降级为“物理基线加学习残差”，或停止该模块。

由预测四点平均力计算：

\[
w=Wf,\qquad f_{int}=(I-W^\dagger W)f,
\]

并验证`||W f_int||`、Q代数残差、方向和镜像一致性。车辆侧反力由`-F`构造只能证明模型内部作用反作用一致，不能冒充独立传感器验证。

### 4.7 训练损失

每个时域`h∈{1,5,10,20}`使用组归一化Huber损失：

\[
L_h=0.25L_{state30}+0.25L_{relative}
+0.30L_{force}+0.10L_{internal}+0.10L_{tension}.
\]

总多步损失：

\[
L_{roll}=0.15L_1+0.20L_5+0.25L_{10}+0.40L_{20}.
\]

物理项：

\[
L=L_{roll}+\lambda_gL_{geometry}+\lambda_FL_{force-law}
+\lambda_qL_Q+\lambda_{int}L_{null}
+\lambda_{sym}L_{mirror}+\lambda_cL_{circle}
+\lambda_eL_{event}+\lambda_{bal}L_{gate}.
\]

权重只从预注册小集合选择，并在validation冻结。训练必须采用课程：一步预训练→5/10步→20步；若加入20步后一步误差恶化超过5%或出现发散，回退到上一合法checkpoint并记录失败。

### 4.8 稳定约束与可声明范围

全局位置和航向含运动学积分模态，不能要求整个状态严格收缩。只对归一化内部相对/形变lift状态`eta_int`约束。

令归一化输入满足`|u_bar_j|<=1`，专家内部算子：

\[
A_m(\bar u)=A_m+\sum_j\bar u_jN_{m,j}.
\]

一个可验证的保守充分条件是：

\[
\|A_m\|_P+\sum_{j=1}^{8}\|N_{m,j}\|_P\le q<1,
\qquad \forall m,
\]

其中：

\[
\|M\|_P=\|P^{1/2}MP^{-1/2}\|_2.
\]

因为门控权重属于单纯形，对任意门控和输入盒有：

\[
\left\|\sum_m\alpha_m A_m(\bar u)\right\|_P\le q.
\]

若非齐次项和模型残差满足`||d_k||_P<=d_bar`，则：

\[
\|\eta_{int,k+h}\|_P
\le q^h\|\eta_{int,k}\|_P
+\frac{1-q^h}{1-q}\bar d.
\]

这只能称为**冻结输入盒内学习内部状态的有界性充分条件**。它不是闭环ISS/UUB证明，也不自动证明真实植物误差有界。若无法在不显著损失精度的情况下满足该条件，则保留无约束候选，论文只报告经验发散率和采样IRSP对照，不制造证书。

## 5. 假设与可证伪预测

| 假设 | 可证伪预测 | 失败后的解释 |
|---|---|---|
| H1 相对表示有效 | C1相对B1在20步相对几何和四点力至少改善8%，state30不恶化超过3% | 若失败，旧EPD问题不只是坐标表示，需查目标时序/事件不可预测性 |
| H2 可训练lift有效 | C2相对C1的20步复合指标改善至少5%，五seed中至少4个方向一致 | 若训练损失下降而rollout恶化，说明lift漂移/递推不稳，不保留 |
| H3 门控有效 | C3在事件/转向切换层至少改善8%，且专家不塌缩、因果gate优于常数gate | 若失败，工况不可由当前因果特征提前辨识，回退共享算子 |
| H4 双线性局部有效 | C4在加减速、阶跃切换或定向激励至少一类改善8%，总体无显著退化 | 若仅贡献非零但误差变差，作为负消融，不进入最终组合 |
| H5 物理解码有效 | C5端点力/平均力/内部力20步至少改善10%，物理残差下降且core不恶化超过3% | 若d/v改善但力不改善，查区间平均目标与事件残差；若d/v本身差，停止C5 |
| H6 稳定约束有效 | C6 50/100步发散率下降，20步复合指标恶化不超过3% | 若精度代价过大，只保留经验稳定候选，不作证书主张 |
| H7 架构可迁移 | 同一模块选择在V1/R3独立训练中方向一致，或明确给出植物相关差异 | 若只在一植物有效，只声明植物特定，不写普适增强 |

所有百分比是预注册研究判据，不是物理安全阈值。

## 6. 代码修改表

连接器目录保持只读。所有实现写入`revision_2026\koopman_next`。

| 文件 | 类/函数 | 修改/新增 | 输入 | 输出 | 必须测试 |
|---|---|---|---|---|---|
| `config/protocol.json` | — | 固定split、seed块、门槛、模型矩阵、预算 | 人工冻结配置 | 完整协议 | JSON schema、hash |
| `src/contracts.py` | `RunContract` | 检查上游SHA、前序门、目录不可覆盖 | manifest/config | gate结果 | 漂移/缺失/重复运行故障注入 |
| `src/causal_schema.py` | `build_schema_v3()` | 明确端点、前一区间、下一区间标签 | 字段注册表 | schema.json | 维度、单位、时间戳、未来泄漏 |
| `src/relative_coordinates.py` | `encode_relative()`、`decode_absolute()` | 完整坐标变换和逆变换 | state30、参数 | relative state/state30 | 平移、旋转、镜像、round-trip |
| `src/force_decoder.py` | `decode_r3_endpoint()`、`interval_force_head()` | 精确R3端点力和有界事件残差 | d/v/事件概率 | endpoint/mean force | 与冻结plant oracle逐点一致 |
| `src/data_adapter.py` | `build_sample()` | 传入真实`ModelParams`，不再内部默认实例化 | 原始轨迹 | 因果样本 | 参数随机化后重算一致 |
| `src/scenarios.py` | 场景注册表 | 左右镜像、加减速、阶跃、事件激励、混合场景 | seed/参数 | 控制序列 | ICR、镜像、限幅 |
| `src/data_manifest.py` | `canonical_params()`、`assign_split()`、`validate_manifest()` | 参数规范化哈希、base family级划分、重放身份 | 参数/seed/场景 | manifest行与审计 | 参数哈希、禁止窗口泄漏、NaN拒绝 |
| `src/dataset.py` | `TrajectoryDataset` | 按base family划分，生成不重叠窗口 | npz/manifest | batch | 无窗口泄漏、归一化仅train |
| `src/fixed_lift.py` | `FixedLift` | B2冻结解析特征 | state/context | lifted state | 特征顺序、有限性 |
| `src/trainable_lift.py` | `IdentityLift` | 恒等通道+MLP | relative state | eta | identity精确保留、重载一致 |
| `src/operators.py` | `LinearOperator`、`LowRankBilinearExpert` | B1/B3/B4/C模型 | eta/u | eta_next | shape、零双线性退化等价 |
| `src/gating.py` | `CausalThreeExpertGate` | 因果门控、变量组权重、事件头 | rho_k | alpha/event prob | 禁止future字段、占用和梯度 |
| `src/stability.py` | `project_internal_norm()`、`audit_box_bound()` | 内部子空间范数投影和连续输入盒审计 | A/N/scale | q、certificate | 与SVD复算、随机盒抽查 |
| `src/losses.py` | `grouped_rollout_loss()` | 多时域、物理和事件损失 | rollout | scalar/components | 每项单位和mask |
| `src/rollout.py` | `rollout_controls()` | 使用同一未来控制序列滚动 | x_k,u[k:k+h] | predictions | h=1/5/10/20、轨迹边界 |
| `src/metrics.py` | `trajectory_metrics()` | macro/P95/P99/worst/方向/事件/物理残差 | 预测真值 | parquet/csv | 手算小例、macro不被长轨迹支配 |
| `src/statistics.py` | `paired_bootstrap()`、`holm()` | 轨迹级成对统计 | 逐轨迹指标 | CI/p值 | 固定seed、配对身份 |
| `src/mpc_adapter.py` | `predict()`、`linearize()` | 20 ms接口和自动微分Jacobian | state/u | A/B/c/side channels | 有限差分交叉检查 |
| `scripts/freeze.py` | K0 | 环境、进程、磁盘、SHA、seed碰撞 | 项目根 | freeze | 完整性复核 |
| `scripts/generate_data.py` | K1–K3 | 调用冻结植物生成成对数据 | protocol | raw/combined | replay、参数、事件、单位 |
| `scripts/run_k2.py` | K2 | 生成pilot、逐轨迹合同审计、覆盖与资源外推 | protocol/K1状态 | `k2/*` | 部分20 ms区间、重放、split故障注入 |
| `scripts/audit_coverage.py` | K2/K3 | 工况、事件、受力、方向和秩覆盖 | dataset | coverage.json | 不重叠窗计数 |
| `scripts/train.py` | K4–K10 | 统一预算训练和早停 | model config | checkpoint/log | 确定性、恢复、OOM |
| `scripts/evaluate.py` | K4–K11 | 分层多步评价 | frozen model | metrics | test只读一次规则 |
| `scripts/confirm.py` | K12 | 一次性盲确认 | frozen selection | confirm结果 | 锁文件防二次选择 |
| `scripts/plot.py` | K14 | 由CSV/NPZ生成论文图 | raw metrics | PNG/PDF | 图数据hash、单位 |
| `scripts/run.py` | 全阶段 | 阶段调度、硬门和留痕 | `--stage` | complete/failure | 前序失败时拒绝运行 |
| `tests/test_k2_data_contracts.py` | K2合同测试 | 100 m完整控制区间、参数身份、base family划分、覆盖计数 | 合成小数据 | pytest结果 | 所有修正各有失败注入 |

## 7. 数据设计

### 7.1 工况族

| 族 | 内容 | 主要激活变量 |
|---|---|---|
| D0 | 直线匀速 | 全局速度；连接变量应低敏感 |
| D1 | 直线加速—匀速—制动 | 纵向力、前后内部载荷 |
| D2 | 100 m正反阶跃转向 | 转向切换、横摆、四点Fy、事件 |
| D3 | 左/右稳态弯 | 曲率、横摆、持续横向载荷 |
| D4 | 左/右单移线 | 过渡横向动力学 |
| D5 | 左/右回头弯 | 强持续转弯和lift优势区 |
| D6 | 直线入弯/弯道出直线，左右成对 | 活跃子空间切换 |
| D7 | 纵向连接定向激励 | 前后内力、双线性加速度耦合 |
| D8 | 横向连接定向激励 | 左右内力和方向判断 |
| D9 | 两种对角连接激励 | 完整内部力零空间 |
| D10 | 边界往复/chirp激励 | 接触、平滑区和短驻留事件 |
| D11 | 混合操纵 | 非单一工况泛化 |

### 7.2 数量与split

每个`base_family`同时生成V1-ES/R3-ES，使用相同初态、控制、参数和seed。左右镜像和同一参数族绑定在同一split。

| split | 每工况基础seed数 | 用途 |
|---|---:|---|
| train | 6 | 拟合和归一化 |
| validation | 2 | 超参数与早停 |
| development | 2 | 一次性模块选择和组合冻结 |
| confirm | 3 | K11之后才生成的一次性盲确认 |

每个seed可产生一条双向组合轨迹或一个左右镜像对；统计时镜像对按一个`base_family`计。若按当前场景成员展开，预计每植物约200–300条轨迹。最终进入下一阶段的依据不是文件数量，而是以下不重叠20步窗覆盖：

- train：每个门控区间至少2000窗；
- validation：每个门控区间至少400窗；
- development：每个门控区间至少400窗；
- confirm：每个门控区间至少400窗；
- 每个主要工况每个非train split至少10个独立base family；
- 左/右方向计数差不超过20%；
- 事件区间不能只来自定向激励，至少三个自然操纵工况含事件。

覆盖不足时只允许增加缺失工况的新base family，不得复制窗口或移动既有轨迹。

### 7.3 初始研究包线

以下是仿真研究包线，不是实物参数认证：

- 初速：1.5–5.0 m/s；
- 加速度命令：约`-0.6`至`+0.4 m/s²`；
- 虚拟转向幅值：5°、8°、12°三级，单车最终转角仍受15°限幅；
- payload mass scale：0.85–1.15；
- `k/c/free_play` scale：0.90–1.10；
- `mu`：0.75–0.95；
- 所有主数据要求无NaN/Inf、无极限力触发、轮胎原始利用率不超过0.9、共同ICR残差通过现有合同。

参数变化必须通过`ModelParams`显式传入仿真和样本构造；禁止仿真用随机参数、Schema重算却偷偷用默认参数。

6–8 m/s、低附着、连接点失效和10–15 m/s只作为后续OOD任务。低速主域未通过前不得启动。

### 7.4 自然集与事件挑战集

- 自然集保持各工况真实时间占比，用于总体声明；
- 事件挑战集增加接触/平滑边界暴露，用于验证C3/C5机理；
- 训练可以分层采样，但评价必须分别报告自然分布和挑战分布；
- 不得用大量事件过采样后的平均结果冒充自然工况改善。

## 8. 公平训练与评价矩阵

### 8.1 统一条件

所有模型统一：

- 相同轨迹和split；
- 相同可见输入；如果模型使用额外事件历史，必须提供相应公平消融；
- 相同未来控制序列；
- 相同归一化统计，仅由train计算；
- 五个模型初始化seed；确定性闭式模型记录一次并在统计中按同一预测配对；
- 相同最大epoch、有效梯度步预算和早停耐心；
- validation选择一次，development只用于模块组合冻结，confirm只评一次；
- 同时报告参数量、GPU训练时间、20步推理P50/P95/P99和显存峰值。

### 8.2 主要指标

至少报告：

1. `h=1/5/10/20`：state30、相对位姿、d、v、端点力、区间平均力、完整内部力、`T_x/T_y` NRMSE；
2. 每个工况均值、轨迹macro、P95、P99和最坏轨迹；
3. 连接力方向准确率和小力死区外宏平均F1；
4. 接触/平滑事件PR-AUC、Brier、ECE和事件时刻误差；
5. `W f_int`、Q代数、几何双路径、单位圆、镜像/旋转残差；
6. 20/50/100步非有限率和归一化幅值超限率；
7. 轨迹级成对bootstrap 95% CI、效应量和Holm校正；
8. 门控占用、切换总变差、专家互换/常数门控消融；
9. 双线性贡献和置零/打乱消融；
10. 物理残差贡献比`r_F`。

### 8.3 复合指标

主指标：

\[
J_{20}=0.25E_{state30}+0.25E_{relative}
+0.30E_{force}+0.10E_{internal}+0.10E_{tension}.
\]

各`E`先按train尺度归一化，再按轨迹macro，避免长100 m轨迹支配定向短轨迹。

### 8.4 声明“有改进”的硬门

最终模型相对**最强合法简单基线**必须同时满足：

1. confirm轨迹macro `J20`改善至少8%；
2. 成对bootstrap 95% CI的改善下界大于0；
3. 四点力20步误差改善至少10%；
4. 相对几何20步误差改善至少8%；
5. state30、内部力和拉伸载荷任何一项不得恶化超过3%；
6. 12个工况中至少8个不劣于3%，且至少3个改善超过8%；
7. 回头弯、正反阶跃和事件挑战集任何一个不得恶化超过10%；
8. 非有限/发散率不高于基线；
9. 20步推理P99小于20 ms；
10. 所有因果、物理和重载检查通过。

若只在某一工况通过，则允许声明该工况优势，不得声明整体方法更优。

## 9. 顺序任务树

### K0 — 冻结和身份审计

- 前置：无；当前第一执行点。
- 动作：创建新目录；记录主机、Python、CUDA、GPU、磁盘、进程；复算上游SHA；扫描seed碰撞；复制只读协议快照。
- 输出：`freeze/environment.json`、`freeze/source_hashes.json`、`freeze/seed_audit.json`、`freeze/complete.json`。
- 硬门：主机正确；所有上游hash一致；无无法解释的训练进程；D盘预计空间充足；seed块无碰撞。
- 失败：立即停止，写`solutions.md`；不得创建数据或模型。

### K1 — 因果Schema与坐标合同

- 前置：K0 PASS。
- 修改：`causal_schema.py`、`relative_coordinates.py`、`data_adapter.py`及测试。
- 输入：冻结26条数据，仅用于接口测试，不用于模型选择。
- 测试：round-trip、平移/旋转/镜像、单位/时间索引、参数透传、未来扰动不影响当前输入。
- 硬门：float64 round-trip≤`1e-10`；未来泄漏0；作用反作用/力矩/Q接口不漂移。
- 失败：定位为坐标、时间或参数合同问题；后续全停。

### K2 — 小规模数据pilot与覆盖诊断

- 前置：K1 PASS。
- 数据：先选D0/D1/D2/D5/D6/D10，train 2个base seed、validation 1个base seed，双植物成对。
- 输出：raw、combined、manifest、coverage、replay、资源外推。
- 硬门：全部轨迹有限；左右镜像和ICR通过；重放hash一致；事件三个区间均有样本；Schema无常量/错误尺度；预计全量不超过50 GiB且单阶段预计运行不超过24 h。
- 覆盖不足：只新增定向缺失激励；不得启动模型训练。
- 失败：保存最小失败轨迹和控制序列，写解决方案后停。

### K3 — 正式train/validation/development数据

- 前置：K2 PASS，且覆盖配置冻结。
- 数据：按第7节生成；confirm不生成。
- 硬门：不重叠窗和工况覆盖全部通过；split/base family/hash唯一；参数和单位复算；自然/事件集分开；无极限力触发；轮胎利用率门通过。
- 输出：`data_manifest.csv`、`split.json`、`normalization_train.npz`、`coverage.json`、`complete.json`。
- 失败：不得通过窗口复制补数；仅允许新seed定向补缺并生成新版本数据目录。

### K4 — 基线复现

- 前置：K3 PASS。
- 模型：B0–B6；先R3，再V1相同配置。
- 选择：ridge/lift/IRSP参数只用validation。
- 硬门：保存/重载误差≤`1e-12`；一步优于persistence；20步有限；报告秩、条件数、发散和成本。
- 输出：`baseline_registry.json`和逐模型结果。
- 决策：确定“最强合法简单基线”；后续增益均相对此基线，不得只挑弱基线。

### K5 — C1相对坐标最小因子

- 前置：K4 PASS。
- 唯一改动：表示从S4绝对状态改为相对状态；模型仍为固定线性。
- 硬门：H1通过才进入K6。
- 若只改善d/F、不改善state30：允许进入K6，但论文定位为受力预测专用；记录边界。
- 若relative/d/F均失败：停止创新主线，优先审计时序、归一化和相对速度定义。

### K6 — C2恒等可训练lift

- 前置：K5至少在目标量有正信号。
- 训练：五seed，一步预训练后多步课程；hidden/lift维度只从冻结集合选择。
- 硬门：H2通过；五seed至少4个方向一致；无新增发散。
- 失败：保留C1作为骨干；不得继续用更大网络硬压validation。

### K7 — C3三专家门控与活跃子空间

- 前置：选择K5或K6最强合法骨干；门控三类窗覆盖通过。
- 训练顺序：先固定专家训练事件分类头→联合训练门控→最后小学习率联合微调。
- 检查：每专家占用建议5%–90%；无单一专家长期>95%；常数gate、oracle label gate、打乱gate特征、专家互换四组消融。
- 解释：变量组权重、Jacobian和组消融三证合一。
- 硬门：H3通过；事件PR-AUC显著高于事件基率；常数gate不能解释全部收益。
- 失败：回退共享骨干；若oracle gate明显有效而因果gate失败，根因是可辨识性/特征不足，不是专家无互补性。

### K8 — C4低秩双线性

- 前置：K7合法；也可在共享骨干上独立运行以隔离门控交互。
- rank：1/2/4 validation选择；五seed。
- 硬门：H4通过；条件数/算子范数可控；置零和打乱消融证明正确配对有用；总体无显著退化。
- 失败：记录“新相对/门控骨干上双线性仍非必要”；C5从C3继续。

### K9 — C5物理解码和事件区间力

- 前置：K5/K7/K8中至少有一个骨干的d/v 20步相对基线改善；否则禁止训练力残差。
- 先做oracle：用真实d/v解码端点力必须与植物一致；再用预测d/v；最后才加事件残差。
- 硬门：H5通过；Q/内部力/方向/镜像通过；残差贡献未主导大多数样本。
- 失败分流：
  - 真实d/v解码失败→公式、坐标或端点/区间混淆，立即停止；
  - 真实通过、预测失败→d/v骨干不足，回K5–K7；
  - 端点通过、区间平均失败→改进事件/积分区间头，不改plant；
  - 残差主导→取消“物理解码”强措辞。

### K10 — C6内部稳定约束

- 前置：K9合法候选。
- q候选：`{0.97,0.99,0.995}`，只用validation；报告连续输入盒诱导范数充分界与采样谱半径B6对照。
- 硬门：H6通过；20步恶化≤3%；50/100步发散下降；完整SVD复算与训练代码一致。
- 失败：保留无约束C5；删除证书贡献，不得把采样IRSP改写成连续域保证。

### K11 — development一次性模块选择

- 前置：K4–K10每个模块都有明确PASS/FAIL。
- 候选：只允许由已通过模块组成，不超过三个最终候选加最强简单基线。
- development只读一次；做五seed、场景、事件和成本联合门。
- 通过：冻结唯一主候选、唯一回退模型、模型hash、阈值和论文预期表头。
- 失败：不生成confirm；总结哪些模块有局部效用，允许论文转为方法适用域比较。

### K12 — 盲confirm

- 前置：K11 PASS且锁文件确认模型/阈值不可变。
- 动作：生成全新seed块confirm数据；一次性评估，不重训、不调阈值。
- 硬门：第8.4节全部通过。
- 失败：保留confirm；不得再回调同一confirm。新的结构只能另立协议和全新development/confirm。

### K13 — MPC接口与控制前置检查

- 前置：K12存在合法候选；不等于授权运行闭环。
- 检查：20 ms推理；64维兼容层或新相对状态适配层；自动微分/有限差分A/B/c；力、内部力和拉伸载荷侧通道；约束梯度有限。
- 输出：`mpc_interface.json`，状态只能为`INTERFACE_VERIFIED_NOT_CLOSED_LOOP_VALIDATED`。
- 若候选不适合局部线性化：提供SQP/非线性MPC适配建议，但不自动改控制器。

### K14 — 论文证据包

- 前置：K12完成，无论PASS/FAIL。
- 生成：主表、工况热图、多时域曲线、门控占用、变量敏感度、双线性消融、物理一致性、发散/成本、失败工况和claim-evidence矩阵。
- 每张图同时保存CSV/NPZ、meta、脚本和hash。
- 最终报告逐条说明可回答、部分回答和未回答的审稿意见。

## 10. 问题处理与停止方案

| 问题 | 最小诊断 | 允许修复 | 必须停止的情况 |
|---|---|---|---|
| 上游hash漂移 | 与F36 manifest逐文件比较 | 若是已知新版本，另立植物版本并重做K0 | 无法解释漂移 |
| control/state错一拍 | 单脉冲控制+人工三步序列 | 修正索引并重建全部数据 | 已训练模型混用了两种时序 |
| 参数随机化未透传 | 同状态两组k/c/mass手算d/v/F | `build_sample`显式接收params | raw与样本参数身份不明 |
| 左右镜像泄漏 | base_family与split交叉表 | 同族重新分组并重建split | validation/test已用于调参且无法隔离 |
| 事件样本不足 | 不重叠20步窗计数 | 新增D10及自然事件seed | 只能靠复制窗口满足门 |
| gate塌缩 | 占用、熵、oracle gate差距 | 先调采样/温度/负载均衡；不先扩大网络 | 三次最小修复仍>95%单专家且无收益 |
| gate表现好但使用未来信息 | 特征时间标签审计、未来扰动测试 | 删除未来字段、整批重训 | 无法证明因果时序 |
| 绝对位置主导误差 | 分组loss和尺度贡献 | 使用相对状态、增量位置和组归一化 | 复合指标仍被单组>70%主导且无法修正 |
| 角度跨±π异常 | 人工穿越序列 | sin/cos与连续unwrap标签 | 同一轨迹角度语义不一致 |
| 双线性病态/发散 | rank、条件数、算子范数、置零N | 低秩、ridge、范数投影 | 需要删除不利轨迹或放宽发散门 |
| lift训练降loss但rollout恶化 | 一步/20步曲线和Jacobian谱 | 课程训练、早停、减lift维度 | 五seed不稳定或20步持续恶化 |
| 真实d/v物理解码不一致 | 单点oracle、坐标旋转、端点/均值对照 | 修正decoder/标签命名 | 必须修改plant真值才能通过 |
| 预测d/v导致力爆炸 | gap、法向、航向、活动边界误差分解 | 提高d/v权重、事件头、相对表示 | d/v无正信号却想靠自由残差补偿 |
| 区间力头失败 | 无事件/有事件分层，梯形误差 | 只在事件区加有界残差或小型积分头 | 残差取代全部物理输出 |
| 稳定投影损害精度 | q扫描与无约束成对对比 | 只约束内部子空间或降级经验稳定 | 为保留证书而放宽预测门 |
| OOM | batch/lift/专家逐项显存profile | 梯度累积、混合精度、减batch；保持有效步数 | 改模型容量后不重做公平预算 |
| NaN/Inf | 第一坏batch、梯度、算子范数 | 梯度裁剪、学习率、数值保护 | 跳过坏样本或把NaN置零 |
| 数据生成过慢 | pilot秒/轨迹和字节/轨迹 | 分阶段、断点、减少无关保存频率 | 预计>24 h或>50 GiB却未重新审批计划 |
| confirm失败 | 场景和模块成对分解 | 只写负结果/局部优势；另立新协议 | 回看confirm调门后再次称盲确认 |
| 没有模型超过线性 | 检查公平性和目标覆盖 | 将结果写成适用域/负结论，保留最简单模型 | 为制造创新继续无边界堆模块 |

任何硬门失败都必须：保存配置、日志、失败轨迹、调用栈和中间模型；更新`stage_status.json`；追加`work_log.md`；写/更新同一个`solutions.md`；后续阶段标为`NOT_RUN`。

### 10.1 K2前四项已知数据问题的修正指令

下列修正不是为了让旧F23“通过”。F23保持冻结，只作K1接口证据；修正应写入`revision_2026\koopman_next`，并生成新的K2 pilot数据。禁止修改、重标或插值旧F23数据。

| 编号 | 已确认问题 | 必须修改的文件/函数 | 修正指令 | 修正后硬门 |
|---|---|---|---|---|
| FIX-DATA-01 | 两条100 m轨迹末端各含一个6 ms区间 | `scripts/generate_data.py::simulate_trajectory()`、`tests/test_k2_data_contracts.py` | 达到100 m时记录“阈值已跨越”，但继续完成当前10×2 ms植物子步；只在完整20 ms控制边界保存样本并终止。记录首次跨越子步、终点距离和超调距离。不得把6 ms标签改成20 ms，也不得插值缺失14 ms。 | 每条轨迹`diff(time_s)=0.020±1e-9 s`；100 m终点距离≥100 m；离网轨迹0；超调可追溯。 |
| FIX-DATA-02 | F23参数身份不可回溯 | `src/data_manifest.py::canonical_params()`、`scripts/generate_data.py` | 每条raw和manifest保存解析参数向量、单位、规范化JSON、`params_sha256`、plant代码SHA、控制SHA、初态SHA、seed和重放SHA。参数必须显式传入植物及`build_sample`，禁止内部重新创建默认`ModelParams()`。 | 参数字段缺失0；参数SHA复算不一致0；抽查重放逐字节一致；改变任一参数必须改变参数SHA。 |
| FIX-DATA-03 | validation/test工况不足且可能诱发选择偏差 | `src/data_manifest.py::assign_split()`、`src/dataset.py` | 在生成窗口前按`base_family`和绑定的左右镜像对分split；同一初态、参数、控制族、seed及其双植物配对只能属于一个split。K2只含train/validation，K3才生成development，K11冻结后K12才生成confirm。 | base family跨split数0；窗口跨轨迹数0；归一化只读train；validation不参与归一化。 |
| FIX-DATA-04 | 平稳/操纵/连接事件覆盖不足，三专家不可辨识 | `src/scenarios.py`、`scripts/audit_coverage.py`、`scripts/run_k2.py` | K2生成D0/D1/D2/D5/D6/D10；按不重叠20步窗分别统计平稳、操纵、连接事件。事件不能只来自D10，至少D2/D5/D6中的三个自然场景合计提供事件证据；缺哪个区间只补相应base seed。 | 三类窗计数均>0；自然事件场景至少3个；左右计数差≤20%；任何常量/错误尺度Schema字段为0。 |

100 m修正的物理语义是“在控制边界终止”，不是强行让最后一个采样点恰好等于100.000 m。终点略微超过100 m是20 ms离散控制下的正常结果，必须报告`distance_overshoot_m`，不能通过回退状态或插值伪造精确终点。

### 10.2 当前代码事实与K2实现前置

截至`2026-08-29 12:22 +08:00`，5080现场`run.py`的`--stage`只接受`K0`和`K1`，目录中尚不存在`generate_data.py`、`run_k2.py`、`audit_coverage.py`、`data_manifest.py`和K2测试。因而当前直接执行`--stage K2`必然失败，这属于“尚未实现”，不能记为K2实验失败。

AI必须先用补丁方式完成以下代码改动，再运行命令：

1. 新建上述K2文件并实现第10.1节四项合同；
2. 扩展`src/contracts.py::RunContract.require_previous()`，使K2要求当前源码身份下的K0、K1均PASS；
3. 扩展`scripts/run.py`的`--stage`选择和调度，使K2调用`run_k2.run()`；
4. K2输出固定为`k2/data_manifest.csv`、`time_grid_audit.csv`、`parameter_identity_audit.csv`、`split_audit.json`、`coverage.json`、`replay_audit.csv`、`resource_projection.json`和`complete.json`；
5. K2失败时退出码为2，保留失败run并追加同一个`work_log.md`与`solutions.md`；未通过时不得进入K3。

禁止使用PowerShell的`Set-Content`、重定向或临时脚本覆盖源码；代码修改应使用可审查的补丁，并在工作记录中保存修改前后SHA256。

### 10.3 可直接执行的修正与验收命令

以下命令在5080的PowerShell中执行。它们是K2代码修正完成后的验收命令，不是授权；只有用户明确要求执行后才能运行。

#### A. 现场和前序状态预检

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$NextRoot = Join-Path $ProjectRoot 'revision_2026\koopman_next'
$ResultsRoot = Join-Path $ProjectRoot 'revision_2026\koopman_next_results'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Protocol = Join-Path $NextRoot 'config\protocol.json'

if ($env:COMPUTERNAME -ne 'DESKTOP-9IUUGEO') { throw 'Wrong host' }
foreach ($RequiredPath in @($ProjectRoot, $NextRoot, $ResultsRoot, $PythonExe, $Protocol)) {
  if (-not (Test-Path -LiteralPath $RequiredPath)) { throw "Missing: $RequiredPath" }
}

& $PythonExe --version
Get-PSDrive -Name D | Select-Object Name,Used,Free
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'python|matlab' -and $_.CommandLine -match 'koopman_next|Adaptive-koopman' } |
  Select-Object ProcessId,Name,CommandLine
Get-Content -LiteralPath (Join-Path $ResultsRoot 'stage_status.json') -Raw
```

若出现未知训练进程、主机不符、路径缺失或源码身份漂移，立即停止，不运行后续命令。

#### B. K2源码存在性、语法和定向单测

```powershell
$K2Files = @(
  (Join-Path $NextRoot 'src\data_manifest.py'),
  (Join-Path $NextRoot 'src\scenarios.py'),
  (Join-Path $NextRoot 'scripts\generate_data.py'),
  (Join-Path $NextRoot 'scripts\audit_coverage.py'),
  (Join-Path $NextRoot 'scripts\run_k2.py'),
  (Join-Path $NextRoot 'tests\test_k2_data_contracts.py')
)
foreach ($File in $K2Files) {
  if (-not (Test-Path -LiteralPath $File)) { throw "K2 implementation missing: $File" }
  & $PythonExe -m py_compile $File
  if ($LASTEXITCODE -ne 0) { throw "py_compile failed: $File" }
}

& $PythonExe -m pytest (Join-Path $NextRoot 'tests\test_k1_contracts.py') (Join-Path $NextRoot 'tests\test_k2_data_contracts.py') -q
if ($LASTEXITCODE -ne 0) { throw 'K1/K2 contract tests failed; do not run pilot' }

$HelpText = & $PythonExe (Join-Path $NextRoot 'scripts\run.py') --help 2>&1 | Out-String
if ($HelpText -notmatch 'K2') { throw 'run.py has not registered K2' }
```

定向单测至少必须包含并通过：

```powershell
& $PythonExe -m pytest (Join-Path $NextRoot 'tests\test_k2_data_contracts.py') -q -k 'hundred_meter_complete_grid or parameter_hash or base_family_split or event_coverage'
if ($LASTEXITCODE -ne 0) { throw 'Known-data-issue correction test failed' }
```

#### C. 源码变化后重新冻结K0/K1

新增K2源码会改变source manifest，旧`K0-R06/K1-R05`不能直接作为新源码身份的前序门。必须生成新run，不覆盖旧run：

```powershell
$RunScript = Join-Path $NextRoot 'scripts\run.py'

& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage K0 --run-tag PREK2_R01
if ($LASTEXITCODE -ne 0) { throw 'K0 refreeze failed; stop before K1/K2' }

& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage K1 --run-tag PREK2_R01
if ($LASTEXITCODE -ne 0) { throw 'K1 revalidation failed; stop before K2' }
```

只有新K0和新K1的`source_manifest_sha256`、`protocol_sha256`一致且均PASS，才允许执行K2。

#### D. K2小规模pilot

```powershell
& $PythonExe -B $RunScript --project-root $ProjectRoot --protocol $Protocol --stage K2 --run-tag PILOT_R01
$K2ExitCode = $LASTEXITCODE
if ($K2ExitCode -ne 0) {
  Get-Content -LiteralPath (Join-Path $ResultsRoot 'stage_status.json') -Raw
  Get-Content -LiteralPath (Join-Path $ResultsRoot 'solutions.md') -Tail 160
  throw "K2 pilot failed with exit code $K2ExitCode; K3 and all model training remain forbidden"
}
```

K2内部应严格使用第699–706行规定的D0/D1/D2/D5/D6/D10、train 2个base seed、validation 1个base seed及双植物配对。不得临时减少不利场景或调整硬门后重跑。

#### E. K2原始产物复核

```powershell
$StageStatus = Get-Content -LiteralPath (Join-Path $ResultsRoot 'stage_status.json') -Raw | ConvertFrom-Json
if ($StageStatus.stages.K2.status -ne 'PASS') { throw 'K2 status is not PASS' }
$K2RunDir = [string]$StageStatus.stages.K2.run_dir
$K2Dir = Join-Path $K2RunDir 'k2'

$RequiredArtifacts = @(
  'data_manifest.csv',
  'time_grid_audit.csv',
  'parameter_identity_audit.csv',
  'split_audit.json',
  'coverage.json',
  'replay_audit.csv',
  'resource_projection.json'
)
foreach ($Name in $RequiredArtifacts) {
  $Artifact = Join-Path $K2Dir $Name
  if (-not (Test-Path -LiteralPath $Artifact)) { throw "Missing K2 artifact: $Artifact" }
  Get-FileHash -LiteralPath $Artifact -Algorithm SHA256
}

$TimeAudit = Import-Csv -LiteralPath (Join-Path $K2Dir 'time_grid_audit.csv')
$BadTime = @($TimeAudit | Where-Object {
  [int]$_.off_grid_interval_count -ne 0 -or [double]$_.step_min_s -lt 0.019999999 -or [double]$_.step_max_s -gt 0.020000001
})
if ($BadTime.Count -ne 0) { throw "Off-grid K2 trajectories: $($BadTime.Count)" }

$ParameterAudit = Import-Csv -LiteralPath (Join-Path $K2Dir 'parameter_identity_audit.csv')
$BadParameter = @($ParameterAudit | Where-Object { $_.params_hash_match -ne 'True' -or $_.replay_hash_match -ne 'True' })
if ($BadParameter.Count -ne 0) { throw "Parameter/replay identity failures: $($BadParameter.Count)" }

$SplitAudit = Get-Content -LiteralPath (Join-Path $K2Dir 'split_audit.json') -Raw | ConvertFrom-Json
if ([int]$SplitAudit.cross_split_base_family_count -ne 0) { throw 'Base-family leakage detected' }

$Coverage = Get-Content -LiteralPath (Join-Path $K2Dir 'coverage.json') -Raw | ConvertFrom-Json
if (-not $Coverage.hard_gate_passed) { throw 'Coverage hard gate failed' }
```

自动报告PASS只能作为候选结论；执行者还必须从`time_grid_audit.csv`、`parameter_identity_audit.csv`和`data_manifest.csv`独立复算轨迹数、时间步、参数SHA、split交集和三类不重叠窗口计数，再追加工作记录。

### 10.4 修正失败后的诊断命令和恢复边界

```powershell
$LatestRuns = Get-ChildItem -LiteralPath (Join-Path $ResultsRoot 'runs') -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 5 FullName,LastWriteTime
$LatestRuns

$LatestRun = $LatestRuns[0].FullName
Get-ChildItem -LiteralPath $LatestRun -Recurse -File |
  Select-Object FullName,Length,LastWriteTime
if (Test-Path -LiteralPath (Join-Path $LatestRun 'failure\exception.txt')) {
  Get-Content -LiteralPath (Join-Path $LatestRun 'failure\exception.txt') -Raw
}
Get-Content -LiteralPath (Join-Path $ResultsRoot 'work_log.md') -Tail 120
Get-Content -LiteralPath (Join-Path $ResultsRoot 'solutions.md') -Tail 200
```

恢复规则：

- 任何代码修正后不得对旧失败run使用`--resume`；应以新run tag重做K0、K1、K2，保留失败证据；
- 仅数据生成中断、且代码/协议/input manifest哈希完全未变时，才允许实现并使用`--resume`；
- 不得删除失败轨迹、修改旧CSV、放宽20 ms容差或复制事件窗口；
- 连续三次最小修正仍无法通过同一硬门时，停止K2，更新`koopman_dev_solutions.md`，列出根因候选、反证、最低成本方案和重新进入门槛；
- K2未PASS时，K3–K14一律保持`NOT_RUN`。

## 11. 运行入口与资源规则

计划中的统一PowerShell入口：

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Protocol = Join-Path $ProjectRoot 'revision_2026\koopman_next\config\protocol.json'

& $PythonExe -B `
  (Join-Path $ProjectRoot 'revision_2026\koopman_next\scripts\run.py') `
  --project-root $ProjectRoot `
  --protocol $Protocol `
  --stage K0
```

后续只改变`--stage K1`至`K14`。`run.py`必须：

- 自动生成唯一run_id；
- 拒绝覆盖已存在目录；
- 前序硬门未通过时退出码非0；
- 捕获stdout/stderr、命令、耗时、GPU峰值、退出码；
- 完成后立即追加工作记录；
- `--resume`只在输入manifest和配置hash完全一致时允许。

资源纪律：

- 一次只启动一个正式GPU训练进程；
- 不终止未知进程；
- 不联网安装依赖；
- pilot先测量秒/轨迹、秒/epoch、显存和磁盘，再外推全量；
- checkpoint只保留每seed的best、last和失败现场，不逐epoch无限保存；
- 每60秒内应能看到进度或心跳；无心跳但GPU占用为0超过10分钟视为疑似挂起，先只读诊断。

## 12. 工作记录格式

新阶段统一使用：

`revision_2026\koopman_next_results\work_log.md`

本地镜像使用：

`D:\PDxc\Review\koopman_dev_log.md`

每完成一个节点立即追加：

```markdown
## KN-XXXX — YYYY-MM-DD HH:mm — 任务标题

- 请求/任务编号：
- 授权模式：执行实验
- 机器与项目根目录：
- 阶段：K0...K14
- 基线身份：
- 输入数据/manifest：
- 读取：
- 修改：
- 命令：
- 退出码：
- 原始产物：
- 关键结果（单位、样本范围、统计口径）：
- 结论类型：事实/推断/建议/未知
- 状态：PASS/PARTIAL/BLOCKED/NOT_RUN
- 停止原因：
- 下一允许动作：
```

计划任务不得提前记为完成。

## 13. 论文需要的最终图表

1. 方法结构图：绝对状态→相对坐标→lift→三专家→相对状态→R3力律→四点/内部载荷；
2. 1/5/10/20步状态、几何、力和内部载荷曲线；
3. 工况×模型性能热图，保留失败值；
4. gate权重随直线—入弯—弯道—出弯变化；
5. 变量组敏感度和组消融，证明活跃子空间而非展示注意力；
6. 双线性完整/置零/打乱和贡献比；
7. 真实d/v、预测d/v、物理解码、事件残差四级误差传播图；
8. 四点Fx/Fy方向、完整内部力、`T_x/T_y`预测；
9. 无约束、采样IRSP、输入盒范数约束的20/50/100步稳定—精度权衡；
10. 精度—参数量—推理时间Pareto；
11. V1/R3同架构结果，明确相同点和植物相关差异；
12. 最坏三条轨迹与失败说明。

所有图片必须有同名CSV/NPZ、meta.json、生成脚本和SHA256。

## 14. 盲确认后允许的结论模板

### 若全局硬门通过

可以写：

> 在本文定义的1.5–5.0 m/s四车协同运输仿真域内，相对几何表示减少了绝对状态差分对连接形变的误差放大；因果三专家结构在平稳、操纵和连接事件区间形成了可验证的分工；结合已知连接器本构的物理解码后，20步四点力与内部载荷预测相对最强简单基线获得统计显著改善，同时未观察到主要状态和最坏关键工况的显著退化。

稳定性只能按K10实际结果选择以下之一：

- 通过输入盒范数门：写“学习内部状态在给定归一化输入盒内满足一个保守有界性充分条件”；
- 未通过：写“使用经验长时滚动和发散率评价，不提出连续输入域稳定性证书”。

### 若只有局部模块通过

写清适用区：例如“相对表示主要改善接触切换和力预测；固定线性在直线/加减速仍更合适”。不得拼接不同工况的oracle最优模型后声称单一方法全局最优。

### 若所有创新均未超过简单基线

合法结论是：

> 在当前数据规模和低载荷域内，增加可训练lift、双线性、门控和物理残差没有稳定超过相对坐标线性模型；复杂模块的收益受事件样本、可辨识性和递推稳定性限制。

这仍能回答审稿人“为什么双线性不够用、何时退化”，但不能作为新主方法正贡献。

## 15. 第一次实际停止点

截至`2026-08-29 02:53 +08:00`，K0最终run `20260829_025304_K0_R06`与K1最终run `20260829_025320_K1_R05`均PASS；5080在`2026-08-29 12:22 +08:00`无本项目Python/MATLAB进程。本次任务书更新没有修改5080代码或启动实验。

下一次获得明确“执行”授权后，只允许先实现第10.1–10.2节的K2数据修正接口，执行第10.3节B的单测，再因源码身份变化重新执行K0/K1，最后执行K2 pilot。当前26条F23数据明确不足；在K2覆盖门通过并由原始CSV独立复算前，不允许启动可训练lift、三专家、双线性、物理解码或任何正式GPU训练。

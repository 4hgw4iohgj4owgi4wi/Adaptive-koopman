# Worker C: Method and Theory Completion Tasks

目标：为 `Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC` 的方法与理论章节提供后续补稿任务拆解。本文档只规划中文稿后续修改，不修改 DOCX、代码、图件或实验数据。

依据材料：

- 任务树：`paper_dcn_tf12_draft/parallel_article_completion_2026-05-10/00_task_tree.md`
- 当前中文稿：`paper_dcn_tf12_draft/manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`
- 代码证据：`tf14_pre.ipynb`、`tf14_runtime.py`、`control_files/tf12/comm_quality_consensus.py`、`control_files/tf14/fdi_monitor.py`、`control_files/tf14/control_switch.py`、`control_files/tf14/stability_certificate.py`

## Reviewer 2 返工硬门禁

本轮返工后，后续中文稿集成必须满足以下 P0/P1 门槛：

- P0 闭环链条：先写清 `u_i^{mpc} -> u_i^{comm} -> u_i^{ftc} -> u_c^{agg} -> x_{c,k+1}`，再说明该组合映射如何在模式 `sigma` 下诱导团队闭环 `A_sigma/B_sigma` 或有界增益抽象；不得模块堆叠后直接套团队稳定性。
- P0 稳定性边界：主结论只能是 practical boundedness、ISS-practical stability 或 UUB；不得写全局渐近稳定、任意通信故障稳定或任意故障完全恢复。
- P1 通信边界：主方法只覆盖 bounded delay/dropout/model error 和 feasible MPC；400 ms、40% dropout、leader-lost 等必须标为边界外压力测试，除非补充 `G_k=(V,E_k)` 的有界连通性/最大失联时长假设。
- P1 online adaptation：若主 preset 关闭在线自适应，只能写成接口或补充模块；若保留为贡献，必须要求 paired ablation。
- P1 符号硬门禁：`q/Gamma/delta/tau/x/z/G/A/B` 等冲突符号必须在最终符号表给出唯一含义，并逐章复核。

## 1. 系统模型

任务目标：把四车刚性载荷运输系统从“车辆独立跟踪”明确改写为“载荷中心团队模型 + 角点刚体映射 + 连接一致性误差”的问题定义，为 Koopman、MPC、通信补偿和 FTC 统一状态基础。

输入材料：

- 当前中文稿第 2 节“系统模型与问题描述”。
- `dynamics/cacalv3_payload_a1.py` 中的团队中心与角点车辆映射逻辑。
- `control_files/rigid_payload_coordinator_a1.py` 中的 `team_to_corner_states` 调用方式。
- `control_files/rigid_payload_connection_compliance_a1_v1.py` 中的连接相对误差和柔性约束限幅。
- `tf14_runtime.py` 中 `payload_cfg`、`corner_offsets`、`payload_force_hist`、`normal_load` 相关记录。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 系统状态定义段 | 定义载荷中心状态 `x_c=[s_c,e_{y,c},e_{\psi,c},v_{x,c},v_{y,c},r_c]^T`，四车局部状态 `x_i`，团队命令 `u_c=[delta_c,a_c]^T` 和单车命令 `u_i=[delta_i,a_i]^T`。 |
| 单车 Frenet 动力学公式 | 给出离散或连续动态自行车 Frenet 模型，必须说明 `s,e_y,e_psi,v_x,v_y,r` 的单位和物理意义。 |
| 载荷中心模型公式 | 给出 `x_{c,k+1}=f_c(x_{c,k},u_{c,k};theta_c)+w_{c,k}` 或连续等价式，明确 `theta_c` 汇总质量、转动惯量、轮胎刚度、载荷几何等参数。 |
| 角点映射公式 | 给出 `x_{i,k}^{ref}=T_i(x_{c,k}^{ref};p_i)` 和 `x_{i,k}=T_i(x_{c,k};p_i)+epsilon_{i,k}^{conn}`，其中 `p_i` 是角点偏置。 |
| 载荷受力指标公式 | 给出团队等效纵向力、横向力、偏航力矩、角点法向载荷或连接误差指标的定义，说明这些是安全/平顺性评估指标，不一定全部进入 MPC 约束。 |
| 参数表 | 列出车辆质量、转动惯量、轴距、轮胎刚度、载荷长宽、角点编号、采样时间、输入约束。若数值来自代码或实验配置，必须标明“以最终实验配置导出为准”。 |

验收标准：

- 模型章节能清楚回答“为什么不是四个单车模型简单拼接”，而是团队中心与角点映射的耦合系统。
- 所有状态、输入、扰动、参数集合在首次出现处有定义，且后续 Koopman/MPC/proof 使用同一符号。
- 载荷受力与角点法向载荷只作为安全和评价指标时，不能写成已经被严格硬约束保证。
- 若公式采用离散时间，Lyapunov 证明也必须采用离散递推；若正文保留连续模型，需明确控制器和证书在离散采样时刻实现。

## 2. 坐标系/符号

任务目标：建立全稿统一符号表，避免方法章节、算法段、实验指标和 Lyapunov 证明使用不同的误差、模式、通信质量和扰动符号。

输入材料：

- 当前中文稿第 2.1 节坐标系与参考路径。
- 当前中文稿第 4.8 节 Lyapunov 型证明。
- `control_files/tf14/stability_certificate.py` 中 `team_state`、`team_ref`、`mode`、`V`、`predicted_upper`、`contraction_margin`。
- `control_files/tf14/control_switch.py` 中三类全局模式名称。
- `control_files/tf12/comm_quality_consensus.py` 中链路质量、全局质量、时延和丢包变量。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 坐标系说明段 | 区分大地坐标、参考路径 Frenet 坐标、车辆车体坐标、载荷中心坐标和角点局部参考坐标。 |
| 符号总表 | 至少包含 `x_c,x_i,u_c,u_i,z,psi(x),A,B,C,B_j,q_{ij},q_i^{in},q_g,tau_{ij},ell_{ij},sigma_k,V_sigma,d_k,tilde Gamma_k`。 |
| 角点编号表 | 明确车辆 0/1/2/3 对应 front-left/front-right/rear-left/rear-right，和代码 `PhaseRoleSchedulerTF14._role` 一致。 |
| 模式名称映射表 | 将论文符号 `N,R,S` 映射到代码 `nominal_koopman_mpc`、`reconfigured_ftc_mpc`、`safe_degraded_consensus`。 |
| 误差定义段 | 统一 `e_k=x_{c,k}-x_{c,k}^{ref}` 或 `e_k=x_{c,k}^{ref}-x_{c,k}` 的方向，后文 Lyapunov、MPC 和 progress supervisor 必须沿用同一方向。 |
| 符号硬门禁表 | 对 `q/Gamma/delta/tau/x/z/G/B/A` 等高冲突符号给出唯一含义、允许下标和禁用含义。 |

验收标准：

- 同一变量不允许在方法中表示局部车、在证明中表示团队中心，除非加下标明确区分。
- `q` 不能同时表示状态权重和通信质量；建议状态权重写为 `Q`，通信质量写为 `q_{ij}` 或 `q_g`。
- `delta` 既可表示前轮转角又可表示增量/扰动，需在公式中把前轮转角固定为 `\delta`，模型增量写为 `Delta A, Delta B`，扰动写为 `d_k`。
- `Gamma` 必须专用于执行器效率矩阵或估计误差；不要再用 `Gamma` 表示通信图。
- 符号硬门禁必须落实到最终中文稿的符号表，而不是只在审稿清单中提醒；若正文、证明、图注或表格有冲突，必须先改符号再改结论。

符号硬门禁：

| 符号 | 唯一允许含义 | 禁止混用 | 最终稿检查点 |
|---|---|---|---|
| `x_c` | 载荷中心/团队中心物理状态 | 不表示单车状态或 lifted state | 系统模型、MPC、证明均使用同一定义。 |
| `x_i` | 第 `i` 辆角点车物理状态 | 不表示团队中心状态 | 局部 MPC 和 FDI 残差只用 `x_i`。 |
| `z_i` 或 `z_c` | Koopman lifted state | 不表示物理状态或通信质量 | Koopman 预测和 MPC lifted 约束中必须显式区分 `x` 与 `z`。 |
| `q_{ij},q_i^{in},q_g` | 链路/入向/全局通信质量 | 不表示 MPC 状态权重 | MPC 权重只能写 `Q_i,Q_c`。 |
| `Gamma_i,\hat Gamma_i,\tilde Gamma_i` | 执行器真实效率、估计效率、估计误差 | 不表示通信图或增益矩阵 | FTC 和 proof 中均用该定义。 |
| `\delta_i` | 第 `i` 车转角输入 | 不表示变化量、扰动或 Dirac 项 | 变化量用 `Delta`，扰动用 `d_k`。 |
| `tau_{ij,k}^{comm}` | 通信离散时延 | 不表示力矩、时间常数或控制周期 | 力矩写 `M_z`，采样周期写 `T_s` 或 `dt`。 |
| `G_k=(V,E_k)` | 时变通信图 | 不表示扰动输入矩阵 | proof 输入矩阵写 `G_{\sigma}` 时需改名为 `D_{\sigma}` 或 `W_{\sigma}`，避免冲突。 |
| `A_{\sigma},B_{\sigma}` | 由完整控制链诱导的模式等效闭环矩阵 | 不直接等同 Koopman 训练矩阵 `A,B` | 证明中必须说明由局部线性化/有界增益抽象得到。 |

## 3. 离线数据生成

任务目标：把离线数据从“训练细节”提升为方法可复现模块，说明数据覆盖、参数随机化和激励设计如何支撑双线性 Koopman 主干，而不是把性能提升归因于更容易的数据。

输入材料：

- `tf14_runtime.py` 中 `build_or_load_a1_dataset`、参数场景构造、`variation_summary`、`offline_dataset_a1_rigid_payload_2t` 相关路径。
- `tf14_pre.ipynb` 中训练/验证划分、样本量、输入激励、`KOOPMAN_CFG`。
- 当前中文稿第 3 节“离线数据生成与双线性 Koopman 升维模型”。
- 后续 Worker D 的实验计划，仅用于确认数据覆盖证据是否需要图表，不在本文档修改实验任务。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 数据生成流程段 | 说明从参数采样、参考速度/转角/加速度激励、车辆/载荷状态 rollout 到训练样本 `(x_k,u_k,x_{k+1})` 的流程。 |
| 变化参数集合公式 | 写出 `theta in Theta`，说明质量、转动惯量、轮胎刚度、载荷参数和噪声/扰动的变化范围由最终配置表给出。 |
| 数据集规模表 | 给出训练样本量、验证样本量、状态维数、输入维数、采样时间、轨迹数量、80/20 划分；当前中文稿可保留 lifted fit 样本数 `805824`，但须由最终日志复核。 |
| 激励覆盖段 | 解释多速度、多曲率、多输入幅值激励覆盖直线、入弯、弯中、出弯和故障前后附近动态。 |
| baseline 公平性段 | 明确 TF14 与 AKE-baseline 在同一 A1 任务数据或可比数据设置下评估，不能把“更丰富训练数据”写成唯一改进来源。 |

验收标准：

- 数据生成章节能复现样本来源，不只列超参数。
- 所有数据规模数值必须与最终 `npz/log` 一致；若尚未复核，用“待由最终训练日志确认”标注，不写死。
- 训练数据与在线故障/通信退化场景的关系要谨慎：若故障未进入训练分布，只能说在线 FDI/FTC 处理部署期退化，不能说 Koopman 离线模型已经覆盖所有故障。
- 不把单 seed gap-closure 结果写成统计结论；多 seed 证据由 Worker D 规划。

## 4. TF14 Koopman 网络

任务目标：完整定义 TF14 稳定投影双线性 Koopman 主干，包括观测构造、矩阵维度、训练损失、岭回归重拟合、谱投影和在线自适应接口的启用边界。

输入材料：

- `tf14_pre.ipynb` 中 `encoder_hidden_width=128`、`encoder_hidden_depth=4`、`activation_type=gelu`、`override_C=False`。
- `tf14_pre.ipynb` 中 `ridge_lambda=5e-5`、`linear_fit_blend=0.60`、`previous_model_blend=0.20`。
- `tf14_pre.ipynb` 中在线自适应配置 `window=18`、`forget_factor=0.97`、`ridge_lambda=2e-4`。
- 当前中文稿第 3.2 节名义双线性 Koopman 升维网络和在线自适应段。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| lifted state 定义公式 | 写出 `z_k=[1,x_k^T,phi_theta(x_k)^T]^T`，并明确 `x_k in R^6`、`phi_theta(x_k) in R^24`、`z_k in R^31`。 |
| 解码公式 | 写出 `hat x_k=C z_k`，说明 `C in R^{6x31}` 为学习矩阵，`override_C=False`，不是固定选择矩阵。 |
| 双线性预测公式 | 建议写为 `z_{k+1}=A z_k + B_0 u_k + sum_{m=1}^{n_u} u_{m,k} B_m z_k + eta_k` 或项目实际等价形式；必须明确 `B` 是单矩阵还是双线性张量/矩阵组。 |
| 训练损失公式 | 包含一步状态绝对增量误差、lifted 增量误差和谱半径稳定正则，说明 `alpha=0.60`、`lambda_rho=0.01` 若最终配置一致则保留。 |
| 稳定投影公式 | 写出 `A <- Pi_rho(A)`，目标谱半径约束 `rho(A)<=bar rho<1`，并说明当前主运行约从 `1.0024` 投影到 `0.9990` 需要最终日志复核。 |
| 在线自适应接口段 | 写出滑动窗口、遗忘因子、样本接受条件、范数裁剪、谱投影和融合系数；若主 preset 关闭在线更新，必须降级表述为“接口/补充模块”，不能列为主方法贡献。 |
| paired ablation 需求段 | 若作者坚持把 online adaptation 保留为贡献，必须要求 paired ablation：同一 seed、同一轨迹、同一故障/通信配置下比较 `adapt on/off`，并报告预测误差、跟踪误差、证书裕度和运行时间差异。 |
| Koopman 配置表 | 列出网络层数、宽度、激活、学习率、epoch、batch size、weight decay、ridge、blend、lifted 维度、矩阵维度。 |

验收标准：

- `31` 维 lifted state 的构造必须与 `24` 维可学习观测加常数和原始 6 维一致。
- 如果论文写“bilinear”，公式必须真的出现输入-状态乘积项；若实际控制中只用 `A z + B u` 的线性 lifted 模型，需改称“lifted linear with bilinear fitting interface”或补齐代码证据。
- 稳定投影只能作为预测主干的谱半径约束，不能单独推出闭环稳定。
- 在线自适应若在主实时实验关闭，正文只能写“保留接口/补充模块/在消融中启用”，不能把主实验性能归因于未启用模块。
- 在线自适应若要进入摘要、贡献或主方法图，必须先补 paired ablation；没有 paired ablation 时，只能作为实现扩展点放在方法末尾或附录。

## 5. MPC

任务目标：把局部 Koopman MPC、团队聚合、稳定保护、进度监督和预算感知求解统一写成控制栈，而不是把多个启发式模块零散堆叠。

输入材料：

- 当前中文稿第 4.1 和 4.4 节。
- `tf14_pre.ipynb` 中 `horizon=12`、PPC/自适应权重配置和输入约束配置。
- `tf14_runtime.py` 中 `realtime_horizon`、`mpc_decimation_steps`、`max_sqp_iters`、`fast_max_sqp_iters`、leader-first/partial solve 相关逻辑。
- `control_files/rigid_payload_stability_guard_a1_v2.py` 和 `control_files/a1_progress_supervisor_v2.py`。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 单车 Koopman MPC 优化问题 | 写出有限时域目标函数，包含跟踪误差、输入、输入变化率或终端项；给出状态/输入约束。 |
| 自适应权重段 | 说明故障、高曲率或误差增大时如何调整 `Q,R`，但不要把权重调整写成严格最优性证明。 |
| PPC/误差包络公式 | 若保留 PPC，明确 `rho_{e_y,k}`、`rho_{e_psi,k}` 的初值、终值和衰减，仅作为误差约束/惩罚设计。 |
| 控制层级链公式 | 必须写出 `u_i^{mpc} -> u_i^{comm} -> u_i^{ftc} -> u_c^{agg}` 的顺序、输入输出和作用域。 |
| 映射组合公式 | 建议写为 `u_i^{comm}=Pi_i^{comm}(u_{1:n}^{mpc},q_k,tau_k)`，`u_i^{ftc}=Pi_i^{ftc}(u_i^{comm},hat Gamma_i,sigma_k)`，`u_c^{agg}=A_{agg}(u_{1:n}^{ftc},x_c)`。 |
| 团队聚合公式 | 写出均值-中值混合聚合器，说明控制离散度越高越偏向中值以抑制离群命令。 |
| 稳定保护公式 | 写出侧偏角、横摆角速度、横向/航向误差触发的 tracking-stability 插值逻辑。 |
| 进度监督公式 | 写出只在横向/航向状态稳定时恢复纵向加速度的条件和限幅。 |
| 团队闭环诱导段 | 将物理系统写成 `x_{c,k+1}=F_c(x_{c,k},u_c^{agg},d_k)`，并说明证明中的 `A_sigma/B_sigma` 是由 `F_c` 与上述控制链在模式 `sigma` 下局部线性化或有界增益抽象得到，不是直接把单车 MPC 矩阵搬到团队层。 |
| 实时求解策略段 | 说明 horizon、SQP 迭代、decimation、预算不足时 partial solve 的工程边界，避免宣称全局最优实时 MPC。 |

验收标准：

- MPC 公式中的状态 `x_i`、lifted state `z_i`、团队状态 `x_c` 不能混用。
- 若优化问题写在局部车层面，团队聚合和稳定保护必须写成优化后的执行层；若写成团队 MPC，则需说明局部 MPC 的角色。
- 必须先证明或说明控制链 `u_i^{mpc} -> u_i^{comm} -> u_i^{ftc} -> u_c^{agg}` 的每一层是限幅、有界或局部 Lipschitz 的，Lyapunov 证明才能把它抽象成模式闭环 `A_sigma/B_sigma`。
- 不能在模块堆叠后直接写团队误差满足 `e_{k+1}=A_sigma e_k+...`；中间必须有“组合映射诱导团队闭环”的桥接段。
- 不能声称 OSQP/SQP 解是全局最优非线性解；应表述为“预算感知近似求解/局部迭代求解”。
- 进度监督不能被写成稳定性证明的一部分，除非证明中把它作为有界 trim 或有界输入项处理。

## 6. 通信补偿

任务目标：把通信质量感知一致性、时延前推预测、约束收紧和退化回退写成网络韧性控制模块，明确其处理的是轻度到中度通信退化，不是任意攻击或无限时延。

输入材料：

- 当前中文稿第 4.3 节。
- `control_files/tf12/comm_quality_consensus.py` 中 `packet_loss_base`、`packet_loss_gain`、`delay_steps_max`、`quality_smooth_beta`、`quality_tau_steps`、`consensus_blend_min/max`、`tighten_max_frac`、`degrade_threshold`。
- `tf14_runtime.py` 中 `use_comm_quality_consensus=True`、`use_delay_compensation=True`、通信诊断和延迟状态读取逻辑。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 链路退化模型公式 | 定义丢包 `ell_{ij,k}`、离散时延 `tau_{ij,k}`、链路质量 `q_{ij,k}` 和全局质量 `q_{g,k}`。 |
| 时变通信图公式 | 定义 `G_k=(V,E_k)`，其中 `E_k={(j,i): ell_{ji,k}=0, tau_{ji,k}^{comm}<=bar tau}`；若要把 leader-lost 纳入理论，必须给出窗口联合连通性或有界失联时长假设。 |
| 质量平滑公式 | 写出 `q_{ij,k}=beta q_{ij,k-1}+(1-beta)q_{ij,k}^{inst}`，说明丢包时质量乘以低可信因子。 |
| 时延前推预测公式 | 写出 `hat x_{j|i,k}=F_pred(x_j(k-tau_{ji,k}),tau_{ji,k})`，并说明当前实现是基于短时 kinematic forward prediction。 |
| 一致性投影公式 | 写出 `u_i^+=(1-lambda_i)u_i+lambda_i bar u_q`，其中 `lambda_i` 随入向质量下降而增大。 |
| 约束收紧公式 | 写出 `U_k(q_g)` 随通信质量下降收缩，不要写成所有安全约束都被严格满足。 |
| 退化回退公式 | 写出当 `q_g` 或 loss ratio 低于阈值时，团队命令与保守安全命令混合。 |
| 通信配置表 | 列出主实验和压力实验的 `packet_loss_base/gain`、`delay_steps_max`、质量平滑、阈值、blend 范围，并明确哪些配置在理论保证边界内。 |
| 通信压力边界表 | 将主方法声明与 stress-test 分开：主方法只声明 bounded delay、bounded dropout/model error、feasible MPC；400 ms、40% dropout、leader-lost 等若未满足连通性假设，必须标为边界外压力测试。 |

验收标准：

- 主实验若采用 `comm_packet_loss_base=0.00`、`gain=0.20`、`delay_steps_max=1`，必须写成轻度负载相关链路模型；不要称为强攻击场景。
- 通信补偿的结论应是减小相位滞后和命令离散度，不是完全消除时延/丢包影响。
- Byzantine、虚假信息、恶意攻击如果没有实现和实验，只能作为相关工作差距，不能写成本文已解决。
- 证明中的通信扰动应写成有界扰动项 `d_k` 或 `1-q_g` 加权项，与本节质量定义一致。
- 理论主声明只能覆盖有界时延 `tau_{ij,k}^{comm}<=bar tau`、有界连续丢包长度或窗口联合连通的 `G_k`、有界模型误差和保持可行的 MPC。
- 如果 stress-test 使用 400 ms 时延、40% dropout、leader-lost 或长时间断连，必须二选一：要么证明这些设置仍满足 `G_k` 的有界连通性/最大失联时长假设，要么在图注和正文中标为“边界外压力测试，不属于稳定性保证范围”。
- 不能把 stress-test 成功通过写成理论保证扩大到任意通信故障；只能写成经验鲁棒性或压力测试证据。

通信压力分层建议：

| 层级 | 可写入主方法保证的条件 | 只能作为压力测试的条件 |
|---|---|---|
| 主方法保证边界 | `tau_{ij,k}^{comm}<=bar tau`、丢包长度有界、`G_k` 在窗口 `T_conn` 内联合连通、MPC 保持局部可行、Koopman/FDI 误差有界。 | 不适用。 |
| 强退化但可解释 | dropout 较高但仍满足联合连通性，leader 短时失联但窗口内恢复，delay 未超过补偿 horizon。 | 必须报告 `T_conn`、最大失联步数、最小 `q_g`。 |
| 边界外压力测试 | 400 ms 超过当前补偿 horizon、40% dropout 导致长窗口不连通、leader-lost 造成无界信息缺失或 MPC 不可行。 | 仅能写 stress-test/empirical robustness，不能进入 Lyapunov 主结论。 |

## 7. FTC/安全

任务目标：把在线 FDI、执行器效率估计、模式切换、故障重构、健康车辆重分配和安全降级一致性写成可诊断的韧性执行层，同时明确安全声明的证据边界。

输入材料：

- 当前中文稿第 4.5 节和后续 TF14 FDI/FTC 段。
- `control_files/tf14/fdi_monitor.py`：残差 EWMA、CUSUM、执行器效率估计、故障模式和置信度。
- `control_files/tf14/control_switch.py`：三模式切换、驻留步数、逆补偿、重分配和 safe degraded 缩放。
- `control_files/tf14/phase_role_scheduler.py`：phase-role 有界 trim。
- `tf14_runtime.py`：故障注入、诊断历史、switch 历史、payload force 记录。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| FDI 残差公式 | 定义一步预测残差 `r_{i,k}=x_{i,k}-hat x_{i,k|k-1}`、归一化残差、EWMA 和 CUSUM 统计量。 |
| 执行器效率公式 | 定义 `Gamma_{i,k}=diag(gamma_{delta,i,k},gamma_{a,i,k})`，说明效率估计来自命令与测量/响应比值。 |
| 诊断模式表 | 列出 `nominal`、`residual_only_alert`、`accel_degraded`、`steer_degraded`、`dual_degraded`、`severe_dual_loss` 的触发逻辑和论文含义。 |
| 切换控制模式表 | 列出 `nominal_koopman_mpc`、`reconfigured_ftc_mpc`、`safe_degraded_consensus`，说明触发条件、控制动作、风险边界。 |
| 逆补偿与重分配公式 | 写出故障车 `u_i` 的效率逆补偿、预测亏损 `Delta u_i` 和健康车均分/加权补偿公式，并包含输入限幅。 |
| 安全降级公式 | 写出 safe mode 下转角和加速度的全局缩放，以及通信质量过低时进入保守一致性的条件。 |
| 安全声明段 | 明确本文安全是“约束感知、降级保护、证书记录和力/载荷指标监测”，不是形式化全局碰撞避免或所有载荷边界的硬证明。 |

验收标准：

- FDI 的 `residual_threshold` 当前中文稿和代码存在可能差异：`tf14_runtime.py` 有默认 `0.85`，`OnlineFDIMonitorTF14` 类默认 `0.18`，后续中文稿必须以实际传入配置为准。
- `switch_dwell_steps` 当前中文稿和代码默认也可能不一致：`tf14_runtime.py` 早期 setdefault 出现 `4`，控制器构造和类默认出现 `6`，后续必须从最终运行配置确认。
- 不能写“未知故障被完全恢复”；应写“在效率估计误差、输入饱和和健康车余量允许范围内重构团队等效力/力矩”。
- safe degraded 模式会降低激进度和收缩控制，不应被写成性能最优模式。

## 8. Lyapunov 证明

任务目标：把 TF14 闭环稳定性证明限定为切换系统的输入到状态实用稳定性或统一最终有界性，确保理论假设与代码证书记录一致，避免在持久通信故障、模型误差和执行器辨识误差存在时宣称过强稳定。

输入材料：

- 当前中文稿第 4.8 节完整 Lyapunov 型稳定性证明。
- `control_files/tf14/stability_certificate.py` 中 `V=e^T P_sigma e`、`predicted_upper`、`contraction_margin`、`certificate_ok`。
- `control_files/tf14/control_switch.py` 中模式切换和驻留逻辑。
- `control_files/tf14/fdi_monitor.py` 中效率估计误差来源。
- 通信补偿模块的 `q_g`、loss ratio、delay residual。

应产出的公式/段落/表格：

| 产出项 | 内容要求 |
|---|---|
| 控制链到闭环桥接公式 | 先写 `u_i^{mpc}=K_i^{mpc}(z_i,x_i^{ref})`，`u_i^{comm}=Pi_i^{comm}(u_{1:n}^{mpc},q_k,tau_k,G_k)`，`u_i^{ftc}=Pi_i^{ftc}(u_i^{comm},hat Gamma_i,sigma_k)`，`u_c^{agg}=A_{agg}(u_{1:n}^{ftc},x_c)`，再写 `x_{c,k+1}=F_c(x_{c,k},u_c^{agg},d_k)`。 |
| 闭环误差抽象公式 | 在上述组合映射后，才能局部线性化或有界增益抽象为 `e_{k+1}=A_{sigma_k}e_k + D_{sigma_k}d_k + H_{sigma_k}tilde Gamma_k + Xi_{sigma_k}xi_k`，其中 `xi_k` 表示 MPC 近似求解、phase-role trim、聚合误差和数值误差。 |
| `A_sigma/B_sigma` 诱导说明 | 明确 `A_sigma,B_sigma` 不是 Koopman 训练矩阵，也不是单车 MPC 矩阵，而是由物理团队模型 `F_c` 与完整控制链在模式 `sigma` 下诱导的团队闭环等效矩阵；若只做有界性证明，可用局部 Lipschitz/增益界替代显式矩阵。 |
| 假设列表 | 至少包含工作域紧致、输入投影非扩张、Koopman 残差有界、通信时延/丢包扰动有界、`G_k` 窗口联合连通或最大失联时长有界、效率估计误差有界、切换有平均驻留时间或最小 dwell、MPC 可行性在局部工作域内保持。 |
| 多 Lyapunov 函数 | 写出 `V_sigma(e)=e^T P_sigma e`，说明 `P_sigma` 正定且可模式依赖。 |
| 单步递推不等式 | 写出 `V_{sigma_k}(e_{k+1})-V_{sigma_k}(e_k)<=-alpha_sigma ||e_k||^2 + c_d||d_k||^2 + c_Gamma||tilde Gamma_k||^2 + c_xi||xi_k||^2`。 |
| 切换跳变界 | 写出 `V_{sigma^+}(e)<=mu V_{sigma^-}(e)`，结合 dwell-time 得到最终有界。 |
| 结论表述 | 结论只能写为 practical boundedness、ISS-practical stability 或 uniform ultimate boundedness，并说明最终界随通信退化、模型残差、效率估计误差和求解误差增大。 |
| 证书对应表 | 把理论量映射到代码记录：`V`、`predicted_upper`、`contraction_margin`、`disturbance_level=1-q_g`、`identification_error`、`certificate_ok`。 |

验收标准：

- 证明不把 `SwitchedFTCCertificateTF14` 写成理论证明本身，只写成证明假设和仿真闭环之间的在线记录器。
- `lambda_nominal=0.08`、`lambda_reconfigured=0.06`、`lambda_safe=0.04` 是证书收缩率参数，不能直接声称真实闭环矩阵特征值已经被这些数严格证明。
- 不得把主结论写成全局渐近稳定、任意通信故障稳定或任意故障恢复；即使讨论理想无扰动名义情形，也只能作为附加说明，不能替代 practical/UUB 主结论。
- 若存在持久丢包、窗口不连通、持续模型失配、MPC 不可行或故障效率低于健康车补偿能力，不得声称误差收敛到零，只能声称超出理论保证并触发保守降级或作为压力测试观察。

## Method 与 Proof 的符号一致性风险

| 风险项 | 可能冲突 | 建议修正 |
|---|---|---|
| 误差方向 | 方法中常用 `x_ref-x` 做进度滞后，证明中可能用 `x-x_ref`。 | 在符号表固定 `e_k=x_{c,k}-x_{c,k}^{ref}`；进度滞后另写 `l_s=s_k^{ref}-s_k`。 |
| 局部车状态与团队状态 | MPC 用 `x_i`，证书用 `team_state`，当前文字可能都写 `x_k`。 | 团队中心固定 `x_c`，车辆局部固定 `x_i`，lifted state 固定 `z_i` 或 `z_c`。 |
| 通信质量符号 | `q` 可能同时表示质量、权重或代价。 | 通信质量写 `q_{ij},q_i^{in},q_g`；代价矩阵写 `Q_i,R_i`。 |
| 输入符号 | `u_c`、`u_i`、`u_team` 和聚合后命令易混。 | 定义 `u_i^{mpc}`、`u_i^{comm}`、`u_i^{ftc}`、`u_c^{agg}`，说明执行顺序。 |
| 双线性矩阵 | `B` 可能表示线性输入矩阵，也可能表示双线性矩阵组。 | 对线性输入写 `B_0`，对输入-状态耦合写 `B_m` 或 `\mathcal{B}`。 |
| 执行器效率 | `Gamma`、`tilde Gamma` 和故障亏损 `Delta u` 可能混用。 | `Gamma_i` 表示真实/估计效率矩阵，`\tilde Gamma_i=Gamma_i-\hat Gamma_i` 表示估计误差，`Delta u_i` 表示补偿亏损。 |
| 模式符号 | 证明中 `sigma` 与代码模式名可能不对应。 | 增加 `sigma_k in {N,R,S}` 到代码模式名的表格。 |
| 时延符号 | `tau` 可能与力矩或时间常数冲突。 | 通信时延写 `tau_{ij,k}^{comm}`；载荷力矩写 `M_z` 或 `m_{z,c}`。 |
| 通信图与扰动矩阵 | `G_k` 若表示通信图，会与证明中的扰动输入矩阵 `G_sigma` 冲突。 | 通信图固定为 `G_k=(V,E_k)`；证明扰动矩阵改写为 `D_sigma` 或 `W_sigma`。 |
| 控制链层级 | 方法写局部车控制，证明直接写团队闭环矩阵。 | 必须增加 `u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}->F_c` 桥接公式，再诱导 `A_sigma/B_sigma`。 |
| Koopman 矩阵与闭环矩阵 | `A,B` 可能同时指 Koopman 预测矩阵和团队闭环矩阵。 | Koopman 矩阵写 `A_K,B_K,\mathcal{B}_K`；闭环等效矩阵写 `A_sigma,B_sigma` 并说明来自组合映射局部线性化。 |
| 证书裕度 | `contraction_margin` 是上一上界减当前 `V`，不是 Lyapunov 下降量本身。 | 文字写“观测裕度与一阶上界一致”，不要写“严格证明每步下降”。 |
| 稳定投影 | `rho(A)<1` 是 Koopman 预测矩阵性质，不等于闭环稳定。 | 证明中把谱投影作为有界预测误差/名义收缩的支撑假设之一。 |

## 不可过强证明的稳定性表述边界

后续中文稿必须避免以下过强表述：

- 不写“全局渐近稳定”。当前 TF14 只适合局部工作域或任务工作域内的 practical boundedness、ISS-practical stability 或 UUB 表述。
- 不写“任意通信时延/任意丢包下稳定”。当前通信模型有最大离散时延、丢包概率和质量阈值，结论应限定在有界时延、非完全失联或可触发降级的条件下。
- 不写“400 ms 时延、40% dropout、leader-lost 等压力测试仍在主理论保证内”，除非补充 `G_k=(V,E_k)` 的窗口联合连通性、最大失联时长、最大时延和 MPC 可行性证明。
- 不写“未知执行器故障完全补偿”。应限定为效率估计误差有界、输入未严重饱和、健康车辆仍有补偿余量时保持团队误差最终有界。
- 不写“安全约束严格保证所有载荷力/法向载荷始终在界内”。若没有控制不变集或硬约束证明，只能写约束感知、限幅、证书监测和仿真验证。
- 不写“证书 ok ratio 为 1 就证明理论成立”。证书是仿真记录，说明该运行与 Lyapunov 型上界一致，不能替代数学证明。
- 不写“实时 MPC 全局最优”。当前是预算感知短时域、有限迭代和可跳步求解，应写为实时可部署的近似 MPC 控制栈。
- 不写“在线自适应始终启用并带来主实验收益”，除非最终主实验配置确实启用并有消融证据。
- 不写“局部指数稳定”或“渐近收敛”作为正文稳定性结论；若需要讨论理想无扰动名义收缩，只能作为附加解释，并且不得替代 practical boundedness / ISS-practical stability / UUB。

推荐稳定性结论边界：

> 在工作域紧致、MPC 局部可行、输入约束紧、Koopman 预测残差有界、通信时延/丢包满足给定上界或窗口联合连通性、执行器效率估计误差有界且切换满足最小驻留时间的条件下，TF14 切换容错闭环满足输入到状态实用稳定性或统一最终有界性。团队误差最终进入一个由模型残差、通信退化、执行器辨识误差和求解误差共同决定的有界邻域；边界外压力测试只能作为经验鲁棒性证据，不扩大上述理论保证。

## 后续修改中文稿时的文件级安全策略

| 安全策略 | 执行要求 |
|---|---|
| 不覆盖源 DOCX | 不直接修改 `manuscript_zh_literature_update_figures_tf14_lyapunov_2026-05-10.docx`，必须另存为带主题和日期的新文件。 |
| 单 worker 单文件边界 | 并行阶段 Worker C 只产出本 Markdown；后续主 agent 集成时再统一修改 DOCX，避免 worker 互相覆盖。 |
| 修改前确认基线 | 集成前重新确认最新中文稿文件名、修改时间和大小，避免基于过期 DOCX 写入。 |
| 结构化编辑 | 使用 `python-docx`、Word COM 或同等结构化工具定位章节，不用手工批量替换整篇正文。 |
| 公式安全 | 复杂公式优先渲染为高分辨率公式图片或可靠 OMML，避免把 LaTeX 片段、上标下标乱码或纯文本公式直接贴进 DOCX。 |
| 版本化输出 | 建议输出名形如 `manuscript_zh_literature_update_figures_tf14_method_theory_consistent_2026-05-10.docx`，并保留原稿。 |
| 表格安全 | 新增参数表、符号表、模式表后检查列宽、换行、跨页和中文字体，避免破坏现有排版。 |
| 图文边界 | Worker C 不插入新图；若方法文字引用图号，必须与 Worker D 的最终图件计划一致后再定稿。 |
| 交叉引用复核 | 修改方法和证明后统一复核章节号、公式号、表号、图号、算法名和变量名。 |
| 导出验证 | DOCX 集成后导出 PDF，抽查方法和证明页的公式、表格、分页、图注和参考文献引用。 |
| 差异审查 | 集成完成后保留变更摘要，重点标出方法符号、证明假设、稳定性边界和未解决待确认数值。 |

## Worker C 交付清单

- 本文件给出系统模型、坐标系/符号、离线数据生成、TF14 Koopman 网络、MPC、通信补偿、FTC/安全和 Lyapunov 证明八个方法章节的补全任务。
- 本文件补入 Reviewer 2 要求的闭环链条门禁：`u_i^{mpc}->u_i^{comm}->u_i^{ftc}->u_c^{agg}` 必须先诱导团队闭环，再进入 `A_sigma/B_sigma` 证明抽象。
- 本文件把通信压力测试边界与主方法保证分离，要求 400 ms、40% dropout、leader-lost 等必须标为边界外压力测试或补充 `G_k/E_k` 有界连通性假设。
- 本文件将 online adaptation 降级规则写入验收标准：主 preset 关闭时只能作为接口/补充模块，作为贡献时必须有 paired ablation。
- 本文件显式标出 method 与 proof 的符号一致性风险。
- 本文件新增符号硬门禁，要求 `q/Gamma/delta/tau/x/z/G/A/B` 在最终符号表中唯一化。
- 本文件显式限定稳定性证明不可过强表述的边界。
- 本文件给出后续中文 DOCX 集成时的文件级安全策略。

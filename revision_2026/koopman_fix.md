# Koopman纠错与创新复验执行书

> 编写时间：2026-09-02（Asia/Shanghai）  
> 授权模式：仅编写方案；本轮未修改5080项目代码，未启动或续跑实验  
> 执行机器：5080工作站 `DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 历史结果：`revision_2026\koopman_predict_v3_results\runs\20260902_115833_KOOPMAN_V2_GDM_RK_R01`  
> 本地审查副本：`D:\PDxc\Review\_koopman_v3_results`  
> 历史源码审查副本：`D:\PDxc\Review\_koopman_p5_dev\koopman_predict_v3`  
> 新候选版本：`revision_2026\koopman_predict_v3r`  
> 远端任务书冻结副本：`revision_2026\koopman_fix.md`（执行前由本地文件同步并核对SHA256）  
> 第一次执行授权边界：以后即使用户说“按此执行”，默认也只允许完成 `F0→F4`，F4结束后无论通过与否均人工停止；未经再次授权不得读取新验证集、旧confirm或进入MPC/网络实验。

---

## 0. 先给结论

当前结果不能简单解释成“GDM-RK失败”或“CVaR无效”。已经确认的是：

1. 历史P5B按预注册D5逐折门停止，这个停止动作本身正确；
2. 历史A2在train-family五折上表现最好：20步总体改善约`9.13%`，D5困难窗改善约`22.16%`，但它当时被定义为不可入选消融；
3. C16/C32的当前批内CVaR版本没有取得D5逐折一致性；
4. 历史执行同时存在最佳检查点未恢复、停止步冒充最佳步、A1训练预算不等、旧检查点跨源码复用、AF读取validation、原始证据不完整等问题；
5. 因此下一步必须先做**证据链纠错和等预算复验**，再判断方法优劣。不能直接从旧P5B进入P5C，也不能先扩大维数、增加专家或调低验收门槛。

本任务书采用三层路线：

```text
F层：修正实验基础设施并从零复验
  └─ 回答“多时域、闭合约束、旧CVaR分别是否有效”

M层：只对F层证明有效的主候选做机制消融
  └─ 回答“分组编码、阻尼模态、必要时的新尾部机制分别贡献什么”

V/C层：冻结唯一方法后做全训练、多seed、新验证集和一次confirm
  └─ 回答“是否能成为论文正式方法”
```

---

## 1. 历史错误清单及其后果

下表中的“错误”指实验实现、证据链或结论边界错误，不等于模型理论必然错误。

| ID | 已确认问题 | 现场依据 | 后果 | 本轮约束/修复 |
|---|---|---|---|---|
| E01 | 早停只更新`best_fold_value`，未保存、恢复最佳模型 | `src/train.py::train_multihorizon()`只在当前模型上累计耐心，退出时保存当前状态 | 最终评价的是停止步模型，可能制造错误退化 | 必须分别保存`best.pt`和`last.pt`，评价前强制加载`best.pt` |
| E02 | CSV中的`best_step`实际是`trace[-1].step`，即停止步 | `scripts/run_v3.py`旧实现 | “五折最佳步数中位数”名不副实 | 同时记录`best_step`、`stop_step`、`best_metric`；三者不可混用 |
| E03 | 早停只看随机抽取的256个折内窗口 | `_fold_batch_from_entries(..., count=256)` | 稀少的D5困难窗可能完全未进入监控集 | 新复验用完整折指标或冻结的分层监控集；必须保存覆盖表 |
| E04 | 续跑没有恢复最佳值、耐心计数和完整随机数状态 | 旧checkpoint只保存模型、优化器、step和curve | 中断续跑不等价于连续训练 | checkpoint必须保存早停状态、Python/NumPy/Torch CPU/CUDA RNG和sampler位置 |
| E05 | 只要发现checkpoint就跳过训练，未区分“中间检查点”和“折已完成” | 旧P5B runner的`if resume_ckpt.exists(): load` | 部分训练可能被当成完整训练 | 只有存在独立`fold_complete.json`且所有身份匹配才允许跳过；否则从last继续 |
| E06 | 修复A2/AF/续跑代码后复用了较早的C16/C32检查点 | 5080工作记录和目录时间：C16/C32早于16:04源码修复，A2晚于修复 | A2与C16“只差CVaR”的因果对照不再是单一源码身份 | 新run不得复制任何旧`.pt`；全部候选从同一warm checkpoint重新开始 |
| E07 | 同一stage重跑会覆盖该stage的source manifest | P5B第二次启动后的manifest对应新源码，而部分模型来自旧源码 | 单一manifest无法绑定全部模型 | 每次尝试使用新run或`attempt_###`；manifest、complete、decision均只写一次且不可覆盖 |
| E08 | AF压力测试直接读取旧validation的D5 | `src/evaluation_v3.py::stress_rollout()`读取`data.validation`；`af_stress.json`明确写明validation | 旧validation已不是完全未见数据 | 旧validation永久降级为开发证据；新验证集另建，AF只能用train-CV折 |
| E09 | 日志写“不得读取validation”，与AF实际读取冲突 | `development_log_append.md`与`af_stress.json`冲突 | 人工日志不能作为可信数据边界证明 | 引入机器生成`split_access.jsonl`；日志必须引用访问账本，不允许凭印象填写 |
| E10 | A1仅训练2000步；A2/C16/C32在相同暖启动后又最多训练15000步 | `_train_one()`中`one_step_only`直接返回 | A1与A2差异同时包含目标函数和6—8倍训练预算，不能单独归因于多时域训练 | 所有训练型候选统一`2000+最多15000`个优化步；A1第二阶段继续一步目标 |
| E11 | 当前CVaR加权后长期占总损失约63%—66%，多时域主损失仅约16%—17% | P5A `loss_scale.json`与`smoke_trace.json`复算 | 尾部项可能压过主要预测目标 | 必须逐步保存原始值、加权贡献和占比；旧CVaR原样复验，新尾部方法设置贡献上限 |
| E12 | 当前CVaR取每个普通batch中20步误差最差10%，不按工况或风险组分层 | `losses.py::cvar_tail()`和普通family-balanced batch | 不保证D5困难窗或切换窗进入尾部集合 | 必须保存tail成员ID/工况/窗口类型；若启用新尾部机制，使用训练集内分层风险组 |
| E13 | CVaR分位数和最小样本数在代码中硬编码`0.90/4` | `train.py::_step_loss()` | 修改配置文件不一定改变实际执行，存在配置漂移 | 所有数值从冻结protocol读取，启动时打印并写入resolved config |
| E14 | `cv_results.json`的`rows_by_fold=null`，本地交付无折内逐窗结果、模型和P5B源码manifest | `_koopman_v3_results\p5b` | 无法独立复算P95/P99、分工况、力、横摆和最坏轨迹 | 每折必须保存逐窗CSV/Parquet、模型、曲线、身份和产物manifest；摘要不能替代原始表 |
| E15 | AF只有中央seed的10/20/40步不发散，没有与阻尼F做等条件精度对照 | `af_stress.json` | 不能声称阻尼F经验上优于自由F | M层做成对、同seed、同折比较；若自由F也稳定，只保留结构性结论 |
| E16 | `rho(F)<1`被误用时容易扩大成整体稳定 | `rho(A0)=rho(K)≈1.004885>1` | 不能证明整体渐近稳定 | 论文只能声称“新增残差模态Schur稳定”；整体只报告有限时域误差/增益/发散 |
| E17 | AF用宽泛`except Exception`吞掉实现、数据和协议错误 | 旧P5B runner | 真正的软件错误可能被包装成“可忽略消融失败” | 仅允许捕获明确的数值发散异常；身份、数据、维数、访问边界错误必须阻塞主流程 |
| E18 | 当前P5B目录引用了未随本地结果一起交付的解决方案文件 | `development_log_append.md`引用`results/solutions_p5b_blocked.md` | 证据包不闭合 | 交付前运行artifact审计；任何引用路径缺失则stage不得标PASS |

### 1.1 这些错误改变了什么判断

- 历史CSV仍然是重要诊断信号，但不能作为论文最终统计证据；
- “A2优于A1”目前只能说是相关结果，不能严格归因于多时域目标，因为训练预算不同；
- “A2优于C16所以CVaR有害”是强烈线索，但跨源码/旧检查点复用使它尚未达到严格单因素消融；
- P5B硬门停止应保留，但不能把它解释为已经证伪整个GDM-RK结构；
- 旧validation不得再作为第一次独立验证集使用，尤其不能继续使用已暴露的D5四个base family。

---

## 2. 强制行为约束

以下规则对执行本任务书的AI、脚本和人工操作同样生效。任何一条被违反，本轮证据默认无效。

### 2.1 每次动作前必须回答的六个问题

执行AI在运行任何命令前，必须在工作记录中写清：

1. 当前任务编号是什么；
2. 当前允许读取哪些split；
3. 当前允许修改哪些目录和文件；
4. 当前源码、协议、任务书和数据manifest的SHA256是什么；
5. 本命令的预期输入、输出、退出码和硬门是什么；
6. 失败时保存什么、停止在哪里。

答不全时不得先运行再补记录。

### 2.2 永久禁止行为

1. 禁止修改或覆盖历史`koopman_predict_v3*`结果、模型、CSV、日志和complete文件；
2. 禁止在新源码下加载旧run的任何`.pt/.pth/.ckpt`；
3. 禁止把“存在checkpoint”解释为“任务完成”；
4. 禁止删除失败折、失败seed、D5或不利工况后重新求平均；
5. 禁止查看validation/confirm后修改模型、损失、维数、训练步数、阈值或随机种子；
6. 禁止以“结果差一点”为理由把3%改成5%、增加64/96/128维或增加专家；
7. 禁止把普通均值改善用来覆盖单一工况的明显退化；
8. 禁止只保存PNG而不保存生成PNG的原始表、配置和脚本；
9. 禁止把无NaN/Inf或40步不发散写成“系统稳定”；
10. 禁止把潜在变量称为真实物理模态，除非另有可识别性和对应关系证据；
11. 禁止用旧validation做AF、超参数选择、早停、阈值标定或故障诊断；
12. 禁止在核心流程中使用`except Exception: continue/pass`；
13. 禁止手工改CSV、JSON数值或complete状态；
14. 禁止两个训练进程同时写同一个run、fold或GPU输出目录；
15. 禁止任务书未授权的MPC、网络、DoS、门控专家或新物理模型实验混入本轮。

### 2.3 修复权限分级

| 级别 | 例子 | AI是否可自动修复 | 修复后要求 |
|---|---|---|---|
| A：机械实现问题 | 缺少import、路径转义、`.cpu()`遗漏、JSON序列化、绘图字体、明确维数包装错误 | 可以，一次只修一个根因 | 记录diff和SHA；重新跑受影响单测与当前stage；不得复用不匹配checkpoint |
| B：实验语义问题 | 损失、采样器、早停指标、模型结构、数据split、训练步数、阈值、seed | 仅本任务书明确写出的改动可做；其余必须停止 | 新protocol、新run，从受影响最早阶段重跑 |
| C：研究边界问题 | 改植物、删工况、读取confirm调参、增加专家/维数、修改论文主张 | 不可自动修复 | 写`solutions.md`并等待用户授权 |

### 2.4 小故障的允许处理

- SSH瞬断、文件暂时占用：原命令最多重试2次，每次等待不超过30秒；不改变参数；
- OOM：只允许`micro_batch 64→32→16`，同时`accumulation 4→8→16`，保证有效batch仍为256；每次变更写日志；仍OOM则停止；
- smoke阶段出现非有限梯度：保存首个失败batch和模型状态；仅允许使用预注册学习率`3e-4→1e-4`重做smoke；正式CV开始后出现NaN/Inf不得现场降学习率救回；
- 进程被外部中断：只有checkpoint内任务书/源码/数据/protocol SHA、fold、variant、seed、步数、RNG状态全部匹配才允许同run续跑；
- 绘图失败不应重训模型；修复绘图后只从冻结原始表再生成；
- 磁盘不足、数据行数不符、访问未授权split、身份不符：立即BLOCKED，不得自动绕过。

### 2.5 状态机

每个stage只能处于：

```text
NOT_RUN → RUNNING → PASS
                 └→ BLOCKED
```

- `complete.json`只在全部硬门通过后原子写入；
- 失败写`blocked.json`和`solutions.md`，不得同时存在伪PASS的`complete.json`；
- PASS文件一旦写入不可覆盖；重做必须创建新run/attempt；
- 下一stage启动前必须读取前一stage的不可变complete和产物manifest；
- 任一硬门失败，后续stage保持`NOT_RUN`。

---

## 3. 目标、非目标与论文声明边界

### 3.1 本轮目标

1. 在公平训练预算和单一源码身份下重新验证一步训练、多时域训练、闭合约束和旧批内CVaR；
2. 找到最简单、可重复通过20步总体和D5门的L16候选；
3. 通过分组编码、阻尼F及必要时的分层尾部机制消融，说明每个模块的作用区间；
4. 在全新未见validation和最终confirm上验证，形成可以回答“20步提升是否显著、为何提升、何处仍会退化”的证据链；
5. 保存逐窗、逐场景、逐seed、力/内部力/横摆和有限时域稳定性证据。

### 3.2 本轮非目标

- 不修改四车—货物植物、连接器、ICR、轮胎或执行器模型；
- 不引入通信干扰、DoS、MPC闭环和控制保护；
- 不做64/96/128维盲目扩容；
- 不证明整个增广系统渐近稳定；
- 不用材料强度或“货物撕裂安全”作为预测模型结论；
- 不在本轮增加多专家门控。只有单模型路线被独立证据证明不足且用户另行授权时，才可重开专家路线。

### 3.3 论文结论分级

| 已完成层级 | 允许写入论文 | 禁止写法 |
|---|---|---|
| F4 train-CV通过 | “在训练族交叉验证中表现出一致趋势” | “在未知工况上显著优越” |
| M层通过 | “消融支持某模块在指定指标上的作用” | “模块具有普适物理最优性” |
| V层新validation通过 | “在独立验证集和五seed上改善” | “最终泛化已确认” |
| C层confirm通过 | “在预留确认集上复现主要结论” | “全工作域绝对稳定/永不退化” |

---

## 4. 假设与可证伪预测

| ID | 假设 | 支持条件 | 反证条件/处理 |
|---|---|---|---|
| H1 | 等预算直接多时域训练优于一步训练 | MH16相对ONE16的`J20`改善至少5%，至少4/5折同向，D5不突破3%退化门 | 失败则不能把历史A2收益归因于多时域目标 |
| H2 | Koopman闭合约束提高滚动一致性 | MHC16相对MH16的20步或40步误差改善至少2%，且任一场景不退化超过3% | 效果不足则删除闭合项，采用更简单MH16 |
| H3 | 旧批内CVaR在当前权重下不能稳定保护D5 | BCV16相对MHC16在D5逐折不一致，或总体代价超过1% | 若反而稳定通过，则保留旧CVaR，不再为得到“创新”强做新尾部项 |
| H4 | 若仍存在尾部缺陷，分层且贡献受控的尾部损失可改善D5/P95而不牺牲总体 | 新SCV相对同采样无尾部对照：D5均值改善≥3%、P95改善≥5%、总体退化≤1% | 失败即删除SCV，不再调权重救结果 |
| H5 | 阻尼F的主要价值是限制新增残差模态，而不一定提高均值精度 | 阻尼F满足`rho(F)<0.995`且40/80步无新增发散；自由F若出现更高P99/增益则形成经验支持 | 若自由F同样稳定且更准，只能保留结构证书或选自由F，不能伪造稳定性优势 |
| H6 | 最终L16候选能够在新validation复现至少5%的20步总体改善 | validation五seed至少4个同向、配对CI下界>0、D5和各场景门通过 | 任一主门失败则停止，不得回到validation调参 |

阈值均在运行前冻结。M层的2%/3%/5%是研究上的最小可辨识改进门，不是实物安全阈值。

---

## 5. 模型、损失与指标公式

### 5.1 冻结物理主干和残差升维

使用当前47维归一化状态、7维控制和冻结S0主干：

\[
x_{k+1}=A_0x_k+B_0u_k+b_0+E\eta_k,
\]

\[
\eta_{k+1}=F\eta_k+Gu_k+c.
\]

`A0/B0/b0`必须为buffer且`requires_grad=False`。训练前后逐字节SHA必须一致。

分组编码继续使用：

\[
\eta_k=
\begin{bmatrix}
\phi_d(g_0,g_1,g_2,u_k)\\
\phi_c(g_2,g_3,u_k)
\end{bmatrix},
\]

其中`g2`同时进入车辆动力学支路和连接器支路，因为它是二者的耦合量。场景标签、未来状态和未来误差不得进入编码器。

阻尼模态：

\[
F_j=r_j
\begin{bmatrix}
\cos\omega_j&-\sin\omega_j\\
\sin\omega_j&\cos\omega_j
\end{bmatrix},
\quad
r_j=0.995\,\sigma(a_j)<0.995.
\]

完整线性块为：

\[
K=\begin{bmatrix}A_0&E\\0&F\end{bmatrix},
\quad
\sigma(K)=\sigma(A_0)\cup\sigma(F).
\]

因此只能证明残差模态不新增更大的特征值，不能消除`rho(A0)>1`。

### 5.2 分组多步误差

对预测时域`h∈{1,5,10,20}`：

\[
\ell_h=\sum_{q=0}^{3}w_q
\sqrt{\frac{1}{N_q}\left\|\hat x^{(q)}_{k+h}-x^{(q)}_{k+h}\right\|_2^2},
\]

\[
(w_0,w_1,w_2,w_3)=(0.3,0.2,0.2,0.3).
\]

多时域主损失：

\[
\mathcal L_{MH}=0.10\ell_1+0.20\ell_5+0.25\ell_{10}+0.45\ell_{20}.
\]

闭合损失：

\[
\mathcal L_{cl}=\frac{1}{4}\sum_{h\in\{1,5,10,20\}}
\left\|\eta_{k+h}^{prop}-\operatorname{sg}(\phi(x_{k+h},u_{k+h}))\right\|_2^2.
\]

冻结训练集初始尺度`m_cl`后：

\[
\widetilde{\mathcal L}_{cl}=\mathcal L_{cl}/\max(m_{cl},\epsilon).
\]

### 5.3 纠错复验的四个核心候选

全部先使用L16、相同初始化、相同2000步暖启动、相同第二阶段最多15000步、相同主batch序列。

| 新名称 | 历史对应 | 第二阶段目标 | 用途 |
|---|---|---|---|
| ONE16 | 修正后的A1 | `L=ell_1+R`，继续训练15000步 | 公平的一步训练基线 |
| MH16 | 新增干净消融 | `L=L_MH+R` | 隔离直接多时域作用 |
| MHC16 | 历史A2的语义 | `L=L_MH+0.10*L_cl_tilde+R` | 验证闭合约束增量 |
| BCV16 | 历史C16的语义 | `L=L_MH+0.10*L_cl_tilde+0.25*T_batch_tilde+R` | 原样复验旧批内CVaR |

其中`R`是完全相同的预注册正则；必须单独记录E正则和其他参数正则，避免E被无意重复惩罚。若保留双重惩罚，需在protocol中明确，而不能隐藏在代码里。

旧批内尾部项：

\[
T_{batch}=\frac{1}{|S_{0.9}(B)|}\sum_{i\in S_{0.9}(B)}e_{20,i},
\]

其中`S_0.9(B)`为当前batch内误差最高10%的样本，至少4个样本。每一步必须保存或可重放tail成员的窗口ID、scenario、window class和base family。

### 5.4 仅在需要时启用的新分层尾部机制

如果MHC16已经满足D5、P95和最坏工况门，则不运行SCV，不为增加复杂度而增加模块。

若MHC16总体通过但仍有尾部缺陷，将训练窗口按以下优先级划为互斥风险组：

```text
R0：D5且window_start∈{100,120}
R1：connector_event，且不属于R0
R2：switch，且不属于R0/R1
R3：maneuver，且不属于R0/R1/R2
R4：steady
```

任何窗口必须且只能属于一个风险组。分组只用于训练采样和损失审计，不得作为推理输入。

对每组：

\[
T_g=\operatorname{CVaR}_{0.90}\{e_{20,i}:i\in B_g\},
\qquad
T_{strat}=\frac{1}{5}\sum_{g=0}^{4}T_g.
\]

为了避免尾部项再次压过主目标，使用停止梯度的贡献上限：

\[
s_k=\min\left(
1,
\frac{\gamma\,\operatorname{sg}(\mathcal L_{MH})}
{\lambda_T\,\operatorname{sg}(\widetilde T_{strat})+\epsilon}
\right),
\]

\[
\mathcal L_{SCV}=\mathcal L_{MH}
+0.10\widetilde{\mathcal L}_{cl}
+s_k\lambda_T\widetilde T_{strat}
+\mathcal R,
\]

其中`lambda_T=0.25`、`gamma=0.25`、`epsilon=1e-12`固定。由构造应满足：

\[
s_k\lambda_T\widetilde T_{strat}\le0.25\mathcal L_{MH}
\]

（允许`1e-6`相对数值误差）。

为隔离“分层采样”和“尾部损失”，必须成对运行：

- `MHC16-S`：相同风险分层batch，但尾部系数为0；
- `SCV16-S`：完全相同batch、初始化和步数，启用上述SCV。

如果只运行SCV而没有`MHC16-S`，不得把收益归因于新尾部损失。

### 5.5 主要评价指标

主指标：

\[
J_h^{macro}=\frac{1}{12}\sum_{s=D0}^{D11}J_{h,s}.
\]

相对改善：

\[
I=100\%\times\frac{J^{S0}-J^{cand}}{\max(|J^{S0}|,10^{-12})}.
\]

同时报告：

- `h=1/5/10/20`总体和D0—D11逐工况；
- D5起点100/120的均值、P95、P99和最大值；
- 四点连接力、完整内部力、车辆/系统横摆、货物状态和执行器状态；
- 发散率、最大归一化绝对值、latent范数和有限时域输入增益；
- 参数量、训练时间、峰值显存、CPU/GPU推理时间。

---

## 6. 版本隔离、数据边界与新目录

### 6.1 禁止写入的历史目录

```text
revision_2026\koopman_predict_v3
revision_2026\koopman_predict_v3_results
revision_2026\koopman_predict_v3_models
revision_2026\koopman_predict_auto*
revision_2026\koopman_predict_v2*
历史672条正式数据及旧confirm
```

### 6.2 新目录

```text
revision_2026/
├─ koopman_fix.md
├─ koopman_predict_v3r/
├─ koopman_predict_v3r_data/
├─ koopman_predict_v3r_models/
└─ koopman_predict_v3r_results/
   ├─ work_log.md
   ├─ stage_status.json
   ├─ decision_log.jsonl
   └─ runs/<run_id>/
```

复制源码时只复制代码、配置和测试，不复制旧results、models、checkpoint、cache中的预测结果。创建前必须确认目标目录不存在；若已存在，不得覆盖，改用新run或等待用户裁决。

### 6.3 数据使用矩阵

| 阶段 | train | 旧development | 旧validation | 新validation | confirm |
|---|---:|---:|---:|---:|---:|
| F0身份核验 | 只读manifest/计数 | 只读历史摘要 | 只记录“已污染”，不读数值 | 只生成并封存manifest | 禁止 |
| F1—F4 | 允许 | 禁止用于选择 | 禁止 | 禁止 | 禁止 |
| M0—M2 | 允许train-CV | 禁止 | 禁止 | 禁止 | 禁止 |
| V0 | 不再改方法；用于full-train | 禁止 | 禁止 | 唯一一次评价 | 禁止 |
| C0 | 冻结模型，不训练 | 禁止 | 禁止 | 不再查看调参 | 唯一一次评价 |

旧validation已经因AF读取D5而污染。默认方案是使用冻结的数据生成器和同一参数分布，新建48个base family、168条轨迹的新validation，seed起点固定为`991000`。生成完成后只允许读取manifest、数量和SHA，不允许读取状态值、标签分布统计以外的性能信息。

如果无法生成同分布的新validation，立即停止并写解决方案。不得把旧validation重新命名为“未见验证集”，也不得提前拿confirm代替调参集。

### 6.4 固定随机数

- 训练族五折划分：继续使用`cv_seed=990700`，避免结果出来后换折；
- 各折网络/采样配对seed：`990100+fold`；
- full-train主seed：`990101—990105`；
- paired family bootstrap：`990500`，2000次；
- 所有候选在同一fold必须共享初始化warm checkpoint和主batch顺序。

---

## 7. 代码修改清单

所有修改只发生在新`koopman_predict_v3r`目录。

| 文件 | 函数/类 | 必须修改的内容 | 输入 | 输出 | 单元测试 |
|---|---|---|---|---|---|
| `src/train.py` | `EarlyStopState`（新增） | 保存best metric/step/state、stop step、patience和比较方向 | 完整折指标 | 可序列化状态 | 合成损失先降后升时恢复已知最佳步 |
| `src/train.py` | `train_objective()`（重构） | ONE/MH/MHC/BCV共用同一训练循环；支持等预算、完整恢复和RNG保存 | model/dataset/objective spec | best/last checkpoint、curve | 四候选优化步上限相同；resume与连续训练逐元素一致 |
| `src/train.py` | `_step_loss()` | 所有量从protocol读取；输出raw/weighted/share；不得硬编码quantile | batch/protocol | 结构化loss字典 | 修改protocol测试值时实际loss同步变化 |
| `src/losses.py` | `cvar_tail()` | 返回loss外，还返回top-k索引；处理各组样本不足 | per-sample errors | loss、member indices | 手算向量与top-k完全一致 |
| `src/losses.py` | `stratified_cvar()`（条件新增） | 实现互斥风险组和五组均值 | errors/group ids | group tails、总tail | 每组计数、互斥性和手算结果 |
| `src/data_contract.py` | dataset sample metadata | 为审计返回trajectory/base family/scenario/window class/start；元数据不进入网络tensor | cache entry | sample tensors+IDs | 无未来泄漏；ID与ledger一致 |
| `src/data_contract.py` | `SplitGuard`（可新文件） | 按stage限制split访问并写`split_access.jsonl` | stage/split/path | allow/deny记录 | F/M阶段读取validation必须抛错 |
| `src/sampler.py`（新增） | `FamilyBalancedSampler` | 保存/恢复完整采样器状态 | family IDs/seed | batch IDs/state | 中断续跑与连续序列完全一致 |
| `src/sampler.py` | `RiskStratifiedSampler`（条件新增） | 五互斥风险组，family-balanced，有放回情况显式记录 | train IDs/group IDs | 配对batch | 每batch配额、长期均衡、无validation ID |
| `src/checkpoint.py`（新增） | save/load/validate | checkpoint内写入源码、任务书、protocol、数据、variant、fold、seed、RNG和complete标志 | state+identity | `best.pt/last.pt` | 任一SHA不匹配拒绝加载 |
| `src/evaluation_v3.py` | `stress_rollout()` | 删除硬编码`data.validation`；只接收显式entries和允许split token | model/entries | stress rows | F/M传validation token必须失败 |
| `src/evaluation_v3.py` | fold evaluator | 保存逐窗1/5/10/20、力、内部力、横摆、latent和发散 | best model/fold entries | rows文件 | 行数公式、单位和分组闭合 |
| `src/provenance.py`（新增） | immutable manifest | attempt级身份冻结、原子写、禁止覆盖 | files/config/data | manifest+SHA | 二次写入必须报错 |
| `scripts/run_v3r.py` | stage runner | 实现F0—C0状态机；无上游PASS不得越级 | CLI args | stage artifacts | 人工构造失败门时不得进入下一stage |
| `scripts/run_v3r.py` | fold runner | 每折共享warm起点；只有fold_complete才能跳过；best模型评价 | variant/fold | models/rows/summary | partial checkpoint不会被误认为complete |
| `scripts/audit_artifacts.py`（新增） | artifact audit | 检查报告引用、SHA、行数、字段、模型和图是否齐全 | run root | audit JSON | 删除任一必要文件后门禁失败 |
| `scripts/plot_v3r.py` | plotting | 只读原始表生成图，附数据SHA和单位 | rows/summary | PNG/PDF+manifest | 图manifest可追溯 |
| `config/protocol_v3r.json` | 全配置 | 固定模型矩阵、预算、seed、split、门槛、损失和授权stage | — | resolved config | schema完整且无未知键 |
| `tests/test_checkpoint_selection.py` | 新增 | 验证best恢复、stop/best区分 | 合成curve | PASS | 必须覆盖先降后升 |
| `tests/test_resume_exact.py` | 新增 | 连续100步与50+resume50步逐元素一致 | 固定batch/seed | 参数/loss | 相对误差`<=1e-7` |
| `tests/test_split_guard.py` | 新增 | 禁止F/M读取validation/confirm；AF只能train fold | fake splits | PASS | 故障注入必须被拒绝 |
| `tests/test_equal_budget.py` | 新增 | ONE/MH/MHC/BCV最大步数、batch序列一致 | fake dataset | PASS | 任一候选少跑不得PASS |
| `tests/test_artifact_contract.py` | 新增 | 原始行、模型、curve、identity、complete成套 | fake run | PASS | `rows_by_fold=null`必须失败 |

### 7.1 检查点最小字段

```json
{
  "run_id": "...",
  "attempt_id": "...",
  "stage": "F4",
  "variant": "MHC16",
  "fold": 0,
  "seed": 990100,
  "source_manifest_sha256": "...",
  "taskbook_sha256": "...",
  "protocol_sha256": "...",
  "data_manifest_sha256": "...",
  "warm_checkpoint_sha256": "...",
  "step": 5000,
  "best_step": 3500,
  "stop_step": 5000,
  "best_metric": 0.0,
  "patience_counter": 1500,
  "rng_state": {},
  "sampler_state": {},
  "model_state": {},
  "optimizer_state": {},
  "is_fold_complete": false
}
```

模型大字段可存二进制，但同名JSON sidecar必须包含上述可审计元数据。

---

## 8. 实验矩阵与公平性

### 8.1 F4核心复验

| Variant | residual dim | encoder | F | 第二阶段损失 | 最大总步数 | 五折 |
|---|---:|---|---|---|---:|---:|
| S0 | 0 | 无 | 无 | 不训练 | 0 | 同折评价 |
| ONE16 | 16 | grouped | damped | one-step | 17000 | 5 |
| MH16 | 16 | grouped | damped | multi only | 17000 | 5 |
| MHC16 | 16 | grouped | damped | multi+closure | 17000 | 5 |
| BCV16 | 16 | grouped | damped | multi+closure+旧batch CVaR | 17000 | 5 |

每折先训练一个共同L16 warm checkpoint（2000步），再复制其模型和优化器状态进入四个第二阶段。不得分别暖启动造成不同起点。

### 8.2 M层条件消融

只有F4选出至少一个合格L16候选后才能运行：

| Variant | 与父模型唯一差异 | 是否必跑 | 目的 |
|---|---|---:|---|
| MONO16 | grouped encoder改为参数量匹配的单体encoder | 是 | 验证物理分组是否真有收益 |
| FREE16 | damped F改为自由稠密F | 是 | 验证阻尼结构的精度/稳定代价 |
| MHC16-S | 分层采样、无新tail | 仅H4触发 | 隔离采样效应 |
| SCV16-S | 在MHC16-S上增加分层受控tail | 仅H4触发 | 验证新尾部机制 |
| BEST32 | 最佳目标扩大到L32 | 条件运行 | 仅当L16有明确欠拟合证据时检查容量 |

`BEST32`进入条件必须同时满足：

1. L16无NaN/发散；
2. train与fold误差均较高且差距小，呈欠拟合而非过拟合；
3. 残差审计显示多个状态组系统性剩余误差；
4. 用户在F4报告后明确授权。

不满足时禁止因“想看看”扩大维数。

### 8.3 参数匹配要求

- MONO16的可训练参数量必须与grouped模型相差不超过2%；
- FREE16除F参数化外，初始化尺度、warm checkpoint、batch、优化器和步数完全相同；
- 所有成对比较按base family、窗口起点、方向、plant、seed配对；
- 若输入信息、数据量或训练预算不同，必须标为非公平探索，不得进入主表。

---

## 9. 顺序任务树

## F0 — 现场身份与旧错误冻结

**前置条件：** 用户明确授权执行本任务书；当前仅方案编写，尚未授权。

**执行引导：** F0是bootstrap现场审查，由执行AI使用PowerShell完成，不依赖尚未创建的`run_v3r.py`。开始前先把本地`D:\PDxc\Review\koopman_fix.md`同步为远端`revision_2026\koopman_fix.md`，核对两端SHA一致；随后为本次run创建唯一结果目录并写F0证据。F1才创建正式stage runner。bootstrap只允许复制任务书和创建空的新结果目录，不允许复制模型/checkpoint或修改历史源码。

**只读检查：**

1. 连接5080，核对hostname；
2. 核对项目根、Python解释器、CUDA、GPU、磁盘剩余空间；
3. 列出Python/MATLAB训练进程；不得终止未知进程；
4. 计算历史taskbook、protocol、source manifest、数据manifest和P5B关键文件SHA；
5. 保存本任务书SHA；
6. 把E01—E18写入新run的`known_issues.json`；
7. 将旧validation状态登记为`CONTAMINATED_D5_BY_AF`；
8. confirm访问计数必须仍为0。

**输出：**

```text
f0/environment.json
f0/processes.txt
f0/baseline_identity.json
f0/known_issues.json
f0/split_status.json
f0/complete.json
```

**硬门：**

- hostname、根目录、Python和CUDA可确认；
- 无身份不明的同项目训练进程；
- 历史结果和训练数据只读可访问；
- confirm未读取；
- D盘可用空间至少60 GiB；
- 新目录目标不会覆盖历史目录。

**失败：** 保存现场并停止；允许保留空的新结果目录和已冻结任务书，不创建候选源码、不开始训练。

## F1 — 隔离源码与基础设施修正

**动作：**

1. 创建`koopman_predict_v3r*`新目录；
2. 只复制历史源码、配置和测试；不复制任何模型与结果；
3. 按第7节完成best/last、resume、split guard、immutable manifest、raw evidence等修复；
4. 建立`protocol_v3r.json`，冻结模型矩阵和所有阈值；
5. 生成新validation的任务清单和seed，不运行模型、不查看预测性能；
6. 保存代码diff、源manifest和resolved protocol。

**硬门：**

- 历史目录SHA无变化；
- 新源码manifest唯一；
- 配置不存在代码硬编码覆盖；
- 无旧checkpoint进入新目录；
- `split_access.jsonl`只包含允许的manifest访问；
- 本任务书、protocol和源码身份写入所有后续入口。

**失败：** 一次只修一个A级根因；涉及B/C级未授权变更立即停止。

## F2 — 单元测试与故障注入

**必须测试：**

1. 当前全部历史测试；
2. best checkpoint先降后升恢复；
3. `best_step != stop_step`时报告字段正确；
4. 连续训练与中断续跑等价；
5. 部分checkpoint不能冒充fold complete；
6. 源码/protocol/data/seed任一不匹配时拒绝resume；
7. F/M读取旧/新validation或confirm必然失败；
8. AF传入validation entries必然失败；
9. ONE/MH/MHC/BCV第二阶段预算均为15000；
10. tail top-k和group membership手算一致；
11. 删除原始rows、模型或manifest时artifact gate失败；
12. 人工制造D5退化、NaN和发散时选择门必须拒绝。

**硬门：** 所有测试100%通过；禁止用`xfail/skip`隐藏本轮新增测试。

## F3 — 小规模冒烟与损失审计

**数据：** 仅train中的固定D0和D5各一个base family；seed=`990100`。

**预算：** 共同warm 200步；四候选第二阶段各500步；有效batch=256。该结果仅检查工程正确性，不进入论文表。

**必须记录：**

- 每个候选的实际优化步数和相同batch ID SHA；
- `L_MH`、closure、tail、正则的原始值、加权值和占比；
- BCV每次tail成员的scenario/window class/D5-hard比例；
- A0/B0/b0训练前后SHA；
- F的各对半径、`rho(F)`和完整K的谱半径；
- best/last模型差异和恢复后评价；
- checkpoint连续/续跑下一批loss相对误差。

**硬门：**

- 无NaN/Inf，梯度和预测均有限；
- 四候选从同一warm SHA开始；
- A0/B0/b0逐字节不变；
- 阻尼F始终`rho(F)<0.995`；
- resume等价误差`<=1e-7`；
- best恢复测试通过；
- 未读取任何validation/development/confirm；
- 若BCV tail贡献仍超过主损失100%，只记录为预期诊断，不得在F3现场改权重，因为F4需原样复验历史BCV定义。

## F4 — 全新五折公平复验

**数据：** 仅96个train base family；折划分seed=`990700`；按base family分折，禁止窗口跨折。

**训练：** ONE16、MH16、MHC16、BCV16，每个5折；共同warm；float32训练；float64最终评价。

**检查点选择：**

每500步在完整 held-out train fold 上计算：

\[
Q_{CV}=0.10J_1^{macro}+0.20J_5^{macro}+0.25J_{10}^{macro}+0.45J_{20}^{macro}.
\]

以`Q_CV`最小作为best，耐心2000优化步。D5不进入best选择公式，而作为独立硬门，防止用单一困难工况完全支配模型选择。评价时必须重新加载best.pt。

**每折输出：**

```text
F4/<variant>/fold_<n>/
├─ warm_identity.json
├─ best.pt + best.json
├─ last.pt + last.json
├─ fold_complete.json
├─ train_curve.csv
├─ cv_curve.csv
├─ tail_members.parquet（BCV）
├─ rows.parquet
├─ summary.json
└─ artifact_manifest.json
```

逐窗`rows`至少包含：run/variant/fold/seed、trajectory/base family/scenario/direction/plant、window class/start、horizon、`J_common`、各状态组误差、四点力误差、完整内部力误差、车辆/系统横摆误差、货物误差、latent norm、normalized max abs、divergent。

**候选合格门：**

1. 五折全部有限、20步发散数为0；
2. 每折D5困难窗相对该折S0退化不超过3%；
3. `J20 macro`改善方向至少4/5折为正；
4. 五折汇总相对S0改善至少5%；
5. 任一D0—D11工况退化不超过3%（分母使用`max(J_s^S0,0.02)`）；
6. 四点力和完整内部力20步macro均不退化超过5%；
7. 原始rows可独立复算summary，绝对误差`<=1e-12`；
8. 访问账本确认validation/development/confirm读取数为0。

**模块判断：**

- MH16相对ONE16用于判断H1；
- MHC16相对MH16用于判断H2；
- BCV16相对MHC16用于判断H3；
- 模块增量不足2%且没有≥5%的D5/P95收益时，删除更复杂模块；
- 若多个候选差异不足1%，选择参数更少、训练更稳、推理更快者。

**第一次实际停止点：** F4结束后无论PASS/BLOCKED都停止，交付原始表、复算报告、失败原因和下一阶段建议。不得自动进入M层或validation。

## M0 — 机制消融（需要第二次授权）

**前置条件：** F4至少一个候选通过；方法损失、维数、训练步数已经冻结。

运行参数匹配的MONO16和FREE16五折。若F4最佳候选仍存在D5/P95缺陷且总体门通过，才同时运行`MHC16-S/SCV16-S`。

**阻尼F压力评价：** 只在held-out train fold上做20/40/80步，报告：

- 发散率和新增发散数；
- `rho(F)`、`rho(K)`；
- latent范数P50/P95/P99/max；
- 状态、力和内部力误差增长；
- 有限时域输入增益和最坏轨迹。

**模块纳入门：**

- grouped相对MONO：20步总体或力/内部力改善至少2%，且无场景退化超过3%；否则不声称分组带来精度优势；
- damped相对FREE：若精度差异小于1%且压力滚动更稳，可基于结构证书选择damped；若FREE更准且同样不发散，必须如实报告；
- SCV相对MHC16-S：D5困难窗均值改善≥3%、P95改善≥5%、总体退化≤1%、每折仍满足S0的3%门；否则删除SCV；
- 任一模块失败，不允许继续调`gamma/lambda/quantile`。

## M1 — 唯一候选冻结

按以下字典序选择：

1. 身份、数据边界、NaN/发散全部通过；
2. 每折D5和分工况退化门通过；
3. 20步macro及成对family CI更好；
4. 差异不足1%时选择更简单者；
5. 固定维数、结构、损失、训练步数（五折真实best step中位数）、seed和全部阈值；
6. 写`model_card.json`和`frozen_method.md`，之后任何代码变化都必须返回F0新run。

## V0 — 五seed全训练与全新validation（需要第三次授权）

**前置条件：** 唯一候选已冻结；新validation manifest已在F1封存且此前访问记录为0。

使用96个train family训练5个full-train模型，seed=`990101—990105`，固定步数来自M1；不在validation早停，不根据validation保存新checkpoint。

一次性打开新validation，评价S0和唯一候选。

**主门：**

1. `J20 macro`相对S0改善`>=5%`；
2. 2000次base-family配对bootstrap的95%CI下界`>0`；
3. 至少4/5个seed方向为改善；
4. `h=1/5/10`任一不退化超过3%；
5. D5整体及困难窗mean/P95/P99/max均不退化超过3%；
6. 任一D0—D11不退化超过3%；
7. 四点力和完整内部力20步不退化超过5%；
8. 1/5/10/20步发散率为0，40步相对S0无新增发散；
9. A0/B0/b0 SHA不变；
10. 单窗口20步GPU中位数<1 ms、P99<2 ms；CPU中位数<5 ms；若硬件调度导致不稳定，保存环境并重复同一计时协议，不改模型。

任一主门失败即停止。validation失败后不得返回M层改模型再看同一validation；如确需新方法，必须将该validation降级为开发集并另立新盲验证协议。

## C0 — 一次confirm（需要第四次授权）

**前置条件：** V0通过、论文方法和代码冻结、confirm访问计数仍为0。

只运行最终模型和S0一次，不训练、不调参、不补seed。确认主要改善方向、D5门、力/内部力和发散结论。失败也原样写入论文和报告。

---

## 10. 自动决策表

| 观察结果 | 正确动作 | 禁止动作 |
|---|---|---|
| MH16不优于等预算ONE16 | 停止“多时域目标有效”主张，检查数据/滚动结构 | 用历史不等预算A1结果覆盖 |
| MH16通过，MHC16无增量 | 选择MH16，closure作为负消融 | 为保持方法复杂度强留closure |
| MHC16通过且BCV16失败 | 选择MHC16作为主路线；仅在仍有尾部缺陷时触发SCV | 继续调旧CVaR直到过门 |
| BCV16稳定优于MHC16 | 保留旧CVaR，不运行SCV | 为追求“新公式”故意忽略成功结果 |
| 所有L16候选失败 | 保存失败并停止；检查模型能力/数据覆盖 | 直接扩到64/96/128维 |
| L16呈明确欠拟合 | 写证据并请求授权BEST32 | 只凭平均误差差就扩维 |
| FREE16同样稳定且更准 | 报告阻尼F只有结构边界或选择FREE | 声称阻尼F经验优势 |
| SCV改善D5但总体退化>1% | 判SCV失败 | 用D5单点遮住总体代价 |
| validation失败 | 停止并保留负结果 | 在同一validation上重新调参 |
| confirm失败 | 论文降级结论 | 更换confirm或删除失败family |

---

## 11. 运行命令模板

以下命令仅在用户以后明确授权后执行。任务书自身不写死自己的SHA；执行时由PowerShell计算本地文件SHA，复制到5080后再次计算并比较。SHA不一致不得进入F0。

本地控制机先冻结远端任务书副本（同步工具可按现场环境选择，下面使用`scp`示意；不得覆盖同名但SHA不同且已有run引用的远端任务书，应改用带版本的文件名并更新protocol）：

```powershell
$LocalTaskbook = 'D:\PDxc\Review\koopman_fix.md'
$TaskbookHash = (Get-FileHash -LiteralPath $LocalTaskbook -Algorithm SHA256).Hash
scp -- $LocalTaskbook '5080:D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/revision_2026/koopman_fix.md'
Write-Host "LOCAL_TASKBOOK_SHA256=$TaskbookHash"
```

F0由执行AI按本节的只读清单完成并写入新run。完成F1、正式runner存在后，使用以下模板执行F2—F4：

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PyExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$SourceRoot = Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3r'
$Protocol = Join-Path $SourceRoot 'config\protocol_v3r.json'
$Taskbook = Join-Path $ProjectRoot 'revision_2026\koopman_fix.md'
```

必须显式使用F0工作记录中创建的run ID：

```powershell
$RunId = '<F0_RETURNED_RUN_ID>'
& $PyExe -m pytest (Join-Path $SourceRoot 'tests') -q
& $PyExe (Join-Path $SourceRoot 'scripts\run_v3r.py') --stage F2 --project-root $ProjectRoot --protocol $Protocol --taskbook $Taskbook --resume-run $RunId
& $PyExe (Join-Path $SourceRoot 'scripts\run_v3r.py') --stage F3 --project-root $ProjectRoot --protocol $Protocol --taskbook $Taskbook --resume-run $RunId
& $PyExe (Join-Path $SourceRoot 'scripts\run_v3r.py') --stage F4 --project-root $ProjectRoot --protocol $Protocol --taskbook $Taskbook --resume-run $RunId
```

`--resume-run`只表示同一身份run继续下一个stage，不授权加载历史v3模型。如果身份校验失败，命令必须返回非零退出码并停止。

### 11.1 资源预计

- F0—F2：约10—30分钟；
- F3：约10—20分钟；
- F4：20个第二阶段折模型，预计4—8小时，实际以首折记录外推；
- M0：按触发模块增加10—20个折模型；
- V0：5个full-train模型，预计2—5小时；
- 至少保留60 GiB磁盘；每个stage开始前重新检查。

时间估计只是资源计划，不是通过条件。若首折外推总耗时超过12小时，先交付成本评估并人工决定，不得擅自减seed/折数。

---

## 12. 原始产物和图表要求

### 12.1 必须产物

1. `identity.json`：源码、数据、任务书、protocol、环境和命令SHA；
2. `split_access.jsonl`：每次split访问的时间、stage、调用栈摘要、用途和行数；
3. `train_curve.csv`：各原始/加权损失、占比、梯度范数、学习率；
4. `cv_curve.csv`：每个检查点的完整折`Q_CV`、J1/5/10/20、D5；
5. `rows.parquet/csv`：逐窗、逐时域、逐物理组结果；
6. `tail_members.parquet`：BCV/SCV尾部成员；
7. `checkpoint_manifest.json`：best/last/warm SHA和身份；
8. `fold_summary.csv`、`scenario_summary.csv`、`horizon_summary.csv`；
9. `paired_bootstrap.csv/json`；
10. `artifact_manifest.json`：所有文件大小和SHA；
11. `complete.json`或`blocked.json`，二者只能有一个；
12. 持续追加的`work_log.md`和失败时的`solutions.md`。

### 12.2 必须图

1. 1/5/10/20步误差增长曲线，带折/seed置信带；
2. D0—D11 20步改善热图，正负值同一色标；
3. D5起点80/100/120/140的均值、P95、P99和最大值；
4. D5最坏轨迹的真实/预测状态、四点力、内部力、车辆/系统横摆；
5. ONE/MH/MHC/BCV损失贡献占比，特别标出tail是否支配；
6. BCV/SCV尾部成员的风险组组成；
7. damped/free F的latent范数和20/40/80步误差增长；
8. 参数量—推理时间—J20 Pareto图；
9. 最佳步和停止步对照图，证明评价确实加载best。

图必须写单位、样本范围、seed、split、数据SHA。任何图的数值必须可以从保存的原始表重新生成。

---

## 13. 工作记录格式

每完成一个最小动作立即追加，不允许实验结束后凭记忆补写：

```markdown
## KFIX-<stage>-<seq> — YYYY-MM-DD HH:mm — 标题

- 请求/任务编号：
- 授权边界：
- 主机/项目根：
- 当前stage与允许split：
- 基线身份：taskbook/source/protocol/data SHA
- 读取：
- 修改：
- 代码diff SHA：
- 命令：
- 退出码：
- 进程与资源：
- 原始产物：
- 关键结果（数值、单位、样本范围）：
- 结论类型：事实/推断/建议/未知
- 状态：PASS/PARTIAL/BLOCKED/NOT_RUN
- 触发的硬门：
- 停止原因：
- 下一允许动作：
```

不得把计划任务记成已完成，不得把`BLOCKED`改写成“基本通过”。

---

## 14. 失败与解决方案模板

发生任何硬门失败时，在当前run写`solutions.md`：

```markdown
# 阻塞问题解决方案

## 阻塞点
- stage/fold/variant/seed：
- 首次时间：
- 失败状态和退出码：
- 已停止的后续任务：

## 已确认事实
- 原始错误、首个失败batch、指标和身份：

## 根因候选
| 候选 | 支持证据 | 反对证据 | 最小诊断 |
|---|---|---|---|

## 可选修复
| 方案 | 修改范围 | 是否改变实验语义 | 预期收益 | 风险 | 成本 | 重新进入条件 |
|---|---|---:|---|---|---|---|

## 推荐动作
- 只写最低成本、可证伪的下一步；不得直接扩大完整实验。
```

### 14.1 必须立即停止的情况

- 代码、任务书、protocol、数据或checkpoint身份不一致；
- validation/confirm发生未授权读取；
- 原始rows缺失或summary无法复算；
- best checkpoint未恢复或resume不等价；
- NaN/Inf、异常发散或关键物理量单位无法确认；
- 某stage硬门失败；
- 需要删工况、改seed、放宽阈值或扩大维数才能继续；
- 当前修复同时改变多个因子，无法归因；
- 继续运行预计只会生成不可用于论文的混合身份数据。

---

## 15. 与审稿意见的最终对应关系

| 审稿关注 | 本任务书如何回答 | 完成到哪一步才算回答 |
|---|---|---|
| 20步改进不明显 | 等预算ONE/MH/MHC/BCV，随后新validation与confirm | 至少V0，正式结论需C0 |
| 改进来自哪里 | 多时域、闭合、尾部、分组编码、阻尼F逐项消融 | M0/M1 |
| 是否只改善平均值 | D0—D11、D5困难窗、P95/P99/max和单场景退化门 | F4趋势，V0正式 |
| 是否稳定 | 残差谱结构+20/40/80步有限时域证据，明确不声称整体渐近稳定 | M0+V0 |
| 是否物理可解释 | 冻结S0主干、物理分组编码、力/内部力/横摆逐项误差；不把latent冒充物理模态 | M0+V0 |
| 是否可复现 | 单一源码身份、不可变manifest、等价resume、逐窗数据、五seed和一次confirm | 全流程 |

---

## 16. 执行前最后检查表

执行AI必须逐项输出`YES/NO`，任何`NO`不得启动F4：

- [ ] 我读完了本任务书，而不是只根据聊天摘要行动；
- [ ] 我知道第一次授权只到F4；
- [ ] 我没有修改历史v3目录；
- [ ] 新run中不存在旧模型或旧checkpoint；
- [ ] taskbook/source/protocol/data SHA已冻结；
- [ ] 旧validation已标污染且被SplitGuard禁止；
- [ ] confirm访问计数为0；
- [ ] ONE/MH/MHC/BCV训练预算相同；
- [ ] 四候选同折共享完全相同warm起点和主batch序列；
- [ ] best/last/stop概念和文件分开；
- [ ] resume等价测试通过；
- [ ] 完整折监控覆盖D0—D11和D5困难窗；
- [ ] 所有损失项的原始值、加权值和占比可审计；
- [ ] 每折逐窗数据和产物manifest会被保存；
- [ ] 硬门失败会自动停止而不是自动“优化”；
- [ ] 我不会用无发散代替稳定证明；
- [ ] 我不会在F4后自动读取validation。

只有全部为`YES`且写入`preflight_ack.json`后，runner才允许进入F4。

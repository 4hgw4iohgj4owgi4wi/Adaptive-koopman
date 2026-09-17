# Koopman功能组合优化方案

> 项目：VT-2026-05393 Koopman预测与控制优化  
> 日期：2026-08-22  
> 依据：`koopman_universal_results/v2/final_report.md`及D3-recovery底层CSV/JSON  
> 状态：新实验设计；尚未修改模型或启动新训练  
> 目标：利用已有模型在状态、受力、不同预测时域和网络条件下的互补性，寻找优于单一K0/K1的组合预测器及安全控制方案，同时避免重演F+H普适叠加失败。

## 1. 结论先行

最新报告不支持继续把`F+H+C+A`全部叠到同一个Koopman骨干上。当前更有希望的方向是：

1. **状态预测、受力预测和安全约束分工**，不要求一个模型同时负责所有输出；
2. **按预测时域和因果工况选择冻结专家**，而不是重新训练三个完整动力学专家；
3. **K1作为默认回退，K0/K4/K5-F2只在证据支持的区间参与**；
4. **控制器使用多模型风险上界**，不把多个模型的平均值直接当成安全力；
5. **网络状态传播增加AoI/不确定度/受力门控**，不能无条件打开。

本轮候选称为：

**安全约束异构Koopman组合器（Safe Heterogeneous Koopman Composer，SHKC）**。

它不是新的单一Koopman算子，而是由多个冻结Koopman预测器、因果选择器、受力风险头和安全回退组成的组合预测/优化系统。论文中必须明确这一边界。

## 2. 最新报告提供的组合依据

### 2.1 直接证据

| 功能 | 最新v2事实 | 对组合设计的含义 |
|---|---|---|
| K0 | internal `J_pred=3.0960`；E1加减速和部分长时状态有优势 | 作为纵向加减速和部分远时域候选，不作为全局唯一模型 |
| K1 | internal `J_pred=2.8041`，当前简单模型中总体最好；回头弯和拉伸方向稳健 | 默认预测器和任何低置信度情况下的回退模型 |
| K4 | internal `J_pred=2.8266`，与K1接近；发散率`5.56%`，明显低于K1的`20.64%` | 作为低发散状态专家和弯道/中时域候选，而不是全局替代K1 |
| K5-linear原输出 | 状态组`5.9549`低于K1的`6.3434`，但力/载荷`8.1699/10.4504`失效 | 状态动力学仍可能有用，原受力解码器不可用 |
| K5-F2 | D3 force/load降至`1.4475/0.2804`，internal `J_pred=2.5609`；v2 development方向准确率约`0.936` | 最强受力/载荷候选，但发散保护未过，必须加可信度和K1回退 |
| H-LS/H-RLS | 所有骨干回退rank 0 | 不进入本轮主组合 |
| C重新升维 | 漂移机理存在，但K4仅改善约2.15%，没有通过性能门 | 把lift漂移改作不确定度特征，不再直接干预预测 |
| A参数适应 | K5-A1-2s相对自身改善10.19%，但external `J=0.2150`仍远差于K1的`0.0640` | 不进入“最优绝对预测”主组合，只保留参数变化诊断 |
| 网络传播保护 | 离线burst/delay/DoS可改善K0/K1；闭环delay可能把峰值力推到11–15 kN | 只能作为带安全门的估计模式，不能默认传播 |

### 2.2 后验探索上限，不是新证据

使用已经查看过的D3结果做后验oracle分析：

- 对160条internal轨迹，在`K0-P0/K1-P0/K4-P0/K5-F2`中逐轨迹选择最低`J_pred`，均值由K0/K1逐轨迹简单包络的`1.97346`降至`1.66213`，理论改善`15.78%`；
- oracle获胜次数为K0 `56`、K1 `23`、K4 `60`、K5-F2 `21`，说明不同专家确有互补，而不是某一个模型始终最好；
- 按时域选择最低状态误差专家、受力/载荷使用K5-F2，20步汇总由K1的`2.69752`降至探索值`2.32350`，理论改善`13.87%`。

这些数字使用了最终确认标签，**只能证明存在值得验证的组合上限**。不能把oracle、获胜次数或由D3选出的时域规则当成正式成果。下一轮必须用全新的selector-development重新确定规则，再使用从未查看的新确认集。

### 2.3 时域互补的探索信号

D3汇总显示，最低状态误差专家随时域变化：

- `h=1–2`：K4；
- `h=3–5`：K5-linear；
- `h=6–10`：K4；
- `h=11–15`：K5-linear；
- `h=16–18`：K1；
- `h=19–20`：K0。

K5-F2在抽查的`h=1/5/10/15/20`均给出最低force/load汇总误差，但该结论仍受高载荷样本不足约束。D3的`L4-high`只有10个等效窗，不能据此冻结高载荷切换规则。

上述区间只作为初始假设。正式区间必须在新开发集上重新选择，允许最终结果完全不同。

## 3. 哪些功能可以组合，哪些不能

### 3.1 进入主组合

1. `K1-P0`：默认完整预测和安全回退；
2. `K0-P0`：纵向加减速/特定远时域状态候选；
3. `K4-P0`：低发散状态候选、lift漂移监测来源；
4. `K5-linear+F2`：受力/拉伸载荷候选，及部分时域的状态候选；
5. 模型分歧、lift漂移、物理残差：只作为置信度与拒绝依据；
6. K0/K1短时状态传播：只作为网络估计候选；
7. K1 hold/降速：网络长时失效和受力风险下的安全回退；
8. 多模型风险约束MPC：把预测分歧变成约束收紧量。

### 3.2 不进入主组合

- K2/K3/K3-r2：秩和数量级门失败；
- K5-bilinear：数值爆炸；
- H-LS/H-RLS非零修正：小残差假设已失败；
- 无条件C重新升维：机理存在但没有部署收益；
- K5-A替代K1：相对K5有改善，但绝对误差仍远差于K1；
- 无条件F2：K0/K1/K4上并不普遍有效；
- 无条件网络状态传播：delay闭环已出现严重受力风险；
- 使用真实E0–E9标签、真实未来接触状态或未来误差选择专家：均属于oracle泄漏。

## 4. SHKC总体结构

### 4.1 四条并行预测轨迹

在每个时刻并行计算：

`Y_m={x_hat_m(1:20), F_hat_m(1:20), Q_hat_m(1:20)}, m∈{K0,K1,K4,K5F2}`。

所有专家使用相同当前观测、相同四车实际/计划输入和相同20步时域。任何专家不能获得其他专家没有的未来状态或真实力。

### 4.2 因果上下文

选择器只能使用当前和历史可用量：

`rho_k=[v_x,a_x,delta,delta_dot,kappa_ref,input_switch,gap_margin,contact_history,AoI,mask,quality]`。

再加入不需要真值的模型诊断：

- K0/K1/K4/K5预测分歧；
- 预测状态是否超出train envelope；
- K1/K4 lift流形漂移；
- 四点力重构`Q_FR/Q_LR`的代数残差；
- 连接力与预测形变/速度的合同残差；
- 预测力是否接近`0.8 rated`；
- 20步轨迹是否出现非有限值、突跳或过大修正。

禁止使用未来真实场景标签、未来真实接触区间或“事后哪个专家误差最小”直接选择模型。

### 4.3 两种预测组合形式

#### 形式A：完整专家选择

每个预测窗选择一个专家的完整状态—力—载荷轨迹：

`Y_hat=Y_m*`。

优点是内部合同较完整；缺点是不能分别利用K4状态和K5-F2受力。

#### 形式B：任务分解组合

状态和受力分开选择：

`x_hat(h)=x_hat_mx(h)`，

`[F_hat(h),Q_hat(h)]=[F_hat_mF(h),Q_hat_mF(h)]`。

任务分解更可能得到最低预测指标，但状态和受力可能来自不同动力学轨迹。因此必须：

1. `Q_FR/Q_LR`始终由所选同一组四点力重构；
2. 报告状态—力合同残差；
3. 若合同残差超过validation 95%分位，回退完整K1轨迹；
4. 论文中称为“多任务组合预测器”，不能称为一个物理一致的单Koopman算子。

### 4.4 时域调度

时域`h`本身是可用信息，可以为每个h设置稀疏权重：

`x_hat(h)=sum_m alpha_m(h,rho_k)x_hat_m(h)`。

约束为：

- `alpha_m≥0`且和为1；
- 每个h最多两个非零专家；
- 相邻h的权重变化受限；
- 不允许在确认集重新切换区间；
- 优先使用完整专家硬选择；只有边界突跳明显时才使用2–3步平滑过渡。

时域调度后的轨迹可能不满足半群性质。它适合20步预测/MPC，不应被表述为单一递归Koopman算子。

### 4.5 低容量因果选择器

依次比较：

1. `G0-fixed`：只按时域固定选择，不看工况；
2. `G1-rule`：预注册物理规则和滞回；
3. `G2-logistic/tree`：低容量逻辑回归或浅层树，预测专家风险；
4. `G3-sparse-soft`：最多两个专家的稀疏凸权重；
5. `G-oracle`：真实误差选专家，只作为不可部署上界。

不重新启用大规模神经门控。以前完整专家门控已经出现专家塌缩，当前样本量也不支持再增加复杂门控。

选择器输出除专家外还必须给出置信度。若最高置信度低于冻结阈值，或模型分歧超过validation 95%分位，执行`abstain → K1`。

### 4.6 切换保护

- 最短驻留时间初值1.0 s，在新validation冻结；
- 正常运行切换率不超过0.5 Hz；
- 连续恢复窗口后才允许从K1回到辅助专家；
- 切换前后2–3步使用固定线性过渡权重，检查状态、力和MPC控制突跳；
- 任一专家非有限、预测力超过安全门或距离趋势失败，立即回退K1/安全控制器。

## 5. 受力预测的专门组合

### 5.1 不能简单把K5-F2全局替换进去

K5-F2在总体force/load上最好，但仍有三个风险：

1. development发散率相对原K5略升；
2. 它使用K5预测形变，状态错误会传入受力头；
3. 高载荷盲确认样本不足，无法证明靠近额定力时仍可靠。

### 5.2 建议的因果受力模式

| 模式 | 因果条件 | 候选输出 | 回退 |
|---|---|---|---|
| `FM0-free` | 当前形变处于间隙内、预测载荷很低 | K1-F2或K1-F0中validation较优者 | K1-F0 |
| `FM1-transition` | 接触建立/卸载、方向反转 | K1-F2与K5-F2并行，按合同残差/分歧选择 | K1-F0 |
| `FM2-loaded` | 连续接触且载荷进入中档 | K5-F2 | K1-F0或两者风险上界 |
| `FM3-high-risk` | 预测力>0.8 rated、分歧/不确定度过门 | 不输出单一乐观力；输出上置信界 | 控制器降速/收紧约束 |

接触模式由当前观测、因果形变历史和各模型预测共同估计，不使用未来真实R0–R5标签。

### 5.3 物理对齐

从预测速度作前向因果差分，新增对齐的预测加速度/横摆角加速度：

`a_hat(h)=(v_hat(h)-v_hat(h-1))/dt`。

据此计算货物和四车的Newton–Euler残差。差分只使用预测序列，不读未来真值。残差只用于置信度和回退，不在本轮第一阶段重新训练大模型。

## 6. 网络条件下的功能组合

### 6.1 最新数据的边界

离线K1状态传播相对不保护：

- iid略有恶化；
- burst、delay和DoS均有改善；
- 但闭环delay保护明显恶化位置、货物拉伸载荷和峰值连接力；
- K1-DoS保护具有局部收益：位置RMSE约改善26.8%，拉伸载荷RMSE约改善51.8%，峰值力约降低20.7%。

因此网络保护的功能可以保留，但必须增加因果模式和安全回退。

### 6.2 三模式网络监督器

1. `NM0-hold`：clean/iid或AoI很小时沿用观测管理器，不主动长时传播；
2. `NM1-short-propagate`：检测到burst/delay/DoS初期且不确定度低时，用K1短时传播到当前；
3. `NM2-safe-slow`：AoI、协方差、模型分歧、预测力或距离趋势超过门时，停止继续传播，hold并降速。

模式由mask、AoI、序列号、包间隔和预测不确定度在线判断，不能直接输入事后网络profile标签。阈值只在新的network-development冻结。

### 6.3 必须保留的安全门

- 任一模型预测连接力上界超过`0.8 rated`；
- 传播协方差/模型分歧超过validation 95%分位；
- 预计100 m终端距离不可达；
- 控制器连续超时；
- ultimate触发或受力方向连续异常。

任一触发均执行`NM2`，并记录触发原因、持续时间和恢复冲击。

## 7. 面向控制优化的多模型MPC

预测指标最低不等于闭环最好。当前clean 100 m中K0/K1均有2/10距离失败，所以正式闭环前先建立模型无关的控制合同。

### 7.1 名义目标与安全约束分离

- 名义状态目标使用SHKC选择的状态轨迹；
- 货物和四车受力约束不使用加权平均，而使用冻结专家的校准上置信界；
- 终端距离、速度、横摆和连接力约束对全部保留风险场景成立；
- 网络不确定度作为tube/约束收紧量，不混入物理状态。

控制问题写为：

`min J_track(x_nom,u)+lambda_u J_control+lambda_switch J_switch`，

满足：

`max_m[||F_hat_m(h)||+q_(1-alpha,m)(h)] <= F_safe`，

`Q_FR/Q_LR`、四车横摆、系统横摆、终端距离和输入/变化率约束。

其中`q_(1-alpha,m)`只由新训练/validation残差校准，confirm不参与。

### 7.2 两级控制

1. 正常层：SHKC-MPC，优化跟踪与内力；
2. 安全层：K1/保守局部模型 + hold/降速，保证受力和终端可行性优先。

安全层触发后至少驻留冻结时间，不能因通信短暂恢复反复跳回。

### 7.3 “最优”的词典序定义

控制最优不使用单一加权平均决定：

1. 无ultimate、无非有限输出；
2. 100 m距离、终端速度和连接力安全约束通过；
3. 货物`Q_FR/Q_LR`和峰值力最小；
4. 跟踪误差最小；
5. 求解p99小于20 ms；
6. 在上述可行解中再减少控制能耗和切换。

不得通过提高跟踪权重换取更大的内部拉伸载荷。

## 8. 新实验矩阵

### 8.1 预测组合

| 编号 | 方法 | 作用 |
|---|---|---|
| `C0` | K0-P0 | 简单raw基线 |
| `C1` | K1-P0 | 默认基线 |
| `C2` | K4-P0 | 低发散候选 |
| `C3` | K5-F2 | 受力候选，保留失败边界 |
| `C4` | 等权四专家 | 证明简单平均是否足够 |
| `C5` | 全局凸权重 | 不看时域/工况的容量对照 |
| `C6` | 固定时域完整专家选择 | 检验纯时域互补 |
| `C7` | 因果完整专家选择 | 保持完整状态—力轨迹 |
| `C8` | 时域+任务分解组合 | 追求最低预测误差 |
| `C9` | C8+物理残差/拒绝/K1回退 | 主SHKC预测候选 |
| `C10` | oracle完整/任务分解 | 不可部署上界 |

### 8.2 控制组合

| 编号 | 预测器 | 网络模式 | 安全约束 | 用途 |
|---|---|---|---|---|
| `M0` | K0 | 原观测管理 | 原约束 | 历史基线 |
| `M1` | K1 | 原观测管理 | 原约束 | 默认基线 |
| `M2` | SHKC-C9 | 原观测管理 | 原约束 | 只检验预测器贡献 |
| `M3` | SHKC-C9 | 原观测管理 | 多模型风险约束 | 检验安全MPC贡献 |
| `M4` | SHKC-C9 | NM0/NM1/NM2 | 多模型风险约束 | 完整候选 |
| `M5` | K1 | NM0/NM1/NM2 | 多模型风险约束 | 分离网络/安全层贡献 |

`M2→M3→M4`每次只新增一个功能，不能只比较M0与M4后把全部收益归给Koopman组合。

## 9. 新数据与防止二次确认污染

### 9.1 证据角色

- D3及其oracle分析归为`hypothesis_only`；
- 新建D4-selector-development，用于重新选择时域、门控、置信度和安全阈值；
- 新建D5-blind-confirm，所有文件在模型/规则/hash冻结前不可查看；
- 原D1/D3不得混入D5的归一化、门控或残差分位数计算。

### 9.2 D4建议规模

- E0–E6和E9：train各20条、validation各8条、development-test各8条；
- 参数任务：至少12/4/4个组合，单参数和联合变化分开；
- 网络：iid/burst/delay/DoS各20条train、8条validation、8条development-test；
- 高载荷`L4-high`至少200个不重叠20步窗，达不到则不训练高载荷选择器；
- 每个selector训练样本由整条轨迹out-of-fold专家预测生成，禁止窗口泄漏。

### 9.3 D5盲确认

- internal：E0–E6/E9各20条，共160条；
- external：24条未见参数任务轨迹；
- network：四类各10条，共40条；
- 高载荷独立子集至少40条轨迹或200个不重叠窗；
- 固定100 m、单移线、回头弯及通信闭环seed；
- 一次性运行C0–C10和满足离线门的M0–M5。

## 10. 训练与选择器防偏差

1. K0/K1/K4/K5-F2全部冻结，不联合微调；
2. 选择器只用D4 train，阈值只用D4 validation；
3. gate标签采用词典序风险：先非发散/状态安全，再force/load，最后J；
4. 训练样本按轨迹和场景均衡，避免E0/E1短误差主导；
5. gate参数量必须远小于任一骨干，报告树深、特征数和系数；
6. 加入专家占用率、有效专家数、切换率和拒绝率；
7. 若gate长期只使用一个专家，应如实退化为该单模型，不继续宣称组合；
8. 同时报告`macro-of-metrics`和`mean per-trajectory J`。最新K4-F2的聚合与轨迹配对信号并非完全一致，不能只挑有利口径；
9. 五个selector seed全部报告，代表模型按validation中位数选择；
10. D5查看后任何规则/hash变化都使整批确认失效。

## 11. 评价指标与通过门

### 11.1 预测门

SHKC相对逐轨迹`min(K0,K1)`简单包络必须同时满足：

1. `J_pred`改善至少8%，配对95% CI不跨0，Holm校正通过；
2. 状态组和关键横摆/侧向单项恶化不超过5%；
3. force/load至少改善8%，方向准确率不恶化；
4. 发散率不高于K1，并报告非有限率；
5. 高载荷、接触切换和方向反转均无超过5%的安全关键退化；
6. 状态—力合同残差不超过K1的validation 95%分位，或触发回退后仍满足门；
7. 推理p99满足20 ms。

### 11.2 选择器门

- 与oracle的收益差距不超过oracle可实现收益的50%；
- 专家选择准确率只作辅助，最终以风险和预测误差判定；
- 拒绝后K1回退率、错误高置信选择率必须报告；
- 切换率≤0.5 Hz，最短驻留满足冻结值；
- 确认集任一ultimate/非有限输出则部署门失败。

### 11.3 闭环门

1. 所有seed完成路径/距离门；
2. ultimate runs=`0`；
3. 峰值连接力、`Q_FR/Q_LR` P99不高于K1；
4. 跟踪RMSE至少改善8%，或落在3%等价带内同时使受力改善8%；
5. 网络条件下不得出现类似K0-delay保护的受力放大；
6. p99求解时间<20 ms，超时率不增加；
7. 预测收益必须能通过M2、M3、M4消融明确归因。

## 12. 实验顺序

1. **离线预测**：D4上比较C0–C10，先完整专家选择，再任务分解；
2. **物理/受力门**：接触建立、稳定加载、卸载、方向反转和高载荷分层；
3. **新盲确认**：一次性D5 internal/external/network；
4. **100 m clean**：先解决现有2/10距离失败，再谈组合控制优势；
5. **100 m无保护通信干扰**：观察AoI、误差、受力与距离失败；
6. **单移线clean**：比较M0–M5的跟踪与内力；
7. **回头弯clean**：检查K1优势、K4低发散与SHKC组合；
8. **iid/burst/delay/DoS**：先M3无网络保护，再M4三模式保护；
9. **参数变化**：K5-A只作辅助对照，不预设进入主组合；
10. **最终Pareto**：预测、受力、实时、切换和安全共同排序。

## 13. 任务树与停止规则

```text
T0 冻结证据
├─ 归档D3为hypothesis_only
├─ 保存oracle分析脚本和结果，不作为正式门
└─ G0：K0/K1/K4/K5-F2复算不一致则停止

T1 D4数据
├─ internal/external/network新seed
├─ 高载荷与接触分层覆盖
└─ G1：L4-high不足则删除高载荷gate主张，不降低门槛

T2 冻结专家接口
├─ 统一状态、力、Q、输入和归一化
├─ 计算分歧、lift漂移和物理残差
└─ G2：时间对齐/输出合同不一致则停止组合训练

T3 预测组合
├─ C4/C5简单平均与全局权重
├─ C6/C7完整专家选择
├─ C8任务分解
├─ C9安全拒绝与K1回退
└─ G3：D4 development未超过简单包络8%则不生成正式控制候选

T4 网络监督器
├─ NM0/NM1/NM2
├─ AoI/不确定度/受力/距离门
└─ G4：任何delay开发轨迹达到ultimate或全距离失败则停止网络保护

T5 冻结与D5
├─ 冻结模型、规则、阈值、seed、hash和结论模板
├─ 生成未查看D5
└─ G5：查看后冻结文件变化则D5整批失效

T6 一次性预测确认
├─ internal/external/network/high-load
├─ 轨迹配对统计与Holm校正
└─ G6：无预测候选则停止正式闭环，仅交付负结果

T7 模型无关MPC合同
├─ 修复clean 100 m距离/终端约束
├─ 校准多模型风险界
└─ G7：K0/K1自身不能全seed完成则停止候选闭环

T8 闭环
├─ M0–M5逐项消融
├─ 100 m、单移线、回头弯
├─ iid/burst/delay/DoS
└─ G8：安全/实时/闭环门任一失败则回退K1

T9 报告
├─ 区分预测最优、受力最优和控制最优
├─ 报告oracle差距、拒绝率和适用边界
└─ 更新工作记录、solutions和论文证据矩阵
```

遇到无法跑出的支撑证据时，立即停止依赖该证据的后续阶段，在`solutions.md`写明事实、原因、替代解释、修复方案、计算成本和论文结论边界。不得使用D3重新调门后继续声称盲验证。

## 14. 必须输出

建议输出目录：`revision_2026/koopman/composer/`。

- `oracle_ceiling.csv`：仅标记hypothesis-only；
- `expert_predictions_manifest.json`；
- `selector_features.csv`和因果性审计；
- `horizon_expert_map.csv`；
- `task_specific_weights.csv`；
- `selector_occupancy.csv`、切换率和拒绝率；
- `prediction_results.csv`；
- `contact_highload_results.csv`；
- `network_mode_results.csv`；
- `closed_loop_results.csv`；
- `gates.json`、`solutions.md`、`work_log.md`、`final_report.md`。

必须生成图片：

1. `oracle_vs_causal.png`：oracle上限、因果选择器和K0/K1包络；
2. `expert_occupancy.png`：不同场景/时域的专家占用；
3. `horizon_state_force.png`：逐时域状态/受力/载荷；
4. `uncertainty_error_calibration.png`：分歧/漂移与真实误差校准；
5. `contact_force_gate.png`：受力模式、预测力和回退；
6. `network_modes.png`：AoI、模式、受力和位置误差；
7. `closed_loop_100m.png`；
8. `lane_change_hairpin.png`；
9. `accuracy_safety_cost_pareto.png`。

## 15. 最终建议

当前最值得验证的不是“大一统增强模型”，而是下面两条分开的组合线：

### 预测线

`K1默认 + K0/K4/K5状态时域专家 + K5-F2受力专家 + 因果置信度 + K1拒绝回退`。

这条路线有约14%–16%的后验oracle余量，但必须重新盲验证。

### 控制线

`SHKC名义状态 + 多模型受力上界 + 终端距离约束 + NM0/NM1/NM2网络监督 + K1/降速安全层`。

这条路线不追求平均预测最小，而是先消除距离失败和通信下的极端连接力，再优化跟踪。

如果新盲确认不能超过K0/K1简单包络，就应保留K1作为主预测器，把K4和K5-F2仅作为不确定度/风险监视器。这仍然是一种有价值的组合，但不能称为预测性能最优。

## 16. 第三步代码级实施方案

### 16.1 已核实的5080路径与只读边界

项目根目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`

已经形成D3证据的冻结文件：

| 文件/目录 | 当前作用 | 本轮处理 |
|---|---|---|
| `revision_2026\koopman\universal_v2_modules.py` | v2数据、模型和评估主实现；D3冻结SHA256记录于`d3_recovery/freeze.json` | **只读，不直接修改** |
| `revision_2026\koopman\universal_v2\t3\models\K0.npz` | K0的F头/组合工件 | 只读加载并核验metadata |
| `...\K1.npz` | K1的F头/组合工件 | 只读加载并核验metadata |
| `...\K4.npz` | K4的F头/组合工件 | 只读加载并核验metadata |
| `...\K5-linear.npz` | K5-linear的F2候选工件 | 只读加载；必须确认实际variant为F2 |
| `revision_2026\koopman\universal_v2\t7_recovery\` | D3恢复确认及统计 | 只读，标记`hypothesis_only` |
| v2 T8闭环脚本 | 当前路径未写入Review副本，冻结SHA256为`30445AE5...C1F1C1F` | 在5080按hash定位，只读复用其plant/适配器，不覆盖 |

本机Review目录没有挂载5080项目源代码，因此目前只能从冻结manifest核实上述路径和hash，不能在本文件中伪造`universal_v2_modules.py`内部函数名。执行T0时必须在5080读取完整源文件并生成API清单；若接口名称与下面适配器预期不同，只修改新适配器，不能改冻结脚本来迁就新方案。

### 16.2 新增代码目录

所有新代码写入：

`revision_2026\koopman\composer\`

建议文件结构：

```text
composer/
├─ __init__.py
├─ config.py
├─ contracts.py
├─ legacy_adapter.py
├─ freeze_inputs.py
├─ generate_d4.py
├─ generate_d5.py
├─ frozen_experts.py
├─ cache_predictions.py
├─ causal_features.py
├─ selector.py
├─ train_selector.py
├─ physics_guard.py
├─ network_supervisor.py
├─ robust_fcs_mpc.py
├─ evaluate_offline.py
├─ run_closed_loop.py
├─ statistics.py
├─ make_report.py
├─ run_stage.py
└─ tests/
   ├─ test_contracts.py
   ├─ test_causality.py
   ├─ test_frozen_hashes.py
   ├─ test_selector_fallback.py
   ├─ test_physics_guard.py
   ├─ test_network_supervisor.py
   └─ test_no_confirm_import.py
```

输出目录固定为：

`revision_2026\koopman\composer_results\`

禁止把新文件写回`universal_v2\t2–t9`，也禁止覆盖D3图片、CSV和JSON。

### 16.3 `config.py`

新增不可变配置对象`ComposerConfig`，至少包含：

```python
project_root
universal_v2_root
composer_root
result_root
horizon = 20
state_dim_s3 = 46
state_dim_main = 30
control_dim_u1 = 8
point_force_shape = (4, 2)
load_dim = 2
expert_names = ("K0", "K1", "K4", "K5F2")
fallback_expert = "K1"
force_warning_ratio = 0.8
control_period_s = 0.02
max_switch_hz = 0.5
min_dwell_s = 1.0
selector_seeds = (109001, 109002, 109003, 109004, 109005)
```

注意：`force_warning_ratio`乘以哪个额定力必须从plant参数读取，不能在多个文件重复硬编码12 kN。配置启动时把额定力、ultimate力和dt写入`resolved_config.json`。

所有seed、阈值、rank、特征清单和路径在D4开始前写入`protocol.json`并计算SHA256。D5冻结后不允许修改配置。

### 16.4 `contracts.py`

定义统一输出对象，隔离不同模型原有数组格式：

```python
@dataclass(frozen=True)
class PredictionBundle:
    state_s3: np.ndarray       # [batch, 20, 46]
    state_main: np.ndarray     # [batch, 20, 30]
    point_force: np.ndarray    # [batch, 20, 4, 2]
    payload_load: np.ndarray   # [batch, 20, 2]
    force_rate: np.ndarray     # [batch, 20, 4, 2]
    finite_mask: np.ndarray    # [batch, 20]
    expert_name: str
    metadata: dict
```

同时定义：

```python
class CausalContext
class SelectorDecision
class PhysicsGuardResult
class NetworkMode
class ControlDecision
```

`validate_bundle()`必须检查：维数、dtype、有限值、时间轴、车辆顺序`FL/FR/RL/RR`、分力顺序`Fx/Fy`、Q符号和归一化逆变换。任何一项不一致立即停止，不能靠reshape把数据凑成目标维数。

### 16.5 `freeze_inputs.py`

负责T0冻结，不训练模型。具体实现：

1. 计算`universal_v2_modules.py`、K0/K1/K4/K5工件、D3 freeze和D3结果hash；
2. 按SHA256 `30445AE583452C5FE495230339E879FC0B3B47FD0A5AF4452E5573B4761F1C1F`在`revision_2026`递归定位旧T8闭环脚本；
3. 读取`universal_v2_modules.py`的顶层函数/类名，写入`legacy_api.json`；
4. 检查四个NPZ的key、shape、variant和训练数据角色，写入`expert_artifacts.json`；
5. 检查D4/D5 seed没有与D1/D2/D3/T8重复；
6. 把所有输入标记为只读，不对原文件执行写操作。

若按hash找不到旧闭环脚本，不应停止离线T1–T6，但T7闭环分支必须标记`blocked_missing_frozen_closed_loop_source`并写`solutions.md`。

### 16.6 `legacy_adapter.py`

这是唯一允许接触`universal_v2_modules.py`内部API的新文件。对外只暴露：

```python
load_frozen_expert(name: str) -> object
rollout_frozen_expert(name, x0_s3, u1_seq, horizon=20,
                      force_variant="P0") -> PredictionBundle
generate_physical_trajectory(job: dict) -> Path
apply_network_trace(traj_path, trace_cfg) -> Path
load_plant_limits() -> dict
```

执行T0后，根据真实函数名完成内部映射。若冻结脚本没有可复用公共函数，可以把最小只读调用逻辑复制到`legacy_adapter.py`，但必须：

- 在每个复制函数注释原文件hash和原行号；
- 写回归测试，确认同一D3样本输出逐元素一致；
- 不把整个v2脚本复制后任意修改；
- 适配器输出始终经过`validate_bundle()`。

### 16.7 `frozen_experts.py`

实现四个包装器：

```python
class K0Expert(FrozenExpert)
class K1Expert(FrozenExpert)
class K4Expert(FrozenExpert)
class K5F2Expert(FrozenExpert)
```

重点检查：

- K0/K1/K4的主版本使用P0输出，不误用validation未选中的F2；
- K5必须显式加载`F2-diagnostic`头，不得因`t3/selection.json`全局回退F0而静默加载错误版本；
- 四个专家接收完全相同的`x0_s3/u1_seq`；
- 每个专家单独返回异常，不能因K5失败让K1结果丢失；
- K5非有限时生成`finite_mask=False`，选择器立即回退K1，禁止数值裁剪后继续。

### 16.8 `generate_d4.py`和`generate_d5.py`

`generate_d4.py`复用v2 plant/共同ICR/连接器模型，只更换冻结seed和任务表。新增命令参数：

```text
--split train|validation|development-test
--scene E0|E1|E2|E3|E4|E5|E6|E9
--seed
--network-profile clean|iid|burst|delay|dos
--parameter-task-id
--coverage-target normal|high-load|transition
--output
```

每条NPZ额外保存但不输入模型的审计元数据：

- `source_seed/split/scene/parameter_task/network_profile`；
- 峰值力占额定力比例；
- R0–R5、L0–L4窗口计数；
- state/control/force的采样时间戳；
- plant/model/config hash。

`generate_d5.py`必须单独实现，不能让`--split confirm`复用一个可被训练脚本扫描的目录。D5生成后：

- 路径写入`d5/freeze.json`；
- 训练与选择脚本中硬编码拒绝包含`d5`的输入路径；
- `test_no_confirm_import.py`递归检查训练manifest没有D5文件/hash；
- D5只允许`evaluate_offline.py --confirm`读取一次。

### 16.9 `cache_predictions.py`

不要一次把四专家、全部轨迹、20步和全部输出堆入内存。按“一条轨迹×一个专家”缓存：

```text
cache/{split}/{trajectory_id}/{expert}.npz
```

每个缓存同时保存：

- `PredictionBundle`；
- 生成该缓存的模型hash、数据hash和代码hash；
- 推理时间、峰值内存、异常位置；
- 当前与历史因果量，不保存未来真值到selector输入区。

缓存写完后使用临时文件原子改名，防止中断留下可被误读的半文件。若内存仍不足，按rolling-origin块处理，例如每块128窗；不能降低轨迹数来掩盖资源问题。

### 16.10 `causal_features.py`

实现冻结特征顺序：

```python
build_context(current_state, applied_u_history, reference_preview,
              network_history, expert_predictions) -> CausalContext
```

特征包括：

- 当前`vx/ax/delta/delta_dot/kappa_ref`；
- 当前/历史连接形变、间隙余量和受力方向；
- 控制符号切换、曲率变化率；
- mask、AoI、质量和序列有效性；
- 四专家状态/力分歧；
- K1/K4 lift漂移；
- Q代数残差、连接合同残差；
- horizon索引。

必须提供`assert_causal_feature_provenance()`：每列记录最晚可用时间，任何时间晚于预测起点的真值列直接抛错。严禁把`scene`、`R0–R5`、`L0–L4`和事后最优专家作为推理输入；它们只作为训练标签/分层统计。

### 16.11 `selector.py`和`train_selector.py`

实现四种可部署选择器和一个oracle：

```python
FixedHorizonSelector
RuleSelector
LogisticRiskSelector
ShallowTreeRiskSelector
SparseSoftSelector
OracleSelector  # 只能在hypothesis目录运行
```

训练任务拆成两个头：

- `state_selector`：每个h选择完整状态专家；
- `force_selector`：选择完整四点力+Q来源。

标签不是“平均误差最小”，而是词典序：

1. 排除非有限、超过状态安全范围和物理残差门的专家；
2. 状态头最小化逐状态安全加权误差；
3. 受力头最小化四点力、Q和方向错误；
4. 差异小于3%时选择K1或参数更少者。

训练输出：

- `selector_seed_*.npz/json`；
- 专家占用率、有效专家数、拒绝率；
- 混淆矩阵和高置信错误率；
- 每个特征的来源和系数/树规则；
- validation冻结阈值。

若5080环境没有`scikit-learn`，先运行Rule/Fixed选择器；不得临时联网安装后改变环境却不记录。确需安装时，记录环境导出和包版本，再重新冻结D4实验。也可用NumPy实现L2逻辑回归作为无额外依赖后备。

### 16.12 `physics_guard.py`

实现：

```python
reconstruct_payload_load(point_force)
compute_connector_contract_residual(state_s3, point_force, params)
compute_newton_euler_residual(prediction, dt)
compute_force_ucb(prediction, calibration)
apply_guard(decision, bundles, thresholds) -> SelectorDecision
```

规则：

- Q必须由同一四点力重构；
- 加速度用预测序列前向差分，不使用未来真值；
- 物理残差或模型分歧超validation 95%分位时回退完整K1；
- 预测力UCB超过`0.8 rated`时不输出乐观单值给控制器，而是标记`high_risk`；
- 车辆侧独立力仍不存在时，作用—反作用字段保持`not_identifiable`，不能把取负当验证。

### 16.13 `network_supervisor.py`

实现有限状态机：

```python
NM0_HOLD
NM1_SHORT_PROPAGATE
NM2_SAFE_SLOW
```

状态包含当前模式、进入时刻、连续恢复计数、最后有效观测、AoI和传播不确定度。接口：

```python
update(packet_meta, guard_result, distance_trend, dt) -> NetworkDecision
```

必须实现：

- 1 s最短驻留和连续恢复；
- iid下默认不主动长时传播；
- NM1只允许validation冻结的最大传播步数；
- 力UCB、AoI、分歧或距离趋势越界立即进入NM2；
- NM2输出hold+降速请求，不直接修改plant真值；
- 记录每次切换的原因、时间、恢复冲击和切换率。

### 16.14 `robust_fcs_mpc.py`

现有T8控制器是9个离散候选的诊断适配器，不应直接写成一般连续MPC。本轮先把它规范为**有限控制集模型预测控制（FCS-MPC）**：

- 公共加速度修正`{-0.15,0,0.15} m/s²`；
- 虚拟前/后转角共同缩放`{0.9,1.0,1.1}`；
- 9个候选经同一共同ICR分配成8维U1；
- 对每个候选并行计算K0/K1/K4/K5-F2 20步预测；
- 名义跟踪代价使用SHKC状态；
- 力/Q约束使用多模型UCB，不使用平均值；
- 增加终端距离、终端速度、单车/系统横摆、控制变化率约束；
- 所有候选不满足时进入安全层，不返回最小违反候选冒充可行解。

接口：

```python
solve_fcs_mpc(current_state, reference, expert_set,
              network_decision, previous_control) -> ControlDecision
```

优先向量化9×4×20预测。若p99仍超过20 ms，按以下顺序处理：缓存公共lift、批量矩阵乘、降低重复诊断计算、把低风险时刻的辅助专家降为每2步更新。不得直接把H从20改到12后仍报告20步控制。

只有FCS-MPC先使K0/K1在clean 100 m全部seed完成距离门后，才允许扩大控制序列或接入连续优化器；否则先解决终端可行性，不增加求解器复杂度。

### 16.15 `run_closed_loop.py`

不要改旧T8脚本。新脚本通过`legacy_adapter.py`复用plant、共同ICR和场景生成逻辑，实现M0–M5：

```text
--method M0|M1|M2|M3|M4|M5
--scenario staged_100m|single_lane_change|hairpin
--network clean|iid|burst|delay|dos
--seed
--output
```

每一步记录：

- 当前/选择的专家、权重和置信度；
- 网络模式、AoI和回退原因；
- 9个候选的可行性、代价和受力UCB；
- 四车控制、单车横摆、系统/货物横摆；
- 四点Fx/Fy方向、Q_FR/Q_LR和峰值力；
- solve时间、超时、距离趋势、ultimate和fallback。

单个seed失败必须写独立`failure.json`，不能让整个批次无结果，也不能从汇总中删掉该seed。

### 16.16 `statistics.py`和`make_report.py`

`statistics.py`固定：轨迹为统计单位、10000次配对bootstrap、Holm校正、8%/5%/3%/20 ms门。输出同时包含：

- macro-of-metrics；
- mean per-trajectory J；
- 逐场景、逐时域、逐接触/载荷档；
- selector seed中位数/IQR/最差值；
- 选择器与oracle差距；
- 拒绝率、切换率和错误高置信率。

`make_report.py`只读冻结CSV/JSON作图，不能重新计算或覆盖确认结果。极端失败用断轴/单图展示，精确值保留。

## 17. 分阶段命令与验收文件

### 17.1 资源预算与预检

以下为代码实施前的规划估算，不是已测运行时间；T0必须用8条D4 pilot实测后更新`resource_budget.json`：

| 资源 | 规划估算/上限 | 依据与处理 |
|---|---|---|
| 单轨迹长度 | 常规约800个控制步、16 s，控制dt 0.02 s；plant dt 0.002 s | 来自v2 combined manifest；不同场景必须记录实际steps |
| 原始D4/D5数据 | 预计2–5 GB | 取决于是否保存plant子步；默认只保存控制步主合同和必要审计量 |
| 四专家20步cache | 未压缩约20 KB/rolling window；30万窗约6 GB | 按64个主要输出×20步×4专家×float32估算；分轨迹压缩后目标3–8 GB |
| 临时/结果总磁盘 | 运行前至少保留30 GB可用空间 | 按原始数据+cache+临时文件+两份恢复余量估算；不足即停止生成 |
| RAM | 目标<8 GB，硬上限按机器实测 | 128窗分块的核心预测数组仅为MB量级；禁止全轨迹全专家一次堆叠 |
| GPU显存 | 目标<4 GB；K0/K1主要为CPU/矩阵运算，K4按现有实现 | T0记录`torch.cuda.max_memory_allocated`；OOM时先减batch，不减数据 |
| selector训练 | 五seed；每seed优先<30 min | 低容量模型；若超过说明特征/cache实现异常，先profile |
| 离线生成/推理时间 | 用8条pilot的p50/p95乘任务数并加30%余量 | 不在未实测时承诺小时数；预计完成时间写入work log |
| 闭环单步 | 9候选×4专家×20步，目标p99<20 ms | 直接串行很可能超过门，必须批量/缓存；首个10 s pilot不过实时门即先优化实现 |

磁盘预检只读目标盘剩余空间；若需要清理，只能清理已验证属于`composer_results/tmp`的临时文件，不得删除D1–D3、checkpoint或旧报告。

### 17.2 阶段命令

实际Python解释器不能凭旧记录硬编码。先在5080项目环境确认：

```powershell
$projectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$pythonExe = (Get-Command python).Source
& $pythonExe -c "import sys,numpy; print(sys.executable); print(numpy.__version__)"
```

然后从项目根目录执行：

```powershell
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t0-freeze
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t1-d4-generate
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t2-cache
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t3-selector
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t4-offline-development
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t5-freeze
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t6-d5-confirm
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t7-fcs-baseline
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t8-closed-loop
& $pythonExe .\revision_2026\koopman\composer\run_stage.py --stage t9-report
```

| 阶段 | 必须产物 | 通过条件 |
|---|---|---|
| T0 | `input_freeze.json`、`legacy_api.json`、`expert_artifacts.json` | 冻结hash一致、API和工件可加载 |
| T1 | `d4/manifest.json`、`coverage.json` | 分层/高载荷/seed门通过 |
| T2 | 分轨迹专家cache、`cache_manifest.json` | 四专家时间轴/合同一致，无静默裁剪 |
| T3 | 五seed selector、占用/拒绝/规则文件 | 无塌缩、无未来特征、validation门通过 |
| T4 | `development_results.json`、消融CSV | C9相对简单包络≥8%，安全量不退化 |
| T5 | `freeze.json`、候选hash、D5 job表 | 查看D5前全部冻结 |
| T6 | `d5_confirm.json`、paired/Holm统计 | 独立确认门通过才进入正式闭环 |
| T7 | K0/K1 clean FCS结果 | 100 m全seed距离/安全/实时通过 |
| T8 | M0–M5闭环结果 | 无ultimate、受力/跟踪/实时联合门通过 |
| T9 | 最终报告、图片、底层CSV/JSON | 结论与门禁一致、失败样本完整保留 |

每个阶段完成后必须在：

`revision_2026\koopman\composer_results\work_log.md`

追加：日期、命令、输入/代码/输出hash、改动文件、结果、失败与下一步。不得只在聊天框留记录。

## 18. 可能跑不动的情况与处置

| 编号 | 症状 | 首先判断 | 允许的解决方案 | 停止条件/禁止做法 |
|---|---|---|---|---|
| `R01` | 5080项目路径不存在/远程断开 | 驱动器、主机和项目挂载 | 恢复连接后只读检查；记录中断时间 | 未确认项目根目录前不在别处新建同名项目 |
| `R02` | 冻结pipeline或模型hash改变 | 用户改动、同步覆盖或文件损坏 | 与D3 freeze比对，另建新版本输入快照 | 不覆盖旧hash、不把变化后的模型称为D3同一模型 |
| `R03` | `universal_v2_modules.py`没有预期公共API | 函数名/脚本结构不同 | 在`legacy_adapter.py`做真实映射或带来源复制最小函数 | 不直接编辑冻结脚本 |
| `R04` | K5工件实际不是F2 | `selection.json`回退F0、metadata缺失 | 从D3评估调用链定位F2参数并独立冻结 | 无法唯一识别F2时停止K5分支 |
| `R05` | 46/30/18维或FL/FR/RL/RR顺序不一致 | 数据合同或解码器版本 | 通过显式索引映射并做逐元素D3回归测试 | 不用reshape/截断掩盖错位 |
| `R06` | force与state错一拍 | 差分、RK4日志或解码时间戳 | 用时间戳和阶跃峰值交叉相关审计，冻结对齐规则 | 未对齐前不训练selector或Newton残差 |
| `R07` | D4高载荷不足 | plant安全门或轨迹太短 | 在已扫描合法配置内固定补充seed；增加持续时间但保持物理合同 | 不能无限增大转角/驱动力；L4不足则删除高载荷主张 |
| `R08` | 数据生成极慢 | RK4、场景串行、重复诊断 | 按轨迹并行，Windows使用`if __name__ == '__main__'`；缓存静态配置 | 不通过减少场景/seed满足时间 |
| `R09` | Windows多进程递归启动 | 缺少main guard或spawn不安全 | 使用进程入口保护；必要时改线程/串行生成 | 不让重复进程继续写同一输出 |
| `R10` | 内存/显存不足 | 四专家×窗口×20全量堆叠 | 逐轨迹/128窗分块、磁盘cache、批量释放；记录batch | 不删失败轨迹、不降低H=20 |
| `R11` | 磁盘不足/cache半文件 | 压缩NPZ和并发中断 | 先估算容量；临时文件原子改名；清理仅限明确的composer临时目录 | 不删除D1–D3或旧模型；目标不清楚时停止 |
| `R12` | K5/某专家NaN或数量级爆炸 | 输入越界、递推不稳定 | 该专家标记invalid，当前窗回退K1；保存首次异常上下文 | 不clip后继续把结果当合法预测 |
| `R13` | 选择器只选一个专家 | 特征无信息、类别不平衡或K1已最优 | 报告塌缩；比较退化单模型；检查场景均衡 | 不用负载均衡强迫使用差专家来制造“组合” |
| `R14` | 选择器训练好、开发差 | oracle不可因果实现或过拟合 | 降低容量、增加拒绝、只保留固定时域规则 | D4 development未过8%则停止正式组合 |
| `R15` | 任务分解后物理残差大 | 状态和力来自不同专家不一致 | 回退完整专家；提高guard拒绝率；把K5力只作风险上界 | 不把不一致输出称为统一物理轨迹 |
| `R16` | sklearn/solver缺失 | 5080环境包不完整 | 先用Rule/NumPy logistic/FCS；记录环境；必要安装后重新冻结 | 不在确认后临时换依赖/算法 |
| `R17` | 特征中混入未来真值 | 时间索引或场景标签误用 | `test_causality.py`失败即删除该列并重做D4 | 任何D5结果已查看后修特征，D5整批失效 |
| `R18` | D5被训练脚本扫描 | 目录glob过宽 | 训练入口白名单D4；`test_no_confirm_import.py`检查hash | 发生即D5失效，必须换新seed重建 |
| `R19` | selector切换抖振 | 无滞回、置信度临界 | 最短驻留、连续恢复、边界平滑 | validation切换率>0.5 Hz且无法降下则回退固定规则/K1 |
| `R20` | 物理UCB过于保守、9候选全不可行 | 残差校准差或安全边界确实冲突 | 分解哪项约束导致不可行；安全层降速；增加终端余量 | 不放宽ultimate/额定力门来取得可行解 |
| `R21` | clean 100 m仍距离失败 | 终端目标、速度参考或候选集不足 | 先修改模型无关FCS终端代价/约束，并同时复算K0/K1 | K0/K1未全seed通过前不比较SHKC闭环优越性 |
| `R22` | p99>20 ms | 四专家重复lift、Python循环或绘图混入控制 | 向量化、缓存、降低辅助专家更新频率、关闭在线绘图 | 不删除超时步、不改控制周期或H后仍称同合同 |
| `R23` | delay保护再次出现11–15 kN | NM1传播过长、模型偏差累积 | 缩短传播门、立即NM2、降低速度、保存触发前后日志 | 任一开发seed ultimate即停止网络保护分支 |
| `R24` | DoS检测过慢/模式识别错误 | AoI阈值、序列号或恢复规则 | 用因果检测延迟曲线校准；不输入事后profile标签 | 不能用真实`dos`标签直接切模式 |
| `R25` | FCS-MPC求解无候选 | 风险界、终端和输入约束冲突 | 安全控制器接管并记录infeasible；分析约束贡献 | 不返回最小违反候选并标记“求解成功” |
| `R26` | 统计口径给出相反结论 | macro与轨迹均值差异、极端轨迹 | 两者全部报告，主门固定为轨迹配对；分场景解释 | 不事后选择更有利口径 |
| `R27` | confirm后发现代码bug | bug影响数值或仅影响展示 | 数值bug使D5失效并新建确认；纯绘图bug可只读CSV重画并记录 | 不在原D5上重跑修正模型后仍称一次性确认 |
| `R28` | 图片被极端值压扁 | K5或网络失败值过大 | 断轴/分图/裁剪显示范围，CSV保留精确值 | 不删除失败值或只给裁剪图 |

若同一阻塞连续出现且三轮安全替代方案都不能产生所需证据，停止相应分支并写：

`revision_2026\koopman\composer_results\solutions.md`

内容必须包括：已确认事实、最可能原因、替代解释、已尝试方案、尚需资源、论文可保留/必须删除的主张。

## 19. 以后实验MD的固定要求

从本文件开始，后续每份实验MD至少必须包含：

1. 当前证据、假设和不可直接推出的结论；
2. 精确项目根目录、只读文件、新增文件和需修改文件；
3. 每个文件要新增/修改的类、函数、输入输出和shape；
4. 数据split、seed、时间轴、归一化和防泄漏规则；
5. 可直接执行的分阶段命令；
6. 每阶段必需输出、hash、验收门和停止门；
7. 预计显存、内存、磁盘、运行时间和并行方式；
8. 跑不动/数值失败/依赖缺失/确认污染的故障矩阵；
9. 安全回退、不可恢复失败和`solutions.md`处理；
10. `work_log.md`留痕位置和每次必须记录的内容。

如果源代码当前不可访问，MD必须明确写“已核实的路径/接口”和“待执行时核实的接口”，不能猜函数名后当作事实。只有完成代码审计后，才能给出具体行号级修改。

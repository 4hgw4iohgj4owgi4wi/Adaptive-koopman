# Koopman自主推进执行书

> 文档状态：`PLAN_AFTER_N3 / AUTONOMY_ENVELOPE_DEFINED`  
> 编写日期：`2026-08-31`  
> 远端主机：`DESKTOP-9IUUGEO`  
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`  
> 冻结父执行书：`D:\PDxc\Review\koopman_step.md`  
> 父执行书 SHA256：`E18CED5E8D3184B6B1FDABC0E489A5FA5B03FC161FA6CCAFE2D1062788889DC2`  
> N3 run：`20260831_220745_N3_PREDICT_N3_R01`  
> N3状态：`PASS_STOPPED_AFTER_N3`  
> N3协议 SHA256：`5C3EAE4FA00A041646C23F1B5DAFD86B5C140722533C4A76CE97E8618CB01614`  
> N3源码 manifest SHA256：`723D97319F74E0003C8C3151D82F6AA64D01AB7D64AA1DA39DFDFDDA7D36B945`  
> N3 `complete.json` SHA256：`4B0D2976FFF3C8F0B690D4B4EA240E8B8983B4EEA28B6D57A2DCB671E4763B56`  
> 当前授权边界：本轮只写本地MD和工作记录；不修改5080、不启动N4、不生成数据、不训练模型。  
> 未来执行规则：用户明确说“按本执行书执行”后，AI可在本文规定的自主包内自行验收并连续推进，不必每个小阶段再次询问。

## 0. 本次更新解决什么问题

父执行书把人工停止点设得很密，优点是谨慎，但会使已经预注册、风险可控的机械检查反复等待确认。本版把验收分成“机器可判硬门、AI可判灰区、必须人工决定”三层，并把下一批执行范围扩大为：

```text
A0 新版本隔离与身份复验
  ↓ 自动判断
N4-S 六条smoke与资源外推
  ↓ 硬门通过自动继续
N4 126条物理pilot + 126次重放
  ↓ 硬门通过自动继续
N5 train/validation/development正式数据
  ↓ 数据合同通过自动继续
N6 S0/S1/S2 × fixed linear/low-rank bilinear
  ↓ 自主完成灰区复验和接口选择
HUMAN_STOP_AFTER_N6
```

放宽的是调度、并行度、断点恢复、非科学小修、预注册候选选择、灰区追加模型种子和阶段衔接；没有放宽物理安全门、因果性、数据隔离和论文声明边界。

本文不覆盖父执行书。N3正式证据已经绑定父SHA，必须保留。执行时优先级为：

1. 本文关于自主权限、自动衔接和N6公平指标的新增规定；
2. 父执行书关于N2事实、A3公式、D0–D11定义、126条展开和物理门的规定；
3. 新版本冻结协议中的机器可读合同。

三者冲突时，物理/数据硬门取更严格者；任何“继续运行”条款都不能覆盖硬停止条款。

## 1. 当前事实

N3已经完成且人工停止，当前没有Python/MATLAB进程。已经核对：

- 94项测试通过；
- S0/S1/S2总输入维数分别为54、58、70；
- 重复物理输入数0，未来实测输入数0；
- 4条N2 A3轨迹的一步和20步解析轮角最大误差均为`0 rad`；
- 126条dry-run身份唯一，D0–D11完整，V1-ES/R3-ES各63条；
- train/validation/development未来base family分别为96/48/48，跨split family为0；
- confirm 96个base family仍隐藏；
- `koopman_predict_next_results`中正式NPZ数量为0，所以N4物理pilot尚未运行。

不能把N3 PASS解释为Koopman精度提高。它只说明接口、执行器递推、场景合同和数据划分已经具备进入N4的条件。

## 2. 自主权限分层

### 2.1 A级：AI直接决定、执行并留痕

获得一次“按本文执行”的明确授权后，下列事项无需再次询问：

1. 在新隔离目录复制源码、排除缓存、生成manifest和唯一run ID；
2. 根据smoke实测选择1–4个worker、轨迹分块大小、日志刷新间隔和checkpoint频率；
3. 在不改变有效样本数、优化步数和数据身份的前提下调整micro-batch与梯度累积；
4. 处理路径、导入、JSON序列化、报告、绘图、日志、临时目录、冷启动和断点恢复问题；
5. 自动核对SHA、轨迹数、重放、有限值、守恒、镜像、split、归一化和未来泄漏；
6. 从预注册rank、ridge和训练种子候选中只使用validation选择；
7. 在灰区内启用预注册的两个备用训练初始化seed；
8. 生成补充图、最坏轨迹表、置信区间和故障注入测试；
9. 某阶段达到`PASS_CONTINUE`或`PASS_WITH_WARNING_CONTINUE`后自动进入下一阶段；
10. 选择最简单的有效S0/S1/S2接口，并记录选择依据。

### 2.2 B级：AI可做有限自修正并重跑当前阶段

下列问题允许AI最多进行三轮“单根因最小修复”：

- CLI/Windows路径/启动器/进程池失败；
- 缓存进入manifest、临时文件导致身份不稳定；
- 数据adapter的明确端点或单位实现错误；
- 独立审计脚本的字段读取、JSON类型或报告聚合错误；
- OOM、显存碎片和不会改变数学问题的batch调度；
- 双线性求解病态，但只允许使用预注册rank与ridge候选；
- 图件、CSV、PDF或manifest漏项。

每轮必须先保存失败证据，只改一个根因，新增回归测试，生成新source/protocol SHA和新run ID。若物理原始数组不变，可重新审计；旧`complete.json`不得继续标PASS。

### 2.3 C级：AI必须停止并交给用户

以下事项不在自主范围内：

- 修改轮胎、连接器、载荷转移、执行器或车辆物理参数；
- 修改D0–D11幅值、持续时间、方向、seed族或删除不利工况；
- 放宽轮胎`0.90`、负支承、连接器、速率/角度、守恒、重放或因果门；
- 修改共同ICR分配器C1/C2；
- 让同一base family跨split，提前查看confirm或用development反复调参；
- 发现未来实测变量泄漏、作用反作用失败、内力零空间失败、NaN/Inf或原始数据缺失；
- 需要新增任务书外的模型、损失主项、专家数或改变论文工作域；
- N6结束后进入K1–K7、MPC或网络攻击实验。

这些问题必须写`solutions.md`，不能以“AI自主判断”为由绕过。

## 3. 四种机器状态与自动衔接

每个阶段必须输出`gate_report.json`、`decision.json`、`complete.json`和工作记录。状态只允许：

| 状态 | 含义 | 行为 |
|---|---|---|
| `PASS_CONTINUE` | 全部硬门和主要研究门通过 | 自动进入下一阶段 |
| `PASS_WITH_WARNING_CONTINUE` | 硬门通过，仅存在预注册的非阻断负结果 | 保留警告并自动进入下一阶段 |
| `REPAIR_CURRENT_STAGE` | L0/L1或证据明确的非物理L2实现问题 | 最小修复、更新身份、重跑当前阶段 |
| `BLOCKED_HUMAN_REQUIRED` | 任一物理/数据硬门失败或需要科学设计改变 | 停止，写解决方案，等待用户 |

允许作为warning继续的例子：

- D0直线下横向变量接近零；
- angle mask在D0–D11仍为0；
- 某一模型在它不擅长的工况没有优势，但未触发最大退化门；
- S2只改善执行器输出、没有改善公共47维物理状态；
- 双线性只在D7–D9强输入耦合工况有效；
- 某张图生成失败，但原始数据、指标和manifest完整，且随后可单独重画。

不能作为warning继续的例子：

- 轮胎利用率超过冻结门、支承为负、连接器越界；
- 126条缺失、重复、重放不一致；
- 某工况无可用20步窗且无法仅靠既有预注册数据解决；
- S0/S1/S2含未来真实轮角或同一物理量重复拼接；
- 任何模型出现非有限输出而聚合脚本把它忽略。

## 4. A0：建立自主执行隔离版本

不得修改已经冻结的`koopman_predict_next`。建立：

```text
revision_2026\koopman_predict_auto
revision_2026\koopman_predict_auto_results
revision_2026\koopman_predict_auto_data
revision_2026\koopman_predict_auto_models
```

### 4.1 代码修改

| 文件 | 修改 | 验收 |
|---|---|---|
| `config/protocol_predict_auto.json` | 继承N3合同，写入本文SHA、自主包边界、阶段状态、资源上限、候选grid和停止规则 | 配置可被runner和审计共同读取 |
| `src/contracts.py` | 增加`AUTONOMY_POLICY`、状态枚举和阶段转移表 | 故障注入不能越过硬门 |
| `scripts/run_koopman_predict.py` | 增加`--auto-through N6`、`--resume-run`、逐阶段锁和原子complete写入 | 只能N4-S→N4→N5→N6；不能进入K/C/MPC |
| `scripts/freeze_predict.py` | 排除缓存、模型临时文件和结果目录；记录父N3身份 | 连续两次manifest一致 |
| `src/evaluation.py` | 实现公共指标、完整指标、工况分层和配对bootstrap | S0/S1/S2比较不会因输出维数不同而失真 |
| `src/dataset.py` | 输出common47标签、actuator4标签和窗口账本；确认train-only归一化 | family不跨split，confirm不可见 |
| `tests/test_auto_stage_gates.py` | 对每个硬门故障注入，验证状态和下一阶段 | 硬门失败时下一阶段目录不存在 |
| `tests/test_metric_fairness.py` | 测S0/S1/S2公共维度、执行器维度和权重归一化 | S0不因缺少执行器标签被错误惩罚 |
| `tests/test_resume_idempotency.py` | 中断、恢复、重复提交、原子complete和run ID测试 | 不重复轨迹、不拼接异源结果 |

### 4.2 A0通过门

- 父N3任务书、协议、源码manifest和complete哈希全部一致；
- 新分支不包含`.pytest_cache`、`__pycache__`和历史结果；
- 94项父测试继续通过，新测试全部通过；
- A3短探针63个公共字段最大差`<=1e-12`；
- S0/S1/S2一步/20步解析轮角合同继续通过；
- runner在故障注入下不能越过N4/N5/N6硬门；
- 当前无冲突进程，或AI确认其他进程不使用同一结果目录/GPU且可降低并行度继续。

A0通过后自动进入N4-S。

## 5. N4-S与N4的自主规则

### 5.1 N4-S smoke

AI从冻结126条矩阵中选择覆盖六种负载的6条，而不是挑最容易的轨迹：

```text
D0直线、D2正反阶跃、D4单移线、D5回头弯、D7前后内力、D9对角内力
```

至少覆盖左右方向、V1-ES/R3-ES和D9两个成员中的一个。每条必须完成生成和重放。

AI根据实测自动选择worker数：

- 先用1 worker取得基准；
- 若2 worker数值身份与1 worker在冻结容差内一致且资源稳定，可继续测试4 worker；
- 最大4 worker；不得通过减少子步、重放或输出字段换速度；
- 预计N4总墙钟`<=18 h`且D/E任一指定输出盘剩余`>=40 GiB`时可自动继续；超出则`BLOCKED_HUMAN_REQUIRED`并给出串行/并行成本方案。

网络断开但远端进程仍正常时，AI可以恢复监控；无进程、无run目录、0字节日志视为“未真正启动”，核对命令后可重新提交一次，不计科学重跑。

### 5.2 N4硬门

完整执行父任务书规定的126条保存轨迹和126次重放。硬门保持：

- 12类工况、36个base family和126个唯一展开身份完整；
- 有限值、时间网格、重放哈希和线程身份通过；
- 作用反作用、支承守恒、完整内力零空间、镜像和方向通过；
- A3轮胎原始利用率`<=0.90`、支承非负、连接器和执行器冻结门通过；
- 四车`Fx/Fy/Fz`、四车/货物/系统横摆、请求/实际轮角和阵列拉伸内力字段完整；
- D0–D11均形成与其目的相符的稳态、操纵、切换或连接事件20步窗；
- 主审计与独立复算一致。

若全部硬门通过，即使angle mask为0或某些诊断效应不明显，也标记`PASS_WITH_WARNING_CONTINUE`并自动进入N5。angle mask为0只能说明该安全限制在当前域不活跃，不能人为增大转向使它激活。

## 6. N5数据生成允许AI自己决定什么

固定base family数量不变：train 96、validation 48、development 48；confirm 96保持隐藏。方向、成员和植物展开由已冻结合同自动产生。

AI可以自行决定：

- 分批生成顺序和chunk大小；
- checkpoint间隔与断点恢复；
- 数据写D盘还是已登记的E盘结果目录；
- 窗口缓存格式和压缩等级；
- 在保持同一轨迹、同一采样点和无损数值的前提下使用NPZ/Parquet索引；
- 对事件窗口不足做统计诊断和报告。

AI不能自行决定：

- 改seed、增加validation/development样本、删除失败family；
- 复制重叠窗口伪造样本量；
- 把development移入train；
- 生成或读取confirm；
- 改D0–D11幅值来增加事件。

N5硬门：数据manifest和逐轨迹SHA完整；train/validation/development family无交叉；归一化只读train；所有20步窗在单条轨迹内；S0/S1/S2由同一原始端点生成；未来实测篡改测试通过；每类窗口数量和有效样本数写入账本。通过后自动进入N6。

若只存在“某个非主要窗口数量偏少”，但所有12工况均有有效样本，允许继续N6并标记warning；若某个预注册主要窗口为0，则停止，不得自动造数据。

## 7. N6公平评价修正

### 7.1 解决S0与S1/S2输出维数不一致

S0预测47维，S1/S2预测51维。主比较必须只使用三者共有的物理输出，不能因为S0没有4维执行器标签而惩罚S0。

定义公共主指标：

\[
J_{20}^{common}=\frac{
0.25E_{core}+0.20E_{relative}+0.20E_{force4}
+0.15E_{internal}+0.10E_{yaw}}{0.90}.
\]

定义只用于S1与S2的完整指标：

\[
J_{20}^{full}=0.90J_{20}^{common}+0.10E_{actuator}.
\]

规则：

- S0与S1/S2的主要结论只依据`J_common`和各原始物理量；
- S1与S2可同时比较`J_common`和`J_full`；
- S2解析轮角几乎精确时，必须单列“解析执行器收益”和“其余47维物理预测收益”；
- 若S2只降低`E_actuator`而`J_common`无改善，不能称整体Koopman动力学改善。

### 7.2 最小实验矩阵

```text
M0 fixed linear × S0/S1/S2
M1 low-rank bilinear rank∈{1,2,4} × S0/S1/S2
horizon∈{1,5,10,20}
窗口∈{steady,maneuver,switch,connector_event}
主训练初始化seed=5个；备用seed=2个，运行前冻结但只在灰区启用
```

同一比较统一原始轨迹、归一化、优化步数、早停、控制序列和rollout方式。报告参数量、条件数、训练/推理时间；接口维度带来的自然参数增量不能隐藏。主要结果采用同骨干设置，另做参数量近似匹配的敏感性检查，不能只保留有利版本。

### 7.3 AI自主判定区间

S1相对S0：

| 判定 | 条件 | 行为 |
|---|---|---|
| 全局有效 | macro `J_common`改善`>=5%`，切换窗`>=8%`，重要工况最大退化`<=3%`，配对95%CI支持方向 | 选择S1进入后续候选，可声明总体+切换收益 |
| 局部有效 | macro不恶化，切换窗`>=5%`，D2/D4/D6/D10至少两类`>=5%`，最大退化`<=5%`，5个seed至少4个同向 | 选择S1，但只声明转向瞬态优势域 |
| 灰区 | 改善介于0–5%、CI跨0或seed方向不稳，但无`>5%`退化 | 自动启用2个备用seed，只重跑对应比较后重新判定 |
| 无效/退化 | 追加seed后仍无一致改善，或任一重要工况退化`>5%` | 选择S0；S1保留为负消融 |

S2相对S1：

| 判定 | 条件 | 行为 |
|---|---|---|
| 公共动力学有效 | `J_common`改善`>=3%`，或明显降低发散且重要工况不恶化`>3%` | 选择S2 |
| 仅执行器有效 | `J_full`改善但`J_common`改善`<3%`，且改善几乎全部来自`E_actuator` | 选择更简单S1；S2写成解析侧车负/中性消融 |
| 灰区 | 0–3%、CI跨0且无明显退化 | 启用备用seed；仍灰区则选择S1 |
| 退化 | 重要工况`J_common`退化`>3%`或发散增加 | 选择S1并记录S2失败区 |

双线性相对fixed linear：

- 任一D1/D2/D7/D8/D9强耦合工况20步`J_common`改善`>=8%`；
- macro不恶化`>3%`；
- 5个seed至少4个同向；
- 条件数、发散率和推理时间可接受；
- 满足时可标为“强耦合优势模块”，不要求D0也更优；
- 不满足则保留负结果，不纳入后续组合。

### 7.4 最简单有效接口选择

AI按以下顺序自行选择，不需要询问：

```text
若S1不满足全局有效或局部有效 → 选S0
若S1有效且S2公共动力学有效 → 选S2
若S1有效但S2仅执行器有效/灰区/退化 → 选S1
```

选择结果必须同时给出总体、优势工况、退化工况、CI、seed一致性、参数量和推理时间，不能只写“最优”。

## 8. 自主资源和恢复策略

### 8.1 可自动延长的范围

- 阶段预计时间以内正常运行；
- 达到预计时间的150%但仍持续产生有效轨迹/epoch，可继续到18小时总上限；
- 30分钟无新日志、无新产物且CPU/GPU无活动，保存现场并诊断；
- 单次网络中断不停止远端有效进程；
- run支持身份安全恢复时，从最后完整checkpoint恢复；
- source/protocol/data SHA变化时禁止拼接旧partial，必须新run。

### 8.2 进程判断

AI可以查看PID、命令行、创建时间、GPU/CPU占用和输出目录：

- 明确属于本任务的进程：可以监控、等待、按runner正常结束；
- 明确无资源冲突的其他任务：降低并行度后继续；
- 使用相同输出目录、占满GPU或身份不明：停止等待，不终止进程；
- 只有用户明确授权，才能结束不属于本任务的进程。

## 9. 每阶段自动验收清单

### N4验收后自动继续N5

- `trajectory_count=126`、`unique_identity_count=126`；
- 每条重放通过，失败数0；
- 12工况、两植物、方向/成员分布和父合同一致；
- 全部部署物理硬门通过；
- 独立审计匹配；
- raw/manifest/config/source/protocol/taskbook SHA完整；
- 输出最坏轨迹和warning清单。

### N5验收后自动继续N6

- train/validation/development family数96/48/48；
- confirm读取数0；
- cross-split family数0；
- train-only normalization通过；
- 20步窗口不跨轨迹；
- 三接口样本同源、因果输入digest通过；
- 缺失/重复/非有限样本数0。

### N6验收后停止

- M0、M1和S0/S1/S2预注册矩阵全部完成，或失败项已有明确错误证据；
- 1/5/10/20步、四类窗口和D0–D11均有结果；
- `J_common`、`J_full`和单位物理误差均报告；
- 配对CI、5+最多2备用seed、最坏工况、发散率、参数量和推理时间完整；
- AI已按规则选择S0/S1/S2；
- C1/C2、K1–K7、confirm、MPC和网络实验仍为NOT_RUN；
- 最终状态必须为`PASS_STOPPED_AFTER_N6`、`PARTIAL_STOPPED_AFTER_N6`或`BLOCKED_HUMAN_REQUIRED`。

## 10. 工作记录和自主决策记录

开发期追加：

```text
revision_2026\koopman_predict_auto\development_log.md
```

正式阶段追加：

```text
revision_2026\koopman_predict_auto_results\work_log.md
revision_2026\koopman_predict_auto_results\solutions.md
revision_2026\koopman_predict_auto_results\decision_log.jsonl
```

每次AI自行判断必须追加一条decision：

```json
{
  "stage": "N4|N5|N6",
  "decision": "continue|repair|select|stop",
  "facts": [],
  "alternatives": [],
  "chosen": "",
  "rule_id": "",
  "confidence": "high|medium|low",
  "affected_identity": false,
  "next_action": ""
}
```

工作记录仍需写完整命令、退出码、seed、线程、墙钟、读取/修改文件、旧/新SHA、原始产物、关键指标、事实/推断和下一动作。

## 11. 运行入口模板

以下命令只有在用户明确要求按本文执行后才可运行：

```powershell
$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$AutoRoot = Join-Path $ProjectRoot 'revision_2026\koopman_predict_auto'
$PythonExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$Protocol = Join-Path $AutoRoot 'config\protocol_predict_auto.json'

& $PythonExe -B -m pytest $AutoRoot -q -p no:cacheprovider
& $PythonExe -B (Join-Path $AutoRoot 'scripts\run_koopman_predict.py') `
  --stage N4-S `
  --auto-through N6 `
  --project-root $ProjectRoot `
  --protocol $Protocol `
  --run-tag PREDICT_AUTO_R01
```

`--auto-through N6`必须由runner逐阶段读取前一阶段`complete.json`和`gate_report.json`后触发，不能实现为无条件shell串联。任一硬门失败时，后续阶段目录不得创建。

## 12. 第一次实际停止点

本次只更新MD，没有执行远端任务。用户下一次明确说“按`koopman_auto.md`执行”后，AI获得一次覆盖A0、N4-S、N4、N5和N6的连续执行授权，可以自行验收、有限修复和继续，不需要每个PASS再次询问。

无论结果好坏，N6结束后必须停止。AI不能自行进入共同ICR修改、复杂lift/三专家/IRSP组合、confirm、MPC或通讯/DoS实验；这些需要基于N6报告另立下一份执行书。

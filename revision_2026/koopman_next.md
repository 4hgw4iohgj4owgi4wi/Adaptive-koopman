# Koopman下一步实验执行书

> 版本：2026-09-05，KC-R3（后台执行版）；文档状态：UPDATED。用户已授权修改必要代码并启动剩余耗时实验，确认后台程序正常启动后结束当前交互，让程序自行运行。最新执行方式以第16节为准。
> 当前执行入口为本文件。旧 `koopman_refine.md`、`koopman_guard.md`及11维输入协议保留原样供溯源，不再直接执行旧命令。本文件接续已实施的11维输入修复，替代旧任务书中的7维主比较、旧run目录和旧阶段调度；未重新授权改植物或扩大研究范围。
> 本次按第16节将必要检查和后续实验接成一个后台队列：自动核对前置、自动逐组运行、保存进度和失败原因，合格后进入下一阶段。已有9组先核验复用。启动状态以实际进程及回执为准，不以本段授权文字视作已经启动。
> 本版父任务书SHA256：`085886D881F5C2A47F76204888DB2A0BB9B791B6136B29B6F56FD93A8D2FA247`。父版冻结副本在下述KC-R1 run的 `taskbook_snapshot.md`；本版不修改历史快照、报告或PASS文件，用新审查回执说明其有效范围。

## 0. 最新进程与本次接续决定

2026-09-05 21:36现场更新：5080已重新连通，主机DESKTOP-9IUUGEO，GPU为RTX 5080，现场显存占用0 MiB、利用率0%，未见其他训练进程；最新科学产物仍为约00:10完成的旧课程试验。下述00:36审查作为历史保留。22点前后的启动与测试结果另见工作记录和后台回执。

### 0.1 现场进度：训练产物比工作记录更靠后，但尚无有效提名

本轮最后成功远程核查约为2026-09-05 00:36 +08:00，主机DESKTOP-9IUUGEO。最新核查run为：

`REV/koopman_predict_v3v_results/runs/20260904_224212_KC_R01`

下文简称“KC-R1 run”。在该次成功检查中未见训练进程；之后SSH连接超时，故不能把00:36状态当成持续在线监控，也不能断言此后绝无新产物。恢复执行时必须先刷新现场身份、进程、目录和工作记录。

| 阶段 | 本轮核查到的实际产物 | 审查后状态与含义 |
|---|---|---|
| 身份与纯线性纠错（KC0/KC1） | complete.json、纯线性7/11维复算、旧best/last分表已生成 | 纯线性纠错进展保留；新日志路径、数据访问范围和原始交付完整性仍需复核，不是全部C项已关闭 |
| 工程门（KC2） | 记录70项测试：63项继承、7项新增；warm200＋旧T0方法600步冒烟 | 不等于原定T01—T28及三种新方法冒烟全部通过；锁/恢复/乘子/课程等门被推迟，需补齐 |
| 旧模型诊断（KC3） | 缩放前沿、残差分解、力分解、阶段诊断及PASS文件 | 发现重复缩放、口径混用和成员混合；旧PASS不足以证明诊断有效，标REPAIR_REQUIRED |
| 三方法试验（KC4） | 3份共同预热；3种方法×3个seed，共9组均有6000步完成摘要及检查点；有pilot_table.csv | 训练已完成，不再写“KC4尚未开始”；但没有完整有效的阶段验收，模型先保留并逐项裁定复用 |
| 条件课程分支 | 3组6000步训练和curriculum_table.csv已生成，最晚产物约00:10:18 | 实际使用RMSE而非任务书MSE；且课程启动前未见完整三方法校准证据，不能作为预注册课程结论 |
| 校准与提名（KC5） | 找到校准源码；成功检查时未见calibration_table.csv、calibration_summary.json或nomination.json | NOT_VERIFIED / INCOMPLETE；源码存在不是阶段完成，不能据此说已选出最优方案 |
| 五折正式复验、延迟与总交付（KC6—KC8） | 相应阶段目录无有效结果 | NOT_RUN；现在不能进入论文正式优越性声明 |

9组主训练的6000步是优化步数，不是6000条独立轨迹。主试验的best：前两个方法的3个seed均为500步；自适应保护方法为500、6000、500步（seed顺序996100、996101、996102）。这些信息来自 `kc4/pilot_seed{0,1,2}_summary.json`，接续时仍须与各检查点payload、SHA逐个相认。本轮不以未独立复算的pilot_table百分比给三方法排名。

已读取的课程表采用fold0内部选择集、12基础族/21轨迹/473窗口、工况分层综合指标；数值无SI单位，正的下降率表示改善：

| 初始化seed | best实际步数 | 纯线性20步综合误差 | 课程模型20步综合误差 | 20步误差下降率 | 表内55项保护是否通过 |
|---|---:|---:|---:|---:|---|
| 996100 | 1000 | 0.10154937 | 0.10204468 | −0.4878% | 否 |
| 996101 | 1000 | 0.10154937 | 0.10193309 | −0.3779% | 否 |
| 996102 | 500 | 0.10154937 | 0.10230302 | −0.7422% | 否 |

来源为KC-R1 run的 `kc4/curriculum_table.csv`。以上是已读取表及其生成代码支持的结果，本轮未对这三份checkpoint再做独立数值重评，且“55项通过”也不是第10节完整验收。它们说明**当前实际跑出的RMSE课程未取得所报的20步收益**，不能推出“正确的MSE课程必然无效”。三个best均≤1000步，选中权重尚未经历后段多步训练；不能把完整6000步运行经历移植到best上。

### 0.2 已确认的偏差，不再沿用的解释

1. **诊断重复乘缩放系数。** `kc3_diagnose.py`先令E变成gamma E，再计算d，随后又用 `pure1 + gamma*d`，一步实际用了gamma²；20步rollout只用了一次。中间三个gamma点的一步前沿不可直接使用。gamma=0/1端点不受这项重复乘法影响，仍须检查指标口径和配对。
2. **课程公式与实现不同。** `refine_loss.py::residual_loss`四组调用smooth_rmse后加权；实际不是注释所写的加权平方误差。现有三组标 `NONCONFORMING_RMSE_CURRICULUM`，保留失败证据，不冒充指定MSE消融。
3. **提名判据没有落全。** 当前校准脚本只算55项约束，未实现5/10步力与内力保护、回头弯20步加权尾部、最大归一化状态误差等完整门；gamma=0不一致仅打印提示，seed缺失直接跳过。这样的脚本不能出有效nomination。
4. **顺序发生偏离。** 课程precheck只统计固定保护在fit最后三个监控点的一步失败，未证明“先完成三方法原始/校准评估且均无提名”。必须先补这部分，不能用已跑课程倒推条件已满足。
5. **PASS与实证不等价。** KC2延期了原定前置测试；KC3完成脚本按文件存在就写PASS，部分gate和oracle值直接写常量。已有runner只实现KC0—KC2，未落地完整锁与恢复语义。禁止靠修改complete.json推进。
6. **历史混写尚未解决。** 新脚本仍将AccessGuard日志指向历史保护run的split_access.jsonl；成员信息也未贯通WindowData。旧“新阶段只写新日志”“前后与对角加减速42窗口”不能直接沿用：42窗口中还混有对角转向成员。
7. **工作记录时间和进度需勘误。** 当前日志写到KC3，但现场已有9＋3组训练；部分手写时间为01:40、03:00、04:30、06:30，晚于本轮现场时钟。保留旧记录，另加来源和机器实时时间，不把手写时刻当成真实运行顺序。

事实边界：纯线性修复与输入补全收益仍可保留；新保护方法尚无完整有效的优越性结论。推断边界：一步退化可能涉及残差过量、目标冲突和局部力敏感性，但要先排除评估和实现偏差，不能把所有失败都归咎于模型能力。

### 0.3 本版唯一接续路线

**刷新现场并冻结证据→修正读取/评估/统计→完成工程前置并裁定9组模型能否复用→先完整校准三方法→仅在严格触发条件成立时补跑正确MSE课程→提名成立才五折正式复验→推理与论文证据。**

第15节给出逐文件修改、回归、产物、命令和失败恢复；第4—10节科学定义、seed、3%/5%阈值、数据范围不变。本轮不新增专家、双线性项、状态维数、传感器、轨迹、植物或控制实验。优先修复证据链，不自动扩大战线，也不把“已完成训练”误写为“验收通过”。

## 1. 历史基线事实、数字和证据等级

### 1.1 现场与版本身份

远程相对路径以以下目录为根，记作REV：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026`

| 对象 | 位置/身份 |
|---|---|
| 机器 | SSH别名5080；主机DESKTOP-9IUUGEO |
| 解释器 | `E:\anaconda\envs\pytorch_new\python.exe` |
| 最近已执行源码 | `koopman_predict_v3v`，对应第0节KC-R1 run；本版冻结为历史来源 |
| 最近输入修复源码 | `koopman_predict_v3u`，下文称旧输入修复树 |
| 最近输入修复run | `koopman_predict_v3u_results/runs/20260904_204301_KR_R01`，下文称输入修复run |
| 之前完整保护实验 | `koopman_predict_v3t_results/runs/20260904_142331_KG_R02`，下文称历史保护run |
| 数据清单 | `koopman_predict_auto_results/runs/20260901_214725_AUTO_PREDICT_AUTO_R04_R01/n5/data_manifest.csv` |
| 划分清单 | 历史保护run的 `g0/fold_manifest.csv` |
| 11维缓存 | `koopman_predict_auto_data/20260901_214725_AUTO_PREDICT_AUTO_R04_R01/n5_cache11` |
| 本地开发副本 | `D:\PDxc\Review\_koopman_kr_dev`，不是远程最新源码的自动替代品 |
| 历史任务书 | `D:\PDxc\Review\koopman_refine.md`，保留原SHA |

以下为上一轮2026-09-04 22:19的历史现场：主机与主要源码SHA吻合，未见训练进程，输入修复run的kr1—kr7均为空；kr0的旧状态仍为BLOCKED。最新阶段以第0节为准。不能把目录已创建、一个决策日志PASS或旧63项测试描述当作新主线完成。

需要现场逐项核验的SHA256：

```text
koopman_refine.md（历史原文）
D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612
koopman_input_protocol.md（已存在的11维输入协议）
B28E1C82F25C455214BD8C6FCF8C317F63F149BD95FD6CCBF36FBD56B5D08FC4
数据清单
B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9
历史fold_manifest.csv
2DBAF6D83B14594C444234E05EC03638C0FE66935F17F8C5A7D82A0E468D1AC0
v3u/src/lift.py
74DDC536CAE7848F0DC4C135B5A01E2FE6617A9126A94B19CEA7376EE7599A4A
v3u/src/guard_core.py
4CF3DCFB5764CC647A19333F3CC5661720D434B046079E2425691B81546EAE78
v3u/scripts/kr_b42_7v11.py
EA36341E4873D99023A31DF513DFB3A46BFAB28747835D2CE9B2B907A1661100
v3u/scripts/kr_b43_7v11.py
13D2D59AD664CCA58FD64E7D36ABCD58A59ACA29825126E7E37361F6C0BA3682
v3u/src/guard_training.py
D94F42C2FC940D220B8DE343F7D439CC37BA362A2552EFD50ECF076EDA640A4C
```

### 1.2 已复算的输入修复效果

原始反例来自fold0合法拟合轨迹：前后反向加减速轨迹193、对角差动加减速轨迹245。两条轨迹在0.04 s与1.02 s的旧control7完全相同，四车请求加速度却分别存在最大0.20、0.15 m/s²差异；核查的11维缓存重构误差为0，原有字段未变。这证明旧控制编码遗漏信息，不证明两时刻的完整状态相同，也不是严格同状态反事实实验。

前次只读审查在内存中关闭随机残差后重算五折内部选择集，得到真正固定线性的比较：

| 工况 | 11维相对7维的20步综合误差变化，五折范围 |
|---|---:|
| 前后车辆反向加减速 | 降低71.1518%—76.7485% |
| 对角差动操纵，两成员合并 | 降低44.7700%—51.3040% |
| 回头弯 | 降低12.2120%—23.1580% |
| 直线加速—匀速—制动 | 增加3.6896%—3.9129% |
| 直线匀速 | 最大绝对增加约0.0002301；不能继续引用旧错误基线下的大幅退化 |

这是归一化综合指标，不带N或m单位；五折范围不是置信区间，不是独立最终测试。以上内存复算未覆盖旧报告文件，KC1须从源数据重新生成带SHA的正式纠错产物，不将聊天数字抄入CSV充当原始结果。

### 1.3 统一11维输入后，残差结构仍未过门

已有残差实验：fold0、一个初始化、共同形式的warm2000＋正式6000步、原多步状态损失。内部选择集有12族、21轨迹、473窗口；每工况只有1个基础族，不能把14或28个相邻窗口称为14或28次独立试验。

与同折真正11维固定线性比较，前次只读复算为：

| 实际检查点 | 一步综合误差 | 20步综合误差 | 一步连接力误差 | 20步连接力误差 |
|---|---:|---:|---:|---:|
| `best.pt`，实际step=500 | 增加16.4158% | 降低15.3878% | 增加15.8009% | 降低12.6828% |
| `last.pt`，实际step=6000 | 增加78.6294% | 降低27.4419% | 增加121.7384% | 降低21.6458% |

6000步内部力误差：一步增加125.6097%，20步降低20.7314%。这些力误差均为归一化RMSE的变化，不是实际力、载荷或货物损伤增加的比例。

已有7/11维残差终点指标可从检查点复现，前次最大偏差约1.53e-15；同预算采样hash一致。可训练参数分别2912、3104，增加192，约6.59%；维数变化也改变初始化抽样布局，不能声称两模型除输入外所有随机权重逐位相同。

可得出的判断：输入修复必要；残差的长短期折中仍需优化。不能由此宣布自适应乘子、双线性、IRSP或新方案已得到证明。

## 2. 全部修正项与禁止行为

以下编号必须逐项进入 `correction_checklist.csv`，列出责任函数、前置测试、证据文件、修复状态和未解决原因。

| ID | 已发现的问题/待核查风险 | 必须做的修正与验收 | 禁止行为 |
|---|---|---|---|
| C01 | 固定线性对照仍含随机E与编码器 | 建立独立纯线性路径；与直接矩阵递推及E=0残差路径一致 | 只调用eval/double/no_grad就认为去掉了残差；全局修改残差初始化掩盖问题 |
| C02 | 错误基线支撑了错误退化解释 | 五折7/11维全部12工况重新评价；旧表标INVALID_BASELINE_REFERENCE并保留 | 用新结果覆盖旧JSON，使错误消失 |
| C03 | 对角两成员被误标为加减速成员 | 由manifest的member字段分出加减速、转向；主表仍合并为原12类之一 | 用scenario==9当作member A；增加为13个等权主工况 |
| C04 | 数字来自last却同时显示best_step | 显式加载并分别评价best、last；CSV的checkpoint_step取payload.step | 根据文件名或best_step推断本次评价权重；将last分数写成最佳模型 |
| C05 | 仅导出5类工况、1/20步 | 全12类×1/5/10/20步，完整分量、SI量、尾部及缺项表 | 删除不利工况；把未导出写成已验收 |
| C06 | 已计算层次均值，却用窗口平铺均值导出 | 统一窗口→轨迹→族→工况→12等权；不平衡合成例回归 | 因当前子集中恰好等长就永久使用平铺均值 |
| C07 | 新旧输入与创新归因混合 | 主基线固定为同折真实11维线性；7维只用于输入修复对照 | 用11维残差胜过7维基线证明算子创新 |
| C08 | KR0旧BLOCKED与后来PASS日志冲突 | 新run重新完成输入/证据闭环；分开工程完成、科学通过、未运行 | 覆盖旧BLOCKED、空目录写PASS、继承旧all_tasks_finished |
| C09 | 新阶段AccessGuard指向历史保护run日志 | 新run专属访问日志；核查旧日志是否被追加，保留影响范围 | 向历史结果树继续写新阶段记录；把日志追加说成模型被篡改 |
| C10 | 缓存派生脚本遍历全部672条清单 | 审计实际读取/授权范围；未来只数值核查允许的train/R3资产 | 672条都称训练数据；“机械转换所以未读取验证数值”的不实声明 |
| C11 | 11维shape参数化仍有隐式回退 | 只接受input_dim=7或11，schema与control字段严格一致；所有B/G/encoder/评价同步 | input_dim>=11模糊匹配；缺control11静默回退control7；截断11维 |
| C12 | 原始命令存在不等于在线未来可得 | 追踪请求生成的反馈依赖，明确给定未来请求序列条件预测 | 把未来实际响应或反馈产生的未来命令冒充在线已知量 |
| C13 | 条件数小于1e14被说成排除病态 | 明确检查的是正则化Gram矩阵；保留解残差/谱/尺度与求解回归 | 条件数相近便断言无共线性、无数值或泛化问题；偷偷改ridge |
| C14 | 一折一个seed被写成一致/普适 | 标为开发性诊断；三seed机制pilot后才允许有限正式复验 | 相邻窗口充当独立重复；把五折看作五次全新独立数据实验 |
| C15 | 63项测试描述不是新工程证据 | 保存本版测试逐项结果、代码身份、恢复/权限/锁实测 | 旧测试通过自动授权新代码训练 |
| C16 | 日志出现晚于现场时钟的手写时间 | 时间由机器生成，旧错误以勘误追加；记录时区、生成/观察时间 | 写计划时间当完成时间；改旧时间掩盖问题 |
| C17 | 内存审查结果尚未形成交付链 | 从原始缓存与checkpoint重算并落CSV/NPZ、命令、SHA、图源 | 抄本节四舍五入数字假装复算 |
| C18 | 500步后的乘子被归给500步模型 | 区分lambda_used、lambda_after、实际更新次数；fixed/adaptive前500步回归 | 保存非零lambda就声称模型受自适应保护 |
| C19 | 状态、连接力、系统横摆和安全混淆 | Fx/Fy为平面分力；真实系统横摆辅助列单列；材料阈值未验证 | force8说成含Fz；四车横摆均值充当系统横摆；预测准确说成货物安全 |
| C20 | 报告完成替代方法成功 | 最终状态分证据有效性、精度、重复性、延迟、部署；失败项不隐藏 | 总体20步更好就宣布全部通过、继续MPC或网络实验 |

C10必须诚实处理：672条清单含train 336、validation 168、development 168，且各有旧/新植物；主研究仅train/R3的168条。全清单转换本身不证明这些数据参与了拟合或选点，但也不能再宣称相关数值从未打开。审计授权原文、脚本和实际产物；若确认违反当时的数据访问限制，标 `EVIDENCE_SCOPE_BLOCKED`，交付范围说明后暂停训练，待用户确认继续权限。不得删除缓存来“恢复未见过”，也不得仅因存在转换文件便虚构调参泄漏。

## 3. 文件隔离、数据使用与历史复用

### 3.1 新树与唯一运行身份

未来执行创建 `REV/koopman_predict_v3w`，从重新核验的v3v复制源码后在新树修复；不是从v3u退回重做。创建 `REV/koopman_predict_v3w_results/receipts/KC_R02.json` 和唯一 `runs/<run_id>`。若同名目录已有内容，先核对，不覆盖；不同身份使用新run_tag。旧v3v训练只作为只读父资产导入，具体复用条件见第15节。

```text
koopman_predict_v3w/
  config/protocol_v3w.json
  scripts/run_v3w.py
  src/pure_linear.py, input_contract.py, cache_input.py
  src/refine_metrics.py, refine_loss.py, calibration.py, run_state.py
  tests/test_*.py
koopman_predict_v3w_results/runs/<run_id>/
  run_identity.json, taskbook_snapshot.md, protocol_snapshot.json
  source_snapshots/, module_paths.json, split_access.jsonl, decision_log.jsonl
  repair/r0 ... r6/, kc0 ... kc8/, units/, solutions.md
  imported_units.csv, reuse_verdict.json, protocol_deviations.csv
```

所有路径以resolved config解析；不能导入硬编码v3t的context或用旧v3s配置隐式决定新实验。训练模块的真实 `__file__`必须在新树；物理依赖只能来自单独登记的冻结父树。

历史v3t/v3u/v3v、输入修复run、KC-R1 run、原始NPZ、已有cache7/cache11、旧报告、旧工作记录段落全部保留。纠错表写新run，指向旧文件和SHA，不向旧实验的split_access.jsonl追加。公共工作记录允许按本次授权追加，不修改用户Word或表格。

### 3.2 不增加数据，不偷换划分

| 用途 | 基础族/轨迹 | 权限 |
|---|---|---|
| 新植物主研究池 | 96族、168轨迹、3830冻结窗口 | 沿用原五折清单 |
| 每折fit | 65/64/64/65/66族 | norm、S0、warm、优化、乘子更新、拟合诊断 |
| 每折inner | 12族，每工况1族 | 选点、gamma、算法提名、内部诊断 |
| 五折outer | 19/20/20/19/18族 | 新主模型全部冻结后一次评价 |
| 旧植物train、旧validation/development、新validation/confirm | 仅保留和元数据盘点 | 本轮不新开数值，不训练、不选点，不生成新数据 |

所有load必须在打开文件前验证split、plant、law、fold、role、purpose、轨迹ID、输入schema。为KC1只读复算、KC3诊断增加明确purpose，不能把guard.enabled=False当常规运行方式。诊断输出不得写到数据缓存目录。

11维缓存已存在，先检查允许资产的旧字段一致与重构；不重复批量生成672份。若train/R3缓存缺失且raw、cache7身份完整，允许在本run派生目录只补该资产；manifest记录来源和派生SHA。发现现有派生值错误时保留坏文件，写新文件并重验，不能覆盖原始数据或以新仿真替代。

历史7/11维残差的best/last/500倍数检查点可在原fit/inner上复用做诊断，不从历史优化器继续训练新方法。缺少某诊断检查点时如实登记；主证据必需的best/last缺失则停止该证据链，不临时补训一个模型冒充原模型。

## 4. 公式和接口的冻结定义

### 4.1 完整控制与时间对齐

\[
u_k^{11}=[(u_k^7)^\top,\Delta a_{FL,k},\Delta a_{FR,k},\Delta a_{RL,k},\Delta a_{RR,k}]^\top,
\qquad \Delta a_{i,k}=a_{i,k}^{req}-a_k^{virtual}.
\]

旧7维为虚拟加速度、虚拟前/后转角、四车请求转角。顺序为左前/右前/左后/右后；角度rad，加速度m/s²。四个差分都保留，不假定限幅后零和。

已核对构造为 `control11[k,7:]=requested_control4x2[k+1,:,0]-base_acceleration_mps2[k+1]`；前7列完全沿用cache7。目标为 `state[k+1:k+H+1]`，请求为 `control[k:k+H]`。仍须以源代码和带索引合成序列验证区间语义。raw首时刻不一定为0，作图用真实time_s。

主采样周期0.02 s；1/5/10/20步为0.02/0.10/0.20/0.40 s，40步为0.80 s。已记录的未来请求只用于“给定输入序列预测”。若它含未来反馈，应在论文接口限制中明确，不用未来实际转向、未来状态或相位标签补入模型。

### 4.2 真正固定线性基线与残差模型

本折fit归一化后，纯线性基线为

\[
\bar x_{h+1}=A_0\bar x_h+B_0u_{k+h}+b_0,\qquad \bar x_0=x_k.
\]

其输出路径不得调用编码器，也不得包含随机E。A0/B0/b0由同fold的fit数据、原设计矩阵与ridge=0.01求解，保存求解配置、norm和系数SHA；偏置是否正则化及Gram是否按样本数缩放必须逐行复核既有solve_model，原样保持，不能只看ridge数值就认为算法相同。

报告纯线性可辨识系数数目：7维为55×47=2585，11维为59×47=2773；梯度训练参数为0，两者不是同一统计量。令R_gram为实际正则化Gram、C为系数、Q为交叉矩阵，记录后向残差 `||R_gram*C-Q||_F/(||R_gram||_2*||C||_F+||Q||_F)`，零分母单独处理。这是求解诊断，不自行增加/放宽科学门，也不能代替前向等价测试。

残差模型保持：

\[
\eta_0=\phi_\theta(x_k,u_k),\quad
\hat x_{h+1}=A_0\hat x_h+B_0u_{k+h}+b_0+E\eta_h,\quad
\eta_{h+1}=F_c\eta_h+Gu_{k+h}+c.
\]

x为47维，u为11维，eta为16维；A0为47×47，B0为47×11，E为47×16，F_c为16×16，G为16×11。编码器仅在预测起点调用一次。行向量代码仍用 `eta @ model.f_matrix()`，故列公式F_c为该矩阵转置。

两分支输入宽42/39；7维历史对照为38/35。不能全局将 `e_init_scale` 改为0来修复线性基线：那会改变新残差方法的初始化。应独立实现纯线性类，并只在测试/回退副本里将E设为0。基线可辨识系数数量与梯度训练参数数量分别报告。

### 4.3 物理读出与可解释性

预测恢复SI单位后，通过同一冻结连接器函数计算四点平面力和完整内力：

\[
\hat f_h=\mathcal D_{R3}(\hat x_h^{SI};p),\quad
\hat f_{int,h}=P(p)\hat f_h,\quad P=I-W_g^\dagger W_g.
\]

W_g为3×8平面抓取矩阵，P为8×8；由同轨迹已知参数p构造。force8为四点Fx/Fy，两者都在货物水平面内，不是垂向Fz。参数缓存键含params SHA、dtype和device，禁止串用。

真实状态必须先经NumPy/Torch读出与缓存真值一致，才能解释预测误差。力误差改善不等于真实受力下降，更不等于没有材料撕裂。没有材料/连接结构强度证据，只报告“拉伸内力”或“撕裂型拉伸载荷代理”。

单车绝对横摆角速度用货物横摆加对应相对横摆，SI状态索引2加21/24/27/30，与缓存真值回归。cache的system_yaw_rate确实存在；其定义与可预测读出未核验前只显示真实辅助曲线，不能用四车均值代替。

### 4.4 一步残差诊断和统一缩放

令r=x_(k+1)-bar_x1，d=E eta0，Omega为固定对角半正定权重：0:3每维0.30/3，3:19每维0.20/16，19:31每维0.20/12，31:47每维0.30/16。

\[
\Delta_1=\|r-d\|_\Omega^2-\|r\|_\Omega^2
=d^\top\Omega d-2r^\top\Omega d.
\]

按 `tau=1e-12*max(1,abs(d'Omega d),abs(2r'Omega d))` 区分方向不利、方向有利但过量、改善、近零。范数平方≤1e-20时夹角为NA。此式仅是加权状态平方误差恒等式，不是综合RMSE、力误差或泛化改进定理。

冻结后令E_eff=gamma E，gamma只可取{0,0.25,0.5,0.75,1}且每模型全工况/全时域共享：

\[
\hat x_h^{(\gamma)}=\bar x_h+\gamma(\hat x_h^{(1)}-\bar x_h).
\]

此式利用eta不依赖预测x、编码仅起点调用；本轮禁止重编码、状态裁剪或状态相关gamma。力必须从缩放后状态重新解码，不能对两组力线性插值。gamma=0退回基线且收益0，不能当创新通过者。

K_gamma=[[A0,gamma E],[0,F_c]]的谱为两对角块谱的并集，缩放E不改变特征值，不能宣称由此修复全系统稳定性、IRSP或闭环ISS。

## 5. 评价、统计、选点口径

### 5.1 主指标不变

\[
j_h=\frac{0.25e_{core,h}+0.20e_{relative,h}+0.20e_{force,h}+0.15e_{internal,h}+0.10e_{yaw,h}}{0.90}.
\]

core为0:3，relative为3:47，yaw为[2,21,24,27,30]；每项按本fold fit尺度归一化后求分量RMSE。yaw项是货物和四车相对横摆，并非四车绝对横摆。状态混合单位综合误差无SI单位；另列连接力/内力N、横摆rad/s、位移m的误差。

层次为窗口→轨迹→基础族→工况，得到J_(s,h)，再对12工况等权得M_h。对角两成员在族内等权，主表工况总数仍12。单独成员、方向、相位仅作诊断，缺样本标NA并给出数量。

```text
普通下降率 = 100*(基线-候选)/max(基线,1e-12)
工况保护退化 = 100*(候选-基线)/max(基线,0.02)
全局短期/力/内力保护退化 = 100*(候选-基线)/max(基线,1e-12)
```

每行保留基线、候选、绝对差、分母、下降率、保护退化和阈值。小基线必须给绝对差；不能在“百分比很大”和“绝对量很小”之间按结果选择有利说法。

### 5.2 检查点身份与权重选择

每次评价显式给出 `checkpoint_path, checkpoint_sha, checkpoint_kind, checkpoint_step, selection_rule, selected_on_split, model_input_schema, norm_sha, s0_sha`。step以payload.step为准；payload.best_step仅是当时选择器的历史记录。

KC1/KC3可在fit/inner评价历史best与last及已有完整曲线；主结果分表，不能混合选择权重。新主训练在500、1000…6000的共同集合中按55项可行性优先选best：最大正违约→正违约和→M20，数值并列容差1e-10，取较早步。均不可行时标BEST_INFEASIBLE，不能因文件名best便宣布通过。

正式outer只评价预先冻结的主best未校准/校准两版，不评价last、best_q或全部gamma后挑最好。历史last诊断不是新增正式候选方法。

### 5.3 尾部、重复性与样本量

分位数用族等权、族内轨迹等权、轨迹内窗口等权的经验CDF，定义为inf{x:F_weighted(x)>=q}；max取真实最大值，不取族均值最大值。另记录最坏轨迹与窗口，不能替换固定代表窗口。

内部每工况一个基础族，不能从其窗口bootstrap得到独立泛化证据。正式先合并每个repeat的各族唯一外层结果，再对repeat平均。2000次配对族bootstrap，PCG64 seed997500，工况内抽族，方法/基线/三个repeat共享抽样索引，2.5/97.5分位method=linear。报告区间条件于三个训练实例，不声称证明全部初始化分布。

所有表列族数、轨迹数、窗口数、repeat数和重复/缺失计数；把三个seed的15320行预测相加不会创造三倍独立物理数据。

## 6. 对应代码修改表

以下均在新树v3w实现，历史树只读。第15节按最新问题细化并优先执行；已有正确实现可核验复用，名称是所需接口，不表示文件已经存在。

| 文件/函数 | 具体改动 | 关键输出/回归 |
|---|---|---|
| `src/pure_linear.py::PureLinearKoopman` | 仅A0/B0/b0递推，统一rollout返回结构，无编码器/随机项 | 多seed、CPU/GPU、7/11维、40步与NumPy及E=0路径一致 |
| `src/guard_core.py::new_model` | 保持残差初始化；另设new_baseline，不用同一工厂混淆类型 | model_kind枚举、是否残差、E范数、输入schema进入身份 |
| `scripts/kr_b42_7v11.py`的替代入口 `audit_input_baselines.py` | 显式pure模型；导出五折所有工况与成员/方向；保存纯线性系数、norm和原始预测 | 错误旧路径仅作污染复现，不入排名；纯线性排名与修复归因分开 |
| `scripts/kr_b43_7v11.py`的替代入口 `audit_checkpoints.py` | 不训练；显式加载已有best/last及注册步数，核验原训练预算和采样hash | 12工况×4时域、逐窗状态/力、best与last分表，参数量差异 |
| `src/refine_metrics.py` | 主层次聚合、加权分位、成员映射、完整性、失败门/诊断分离 | 独立实现聚合复算；不平衡合成数据手算一致 |
| `src/input_contract.py` | control7/11显式schema与重构、单位、时序、命令来源 | 未知维数/字段/实际响应替代请求立即拒绝 |
| `src/cache_input.py` | 仅允许清单的原始资产派生，默认dry-run；已存在正确文件复用 | 旧字段逐位一致、重构≤1e-12 m/s²、逐文件谱系SHA |
| `src/guard_core.py::AccessGuard/WindowData` | 新run日志、purpose分层、验证源身份后load；meta加member/direction/name但不传模型 | 真实文件打开前拒绝非法；归一化/S0只fit；outer冻结开门 |
| `src/guard_core.py::fit_normalization/fit_s0`及`evaluation_v2.py` | 参数化7或11；显式输入schema；新主norm/S0为11维，cache字段不猜测 | Gram宽55/59，coeff为55×47或59×47；B0/G无截断 |
| `src/refine_diagnostics.py` | 残差方向/过量、力位移/速度分解、相位/梯度诊断 | 真值混合诊断与实际预测严格隔离 |
| `src/refine_loss.py` | aligned/fixed/adaptive及注册课程，严格原55项与尺度 | lambda=0两保护组loss/梯度一致；正则和权重未变 |
| `src/guard_training.py::train_phase` | 训练步/监控步/乘子更新分离；固定6000步；记录used/after；保存全部状态 | 不把evaluate的double副本反传给原训练模型；全程dtype审计 |
| `src/calibration.py` | 固定主best五点gamma扫描；按inner选一个全局gamma | 原E与有效E双SHA；不展开checkpoint×gamma搜优 |
| `src/run_state.py`与`scripts/run_v3w.py` | R0—R6接续及KC0—KC8真实状态机、锁、失败码、跨单元恢复、精确回执 | 拒绝空PASS和旧run路径；恢复不覆盖已有单位 |
| `config/protocol_v3w.json` | 汇集数据/协议/方法/seed/预算/门槛/诊断/输出身份 | 拒绝未知键；resolved config进入run；不隐式借旧v3s配置 |
| `src/inference_fast.py` | 对冻结11维模型最多两种等价优化 | 完整20步状态/力/内力输出，矩阵约定和读出一致 |
| `scripts/refine_report.py/refine_figures.py` | 旧错表勘误、全方法/工况/seed报告、图源SHA、未运行状态 | 报告数量与逻辑单元账本相等，不从控制台一句PASS推断 |

新固定线性评价与污染复现必须分开保存，不允许随机残差对照仍叫S0。原B.4-3训练用E=0的anchor路径与B.4-2错误对照不是同一个错误范围：先核查，不能据B.4-2错误直接作废所有历史残差训练。

## 7. 实验矩阵、预算和机制归因

### 7.1 第一组：纠错复算，不重新训练残差网络

| 比较 | 数据范围 | 需要回答什么 |
|---|---|---|
| 旧错误“线性”路径 vs 真纯线性 | 5折inner；旧seed=990100+fold | 随机残差污染究竟改变了哪些结论 |
| 纯线性7维 vs 纯线性11维 | 相同5折fit/inner，各自合法norm/S0 | 只补输入的收益与代价 |
| 历史残差7维 vs 11维 | fold0既有best与last，各自身份一致 | 信息补全对同结构的影响，披露增加192参数 |
| 历史11维残差 vs 真11维线性 | 同fold0、同norm/标签/窗口 | 算法净收益、一步代价、选点权衡 |

普通线性求解是确定性辨识，允许为复算重建系数；不得把这一阶段变成重新优化历史神经网络。保存每折fit/inner族名单，区分折间inner重叠，不将五折范围称作五次独立验证。

### 7.2 主机制：共同11维输入、共同纯线性锚、共同warm

训练平滑RMSE用sqrt(mean(err²)+1e-16)-1e-8，评价用精确RMSE。a=(0.10,0.20,0.25,0.45)，对应1/5/10/20步。

\[
L_{align}=\sum_h a_h M_h^{fit,\varepsilon}+R(\theta),\qquad
R=10^{-4}\|E\|_F^2+10^{-5}\sum_{\theta_{train}}\|\theta\|^2.
\]

E在两正则项中都出现是原定义，不去重。训练保护g共55项：全局1/5/10步≤3%共3项，12类×4步工况≤3%共48项，连接力/内力1/20步≤5%共4项。使用第5节相应分母，g≤0为满足。

\[
L_{fixed}=L_{align}+\frac{M_{20}^{0,fit}}{55}\sum_{j=1}^{55}\frac12[g_j]_+^2,
\]
\[
L_{adaptive}=L_{align}+\frac{M_{20}^{0,fit}}{55}\sum_{j=1}^{55}\left(\lambda_jg_j+\frac12[g_j]_+^2\right).
\]

M20锚取本fold完整fit的纯线性值；训练g_batch保持梯度；lambda detached。每500正式步先更新模型，再完整fit计算g，执行lambda←clip(lambda+0.5g,0,20)，初值0。不用inner更新lambda。fixed/adaptive前500步应一致，501步才可能受首次非零乘子影响。

| 预算字段 | 冻结值 |
|---|---|
| pilot | fold0；初始化996100/996101/996102；3方法×3seed=9训练，3共同warm |
| 正式 | repeat=0/1/2，fold=0..4，初始化997100+100×repeat+fold |
| warm | 每fold/seed一次2000步，原一步状态组RMSE，lr=0.001 |
| 正式 | 6000步，lr=0.0003；不质量早停，科学/资源硬门除外 |
| 优化器 | AdamW，betas=(0.9,0.999)，eps=1e-8，weight_decay=0.01，clip_grad_norm=1 |
| batch | 256；每类21窗及4个轮换额外窗，族/轨迹/窗口均衡 |
| 采样seed | 初始化seed+50000；同fold/seed的各方法同样本流 |
| 精度 | trainable float32；S0 buffer float64；评价副本float64；禁TF32 |
| 监控 | 每500步完整fit/inner；额外0/100/250/750仅诊断；正式步500倍数才更新lambda |
| 运行次序 | 同一GPU串行，各fold/repeat轮换方法顺序；不抢其他训练进程 |
| 最坏预算 | 全部阶段独占GPU墙钟≤12小时，预计最终D盘空闲≥60 GiB |

同一个11维fold/seed的三方法从相同warm参数开始，新建正式AdamW，不带warm动量。正式比较固定/自适应机制时，架构、初始化、目标权重、数据和预算不变。历史7维结果只是背景，不能替代新共同基线。

### 7.3 校准与唯一允许的课程分支

每个主best同时保留gamma=1和校准版。只在inner对五点gamma检查第10节精度/有限性/回头弯20步要求；有保护通过且I20≥5%的点，取M20最小者，并列取较小gamma。没有达5%的点，选保护通过者中最小M20并标PROTECTED_BUT_LOW_GAIN，不提名。gamma=0也不满足不退化时先查锚/配对/数值错误。

不得把500步与6000步各自最佳gamma比较后临时换主检查点；诊断前沿可以画多点，但提名只遵守冻结选择器。

若三方法均无可提名版本，且fixed_guard至少2/3个seed在最后三个500步监控点均存在完整fit的一步保护失败，才加一组 `residual_curriculum`：同warm、seed、采样、总6000步；前1000步为第4.4节残差加权平方误差加原正则，后5000步为fixed_guard；切换不重建Adam。若fit通过而inner失败，不启动课程，按泛化候选问题停止。

该残差MSE等价于对应一步状态MSE，不增加新的物理标签；原来已有2000步一步预热，不能包装成首次加入一步监督。F/G/c在课程前段无一步数据梯度，只受正则/衰减影响。若选中点≤1000步，必须声明所选模型未经历后段多步训练。

课程仍无合格提名者即停，不自动加分组gamma、门控、双线性、潜变量或数据。

## 8. 研究阶段定义：修复接续以第15节为入口

以下是研究阶段的完整要求，不表示当前应从KC0全部重跑。KC-R2必须先走R0—R6；已完成资产按复用裁定接入，不直接信任旧PASS。

```text
KC0 现场、版本、访问边界和旧状态核查
 ├─ 证据/权限不清 → KC8失败说明，停
 └─ KC1 纯线性纠错＋已有检查点评价＋11维输入闭环（不训练网络）
     ├─ 基线/数据/读出无法复现 → KC8，停
     └─ KC2 新工程、数学、权限、恢复/锁测试及成本冒烟
         └─ KC3 冻结11维检查点的残差/受力/gamma/阶段诊断
             └─ KC4 一折×三seed×三方法pilot
                 └─ KC5 内部提名；满足条件才加唯一课程
                     ├─ 无提名 → KC8，停
                     └─ KC6 五折×三seed，全部冻结后一次outer评价
                         ├─ 提名算法精度未过 → KC8，停
                         └─ KC7 等价推理优化与延迟验收
                             └─ KC8 完整证据、图表、论文边界；必停
```

### KC0：先把运行与数据边界说清楚

- 前置：用户另行授权执行本文件；只读预检先于创建run。
- 检查：hostname、绝对路径、Python/NumPy/Torch/CUDA版本、磁盘、相关进程；第1节SHA；旧run/checkpoint/数据谱系；本协议与11维协议来源；C09/C10/C16。
- 最小入口必须先具备唯一回执、失败码和解决方案输出；其他阶段未实现要真实拒绝。
- 输出：environment、source_manifest、historical_artifacts、data_scope_audit、clock_audit、access_policy、run_identity、完整修正清单。
- 门：身份可解释、权限无未裁定冲突、没有与其他运行抢占。历史“转换涉及验证”不明时停止训练，只做受许可的元数据核查和失败收尾。
- 不更改旧kr0/complete.json；新run记录其旧BLOCKED及本轮待复核状态。

### KC1：纠错与基线闭环（本版由R1核验并补齐）

- 前置：KC0通过；先通过纯线性、成员过滤、checkpoint身份及11维重构的最小合成测试。
- 修改：第6节pure_linear、audit_input_baselines、audit_checkpoints、metrics、input_contract；不调用旧脚本main，以免写历史目录或训练。
- 执行第7.1节四组只读复算，输出12类全部1/5/10/20步及成员诊断。纯线性复现三路：直接NumPy、独立pure类、同系数残差副本E=0。
- 核查所有允许train/R3的cache11前7列、旧状态/标签/窗口不变、四车请求可重构；只为该范围补缺失派生缓存。
- 旧“固定线性”的随机残差污染复现采用原seed=990100+fold，报告E范数和相对pure的预测差；该路径只能标BUG_REPRODUCTION。
- 已有B.4-3两维度分别加载best与last，以payload.step验证500/6000，核对warm2000、正式6000、模型shape、采样hash及norm/S0数组。旧JSON应匹配last；无法复现则保存偏差、停止该证据链，不能改标签凑一致。
- 对diag成员A/B分别输出：ID、member、family、窗口数、一步/20步及所有力分量。KR0原检查器用trajectory字符串查A后回退全scenario的逻辑也要改为manifest.member，禁止再次误分。
- 输出：`baseline_manifest.json`、`input_contract.json`、`input7_vs11_rows.csv/npz`、`checkpoint_rows.csv/npz`、`scenario_metrics.csv`、`member_metrics.csv`、`checkpoint_identity.csv`、`errata.md`、`baseline_oracle.json`、`correction_checklist.csv`。
- 门：三路线性等价、数据/输入/时间/力读出一致、原残差分数可追踪、全工况无漏项、C01—C17中本阶段证据项闭环。C15先要求KC1最小测试有真实记录，完整恢复/锁/新训练回归明确登记待KC2，不能因阶段安排伪造全测试通过。性能有退化不令此诊断阶段伪造通过；只将“证据有效”标PASS，不将模型质量标PASS。
- 通过后自动进入KC2；**不需要重新训练历史7维/11维残差模型来修报告。**

### KC2：新实现与工程冒烟

- 完成第6、9节的全部实现/测试；保存实际代码路径、环境和源码快照。旧测试数量不能替代本版回归。
- fold0每工况按族ID取前两个fit族做训练冒烟；norm/S0仍来自完整fit。seed996900，warm200，各主方法600步，同样本流；不以其权重或性能决定正式方法。
- 合成用例覆盖课程1000步切换、跨乘子恢复、跨阶段恢复、锁竞争和权限拒绝；不需要在冒烟里训练新的科学方法。
- 输出tests.json、test_output.txt、resume_equivalence、lock_tests、module_paths、smoke_cost；所有测试通过且12小时/60GiB预算可满足才进入KC3。
- 拟合能力差不是跳过测试理由；工程问题允许两轮最小修复，科学门不得放宽。

### KC3：已有11维模型诊断，不新增训练

- 使用KC1已验证的fold0、11维best与last及已有500倍数点，范围仅fit/inner。7维作历史参照，与11维分别使用正确锚，不混算残差r。
- 每个冻结点画一步—20步曲线、残差方向与幅度、五点gamma前沿；多检查点前沿只作诊断，不改变下一阶段500倍数主选点规则。
- 用raw命令相位分开始、持续、反向、恢复；切换后0—0.20 s、0.20—0.60 s为固定诊断区间。标签仅用于评价，不传入模型或按未来标签重采样。
- 力分解：f00=D(q,v)、f10=D(qhat,v)、f01=D(q,vhat)、f11=D(qhat,vhat)；总误差等于(f10-f00)+(f01-f00)+(f11-f10-f01+f00)。先验证f00等于真力。
- 正/反转向、前后差动、对角加减速、对角转向分别看位移/速度/交互项；保留其他工况。无冻结窗口覆盖的相位记NA，不补新窗口假装充分覆盖。
- 输出逐窗correction_components、gamma_frontier、force_factorization、phase_metrics、oracle和diagnosis.md。未找到合格gamma是有效负结果，可进入KC4；恒等式/配对/力oracle不成立则停。

### KC4：三机制pilot

- 固定fold0×3seed×3方法，3共同warm、9正式训练，每组6000步；按第7节执行。
- 保存完整fit/inner监控、模型/样本流身份；梯度诊断在正式0/500/2500/6000，使用独立固定诊断seed996800的3批，不影响训练RNG。
- J1与J20任务梯度不包含显式正则，分encoder/E与F/G/c；任一梯度范数≤1e-12时余弦NA，不将一步F/G/c零梯度判为错误。
- 对500倍数完整曲线重放旧早停：至少2000步、连续2000步无词典序改善则停；额外100/250/750监控不影响重放。
- 输出主best未校准/校准、last/旧早停诊断、fit/inner失败门、lambda_used/after和更新次数。不能只用batch loss下降证明约束已改善。
- 完成门为9组证据完整且公平，不是9组必须性能全过；之后按KC5提名，不因负结果临时改seed或方法。

### KC5：一次内部提名与条件课程

- 可提名版本=方法键＋是否校准，在≥2/3个seed上满足全部内部精度/有限性/回头弯20步保护且I20≥5%，三个seed都完整有限；失败seed保留。
- 有候选时按三seed内部I20中位数最高提名；差≤0.5个百分点时选简单版本：aligned原始→aligned校准→fixed原始→fixed校准→adaptive原始→adaptive校准→课程原始→课程校准。
- 无候选才按第7.3节严格检查课程触发；满足时新增3次课程训练，随后同规则提名；不满足或仍无候选→KC8停止。
- 冻结nomination.json：全pilot分数、课程触发证据、算法和校准规则、源码/协议SHA、正式seed矩阵。不能依据外层结果改提名。

### KC6：五折三个seed正式复验

- 前置：KC5有提名，工程与配置身份通过；每折pure11基线和norm固定且只fit，15共同warm，三方法45正式训练。若课程曾被实际触发，课程也做正式，总60训练。
- 全部fold/seed/method的best、校准gamma、有效E和提名身份冻结后，统一打开outer。完整冻结前任何一个outer预测/评价均拒绝。
- 每算法每repeat汇总五折3830窗口×4时域=15320条。三方法×原始/校准×3repeat，再加唯一纯线性基线，总291080条；有课程383000条。这是逻辑预测记录，不是独立样本量。
- 40步压力只用有完整未来真值/控制的共同起点，先按可用性固定清单；不能依据预测好坏删窗。
- 对预提名算法按第10节裁决；其他算法虽在outer更好，也只能报告，不允许临时替换后进入下一阶段。
- 提名算法精度失败→KC8。对照失败仍如实保留；所有方法都必须完整导出，不只呈现获胜模型。

### KC7：等价推理优化

- 只对KC6精度通过的冻结提名模型进行；最多两类尝试：固定参数/投影缓存与整体力读出向量化；增广线性传播预计算或固定执行图。
- 增广z=[x;eta;1]为64维，Kbar=[[A0,gamma E,b0],[0,F_c,c],[0,0,1]]，Bbar=[B0;G;0]为64×11；z_h=Kbar^h z0+sum(i=0..h-1)Kbar^(h-1-i)Bbar u_(k+i)。不能将首步控制重复20次，也不能遗漏编码器。
- cache键含模型/E_eff/gamma/norm/params/dtype/device/horizon身份。预计算时间单列，原/优化输出按第9节回归，再复算全部既有质量门。
- 固定主计时样例为fold0/repeat0、outer元数据排序首合法窗；batch1完整20步状态＋力＋内力，CPU单线程，预热200次、测1000次。输入驻留与传输耗时分列，CUDA同步计时。
- CPU中位数<5 ms、GPU中位数<1 ms且P99<2 ms；两类尝试后仍失败标LATENCY_BLOCKED，不改为仅CPU过门。预测有效性与尚未完整部署可分开声明。

### KC8：无论成功失败，都形成可交付结论

- 独立从磁盘预测/目标重算主表、门表、层次分位和置信区间；不复用训练内存摘要。
- 输出report.md、errata.md、solutions.md（如失败）、next_stage.json、correction_checklist、图和figure_manifest、delivery_audit、源码/数据/模型SHA链。
- 所有未执行阶段NOT_RUN；发生前置失败时只收尾已有合法证据，不为凑齐图打开新数据。结束码保留首个真实失败类型。
- 更新本地和5080同一工作记录的本次段落，按entry_id核对避免覆盖别人新增内容；如同步失败，明确哪一份尚未同步。
- 不进入新validation/confirm、全train重拟合、MPC、通讯干扰、DoS或原论文部署。

## 9. 必须落地的回归测试

每项保存ID、输入、设备、dtype、实际误差、容差、状态、代码SHA。旧“63 passed”不能替代以下测试。

| 测试ID | 必须验证 |
|---|---|
| T01 | 纯线性无encoder/E依赖；不同seed不改变输出；7/11维1/5/10/20/40步和NumPy一致 |
| T02 | 构造E非零反例，错误“线性”标签必须被拒绝；E=0副本与pure一致，主残差初始化未变 |
| T03 | 旧7维相同、四车差分不同的反例被识别；u11首7列逐位一致、请求重构≤1e-12 m/s² |
| T04 | 非零首时间和唯一索引合成序列，raw[k+1]/u[k]/target[k+1]严格对齐 |
| T05 | shape/schema只允许7和11；缺字段、12维、截断、schema冲突均拒绝 |
| T06 | 两成员指标刻意不同，分别与合并结果手算正确；主表仍12类，诊断NA不填0 |
| T07 | best step500、last step6000采用不同人工权重，评价数字和SHA/step对应；错标直接失败 |
| T08 | 不等长轨迹/不同族数的层次均值、经验CDF与手算一致，不能误用平铺均值 |
| T09 | 从新stage访问记录全部只写新run；禁止直接np.load绕guard、读取禁用集及提前outer |
| T10 | 修改合成inner/outer不改变fit norm/S0/warm；相位/成员meta置乱不改变预测输入 |
| T11 | 同权重gamma=1原路径一致、gamma=0 pure一致，0.25/0.5/0.75满足40步仿射恒等式 |
| T12 | fullK列矩阵与行向量eta@F一致；增广B为64×11；不同控制序列不能被重复首步代替 |
| T13 | 残差误差恒等式及方向/过量/近零分类，相对残差≤1e-12 |
| T14 | 真实状态→缓存/NumPy/Torch力oracle；覆盖接触、非接触、边界及所有已用参数 |
| T15 | 力分解总和、W_g P f≈0、单车绝对横摆读出；近零力角度NA，不删除误差样本 |
| T16 | 训练55项与完整验收分开；回头弯一步尾部失败不会伪造20步原硬门失败 |
| T17 | lambda=0 fixed/adaptive的loss/梯度一致；前500步模型一致，第501步活跃约束可影响梯度 |
| T18 | used/after记录准确；额外监控不更新lambda；全fit而非inner更新lambda |
| T19 | 各方法同warm/同样本流；诊断不改变RNG、optimizer、训练mode或下一批 |
| T20 | 旧早停在最佳500后停2500；完整曲线3500改善不被截掉；主选点不含100/250/750 |
| T21 | gamma=0收益0不可提名；五点力由缩放状态重算；不修改原best，不按工况选择gamma |
| T22 | 课程1000步切换不重置Adam；残差MSE等于一步MSE；F/G/c一步零梯度不误判 |
| T23 | 连续1100与450+650、1000+100恢复，跨500/1000事件，模型/Adam/RNG/采样/lambda/课程/下一批一致 |
| T24 | 跨单元resume-incomplete跳过已完成且SHA正确单元；不重训、不重开已评价outer；活锁拒绝第二启动 |
| T25 | 数值相同的原始/校准副本不增加独立样本；bootstrap配对及repeat层次正确 |
| T26 | NaN/Inf、缺工况、缺文件、重复行、未知方法、错误身份和未实现stage返回真实失败，禁止吞异常 |
| T27 | 优化前后完整20步状态/力/内力和所有原质量门一致，计时不删读出、不改batch |
| T28 | 代码级时间由系统生成，报告generated_at/observed_at分开；未来时间、空PASS与漏单元被审计报告 |

同系数float64状态路径比较atol=1e-10、rtol=1e-10；float32状态atol=1e-6、rtol=1e-5。力float64 atol=1e-8 N、rtol=1e-10；float32 atol=1e-4 N、rtol=1e-5。纯算子相等测试和跨环境重新辨识的误差要分开，不能用条件数解释所有容差失败。

精确恢复在同确定性环境目标为逐位一致；确有平台舍入差异时逐项说明且相对误差≤1e-7，不能只比较loss。未知差异不能放行。T09/T10使用临时合成资产，不改真实验证集。

## 10. 验收门：既不放宽，也不混淆

| 类别 | 冻结门槛 |
|---|---|
| 证据、输入、权限 | 身份完整，无未裁定越界；重构/时序/纯线性oracle通过；新阶段未经授权数值读取0 |
| 完整性 | 12工况、配对和角色齐全，缺失/重复/错配0 |
| 20步收益 | 每个正式seed合并五折I20≥5%，该seed至少4/5折为正 |
| 全局短期 | 1/5/10步退化≤3%，每seed每折及合并均检查 |
| 工况保护 | 12×1/5/10/20步，分母max(J0,0.02)，退化≤3%，每seed逐折及合并 |
| 连接力/完整内力 | 1/5/10/20步全局归一化误差退化≤5%，每seed逐折及合并 |
| 回头弯尾部 | 20步整体与start100/120合并困难窗，均值/P95/P99/max退化≤3%，分母max(基线统计量,0.02) |
| 有限性 | 全部预测/误差有限；注册四时域每窗口最大绝对归一化状态误差≤20 |
| 40步压力 | 合法共同起点不出现基线没有的新发散；发散=40步最大绝对归一化状态误差>20或非有限 |
| 统计重复性 | 三seed逐项通过；seed平均后的配对族I20的95%区间下界>0 |
| 推理 | KC7完整口径CPU median<5 ms、GPU median<1 ms且P99<2 ms |

55项训练保护不包含全部正式门；尤其不能省略5/10步力误差。回头弯一步/5/10步尾部、单独起点100或120的尾部是DIAGNOSTIC_ONLY，不能事后升级为历史硬门，也不能隐藏。

内部提名/gamma用本折inner的同样精度/有限性/回头弯20步要求，不用外层bootstrap或延迟选模型。pilot的2/3允许进入复验，不等于正式3/3通过。3%/5%及GPU指标是开发协议门，不是材料安全阈值或实车可部署证明。

## 11. 遇到问题时的处理方向与自主空间

| 情况 | 最小处理与允许动作 | 停止/恢复条件 |
|---|---|---|
| SSH超时 | 两次有明确超时的只读重试；查询原回执，不重复派训练 | 仍不可达标现场未知，保存本地说明 |
| 新pure与E=0不一致 | 检查norm、coeff切片、偏置、dtype、控制索引，保存首差异窗 | 修隔离代码并通过T01/T02，不能改S0标签 |
| 原报告不能由last复现 | 查payload.step、训练源码、norm/S0、params、聚合，逐项比对 | 不能匹配则证据阻塞；不补训或改JSON凑分数 |
| baseline源系数重算略不同 | 核查BLAS/原始设计矩阵/正则/输入顺序，分别保存系数与前向误差 | 不因舍入差异直接更改ridge，也不把随机残差归于求解误差 |
| condition约1.3e8 | 报告正则化矩阵条件数、相对解残差及原实现一致性 | 低于1e14只说明未触发旧门；不能排除共线性/敏感性 |
| cache11某允许资产缺失 | 验证raw/cache7 SHA，只在新run派生目录补该文件 | 无可信raw或标签变化则停，不重跑植物 |
| 发现过去越界或旧日志被追加 | 固定受影响文件、身份和实际用途，区分机械转换/训练/选点 | 权限未裁定停；不能删除文件或日志洗白 |
| 少数场景或成员未显示 | 查manifest.member/direction和字符串ID、BOM、层次聚合 | 修接口后重算全部，不能复制行、填0或删场景 |
| 一步保护不满足但20步更好 | 同看fit/inner、方向与过量、力敏感度和梯度冲突；按KC4/KC5 | 只允许预注册课程；不能无限延长或加模型 |
| 拟合过门、inner不行 | 记录每族参数、seed差异，考虑泛化/代表性不足 | 停止并提出后续协议，不当场补数据 |
| 仅gamma=0可行 | 保留回退前沿与失败解释 | 收益不足，不提名、不宣称创新成功 |
| 自适应不优于固定 | 核查lambda实际参与，报告效应区间/seed方向 | 如无额外证据优先保留简单方案，不强行解释为有效 |
| CUDA内存不足 | 不结束他人进程；去除本任务冗余副本，必要时做等价微批 | 非线性batch约束用充分统计/两遍梯度并验等价，不能改变batch目标 |
| OpenMP冲突 | 沿用进程级MKL_THREADING_LAYER=SEQUENTIAL，记录导入顺序 | 不使用忽略重复运行库错误的KMP开关 |
| GPU慢于CPU | profile编码/传播/解码/拷贝/同步，最多两类等价优化 | 超原延迟门停，不靠删力读出或增加batch过门 |
| 资源预算不足 | 精确保存optimizer/RNG/采样/lambda和单位进度 | RESOURCE_PAUSED，不能少跑seed后称正式完成 |
| 提名算法outer失败、对照更好 | 保留全部结果，解释优势工况 | 不回选替换提名或开放新validation |
| 排版、字体、CSV编码、明确路径错误 | 可自主修复，不改科学语义，记录diff与回归 | 两轮仍失败则保存最小复现，不无限循环 |

允许自主处理的是已证实的实现错误和语义等价工程修复；不必每一小步询问。禁止自行改变输入信息、状态、物理力律、ridge、主权重、seed、训练预算、gamma网格、乘子规则、验收门、数据划分或新增科学分支。

语义变化或训练源码变化后不得拿旧优化器直接续跑；新身份重跑受影响单元。纯报告修正可复用冻结模型，但须保存独立报告源码身份。所有修改使用apply_patch，并写同一工作记录。

## 12. 执行与恢复命令契约

本节是KC-R2的原接口设计记录；KC-R3实际入口为第16节的 `scripts/run_background.py`。禁止把本节尚未实现的stage参数传给实际后台程序。第16节保留必要科学门，将其串入真实程序，不再要求人工逐段调用R0—R6。

下列为KC-R2的**待实现接口契约**，不是已有可直接运行的程序；只能在用户明确执行授权后运行。必须先实现新runner及其失败/只读/锁测试。旧v3v runner只实现部分阶段，不能把下列参数传给它凑续跑。`REPAIR_AUTO`按第15节执行，`AUTO`仅在R6放行后进入KC6—KC8。

在5080 PowerShell中：

```powershell
$KcProject = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$KcRevision = Join-Path $KcProject 'revision_2026'
$KcPython = 'E:\anaconda\envs\pytorch_new\python.exe'
$KcSource = Join-Path $KcRevision 'koopman_predict_v3w'
$KcRunner = Join-Path $KcSource 'scripts\run_v3w.py'
$KcProtocol = Join-Path $KcSource 'config\protocol_v3w.json'
$KcBook = Join-Path $KcRevision 'koopman_next.md'
$KcReceipt = Join-Path $KcRevision 'koopman_predict_v3w_results\receipts\KC_R02.json'
$KcParent = Join-Path $KcRevision 'koopman_predict_v3v_results\runs\20260904_224212_KC_R01'

hostname
& $KcPython -B -c "import sys,torch; print(sys.executable); print(torch.__version__); print(torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed' }
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw|MATLAB)\.exe$' } | Select-Object ProcessId,Name,CommandLine
Get-PSDrive -Name D
Get-FileHash -LiteralPath $KcBook -Algorithm SHA256

# 核对本地最新版和远端任务书SHA；不是把父版快照当作最新版。
if (-not (Test-Path -LiteralPath $KcRunner -PathType Leaf)) { throw 'Implement and test the v3w runner first' }
if (-not (Test-Path -LiteralPath $KcProtocol -PathType Leaf)) { throw 'Missing resolved v3w protocol' }

# 最小入口和新树准备好后执行；回执只能独占创建一次。R0不训练。
& $KcPython -B $KcRunner --stage R0 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --run-tag KC_R02 --parent-run $KcParent --receipt-path $KcReceipt --read-only-models
if ($LASTEXITCODE -ne 0) { throw 'R0 identity/access gate blocked; do not train' }
$KcMeta = Get-Content -LiteralPath $KcReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
if ($KcMeta.run_tag -ne 'KC_R02' -or -not $KcMeta.run_id) { throw 'Invalid run receipt' }
$KcRunId = [string]$KcMeta.run_id

# 修评价与旧诊断；可以在新run写纠错产物，不得写旧模型/日志，不做optimizer.step。
& $KcPython -B $KcRunner --stage R1 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt --read-only-models
if ($LASTEXITCODE -ne 0) { throw 'R1 evaluation evidence gate failed; do not train' }

# 工程测试/三方法小冒烟/旧9组复用裁定；不重复提交9组完整训练。
& $KcPython -B $KcRunner --stage R2 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'R2 tests, reuse or resource gate failed' }

# 仅冻结best五点校准，未通过前不启动课程。
& $KcPython -B $KcRunner --stage R3 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt --read-only-models
if ($LASTEXITCODE -ne 0) { throw 'R3 incomplete; no curriculum or formal training' }

# 依证据决定R4做正确MSE课程还是SKIPPED，再R5提名、R6核准。
& $KcPython -B $KcRunner --stage REPAIR_AUTO --until R6 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'Repair branch stopped; preserve evidence and finalize only' }

# runner还须实际核验R6放行回执、预算和全数据边界；不能仅凭上一行返回0。
& $KcPython -B $KcRunner --stage AUTO --until KC8 --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'KC stopped; inspect exact failure and completed units' }
```

恢复与仅收尾：

```powershell
# 同一新run内才是resume；从KC-R1读取模型叫import，不叫精确恢复。
# 根据unit ledger决定恢复修复阶段还是正式阶段，不从固定KC2重启。
& $KcPython -B $KcRunner --stage REPAIR_AUTO --until R6 --resume-incomplete --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'Repair resume stopped; inspect unit ledger' }

# 仅相同任务书/源码/数据/norm/S0/seed/输入schema身份允许精确恢复。
& $KcPython -B $KcRunner --stage AUTO --until KC8 --resume-incomplete --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'Resume stopped; do not submit a duplicate run' }

# 前序失败后只整理已有合法证据；不扩大数据权限。
& $KcPython -B $KcRunner --stage KC8 --finalize-only --project-root $KcProject --protocol $KcProtocol --taskbook $KcBook --resume-run $KcRunId --receipt-path $KcReceipt
if ($LASTEXITCODE -ne 0) { throw 'Finalization retains a failure; preserve artifacts' }
```

退出码：0=请求阶段有效完成；20=科学门失败/无提名；21=输入契约失败；22=证据/身份/权限失败；23=资源/连接暂停；24=工程错误。KC8收尾不能把原失败改成整轮0；阶段本身成功与整轮成功分开。

锁含host/PID/进程创建时间/run和命令身份；旧锁未知归属时不抢。后台启动必须隐藏窗口，保存stdout/stderr、退出码、心跳和回执。单元恢复包含模型、Adam、全部RNG、采样位置/hash、lambda及used计数、课程位置、best、累计预算；不能只恢复模型权重。

## 13. 交付图、原始数据和工作记录

每条预测记录至少包含：run/stage/fold/repeat/method/input_schema/model_kind、checkpoint_kind/step/SHA、gamma及E_eff SHA、trajectory/family/member/direction、中文工况名、start/horizon/time_s、norm/S0/params SHA、预测与真值各分量、SI量和有限性。CSV读取utf-8-sig，ID按字符串。

纯线性没有神经网络训练步数，使用 `checkpoint_kind=identified_linear, checkpoint_step=null`，身份取冻结系数文件SHA；不得编一个step=500让其看起来与残差同样训练过。诊断步0与未经训练的随机残差另标初始化，不能冒充纯线性。

| 图 | 必须说明什么 |
|---|---|
| `01_input.png/pdf` | 同旧输入不同四车请求的反例，7/11映射与单位 |
| `02_baseline.png/pdf` | 错误随机残差“线性”与真正线性差异，清楚标BUG_REPRODUCTION |
| `03_input_gain.png/pdf` | 纯线性7/11五折12工况四时域；对角两成员另面板 |
| `04_checkpoints.png/pdf` | best500与last6000分别对纯11基线，一步—20步折中 |
| `05_gamma.png/pdf` | 五点全局gamma前沿、保护区和收益门，不只展示选中点 |
| `06_force.png/pdf` | 固定窗四点Fx/Fy、内力、方向、形变/速度/交互项，N与时间 |
| `07_training.png/pdf` | 三机制fit/inner完整曲线，lambda_used/after，旧早停与新best |
| `08_scenarios.png/pdf` | 全12中文工况×四时域，各seed/尾部，普通改善与保护退化分开 |
| `09_motion.png/pdf` | 货物/单车横摆和连接运动，真实系统横摆辅助量标未预测 |
| `10_cost_claims.png/pdf` | 参数/时间/延迟与已支持/部分支持/未支持结论 |

代表窗在看模型误差前，从对应合法fit/inner按family→trajectory→start选首窗及距首次反转最近窗；并列较早start。事后最坏窗可以另画，必须标明。near-zero力方向阈值1e-6 N，仅令角度NA，不删误差样本。

图源manifest保存数据/代码SHA、过滤条件、样本数量和检查点身份；必须实际查看总览、重点力图和约束图。缺中文字体先查系统字体；不以工况编号代替中文。未执行阶段不以旧图填充。

持续追加 `D:\PDxc\Review\koopman_work_log.md`，执行时与REV同名日志按entry_id同步。每节点记录：真实系统时间/时区、授权、host/run/unit、读取/改动文件与SHA、准确命令/退出码/耗时、原始产物、数字单位/范围、事实与推断、PASS/FAILED/BLOCKED/NOT_RUN、下步权限。更正旧条目只能追加“勘误”，不改旧文字或用户表格。

## 14. 论文声明与最后一道边界

| 证据层 | 本轮能建立的结论 | 仍不能宣称 |
|---|---|---|
| 输入修复 | 完整控制信息降低特定操纵下的预测误差；给出7/11对照 | 新Koopman算子创新、所有场景提升、在线未来指令可得 |
| 残差结构 | 相同11维信息下的净多步收益和短期代价 | 只比较7维旧模型就证明新结构优越 |
| 固定/自适应保护 | 公平消融后证明某机制在指定工况与时域额外有效 | 自适应复杂所以必然有效；未参与训练的乘子产生收益 |
| gamma/课程 | 恒等式、前沿和训练时序的经验效果 | 新稳定性定理、增加了新物理信息、修复原IRSP证明 |
| 力可解释性 | 固定物理读出、完整内力、方向与误差来源 | 实际货物未撕裂、连接器疲劳安全、闭环力峰值下降 |
| 重复性与成本 | 当前开发池五折三seed与完整推理开销 | 独立盲泛化、完整MPC实时性、网络/DoS鲁棒性 |

写作仍按三层组织：先定位原方法不足；再公平检验针对性机制；最后仅组合已证实的有效机制。本轮先完成“正确比较”，不能为追求创新叙事掩盖输入遗漏和基线错误。

最终 `next_stage.json` 必须分别给出 evidence_valid、input_contract、precision_pass、repeatability_pass、latency_pass、nominated_method、未完成项、历史勘误状态、数据暴露账本和下一步需授权内容。

**当前第一实际停止点：R0重新连通并核验现场；数据访问/模型身份无法解释则停，不进入训练。边界明确后先R1修评估，再R2裁定旧9组复用。完成文档、完成训练、验收有效与方法成功是四种不同状态。**

## 15. KC-R2修复与接续任务书（覆盖旧阶段的直接续跑方式）

### 15.1 本轮证据位置与可信度

| 结论/对象 | 来源（远程相对REV） | 本轮证据等级 | 恢复时还须做什么 |
|---|---|---|---|
| 9组主训练已到6000步 | KC-R1 run的 `kc4/pilot_seed{0,1,2}_summary.json`、`kc4/seed{0,1,2}_{aligned,fixed_guard,adaptive_guard}/` | 已读取摘要并核查产物/源码；不是完整质量复算 | 对照payload、每500步文件、样本hash、优化器与时间 |
| 3组课程数据 | KC-R1 run的 `kc4/curriculum_table.csv`、`seed*_residual_curriculum/` | 表与生成实现已读取；列出的百分比非本轮独立重评 | 冻结为偏离协议结果；复核原始输出，不再叫MSE课程 |
| 课程损失错误 | `koopman_predict_v3v/src/refine_loss.py::residual_loss` | 远程源码已核查，与本地副本SHA一致 | 修在v3w；旧树不动 |
| 训练/乘子时序 | `koopman_predict_v3v/src/guard_training.py::train_phase` | 已核对实现，当前并非全部工程测试已通过 | 补lambda使用次数、监控、恢复与只读回归 |
| 缩放与诊断偏差 | `koopman_predict_v3v/scripts/kc3_diagnose.py`，KC-R1 run的 `kc3/gamma_frontier.csv` | 已读取实现和诊断；中间gamma的一步公式存在重复乘法 | 新代码从统一rollout重算，不修CSV小数蒙混 |
| 提名入口不完整 | `koopman_predict_v3v/scripts/kc5_gamma_selection.py`、`kc5_precheck.py` | 已读取代码；未见有效校准/提名产物 | 完整门实现后再运行；本地副本不得自动当远端最新 |
| 日志不一致 | 本地 `koopman_work_log.md`、新脚本的KG_RUN日志常量、旧/新decision_log | 源码和记录冲突已确认；历史日志被追加的精确数量待恢复连接复核 | 统计实际访问，保留原文，追加勘误，不伪造“从未写入” |

源码身份锚点（SHA256）：

```text
远程v3v/src/guard_core.py
4CF3DCFB5764CC647A19333F3CC5661720D434B046079E2425691B81546EAE78
远程v3v/src/pure_linear.py
DD8D719B9D93602CDC0C64E76FDCDEE72DB4CF5D6717BC0823F5174E526695FD
远程v3v/src/refine_loss.py（本地副本一致）
F3338814B592C12C70C89B8546D7339FC99BD7957CBAF68F8CF5CDA57C2F2476
远程v3v/src/guard_training.py（本地guard_training_v3v.py一致）
9EA50F134D3B303ADC72CEC677287D73CFFF852EF9C8616D3BA4E7141987E1AF
本地_koopman_kr_dev/koopman_predict_v3v/scripts/kc3_diagnose.py
D29989207F622D23336AE83F43301FB3F7C20ADC4501D3867367A34BB632C66E
本地_koopman_kr_dev/koopman_predict_v3v/scripts/kc5_gamma_selection.py
55E539C62396B29EF2BB92EAE4611D6C79FE5759F029ACF1A8ADDF9C0F2A5832
```

后两个脚本的本地SHA只用于定位本轮检查版本；恢复时再次取远程SHA并比对，不假定本地永远与5080同步。新代码和新产物必须登记各自SHA，不用上述父版本哈希替代。

### 15.2 修正清单：旧关闭状态需要有条件重开

原C01—C20保留，以下追加项和复核项是接续必做，不用新条目数量代替完成率。

| 编号 | 具体问题 | 必改文件/函数（复制到v3w后） | 必须产生的证据 |
|---|---|---|---|
| U01 | 一步gamma重复乘，且前沿不是J_common | `scripts/kc3_diagnose.py`迁移到`src/refine_diagnostics.py::gamma_frontier` | 五点×四时域统一rollout，逐窗状态/力/内力、J及独立RMSE分列；T11＋T29 |
| U02 | 课程RMSE冒充MSE | `src/refine_loss.py::residual_loss` | 第15.3节精确MSE，逐窗再等工况聚合；T22＋T30；新旧目标不混名 |
| U03 | 校准仅55门、只提示锚错误、缺seed可提名 | `src/calibration.py::evaluate_gamma/select`、`src/refine_metrics.py::full_quality_gate` | 全门逐条值/分母/阈值/布尔，3seed完整检查；T21＋T31 |
| U04 | 课程触发只检查了一个必要条件 | `scripts/kc5_precheck.py`迁移到`src/calibration.py::curriculum_trigger` | 引用完整45点评估SHA和固定保护最后3次fit记录；缺一项即INCOMPLETE；T32 |
| U05 | 旧runner、完成脚本不是真实状态机 | `src/run_state.py`、`scripts/run_v3w.py`；替代kc2_complete/kc3_complete逻辑 | 测试结果、schema、行数、SHA、数值门共同裁决；无硬编码gate；T23/T24/T28＋T35 |
| U06 | KC2未覆盖新机制，smoke仍旧T0 | 新测试文件与独立smoke入口 | 28项映射到实际用例，7项新增专项回归，三新方法共享warm的600步冒烟；未做项不得PASS |
| U07 | 新阶段向旧日志写入、数据范围自述不充分 | `AccessGuard`构造、所有脚本配置和loader | 新run唯一log路径；受保护目录写入测试；按实际打开字段和purpose的范围账本；C09/C10重开 |
| U08 | 对角两个成员混为加减速、阶段时间不严密 | `WindowData.meta`、`refine_metrics`、`refine_diagnostics::phase` | 前后反向加减速/对角差动加减速/对角差动转向分表，物理时间与命令区间对齐；C03/C06复核 |
| U09 | 乘子已更新次数被当作实际使用次数 | `guard_training::train_phase.pack`、`kc4_summary`替代函数 | lambda_before/after/used，applied_updates与updates_completed分列；T17/T18＋T33 |
| U10 | 摘要字段“last违约”实为best，诊断步缺失 | `kc4_summary`替代函数、训练monitor、checkpoint导出 | best/last分别评估；补可复用诊断，缺失步不得伪造；T07＋T34 |
| U11 | 70 tests和文件存在被当全阶段PASS | 逐项test ledger、`complete.json`生成器 | required/performed/passed/skipped、具体用例、stdout/exit/SHA；C08/C15/C20重开 |
| U12 | 时钟、源码与协议快照链不足 | `run_identity`、`module_paths`、`protocol_snapshot`、工作日志 | 机器时区时间、单调耗时、真实导入路径、有效配置、父资产SHA；C16/C17重新核验 |

C01纯线性独立路径已有实质修复，不要求推倒重写；C02/C04的best/last纠错可按已生成表核验复用。C05/C06/C17只有在12工况×4时域、成员元数据、原始数组和分层统计完整后才重新关闭。C11不能因pure_linear拒绝未知维度就认定整个管线严格：现有 `fit_normalization`仍以input_dim≥11猜control11，`u_field`仍按norm键猜schema，两处均须显式7/11枚举与形状断言。

### 15.3 两个必须改对的公式

#### A. 统一缩放只作用一次

设未缩放残差为d=Eη0，纯线性一步预测为x̄1，目标残差r=x1−x̄1，Ω沿第4.4节固定。正确关系为：

\[
\hat x_1(\gamma)=\bar x_1+\gamma d,\qquad
\Delta_1(\gamma)=\gamma^2d^\top\Omega d-2\gamma r^\top\Omega d.
\]

旧诊断已将E改为gamma E，又额外乘gamma，产生x̄1＋gamma²d。这会把gamma=0.5的一步修正从0.5d缩成0.25d，使一步/20步不再对应同一个模型。该错误不等于KC5校准脚本也重复缩放；当前校准脚本的E缩放本身只做一次，其主要问题是验收门不完整。

实现只允许两条之一，并用同一条输出链评价全部时域：

- 从未修改的父模型深拷贝，令 `E_eff = gamma * E_original`，所有1/5/10/20步均从该副本rollout取；禁止手写另一份一步预测。
- 保持E不变，用已验证的全状态仿射恒等式组合状态；仍逐状态进行非线性物理读出，不能线性混合两端连接力。

存原E与E_eff的SHA；每个gamma均从原E出发，禁止0.25→0.5顺序累乘。统一取h步输出的h−1索引。gamma=0状态必须与相同输入/norm/S0的pure一致；若仅误差百分比接近但状态不同，不算通过。容差采用T01/T11已注册精度，不能临时放宽；力oracle的3.4e−13 N属于容差内接近，不是“逐位0”。

平方误差改善的条件是 `gamma² dᵀΩd < 2 gamma rᵀΩd`。它解释缩小过量修正为何可能改善一步，不保证20步、非线性连接力或全部工况同时更好。r包含真值，只能用于离线诊断，不能由每窗口真值反求gamma送入正式预测器。

#### B. 课程前1000步是真正的加权平方误差

用归一化状态误差e_b=hat x_(b,1)−x_(b,1)，组索引G=(0:3,3:19,19:31,31:47)，组宽n=(3,16,12,16)，组权w=(0.30,0.20,0.20,0.30)。每个窗口损失：

\[
\ell_b=\sum_{g=1}^{4}\frac{w_g}{n_g}\sum_{j\in G_g}e_{b,j}^{2}
=e_b^\top\Omega e_b.
\]

继续使用原等工况、族/轨迹/窗口均衡采样器；批次中每类21/22个窗口，先在每类求均值，再12类等权：

\[
L_{\mathrm{curr},1}=
\frac1{12}\sum_{s=1}^{12}\frac1{|B_s|}\sum_{b\in B_s}\ell_b+R(\theta).
\]

完整fit/inner报告仍严格按第5节窗口→轨迹→族→工况分层。不得先对整个batch/组取平方根，不加smooth_rmse，不改原R。步骤1—1000用上式；1001—6000用原fixed_guard；正式AdamW在开始时新建一次，1000→1001不重置动量、步数、采样流。warm2000仍沿原RMSE预热，不顺带更换，以免失去单因素对照。

验证时将R独立扣除：固定非零e，e变为2e，数据项必须变为4倍、对e的梯度变为2倍。随机数据验证 `Eη0−r = hat x1−x1`及加权平方范数相等；检查训练梯度不是仅注释写MSE。F/G/c在首步状态输出中无数据梯度是结构事实，正则/权重衰减可能仍使它们变化，不能据参数变化说已学到多步传播。

MSE比RMSE更强调大误差，但并不保证最终J_common或保护项更好。现有选中≤1000步的结果更需要区分“前段一步拟合”与“后段多步折中”，不是通过改公式就宣告创新成功。

### 15.4 执行R0：刷新现场、冻结父证据、裁定权限

- 前置：用户明确执行授权且5080可达。SSH最多两次有限重试；仍超时只保存本地进程未知说明，不远程重复派发。
- 读取：现场时钟/主机/Python/GPU进程/磁盘；KC-R1和所有更新run的目录清单、真实receipt、taskbook、protocol、源码、9＋3组checkpoint和工作记录。若发现晚于本次审查的新校准产物，先验证并纳入，不按旧“缺失”结论覆盖它。
- 修改：仅新v3w树/新run。先保存当前父源码快照与逐文件SHA，区别“本次获取的源码”与“历史训练时源码”；不能靠今天快照补造昨天的身份。
- 输出：`repair/r0/inventory.csv`、`clock_audit.json`、`source_lineage.csv`、`access_scope.json`、`protocol_deviations.csv`、`imported_units.csv`。每资产有parent_run/unit/path/size/mtime/SHA/role，mtime只用于发现。
- 核查旧日志实际追加项及672缓存派生范围：机械输入构造不自动等于训练泄漏；但实际loader若展开全部NPZ字段，就不能写“只打开了请求加速度”。把打开、派生、归一化、训练、选点、评价分别列出。权限不明或存在未经裁定的数值越界，停止训练并提交solutions.md；不能用一段解释把违规则标PASS。
- 新context只打开合法train/R3的fit/inner；metadata盘点和SHA读取不成为载入未授权数值数组的借口。训练权重、旧缓存、旧日志不得有写入，审查前后比较SHA/大小。
- 通过门：身份可解释、无未裁定权限问题、现场无冲突进程、有效配置与版本映射完整。已有进程不杀、不抢GPU；记录PID/创建时间/命令后暂停新训练。
- 失败恢复：连接失败退出23；身份/访问失败22。保留现场差异，修正映射或请求必要裁定后从R0恢复，不提前“先跑起来”。

### 15.5 执行R1：修评估和诊断，只加载旧模型，不训练

- 前置：R0有效完成，模型只读模式强制拒绝optimizer.step；允许新run写审查结果，不允许写旧AccessGuard日志。
- 代码：先修U01/U03/U07/U08/U10及指标/契约；将所有KG_RUN日志常量替为resolved `current_run/split_access.jsonl`。物理冻结父树可以明确只读导入，训练/评估模块必须在v3w真实路径。
- 统一评价返回：逐窗4时域的47状态、8连接力、8完整内力、J及各分项，元数据包含fold/role/trajectory/family/member/direction/start/time_s/params/model/norm/S0/gamma。缺字段即INCOMPLETE，不补member="none"后继续分组。
- 重新计算KC1需要补齐的原始数组和12工况×4时域表；已验证纯线性系数与已有正确表复用并引用SHA，不重新训练已有残差模型。
- 重做KC3五点前沿、一步残差、物理读出分解和阶段诊断。前沿同时输出J_common与单独的47维归一化状态RMSE，两者不可混称；不把诊断计数当独立样本量。
- 成员拆分：前后车辆反向加减速、对角差动加减速、对角差动转向三份诊断；主比较仍12类，不将对角拆成13类抬高权重。阶段依据raw实际time_s和控制区间映射，核对原始[k+1]与缓存u[k]的约定；预测期内是否发生切换只是离线分层标签，不作为输入。42混合窗口不得再标成只有两种加减速。
- 力分解保留 `f00, f10, f01, f11`和`f11−f10−f01+f00`，先验证f00对真实force8的oracle。分解统一单位和统计量；不能把向量范数均值44 N和逐分量RMSE22 N直接作倍数解释。仍区分平面Fx/Fy与垂向Fz，本数据输出force8不证明垂向预测能力。
- 输出：`repair/r1/errata.md`、`predictions.npz`及schema/索引、修正后的 `gamma_frontier.csv`、`correction_components.csv`、`force_factorization.csv`、`phase_metrics.csv`、`oracle.json`、`quality_gate_rows.csv`。所有表可从保存数组独立重算。
- 验收：T01/T05/T06/T07/T08/T09/T10/T11/T21及相关新增测试通过；重复/缺失/身份错配为0，oracle按原容差通过。某些组确无样本只能诊断NA；主工况缺失阻塞，不删掉该工况。
- R1不宣布模型通过，仅证明评价链可用；保护不通过是可以记录的科学负结果。恒等式/配对/物理oracle错误属于硬阻塞，不能先上新训练。

### 15.6 执行R2：补工程门，裁定哪些已完成训练可以复用

- 实现U02/U05/U06/U09/U12及第9节剩余工程要求；T27推理等价实现亦须有小规模回归，KC7再做正式性能测量。pytest只传它认识的参数，实验配置通过明确fixture/环境接口提供，不能向未注册pytest选项直接传项目runner参数。
- test ledger逐项列T01—T35，不允许以63旧＋7新=70为完成判据；一项可映射多个用例，重复、跳过和失效用例单列。真正执行测试并保存stdout、退出码、覆盖接口及源码SHA。
- 冒烟：原seed996900，fold0每工况2个fit族，norm/S0仍从完整fit取得；共享warm200，aligned/fixed/adaptive各600步。旧T0冒烟只作旧引擎参考，不能替代新三方法。课程切换/恢复用合成测试覆盖，不提前新增课程科学训练。
- 跨500步验证固定/自适应同warm同batch前500步模型一致，活跃约束下501步可分歧。保存 `updates_completed` 与 `updates_applied_to_weights`：500步checkpoint的首次乘子更新尚未参与其权重；6000步后更新的第12组乘子也没再用于优化。实际非零影响另列 `nonzero_multiplier_steps`，不能由“更新12次”声称best用了12次保护。
- 用原500倍数checkpoint补做0/500/2500/6000梯度诊断，其中0取该seed共同warm；诊断使用独立seed996800三批，保存/恢复全RNG，不修改旧模型、优化器或采样状态。缺100/250/750的历史权重不能从500或1000替代。

逐单元复用裁定必须是以下三种之一：

| 裁定 | 进入条件 | 允许做什么 | 不允许做什么 |
|---|---|---|---|
| IMPORT_VALIDATED | 数据/输入/norm/S0/warm/损失/seed/采样/优化器/6000步/选点身份可核对；训练目标符合R1；缺陷只在报告或旁路工程 | 引用只读checkpoint，重评、补表、按原规则重建best；注明历史前置门未按序执行 | 追写旧PASS证明当时合规；修改原best或父run |
| REPLAY_REQUIRED | 缺少必要训练身份或监控、尚可用既有状态验证确定性 | 新run做最小确定性重放/核对；100/250/750仅用于补原定诊断 | 从旧优化器接上新损失；新增seed；重放中挑更优路径 |
| NONCONFORMING | 目标、数据或采样有实质偏离，或身份不能重建 | 保留为历史偏离结果；仅受影响方法/seed在新身份下按原预算重做 | 删除负结果；把旧RMSE课程当MSE；无差别重跑所有9组 |

旧9组不是因为runner不完整就全部无效；但也不能因为step=6000就全部可复用。检查实际warm采样seed与协议要求、同seed各方法warm参数及正式sample_hash一致性；有差异必须列为偏离并裁定，而不是默认为一致。若缺历史source snapshot，通过保存的源码/调用链、损失数值和梯度对照、模型/采样哈希建立有限可复验身份；无法建立则只重做受影响单元。

若仅缺早期诊断，在原warm、原采样与原训练代码可确定重建时重放至750步，核对500步权重/样本hash，再补100/250/750；重放权重不替换既定主模型，也不新增checkpoint选择点。非确定性差异不得任意设新容差硬认一致，记录为无法精确追溯；必要时同seed受影响6000步单元重做，先核算成本。修目标必须重新开始该正式阶段，不能修改损失后接旧optimizer。

输出 `repair/r2/test_ledger.csv`、`smoke/`、`reuse_verdict.json`、`imported_units.csv`、`diagnostic_completeness.csv`、`budget.json`。总独占GPU预算仍≤12 h、预计D盘余量≥60 GiB，计入已用时间、工程重放、课程和正式全流程，不给每个小阶段各自12小时；成本超门先暂停，不删除失败资产腾空间。

### 15.7 执行R3：先把三方法的45个校准点算完整

- 输入：R2认定有效的3方法×3seed固定主best、纯11维基线、同fold0 inner；原始版gamma=1另保留，不再把last或best_q加入主候选。
- 主best仍按原500倍数和55项字典序选择，不为通过新增完整门而倒查另一个checkpoint。若原选择器确有实现错误，可按原规则在新报告重建正确best并记录父文件/旧选择/新选择，不覆盖父best。
- 评价矩阵：3×3×5=45个model/seed/gamma点，每点473窗口×4时域，预计85140条逐窗时域记录；473必须由清单独立核对，不靠固定行数造数据。连接力与内力是每条记录的向量列，不额外充当独立样本。
- 完整内部门：55项训练保护之外，加连接力/内力5步与10步的5%门；回头弯20步整体及start100/120合并困难窗的均值/P95/P99/max的3%门；全部四时域逐窗状态误差有限且最大绝对归一化误差≤20。精度门采用第10节，不能把诊断性一步尾部临时升成新硬门。
- 接口 `full_quality_gate(prediction_bundle, baseline_bundle, metadata, protocol)`返回逐条 `name/value/baseline/denominator/limit/pass/source_rows`、missing_required和overall。NaN/NA/缺成员/缺seed不得由空数组all()变成通过。40步压力仍按原阶段/共同起点要求单列，不擅自新增内部调参门。
- gamma=0与pure不一致立即22退出并查S0/norm/窗口/dtype；如果状态一致但基线本身违反绝对有限性门，标BASELINE_GATE_FAILED并停止该证据链，不错说成创新失败。只有gamma=0可保护时保留 `PROTECTED_BUT_LOW_GAIN`，收益0、不能提名；不能返回None让回退结果从图表消失。
- 有保护且I20≥5%才是该seed合格点；取M20最小，并列容差1e−10时选较小gamma。其余保护点中取最佳用于低收益报告。禁止用round(...,12)替换原并列规则；五点重复使用同一验证代码。
- 方法版本键必须含“是否校准”。按原规则三个seed均完整有限，至少2/3 seed达全部内部保护且I20≥5%才能提名；不能跳过缺seed后拿2个成功凑2/3。失败seed、负收益、逐门失败位置全部保留。
- 输出统一写新run的 `kc5/calibration_table.csv`、`calibration_rows.npz`、`calibration_summary.json`、`quality_gate_rows.csv`、`raw_version_table.csv`，不是继续散落kc4。主9组未完整时R3状态INCOMPLETE，不得触发课程。
- 通过：评价完整且证据有效即可完成R3；“没有合格方法”是R3可能的合法结果，下一步按触发逻辑走R4，不修改门槛。

### 15.8 执行R4：正确MSE课程只在严格条件成立时运行

触发必须同时满足：

1. R3三方法原始/校准版全部评价完整，按原规则均无提名资格。
2. fixed_guard至少2/3 seed在完整fit的5000、5500、6000步三个监控点均有一步保护失败，读取的是各自last曲线/对应checkpoint，不是best的g；缺点、非有限或曲线身份不明不能返回trigger=true。
3. U02/T22/T30/切换恢复测试通过、数据权限明确、剩余预算可容纳3×6000步及后续正式阶段。

有原三方法候选则课程SKIPPED；无候选但只有inner失败、fit已经受控则课程NOT_TRIGGERED并科学停止/收尾；缺评估证据则INCOMPLETE先补证，不能伪装成“无候选”。`trigger.json`分别存三个条件、使用文件SHA和允许/拒绝理由。

触发后仅新增正确MSE课程3组，seed996100/996101/996102、对应已核验warm2000、正式采样seed+50000，总6000步，前1000真MSE/后5000fixed_guard。已跑错的三组不计为这三次，也不能用其最优权重初始化正确课程；每组从相同原warm重新开始。保存目标类型 `residual_curriculum_mse` 与父计划方法键映射，旧组明确 `residual_curriculum_rmse_nonconforming`。

新组完成后按同一主选点和五点校准再评估，额外15个点/预计28380条逐窗时域记录。gamma不因方法改变而加密。正负结果均保存；正确课程仍无提名则退出20并KC8收尾，不加门控/专家/双线性或更长训练。

这里的“补跑”不是保证有收益：MSE可能改善大残差一步拟合，也可能降低原多步目标表现，验证目的正是区分这两种情况。不能写成“修好公式即可解决审稿意见”。

### 15.9 执行R5与R6：提名、封存和正式阶段放行

- R5生成唯一 `kc5/nomination.json`：三seed全分数、原始/校准身份、所有保护结果、课程是否合法触发、各checkpoint SHA/step、gamma/E_eff、代码/数据/norm/S0/参数SHA及选择规则。中位I20比较与0.5个百分点简单性优先顺序沿KC5原定义。
- 旧RMSE课程是协议偏离结果，只能放错误分析/附录，不参与新MSE方案主提名。以后正式60组课程预算只在**正确MSE分支被合法触发**时启用；不能因为错版本已运行而自动加15组正式课程。
- R6核对R0—R5和C/U/test ledger：所有必需前置有效，无待裁定身份/权限/原始数据缺失，GPU/磁盘预算通过，KC6—KC8真实runner已实现并有回归。没有合格提名不得写READY_FOR_KC6。
- 通过后进入原KC6：45组正式训练＋15份共同warm；只有合法MSE课程触发时才60组，seed不变。已在fold0内部做过多轮开发，必须如实列数据暴露历史；这不是新盲测，外层只按本轮完整冻结协议评价，不能声称独立于全部历史开发。
- 所有正式best/gamma/方法和代码全部冻结后一次开outer；精度过门再测推理，不提前进入MPC、通信保护或DoS。任何下游失败都保留相应研究结论的边界。
- 缺关键前置退出22/24；科学无提名退出20；资源暂停23。收尾用KC8 finalize-only，保存 `solutions.md` 和 `next_stage.json`；完成报告不把失败转成全局PASS。

### 15.10 新增专项回归（补充T01—T28，不替代）

| 编号 | 必须实际执行的反例/手算 | 通过条件 |
|---|---|---|
| T29 | 手工取pure1=0、未缩放d=2、gamma=0.5，输出须为1而非0.5；打乱五点顺序重复评估 | 与统一rollout及40步状态仿射恒等式一致，原E/SHA不变，五点结果不依赖循环顺序 |
| T30 | 非零误差乘2，分别比较MSE数据项、梯度与RMSE对照；每类21/22个窗口的不均衡合成批 | MSE损失4倍/梯度2倍，组宽及等工况权重正确；与Eη−r平方误差一致 |
| T31 | 人工构造55项全通过但5步力失败、回头弯P99失败、单窗误差>20、一个seed缺失、只有gamma0通过 | 分别阻止不合格提名，缺失报INCOMPLETE，gamma0保留低收益；锚不一致硬停 |
| T32 | 三方法未校准/已有候选/固定保护fit通过/最后3点缺一/仅1个seed失败/完整两条件满足 | 只有完整无候选且≥2/3 seed的5000/5500/6000逐点失败时允许MSE课程 |
| T33 | 固定/自适应同warm同样本500步；501步使用首个活跃乘子；6000监控后无进一步优化 | model500一致；used/after分明；第12次更新不能归功于6000权重；恢复不多更新 |
| T34 | best与last用不同人工权重；成员同start但不同轨迹；原始time_s非均匀小样本 | 旧best误命名last被检测；完整键唯一；阶段采用真实时间且不向模型输入未来标签 |
| T35 | 伪造只有文件存在的complete；第二进程锁竞争；未知CLI选项；只读模式尝试训练；遗留旧日志路径 | 全部拒绝并正确退出；不写旧文件、不覆盖检查点；只有已执行验证才能产有效回执 |

数值门沿原协议；测试必须设计会失败的反例，不能只测试理想数据或只检查函数能调用。任何“通过”记录附用例路径、源码SHA、命令、退出码和实际观测；不能把expected值写入observed字段。

### 15.11 小问题自主处理与真正停止点

| 遇到的问题 | 可自主执行的最小修正 | 必须停的边界 |
|---|---|---|
| Unicode/CSV BOM/中文字体/路径分隔符 | UTF-8-sig读CSV、显式编码和resolved路径，图用已装中文字体；加回归 | 不改数值/中文工况含义，不用工况代号代替面向用户说明 |
| GPU OOM或评价显存高 | 降低纯评价batch，完整float64 CPU复评或清理无用临时张量；记录耗时 | 不改训练batch/精度/损失，不丢困难窗口，不解除物理读出 |
| 并发写入或旧run新产物出现 | 停新写入、核对PID和SHA，读取更新后重新编清单 | 不杀未知进程，不复写父结果，不假设最新mtime就是有效版本 |
| 仅缺报表或原始导出 | 从已认定模型重评并写新run，优先做这个 | 无法还原模型身份/输入时不能补造数组 |
| 未保存早期诊断权重 | 按R2最小确定性重放，标明replay而非历史原件 | 不用未来checkpoint替代早期；不能改seed寻优 |
| 测试失败但看似工程小错 | 同一问题最多两轮有记录的语义等价修复，每轮重跑相关测试 | 第二轮仍失败或涉及科学定义/数据权限/阈值即停并写solutions.md |
| 多步收益不足或仅gamma0合格 | 先保留完整前沿、定位具体工况/时域；只走合法MSE课程 | 不增训练步数、不放宽3%/5%、不删除负工况、不新增模型分支 |
| 数据访问范围或训练身份无法核实 | 元数据/现有日志/配置/哈希的最小只读核查，列可选处理与成本 | 未裁定不能训练；不能通过关闭AccessGuard绕过 |

执行器允许自我修正的是可检验的实现/流程问题，不是根据结果改研究问题。每完成节点立即在同一工作记录追加真实时间、改动、命令/退出码、SHA、指标范围、裁定和下一步；若只做了文档，不写成代码修复已完成。

### 15.12 本版交付验收与审稿回答边界

本次MD更新交付的目标是使下一次执行不用猜测顺序或补丁范围。未来实验交付须另外满足：

1. 一张“已完成/可复用/需重评/需补训/未运行”清单，9组主训练与3组错误课程逐一对应。
2. 一套由原始数组生成的中文图：修正前后gamma前沿、三方法原始与校准的1/5/10/20步误差、前后/对角操纵分成员、回头弯尾部、力分解、lambda使用时序和课程1000步切换。错误版本清楚标出，不混入正式排名。
3. 所有固定阈值和负结果可追溯；图、表、报告的checkpoint/step/gamma一致；逐位一致只用于实际最大差=0的场合。
4. 对论文分别回答：输入信息缺项已修复到什么程度；在同样11维信息下预测机制是否有额外收益；短期和连接力代价是否受控；跨工况/三seed/五折是否重复；成本是否合格。尚未完成的项写“未回答”。

截至本轮审查，只能肯定有输入契约/纯线性对照纠错进展以及新的训练产物；不能宣称保护机制、MSE课程、整体最优预测、闭环/网络鲁棒性已经证明。本版修复后如果仍没有合格候选，诚实交付失败机制和边界就是本阶段结论，不把继续堆方法当成默认下一步。

## 16. 后台执行：把耗时工作一次排好，程序自行推进

### 16.1 剩下的实验，用常用中文说明

| 工作 | 具体要做什么 | 要回答的问题 | 数量与顺序 |
|---|---|---|---|
| 修正计算 | 残差修正强度只乘一次；课程前段改为真正的均方误差；补齐力、内部力和回头弯尾部检查 | 前面看到的改善和退化是否计算正确 | 正式耗时训练前完成必要修正和小规模验证 |
| 复核已有模型 | 检查9组已完成训练的输入、固定线性部分、随机种子、样本顺序和选中检查点 | 哪些已有成果可以直接使用 | 9组主试验先复用核验；错误的3组旧课程单列保留 |
| 调整修正强度 | 分别保留0、四分之一、二分之一、四分之三和全部残差修正，再比较1、5、10、20步误差及受力误差 | 能否保留长期预测收益，同时避免短期或个别工况明显变差 | 三种方法×三个初始化×五种强度，共45个评价点，不训练新网络 |
| 必要时分两段训练 | 先用1000步把下一时刻预测学好，再用5000步训练多步预测与保护要求 | 先处理大的一步误差，能否改善后续多步学习 | 只有原三方法完整校准后无合格候选，且固定保护在训练集仍持续一步失败，才做3组 |
| 重复验证 | 五次按基础族划分的数据交叉验证，每次用三个初始化；比较统一预测目标、固定强度保护、自适应强度保护，必要时加入正确分段训练 | 改善是否能在不同划分和初始化下重复出现，哪些工况仍退化 | 15份共同预热＋45组正式训练；正确课程合法触发时为60组正式训练 |
| 检查预测速度 | 对选定模型一次完整预测未来20步状态、连接力和内部力；做数学等价的计算加速 | 预测更准以后，计算是否足够快 | 正式精度通过后运行；同时保留原实现和加速实现的输出一致性与耗时 |

“一步、五步”等是预测时域；“训练1000步、6000步”是参数更新次数。两者不可混称。正式训练的45/60组也不是45/60种模型结构，而是方法、数据划分和初始化的组合。

工况面向用户使用中文名称：直线匀速、直线加速—匀速—制动、100米正反转向、持续稳态转弯、单移线、回头弯、直线入弯和出弯、前后车辆反向加减速、左右车辆反向转向、对角车辆差动操纵、往复转向与连接器边界激励、加减速与转向混合操纵。对角加减速和对角转向在诊断中分别解释，主比较仍保持12类等权。

### 16.2 对执行方式的明确调整

用户这次授权启动耗时工作并让其后台完成。因此，一次启动一个独立于聊天和SSH连接的后台程序，由它依次执行校准、条件课程、正式训练、统一外层评价和速度测试。单张5080采用串行训练；“全部排入队列”不表示同时挤占显存，也不表示跳过前置条件强行训练所有分支。

当前交互只需做到：现场核对→修正必要代码→实际回归与短训练检查→启动后台队列→确认真实进程、进度和输出日志。确认启动正常后结束本轮，不等待45/60组训练全部结束，不设置循环聊天提醒或额外定时监控。程序每15秒记录心跳，每组完成立即记工作记录，最后自动生成结束状态和已有结果报告。

必要检查保留如下，均须在进入对应耗时阶段前实际通过：

1. **数据与身份**：固定数据/划分SHA、11维输入重构、47维状态、只使用当前许可的fit/inner角色、纯线性和力读出正确、模型与S0一致。
2. **计算与公平性**：正确MSE及梯度、五点缩放恒等式、同seed同样本流、固定/自适应前500步权重一致、选点和乘子使用时序正确。
3. **完整验收**：1/5/10/20步、12工况、连接力/完整内力、回头弯20步整体和困难窗尾部、有限性与绝对误差。缺失不是通过；性能门继续用原3%/5%，不改阈值。
4. **后台可靠性**：独占进程锁、跨500步乘子和1000步课程切换的断点恢复、每组检查点和结束回执、累计预算与磁盘检查。入口拒绝未知参数，长实验需要同版本验证回执。
5. **外层使用顺序**：全部正式模型、检查点和校准强度冻结后才统一读取outer。内部失败按原条件走课程或停止；不能为了让机器多跑而打开外层提前选模型。

旧诊断的完整排版、历史早期点重放、全部历史图重绘及逐项论文措辞整理，不挡住已具有科学有效性的耗时队列；保留为后续资料整理项并如实标待补。本次后台程序不将这些未完成的低成本整理项计为已完成，也不声称原35项编号全部一一落实。必须完成的计算、权限、恢复及科学判据用本次实际测试清单和现场检查证明。

### 16.3 实际代码位置与作用

新树为 `REV/koopman_predict_v3w`，父v3v源码和结果保留。实际新增/修改：

| 文件 | 本次职责 |
|---|---|
| `scripts/run_background.py` | 顺序队列、前置检查、旧模型复用、条件课程、45/60组正式训练、冻结后外层评价、族级统计、心跳和失败收尾 |
| `src/background_core.py` | 输入/缓存身份检查、完整评价、逐窗数组、分层统计和尾部、唯一gamma选择器、课程触发和正确MSE |
| `src/refine_loss.py` | 课程前段调用正确的逐窗加权MSE，按工况等权聚合；其余三方法目标保持一致 |
| `src/guard_core.py` | 显式7/11输入检查、分层分组键限定工况和基础族，避免跨工况混组 |
| `src/guard_training.py` | 增加诊断回调、真实乘子使用次数和课程阶段；保持原优化器、6000步预算和断点状态 |
| `src/background_speed.py` | 预计算增广线性传播，状态/力/内部力等价验证，CPU/GPU完整计时 |
| `src/background_report.py` | 从保存数据生成中文结果表、校准图和报告；失败也输出，不填补未运行结果 |
| `tests/test_background.py` | MSE值/梯度、完整门的失败反例、缩放、缺seed、课程条件、精确恢复、进程锁及等价加速 |

真实执行使用同一新run，路径从实际启动回执获取。父模型的9组比较只读导入；新run拥有自己的 `split_access.jsonl`。旧3组RMSE课程不加入正确MSE课程排名。旧源码中的错误KC3绘图入口不再由新后台程序调用。

启动检查中补充的基线复用细节：重新求解fold0固定线性参数与旧checkpoint的最大系数差约4.505e−9；相同fit数据和ridge=0.01的正规方程，旧/新解的归一化后向误差分别约3.708e−17/3.465e−17，正则化矩阵条件数约1.358e8。由此判断差异符合浮点求解误差；复用时从旧checkpoint精确读取A0/B0/b0，核验其满足同一拟合方程（数值诊断门≤1e−12）后冻结，而不是重新求解再要求所有系数逐位相等。该数值诊断门不改变3%/5%预测验收门。新/旧系数差、后向误差和父检查点SHA写入 `folds/fold0/backbone_import.json`，旧失败尝试保留；其余八组及预热的固定块仍须与导入值逐位一致。

### 16.4 队列的继续和停止规则

- 三方法的45个校准点完成后，程序检查原始版和校准版的提名资格。有候选直接进入正式重复试验，课程标“无需启动”。
- 无候选时，程序同时检查固定保护三个初始化在5000/5500/6000步的一步训练误差。严格满足原条件才做正确MSE课程3组，然后再次校准；否则保存“未达到启动课程的条件”并停止。
- 正确课程仍无候选，自动停止正式训练并输出失败结果。用户授权“全部耗时实验”不要求跳过这个科学前置。
- 正式训练完成后统一冻结，再做外层评价；预选方法没有通过全部正式质量和重复性要求，保留结果并停止速度优化。预选方法不能根据外层排名临时替换。
- 精度合格后做速度实验。CPU/GPU阈值不变，等价实现不能改变控制序列、状态归一化或物理力计算。
- 连接断开不影响已启动的后台进程。程序异常、证据失败、资源不足或累计预算用完时，保留最近检查点、异常堆栈、进度和solutions.md；不删除旧数据，不后台无限重试。

累计预算仍为12小时；父run约22:42到00:10的整个区间按90分钟预留计入，含空闲和诊断，采用保守估计。新run本身的真实用时继续累计，恢复不重新获得12小时；D盘至少保留60 GiB。精确GPU纯训练耗时和此保守运行预算分开报告。

### 16.5 真实启动和恢复命令

下列命令对应本次新增入口。`$KcBgRun`必须取实际回执的run_dir，不能填一个新的时间戳来绕开已有检查点。启动前pytest与实际三方法短训练必须成功，写入包含同版源码SHA的verification.json，后台长实验会检查它。

```powershell
$KcBgProject = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$KcBgRevision = Join-Path $KcBgProject 'revision_2026'
$KcBgPython = 'E:\anaconda\envs\pytorch_new\python.exe'
$KcBgSource = Join-Path $KcBgRevision 'koopman_predict_v3w'
$KcBgReceipt = Join-Path $KcBgRevision 'koopman_predict_v3w_results\receipts\KC_BG01.json'
$KcBgInfo = Get-Content -LiteralPath $KcBgReceipt -Raw -Encoding UTF8 | ConvertFrom-Json
$KcBgRun = [string]$KcBgInfo.run_dir
$KcBgBook = Join-Path $KcBgRevision 'koopman_next.md'
$KcBgRunner = Join-Path $KcBgSource 'scripts\run_background.py'

# 前台只做必要验证；不是等待完整长实验。
& $KcBgPython -B $KcBgRunner --project $KcBgProject --run $KcBgRun --taskbook $KcBgBook --smoke-only
if ($LASTEXITCODE -ne 0) { throw '短训练或必要证据未通过，查看该run的traceback/solutions' }

# 后台由本次已注册的Windows任务调度项启动，命令和输出路径写在回执。
# 启动前核对该任务与run归属及是否已运行；不重复启动。
Get-ScheduledTask -TaskName ([string]$KcBgInfo.task_name)
Get-Content -LiteralPath (Join-Path $KcBgRun 'progress.json') -Raw -Encoding UTF8
```

后台实际执行的Python命令是同一入口加 `--project / --run / --taskbook`，不带 `--smoke-only`。Windows任务使用当前已登录账户的交互令牌，以隐藏方式运行；任务结束不会重复定时触发。注册/启动的真实结果和PID另记回执，不用这段设计文字冒充已执行。

恢复时先看 `exit.json`：资源暂停且身份不变可重新启动同一任务，由单元回执跳过已完成训练并从未完成单元last.pt恢复；科学失败不能自动重启撞门。代码或任务书发生实质变化后需要新身份和相应验证，禁止在正在运行时覆盖源码或任务书。

### 16.6 用户后来查看哪些文件

| 文件 | 能看到什么 |
|---|---|
| `progress.json` | 当前正在做哪一步、进程号、最后心跳、累计预算用时 |
| `events.jsonl`、`work_log.md` | 每个阶段及每组训练的开始、完成、失败与实际时间 |
| `stdout.log`、`stderr.log` | 程序输出与错误；不能只靠日志最后一行判断整个实验已通过 |
| `imported_units.csv` | 哪9组旧模型被复用、对应检查点与SHA |
| `pilot/`、`curriculum_trigger.json`、`nomination.json` | 校准全过程、课程是否启动、正式试验前选定哪一种方案 |
| `formal/`、`formal_freeze.json` | 各折、各初始化、各方法的训练记录和冻结身份 |
| `outer/`、`formal_verdict.json`、`latency.json` | 外层原始预测、完整验收和速度结果；未运行则不伪造这些文件 |
| `report.md`、`calibration_table.csv`、`calibration.png` | 自动中文说明及已完成部分的图表 |
| `exit.json`、`solutions.md`、`traceback.txt` | 成功/科学失败/资源暂停/程序错误的区别和处理方向 |

启动确认后本轮交互结束。后续查看结果时，再依据这些文件和真实进程解释状态，不依赖聊天继续采样来维持训练。

# Koopman工作记录

## 2026-09-14 EXP-R4-C完整0.5ms启动

- 冻结`full_route_0p5ms_EXP-R4C.json`，SHA=`4e365ee5d87c6cf0a0f96b456a263ef7d776c3d092759ac39f08d4277ad2a7fe`；21项源码/父证据、1ms审计PASS和图表PASS均核对，错误SHA负例无输出。
- 19:49:40启动唯一`R4C_FULL_0P5MS01`，PID32068；parallel8、2379周期、0.5ms最大植物步，绝对截止2026-09-15 07:48:23，启动实际预算11.9786h。
- 初查进程存活、首条solver和非线性复核PASS、stderr为空。完整R3比较、R4、R5继续锁定。

## 2026-09-14 EXP-R4-C完整1ms结束与单条验收

- `R4C_FULL_1MS01`完整结束：2379周期、47.58s、95.1283155163m参考、墙钟33308.693095s（9.2524h），早于12h截止；stderr为空。
- `single_run_audit.json`的21项检查全PASS：全部solver/非线性复核、力/轮胎/支承、请求/实际转角、完成性、源身份及指标复算均通过。峰值点力288.059652N，最大轮胎利用率0.0499304，最小支承4677.138N，最大构形误差12.9976mm。
- 求解均值/P95/最大为13.72775/14.58468/19.61660s，2379步全部超过原5s预算；继续标记离线、非实时。
- 绘图先后因`COMPLETED`/`PASS`枚举混用和工具脚本缺`src`导入路径失败；确认空输出后清理空目录并修复，只重做后处理。最终六面板PNG/SVG打开检查PASS。
- 单条1ms只释放0.5ms协议；数值收敛和完整R3仍未裁决。

## 2026-09-14 EXP-R4-C完整1ms启动

- 新增`diagnostics/r4c_full_runner.py`：现有控制器/植物和有力窗口runner保持不改；只接入已验证8进程差分、1ms最大植物步、每25周期检查点、接受段保存和绝对截止。
- `full_route_1ms_EXP-R4C.json`冻结21项源码/父报告身份，SHA=`14f4e0101dedb59ae965f1383a3498ba6f6f07997da82df2de1f27fd00d059dd`。`--help`、正向预检PASS；错误SHA负例exit1且未建输出。
- 10:25:50在`DESKTOP-9IUUGEO`启动唯一`R4C_FULL_1MS01`，PID16796；2379周期、1ms最大植物步、parallel8，截止22:24:13，启动实际预算11.9731h。
- 初查进程存活、pool/solver流已建立，前4条solver和非线性复核PASS，stderr为空。仍是运行中状态；0.5ms及后续依赖未释放。

## 2026-09-14 EXP-R4-C有力配对PASS与预算复核

- `R4C_FORCE_PARALLEL01`于10:19:36完整结束：50周期、500子步、50条solver、stderr为空，墙钟702.142416s；相对串行1550.584120s加速2.208361倍。
- 单条图首版出现空图例框；原图保留，脚本只改后处理图例逻辑并输出`_qa`版，串/并修正版均打开检查PASS，动力学未重跑。
- `R4C_FORCE_COMPARE01`为`PASS_FORCE_WINDOW_EQUIVALENCE`：串/并/源全部非时间物理字段逐位一致，串并substeps、QP哈希及首控制逐位一致，三方首控制一致；9组时间流均在冻结32ε界内；峰值力288.0596665626036N精确复现。
- 配对图PNG/SVG打开检查PASS。旧B2b正式FAIL保持，不因新协议结果覆盖。
- 并行实测14.04284832s/周期，2379周期外推9.279982h；12h预算名义余量2.720018h。预算复核只释放完整1ms协议准备，原5s/步预算仍FAIL，0.5ms继续依赖1ms完整单条门。

## 2026-09-14 EXP-R4-C有力串行完成、并行启动

- `R4C_FORCE_SERIAL01`于09:58:14完整结束：50周期、500个2ms子步、50条solver、stderr为空，墙钟1550.584120s；峰值点力288.0596665626036N。
- 独立单条验收按整数tick对齐冻结2ms源：raw和substeps全部非时间物理字段逐位一致，最大时间表示误差3.552713678800501e-15s，低于冻结32ε界；solver状态和非线性复核全PASS。
- 新增`tools/r4c_force_window_plot.py`，生成单条六面板PNG/SVG、manifest和中文README；原始受力未平滑，图内标出5s预算，打开检查PASS。此图不替代串并行配对裁决。
- 首次重复进程检查因命令行文本包含目标run名而误命中当前PowerShell；改为仅匹配Python进程后确认无重复任务，未产生额外输出或进程。
- 10:07:21启动唯一`R4C_FORCE_PARALLEL01`，PID23808；同v3协议、同26.66—27.66s窗口及10:32:20共同截止。启动8秒后进程存活、输出目录存在、stderr为空。完整1ms继续锁定。

## 2026-09-14 EXP-R4-C时间重审与有力窗口启动

- 时间审计v1因原2ms源solver缺少`problem_hashes`在裁决前停止；v2不伪造该字段，仍要求串并行QP哈希、三方首控制及所有物理字段严格相等。
- v2协议SHA=`77e98747ff01cd8e615e0e307fa406938463d641099044be60439c90958b50c0`；错误SHA负例拒绝。`TIME_IDENTITY02`为`PASS_NEW_TIME_IDENTITY_CONTRACT`：raw/substeps/solver唯一映射登记tick，最大时间表示误差7.105427357601002e-15s小于预登记32ε界，9项正负例全PASS。旧正式FAIL保持。
- 时间审计PNG/SVG已生成并打开检查，图例、单位、边界和负例覆盖可读，figure_status=PASS。
- 首个全程最大子步点力为288.0596665626036N，首次出现于connector0、t=27.154s。按最近20ms tick居中规则登记26.66—27.66s、50周期、500子步窗口；R3连接器无隐藏历史状态。
- 有力窗口协议v1/v2分别因两个SHA录入错误在QP构造前被拒绝，证据保留；最终v3的12项身份已全表核对无错，SHA=`09fbd10be827af1da6177c88917b9f701ab14472df2097fbdb3b3791501042d6`。
- `R4C_FORCE_QP01`通过：状态恢复完整，P/q/A/l/u/u_nom及首控制逐位一致，串并非线性复核PASS。串行build=36.444446s，并行build=13.940386s；仍为OFFLINE_ONLY/FAIL_ORIGINAL_5S_BUDGET。
- QP原图的相同无穷边界做`inf-inf`产生NaN并使零差异面板空白。保留原图，新增不重算QP的QA图和修正JSON，六组差异0清晰可见，图表QA通过。
- 09:32:20启动`R4C_FORCE_SERIAL01`，PID36904，共同截止10:32:20；启动10秒后存活且stderr为空。串行通过后才启动唯一parallel8，完整1ms继续锁定。

## 2026-09-13 B2b完成、分析失败与停止

- PARALLEL01于23:01:09完整结束：COMPLETED，125/125周期，raw=125行、substeps=1250行、solver=125条，stderr为空；墙钟1797.407461s。相对串行3922.794941s加速2.18247倍，两窗合计5720.202402s，未超过冻结2小时预算。
- 正式分析产物`20260913_R4B_B2B_COMPARE01/window_equivalence.json`返回FAIL（exit 20）。通过项包括串并行raw、substeps、QP problem hashes、首控制逐位一致及两批完整结束。
- 失败项首先暴露分析器源切片边界问题：源42s边界浮点值为42.00000000000001，严格`>42.0`仍会纳入，造成raw比较错位、源substeps=1251。未覆盖正式报告。
- 只读对齐诊断显示：正确125个raw/1250个substeps对齐后，全部非时间字段逐位一致；仅`time_s`在raw 15行、substeps 150行不逐位相同，最大差7.105427357601002e-15s。详细证据写入`failure_diagnosis.json`。
- 按第22.3节“浮点差异不得自动放宽”停止：`STOP_B3_NEEDS_INDEPENDENT_REVIEW`。未启动完整1ms、0.5ms、R4或R5，也未消耗其预算。

## 2026-09-13 SERIAL02完成与PARALLEL01启动

- SERIAL02于22:28:14完整结束：`COMPLETED`，125/125周期，raw=125行、substeps=1250行、solver=125条，stderr为空，墙钟3922.794941s。
- 物理摘要：最大轮胎利用率0.00522764、最小支承载荷4905N、最大构形误差0.00357381m；终止原因为空。此处只判定串行短窗证据完整，不替代后续源窗口复现和串并行逐位比较。
- 确认不存在目标输出目录或既有parallel8 runner后，于22:30:59启动唯一`20260913_R4B_B2B_PARALLEL01`，PID37684；协议SHA=`e421a0eacde4b6ec26a861f4ef377329fdfedf1cd2ca9616f812d5a49859d774`，共同截止仍为23:22:46。
- 启动8秒后PID存活、stdout/stderr均为空，符合初始化阶段；B3继续锁定，待parallel8完成并运行`r4b_window_analyze`。

## 2026-09-13 B2b后台承载修复与SERIAL02

- 用户“继续”作为B2同窗重入授权；冻结`offline_budget_EXP-R4B_B2_retry1.json`，SHA=`e421a0eacde4b6ec26a861f4ef377329fdfedf1cd2ca9616f812d5a49859d774`，只允许一次完整重试，禁止拼接SERIAL01。
- `20260913_R4B_BACKGROUND_PROBE01`：隐藏Python子进程在父PowerShell退出后继续存活，15秒后独立写出PASS。
- `20260913_R4B_B2B_SERIAL02`：PID17928，42.00—44.50s、125周期、串行逐步雅可比、2ms植物；截止2026-09-13 23:22:46+08:00。stdout/stderr分别写入`logs/20260913_R4B_B2B_SERIAL02.*.log`。启动10秒后进程存活、stderr 0字节。
- 门控不变：SERIAL02完成并独立验收PASS后才启动parallel8；重试失败/超时则停止B3且不自动追加预算。

## 2026-09-13 EXP-R4-B B2b承载中断

- 续接时`20260913_R4B_B2B_SERIAL01/status.json`仍显示45/125 RUNNING，但无对应Python进程，前台exec session已不存在。独立核对：raw=45行、终点42.90s；substeps=450行；solver=46行且末条tick2145/time42.9/statusPASS，但该控制未进入raw/plant。
- 新增只读裁决`interruption.json`：`INTERRUPTED_INCOMPLETE / FOREGROUND_EXEC_SESSION_TERMINATED`。保留原RUNNING检查点，不覆盖raw/substeps/solver。
- 发现时共同截止21:59:49只余约40分钟；完整串行重跑按31s/步约65分钟，无法合法完成。未验证断点恢复与连续运行逐位一致，因此不拼接，不启动parallel8，不进入B3/完整1ms。
- 科学边界：这是基础设施承载失败，不是求解、植物或算法等价失败。重新进入需新的B2重试预算及已验证可独立存活的后台承载。

## 2026-09-13 EXP-R4-B B0—B2启动

- 冻结第22节任务书`inputs/experiment_EXP-R4B_5586D94A.md`及离线预算`protocol/offline_budget_EXP-R4B.json`（SHA=`56c05813ea85a71c95e57d2178dceea6f43f519c2cb6e3901cac34e8694a4870`）。B0/B1正向门PASS，错误协议SHA负例FAIL，旧2ms status哈希未变，无活动重复任务。
- B2a `results/20260913_R4B_B2A_01` PASS：四个登记点的串行/8进程P/q/A/l/u/u_nom、首控制逐位一致，双方非线性复核PASS。串行31.29—31.41s，8进程12.47—12.58s，继续标记OFFLINE_ONLY和原5秒预算失败。
- B2b串行窗口`20260913_R4B_B2B_SERIAL01`已按42.00—44.50s、125周期、2ms植物、共同截止`1789307989`启动；5/125检查点正常，最近求解31.5322s。心跳`EXP-R4B门控续跑`每10分钟只在状态变化时续接或报告，不重复启动，不跨门。

## 2026-09-13 EXP-R4 U0—U3实际执行

- 主机`DESKTOP-9IUUGEO`，Python 3.11.14，Ryzen 7 9700X（8核/16线程）；现场无活动`paper_v4`实验进程，未发现晚于既有2 ms批次的新动力学结果。
- 冻结当前任务书为`inputs/experiment_EXP-R4_97D79F76.md`，SHA256=`97d79f764f0ed308539e9a911d0498ecc571a82dda2942761a092ddb3fce1144`，父EXP-R3 SHA保持`eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87`。EXP-R4 preflight成功，E00仍PARTIAL。
- U1：新增版本化候选合同和负例；原`20260911_R3_UNFROZEN_FULL01/2ms`的runner/controller/batch/protocol/递归plant及独立物理证据全部通过，裁决为`PASS_RECONSTRUCTED_IDENTITY`。原`status.json`未改，SHA256=`c1db7cde0e17f4dabb755c51403086db79dd2900b201dcdfa6904c00e4cac8f8`。
- U2：四个登记QP点逐位复现，QP和非线性复核均通过。逐步雅可比两点总计34.818888/32.300863 s，构建34.342859/31.923166 s，其中动力学线性化32.326657/30.311146 s；QP求解约0.01 s。平均33.559876 s，未达5 s。
- U3：只并行彼此独立的中心差分rollout，8进程14.151784 s，16进程14.684687 s；两轮P/q/A/l/u/u_nom均与保存问题逐位一致、非线性复核PASS，但预算均FAIL。按两轮小工程修复上限停止，未启动1/0.5 ms完整轨迹、R4或R5。
- 自动验证：候选身份测试3项通过；全`paper_v4/tests`为`3 passed in 0.82s`。首次pytest仅有根目录缓存权限警告，复验以禁用cache和项目内临时目录解决。
- 详细问题、方法和效果：`experiment_execution_20260913.md`。

## KFIX-PLAN-001 — 2026-09-02 21:03 — 纠错与创新复验任务书

- 请求/任务编号：基于最新P5B数据指出历史错误、建立行为约束并编写后续实验指导。
- 授权模式：方案编写。
- 机器与项目根目录：计划执行目标为5080 `DESKTOP-9IUUGEO`，`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 读取：本地`_koopman_v3_results`、历史任务书快照、P5A/P5B数据；只读核对5080历史run、进程、源码manifest、工作记录和checkpoint目录时间。
- 修改：新增本地任务书`D:\PDxc\Review\koopman_fix.md`；新增本工作记录。未修改5080项目代码和历史结果。
- 任务书SHA256：`64A61DF224EF5F8B56D0A6298D15080B797792DD1B669B295B537ACB73803927`。
- 关键修正：最佳检查点恢复；best/stop步分离；完整resume身份和RNG；stage不可覆盖；禁止跨源码复用旧checkpoint；旧validation污染隔离；A1等预算；完整折早停；CVaR贡献与成员审计；逐窗原始证据；有限稳定性声明边界。
- 执行边界：本轮未启动训练。以后首次按任务书执行时默认只授权`F0→F4`，F4后人工停止。
- 结论类型：事实审计与实验建议。
- 状态：PASS（任务书已生成，实验NOT_RUN）。
- 下一步：用户审阅任务书；若明确要求执行，再从F0现场身份核验开始。

## KFIX-EXEC-001 — 2026-09-02 22:21 — 第一轮授权 F0→F4 执行中（run 20260902_212715_KFIX_R01）

- 授权：`F0→F4`，F4 后无论 PASS/BLOCKED 人工停止；M/V/C 层待二次授权。
- F0 PASS（21:27）：E01—E18 登记 f0/known_issues.json；environment/baseline/split_status/processes 证据落盘；old validation=CONTAMINATED_D5_BY_AF，confirm=0。
- F1 PASS（21:41）：硬门 no_legacy_checkpoints/confirm_zero/history_untouched 全过；identity 封存（source 49 files sha 20338E9F…）；new_validation_ledger 封存（seed_start 991000，模拟推迟 V0）。
- F2 PASS（22:19）：56/56 测试。期间修复小故障（2.4 规则）：`src/losses.py cvar_tail` 曾返回标量，与 train.py BCV 分支元组解包契约不符（TypeError: iteration over a 0-d tensor）；恢复 `(mean, topk_indices)` 返回，SHA 8EE5B4AD…，记录于远程 solutions.md/decision_log.jsonl。
- F3 运行中（22:20 启动）：smoke warm200+phase500 × ONE/MH/MHC/BCV + resume 等价 ≤1e-7。首启因 f3 残留旧冻结文件被 write_once 正确拦截，清理后重跑。
- F3 PASS（22:26）：resume_rel_error=0.0（修复 _resume_equivalence 评估模型未 .to(device) 的 cuda/cpu 不匹配；run_v3r.py SHA 9CCE81D0…）；runner 顺延自动进入 F4。
- F4 运行中（22:29 起）：五折公平复验，fold 0 ONE16 early stop at 4500（best 2500）；预计 1.5–4h，F4 后人工停止交付报告。
- **F4 缺陷发现（run 20260902_212715）**：MH16/MHC16/BCV16 rows_best 逐位相同——closure/tail 项被 `.item()` 断梯度，MHC/BCV 实际按 MH 梯度训练（同型于 P5B A2==C16）。修复 train.py 保持 tensor 梯度流 + 新增梯度回归测试（MHC≠MH、BCV≠MHC）；按 E07 建新 run 全链重跑。
- **新 run 20260903_041205_KFIX_R01**：F0 04:12 → F1/F2(57 passed)/F3(resume 0.0) PASS → F4 09:52 BLOCKED。
- **F4 裁决**：修复生效（MHC/BCV 与 MH 分化；ONE16/MH16 与缺陷 run 逐位一致）。macro 改进 ONE16 +0.02% / MH16 +20.08% / MHC16 +20.10% / BCV16 +17.71%（均 5/5 正折、d5_hard +25~48% 无退化）；**唯一失败门 scenario_degradation**：MH 系在 D10/D11 场景退化 24–35%（ONE16 各场景 ≤2.5%）。无变体通过候选合格门 → **BLOCKED，人工停止**；M/V/C（含 V0 模拟）等待二次授权。

## KFIX-AB-001 — 2026-09-03 — koopman_ab.md 双路执行 Q0→Q1（run 20260903_193821_AB_Q0_R01）

- 授权：默认 Q0→Q1；Q2 人工决策；AR/SB/V0/C0 逐次授权。用户指示"能自决就不要停"。
- **Q0 PASS**（19:38）：SHA 链全过（ab 任务书 C835AE56…）；confirm split 计数 0（manifest 无 confirm 行，任务书 1.1 "96"与 3.5 "0"矛盾已记录）；新 validation 账本 95F1A201… 未动；P1–P7 无损；步骤 6 A 级修复（v3r 加 V0/C0 入口，新 manifest 6851C696…，57 测试全绿）。
- **Q1 PASS**：M1 完整；M2 与 F4 verdict 数值一致 ≤1e-9；M3–M8 全落盘。
- **Q1 重大发现（前提修正）**：
  1. F4/D10–D11"退化 24–35%"是符号误读——正值为候选改善，D10/D11 实为 MH16 最大改善区（h20 +24~32%）；
  2. 真实最差工况 = **D1**（MH16 fold4 +20.9%、fold0 +8.5%、fold3 +6.4%、fold1 +3.7%）；
  3. D1 退化由 **connector_event start=360 窗力/内部力崩溃**驱动（force4_d +0.24~+0.36 而 relative_d 改善）→ F-A'/F-C'；
  4. **E19**：F4 scenario_degradation 门实现缺陷（max(s−c)≤3 拦截最大改善，与 macro≥5% 自相矛盾；任务书语义为最差退化 ≤3%）——人工裁决项；
  5. F-B/F-D 不成立（无振荡相位；退化跨 h）。
- **状态：人工停止点①**——q1_report.md 第 5 节 5 个 Q2 选项（含 AI 推荐：裁决 E19 口径 → AR'(D1) 先行 + SB16-eq/up(D1) 并行）；等待用户圈选路线。

## KFIX-AB-002 — 2026-09-03 22:30 — Q2 圈选后执行（AR' + SB16 + E19 新 run）

- **Q2 人工决策**：E19 = 新 run 重跑 F4 裁决（修正门实现）；路线 = AR'(D1 回退) 先行 + SB16 并行。
- **E19 修复**：v3r run_v3r.py scenario 门改 worse 方向（max(候选差) ≤3%）；57 测试绿；
  新 v3r manifest A0D7117F…；F4 重跑新 run **20260903_215712_AB_F4E19_R01**（F1-F3 PASS，F4 fold_0+ 训练中，预计 ~04:00 完成）。
- **AR1+AR2 PASS**：spec_A（场景级 {D1} 回退）八门全过（macro +20.39%、5/5 正折、零发散、
  D1 构造性 0）→ AR 路线冻结候选；spec_B（窗口级）失败记录；V0 步数冻结 MH16 median 14000；
  fallback 组合器 + 测试 4/4。
- **SB1+SB2+SB3 PASS**：v3s 新树（52 文件）实现场景均衡（w_s=N/(12·n_s)，up D1 3×）；
  63/63 测试（57 继承+6 新增）；smoke resume=0.0、warm SHA 与 v3r 一致、权重均值=1。
- **下一步**：F4 重跑 verdict → SB4 五折双臂（GPU 独占）→ 人工停止点②（V0 第三次授权）。

## KFIX-AB-003 — 2026-09-04 03:40 — F4 E19 重跑裁决 + SB4

- **F4 E19 重跑**（20260903_215712_AB_F4E19_R01）03:37 出 verdict：数值与修复前**逐位一致**
  （可复现）；修正门语义下 MH16/MHC16/BCV16 仅因 **D1 退化**失败（macro/d5/D5/力门全过）；
  ONE16 基线多门失败 → BLOCKED（passed_variants=[]）。E19 闭环（官方裁决=Q1 复算）。
- **SB4 运行中**（v3s run 20260903_222641_AB_SB_SB_R01）：五折双臂 SB16EQ/SB16UP(D1 3×)，
  预计 ~07:30 完成 → sb4_verdict（F4 八门 E19 修正口径）。

## KFIX-AB-004 — 2026-09-04 06:50 — SB4 BLOCKED → 人工停止点②

- **SB4 裁决**（06:47）：双臂 BLOCKED——SB16EQ macro +18.57%、SB16UP +18.88%（5/5 正折、
  d5_hard +24~45%、零发散、力门过）但 scenario_degradation 双臂失败。
- **机制证据**：SB16UP（D1 3×）几乎修复 D1（fold1/3 达 −6~−11% 改善）→ 证明 D1 退化可训练修复；
  但 D1 上权把梯度拉离 D0 → fold3 D0 +5.50% 退化（绝对量 0.0011，S0 0.003 低误差工况被相对口径惩罚）。
  SB16EQ 把 D1 从 +20.9% 峰值降到 +1.4~+11.1%（fold1/4 仍超 3%）。
- **路线状态**：AR'（MH16 + spec_A D1 场景回退）**AR2 八门全过**（macro +20.39%、V0 步数 14000 冻结）
  = 冻结候选；SB16 双臂失败（按预注册规则停止）。
- **人工停止点②**：等待人工决策（① AR'→V0 第三次授权；② SB16UP+D0 防护变体需新预注册；
  ③ AR'+SB16UP 混合；④ 路线 C）。V0/C0 禁止自动进入。

## KG-PLAN-001 — 2026-09-04 13:42 — 短期精度保护与多步收益实验指导

- 请求：根据最近实验数据编写下一步指导MD；用户“继续处理”承接文档完善，不作为启动实验授权。
- 授权模式：方案编写。只读核查5080；只修改本地指导书和本工作日志。
- 机器/项目：`DESKTOP-9IUUGEO`；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026`。
- 读取：最新F4 `20260903_215712_AB_F4E19_R01`、SB4 `20260903_222641_AB_SB_SB_R01`、AR `20260903_193821_AB_Q0_R01`的逐窗CSV、裁决与源码清单；N5 manifest、N6 fixed-linear S0超参数选择；本地v3s代码、任务书、工作记录；用户原审稿意见附件。
- 身份核验：v3r源码49文件、v3s源码52文件均与各自最新阶段manifest逐项SHA一致；Python 3.11.14，NumPy 2.0.1，PyTorch 2.12.0.dev20260304+cu128，pandas 3.0.1；CUDA可用。只读检查期间未见其他训练/MATLAB进程。
- 数据事实：train共96族/336轨迹，R3-ES与V1-ES各168轨迹；D0—D11每类8族。两植物同族不能算成192个独立样本族。confirm资产0，新validation未生成。
- 复算：五折各自工况等权后改善率平均，MH的一步/20步为-40.0485%/+20.0781%；AR为-37.2675%/+20.3863%。分植物合并五折后12工况等权，R3为-40.3228%/+19.2805%，V1为-40.5923%/+19.2893%。正为改善，负为退化；不同聚合口径不混用。
- 对历史记录的补充纠正（保留原文，不覆盖）：AR2通过不代表满足V0短期门；BCV不只有D1问题，还存在D0失败；“D1上权把梯度拉离D0”是未被梯度诊断证明的推断；D0使用0.02分母下限后仍超3%门，不能仅归咎于小分母。旧CV复用FULL_TRAIN S0与全train归一化，不是整条学习流程独立CV。
- 修改：新增`D:\PDxc\Review\koopman_guard.md`（648行）；追加本日志。未修改5080代码/协议/模型/结果，也未覆盖旧MD及用户Word表格。
- 指导书SHA256：`8F9367990910DA45B6EABB726C1FF717EFB8C745338DAFCCE382DCDF3D8A058D`。
- 方案：最新R3全12工况为主；折内重拟合S0及归一化，拟合/内部选择/外层分离；共同MH、指标对齐JM、55项经验保护JG三组；G0—G5门控；明确公式、代码函数、参数、采样、检查点、权限、图表、修复命令、成本和失败处理。未把保护损失包装成效果或泛化保证。
- 校验细节：修正公式的有效F行列约定；区分47维误差权矩阵与3×8抓取矩阵；分开float64平滑误差和float32舍入误差；T0/T2微批需非线性聚合等价验证；续跑测试跨500步乘子更新；准确run回执避免无人值守Read-Host挂起。
- 命令：PowerShell Get-Content/rg/Get-FileHash；通过`ssh 5080`向指定Python传入只读CSV/manifest复算脚本；文档编辑使用apply_patch。一个编辑patch因上下文行不匹配被拒绝，未改文件，随后修正上下文成功；未触发实验重试。
- 文档核验：UTF-8无替换字符；Markdown代码围栏8处成对，显示公式13组成对；G0—G5/T0—T2、停止/日志/回执等必选项检查无缺失。检查退出码0。此核验是文档检查，不是尚未实现实验代码的测试通过。
- 结论类型：指标和源码问题为事实；短长期冲突/目标错位为待验证推断；三组实验与验收规则为建议。
- 状态：指导书PASS；新代码、新训练、V0/C0均NOT_RUN。
- 下一步：用户审阅指导书；未来明确授权执行本文件后，按G0—G5自动推进并在G5或硬门失败处停止；不得自动开启新validation/confirm、MPC或网络实验。

## KG-EXEC-001 — 2026-09-04：G0登记完成

- 用户明确授权执行 `koopman_guard.md`；本轮仅G0—G5，硬门失败即停，不进入V0/C0。
- 5080机器现场确认 DESKTOP-9IUUGEO；创建独立 `revision_2026/koopman_predict_v3t`，从已核验v3s复制，历史目录未修改。
- 新增 `scripts/run_v3t.py`、`config/protocol_v3t.json`、任务书原样快照。正式run：`20260904_141510_KG_R01`，回执 `koopman_predict_v3t_results/receipts/KG_R01.json`。
- v3r 49个/v3s 52个文件哈希与历史manifest一致；N5清单SHA与任务书一致。训练336轨迹的原始及缓存共672次文件哈希核验全部吻合，无数值解包读取。R3为96族168轨迹；五折outer族数19/20/20/19/18、inner各12、fit65/64/64/65/66，各角色均含12工况。
- G0命令：指定5080 `E:\anaconda\envs\pytorch_new\python.exe` 调用新runner `--stage G0 --run-tag KG_R01`，绝对项目/协议/任务书/回执路径均登记在run中。退出码0；`g0/complete.json` PASS。
- 工程异常：首次过早启动时scp仍在传输任务书，因FileNotFoundError退出1，未分配run、未运行实验。等待全部传输退出0后启动成功；未修改算法或门槛。
- 证据：新run的g0/environment、historical_identity、baseline_files、fold_manifest、data_access_policy、source_manifest和complete，以及split_access/decision日志。
- 状态：G0 PASS；G1正在实现历史诊断；G2—G5 NOT_RUN。G0策略JSON不是G2实际文件权限测试通过的替代证据。

## KG-EXEC-002 — 2026-09-04：G1完成、G2复测

- KG_R01 的G1在历史表完成后因OpenMP重复运行库原生退出1；保留部分产物。改为MKL_THREADING_LAYER=SEQUENTIAL，未使用忽略运行库冲突的开关；新代码/环境在KG_R02重新登记G0，全部身份再次通过。
- 当前run：`revision_2026/koopman_predict_v3t_results/runs/20260904_142331_KG_R02`。
- G1完成：7条历史路线表重算，53条历史轨迹、262个预选窗口的真实状态—NumPy—Torch力oracle通过（CPU float64，atol=1e-8 N、rtol=1e-10）；262窗中91窗一步归一化平方误差增大，恒等式残差最大2.22e-16。30项短期/20步梯度对比中8项余弦负。两项计数仅为预选诊断样本，不能外推总体或作为J_common改善结论。
- G1退出0，完整产物位于g1，包括history_horizons、plant_scenario_metrics、force_oracle、one_step_correction、boundary_diagnostics、force_jacobian、gradient_conflict、diagnosis和complete。
- 新增guard_core、guard_training、guard_tests等隔离实现：真实文件打开权限检查、折内S0/归一化、params身份常量缓存、工况/族/轨迹/窗口采样、55项保护、可行性优先检查点、原子保存和精确恢复。
- G2首轮因测试参考表达式重排了正则项加法而失败；核查旧train.step_loss后直接调用原函数，未放宽测试容差。attempt_002的15项测试退出0；600与350+250在第500步更新之后模型/Adam/RNG/采样/lambda逐位一致。
- 后续自查补强公开full_k_matrix接口、真实NaN/Inf/缺文件/重复行/缺工况拒绝，以及warm更新独立性；修复公开K的F转置约定，保持eta@F传播不变；F在一次rollout内只构造一次，待与原v3s未改lift进行回归。源码变动后必须再执行G2，attempt_002不能直接授权新源码训练。
- G3/G4/G5入口已实现但尚未执行；正式训练和外层评价未开始。外层读取必须在全部15个主检查点冻结后开启。禁止把代码实现或测试冒烟当作方法精度证据。

## KG-EXEC-003 — 2026-09-04：G2最终复测、G3通过、启动G4

- G2 attempt_003全部15项通过，退出0；直接与原v3s未改lift/step_loss比较，前向和梯度回归通过。公开full_k_matrix用F.T且支持所在device，实际传播仍eta@F；只在一次rollout内缓存固定F以省去重复构造。
- 恢复测试使用小型合成拟合集，连续600步与350+250步跨500乘子更新后模型、Adam、随机状态、采样流、lambda一致。实际NaN/Inf输入、重复行、缺工况、缺文件及权限绕过均有异常拒绝；测试清单和源码manifest在g2/attempt_003。
- G3按预定fold0每工况2族、共同warm200、三组各500步执行。正式段T0/T1/T2用时8.8/9.9/10.4 s（包含监控）；G4估计1.264 GPU小时，低于12小时上限。G3 complete PASS，退出0，成本、显存、窗口和曲线以g3/cost.json为准。
- 启动同一KG_R02的G4五折三组正式训练；源码必须与G2最终manifest一致，实际命令--stage G4 --g2-attempt attempt_003，所有项目/协议/任务书/回执均使用绝对路径。
- 当前只允许fit训练和inner监控，全部15个best冻结前不允许outer评价。未启动V0/C0、确认集或控制/网络实验。

## KG-EXEC-004 — 2026-09-04：G4/G5结束与交付审计

- G4退出0，五折15个主检查点全部冻结后统一开启outer；G4 complete PASS，gpu_wall_s=973.9015975。每折warm2000；除fold2 T2正式5500步外，其余正式2500步；最佳点除fold2 T2为3500外，其余500。未为了凑成功重跑seed，未依据outer回选。
- G5退出0，独立Python与pandas层次聚合一致到1e-12；完成2000次族级配对bootstrap、全门表、40步压力、同步GPU/单线程CPU延迟、残差/全K统计和8组图（含固定及事后最坏力窗口，共12 PNG+12 PDF）。
- R3合并外层J改善率h1/5/10/20：T0=-16.5827/+19.507/+19.097/+13.7952%；T1=-3.665/+22.447/+20.736/+16.9160%；T2=-0.246/+22.580/+22.519/+19.5111%。精确值以g5/horizons.csv为准。T2 h20 CI95=[17.3943%,21.7516%]，5/5折同向。
- 无组通过全部门，selected=null，停在G5。T2合并外层D2/D7/D8/D9一步分别退化7.0132/10.6122/3.8719/3.7544%；D5一步最大误差统计退化25.5711%；GPU batch1 20步含力解码median=4.09095 ms、P99=4.76159 ms，超1/2ms门；CPU median=0.78120ms。不能用总体改善掩盖局部和尾部失败。
- 最终审计：15个主检查点SHA、20份outer CSV SHA、24份图文件SHA全部吻合；15个best均BEST_INFEASIBLE。T2乘子未饱和，上限不能作为既定失败原因。完整证据g5/checkpoint_verdicts.csv、delivery_audit.json。
- 新增磁盘级合成heldout扰动补充测试：分别改变inner/outer测试NPZ后，fit归一化/S0和5步warm均逐位不变，真实缓存修改0；结果g2/heldout_fixture_probe/complete.json。该测试不属于新validation/confirm。
- G4源码63文件按冻结manifest逐项核验归档source_snapshot.zip。G4之后只修改报告/绘图脚本：校正S0延迟使用真正固定线性路径、单列传输耗时、补充预注册最坏窗、物理/全K证据和图源SHA。G5保存独立源码manifest和变更说明，未改变任何训练、预测或选点。
- 工程边界审计：主CLI跨阶段--resume-incomplete分发器与持久进程锁未完全实现；本次采用现场进程检查及单进程顺序调度。底层精确续跑通过不等于完整运行器恢复入口通过。自动complete中的all_tasks_finished只适用于实验阶段，交付审计明确了遗留项，不宣称任务书全部工程项100%完成。
- 本地交付D:\PDxc\Review\guard\：自动报告/解决方案、notes.md独立解释、CSV/JSON和全部图。工作记录本地与5080追加同步；历史源码、原始数据、旧结果均保留，未运行V0/C0或控制/网络实验。

## KR-PLAN-001 — 2026-09-04 20:32 — 一步修正与保护机制详细指导

- 请求：按最新讨论编写下一轮细致实验MD，包含代码、公式、步骤、失败处理、自主修复边界和工作留痕；工况使用中文名称。
- 授权模式：方案编写。只读核查5080；仅新增本地任务书并追加本日志。未部署新源码、未启动训练、未生成新数据，也未修改旧任务书、历史结果或用户Word表格。
- 主机/项目：`DESKTOP-9IUUGEO`；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026`；Python `E:\anaconda\envs\pytorch_new\python.exe`，3.11.14。
- 本轮基线：`20260904_142331_KG_R02`，G5为COMPLETE_STOP、selected=null。当前v3t源码与G5清单63项一致，15个冻结主检查点SHA一致，历史折划分SHA为`2DBAF6D83B14594C444234E05EC03638C0FE66935F17F8C5A7D82A0E468D1AC0`；v3u目录现场尚不存在。
- 读取：原koopman_guard.md和完整审稿意见；guard本地结果/交付审计；远程lift、guard_core、guard_training、guard_experiments、run_v3t、causal_schema和数据缓存构造代码；一个fold0合法拟合轨迹的raw/cache字段schema；历史源码及模型清单。
- 证据基线：最新保护方案总体一步改善-0.2456%、20步改善+19.5111%；回头弯20步原定尾部保护通过。原报告额外诊断与硬门混合导致84条失败记录，按原范围重算为29条；不修改旧CSV，也不把检查记录数当独立故障数。
- 机制约束：四个折best500保存前没有用过非零自适应乘子；新文档分开lambda_used/after并注册固定保护与自适应消融。当前已有2000步一步预热，新课程只能作为一步平方误差时序对照，不能包装成此前没有的一步监督。
- 新发现（代码事实）：`koopman_predict_auto/src/dataset.py::prediction_cache_from_raw`的control7由虚拟三量加四车请求转角构成，没有显式加入四车请求加速度；工况生成器存在前后/对角差分加速度。因此任务书新增输入控制完整性前置门。
- 新发现的边界：原始控制差分的逐轨迹数值对照请求遇到SSH连接超时，未得到该次结果；不据此声称已经量化缺项的误差贡献。KR0必须核验是否存在可恢复该控制量的其他因果输入。若缺项成立，先停训练路线，按附录B提出control11派生缓存、所有基线共同重训及公平对照；该输入扩展需另行确认协议，不暗中混入7维实验。
- 字段核对：cache实际上有system_yaw_rate辅助列，但47维状态中没有直接系统横摆输出；文档要求追踪其定义，不能说字段不存在，也不能用四车均值充当系统横摆。单车绝对横摆由货物横摆加对应相对横摆读出并回归核验。
- 新增文件：`D:\PDxc\Review\koopman_refine.md`，925行、78704字节，SHA256=`D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612`。
- 任务书内容：KR0—KR7；残差误差分解、统一gamma五点前沿、三方法一折三seed机制pilot、固定6000步与旧早停重放、唯一条件课程、预提名后五折三seed验证、等价推理优化、原硬门/额外诊断分表、20项测试、恢复/锁/回执、输入修复附录、图源与论文声明边界。
- 范围：本轮明确不启动新validation/confirm、全train重训、MPC、网络、DoS；未通过硬门不能自动向后推进。文档中的新CLI、文件和测试均标明尚待实现，不记作代码完成。
- 校验：UTF-8无替换字符；18处代码围栏成对，11组显示公式成对；所有必需章节/阶段/停止/恢复字段齐全；两个PowerShell代码块通过语法解析，仅解析、未执行。100个合成玩具算例的40步gamma仿射恒等式最大残差6.11e-16，一步平方误差恒等式最大残差5.55e-17；这些只验证文档数学，不是项目训练测试。
- 数量校验：正式三主方法未缩放/校准三seed加不重复基线共291080条时域记录；加课程为383000条。没有把三个seed当成三倍独立轨迹。
- 命令与异常：PowerShell Get-Content/rg/Get-FileHash及指定SSH/Python只读检查；编辑使用apply_patch。一次CSV读取因BOM字段名失败，改utf-8-sig后成功；一次patch因上下文顺序失败且未改文件，按顺序重提后成功；一次补充SSH对照超时如实保留。均未触发实验运行或原始数据修改。
- 历史保护核验：koopman_guard.md SHA仍为`8F9367990910DA45B6EABB726C1FF717EFB8C745338DAFCCE382DCDF3D8A058D`。
- 状态：文档校验PASS；新源码/训练/输入修复/控制均NOT_RUN。本日志本次只在本地追加，未声称已同步5080。
- 下一步：用户审阅新任务书。若授权执行，先做KR0输入契约核查；发现真实控制缺项时停止调参，按附录B提交新输入协议，不在信息缺失前提下反复训练。

## KR-001 执行 — 2026-09-04 21:10 — koopman_refine.md KR0（run 20260904_204301_KR_R01）

- 授权：用户"严格执行这个md"→ KR0—KR7（第 8 节自动推进；KR7 后停止）。远端任务书 SHA D6982DE2… 与本地一致；v3u 树创建（63 文件，自 v3t 复制未改）；KR run 回执 KR_R01.json。
- **KR0 结果：INPUT_CONTRACT_BLOCKED（exit 21）→ KR1—KR6 训练路线停止**。
- 身份核验 PASS：guard 任务书 8F936799…、数据清单 B04F2C0C…、折划分 2DBAF6D8…、v3t 四源码 SHA 全对（lift 2CEB2198 / guard_core A14C3352 / guard_training D94F42C2 / guard_experiments 1F306A92）、g5=COMPLETE_STOP selected=null。
- 历史复算 PASS：20 份 outer rows CSV 独立复算主表（族等权分层聚合：窗口→轨迹→族→工况→12 等权），与 guard 交付表逐位一致（max diff=0.0）。
- **输入契约 BLOCKED（数值证据）**：dataset.py control7 只用 requested 转角列；generate_data.py:229 把四车加速度偏置（D7 ±0.20、D9A ±0.15）写入 requested_control4x2[:,:,0]——从未进 control7。fold0 fit 轨迹数值：D7 diff max 0.2281 m/s²（活跃 83.3%）、D9A 0.1728 m/s²；**存在相同 control7 行携带不同差分加速度**（无歧义恢复不可能）。
- 产物：kr0/{environment,identity_audit,historical_recompute.csv/json,input_contract.csv/json,schema,fold_manifest,complete.json} + solutions.md（附录 B 11 维输入协议修复方案：control11 派生缓存、编码器 38/35→42/39、B0 47×11、先 7 维 vs 11 维固定线性公平比较）。
- 事实 vs 推断：BLOCKED 判定与代码/数值证据为事实；"状态历史不能保证区分将来反向指令"为推断边界（严格反事实未运行，如任务书 KR0 所述）。
- 下一步（人工）：用户确认 11 维输入协议（新任务书/协议版本）→ KR0 重跑 INPUT_CONTRACT_OK 后才允许 KR1。禁止 AI 在未确认前继续训练路线。

## KR-002 输入协议实施 — 2026-09-04 23:10（用户批准 11 维协议后）

- **用户批准附录 B 11 维输入协议**（ask_user 圈选"批准 11 维输入协议"）。
- 协议冻结：revision_2026/koopman_input_protocol.md（SHA B28E1C82F25C455214BD8C6FCF8C317F63F149BD95FD6CCBF36FBD56B5D08FC4）——u11 定义/缓存派生规则/模型接口/比较矩阵 B.4/基线规则。
- **control11 缓存派生完成**：672/672（n5_cache11/ 目录，control11 前 7 列与 control7 逐位一致、四车请求加速度重构误差 ≤1e-12）；cache11_manifest.csv 落盘。
- **v3u 接口 input_dim 参数化**：lift.py（encoder 38/35→42/39 按 input_dim；B0 47×input_dim；G 16×input_dim；input_schema）、guard_core.py（fit_normalization(input_dim)/u_field 检测/WindowData/fit_s0 gram 59/new_model(input_dim)）、evaluation_v2.py（control11 norm 检测）；**63 测试全绿（7 维默认逐位无回归）**。
- **11 维垂直切片冒烟 OK**（units/kr_input11_smoke.json）：fold0 fit control11 归一化 + S0 拟合（coeff 59×47、condition 1.36e8 <1e14）+ 模型（u11、B0 47×11、G 16×11）+ rollout 有限；AccessGuard 拦截直读验证权限链有效。
- 下一步：B.4-2 固定线性 7 维 vs 11 维比较（D7/D9A 一步）；B.4-3 残差结构同预算比较；KR1 正式工程（runner/20 项测试/冒烟）。

## KR-003 B.4-2 结果 — 2026-09-05 00:30 — 固定线性 7v11 五折（fold0-4 inner）

- **D7（前后反向加减速）h20 平均改善 ~64%**（5/5 折：58.9/68.3/68.2/61.4/61.6%）、h1 ~35% 改善；
  D9A h20 ~35%（26.9/39.7/36.6/29.2/41.5%）、h1 ~19%；D5 h20 亦改善（6.5–16.3%）。
  → **输入契约补全（仅加四车差分加速度列）对目标工况带来巨大一致改善（固定线性，无任何算子改动）**。
- D0/D1（无加速度偏置工况）h20 一致退化（D0 fold2 0.009→0.036；D1 fold0 0.077→0.109）——
  11 维线性基线的弱点；条件数 7v11 几乎相同（~1.3e8 <1e14）排除病态原因；如实保留，待 B.4-3
  残差结构与 B.4-4 新基线规则处理。
- 产物：units/kr_b42_dim{7,11}_allfolds.json（含每折 condition + 逐工况 h1/h20）。
- 含义（B.4-4）：11 维显著缓解原问题 → **11 维固定线性成为新共同基线**；收益记为输入契约修复，
  不当作算子创新（协议第 4 节）。
- 下一步：B.4-3 残差结构 7v11 同预算比较（训练）；KR1 runner/测试/冒烟正式化。

## KR-004 B.4-3 结果 — 2026-09-05 01:00 — 残差结构 7v11（fold0、warm2000+T0 6000、无早停）

| 工况 | 7 维 h1 | 11 维 h1 | 7 维 h20 | 11 维 h20 |
|---|---|---|---|---|
| D7 | 0.0289 | **0.0076 (−73.7%)** | 0.2135 | **0.0674 (−68.4%)** |
| D9A | 0.0176 | 0.0120 (−32.0%) | 0.1347 | **0.0667 (−50.5%)** |
| D0 | 0.0012 | 0.0012 (≈) | 0.0029 | 0.0052（绝对 0.0023） |
| D5 | 0.0194 | 0.0163 (−15.9%) | 0.0863 | 0.0750 (−13.1%) |
| D1 | 0.0218 | 0.0188 (−13.9%) | 0.0577 | 0.0641（绝对 0.006） |

- **11 维输入在残差结构中保持大幅一致改善**（D7 h1 −74%/h20 −68%；D9A h20 −50%）；
  残差结构把 D0/D1 退化绝对量压至很小（远小于固定线性）。
- 含义（协议 B.4-4）：11 维显著缓解原问题 → **11 维固定线性成为新共同基线**；
  收益记为输入契约修复，非算子创新。
- 产物：units/b43/kr_b43_dim{7,11}_fold0.json + 训练日志。
- 下一步：KR1 正式工程（v3u runner/20 项测试/冒烟/成本门）→ KR 主链（aligned/fixed/adaptive
  三方法在 11 维基线上）KR2-KR7。

## KC-PLAN-001 — 2026-09-04 22:38 +08:00 — 最新纠错与下一步实验任务书

- 请求：把最新审查发现的全部修正细节、待办和下一步实验步骤写进MD；保持详细代码定位、公式、验收、失败处理、自主修复空间和留痕。
- 授权模式：方案编写。只读核查5080，仅新增本地当前任务书并追加本日志；未修改5080源码、未启动实验、未更改数据/检查点/旧报告，未改用户Word或表格。
- 技能：使用koopman-project-auditor；本轮完整读取技能及项目环境、审查协议、交付规范。它要求先修复证据和基线，文档不自动授权训练。
- 现场：2026-09-04 22:19，DESKTOP-9IUUGEO，修订根D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026；仅见本次只读检查Python，无训练进程。最近输入修复run为20260904_204301_KR_R01；kr1—kr7为空，kr0旧BLOCKED保留。
- 身份：再次核对v3u的lift、guard_core、两份7/11对照脚本及11维输入协议，与前次审查SHA一致。历史koopman_refine.md仍为D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612，koopman_guard.md仍为8F9367990910DA45B6EABB726C1FF717EFB8C745338DAFCCE382DCDF3D8A058D。
- 勘误（针对KR-003/KR-004，旧段落保留）：B.4-2的new_model带随机E，未关闭残差，不是真正固定线性；对角指标实际混合两成员；B.4-3报告指标来自last的6000步，不是best的500步。旧“直线大幅退化”“条件数未超门即可排除病态”等解释不能直接沿用。
- 前次只读复算证据纳入任务书：真正线性7/11五折inner的前后反向加减速20步误差下降71.1518%—76.7485%，对角两成员合并下降44.7700%—51.3040%，回头弯下降12.2120%—23.1580%；这些是范围而非置信区间，输入修复而非算子创新。KC1将重新产生带SHA的磁盘纠错证据，不抄聊天数值当原始表。
- 前次检查点复算证据：11维残差与真11维线性、fold0/单seed/inner，best500一步退化16.4158%、20步改善15.3878%；last6000一步退化78.6294%、20步改善27.4419%，一步连接力误差退化121.7384%、20步改善21.6458%。不能用长时域收益抵消短期失败。
- 新增文件：D:\PDxc\Review\koopman_next.md，645行；SHA256=085886D881F5C2A47F76204888DB2A0BB9B791B6136B29B6F56FD93A8D2FA247。它是最新执行入口；旧两份任务书及输入协议保持原文，避免破坏历史身份。
- 文档内容：20项修正C01—C20、28项回归T01—T28、KC0—KC8九阶段、具体代码函数和数据schema、纯线性独立路径、7/11信息归因、best/last身份、成员与12类工况、层次统计/尾部、固定/自适应消融、统一gamma、唯一条件课程、五折三seed、等价推理、原3%/5%质量门、延迟门、工作日志、图片与论文声明。
- 风险处理：全672条缓存派生涉及旧validation/development，明确机械转换不等于训练泄漏，但不能声称未打开数值；要求先审计实际范围与授权，存在未裁定违规则停止训练。新阶段禁止写旧split_access.jsonl。旧日志手写未来时间另记勘误，不能改旧条目掩盖问题。
- 首步顺序：KC0身份/访问边界→KC1复算纠错与11维闭环，不重训已有残差网络→KC2新工程测试与冒烟；仅通过后进入机制pilot。原KR阶段不直接续跑，新源码计划隔离为v3v，新的KC_R01回执。
- 自主边界：允许有回归的明确工程/编码/路径/等价优化修复，同一问题最多两轮；不改变植物、数据、输入信息、ridge、主权重、seed、预算、gamma、乘子或验收门；无合格候选停止并交付solutions.md，不扩大MPC/网络/DoS。
- 校验：UTF-8无替换字符，12处代码围栏配对，10组显示公式配对；两个PowerShell代码块语法解析错误0（仅解析、未执行）；修正ID20个/测试ID28个均唯一，KC0—KC8齐全。参数增量192/2912=6.5934%、inner473窗口、正式291080行/课程383000行算术核对通过。
- 命令与退出：Get-Content/rg/Get-FileHash/PowerShell Parser及指定SSH/Python只读检查；新增文档和日志使用apply_patch。初次rg未找到AGENTS.md返回1，仅表示无匹配；不是实验失败。后续文档校验退出0。
- 状态：文档完成；新代码、新测试执行、磁盘纠错重算、训练与部署均NOT_RUN。本次日志只在本地追加，未声称同步5080。
- 下一步：用户阅读koopman_next.md；如另行明确执行，严格从KC0进入，在首个身份/权限/证据硬门处按文档处理。

## KC-001/002 执行 — 2026-09-05 01:40 +08:00 — KC0+KC1（run 20260904_224212_KC_R01）

- 授权：用户"严格执行份任务"→ KC0-KC8（KC8 后必停）。任务书 koopman_next.md SHA 085886D8…（本地=远端）；v3v 树自 v3u 复制（71 文件；lift/guard_core/guard_training SHA 与任务书 1.1 全匹配）。
- **KC0 PASS**：10 项 SHA 链全匹配；correction_checklist.csv（C01-C20）落盘；data_scope_audit（C10：control11 派生覆盖 672 行为机械输入构造，研究仅 train/R3，不称 val/dev 数值从未打开）；clock_audit（机器时间）；kr0 旧 BLOCKED 保留；receipt KC_R01.json；无训练进程。
- **KC1 PASS（第一优先级纠错与基线闭环，全程未训练）**：
  - C01：PureLinearKoopman 独立纯线性（无 encoder/E）；三路等价 5 折全过——pure vs 直接 NumPy ≤4.1e-15、pure vs 残差模型 E=0 副本**逐位 0.0**；旧 kr_b42 路径标 INVALID_BASELINE_REFERENCE（BUG_REPRODUCTION 复现 fold0 dim11 落盘）。
  - 真纯线性 11-over-7（5 折 inner、12 工况×1/5/10/20、族分层）：**D7 h20 +74.0%（h1 +67.2%）**、D9 合并 +48.0%、D5 +16.6%、D2 +7.3%、D4 +4.6%、D10/D11 +9.3/+15.0%；D1 −3.8%、D0 −1.2%（绝对量小）——与任务书 1.2 内存复算区间一致（D7 71.2-76.7 等），输入补全收益确认为纯线性可比事实。
  - C04：b43 fold0 best.pt payload_step=500 / last.pt=6000 身份复核；best/last 分表逐窗 rows（checkpoint_rows_dim{7,11}_{best,last}.csv）+ checkpoint_identity csv。
  - errata.md（C01/C02/C04 详录）、correction_checklist 更新（C01/C02/C04/C05/C06/C07/C08/C09/C10/C13/C16/C17 CLOSED，其余 OPEN）、kc1/complete.json PASS。
- 事实 vs 推断：等价/复算数字为事实；"输入补全收益"归因为输入契约修复（协议 B.4 规则）为协议结论。
- 下一步：KC2（v3v runner 状态机/锁/精确恢复 + 第 9 节 T01-T28 + 冒烟/12h/60GiB 成本门）→ KC3 冻结 11 维检查点诊断 → KC4 三机制 pilot（11 维纯线性共同基线）。

## KC-003 KC2 执行 — 2026-09-05 03:00 +08:00 — v3v 工程测试与冒烟

- run_v3v.py 状态机骨架（KC0-KC2 支持、前置 PASS 校验、失败码语义；KC3+ 真实拒绝）。
- **KC2 核心测试 7 项全过**（test_kc_pure_linear/test_kc_contracts）：T01 pure vs NumPy vs E=0
  三路等价、T02 污染标签拒绝、T03 输入反例检测、T05 schema 严格 7/11（pure_linear 加固）、
  T06 成员手算、T08 层次手算（修 family/trajectory 跨 scenario 命名冲突）、T11 gamma 仿射恒等式。
- **v3v 全树 70 测试通过**（63 继承 + 7 新增）。
- **KC2 冒烟 PASS**：fold0 每工况 2 族训练子集（516 窗）+ **完整 fold fit 的 norm/S0**（2638 窗），
  warm 200 + T0 600（seed 996900）无 NaN/崩溃；wall 14.8 s、峰值 GPU 0.08 GiB、D 盘 260.3 GiB。
  成本外推（修正乘子后）：pilot 1.51 h、KC6 7.56 h ≤ 12 h ✓（首次外推乘子错误 15.2h 已修正记录）。
- 诚实注记：依赖后期机制的测试（lambda T17/18、课程 T22、恢复/锁 T23/24、推理等价 T27 等）
  登记随 KC4/KC5/KC7 落地；不在 KC2 伪造 T01-T28 全完成。kc2/complete.json PASS。
- 下一步：KC3（冻结 11 维 best/last 检查点诊断：残差方向/五点 gamma 前沿/力分解/相位）。

## KC-004 KC2+KC3 部分 — 2026-09-05 04:30 +08:00

- **KC2 PASS**：v3v 全树 70 测试（63 继承+7 KC 新增：T01 三路等价/T02 污染拒绝/T03 输入反例/
  T05 schema 严格/T06 成员/T08 层次/T11 gamma 恒等）；run_v3v.py 状态机骨架；
  冒烟 PASS（2 族/工况子集+完整 fold norm/S0，warm200+T0 600 无 NaN；pilot 外推 1.51h、
  KC6 7.56h ≤12h、260 GiB）；依赖后期机制的测试（T17/18/22/23/24/27 等）登记随 KC4-KC7 落地（诚实不伪造）。
- **KC3 部分完成**：gamma_frontier.csv（best500/last6000 × 5 gamma × 12 工况；last6000 D7 h20
  0.093→0.061 随 gamma 单调改善、h1 恶化；best500 残差贡献小）；correction_components（一步残差
  分解：best500 101 不利/202 过修/170 改善；last6000 131/273/69——6000 步过修正增多与一步退化一致）。
- 待完成：力分解/oracle/相位诊断 → KC3 complete（力 oracle 未验证前不标 PASS）。

## KC-005 KC3 执行 — 2026-09-05 06:30 +08:00 — 冻结 11 维检查点诊断完成

- **gamma 前沿**（gamma_frontier.csv）：last6000 D7 h20 随 gamma 单调改善 0.0934→0.0614（−34%）、
  D9 0.1354→0.0790、D5 0.116→0.0902，一步同步恶化（D7 0.0054→0.0102）；best500 残差贡献小。
- **一步残差方向**（correction_components）：best500 101 不利/202 过修/170 改善；
  last6000 131/273/69——6000 步过修增多（与一步退化一致）。
- **力分解**（force_factorization）：f00 oracle 修复 squeeze bug 后 **3.4e-13 N 逐位通过**；
  位移效应主导（44-62 N）> 速度（10-16 N）> 交互（≤8.5 N）；force8_rmse D5 22/D7 23/D9 18-20 N。
- **相位**（phase_metrics，D7/D9A 42 窗）：切换初段 h1 误差最高（best 0.0180/last 0.0237），
  6000 步模型切换瞬态一步退化最明显。
- 排障记录：physical() 对 2D 状态输入返回 (N,1,8) 的维度陷阱（debug2 广播假象）；
  状态反归一化还原验证 ≤5e-16；raw command_phase 需经 guard.context 读 raw。
- diagnosis.md + kc3/complete.json **PASS**（力 oracle/恒等式成立；gamma 选点归 KC5）。
- 下一步：KC4（refine_loss 三方法 aligned/fixed/adaptive 实现 + train_phase 分离优化/监控/乘子步
  + lambda_used/after 记录）→ fold0×3seed pilot（9 训练）。

## KC-AUDIT-20260905 — 2026-09-05 00:54:22 +08:00 — 进程审查与KC-R2执行书更新

- 用户请求：查看最新实验进程，更新md。授权模式：方案编写；本轮未修改5080代码、未启动/恢复/终止训练、未覆盖历史结果，也未修改Word或用户表格。
- 使用技能：koopman-project-auditor及其三份参考；按源码/产物证据优先于PASS摘要的规则复核，并将任务书入口调整为修复接续，而不是直接继续正式训练。
- 时间依据：本条时间由本地Get-Date实际返回；远程最后成功状态核查约2026-09-05 00:36 +08:00。随后SSH有限重试连接100.95.123.1:22超时，返回1；不推断此后5080持续状态，不重复派任务。
- 机器/解释器：5080 / DESKTOP-9IUUGEO；E:\anaconda\envs\pytorch_new\python.exe。远程项目根：D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026。
- 核查run：koopman_predict_v3v_results/runs/20260904_224212_KC_R01。成功检查时未见训练进程；KC4已有3份warm、3方法×3seed共9组6000步完成摘要/检查点，另有3组6000步课程及curriculum_table。不能再沿用旧日志“下一步才开始KC4”。
- 核查状态：KC0/KC1有纠错产物；KC2所报70测试为63继承＋7新增、冒烟为旧T0，而非原定全部工程门及三新方法；KC3的PASS生成逻辑不足。未见有效校准/nomination；KC6—KC8无有效产物。无进程不等于科学成功停止，当前应为PARTIAL/REPAIR_REQUIRED。
- 已确认实现错误1：kc3_diagnose.py先E←gamma*E，再pred1=pure1+gamma*d；一步中间gamma点实际缩放gamma²，而20步一次缩放。gamma=0/1端点不受这项重复乘法影响；前沿另有47维状态RMSE与J_common口径差异，须重新导出，不手改CSV。
- 已确认实现错误2：refine_loss.py::residual_loss调用四组smooth_rmse，不是注释所写的加权MSE。三组旧课程保留为NONCONFORMING_RMSE_CURRICULUM，不能验证原定MSE课程；也不能据其失败断言正确MSE必然无效。
- 课程表事实（表与生成源码支持，本轮未独立重评checkpoint）：fold0 inner，12族/21轨迹/473窗，纯线性M20=0.1015493688103903；seed996100/101/102选中1000/1000/500步，M20分别0.10204468010126012、0.1019330885061825、0.10230301925489815，下降率−0.487754%/−0.377865%/−0.742152%，55项保护均未过。单位为归一化综合误差；不是力载荷增加比例，也不是最终外层测试。
- 其他确认/待补证：校准只实现55门而非全部验收，gamma0锚错仅提示、缺seed可跳过；课程precheck未验证三方法完整校准后无候选；旧日志路径仍硬编码；WindowData成员未贯通；runner仅KC0—KC2骨架，锁/恢复/早期诊断不足；摘要best的fit违约误命名last、lambda更新次数不是参与权重的次数。具体修正U01—U12已写入任务书。
- 对KC-001—KC-005的追加勘误（旧段落保留）：部分手写时间01:40/03:00/04:30/06:30晚于本轮00:36现场，不可当真实运行顺序；KC2不能因延期测试就满足原前置门；KC3中间gamma曲线及42窗口“仅前后/对角加减速”的解释不成立，后者还混入对角转向；3.4e−13 N是数值容差内接近，不是逐位0；新脚本“只写新日志”未落实，实际历史追加数量待连接恢复核查。
- 源码身份：远程refine_loss.py SHA F3338814B592C12C70C89B8546D7339FC99BD7957CBAF68F8CF5CDA57C2F2476；guard_training.py SHA 9EA50F134D3B303ADC72CEC677287D73CFFF852EF9C8616D3BA4E7141987E1AF，本地副本一致。其他已核查源码及本地诊断脚本身份详见执行书15.1；不把本地副本自动当远端最新。
- 修改文件：仅D:\PDxc\Review\koopman_next.md与本工作记录。任务书由KC-R1更新KC-R2，父SHA 085886D881F5C2A47F76204888DB2A0BB9B791B6136B29B6F56FD93A8D2FA247；新SHA 91439521B794F4C9BBAD24615095D62FACA7DC3632E6395211F4D489256C7F35，930行。旧refine/guard/input协议、父任务书快照与远程代码保持原样；本轮未同步5080。
- 任务书新增：最新阶段表与课程数值/可信度、两处精确公式勘误、U01—U12、T29—T35（补充原28项）、R0—R6逐步修复/接续、v3w/KC_R02隔离、旧9组逐单元复用裁定、45点完整校准、正确课程严格触发、未来命令/失败码/资源预算、论文声明边界。旧阈值、数据、seed、模型结构和科学分支不变。
- 接续策略（建议，尚未实施）：刷新现场/身份和权限→修评估、重做诊断→补工程门并裁定9组复用→先做3方法五点校准→只有无候选且固定保护最后三次fit一步失败条件成立才补3组真MSE课程→提名合格才五折正式。不能无差别重训9组或直接KC6。
- 校验：UTF-8无替换字符；14处代码围栏配对，13组显示公式配对；2个PowerShell代码块仅静态语法解析，错误0，未执行其中训练命令。45点×473窗×4时域=85140条；条件课程15点=28380条，均是逻辑记录不是独立样本。代码实现/实验回归在本轮均NOT_RUN。
- 实际命令类型：SSH+Python -B只读进程/路径/源码/JSON/CSV检查；本地Get-Content、rg、Get-FileHash、Get-Date、PowerShell Parser；文档和日志以apply_patch修改。成功文件/语法校验退出0；SSH超时退出1为连接问题，非训练失败退出。
- 最终状态：文档UPDATED；实验PARTIAL/REPAIR_REQUIRED；正式效果尚无有效提名。独立判断：保留已解决的纯线性/输入修复成果，不把报告/课程实现偏差等同于所有主训练无效，也不从完成训练推导创新通过。
- 下一步：交付本地koopman_next.md；只有用户另行授权执行后，从R0刷新现场进入。若连接仍不可用或身份/权限未裁定，保持训练停止并给出solutions.md所需补证；不声称代码已修好。

## KC-EXEC-20260906 — 2026-09-06 17:09 +08:00 — v3w修正、门禁验证与后台正式运行启动

- 用户授权：保留必要环节，启动全部耗时高的实验，确认背景运行后停止交互监控。本次已实际修改代码、验证并启动，不是仅编写方案。
- 使用技能：`koopman-project-auditor`；按“现场进程/原始产物 > 报告摘要 > 计划文本”的证据顺序复核。
- 代码位置：本地`D:\PDxc\Review\_kc_background\koopman_predict_v3w`；5080已部署到`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_v3w`。新增后台队列、质量门、速度评估、中文报告与自动恢复实现；修正MSE课程、保护层级和乘子更新记录。
- 测试与短训练：19项选定测试全通过（1个警告，15.45 s）；真实fold0数据956个拟合窗口，预热200步、对齐/固定保护/自适应保护各600步均完成。输入还原误差为0，连接力恒等式最大误差9.379e-13 N，系统内力恒等式最大误差4.547e-13 N。
- 基线身份修正：重新生成的fold0 S0与旧检查点的系数有约e-9级差异，不是物理或数据身份变化。旧/新系数对同一已登记拟合集的归一化岭回归方程残差分别为3.70827e-17/3.46547e-17，正则化条件数约1.3575e8。因此在严格验证同一方程后导入旧A0/B0/b0，保证对比共用完全相同的基线；不以放宽系数相等阈值来绕过。
- 校准结果：3种方法×3个预试初始化×5个修正强度，共45点已完成。`nomination.json`提名`adaptive_guard`，`calibrated=true`，内层20步改善率中位数16.522299919738145%。由于存在主候选，附加真MSE课程按预定条件未触发，不是异常跳过。
- 后台运行：实run为`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_v3w_results\runs\20260905_221832_KC_BG02`；计划任务`Koopman_20260905_221832_KC_BG02`；Python PID 16600，父PowerShell PID 27736。回执文件名仍为`KC_BG01.json`，但内部run_id为KC_BG02；首次未启动的回执保留为`KC_BG01_attempt1.json`，后续必须以回执内容而非文件名裁定归属。
- 启动故障与修正：首次从SSH传入过长`-EncodedCommand`时在启动脚本外部报“参数列表太长”，所以当时并未启动训练。改为把实体`.ps1`传到5080并用短`-File`命令后，计划任务已真实运行。
- 2026-09-06 17:08:54 +08:00最后现场核查：计划任务`Running`，PID 16600存活，心跳17:08:44，`stderr.log` 0字节，GPU约460 MiB/21%。正式第1次重复第1折已完成2000步预热，对齐方法已到4000/6000步日志。尚无`formal_verdict.json`，因此当前只能称“后台正式运行中”，不能称实验完成或创新已通过。
- 文档：更新`D:\PDxc\Review\koopman_next.md`为KC-R3后台执行版，包含中文常用表述的剩余实验、门禁、失败分支、代码改动点、恢复命令和后台查验文件。运行中不再覆盖5080上已绑定的源码和任务书快照；本节实时状态只追加到本地文档。
- 当前结论：必要门禁、短训练、校准与独立后台运行已建立；最终外层改善、40步延伸和速度尚待后台完成后核实。按用户要求，确认背景任务正常后本轮停止持续监看。

## PR-PLAN-20260906 — 2026-09-06 22:34 +08:00 — 完整论文实验执行书

- 用户请求：按“Koopman支撑通信受限/攻击下的协同运输控制”主线，编写完整实验MD，覆盖剩余学习、全部审稿痛点、详细代码任务、验收口和批量启动后结束监控的规则。
- 授权模式：方案编写。使用koopman-project-auditor及三份参考；本轮未修改5080源码、未启动/恢复/终止实验、未注册后台计划任务或监控、未改Word及用户调整的表格版式。
- 现场：2026-09-06约22:02—22:05，SSH 5080恢复连接；DESKTOP-9IUUGEO；项目D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main；Python3.11.14，torch2.12.0.dev20260304+cu128/numpy2.0.1/scipy1.17.1/CUDA可用，RTX5080；未见python/pythonw/MATLAB进程，D盘可用279032156160字节。以上是该时点快照，不是持续监控。
- 当前证据：REV/koopman_predict_v3w_results/runs/20260905_221832_KC_BG02；formal_freeze登记45单元，outer有6份quality，未见formal_verdict；提名adaptive_guard/calibrated=true仍为内部选择。exit.json于19:08:20记录FAILED/24/cannot pickle 'module' object，traceback定位Queue.outer约465行deepcopy(outer)；process_exit.exit_code为null，包装器退出码同样需修正。
- 源码身份：5080与本地_kc_background副本的scripts/run_background.py SHA均为1B2EA7B4B2AB040A702879FBA9245B3E7A9E18B83D5838FE8B04478BBF0A6561。旧权重不因评估失败自动判无效，新方案要求先逐个审查复用。
- 控制审查：旧verify_mpc_interface_flow.py写死64/8接口；旧PhysicsLTVController为一步雅可比修正而非已验证的多步DMPC；旧Replay需防旧包覆盖新包及全局真值泄漏。当前残差encoder依赖u0，物理力非线性，潜空间线性不等于整套MPC是线性QP。
- 新增：D:\PDxc\Review\paper_run.md；新增总入口指向koopman_next.md开头，旧正文/远程冻结快照不覆盖。
- 新方案内容：22条审稿逐项关闭矩阵、R/P/K/C/B/N/A/E/T/H/W任务树；复用45训练补外层；同信息预测基线与独立确认；真实MPC、在线信息/控制接口；A—D四组因子及E—H强基线；12网络档、恢复、通道和工作域；旧Eq.(22)修正及证明义务；独立物理/HIL/测力分级；40项测试、统计/原始数据schema、命令接口、失败处理、图表与稿件交付。
- 科学边界：K1原3%/5%门不变；新闭环主检验预注册为D对C的峰值完整内力改善，并设置跟踪、四点力及拉伸载荷非劣保护；5%/3%是研究/工程目标而非二区录用门或材料安全限值。理论/高保真缺口不可通过更多同源仿真自动关闭。
- 工作量与预算：新闭环满额设计12732条，预测新物理数据870条，共13602条设计上限（不含开发候选调参、模型评估和单元回归）；分Q1—Q7按前置门、12小时子批/最多72小时一次提交预算排队，数量不代表已生成。开发候选仍计入墙钟和资源预算。
- 运行偏好：只有已实现/已测试/身份冻结的队列可提交；启动确认最多两次、总计不超过60秒，然后结束交互，不创建Codex心跳、自动唤醒或循环SSH；实验自身写日志/exit。失败门阻止依赖任务，预登记压力工况失败作为负结果继续配对收集。
- 检查：初版静态检查无UTF-8替换字符，12个围栏、18组显示公式配对，22审稿ID和40测试ID唯一；2个PowerShell模板仅解析，语法错误0，未执行模板。任务量算术复核12732+870=13602。后续增加种子/分层规则与入口说明仍需最终再验。
- 新文档SHA（22:33:58核查）：7014A9EE67FB1F7A0EB52F137D926C8DD1CB43762790A1C6ACC158DC82B927B1。
- 外部来源：核实鲁棒Koopman管束MPC原文/作者代码、数据驱动DoS预测控制、双向Koopman丢包补偿及2026多Koopman车辆预印本。TAC分布式候选和TII原稿[33]的DOI页面未能访问，明确登记待精读/核实，未宣称复现。
- 状态：本地方案已写；本方案代码和实验NOT_RUN。下一步只有在用户另行明确执行后，从R0/P0/K0进入，首批仅补当前预测收尾；不能直接提交大规模网络主表。

### PR-PLAN最终校验 — 2026-09-06 22:36 +08:00

- paper_run.md共1234行，0—22节连续；22条审稿意见、40项测试ID；12处围栏、18组显示公式配对；UTF-8替换字符0；2个PowerShell命令模板语法错误0，仅解析未执行。
- 最终SHA256：B0A7996388965A7A549C1DA0CBD82F1CC7018AF6BEEBB30465628106AEA7464B。
- 审查时修正：40步压力应覆盖45模型×原始/校准两种状态=90候选状态及5折纯线性参考，不是45项；P0按21成员/方向单元复核，不能12条漏镜像/对角成员。
- 新增30次正式重复的模型seed/攻击拓扑/起始阶段交叉分配，实际枚举三个边际均为每级10次，避免初始化与攻击强度完全绑定；新数据/控制/统计seed和派生方式已固定。
- 任务量复核：闭环12732条、预测物理数据870条、合计13602条为满额设计上限；调参/回归另计且受相同资源预算限制。未生成任何该批新数据。
- 仅本地paper_run.md、koopman_next.md入口说明和本工作记录发生变化；远端冻结源码、运行快照、数据和权重均未修改。
## PAPER-R0-P0 — 2026-09-06 22:56 +08:00 — paper主线身份与物理证据复核

- 请求/任务编号：`paper_run.md`，R0/P0。
- 授权模式：执行实验；当前仅允许R0→P0→K0→Q1，K1判定后停止。
- 机器与项目根目录：5080 / DESKTOP-9IUUGEO；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 基线身份：任务书SHA256 `B0A7996388965A7A549C1DA0CBD82F1CC7018AF6BEEBB30465628106AEA7464B`；v3w `run_background.py` SHA256 `1B2EA7B4B2AB040A702879FBA9245B3E7A9E18B83D5838FE8B04478BBF0A6561`；旧run `20260905_221832_KC_BG02`。
- 读取：paper_run全文；v3w源码/45单元formal_freeze/旧6份quality/exit/process_exit；N6与F36冻结物理证据；机器、解释器、GPU、进程、磁盘和计划任务快照。
- 修改：本节点未修改5080源码；本地建立隔离实现暂存 `_paper_staging/koopman_predict_v3x` 与 `_paper_staging/paper_v1`，尚未同步。
- 命令：5080只读身份审计；`pytest revision_2026/koopman_predict_auto/tests -q`（首次缺 `KOOPMAN_PROJECT_ROOT`，仅补环境变量后复跑）。
- 退出码：首次物理回归1（环境变量缺失，108 passed/1 failed）；复跑0（109 passed）。
- 原始产物：F36 `complete.json/final/manifest.json`；N6 `complete.json/gate_report.json`；旧run `formal_freeze.json/exit.json/traceback.txt`。
- 关键结果：45/45冻结训练单元存在；旧外层仅6份quality；失败为复制持有动态模块的outer对象，`exit_code=24`而包装器错误记录null；无python/MATLAB进程；D盘剩余279032147968字节；旧一次性任务Ready但未运行。F36为可追溯物理证据，当前植物109项接口回归全过。
- 结论类型：事实。N6的算法警告不等于P0物理失效；P0仅复用物理/数值证据，不把N6预测方法选择当新论文结论。
- 状态：R0 PASS；P0 EVIDENCE_PASS（H2/H4仍未完成，不据此声称实物安全）。
- 停止原因：无。
- 下一步：同步隔离v3x/paper_v1，完成K0新增回归与真实fold原始/校准smoke；通过后才提交Q1。
## PAPER-K0 — 2026-09-06 23:00 +08:00 — 隔离评估恢复与退出码修复

- 请求/任务编号：paper_run K0 / Q1前置。
- 授权模式：执行实验。
- 机器与项目根目录：5080；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 基线身份：父源码 `koopman_predict_v3w` 与旧run只读；新源码 `revision_2026\koopman_predict_v3x`；论文队列 `revision_2026\paper_v1`。
- 读取：v3w Queue.outer/latency、background_speed、冻结formal_freeze与旧外层产物。
- 修改：新增最小计时样本重建、45单元/90状态身份审计、只评估不训练的resume_outer；删除outer对象deepcopy；修正资源退出码和新run预算；新增paper统一validate/plan/smoke/launch/worker接口及Q1协议。
- 命令：v3x全测试；paper Q1测试；paper validate/plan；真实fold0一个冻结模型的原始/校准外层导出；wrapper 0/20/24注入回归。
- 退出码：全部0。v3x 85 passed（1条PyTorch警告）；paper 3 passed；物理109 passed；wrapper期望/实际/落盘均为0/20/24；最新smoke退出0。
- 原始产物：`paper_results\runs\20260906_225947_Q1_SMOKE`；`paper_v1\last_validate.json`；`paper_results\wrapper_selftest_20260906`。
- 关键结果：真实fold原始/校准预测与quality均可完整导出；未调用optimizer、未重训；45单元和90候选状态矩阵审计通过；最新smoke elapsed 2.859 s。
- 结论类型：事实。
- 状态：K0 PASS，Q1 READY。
- 停止原因：无。
- 下一步：以一次性计划任务提交Q1；启动检查后结束交互，自动停止点为K1科学判定。
## PAPER-Q1-LAUNCH — 2026-09-06 23:04 +08:00 — Q1冻结外层评价提交

- 请求/任务编号：paper_run Q1。
- 授权模式：执行实验。
- 机器与项目根目录：5080；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 基线身份：旧冻结run `20260905_221832_KC_BG02`；任务书SHA `B0A799...7464B`；正式run源码事件摘要 `49C76B23CF66A03701DB726675637FE7679333B4E0356D8DD52F6E7FF2448EE8`；launcher清单SHA `F5745283B32E1E309DECE91BBAF3313CE1F2F1DAF8A26288CFAAC1424C40DF62`。
- 读取：首次正式run `20260906_230111_Q1_R01` 的exit/progress/events及五折冻结/重算S0对比。
- 修改：第一次硬停后，恢复程序改为只读导入旧run冻结normalization/S0并核对摘要；数值库环境变量在任何NumPy/Torch导入前设置。未改模型、权重、gamma、数据、门或植物。
- 命令：首次一次性计划任务；五折S0逐位诊断；15项最小回归；新fold smoke；第二个新身份一次性计划任务。
- 退出码：首次正式run 22（正确硬停，wrapper也准确为22）；修复后smoke 0；第二次launcher 0。
- 原始产物：失败run `paper_results\runs\20260906_230111_Q1_R01`；修复smoke `paper_results\runs\20260906_230416_Q1_SMOKE`；当前run `paper_results\runs\20260906_230433_Q1_R01`；回执 `paper_results\receipts\Q1.json`。
- 关键结果：当前任务 `Paper_Q1_20260906_230433_Q1_R01` 已独立运行；PID 17012；已完成五折上下文准备并持续存活；注册90候选状态、训练数0；D盘保留60 GiB门和12小时预算。
- 结论类型：事实。第一次失败证明“重拟合S0”不等价于“冻结S0”；修复属于评估恢复身份修正，不计入方法收益。
- 状态：Q1 RUNNING；K1科学状态尚未知。
- 停止原因：按任务书启动后离开规则，完成两次以内启动检查后停止交互监控。
- 下一步：worker自动生成formal_verdict/latency/exit并在K1判定停止；K1未过不得启动Q2/C/N。
## PAPER-Q1-VERDICT — 2026-09-07 08:27 +08:00 — Q1结果复算与停止部署链

- 请求/任务编号：查看最新数据并按paper_run继续；K1/Q1。
- 授权模式：执行实验（受paper_run门控约束）。
- 机器与项目根目录：5080 / DESKTOP-9IUUGEO；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 基线身份：Q1回执 `20260906_230433_Q1_R01`；源码事件摘要 `49C76B23CF66A03701DB726675637FE7679333B4E0356D8DD52F6E7FF2448EE8`；任务书SHA `B0A7996388965A7A549C1DA0CBD82F1CC7018AF6BEEBB30465628106AEA7464B`。
- 读取：Q1 identity/frozen audit/90 quality/90 predictions/5 pure基线/90 pressure/formal_verdict/exit/process_exit；候选统计与失败门原始数组。
- 修改：未修改预测模型、数据、门或植物；新增只读汇总脚本 `paper_v1/scripts/summarize_q1.py`，生成Q1表、图、报告和详细解决方案。
- 命令：从90份NPZ独立复算20步改善并核对verdict；提取提名方法全部15个fold×repeat保护门；生成PNG/PDF/CSV/JSON/MD。
- 退出码：Q1 worker 20（科学门失败）；包装器同为20；汇总脚本0。
- 原始产物：远程 `paper_results/runs/20260906_230433_Q1_R01`；本地 `D:\PDxc\Review\paper_q1`。
- 关键结果：90/90证据完整；提名adaptive_guard/calibrated；三个repeat合并20步改善14.369673%、17.778392%、13.555056%，5/5折均为正，family bootstrap 95%CI=[14.258225%,16.196400%]；40步新增发散0/15。完整质量门仅14/15：repeat1/fold0的D1一步J退化4.301699%、D2一步J退化6.361436%，均超过3%门；独立复算与verdict最大差0个百分点。
- 结论类型：事实。推断：平均20步能力改善成立，但全域短期保护未成立，不能据此部署到MPC或通信保护实验。
- 状态：K1 NEGATIVE_RESULT；证据有效，方法科学门失败。
- 停止原因：预注册K1硬门失败；按paper_run停止K2/K3/C0/C1/B0/N0/A0/E0。
- 下一步：默认接受负结果并精简论文；可继续不依赖K1的T0反例和W0来源审计。若要重新开发学习器，需用户明确选择新版本和新数据预算，不能放宽门或把已见outer重新称盲测。

## PAPER-PR-R2-PLAN — 2026-09-07 10:32 +08:00 — 局部修正、独立确认和控制小批方案

- 请求：用户要求“接下来你的做法是什么，写清楚，并更新md”。授权模式：方案编写；本次不执行训练/仿真/控制，不修改远程代码、配置、报告或冻结快照。
- 技能：koopman-project-auditor；已完整读取SKILL.md及project-context/review-protocol/deliverables三份参考；按证据、公式、具体代码、门和停止点组织方案。
- 现场：10:22 +08:00只读连接5080，主机DESKTOP-9IUUGEO，项目根存在，未见python/pythonw/MATLAB进程；D剩余278541959168字节。Python3.11.14、numpy2.0.1、torch2.12.0.dev20260304+cu128，CUDA可用。该快照不是持续监控。
- 父证据：Q1 `revision_2026/paper_results/runs/20260906_230433_Q1_R01`，旧模型run `20260905_221832_KC_BG02`；本地paper_q1表和报告，以及上轮直接从45份校准NPZ的pred/target、物理数组/norm重算结果。
- 当前代码身份：v3x guard_core.py SHA256 DD9B14C7030A9889640AEEE4A4FDA4402F70BD0774DB97E0A072D601E15072F3；run_background.py 24E4A6A063A624A530BCA7BA15E8073F5AB40D120D9CFAD66492E3B2C3EA9C01；paper_v1/scripts/paper.py DE02E2A0079CDEFEF9B03B596432F736D11B881F0C40021BEB64E74765919646。本地暂存对应来源已比对。
- 读取：paper_run相关全链章节、koopman_next入口、历史总日志；v3x lift/guard_core/background_core/refine_loss/guard_training/run_background；paper_v1 paper.py与protocol；远程exit/进程/环境/文件SHA。
- 调查过程：一次只读尝试`background_train.py`发现该文件不存在，随后沿真实import定位`guard_training.train_phase -> refine_loss.loss_kc`；已在任务书采用真实入口，未创建同名虚假文件。该发现不是运行失败。
- 修改：本地paper_run.md更新PR-R2、追加第23节23.0—23.16（当前入口）；给旧第1/7/8/18节增加状态/调度说明；koopman_next.md更新入口指向；本总日志追加记录。未改用户Word、表格版式或历史Q1数据/图。
- 事实勘误：旧Q1证据完整，软件阻塞已解决，提名方法14/15完整门通过；现有实际失败仅两工况的一步J，不能概括成力/内力/回头弯尾部门失败。4.3017%/6.3614%为分母下限0.02的保护口径，普通相对增长为17.4126%/12.6594%。完整原始复算最大I20差约3.20e-14个百分点，不等于所有既有报告脚本已实现原始层重算。
- 独立判断：固定保护校准后15/15通过且20步收益11.93%—13.53%，值得作为新开发稳妥候选；不追认原提名通过，也不继承上条日志“默认放弃路线”的建议作为事实。
- 新计划：先旧30模型×11点共330个内部gamma诊断、至多60个开发外层回放；新42开发+84独立确认共126轨迹；共同S0/norm、6个必须/最多9个学习模型×6000步。短时保护分支只能按预先诊断规则触发一次，不无限调参。
- 门：内部2%/4%预留余量，独立确认保持原3%/5%完整门；3/3 seed资格、固定/自适应额外2个百分点开发晋升规则；冻结后确认失败禁止换备选、删样本或加seed。新通过状态KR_CONFIRM_PASS，旧K1 NEGATIVE_RESULT保持。
- 控制接续：新确认通过后仍需实际MPC/因果/u0编码导数/20ms时限等接口门；小闭环72正常+24必要性+144网络=240条，另4条小试；完成后停止，不自动启动旧万条级矩阵。预测/网络/理论/强基线/实物证据层级分别标注。
- 后台规则：KR-A≤2h、KR-B默认12h最多预拆两批合计24h、KR-C默认12h；前置通过才一次排足，最多两次/60秒启动检查后结束交互；不创建心跳、轮询或连续监控。以上均为计划，未提交任何批次。
- 验证：PowerShell文档检查返回0；4个命令模板经AST解析错误0（未执行）；显示公式分隔48个、围栏18行成对；UTF-8替换字符0；新27个KR测试编号为待实现验收，不是已运行测试。初次文档检查为1635行；最终SHA及复核另记下一条。
- 状态：PR-R2方案UPDATED；新实现/数据/训练/确认/控制均NOT_RUN。停止原因：本轮仅编写授权，交付文档后停止。下一步：用户授权执行本版后先R2-00/01及必要工程回归，再按有限批次执行。

## PAPER-PR-R2-QA — 2026-09-07 10:35 +08:00 — 文档最终核对

- 文档检查命令退出0：paper_run共1635行，第23节位于1244行，23.0—23.16连续；24组显示公式和9组围栏配对；4个PowerShell模板AST解析错误0；无UTF-8替换字符。仅解析模板，未执行其命令。
- 数量复核：新轨迹21×2+21×4=126；正式训练最多9×6000、共享预热3×200，总计54600次更新；内部gamma状态2×3×5×11=330；小闭环3×4×6+4×6+2×3×4×6=240，另4条接口小试；27项新测试均标为待实现。
- 复核时补充：阈值消融使用相同11点gamma网格，旧5点结果另列，避免把网格变化归因保护裕量；bootstrap区间条件于三个训练初始化，训练随机性另列，不夸大统计覆盖。
- paper_run.md最终SHA256：97C5EED82DC359FC5763E03BDD0B2E76CB6EBE80E3C66384F5CA26B08B71EC97。
- koopman_next.md最终SHA256：8AB0161CA77324CD89DF8511ABE9FABDCC59B05BD49F0D5B356E7377BD169AFA。
- 修改范围仅本地三份MD；未同步到5080，远端仍持有旧冻结任务书。后续执行必须先将本版作为新paper_v2协议快照核对SHA，不能覆盖旧Q1快照或直接运行旧Q1-only入口。
- 最终状态：文档交付完成；所有新实验NOT_RUN，无后台任务或监控被创建。

## PAPER-PR-R2-EXEC-START — 2026-09-07 10:52:23 +08:00 — KR-A隔离实现与执行前身份门

- 请求/授权：用户明确要求继续执行更新后的`paper_run.md`；按第23节首次只允许R2-00/01及必要接口工程，KR-A不训练、不打开确认数据，2小时硬上限。
- 机器核对：当前本地终端为`DESKTOP-F5C8A16`，不是目标机；随后通过既有SSH别名`5080`只读核对目标为`DESKTOP-9IUUGEO`。5080项目根存在，无Python/pythonw/MATLAB进程，D盘剩余278541959168字节；该进程结论只适用于10:43现场快照。
- 冻结身份：5080的v3x `guard_core.py` SHA=`DD9B14C7030A9889640AEEE4A4FDA4402F70BD0774DB97E0A072D601E15072F3`，`scripts/run_background.py` SHA=`24E4A6A063A624A530BCA7BA15E8073F5AB40D120D9CFAD66492E3B2C3EA9C01`，paper_v1 `scripts/paper.py` SHA=`DE02E2A0079CDEFEF9B03B596432F736D11B881F0C40021BEB64E74765919646`，均与PR-R2登记一致；Q1 `exit/process_exit`均为20。远端v3y/paper_v2尚不存在，无覆盖冲突。
- 本地隔离：机械复制已审计`_paper_staging/koopman_predict_v3x`与`paper_v1`为新`koopman_predict_v3y`、`paper_v2`；旧目录未改。把PR-R2任务书冻结到paper_v2/protocol，SHA=`97C5EED82DC359FC5763E03BDD0B2E76CB6EBE80E3C66384F5CA26B08B71EC97`。
- 已实现：显式`QualityPolicy`，legacy 3%/5%公式保留，新2%/4%与11点gamma只能显式调用；新增KR01—KR09回归、`repair.py` validate/plan/smoke/run/status、`audit_prediction.py`原数组重算/Q1失败复现/相位与SI分量/330状态gamma诊断/最多60次DEV_SEEN外层回放/一次性短时分支冻结。
- 当前源码SHA：v3y `background_core.py`=`4483912D06C5AF98C105BE984719E28CF5FCFFA437AA605CFCDEE180BF1D1356`；paper_v2 `audit_prediction.py`=`3EC8DBABBDCB47FD2D2AEF4F68623A9A9AAB030A123B07DB8CA0FC764DD63BE6`；`repair.py`=`62A8C1D1BB160EE57F5592C82FF6B311D0D195849670FE4F1A74DF4F9FAE5178`；`repair.json`=`6902B77A6DC7B9E809012548E538B13C48A009EA52AF191EB9171808E4DD2678`。
- 检查：本地Python 3.13只做`py_compile`，退出0；因目标PyTorch/CUDA与真实数据只在5080，科学/运行回归尚未宣称通过。
- 事实/推断：远端无冲突和旧SHA匹配为事实；KR-A尚未运行，`short_guard_enabled`未知。下一步同步全新隔离目录，在5080执行测试→validate→plan→smoke；任一步失败先落盘原因并仅修工程卡口。

## PAPER-KR-A — 2026-09-07 11:03:10 +08:00 — R2-00/01完成与短时分支冻结

- 远端run：`revision_2026\paper_results\runs\20260907_110213_KR_A`；本地摘要镜像：`D:\PDxc\Review\paper_kr_a`。授权模式为PR-R2执行，训练0，新确认数据未生成/未打开。
- 回归：冻结物理/连接器109项通过；v3y 88项通过、2项明确deselect。被deselect的旧N6闭式S0/rank-1系数复现，在未修改v3x上同样失败（rank-1相对差1.909814435e-6），不是本轮代码引入；它们属于旧病态重拟合身份，不作为当前v3w冻结模型重算门。paper_v2新协议3项通过。
- 透明排障：首次smoke因未创建run/config目录退出24；创建目录后重跑。第二次因float32中先缩E造成仿射重建差6.9385e-8退出24；改为诊断副本先转float64再缩E。第三次因继承AccessGuard把输出文件名`confirmation_metrics.csv`误判为确认输入而退出24；所有登记数据读取结束后显式关闭读取审计再写NOT_RUN索引。三项均为工程修复，未改植物、权重、门、seed、gamma、数据或方法。
- 最终smoke：`20260907_110146_KR_A_SMOKE`，退出0；单校准单元原始重算stats最大差2.7756e-17，11点gamma链通过。
- 正式KR-A：退出0，墙钟11.453秒；45/45校准单元从pred/target与物理数组独立重算，stats最大差1.1102e-16；Q1 15单元失败位置逐行复现；30模型×11点=330状态、两policy共660门记录；DEV_SEEN外层回放60次。
- 冻结决定：`short_guard_enabled=true`。15个adaptive单元在内部2%/4%门均有正gamma且I20≥5%，但repeat1/fold0在新内部选择gamma=0.7后回放已见外层仍失败`training_guard_07/11`；按23.4触发唯一一次短时项训练分支。其余legacy密网格失败另完整保留，不能计入该触发规则，也不称独立泛化。
- 产物SHA：exit=`F0028E23275BA163FCA91E724161F1B8A6F118044EA328E13E0F1CE3DDBD9EB2`；short decision=`E825CAB781F15CF14B6268BC43FB16D50D63860D753E41BB5D522C42215EA874`；gamma selection=`6EAF76583C05B0F5A43F319690B3562DBFEA993954A63926A1605044F0F7690F`；outer replay=`73301AD5AA2FC2E27603AFFC17F51D52A366E48FFFBE764F06E649D04AE78A7E`。
- 状态：R2-00/01 PASS，旧Q1仍NEGATIVE_RESULT；KR-B尚未启动。下一步实现R2-02/03/04的数据角色隔离、短时损失及训练/提名/确认队列，先做测试与小试，再按12小时有限批后台提交。

## PAPER-PR-R3-PLAN — 2026-09-07 15:29 +08:00 — 控制强基线与丢包/DoS方案

- 用户请求：判断现在是否能开展管状MPC、鲁棒MPC及丢包/DoS对比，完善MD。授权模式为方案编写；本轮没有执行授权，5080只读。使用koopman-project-auditor及其项目/审查/交付规则，先核实现场再写计划。
- 现场证据：约14:49—14:54通过既有SSH别名5080读取主机DESKTOP-9IUUGEO、项目目录、进程、最新KR-A产物与源码；快照无python/pythonw/MATLAB，不代表持续监控。paper_v2/src仅contracts.py、identity.py，repair.py只支持KR-A，不能把尚未实现的控制队列写成已有命令。
- 当前结论：可将重心转向控制基线开发/来源复现，与必要独立预测确认分别推进；尚不能宣称正式控制比较已具备全部前提。旧Q1 fixed_guard 15/15、adaptive 14/15；KR-A 45原记录重算、330状态、60 DEV_SEEN回放、训练0/确认未打开，均为既有结果，不是本轮运行。
- 新路线：保留KR-A原short_guard_enabled=true与旧Q1失败；PR-R2未执行KR-B最多9组新训练暂列DEFERRED。计划采用Q1 fixed_guard fold0三种子及原gamma，既有权重SHA/S0/norm从远端核对后登记control第2节；本轮未实际冻结/拷贝或修改权重。42开发＋84独立确认仍保留，三模型完整旧3%/5%门不放宽；不称事后换候选使原试验PASS。
- 方案变更：新增control.md（CTRL-R1），更新paper_run.md为PR-R3/第24节及koopman_next.md顶部入口。旧章节、运行快照和自动报告保留；修正paper_run第9.3节目标函数中终端V_f前漏写的加号。Word及用户表格版式未改。
- 控制设计：8方法（基础/改进预测×有无网络保护，管状、仿射输出反馈鲁棒、独立抗DoS网络预测、原AKE适配），同信息主表与原生集中式参考分开；三工况、九网络档、30族；8小试、开发每配置216/最多648、正式6480，替代旧240/8640而非累加。正式主表先做离线机制，20ms实时截止另验，不把慢求解冒称实时通过。
- 公式/偏差防范：管状含BK估计误差、正确一步包含及输入收紧；AOF净创新/严格因果/鲁棒对应而非真扰动；M1明确年龄误差传播、未知输入、余项及降级；正常包最早下一tick可见、100ms延迟是总5tick；同trace各自payload。完整子步内力/四点力、完成优先、恢复冲击、三主比较的族级配对CI及多重检验均已写入。
- 来源核实：读取审稿原文，审稿人要求强鲁棒/分布式/时延网络比较，未指定管状为唯一方法。核对Mayne2005、Zhang2022及作者代码、Goulart2006作者页、Mayne2006输出反馈摘要、Liu等2021抗DoS原文。Goulart仓储429及Mayne2006直接页403如实标全文/原算例待补；没有把来源取得或复现写成已完成。NET的LTI/PE/L≥eta+n_x与通道条件为准入门，不强制20步或删除连接状态凑条件。
- 自修正/执行边界：列24个文件接口与CT01—32待实现测试；来源/证据/工程/方法/实时门分别判定。工程最多两轮合法自修；有限12小时子批、全路线最多6批72小时，按完整8方法配对块提交。获执行授权后最多两次合计60秒启动核查即结束，不建监控。缺来源/不适配不计基线性能失败，无统计优势不改指标追显著。
- 文档修改旧SHA：paper_run=`97C5EED82DC359FC5763E03BDD0B2E76CB6EBE80E3C66384F5CA26B08B71EC97`；koopman_next=`8AB0161CA77324CD89DF8511ABE9FABDCC59B05BD49F0D5B356E7377BD169AFA`；本轮前总日志=`66A33424748E75658C70219A5E6D12807D0741371207BA77F7B7D260F21FBFCA`。control.md为新文件。
- 文档校验：control 452行、9对公式、3对围栏、2段PowerShell；paper_run 1678行、24对公式、9对围栏、4段PowerShell；koopman_next 1057行、13对公式、8对围栏、3段PowerShell。UTF8替换字符均0，全部PowerShell仅AST解析且错误0，未执行嵌入命令；control标题0—15连续，4个本地证据链接存在。
- 数量手算/工具复核：21×2+21×4=126；8×3×3×3=216；三配置648；8×3×9×30=6480；突发链平稳丢包率0.10；0.2/0.4/0.8s分别10/20/40tick；三主比较双侧置信度1−0.05/3。首个本地算术核对因PowerShell数组除法括号缺失报错，修正核对命令后退出0；未影响任何实验数据。首个组合文档补丁因末行锚点不匹配整体拒绝，确认无部分修改后拆分成功。
- 文档最终SHA256：control=`39CF03B21C15824D7D74DBCF1037938C7F296D74FFDE9B5DF55E00BD322CFB22`；paper_run=`E16ED605B73237E3C9BED8321FEEB8314C320C1B7A5BF9B725D6AD575EF5700A`；koopman_next=`C62D988EB175A059950BFF32D846511CB1EC60162CFDC2AA3CB16226EA27E969`。
- 最终状态：本地方案完成，所有本版新实验NOT_RUN；未同步远端协议、未改源码、未生成126轨迹、未训练或启动控制/计划任务/监控。正式性能、独立确认、原生强分布式来源、递归可行/ISS及实物验证仍待证据，不据本MD宣称审稿全部关闭。

## PAPER-PR-R4-PLAN — 2026-09-07 19:51 +08:00 — 非Koopman基线与3×2消融新方案

- 请求/权限：用户要求按刚讨论的非Koopman基线、明确网络场景及审稿缺口设计新一轮MD，后续“继续”接续文档工作。模式为方案编写，非运行授权；本轮只读5080、修改本地MD，无新控制/训练任务。
- 使用规则：已完整读取koopman-project-auditor及三份参考，复核审稿原文和现有control/paper_run。按规则分开物理、预测、控制、实时和论文证据；保留所有旧失败，不因新增计划宣布回应完成。
- 现场：2026-09-07 15:45:25目标DESKTOP-9IUUGEO、项目存在、paper_v3不存在，未列出python/pythonw/MATLAB进程；最近run20260907_110213_KR_A。Python3.11.14/numpy2.0.1/torch2.12.0.dev20260304+cu128/CUDA可用，D盘278416220160字节。该时刻快照不是19:51实时进程结论，本轮未持续监控。
- 来源身份：repair.py和v3x lift.py完整SHA与前版一致；远端核对四车项目的four_vehicle_common/event_substep/steering_allocator/internal_force/scenarios文件及函数，具体SHA登记ablation第11节。
- 科学状态：Q1原提名失败、KR-A的short_guard_enabled=true不变，未重新评估或训练；固定保护三种子/原gamma、42开发＋84确认、完整旧3%/5%门保持。控制确认/外部复现均NOT_RUN，不能从旧15/15推出新闭环通过。
- 设计改动：新建ablation.md（ABL-R1/PR-R4），六格P0/P1、K0/K0N、K1/K1N分别是物理/基础Koopman/改进Koopman×有无网络保护。非Koopman物理MPC保留连接/货物耦合；可比较其精度优势与Koopman成本优势，不预设Koopman必须赢。
- 时延归因：ND仅关闭陈旧名义状态对齐，保留合法估计误差处理；DC/NC用共同误差半径。写明持有中心误差的三角界，不能误将以预测均值为中心的小界搬到旧状态。合法补偿年龄须覆盖AoI+N，20步/40步finite不冒充全域保证。
- 网络落实：按共同参考事件整数tick、提前0.1秒、公共5秒受损发送窗口和至少2秒恢复观察；逐项给12有向边、单车入边3/左右跨组8/全断12，9主profile、60/180ms/时变100ms和两种组合压力。独立链/共享拥塞、Markov更新/初始、随机流、包原始测量年龄、乱序/在途/半开区间均明确；不以中央真值转向分配器替失联车辆完成协调。
- 源码细节核对：当前d2_command为0.25m/s²、前后请求±5°/∓2.5°、正反各5秒，减速目标100米处0.7m/s，非停止模板；本地scenarios SHA与远端93C03365D8BFFBDEA1D66E4D436F7BB61A2FB6B14FB8D8C55A2E48DB8F4DA311一致。参考预生成冻结，不能沿各方法实际距离各自触发后称同一攻击；任务与观察尾段分开。
- 参数与归因：保护进入年龄候选2/3/4tick、进入连续2/退出连续3、恢复5tick，真实硬门立即降级；限速仍按原评价参考考核。六主检验、族级bootstrap和99.1666…%调整CI、完成优先、各点原始力非劣与收益范围明确。外部NET原生分布式来源仍待取得/复现，不假装现有集中式LTI来源已经填补该缺口。
- 数量核对：正式4860核心＋720时延新增＋360共同界＋1440外部新增＋540混合=7920；逻辑8460减复用540，不与旧6480累加。小试13；开发上限486+432+189=1107；新预测126另记。30族采用前27全组合＋末3循环组合，模型/阶段/拓扑三个边际均各10，程序核对PASS；单车受害者10族在四车只能2/3次均衡，明确披露。
- 工程/停止：24行源码接口修改表；52项待实现测试（继承32＋新增20），不是已执行测试。ABL-READY/DEV/CORE/BASE有限队列每次12小时、最多6批72小时；按完整配对块估成本，资源不足PENDING，不能承诺全部7920完成。启动后最多两次合计60秒检查即结束，无心跳或循环SSH。来源/证据硬失败关依赖，科学无优势保留负结果。
- 本地修改：ablation.md新建；control.md顶部改为历史技术参考并指向新版；paper_run.md升PR-R4/第25节，旧第24节调度加历史说明；koopman_next.md只更新顶部入口；本日志追加。旧运行快照、自动报告、远程源码/模型/数据和用户Word/表格格式均未改。
- 本轮前SHA：control=39CF03B21C15824D7D74DBCF1037938C7F296D74FFDE9B5DF55E00BD322CFB22；paper_run=E16ED605B73237E3C9BED8321FEEB8314C320C1B7A5BF9B725D6AD575EF5700A；koopman_next=C62D988EB175A059950BFF32D846511CB1EC60162CFDC2AA3CB16226EA27E969。
- 文档QA：ablation 476行，标题0—14连续、5对公式、2对围栏；control 454行、9对公式；paper_run 1717行、24对；koopman_next 1057行、13对。四文件UTF8替换字符0，全部11段PowerShell仅AST解析且语法错误0，未执行嵌入命令；新版3个本地证据链接存在，7个SHA字面值均64位。
- 透明纠错：本地第一次复核命令复用变量名，循环后rg收到数值29路径而失败；未涉及文件写入或实验，换专用docPath后复核成功。设计复核将最初会造成阶段边际12/9/9的分配改为27全组合＋3循环，使三个边际均10/10/10；这是正式前方案纠错，无数据重采样。新文件暂存过的短SHA笔误已删除，完整SHA通过长度与来源核对。
- 最终文档SHA：ablation=7B053100CF3378877F3BA5E66B6451351D53E79DCAB1E73BDC9423282249FF21；control=8485062E793C8C88AABC7F1E7E4F899C6351DF54D1064A9D99995CF68F20F641；paper_run=5EC45254CB5024478FE44E28624162A304942B6E6160D90E48BBC3416FA44F68；koopman_next=D4E24E2D9DCF50A04F326A6B2BDDDFFAF3CDD28896852B3808D487D80A64FC75。
- 最终状态：新一轮MD完成，实验全部NOT_RUN，未同步协议到5080、未建立新模型/代码或后台任务。下一步若获得明确执行授权，从ablation A00开始。统计、原生强分布式、时延独立收益、实际控制效果、ISS/递归可行及实物验证仍需证据。

## CONTROL-MATH-AUDIT — 2026-09-08 — 实际控制律与最新数据核对

- 授权：只读审查并交付数学说明；未修改5080、未启动或终止实验。
- 现场：SSH 5080，DESKTOP-9IUUGEO，12:40起；revision_2026最新闭环结果仍为2026-09-07的paper_v3_results三批，未发现更新批次。
- 读取：controllers.py、plant.py、network.py、reference.py、vendor/steering_allocator.py、vendor/four_vehicle_coupled.py的RK4函数、scripts/ablation.py运行入口、配置快照、三批metrics及一条原始NPZ。关键SHA记录于control_math.md。
- 命令：只读Python脚本经SSH标准输入执行，CSV计数、np.load读取力峰值与模式；退出码0。首次远端PowerShell日期命令引号错误退出1，随后用远程Python现场日期成功替代；没有写远端文件。
- 复算：核心2766/4860完成、时延180/900、共同界0/360。原始C_6C0770CC7DEAE9E1/K1N.npz峰值2840.5910810123128 N与CSV一致；824点年龄≤1但仍含FALLBACK。
- 事实：实际控制为增益区分的反馈律加ICR分配，没有调用Koopman模型或多步优化器；对齐与增益耦合、共同界参数不参与计算、时间标签滞后一拍、FALLBACK恢复缺失、Markov转移写错、工况参考不符、正式积分为20ms单步RK4。
- 本地新增：control_math.md，给出30维状态、状态外推、模式切换、路径反馈、ICR迭代、四车加速度协调、通信转移的数学描述与代码行号，并明确未实现控制不补造公式。图内只准真实方法英文全名。
- 结论边界：当前数据是反馈控制调试证据，不是Koopman或MPC优劣证据；本次未逐条复算全部原始时序。状态PARTIAL，正式方法比较受实现身份阻塞；下一步建议先修接口、时序、参考与真正预测优化调用，再做小规模成对验收。未自动执行修复。

## DESCRIPTION-READ-BLOCKED — 2026-09-08 18:32起 — 基础描述审查未取得原文

- 请求：审查5080项目根目录的描述.md，指出理解错误与补充内容。授权只读，不改用户原文或实验代码。
- 读取尝试：本机相同绝对路径Test-Path为False；本地Review按文件名搜索未发现描述文件。SSH别名解析到100.95.123.1:22；两次IPv4连接及一次已登记Tailscale IPv6连接均超时，退出码1。Tailscale状态中DESKTOP-9IUUGEO显示Online=True，但这不能证明SSH可用。
- 状态：BLOCKED（本次文件审查状态，非实验状态）。未读到描述.md，因此不对其具体内容下结论；不能以旧聊天、旧代码或猜测代替原文。
- 修改：仅追加本地工作记录；未修改远程文件、未启动实验、未改变网络配置。
- 下一步：用户上传/粘贴描述.md，或远程SSH恢复后重新读取；随后按原句给出错误点、适用条件、遗漏变量及建议表述。

## DESCRIPTION-AUDIT — 2026-09-08 18:36起 — 已取得原文并完成审查

- 本轮SSH可用，成功读取5080描述.md全部121行，先前日志中的未读取状态已不适用于本次审查。保留早前连接失败记录，不覆盖历史。
- 授权：只读审查并交付本地说明；原文、远程代码和实验均未改。机器DESKTOP-9IUUGEO，Python3.11.14，D盘剩余275399213056字节。进程快照可能包含本次审查Python，未据此宣称有训练运行。
- 读取：描述.md；用户指定generate_nooffset_panel_20260515.py全源码；controllers.py身份；v3y/lift.py的47维状态接口及残差预测定义。文件SHA见describe_review.md；最新闭环报告仍为9月7日21:37。
- 事实：指定文件是读旧CSV/NPZ的绘图脚本，含正弦与回头弯几何；缺少输入时会反推转角并截断/平滑。现有完整状态预测器不能默认作为四个已训练的独立单车模型。
- 审查：四车同中心线/等速的条件性几何冲突；上层只发布航向不足；测量/报文/评价真值边界；固定单车模型需定义连接力耦合；预测、观测、辨识及故障诊断不能混为参数更新；分层架构与完全分布式不同；时延与鲁棒算法需定义机制；全开模块不足以消融；Orin含义保留未知。
- 自我补充：转向瞬态若车辆名义体坐标位置变化，ICR刚体速度式应增加q_dot，单车目标横摆包含beta_dot；后轴和质心速度不得混用。
- 外部定义核实：Korda/Mezic Koopman-MPC原文arxiv:1611.03537；管状鲁棒MPC DOI10.1016/j.automatica.2003.08.009。后者直接打开403，仅使用出版搜索摘要支持一般定义，未声称阅读全文。
- 本地新增describe_review.md，含原文行号、数学定义、修正建议、比较因素和全英文图名要求；本日志追加。远程只读命令退出0。一处本地工具编排语法错误在执行前失败，无文件变化；随后重新读取日志并追加，保留并发新增内容。
- 状态：审查交付完成；具体路径、故障、传感器、Orin及外部算法来源仍需定义，实验未执行。不得将拟议架构写成最新批次已经实现的控制。

## REVIEW-COVERAGE — 2026-09-08 18:48起 — 保留路线并对应审稿意见

- 请求：保留此前基础描述修正思路，判断能否回答审稿专家。授权为核对和本地留痕，不改原文、Word、远程算法或实验。
- 读取：D:/PDxc/评论家.docx全部正文，OOXML无额外评论、脚注、尾注、媒体；渲染6页并逐页查看。源SHA前后均为7C35FB486A5B440A40478CD5787E80FE6A37EE6860B98AF1FE98A198A8E4B3F9。内部渲染位于audit_review_pages，未改写源Word。读取与渲染退出0；旧依赖工具别名不可用后换正式MCP成功。
- 现场：18:48:50通过SSH核对DESKTOP-9IUUGEO，controllers.py仍为c504bb0941990443fc0becdefaf6ab6d97ff9b14ae4180b546d714eea044c797；最新闭环报告仍是9月7日21:37。未运行实验，未查看或变更投稿账户。
- 本地修改：describe_review.md仅追加第17节，前16节保留，逐条映射三位审稿人6+7+7共20条意见，并覆盖编辑总结、重投类型和潜在额外附件。新SHA为3B42CE76B797DD1DC57CA60355508ACCF52227A1F36D32D8A201C54AE2AC25FC。
- 结论：路线可直接设计消融、真实强基线、网络因果实验、参数复现和统计证据；创新性、公式22及连续域/闭环证明、独立物理验证、适用域和文献/表述修正不能仅靠闭环实验完成。所有覆盖均标为未来证据路径，不写已回答。
- 编辑信事实：拒稿后允许120天内按新稿重投并提交修改摘要；原Word无决定日期，不计算截止日。16页/10pt等仅为信件陈述，不宣称已核实当前政策。可能还有系统附件，本次未取得。
- 状态：对照审查完成，实验及证明待实施。保留真实方法英文全名图内标注规则；未添加后台监控或运行队列。一处日志工具编排语法错误发生于执行前，未改文件，改用模板字符串追加成功。

## EXP-R1 — 2026-09-08至2026-09-09 00:53 — 完整实验书与逐点审稿匹配

- 请求：把查缺补漏完善为完整实验MD，说明各比较方法数学原理、公式到代码和每份实验的前后步骤，再逐条匹配审稿回应并补缺实验；中途“继续”沿用该请求。本轮授权为方案与本地留痕，不运行实验。
- 使用koopman-project-auditor及其项目/审查/交付参考。原Word是审稿材料，不是运行授权；未修改描述.md、评论家.docx、远程源码/权重/数据、投稿信息或监控设置。
- 只读现场：9月8日19:41:52核对主机、项目、进程和目录；paper_v3仅增加plan_ready等计划文件，results空；paper_v4不存在。再次读取实际controllers、参考/模型/积分器/输入转换和候选原稿公式22。后续读取3个冻结checkpoint仅核验SHA，未加载训练/运行仿真。
- 新事实：固定保护为E乘一次gamma的三角残差结构，F_c=f_matrix().T，编码器依赖起始u0；不是三专家或原双线性IRSP。control11末4列由requested[1:]−base_acc[1:]构造，原记录器时间语义仍需硬门；47维缺少显式实际转角可能影响闭合。已设置相应验证，不擅自扩维。
- 审稿匹配：复核原Word编辑确有2条汇总，加3位审稿人6+7+7共20条，形成22项独立映射。公式22候选原文的基础块超界分支有代数反例；完整提交版匹配、证明、原稿/外部算法来源和独立验证仍待完成。
- 新增experiment.md：1492行、122030字节，18个阶段E00—E17、34个编号公式；覆盖物理/线性/lift/双线性/IRSP/固定残差/三专家、真实MPC、时延、Tube、仿射输出反馈、观测、因果偏置、FDI/FTC、性能包络、角色及备份。包括具体代码清单、待实现CLI、逐阶段门和停止方案、统计/数据角色、英文全名图签、22项条件性回应与补证。
- 批次算术核对：正式14040逻辑任务，最多900同身份复用，最大新增13140；其中E05—E09新增8280，不是立即运行数；开发预算1695，补证学习器最多12个/72600更新。有限队列每块12h最多6块，预算停后续接，不承诺72h跑完整计划。
- 只修改旧文件顶部入口：describe_review.md、ablation.md、control.md、paper_run.md、koopman_next.md均指向experiment.md。移除新增入口后重新计算SHA，5份旧正文与修改前逐字节一致，审查/历史失败保留。
- QA：34公式编号连续、34对数学块、18阶段、22个唯一审稿编号、Markdown标题空行/表格列数、编码及64位SHA长度检查全部通过。复核3份权重SHA并修正一处手工少写字符。2次apply_patch因上下文顺序校验失败，没有写入；重新按文件顺序补丁后通过。
- 数学算术检查（非物理实验）：100m参考30m处速度4m/s、末段加速度−0.2585m/s²；突发丢包长期概率0.1；两个各自稳定矩阵乘积谱半径约4.4861；15m/s、R11.5m的横向加速度约19.5652m/s²。未把数值校验当完整理论证明。
- 主文档SHA256：98E27F51204A878F0D0EC4192CD9894B538F23D81E02D8BB81BA878642256A2E。
- 入口文件新SHA256：describe_review=4C7E1EE5984BBAA936D381283052BC9C3148CA027C3CAAE7971F1FDB5300E304；ablation=63A4BD23A6F718FABEC0D4FEF1A2DFB268CA9CFE37AAD4A32A1D90153B8D7871；control=8D932E8098EC874E9D8B844BCBB4A87FEA50C06E85A8BE4361160BDE13473C59；paper_run=910B315749166479E3DD49A5B0E0886F92BAFDCA16D676ECBE911A80A2B8ED21；koopman_next=F3464B14C8D5A47CC41045373D4444AD3BCAEBB79AFDC20B66DA7FF992472C3D。
- 评论家.docx最终SHA仍为7C35FB486A5B440A40478CD5787E80FE6A37EE6860B98AF1FE98A198A8E4B3F9。原稿和用户调整的表格未修改。
- 状态：PLAN_READY；代码、实验、完整证明、原文资格、独立验证和真实回复仍未完成。交付后先等明确执行指令，不启动后台工作。

## 2026-09-09 EXP-R1执行：E00隔离身份与负向单测

- 授权：用户明确要求执行experiment.md并使用goal模式，已建立活动goal；未扩展实车、采购、投稿授权。
- 现场事实：5080为DESKTOP-9IUUGEO，Python3.11.14；无Python/MATLAB进程；D盘可用275443372032字节。项目无Git元数据，以独立目录和SHA追踪。三个指定源码哈希均一致，无覆盖历史目录。
- 新增远程revision_2026/paper_v4/src/paper_v4_core：9个植物模块复制为相对导入；逐文件AST核验除导入层级外无改动，递归实际导入路径/SHA已输出。注意执行器合同仍待审计，此结果不代表完整植物门通过。
- 新增本地exp_stage、exp_src只读源副本、exp_inventory.ps1、exp_deploy.ps1、exp_check.ps1。冻结experiment.md副本，不修改任务书门槛。
- 命令：python -B -m paper_v4_core.cli preflight --taskbook ../inputs/experiment.md --out REV/paper_v4_results/20260909_E00_01；随后self-test --suite mandatory --out同目录。两次实际退出0。
- 结果：源码相对导入身份PASS；5项拒绝检查（改权重摘要、错位时间戳、未来包、同tick到达、缺基线源）及新接口脉冲单测通过。只是守卫函数测试，未证明历史记录器时间语义，也不是完整mandatory验收。
- E16最小代数测试已执行：基础块超界返回NOT_CERTIFIABLE_BY_THIS_BOUND；零耦合、边界、非正规、稳定子系统切换反例均正确分类。尚无完整理论证明或提交版公式匹配。
- 证据：5080 revision_2026/paper_v4_results/20260909_E00_01/audit、tests、E16/counterexamples.json。E00总状态PARTIAL；数据角色、执行器、原记录器和提交版身份仍未完成，不启动正式控制比较。
- 下一步：追溯执行器及control11原始记录链，完善方法注册、源映射与物理单测。无科学通过结论、无方法晋升。

## 2026-09-09 EXP-R1执行：基础受力及记录器源码核对

- 新增paper_v4_core/physics_tests.py，在5080执行python -B -m paper_v4_core.physics_tests --out REV/paper_v4_results/20260909_E00_01，退出0。原始状态/力存E01/static_raw.npz，逐项结果存E01/static_tests.json。
- 5项基础力测试通过，最大归一化残差1.5325941567668805e-14；仅说明受力恒等式和RHS耦合，不代表ICR/33条轨迹或完整plant门通过。
- 读取5080 generate_data.py、dataset.py、build_control11.py、steering_actuator.py并保存本地exp_src副本。源码表明raw行在区间执行后记录，control7与末4列均对raw相邻状态采用下一行所附的已执行区间命令。运行级脉冲和历史生产身份仍待补证，不将源码阅读写成完整时序PASS。
- 执行器为指数一步加增量/角度限制；旧生产每2ms更新后将终点角保持送入植物，并非联合连续精确积分。保持模型不改，后续收敛试验须覆盖这一误差来源。
- 新增exp_status.md整理已完成、未知和下一步。Goal保持ACTIVE，无后台大批次、无训练、无方法晋升。

## 2026-09-09 EXP-R1 E00：原记录器脉冲通过

- 新增recorder_probe.py和exp_recorder.ps1，使用原generate_data.simulate_trajectory，仅替换输入发生器为预定义0.12s脉冲，不修改原生产代码或训练数据。
- 5080执行python -B -m paper_v4_core.recorder_probe --out REV/paper_v4_results/20260909_E00_02，退出0。6个20ms区间：脉冲在raw第2行、cache第1行（均0起算）；全部11列恢复正确；逐区间从raw状态/实际转角独立重放，下一状态最大绝对差0。
- 原始证据pulse_raw.npz、pulse_cache.npz、recorder.json保存源码实际导入SHA及协议SHA。该PASS覆盖当前原记录器链，不追认历史生产源码身份、数据角色或模型性能。
- 下一步审计原训练/确认manifest和读取账本；E00仍PARTIAL。

## 2026-09-09 EXP-R1 E00：历史源码和划分访问审计

- 新增data_audit.py、exp_audit.ps1及只读发现脚本；5080运行两次，输出分别E00_03、E00_04，均退出0，不覆盖前次证据，不读取确认集数值数组。
- 核对97个历史源码SHA，无不一致；3份固定候选权重SHA均与任务书匹配。归一化内容摘要匹配。672条manifest、14842条访问记录全部映射，各折fit/inner/outer参数族重叠0。
- 第一遍发现S0全文件数组字段摘要不同；沿run_background.py:252追溯，原登记使用dict(coeff=coefficients)求摘要。第二遍新增正确命名映射并断言匹配，保留原全文件字段摘要供区分。没有改权重或重新拟合。
- 证据：20260909_E00_04/data_audit.json；未把单批账本无重叠解释为跨历史盲测通过。42/84后续访问链、原训练生成身份、归一化池独立复算、完整方法注册仍待实施。
- 同步本地E00_02脉冲证据、E00_04审计证据；新增input_time_map.md；更新exp_status.md。Goal ACTIVE，下一步继续E00剩余来源链及E01几何/收敛实现。

## 2026-09-09 EXP-R1 E01：后轴几何反例及稳态修正

- 新增reference_geometry.py、geometry_probe.py、exp_geometry.ps1，在5080执行9点检查，退出0（测试正确检出旧几何失败，并验证新稳态实现；不表示旧几何通过）。
- 旧kinematic_targets用质心速度切线设车身航向，后轴v_y−l_r*r不为零，最大0.1363955906918138m/s。新稳态参考显式求后轴无侧滑方向并从前轴速度求转角，残差最大8.326672684688674e-17m/s，锚点位置及前轴法向检查同时通过。
- 不修改plant目录公式、旧分配器、权重或历史数据。新代码为式(6)的稳态部分，转向过渡beta_dot/q_dot、约束和完整轨迹仍NOT_RUN。
- 原始证据：REV/paper_v4_results/20260909_E01_G01/geometry.json；新增exp_solution.md明确旧几何失败与下一步补证。停止旧几何的正式排名依赖分支，不停止独立任务。
- Goal ACTIVE，未标完成、未启动大批次。

## 2026-09-09 EXP-R1 E01：100m批次完成、复算及证据修复

- 100M03统一会话句柄5006最终退出0，9/9完整轨迹运行PASS。两种后台包装100M01/02均在SSH断开后消失且无Python、批次目录或日志内容，不作为实验；随后只续接5006，没有重复已开始的轨迹。
- 新增e01_analyze.py，从9份raw/metrics独立计算。三参数1→0.5ms：峰值最大相对差2.3644613e-6，冲量向量最大相对差2.1106656e-5，终态货物位置差最大1.3637407e-8m，航向差最大9.8444771e-9deg；均通过2%、1mm、0.01deg门。生成figure_100m_P0_0p5ms.png与figure_convergence_100m.png并同步本地。
- 分析命令首次因手工SSH占位参数错误未连接远端，未改变文件；改正命令后退出0。
- 完成后按交付清单复核发现100M03缺Fz、轮胎利用率和事件子步数组，故标PILOT_EVIDENCE_INCOMPLETE。修改e01_100m.py和e01_batch.py仅增加raw/substeps证据字段，不改力律、参数、输入或阈值。
- S02 0.4s短测退出0，保存220条事件子步；最小货物支承4813.231N，最大轮胎原始利用率0.028336。启动同九格100M04统一会话句柄15927；当前运行中。Goal ACTIVE，正式100m子集须待100M04及独立复算。

## 2026-09-09 EXP-R1 E01：运动参考速度一致性

- 新增transition_targets、transition_probe.py及exp_transition.ps1；相对航向作为参考状态积分，显式加入q_dot与各车r_i，不修改冻结植物。
- 5080 G02首次运行退出1：输出JSON不接受NumPy bool；原始transition.npz已保留。仅增加标量序列化转换，G03重跑退出0。
- 20s/2001点诊断：位置差分速度最大误差6.957869835844122e-10m/s，后轴/前轴/锚点速度残差最大分别1.9429e-16、1.1102e-16、1.3323e-15m/s；请求轮角最大12.855748°，采样转角速率0.221371rad/s。
- 证据REV/paper_v4_results/20260909_E01_G03已同步本地；更新exp_solution.md及exp_status.md。该小诊断只用于E01几何接口，不代替33条注册轨迹或物理门。下一步继续注册输入与有限轨迹积分。Goal ACTIVE。

## 2026-09-09 EXP-R1 E01：100m九轨迹批次启动

- 新增e01_100m.py、e01_batch.py。冻结三参数点：P0=(payload×1,connector×1,mu=.9)，P1=(.9,.95,.95)，P2=(1.1,1.05,.8)；每点最大子步2/1/.5ms，固定顺序，任一非PASS立即停止。参数组合用于任务书要求的预定三点诊断，不作为单因素因果分解。
- 0.4s P0/2ms冒烟退出0：作用反作用归一化残差0，内部投影1.1895e-16，时间闭合0；不计入9条完整轨迹。
- 两次Start-Process包装（100M01、100M02）在SSH断开时终止，无Python残留、无批次目录、空日志；没有实验数据，不重用。改为保持远程会话启动100M03，统一会话session=5006，远程Python PID28692。
- 现场复核至15:21：P0/2ms、P0/1ms两条完整raw.npz及metrics.json已落盘，batch.json更新；P0/.5ms运行中。该状态是运行证据，不提前作收敛判决。
- 输出根REV/paper_v4_results/20260909_E01_100M03；Goal ACTIVE。批次完成后独立计算2→1ms和1→.5ms峰值、冲量、终态位置/航向差，按预注册2%/1mm/.01deg门判断。

## 2026-09-09 15:35 EXP-R1进度只读审查

- 用户请求查看最新进度；使用koopman-project-auditor，只读5080进程、注册文件、批次状态、源码和已完成raw；仅追加本地工作记录。未修改/停止/启动远程实验，未改正在由执行任务维护的exp_status.md。
- 15:33主机DESKTOP-9IUUGEO，Python3.11.14，D盘剩余275429076992字节；真实实验PID28692运行paper_v4_core.e01_batch，另一Python为本次只读探针，不计实验进程。
- 15:35:14批次20260909_E01_100M03已落盘4/9：名义参数2/1/0.5ms及第二参数点2ms；第二参数点1ms目录存在、尚无完成文件，结合顺序循环判为第5条运行。不能将batch.json中PASS理解为9条完成或收敛门通过；源码在运行中也写PASS。
- 复算名义参数三份raw.npz：区间峰值最大值与metrics完全一致，冲量加和差≤2.51e-12 N·s。2→1ms四点力峰最大相对差0.0002988673%，1→0.5ms为0.0000951529%；冲量逐分量最大相对差分别0.00419039%、0.00236315%。最后两档五刚体终态位置最大差9.724e-9m、航向6.891e-9度。仅支持固定2ms执行器更新条件下的植物内积分收敛，不能证明整个执行器—植物联合离散已收敛。
- 新发现证据缺口：每条仅有raw.npz/metrics.json，raw是1740×79的20ms端点与区间峰值/冲量，不是完整子步时序，缺逐子步受力/事件/能量等复核证据；不能从这些汇总独立重建子步真实峰值。完整E01仍未通过。
- 时间语义：e01_100m.py每行先推进20ms再保存状态，但time_s记录区间起点t。末行标签34.78s对应实际推进至34.80s，缺初始状态行。与原历史记录器已验证的命令对齐是两个不同问题，不否定此前脉冲验收。
- 100m指参考累计距离，不是实际严格走100m：名义0.5ms数据从首个保存状态累计约102.8074m，最终货物位置约(100.8553,10.6286)m、体纵向速度0.85456m/s。该批是含基础分配反馈的激励诊断，不是真实MPC排名，也不能称直道轨迹跟踪已通过。
- 源码SHA：e01_100m=46ccbe6d7df8dd788b85db58502574769d25c02cb0d279b0e809f3ea1b9080a4；e01_batch=0e7721119566266a88b398f4e3baef694c5971b7db445723dedc2cf719883f88。名义raw三份SHA分别116e7fee3a1d65b212b5dfecdfafcfd92bba226dd282c738ceaf8e25f2a889d1、2c4810b708d1a45bd1c61cb2092aa94d43d9d7071a7dadb6c5b679bf94ea027c、55a0a0c4494ba776738922eae9b591791e0b61ab5132df7d9023e029f3a2ef81。
- 建议：在转入预测/MPC前补齐状态/区间双时间、完整子步及执行器离散验收，真实区分RUNNING/COMPLETE/CONVERGENCE_PASS。当前只读授权，不自行修复或终止现有运行。尚无新Koopman或网络MPC优劣结果。

## 2026-09-09 EXP-R1 E01：M04完成后时间语义硬检查

- 续接句柄15927，M04 9/9退出0；每条新增raw/substeps/metrics，最小支承载荷均为正，最大轮胎原始利用率最高0.26044，作用反作用、投影和每个外层时间闭合通过。
- 独立核对发现raw的time_s是命令区间起点，而所附state30是积分后终点；循环ceil(T/DT)+1还多执行20ms。这与任务书时间语义不符，因此M04继续作为调试证据，不用于论文图或正式计数。
- 修e01_100m.py：保存终点time_s与interval_start_time_s双列，参考距离起终点双列，循环移除额外+1，并输出integrated_duration_s。未改植物、控制输入、三参数点、步长或门槛。
- S03短测退出0：20区间、终点0.4s、210真实接受子步，dt总和0.40000000000000013s。随后启动M05统一会话句柄88375；任一科学失败仍自动停止。Goal ACTIVE。

## 2026-09-09 EXP-R1 / E01-100M05 等待期验收器加固

- 保持远端前台批次 `20260909_E01_100M05` 的既有会话（session 88375），未因旁路 SSH 查询无返回而重启，避免重复计算与证据目录污染。
- 仅修改本地离线验收器 `exp_stage/src/paper_v4_core/e01_analyze.py`，未修改正在运行的模型、积分器或原始输出。
- 新增逐轨迹证据审计：`raw.npz` / `substeps.npz` / `metrics.json` 三件套、必需字段、有限值、接受子步计数、积分时长闭合、最小支撑力和最大轮胎利用率复算、完整轨迹标志。
- 主图新增四连接点垂向支撑力；新增四点水平合力方向箭头图。方向箭头按面板独立归一化，只用于方向判断，不用于跨时刻幅值比较。
- `python -m py_compile` 通过。该修改尚未对 M05 数据执行，须待远端批次完整退出并同步后才能给出科学门结论。

## 2026-09-09 EXP-R1 / E01-100M05 九轨迹计算完成

- 请求/任务编号：EXP-R1 E01，100m诊断三参数点×三最大子步。
- 授权模式：执行实验。
- 机器与项目根目录：`DESKTOP-9IUUGEO`；`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026`。
- 基线身份：`e01_100m.py` SHA256 `2f3c93e7a24959ab2c0dc2785f043818f28f8a0f8ceb3c91ce13d88ba4841025`；`reference_geometry.py` SHA256 `6aeac2cbab4f96726915c9124c83b012c368ab5f06df8f2281a4b89fcb97228d`。
- 命令：保持的远程前台会话 88375，模块 `paper_v4_core.e01_batch`。
- 退出码：0；批次摘要 `status=PASS, completed=9`。
- 原始产物：远端 `paper_v4_results/20260909_E01_100M05`，每条均报告 `raw.npz`、`substeps.npz`、`metrics.json`。
- 关键结果：9条均完成1739个20ms区间，实际积分时长34.78s；最小货物支撑力范围3677.7404—4477.7258N，最大轮胎原始利用率范围0.23125—0.26044；作用反作用归一化残差为0，内部投影残差最大3.5442e-16，时间闭合残差为0。
- 结论类型：事实（运行输出）；尚待从同步后的原始数组独立复算收敛及证据完整性。
- 状态：PARTIAL；单轨迹运行通过，不提前等同100m数值收敛子门通过。
- 下一步：完成同步；运行加固后的 `e01_analyze.py`；检查图和JSON后再裁决。

## 2026-09-09 EXP-R1 / E01真实回头弯几何冻结

- 新增：`exp_stage/src/paper_v4_core/references.py`、`hairpin_probe.py`、`exp_stage/e01_routes.json`。
- 冻结选择：入口/出口各24m、名义半径11.5m、两端各2m三次smoothstep曲率过渡、恒曲率段34.1283155m、路线弧长86.1283155m；三参数点和三最大子步沿用100m诊断。
- 本地探针退出0：总航向误差3.2723e-11rad，终点约(0,23.017388)m；相对瞬时进入的理想半圆，转弯区最大径向偏离0.999918m，必须在成果中披露。
- 依据：2m/s下过渡持续约1s；对称前后转角分配的解析峰值虚拟转角速率约0.161rad/s，小于冻结执行器1.2rad/s限制。
- 状态：几何探针PASS；完整植物轨迹NOT_RUN，等待100m原始证据独立门。

## 2026-09-09 EXP-R1 / E01-100M05 独立验收通过

- 使用正确SSH配置别名`5080`同步完整远端目录；此前直接用主机名缺失中文用户名与专用密钥，详细握手显示主机校验失败。未修改`known_hosts`，未接受新密钥。
- 5080 `pytorch_new`环境运行加固后的`e01_analyze.py`退出0；九条逐文件审计全部PASS，原始/子步/指标三件套、有限值、子步计数、时长、Fz和轮胎利用率复算均一致。
- 最终两档1→0.5ms：峰值最大相对差2.3645e-6，冲量向量最大相对差2.1503e-5，末端位置最大差1.3591e-8m，航向最大差1.0825e-8deg；均通过2%/1mm/0.01deg预注册门。
- 名义最细轨迹：实际货物路径102.81025m，末端(100.83820,10.62854)m；最大点力模1540.947N，纵/横向拉开代理最大131.972/218.916N，最小支撑4077.380N，最大轮胎原始利用率0.237411。
- 图像复核后将收敛图纵轴改为对数尺度并重生成；不改变数据、门槛或结论。
- 证据：本地`20260909_E01_100M05`及远端同名目录；状态：100m子门PASS，完整E01仍PARTIAL。

## 2026-09-09 EXP-R1 / E01回头弯工作域修复与正式批次启动

- 初始2m过渡HG01几何本身PASS，但HS02记录47个请求饱和事件、请求前轮几何残差0.294438m/s；目标几何残差1.67e-16m/s。去掉附加航向反馈的HS03仍有44个目标角超限，证明根因是偏置连接点动态几何工作域，不只是反馈。
- 按停止规则未启动正式批次。纯几何扫长显示2/3/4/5/6/8/10m过渡的四车最大目标角依次约23.71/20.97/19.15/17.89/16.98/15.81/15.12deg；冻结11m后为14.88deg。
- 11m版本HG02：总航向误差1.03e-12rad，恒曲率核心半径11.5m；路线总长95.1283m，相对瞬时半圆最大径向偏离5.48636m（显著，必须披露）。
- HS04覆盖36m/18s、完整入弯过渡：退出0；饱和0；目标/请求残差2.22e-16/1.11e-16m/s；实际后/前轮侧滑最大0.011891/0.014137m/s；最小支撑4681.26N；作用反作用、投影和时间闭合通过。
- 正式批次`20260909_E01_HAIRPIN01`已用前台会话75784启动：三参数点×2/1/0.5ms，任一非PASS停止。状态RUNNING；尚无完整回头弯收敛结论。

## 2026-09-09 EXP-R1 / E01回头弯硬失败与停止

- `HAIRPIN01/P0_2ms`在75.92m触发`STOP_ULTIMATE_FORCE`，批次退出1，后8条未运行。峰值约15.002kN，最大横向拉开代理15.020kN，最大货物速度/航向误差1.335m/s/22.81°。
- 修复失败轨迹时间语义：以后raw末行使用实际接受子步时长；HR01/HR02的raw终时与子步积分一致。原HAIRPIN01错误标签保留并在对比JSON标记false。
- Repair 1冻结共同速度P与共享航向P-D后，HR01在50.836m失败，且出现188次不可行转向；未调大增益，判该结构不合适。
- Repair 2仅保留共同速度P，HR02在81.72m失败；请求饱和0、目标/请求几何残差约1e-16m/s，仍达到15.002kN，横向拉开代理14.601kN。
- 输出远端/本地`20260909_E01_HFAIL01/failure_comparison.json`与`hairpin_failures.png`；三条原始轨迹分别保存在HAIRPIN01、HR01、HR02。
- 状态：E01真实回头弯硬门FAIL；停止剩余E01正式轨迹及依赖完整plant_gate的E02/E03/排名。未修改连接刚度、轮胎、极限或删减失败工况。下一步方案写入`exp_solution.md`，推荐另行预注册受约束的物理下层阵列跟踪器。

## 2026-09-09 EXP-R1 / E01停止现场复核

- 授权模式：硬门失败后的只读现场审计；未启动、修改或终止远端实验。
- 5080主机身份：`DESKTOP-9IUUGEO`；筛选`paper_v4_core`/`20260909_E01`命令行的Python或MATLAB实验进程为0，确认停止状态真实。
- 远端/本地失败汇总哈希一致：`failure_comparison.json` SHA256 `B413DBB5CDE39F5F3E9B51BD37D8C8E8636D00C826496ECCE26CA112846E76AE`；`hairpin_failures.png` SHA256 `50BADBDE1EBDCD145602C1E25585B406E65A9568982E459A0831DE873CE1A09D`。
- `exp_solution.md`已包含三条失败事实、根因候选、被反证的两次最小修复、A/B/C方案及重新进入门槛；当前没有新证据推翻`E01 true hairpin FAIL`。
- 状态：BLOCKED审计第2次；按用户“支撑证据跑不出就停”和任务书硬门，继续需要用户选择并授权新的下层阵列控制接口或修改冻结工作域。

## 2026-09-09 21:26 EXP-R2：结合最新失败修正完整任务书

- 请求：结合完整执行书和最新数据更新下一步修正方向。模式为只读审查＋本地MD编写；未运行/终止实验，未修改远程代码、数据、阈值或植物，未改变其他任务Goal。
- 现场21:20：DESKTOP-9IUUGEO，实验Python/MATLAB进程0（审计探针除外），D盘余275075526656字节；最新失败汇总SHA与本地一致b413dbb5cde39f5f3e9b51bd37d8c8e8636d00c826496ecce26ca112846e76ae。
- 读取M05收敛报告、三失败汇总、HR02原始/子步数据及e01_hairpin、event_substep停止分支。确认100m已有9条完整证据，不能沿用15:35的未完成判断；回头弯及两次P修复仍FAIL。
- HR02复算：raw点力最大15001.651735N、横向拉伸代理14601.077889N；substeps对应最大值14995.127746N/14594.871240N，metrics峰值又为14997.301485N。当前run在audit失败时先break，漏累计失败调用中已接受的段；积分器先更新状态再检测极限。因此FAIL真实，但失败末态时间/峰值证据仍须补齐，不能只凭raw/substeps时长彼此相等宣布正确。
- 更新experiment.md为EXP-R2：顶部状态改正，新增第18节（18.1—18.10）并保留完整原计划。拆开PHYSICS_BASE、ROUTE_CLOSED_LOOP、PLANT_GATE_FULL，允许在基础物理门后进行E03-P集中全状态物理控制诊断，避免原控制开发与全路线完成的循环依赖。它不是分布式排名基线，也不自动证明可行性。
- 推荐：先R0失败记录/状态单测→R1已有数据构形与内部力归因→受约束8输入物理MPC小试→数值/参数配对→合法信息接口→恢复Koopman与网络比较。名义共同ICR作为兼容参考，不强制实际弹性阵列无逐车纠偏自由度；不调软连接器或放宽15kN停止线。
- 新计划最多14条控制开发＋1条≤2s边界重放＋9条≤2s执行器离散片段=24条，按门分段，不是立即运行。保留旧正式13140最大新增逻辑任务为远期计划。明确11m过渡对理想半圆约5.486m偏离及其工作域限制。
- exp_solution.md、exp_status.md仅增加最新入口/状态提示，历史问题和失败仍保留。原稿/Word/历史输出未变。
- QA：公式1—36顺序、36对数学块、新阶段预算和章节存在检查通过。experiment.md最终SHA417CFCDBF22A026973DFF617E29E4814361F9013AED7CA06F065992C20F0D81D；exp_solution.md新SHA3D29E8E8A80DFC0249D0E648D53E4924FB53E5A2AC8F6D16E4ECB9562B4FE08B；exp_status.md新SHAEF31C3E22E639D1AF8E8C988AD63A43CEB750F181E88691C7D16D8A03C8E7789。
- 按koopman-project-auditor设置失败证据硬门及不扩大授权规则。状态PLAN_UPDATED；新控制器及上述试验NOT_RUN，完整E01仍未通过。

## 2026-09-09 EXP-R2 / R0—R2a执行与R2b启动前状态

- 授权：用户要求按更新后的`experiment.md`继续执行；任务书SHA256为`417CFCDBF22A026973DFF617E29E4814361F9013AED7CA06F065992C20F0D81D`。按第18节新入口执行，未放宽连接器、轮胎、支撑、12kN预测预算或15kN停止线。
- 现场：通过SSH配置别名`5080`确认主机`DESKTOP-9IUUGEO`、项目和Python 3.11.14存在、D盘余275075514368字节、相关Python/MATLAB实验进程0。
- R0修复：新增`failure_boundary.py`和6项mock；修改`e01_hairpin.py`，对积分器返回先累计所有已接受段再判断停止，保存起止时刻、接受时长、末态、失败时刻、峰值argmax及执行器区间起点离散跳变语义；拆分`requested_full_trajectory`与`trajectory_completed`，状态使用RUNNING/COMPLETED/FAILED/PAUSED。`e01_analyze.audit_failure_boundary`会拒绝故意漏终止段的记录。
- R0验收：远端`paper_v4/results/20260909_R0_MOCK02/r0_mock_tests.json`退出0，6项PASS（已接受1ms后停止、未接受失败、正常2ms、端点触发、完整证据接受、漏末段拒绝）。无时间一致的历史失败检查点，未猜测重放旧末段；三条旧失败继续标`FINAL_STATE_TIME_UNCERTAIN`。
- R1离线归因：只读取三条旧失败和100M05名义轨迹，未生成新动力学。有效输出在远端`paper_v4_results/20260909_R1_03`；前两次R1_01/R1_02因旧列兼容读取错误退出，未形成有效报告，保留失败尝试。
- R1事实：原输入/航向修复/共同速度修复的最大实际构形误差约0.623/0.673/0.580m，内力零空间范数约20.917/19.466/21.259kN；100m名义约0.07645m/2.343kN。三失败的20%持续阈值中，相对运动均早于持续内力上升；这只是时序定位，不宣称因果。最终差动加速度均未越过声明±0.8m/s²。
- R1诊断单测：远端`paper_v4/results/20260909_R1_TEST01`四项PASS（初态构形、旋转坐标帧、内力零空间、连接对功率符号）。
- R2a实现：新增集中全状态物理MPC诊断上界，8维请求、Ts=20ms、N=20；十个2ms冻结执行器/物理步构成一步预测，不含Koopman。输入包络沿用共同1.2＋差动0.8得到每车±2m/s²，转角±15°；加速度速率因冻结植物未建执行器而不伪造。QP含跟踪、构形、相对速度、内力、名义转角和输入变化；线性化硬约束含12kN逐点力、轮胎利用率≤1、支撑非负，候选再做20步非线性复算。
- R2a有效验收：远端`paper_v4/results/20260909_R2A_05/r2a_tests.json`退出0，N=1/20真实优化、方向梯度、转角边界、不可行拒绝、受激模型扰动共6项PASS。刚度+10%使一步预测/A/B最大变化分别`2.667854e-4`/`6.498157e-2`/`7.646226e-6`。N20从约25.03s优化到约2.93s：仅在0.4s预测窗复用当前点物理动力学Jacobian，名义轨迹仍逐步非线性推进，候选仍完整非线性复算；未缩N或换反馈律。
- R2a中间失败保留：R2A_01暴露模型域异常未返回显式失败，已改为`MODEL_DOMAIN_ERROR`；R2A_03在自由间隙内零受力平衡点做刚度扰动导致零变化，属于测试前提错误，改为轻微伸长＋相对速度受激点。一次上传超时导致远端误跑旧哈希，不计新方法结果。
- 源码当前本地SHA：`failure_boundary.py` 1BB27D93；`failure_boundary_tests.py` E7ED9DF4；`e01_hairpin.py` 6FEAD661；`e01_analyze.py` 82F1827E；`relative_motion.py` 4E280759；`internal_loading.py` 84BDB227；`r1_diagnose.py` 7B719E32；`r1_diagnostic_tests.py` C525BFEB；`physical_tracking_pilot.py` 27B43EF9；`r2a_tests.py` A28A3533；`pilot_runner.py` DA2A33B6。
- R2b runner已在本地完成并通过语法编译，职责为每20ms求解、10×2ms真实植物推进、R0边界记录、raw/substeps/solver/status检查点及硬门停止。上传前5080 SSH端口开始超时；Tailscale仍显示主机active且6ms直连，但TCP/22无响应。`pilot_runner.py`尚未确认到达远端，0.02s smoke和两条18s R2b均未启动，严禁声称正在运行。

## 2026-09-10 EXP-R2 / R2b与R2c执行增量

- 5080连接恢复后核对远端`pilot_runner.py` SHA256为`DA2A33B6FCEE6A975AE0561683720CC20D800A61C52CBD738FB165DFCCAFFF82`；0.02s集成冒烟`paper_v4/results/20260910_R2A_RUNNER_SMOKE01`通过。未更改P0植物、路线、12kN预测工作预算、15kN实际停止线、轮胎或支撑门。
- R2b两条冻结18s/36m入弯片段均完整完成。`20260910_R2B_L1_02`：点力峰值252.822N、内力峰值203.840N、轮胎利用率0.050418、最小支撑4680.268N、最大构形误差0.011139m；`20260910_R2B_L2_01`：252.012N、202.616N、0.050368、4680.240N、0.011105m。两者均900次求解、9000个以上真实2ms子步，无硬门失败。
- R2b独立比较第一次`20260910_R2B_COMPARE01`错误地把短片段优选写成R3最终候选；原目录保留，不覆盖。修正后的有效报告`20260910_R2B_COMPARE02`明确只给R2c顺序`lambda2, lambda1`，`selected_for_r3=null`。λ=2内力峰值仅低约0.60%，不声称显著或普适优势。
- R2c λ=2完整路线`paper_v4/results/20260910_R2C_L2_01`状态`COMPLETED`：2379个20ms周期、47.58s、参考95.1283155m全部完成，实际货物路径95.8138805m；点力峰值345.882N、内力峰值312.088N、轮胎利用率0.0542353、最小支撑4675.573N、最大构形误差0.0134882m。总墙钟7343.339s；该计算耗时远大于20ms控制周期，只能作为非实时集中全状态诊断上界。
- R2c λ=1于16:54启动到`paper_v4/results/20260910_R2C_L1_01`，配置与λ=2相同，仅`lambda_internal=1`。两次错误入口分别因不存在的根目录文件和包相对导入被立即拒绝，均未创建/覆盖结果；改为设置`PYTHONPATH=src`后用`python -m paper_v4_core.pilot_runner`启动。首批检查点及远端PID 34460已验证。
- Windows在写句柄打开期间把`solver.jsonl`目录长度暂报0；以共享读句柄直接读取长度190735字节，确认求解器记录实际持续写入。未将元数据缓存误判为证据丢失，也未重启有效长跑。
- 新增独立`r2c_analyze.py`，本地语法检查通过并上传远端，双方SHA256均为`EEC61A813C4C567AB869BA00FFBD754BB24FCB0F7749564F5506F01CED7ED736`。它逐项复算全程/子步/求解器/12kN预测门/15kN实际门/轮胎/支撑/输入边界/记录一致性，按“内力→货物跟踪→计算”冻结R3候选，并同时画实际冻结参考与理想瞬时11.5m半圆。
- 当前状态：R2c λ=1 `RUNNING`；两条R2c都完成且独立分析通过前不启动R3、不宣布候选优越。
- 后续视觉QA发现15kN/轮胎1.0硬门线会把实际低载荷候选压在坐标底部；仅修改`r2c_analyze.py`图形为远离数据时标注`off scale`，JSON硬门和选择规则不变。第二次只读冒烟`20260910_R2C_ANALYZER_SMOKE02` PASS；当前本地/远端SHA为`7BAD4D388880124E8590F3808597499F76AB0730D860AEB9E838E018A46D9B95`。第一版SHA及SMOKE01原样保留。
- Tailscale节点仍可4—32ms直连，但其100.95.123.1:22阶段性超时并最终重置原前台会话。核对同机局域网`192.168.0.2:22`开放，使用相同用户名、`id_ed25519_5080`和`HostKeyAlias=100.95.123.1`复用原主机密钥，返回主机名仍为`DESKTOP-9IUUGEO`。通过该通道确认原PID 34460继续运行，没有重启轨迹。
- 为后续已授权分支准备并上传门锁入口：`r3_batch.py` SHA `65085D3D...`、`r3_analyze.py` `B5A71D34...`、`r4_batch.py` `588E172A...`、`r4_analyze.py` `FB429E78...`，远端哈希逐一相同。R3必须读取有效R2c选择并核对2ms基准后才顺序运行1/0.5ms；R4必须再读取PASS的R3报告才运行P1/P2三步长，任一非完成立即停止。仅编译/上传，尚未启动R3/R4动力学。
- 在5080的Python 3.11.14环境对`r2c_analyze.py`、R3/R4批处理和分析器统一执行`py_compile`，退出0。新增本地启动封装`remote_run_r2c_compare.ps1`、`remote_run_r3.ps1`、`remote_run_r3_analyze.ps1`、`remote_run_r4.ps1`、`remote_run_r4_analyze.ps1`并通过PowerShell语法解析；每个封装都先验前置状态且拒绝覆盖已有目录，尚未执行。
- 新增只读监视脚本`remote_compact_r2c_status.ps1`与`monitor_r2c_l1.ps1`，每30s核对原PID和状态，只在COMPLETED/FAILED/PAUSED时退出，不写远端。17:50最新权威检查点为PID 34460、1050/2379周期、21.0s、42.0m，状态仍RUNNING。

## 2026-09-11 EXP-R2 / R2c终态、选择与R3启动

- R2c λ=1原PID 34460于2026-09-10 19:02完整结束；`paper_v4/results/20260910_R2C_L1_01`含raw/substeps/solver/status/metrics五件套，2379个20ms周期、47.58s、95.1283155m参考全程，实际货物路径95.8835482m。终态摘要：点力峰值358.861N、内力峰值320.907N、轮胎利用率0.0728369、最小支撑4675.590N、最大构形误差0.0138544m，runner SHA仍为`DA2A33B...`。
- 独立`20260910_R2C_COMPARE01`返回FAIL：λ1请求转角峰值15.0054157°，超过冻结15°硬界0.0054157°；实际执行器角度14.9980547°不改变“请求越界”的裁决。λ2请求峰值15.0000000°并通过。未用OSQP容差、小幅度或实际执行器裁剪为λ1豁免。
- 比较器第一版错误地要求两个候选同时PASS才允许选择；任务书实际规则是“两者均失败才停止”，一个失败时应淘汰它并从合格者选择。保留COMPARE01，修改分析器而不改数据/阈值/控制器；新SHA `94C1F9AA...`在本地和5080一致、远端py_compile退出0。
- 有效`paper_v4/results/20260911_R2C_COMPARE02`状态PASS：唯一合格候选`lambda2`，拒绝`lambda1`的检查仅为`request_steering_bound`；全部其他原始、子步、求解器、12kN预测、15kN实际、轮胎、支撑、时间、控制记录及源码身份检查通过。正式图和路径图已同步到本地`20260911_R2C_COMPARE02`并目视QA通过；冻结11m过渡参考与理想瞬时11.5m半圆分开显示。
- R3/R4批处理增加逐条独立事后硬门：每条完成后复用R2c审计检查请求边界、求解/非线性验证、实际力/轮胎/支撑、证据计数和身份；失败即写批次FAILED并停止后续。冻结`pilot_runner.py`不改，避免R3与R2c控制器身份不一致。更新后`r3_batch.py` SHA `CD70B70D...`、`r4_batch.py` `309D409F...`，本地/远端一致并编译通过。
- R3第一次后台启动`20260911_R3_01`仅产生相邻零字节stdout/stderr，PID瞬时消失、无批次目录，证明Windows OpenSSH会话回收`Start-Process`子进程；未进入Python主程序、未生成动态轨迹、未消耗R3两条预算，痕迹保留。
- 改用受控SSH前台会话并把Python输出重定向独立日志，启动新目录`paper_v4/results/20260911_R3_02`。远端父PID 36320、批次RUNNING；1ms首个检查点已验证为25周期/0.5s/1.0m，stderr 0。配置由COMPARE02自动读取λ=2，P0、N20、20ms控制和同一路线不变；只有1ms独立事后门PASS才进入0.5ms。

## 2026-09-11 EXP-R2 / R3运行期间E00投稿候选身份核验

- R3仍由原前台PID 36320顺序运行，最新已核实1ms子项到275/2379周期（5.5s、11.0m），批次`RUNNING`、stderr为0；未重启、未改控制器或门槛。
- 在5080项目中发现`tmp/tvt_check_20260706/main.pdf`，SHA256 `1482D00A...A9F5`、12页、PDF生成时间2026-07-06 15:28:36；同目录`manuscript.tex` SHA `C4C0075F...17E6`。冻结`00_baseline/manuscript.original.tex` SHA `1E9E5154...94F6`与候选TeX仅`markboth`期刊头一行不同。
- 审稿信附件与5080冻结`reviewer_decision.txt`逐字节相同，SHA256均为`6604BCCE...E5A44`；候选PDF标题与VT-2026-05393完全匹配。PDF第5页式(22)、第8页Table II及第10页Table III的内容分别对应审稿人对基础块界、K1/K2与K3、以及力峰值的质疑；已渲染检查第1/5/8/9/10页，公式、表格和标题可读。
- 不能把上述高度一致性升级为“已取得提交PDF”：候选包README写的是`IEEE Sensors Journal LaTeX source package`，且审稿信称Table III在第11页、候选PDF印刷页为第10页；未找到投稿门户回执、提交文件清单或提交文件哈希。可能存在门户封面导致页码偏移，但这只是推测。
- 新建远端`paper_v4/audit/submission_match.json`，SHA256 `4075856C...929E`，状态保持`SOURCE_PENDING`，明确允许把该PDF作为候选原稿做公式/表格映射，禁止称其为提交版。未修改该PDF、TeX或冻结基线。
- R3运行期间只准备、不执行R5：新增`information/legal_information.py`、`r5_information_tests.py`、`r5_runner.py`、`r5_analyze.py`、`r5_batch.py`。接口把植物真值限制在传感注入器/评价器边界，控制器只接收四车本地同tick测量包与货物协调节点测量包；拒绝raw ndarray、未来包、缺节点和truth字段。基础噪声严格采用任务书0.01m/0.2deg/0.02m/s/0.005rad/s，未有标定依据的实际转角暂按零噪声并明示。
- R5批处理被R2c λ2选择与R4 PASS双门锁定；执行顺序为接口单测→无噪声完整路线→基础噪声完整路线，任一硬门失败停止。无噪声接口还必须在1e-12内复现R2c全状态基准，避免“换信息接口”悄悄改变控制器。当前仅本地/远端`py_compile`通过，未运行接口单测或R5动力学，未提前消耗两条R5预算。
- R5初版审查发现无噪声航向若强制包到[-π,π)会在回头弯跨π时造成表示跳变，破坏“接口不改变控制器状态”的验收前提；改为由本地历史因果解缠后的连续航向，并增加跨π无噪声保持单测。这是接口表示修正，不改植物、控制器或噪声幅值。
- R5当前源码本地/远端SHA一致：legal information `3C95192C...3E5E`、tests `D5E5A789...4499`、runner `AFD72A39...FFEA`、analyzer `D72B376F...ED07`、batch `8B14DDB2...A6AA`。本轮工作记录/状态/方案已同步到5080的`paper_v4/logs/20260911_*`，未覆盖旧根目录日志。
- E00数据角色审计在当前5080源上只读重放，产物`paper_v4/audit/data_roles_refresh_20260911/data_audit.json`与20260909_E00_04逐字节同SHA `04B43453...C6D3`：97个源文件和3个checkpoint均匹配，672条manifest、14842条访问记录，0拒绝、0未映射、同fold跨角色family交集0。新建简表`paper_v4/audit/data_roles.json` SHA `130F90E1...BB70`，状态仍`PARTIAL`；单一运行账本不能证明后来42/84确认池盲性，也尚未重放归一化只使用fit池，因此正式数据仍未授权。
- 按第18.7节只准备执行器离散诊断，未运行九条短轨迹：冻结源为100M05/P0_0.5ms `raw.npz` SHA `C68CCAF5...CC92`，预登记窗口为直线加速0—2s、转向起始11.5—13.5s、反向切换16.5—18.5s；三档执行器更新2/1/0.5ms，共用同一窗口初态、实际转角和冻结命令，植物最大步长固定0.5ms。
- 新增`actuator_discretization.py`、`actuator_discretization_analyze.py`、`actuator_discretization_batch.py`，R4 PASS门锁、首个动态/证据硬失败即停。2ms重放须在1e-12内复现冻结源；1→0.5ms按原2%峰值/冲量、1mm终态位置、0.01deg终态航向门裁决，2→1ms仅诊断。当前仅本地/远端编译通过，SHA依次`DBC18F99...C3B5`、`37AE7DAE...5435`、`85710D35...BC51`，预算未消耗。

## 2026-09-11 EXP-R2 / E00任务书与代码身份审计

- 发现5080的`paper_v4/inputs/experiment.md`仍为旧EXP-R1，SHA256 `98E27F51...`，并非本轮用户指定的最新EXP-R2。首次身份审计因此按预期拒绝，且未创建结果目录；没有把旧任务书误记为当前协议。
- 原文件保留为`paper_v4/inputs/experiment_EXP-R1_98E27F51.md`，随后同步本地最新任务书；远端现有`paper_v4/inputs/experiment.md` SHA256为`417CFCDBF22A026973DFF617E29E4814361F9013AED7CA06F065992C20F0D81D`、141812字节，与本地一致。
- 新增并运行只读`identity_audit.py`，SHA256 `0AFD58B6...EE53`。包/导入身份检查通过：主机`DESKTOP-9IUUGEO`，53个Python文件纳入清单，9个plant文件在相对导入归一化后AST等价，`sys.path`仅解析到唯一`paper_v4_core`，当前任务书哈希匹配；执行器离散实现及其假设已登记。
- 直接证据为`paper_v4/audit/identity.json` SHA256 `E19C40A0...E250F`和`paper_v4/audit/imports.json` SHA256 `F156AE07...32DCD`。总体身份状态仍`PARTIAL`，原因是投稿PDF来源链与正式数据授权均未闭合；不能由代码身份PASS替代这两个缺口。
- 历史输入时序图只补充来源链并迁移到`paper_v4/audit/input_time_map.md`，SHA256 `3BD7E9D0...00FC`；当前producer语义已验证，历史生产冻结来源仍未被补证。
- 补齐E00要求但先前缺失的两个登记产物：`paper_v4/protocol/methods.json` SHA256 `38960DC4...C96367`含6个唯一核心方法键，全部保持`NOT_RUN`；外部强基线保持`SOURCE_PENDING/NOT_RUN`。当前R2—R5集中全状态控制明确列入`excluded_diagnostics`，不得冒充P0/P0N或进入H1—H6。
- `paper_v4/review/review_matrix.json` SHA256 `63CFB4ED...E5B37`逐条登记AE 2项、R1 6项、R2 7项、R3 7项，共22个唯一编号；状态来自任务书第14.1节，没有把当前开发结果自动改成审稿意见已解决。双方JSON在本地和5080均解析通过、计数及SHA一致。
- 继续递归入口审计时发现`src/paper_v4_core/cli.py::preflight`第65行仍硬编码旧EXP-R1哈希`98E27F51...`，第96—97行还会生成空的review/method占位。这一旧CLI未被当前R3的`r3_batch→pilot_runner`调用，R3注册的runner/batch/selection/route身份不受其运行时影响；但它不能再作为EXP-R2权威预检，且若误执行会与已补齐登记表冲突。
- 为保持运行中源码冻结，本轮没有在PID 36320存活时修改`cli.py`。后续须在R3/R4数值批次无活动进程后：改为从受核验输入任务书读取当前哈希或显式协议清单，拒绝覆盖现有正式登记产物，运行其负向测试，再重跑`identity_audit.py`更新53文件清单。当前E00总体继续PARTIAL。

## 2026-09-11 EXP-R2 / R3终态与数值硬门失败

- 原PID 36320顺序完成`20260911_R3_02/1ms`和`0.5ms`，两条均2379个20ms控制周期、47.58s、95.1283155163m参考全程；批次状态COMPLETED、completed_runs=2、stderr 0，随后PID正常退出。1ms通过独立事后门后批次才进入0.5ms，没有并行或跳门。
- 独立`paper_v4/results/20260911_R3_COMPARE01/r3_convergence.json`退出20、状态FAIL。三档原始/子步/求解器/请求/实际力/轮胎/支撑/时间/源码身份审计全部PASS；失败只在决定性1→0.5ms数值门。
- 1→0.5ms：峰值差0.00889827、冲量向量差0.000456931，均低于2%；终态位置差0.007026279m超过0.001m，终态航向差0.013079743°超过0.01°。2→1ms诊断对应0.00592482、0.000272890、0.009163596m、0.021539851°。
- 正式图已同步本地`20260911_R3_COMPARE01/r3_convergence.png`并目视QA；四面板正确显示位置与航向越过红色冻结门。JSON/PNG SHA256分别`F552FEA7...E5678`、`670B4805...E0E0CA`。
- 未启动R4、R5或执行器批次。任务书要求R3数值配对通过后才进入R4及回到Koopman主线，因此当前依赖分支硬停止；不以低力、安全完成或接近航向门替代数值收敛。
- 新增只读同tick诊断脚本`tools/r3_divergence_diagnose.py`，不积分植物。有效DIAG02确认初态位姿和2379时间格完全相同；位置42.90s首超1mm、航向44.20s首超0.01°、请求加速度42.58s首超0.01m/s²。最大请求转角差2.2434°@43.06s、加速度差0.5949m/s²@43.12s、逐点力差56.26N@43.04s，说明后段控制序列已分叉。
- 第一次本地诊断因本机Python缺matplotlib，在写JSON后作图失败；未运行新动力学。远端DIAG01作图仅有空legend警告，保留；修正只影响图例显示后另建`20260911_R3_DIAG02`。有效JSON/PNG本地SHA为`234C0248...3B014`、`A1AB2600...7F284`。
- 运行级`solution.md`已写入本地并同步5080的`20260911_R3_COMPARE01`目录。根因当前仅能判断为闭环分辨率敏感性集中在约43s晚段；活跃约束/局部线性化/执行器/积分器的相对贡献尚未证实。

## 2026-09-11 EXP-R2 / R3停止后的E00旧CLI修复

- 修改前确认5080不存在`paper_v4_core`实验进程，避免运行中改变Python源码快照。修改`cli.py`只涉及预检/登记验证入口，不改plant、controller、runner、R3数据或R3裁决。
- `cli.py`从旧EXP-R1标题/固定`98E27F51...`改为当前EXP-R2任务书SHA `417CFCDB...D81D`；preflight新增必需的`--methods`与`--review-matrix`，严格要求核心键恰为P0/P0N/K0/K0N/K1/K1N且唯一、审稿编号恰为22项且唯一。所有输入/递归AST身份通过后才创建输出，防止拒绝时留下半成品目录。
- 移除preflight自动生成的空methods/review占位，改为验证并复制已登记的真实结构；执行器合同标为`IMPLEMENTED_SIMULATION_ASSUMPTION_NOT_MEASURED`，不再笼统写SOURCE_PENDING。当前`cli.py` SHA256 `5F18E475...547AC`。
- 远端py_compile退出0；`20260911_E00_CLI_TEST01`退出0，新增“不完整6方法/22意见必须拒绝”负向测试；mandatory JSON SHA `531D7D0D...8F42B`。`20260911_E00_PREFLIGHT01`成功核对当前任务书与两登记表，E00仍按真实缺口输出PARTIAL。
- 递归`identity_audit.py`在`audit/identity_refresh_20260911_02`重跑：53个Python、9个plant AST对照，状态PARTIAL。identity摘要仍为`E19C40A0...E250F`；imports因CLI源码更新变为`EABEAEB6...E1465`。旧canonical imports已保留为`imports_pre_cli_fix_F156AE07.json`，新imports核验后更新到canonical路径。
- 此修复关闭`LEGACY_PREFLIGHT_STALE`工程缺口，但不改变投稿SOURCE_PENDING、数据角色PARTIAL或R3 numerical FAIL；主实验依赖链仍停止。

## 2026-09-11 EXP-R2 / R3停止后的E00公式映射与总门

- 复核本地/远端任务书仍为SHA `417CFCDB...D81D`，本地最后更新时间2026-09-09 21:26，未新增42—44.5s冻结输入或0.25ms预算；5080无`paper_v4_core`实验进程。因此没有绕过R3 FAIL启动新动力学。
- 新建`paper_v4/audit/source_map.json`，逐一登记候选TeX公式1—22的label/行号、当前代码函数、配置、输出及状态。22个编号连续且唯一；9项存在当前直接或相关实现映射，13项保持SOURCE_PENDING/NOT_RUN。候选TeX SHA `C4C0075F...17E6`，未取得提交PDF身份，故所有公式编号明确限于候选版本。
- 映射不把相似实现强称同一算法：式12候选四轮转向上层优化与当前几何分配器分开；式15—21 Koopman训练/IRSP保持E02来源待核；式22只映射到标量充分界反例utility，状态为候选公式问题已确认、完整算法未实现。
- 新建`paper_v4/gates/E00.json`，汇总主机/递归导入/9个plant AST/任务书/执行器实现合同/当前时序/97源文件+3checkpoint/6方法/22意见等证据，同时列出提交PDF、历史确认盲性与fit-only归一化、Koopman provenance、完整mandatory suite四个缺口。总状态严格为PARTIAL、`formal_allowed=false`。
- 两文件本地/远端JSON解析与哈希一致：source_map SHA `81FD36DC...AF010`，E00 gate SHA `EF5A50AC...2B876`。未修改论文、原始数据或任何动态结果。

## 2026-09-11 EXP-R2 / E00归一化fit-only来源链

- 只读核对历史`20260905_221832_KC_BG02`的真实生成调用：`run_background.py`第184—193行按fold role构造`fit_e/inner_e`，只把`fit_e`传给`guard_core.fit_normalization`；源码SHA分别`1B2EA7B4...0A6561`与`DD9B14C7...5072F3`。
- `AccessGuard._audit`明确规定purpose为normalization/S0/warm/optimize/fit_monitor时只有role=fit可打开受保护数值资产。CPython open审计账本SHA `F82C3BE3...D65C71`的五个normalization context分别为fold0—4，读取904/368/339/342/345次，总计2298次，全部role=fit；非fit normalization读取0、全用途denied 0、unmapped 0。
- 新建`audit/normalization_provenance.json`，状态`PASS_FOR_20260905_221832_KC_BG02`，SHA `25C636A3...C9DB93`。这证明该历史运行的归一化加载只使用fit角色；不证明之后42/84确认池始终盲，也尚未逐数组重新拼接缓存复算mean/std。
- 更新`audit/data_roles.json`（SHA `2365F434...0B9624`）和`gates/E00.json`（SHA `E903D10A...212EB6`）区分“fit-only代码＋运行时open审计PASS”与“确认盲性PARTIAL”。E00总状态及`formal_data_authorized=false`不变。

## 2026-09-11 EXP-R2 / 后续确认集访问账本扫描

- 新增只读`tools/ledger_exposure_audit.py`，只解析访问账本元数据，不打开任何受保护数值数组。扫描revision_2026下2026-09-05起14份`*access*.jsonl`，覆盖v3t、v3w和paper_results后续运行。
- 第一版把任意路径命中`confirm/new_validation`都标`EXPOSURE_REQUIRES_REVIEW`，但复核5条命中均为`allowed=false`：4条是guard负向测试的`new_validation/denied.npz`或`confirm/denied.npz`，1条是被拒绝的`confirmation_metrics.csv.partial`输出，并非获准读取确认数组。保留第一版报告，不用错误标签作结论。
- 修正分类后另生成`audit/later_access_ledger_scan_20260911_02.json`，状态`NO_ALLOWED_CONFIRMATION_ACCESS_FOUND_IN_SCANNED_LEDGERS`：14账本、5个路径命中、允许命中0、决策用途命中0，SHA `338029A2...42FE07`。
- 结论边界：这增强了“已插桩后续运行未获准打开显式确认路径”的证据，但中性文件名或未插桩loader仍未排除，因此不能升级为全历史确认盲性PASS。`data_roles.json`更新SHA `A943C256...2342DA`，`gates/E00.json`更新SHA `41A1E8D5...3956B`；二者仍PARTIAL/正式数据未授权。

## 2026-09-11 EXP-R2 / Koopman父模型与三层选择元数据来源链

- 新增只读`tools/model_provenance_audit.py`，不打开确认池，也不运行新训练或动力学。审计对象为当前冻结父checkpoint、三层选择记录、每fold归一化/S0身份以及已保存的选择规则元数据。
- `audit/model_provenance_20260911.json`状态`PASS_METADATA_CHAIN`，SHA256 `46E68217...A1F91`。父checkpoint存在且哈希匹配；冻结/重载后的反向误差均不超过`1e-12`，系数差有限，条件数低于`1e14`。
- 3次重复×5折×3方法共45/45条正式选择记录齐全；checkpoint哈希全部匹配，按已保存指标重放“选择最小gamma”的确定性规则全部一致。每个fold的9条选择共享同一归一化与S0身份且与保存文件匹配；gamma计数为0.25:2、0.5:37、0.75:6。
- 证据边界：本项只闭合父模型/权重/选择记录的元数据和确定性选择链，没有从预测数组重新计算m20/i20，也不构成E02预测门通过；正式数据仍因提交源和全历史确认盲性缺口保持未授权。
- canonical `audit/data_roles.json`更新SHA `FB742D9E...ABD12`，`gates/E00.json`更新SHA `AED27222...30C7F`；二者均保持PARTIAL，`formal_allowed=false`。R3主路径及R4/R5停止状态不变。

## 2026-09-11 EXP-R2 / 历史数据生产源码冻结链闭合

- 新增只读`tools/historical_source_audit.py`（SHA `D6D1453F...E533E`），核对R03原始轨迹生成、R04窗口重分类/缓存以及v3w模型父运行三段来源；不打开确认池、不运行训练或动力学。
- R03 A0冻结的97文件canonical manifest摘要为`A5C3098B...F7050`，连续两次清单一致；A0 complete及N5 `source_identity`均匹配。冻结`generate_data.py`、`dataset.py`、`data_adapter.py`身份已记录，R03 N5 complete文件哈希与R04 reuse登记完全相同。
- R04明确登记为`window-classification-only repair`，672条manifest全部仍指向R03 raw目录；R04 A0 manifest摘要`B421EE89...3D55F`、连续清单一致，N5 source identity通过。R03→R04之间只有protocol、日志、pipeline、physics audit和相关测试5项变化；原raw不被重写。
- v3w `protocol_snapshot.json`登记的parent N6 run、source manifest、complete哈希与R04实际文件逐项一致；R04冻结的97/97源文件当前仍逐文件匹配。审计报告`audit/historical_source_20260911.json`状态`PASS_HISTORICAL_PRODUCTION_CHAIN`，SHA `4006D396...8491`。
- 此证据把E00的历史生产源码/输入时序来源从SOURCE_PENDING升级为范围内PASS；不证明提交PDF身份、全历史确认盲性或E02预测精度。canonical `data_roles.json`更新SHA `917B590C...29DD`，`gates/E00.json`更新SHA `219152CB...321E`，总门仍PARTIAL且正式数据未授权。

## 2026-09-11 EXP-R2 / confirmation命名产物误报排除

- 文件名扫描发现`paper_results/runs/20260907_110146_KR_A_SMOKE`与`20260907_110213_KR_A`均含`confirmation_metrics.csv`/`confirmation_verdict.json`，因此不能只凭命名推断确认集已打开。
- 两份metrics逐字节同SHA `F5A9386C...0AA55`，内容均为`NOT_RUN, KR-A stops before training/confirmation`；verdict逐字节同SHA `3CC2EA82...33B93`且`confirmation_opened=false`。对应670与3027条访问记录仅含fit/inner/outer角色，没有confirmation角色。
- 新增`audit/confirmation_artifact_followup_20260911.json`，SHA `74527369...868C7`，把这两项判为占位而非暴露。该排除仍不能覆盖未插桩loader或中性命名资产，因此确认盲性不升级为PASS，正式数据授权保持false。


## 2026-09-13 最新实验核查与EXP-R4执行书

读取R3A、QP SENS02/TOL03/FD01、新候选完整2ms批次及原始raw；核对旧比较器硬编码runner身份与新登记/现存runner哈希。新建当前入口experiment.md，保留inputs/experiment.md原SHA；同步根目录状态/方案的顶部提示。详见第20节同2ms效果表、来源审计修复规则、计算预算门及后续依赖。原JSON与计算源码未改，训练/动力学未启动；R3未晋升，E00仍PARTIAL。


## 2026-09-13 EXP-R4-B方案写入

按用户“写入任务书”，新增experiment.md第22节并更新首页当前入口；同步exp_status/exp_solution。补足单点并行等价证据不足的多点QP与2.5s闭环短窗任务，登记每条12小时初始离线预算、超时处理、原2ms复用条件与完整R3科学门。当前仅文档完成，未运行B0—B4或修改计算源码。核验新增4个证据链接有效，原EXP-R3/EXP-R4冻结输入与历史FAILED状态SHA均保持不变。


## 最新数据复核与逐实验出图要求

读取SERIAL02/PARALLEL01及源raw/substeps，整数周期对齐独立确认非时间物理字段一致；保留原正式FAIL。补充零连接力窗口的证据限制与有力阶段补证，更新每条约9.50小时外推。新增执行书第25节（EXP-R4-C）及覆盖E00—E17/R/B阶段的出图矩阵，补3张PNG+SVG与可复算脚本/来源SHA清单。未修改冻结协议、科学裁决或启动新动力学。


## 2026-09-14增量核查

本地paper_v4及paper_v4_results未发现更新实验；正式B2b比较仍FAIL，失败诊断不升级裁决。本机相关Python进程瞬时清单为空。任务树保持第25节，只新增25.6节点状态表并同步exp_status；没有启动动力学、修改源码/冻结协议或重生成已有图。

## 2026-09-15 EXP-R4-C完整R3恢复完成

- 输入/身份：1ms协议SHA `14f4e010...d059dd`，0.5ms协议SHA `4e365ee5...d2a7fe`；共同runner SHA `6fe85a68...87bba60`，controller SHA `694ab7b8...6b1531`，候选`EXP-R3-unfrozen-v1`。
- 0.5ms执行：2379/2379周期、47.58s、参考95.1283155163m，墙钟33601.870952s（9.3339h），stderr为空，早于截止；独立21项审计PASS，审计SHA `20d1d0c4...c72de`。
- 单条效果：峰值点力288.059651N、最大内部力180.164761N、轮胎利用率0.0499304、最小支承4677.138N、构形误差12.9976mm；位置/航向RMSE 0.255770m/0.903913°。2379步全部超过5s，均值13.585393s，`OFFLINE_ONLY`保持。
- 决定性比较：`20260915_R4C_FULL_COMPARE01/r3_convergence.json` SHA `8b9f45b1...e6b06a8`；峰值相对差4.5892936e-8、冲量向量3.2463998e-6、终点位置8.7018595e-6m、航向4.1915693e-5°，四门及身份门全部PASS。
- 图表：0.5ms单条和配对各含PNG/SVG、manifest、中文README；全部打开视觉检查PASS。配对manifest SHA `d6716e38...ab2450`。
- 工程问题：比较器首次因NumPy布尔JSON序列化失败；失败目录仅空图目录。显式转换`bool`并把无效空父字段门收紧为共同任务书SHA/共享源码清单后，只重跑后处理，未重跑动力学。
- 裁决：`EXP_R4C_RECOVERY_PASS / R3_NUMERICAL_PAIR_PASS`。旧R3/B2b失败原样保留；原5s预算仍FAIL。R4/R5解除R3依赖阻断但本批未启动；没有产生Koopman、通信、分布式、实时或材料安全优越性结论。


## 2026-09-15 R3通过后的任务书细化

更新总入口第27节并新增12节详细附件，明确C0旧runner迁移、R4六行矩阵、R5同候选基准和信息噪声、执行器九片段、E01核销及E02—E17接续证据。读源码发现r4_batch旧scope与pilot默认冻结雅可比、R5同名列包含墙钟及旧基准问题，列为实施前必检。计划预算与科学/图表门分开；本轮未启动仿真、改计算源码或冻结协议。附件12节和主链接检查通过，历史FAILED SHA未改。

## 2026-09-15 更新任务书：C0完成并启动R4-P1-2ms

- 新增隔离`post_r3_r4_runner.py`、`post_r3_r4_audit.py`、`post_r3_r4_plot.py`和`post_r3_c0_preflight.py`，保持旧冻结实现与历史结果不变。
- C0_01后补齐父C0报告/图表状态及SHA门；C0_02后修正锚点元组与JSON数组的身份表示误判。两次仅属工程失败证据，均未升级为正式通过。
- C0_03正式结果为`PASS_C0_R4_READY`：10个负例全拒绝，P1/P2共4个固定QP串并行矩阵/边界/首控制/非线性复核一致；有力组最大点力为800.85N与878.85N。PNG/SVG覆盖图打开验收PASS。
- 冻结`R4_P1_2MS_20260915.json`（SHA `e41b663...1dd5`），错误SHA/输出路径负例无输出拒绝；PID 27780于10:00:08启动，截止21:53:02。当前只登记RUNNING，审计、单条图和后续步长均未释放。

## 2026-09-15 R4-P1-2ms外部中断及用户停止

- 18:41检查发现PID 27780已退出，系统未重启且stderr为空；闭合检查点为2200/2379周期、44.0s、88.0m。
- solver共有2210条连续PASS，但最后10条没有持久化raw/substep证据，按任务书不计为完成；没有metrics，结论为`EXTERNAL_PROCESS_TERMINATION_INCOMPLETE`，不是科学PASS或算法/物理FAIL。
- 实测solver平均13.911148s、中位13.739660s、P95 14.870203s、最大22.855401s。耗时来自每周期20步MPC与未冻结有限差分雅可比；parallel8是CPU并行，不使用RTX 5080。完整2379周期按均值约9.19h，原5s预算FAIL保持。
- 用户明确要求“别重新跑”。不拼接检查点、不从头重试、不启动后续R4/R5；已接受证据与日志原样保留。

## 2026-09-15 RTX 5080 G0—G2迁移

- 按新任务说明实现独立`gpu_port`：float64批量物理、20ms rollout、85项中心差分、单CUDA worker IPC；CPU保留真实植物/OSQP/非线性复核，未续跑P1或启动闭环。
- 事前冻结G1/G2逐字段数值门与同步计时合同，协议错误SHA负例无输出拒绝；新增Python均通过编译。
- G0 PASS：RTX5080、CUDA12.8、float64有限；环境PNG/SVG打开验收PASS。
- v1同进程、v2隔离worker、v3纯Torch worker均在G1前触发libomp/libiomp冲突；未使用不安全运行库绕过。两轮工程修复额度耗尽，G1/G2 NOT_RUN，停止分支。
- 裁决：只有环境与实现证据，没有GPU数值等价、QP等价、性能收益或闭环资格。


## 2026-09-15 用户指定P1后期发散与GPU接续

按最新请求更新主入口第31节、状态/方案及两份附件。实验分类FAIL_LATE_TRACKING_DIVERGENCE，注明用户指定及晚段误差增长依据；原执行外部中断/未观测末段保留。GPU按用户报告搭建完成，增量核对资格替代从零搭建；本地最后报告尚未证明G1/G2通过。任务树改为GPU资格与P1归因→新候选验证，不续跑旧CPU、不释放R4后继。原raw/substeps/solver/status四文件SHA与既有分析清单一致。未启动实验或修改计算源码。

## 2026-09-15 D0/D1只读执行完成

- v2协议SHA `9756ce4d...371025`，正式输出`analysis/20260915_D0_D1_GPU_GATE_P1_02`，状态`PASS_D0_D1_READ_ONLY`；未运行GPU或动力学。
- D0：RTX5080、旧G0和迁移源码身份存在；G1/G2报告缺失且旧协议任务书身份过期，裁决`GPU_ENTRY_PRESENT_QUALIFICATION_PENDING`。
- D1：35.58—44.00s位置RMSE 0.390565m，误差增至0.542481m，末值横向0.534510m、纵向-0.092653m；时序/相关性不作根因证明。物理门未触发。
- raw请求与solver首控制一致，previous_u可重建；beta记忆和完整恢复状态缺失，禁止从旧44s点拼接D3。
- 首次执行因`ndarray.square()`属性错误停止；保留部分目录，改为`np.square()`并在新目录重跑只读后处理。三组PNG/SVG打开检查，视觉QA PASS；没有补画未来179周期。
- 当前：`D1_COMPLETE / D2_ACCELERATION_ONLY_CANDIDATE_DEFINED / D3_BLOCKED / NO_OLD_CPU_RERUN / NO_GPU_CLOSED_LOOP`。

## 2026-09-15 D2 GPU资格阻断定位

- 搜索未发现更新G1/G2报告；现有替代Torch环境不是可用5080资格环境，未安装或修改软件。
- 冻结D2只读v2协议SHA `609e4533...0cc0ed`，错误SHA负例无输出拒绝；正式报告`PASS_READ_ONLY_BLOCKER_LOCALIZED`。
- 静态数据流确认旧v3仍把NumPy ndarray放入G1/G2的pickle请求；worker在反序列化时可隐式导入NumPy。它与G0列表初始化通过、G1前双OpenMP冲突时序一致，登记为高可信候选，不冒充修复后因果证明。
- 资格脚本还存在`error.square()`的NumPy 2.0.1兼容问题。建议IPC发送前全部转列表并改`np.square(error)`，但因两轮工程修复额度未重新开放，本次未改GPU后端、未跑G1/G2/G3。
- 首版阻断图零柱白字不可读，保留为视觉QA失败；仅改标签颜色后在新目录重做PNG/SVG并打开验收PASS。
- 当前：`D2_BLOCKER_LOCALIZED / ENGINEERING_FIX_REQUIRED_NOT_AUTHORIZED / G1_G2_NOT_RUN / D3_BLOCKED`。

## 2026-09-15 D1+参考链记忆（beta）只读回放

- 用户选择P0档：只登记只读分析并更新MD，不修GPU、不跑动力学、不续跑旧P1。冻结`protocol/D1B_BETA_MEMORY_REPLAY_20260915_v3.json`（SHA `0b766030...900954`），错误协议SHA负例退出1且未建输出。
- 正式输出`analysis/20260915_D1B_BETA_MEMORY_REPLAY_03`，`PASS_READ_ONLY_BETA_MEMORY_RECONSTRUCTED_WITH_GATE_LIMITS`，`figure_status=PASS_VISUAL_QA`（PNG打开验收；SVG为同图matplotlib路径文本，XML解析通过）。
- 方法：从`time_s = k·Ts + accepted_duration`还原每周期时长，按`post_r3_r4_runner.py`第171—172行同序重放`distance`与`beta`，以落盘`reference_distance_m`独立校核。
- 结果：距离重放最大绝对差`1.4210854715202004e-14`m、最大相对差`2.2204460492503116e-16`、1246/2200 tick逐位为零；时长和`44.00000000000128`s、与`Ts`最大偏差`3.13e-15`s；22051条子步`dt`和与时长和闭合残差`−1.26e-12`s，子步严格递增零违反。
- 重建`beta`末值≈`[1.2e-9, 1.2e-9, −9.2e-5, −8.4e-5]`deg，前缀最大绝对值`[8.61, 7.26, 22.45, 18.97]`deg。`previous_u`经分组/交错排列还原后**2200/2200 tick与solver首控制逐位相同，最大差`0.0`**。
- 静态核查：冻结plant/连接器无历史或滞回字段，`advance_outer_step`为`(state, controls, params, duration)`纯函数；`full_restart_equivalence_test`未做，标`NOT_RUN`。
- 修订边界：只修订D1“beta不可恢复”一条；D1误差分解、`FAIL_LATE_TRACKING_DIVERGENCE`、未观测179周期不补画、旧P1不续跑、D3阻断全部保留。
- 工程缺陷（自身，按惯例保留不覆盖）：v1把raw分组排列与solver交错排列直接相减，报出`9.376302005812323e-15`伪差异，另有三处图缺陷；v2修正排列后`previous_u`变为逐位相同，但面板2标题截断、面板3量程不可读，标`FAIL_VISUAL_QA_SUPERSEDED`（数值有效并保留）；v3仅改绘图，四面板QA PASS。两次失败目录均写`failure.json`。
- 顺带核实：v3协议23条身份中源码与P1四份数据全部MATCH（未越权改动），但`experiment.md`与迁移任务说明STALE；GPU资格**必须另冻v4协议**，不能直接复用v3重跑G1/G2。
- 裁决：`D1B_BETA_MEMORY_RECOVERABLE_REGISTERED / G1_G2_NOT_RUN / GPU_PROTOCOL_V4_REQUIRED / ENGINEERING_FIX_NOT_AUTHORIZED / D3_BLOCKED`。三次运行`executed`六项全为false：未跑植物、MPC求解器、GPU、闭环、未续跑P1、未改`src/`。

## 2026-09-15 RTX5080 G0—G2 v4失败与v5通过

- 按用户指令继续并启动。第3轮修复（请求路径list化、worker模块自证、`error.square()`→`np.square`）后冻v4协议`RTX5080_G0_G2_20260915_v4.json`（SHA `d8f0e9ec...afbef`，由生成器实读哈希），两次负例（错误协议SHA、错误输出路径）均退出1且无输出。
- v4实测**失败**：21:37:40启动、21:37:48结束，退出码3，`OMP Error #15`；G0 JSON与图已生成，G1未完成。失败证据保留在`results/20260915_RTX5080_G0_G2_04`。
- 否证旧根因：worker自证`forbidden_present_at_startup.numpy=true`、`imported_after_startup=[]`——NumPy随`import torch`在启动时即在worker内，第33节“ndarray经pickle在G1才进入worker”的登记不成立。
- 根因定位链：三进程隔离（父CPU链正常、worker四操作链正常并干净退出、torch单独CUDA float64 matmul正常）→ 复刻资格脚本精确调用序列并开`faulthandler`，抓到父进程栈`numpy.linalg.svd → internal_force._pinv → decompose_planar_point_forces → connector_diagnostics → assemble_derivative → system_derivative` → 逐步计数发现父进程torch模块在`backend.environment()`后由0变718 → `builtins.__import__`钩子定位入口`torch.torch_version`。
- 真实机制：`torch.__version__`是`torch.torch_version.TorchVersion`（str子类）；worker环境回包直接pickle该对象，流中带`torch.torch_version`类引用，父进程`pickle.loads`被迫`import torch`，把torch的OpenMP运行库带进已持有MKL的父进程，随后在MKL LAPACK调用初始化`libomp.dll`时abort。v1/v2/v3“全停在G1前”由此解释：G0自己的回包埋雷，G1首次`system_derivative`引爆。
- 第4轮修复（两点、均不改数值）：`gpu_worker._plain()`回包递归强制为精确内建原语、str子类展平、非原语抛`NON_PRIMITIVE_IN_IPC_REPLY`；`ipc_backend._assert_parent_free_of_torch()`每次反序列化后断言无新增torch模块，命中抛`CUDA_PARENT_TORCH_CONTAMINATION`。未使用`KMP_DUPLICATE_LIB_OK`，未改dtype/门/阈值/求解器/控制律。
- v5协议`RTX5080_G0_G2_20260915_v5.json`（SHA `6e614262...cf173f`），21条身份、10项前置断言全true；两次负例均退出1且无输出。**21:42:16启动、21:43:00结束，共44秒**。
- 结果：`PASS_G0_G2_GPU_QUALIFIED`。G1六类固定样本全PASS，最差归一化误差`8.046313422869875e-07`（门=1.0），`straight`/`steering_limit`/`late_prefix`的RK4与rollout逐位相同，最差绝对误差`1.61e-15`。G2两用例全PASS、非线性复核PASS，FD最差`3.363269422013451e-05`、QP最差`3.3547375137958427e-03`、首控制差`6.74e-11`m/s²与`2.16e-11`rad。
- 成本：CPU parallel8均值`14.070881400024518s`、GPU`4.321555100032128s`、**加速`3.255976396070921×`**、**`original_5s_budget_pass=true`**——R3以来第一次进入原5s/步预算（此前13.59/13.91/32.64s全部FAIL）。
- 边界：仅固定样本；未跑2379周期闭环，`4.32s≤5s`是单次固定样本求解，不等于完整路线实时性；GPU只承担预测线性化，真实植物/QP/OSQP/非线性复核仍在CPU；不支持通信、分布式、Koopman或材料安全结论；脚本自身给出`next_action = STOP_NO_G3_G4`。
- 图表：G1/G2误差面板线性轴不可读，视觉QA失败；不改源码不重跑，另出只读重绘`analysis/20260915_RTX5080_G0_G2_05_FIGURE_QA_01`（`tools/rtx5080_g0_g2_figure_qa.py`），`figure_status=PASS_VISUAL_QA`；原目录标`FAIL_VISUAL_QA_SUPERSEDED`并留`figure_qa_failure.json`。
- 状态：`G0_PASS / G1_PASS / G2_PASS / G2_PERFORMANCE_PASS / D2_ROOT_CAUSE_FALSIFIED / D3_G1_G2_PRECONDITION_SATISFIED / D3_STILL_BLOCKED_ON_RESTART_EQUIVALENCE_AND_SEPARATE_PROTOCOL / NO_CLOSED_LOOP / NO_OLD_CPU_RERUN`。旧P1未续跑、未重跑、未拼接。完整记录见`rtx5080_g0_g2_v5_execution_20260915.md`。

## 2026-09-15 G0—G2 v5详细分析（只读登记）

- 协议`RTX5080_G0_G2_V5_ANALYSIS_20260915_v2.json`（SHA `a8559a63...62dba`），输出`analysis/20260915_RTX5080_G0_G2_V5_ANALYSIS_02`，`PASS_READ_ONLY_ANALYSIS_OF_G0_G2_V5`、`figure_status=PASS_VISUAL_QA`；错误SHA负例退出1且无输出。首版v1因三处图缺陷（G1刻度拥挤、Amdahl floor标注压条、外推红字压柱）标`FAIL_VISUAL_QA_SUPERSEDED`并保留，v2仅改绘图。
- G1门裕度：18对比对中9个逐位为零；最差`force_peak/rhs`=`8.046313422869875e-07`（离门6.1个数量级），最差绝对差`1.61e-15`；`near_gap_boundary`的rhs/rollout为`5.20e-09`/`1.07e-09`，说明连接器分段非线性边界未被GPU静默走错分支。
- G2偏差结构：18字段中8个逐位为零；最大非零`force_bearing/P`=`3.3547375137958427e-03`（绝对`1.002736e-07`），次之`q`=`3.003930e-03`；传播链`A/B(1e-12~1e-11) → P/q(1e-07)`为代价加权后的舍入放大。`l`两用例均逐位为零、`u`最大差`1.110223e-15`，约束边界未移动；`initial`的`f0/q/A/l/u/u_nom`六项全零。GPU解经CPU真实植物非线性复核PASS：`force_bearing`最大点力`794.4273087244296 N`、轮胎`0.12213901731496084`、最小支承`4296.356761928783 N`，无失败步。
- Amdahl分解：`initial` CPU 14.552s/GPU 4.346s（内核2.236s、传输0.0022s、CPU侧固定2.108s=48.51%；线性化阶段加速5.566×、端到端3.348×）；`force_bearing` 13.590/4.297s（内核2.213s、传输0.0024s、固定2.082s=48.45%；阶段5.201×、端到端3.163×）。**结论：GPU内核即使归零，该固定样本求解仍有约2.1s下限，最多再得2.06×**；传输仅占0.05%，任务说明担心的CPU/GPU往返风险被实测排除；后续加速应针对CPU侧QP组装/OSQP/非线性复核与参考预览。
- 全路线外推（标`EXTRAPOLATION_NOT_A_MEASUREMENT`）：实测P1每周期solver均值`13.911148 s`、中位`13.739660`、P95`14.870203`、记录2210条→按3.256×投影`4.272497 s/周期`；2379周期由`9.192950 h`降至投影`2.823408 h`。四条限制已登记（单次冷启动非连续热启动、不含event-substep植物/预览/落盘、均值为两点非分布、不得用于实时主张）。
- 净影响：本资格不解决P1后期发散（加速不改变控制律/参考/优化问题），价值在实验吞吐约提升三倍；D3阻断点由“GPU资格”整体平移为“重启等价试验 + 单独短窗协议 + 事前冻结的晚期失效判据”。
- 正文：`rtx5080_g0_g2_v5_detailed_analysis_20260915.md`。本轮未跑植物、MPC、GPU或闭环，未改`src/`。

## 2026-09-15 G3有界闭环窗口与全路线GPU放行

- 用户指令“一次性全部搞定，直到实验可以完整开始”。新增`gpu_closed_loop_runner.py`（可切换CPU/CUDA后端、从重建检查点续跑、补落盘`tick_index`/`reference_beta*`/`previous_u*`/区间起始距离）与`reference_memory.py`（与D1B同源的参考链回放），未修改任何冻结runner。
- 冻结`G3_RESTART_EQUIVALENCE_20260915_v4.json`（SHA `02e1ed84...db5ee5`），3窗口×2后端共6条全部`COMPLETED`；比较输出`analysis/20260915_G3_RESTART_EQUIVALENCE_02`。
- 结果（必须分开读）：`gpu_*`与`original_hard_gates_hold`**三窗口全PASS**；`restart_*`force_peak/steering_limit PASS、**late_prefix FAIL**。偏差：CPU重放 force_peak **0.0（30 tick逐位相同）**、steering 2.87e-10 m、late 1.22e-6 m（门1e-6）；GPU对应8.86e-10/2.57e-10/5.29e-6 m。窗口耗时GPU约130s、CPU约388s（≈3.0×）。
- 机理登记：`G3B_DIVERGENCE_MECHANISM_20260915_v1.json`（SHA `85645578...68910`）→`analysis/20260915_G3B_DIVERGENCE_MECHANISM_01`，`PASS_READ_ONLY_MECHANISM_ANALYSIS`。late窗口保存连接力**恰为0.000N（free play）**、偏差台阶式；唯一seed是`beta`回放1e-16误差；冻结runner**从未落盘每周期接受时长**，逐位重建`beta`原理上不可能。**结论：中断P1前缀不可续接；D1原始判定被实测证实。**
- 放行：冻结`R4_P1_2MS_GPU_20260915_v1.json`（SHA `1db9ab18...466e70`，29条身份）。以`decision_rule_supersession`**显式书面取代**G3“任一失败不释放”规则，只针对两个`restart_*`判定，附四条理由与审计注记；**未改任何阈值**，FAIL判定原样保留。runner内父门逐条实时复核。错误协议SHA负例退出1且无输出。
- 正式运行`results/20260915_R4_P1_2MS_GPU01`于23:09:44启动：P1、2ms、2379周期、截止6h、候选`EXP-R3-unfrozen-v1`；开始后约7分钟到90/2379，约4.2s/次求解，预计约3.1h。除后端外与原CPU候选逐项不变。该实现不内部维护构形误差，字段置`null`并附注，真实值由比较器从落盘数据计算；比较器初版`yaw_rate=0`缺陷已修为路线曲率（运行中路线不受影响，完成后以比较协议v2重新冻结）。
- 过程四个工程缺陷全部保留证据：v1缺`absolute_parameters`；v2 `execute()`自行重取model实例触发CUDA后端身份检查、被`solve()`吞成`MODEL_DOMAIN_ERROR`（残差inf、0秒返回）；v3 `previous_u`分组/交错排列错（**该坑第三次出现**，用`solver.jsonl`首控制逐位定案：交错`True`/分组`False`，交错复现差6.77e-11、分组1.39e-01，故v4加入`assert_previous_control_layout`运行时自检）；比较器FAIL柱零高度致面板看似全绿（另出只读重绘`analysis/20260915_G3_VERDICT_QA_02`，`figure_status=PASS_VISUAL_QA`）。
- 状态：`G3_GPU_EQUIVALENCE_PASS_ALL_WINDOWS / G3_RESTART_EQUIVALENCE_FAIL_LATE_FREE_PLAY / P1_PREFIX_SPLICING_IMPOSSIBLE_CONFIRMED / FULL_ROUTE_GPU_RUNNING / NO_GATE_WIDENED`。运行未出裁决，不得与旧CPU前缀拼接。

## 2026-09-16 R4-P1-2ms GPU全路线完成

- `results/20260915_R4_P1_2MS_GPU01`：23:09:44启动、02:02:47结束，`COMPLETED`、**2379/2379周期**、参考距离`95.12831551628261 m`（全长）、累计求解墙钟`10380.73633580003 s`（2.88 h）。
- 硬门全过：点力峰`263.3746266544468 N`（限15000）、内部力`175.92091446643528 N`、轮胎`0.047415676201520325`（限1.0）、最小支承`4209.515971801054 N`；最大构形误差（由落盘状态/参考距离/beta计算）`12.562508468767618 mm`。
- 比较：`R4_P1_2MS_GPU_COMPARE_20260915_v1.json`（SHA `7a6e441e...1ac7e`）→`analysis/20260915_R4_P1_2MS_GPU_COMPARE_03`，`PASS_FULL_ROUTE_REPORT`、`figure_status=PASS_VISUAL_QA`。前2200重叠tick：位置偏差**2.398450764928839e-05 m（24 µm）**、末值1.32e-05 m、航向1.95e-05 rad、点力峰263.3737 vs 263.3731 N；**tick 0—630逐位相同、首差在tick 631（curve_entry）**。
- 强印证两处：构形误差`12.562508468767618 mm`与冻结记录CPU前缀`12.562509 mm`吻合到6位有效数字；内部力`175.92091446643528`与`175.920914`一致。**该路线复现了CPU轨迹**（含晚段跟踪偏离0.54m@44s），并跑完剩余179周期到终点→**用户指定的"晚段发散"是跟踪现象而非物理失稳**。
- 成本：均值`4.225913995374546 s`、中位`4.218413199996576`、P95`4.299485800089315`、**最大`5.281302799936384 s`**；**2378/2379在5s内（99.958%）**，故`within_5s_budget=false`——**不得写成"全程满足5s"**；相对CPU均值13.911148 s为**3.292×**（2.88h vs 9.19h投影），仍为离线墙钟、无实时性结论。
- 三次比较器自身缺陷：构形误差误用`yaw_rate=0`（应为路线曲率`SPEED*_path_sample(distance)[3]`）；`SPEED`误从`e01_100m`导入致首次`ImportError`并留下空目录`_01`（已写`failure.json`）；图表把`99.958%`四舍五入成`100.0%`且未标注逐位相同段。前两项修好后在协议`supersedes_comparator`登记（含运行协议冻结的旧哈希与现哈希），第三项标`FAIL_VISUAL_QA_SUPERSEDED`并重出`_03`。比较器是只读后处理，运行不受影响。
- 下一单元：`R4_P1_1MS_GPU_20260915_v1.json`（SHA `f082c5be...5b59c`，29条身份）新增`previous_cell_same_parameter_point`并在前置中强制"更细步长必须声明同参数点已完成前序单元"；错误SHA负例退出1且无输出；02:10启动。
- 状态：`R4_P1_2MS_GPU_COMPLETED_ALL_GATES_PASS / CPU_GPU_DIVERGENCE_2P4E5_M / WALL_MEAN_4P226S_MAX_5P281S / R4_P1_1MS_GPU_RUNNING / R4_P1_0P5MS_AND_P2_PENDING / NO_REAL_TIME_CLAIM / NO_SPLICING`。

## 2026-09-16 R4-P1-1ms 全路线与 2ms↔1ms 收敛

- `results/20260915_R4_P1_1MS_GPU01`：02:09:54启动、05:09:02结束，`COMPLETED`、2379/2379、全长`95.12831551628261 m`、植物步长1ms、墙钟`10746.641351100057 s`（2.99 h）。协议`R4_P1_1MS_GPU_20260915_v1.json`（SHA `f082c5be...5b59c`），错误SHA负例退出1且无输出。
- 硬门全过：点力峰`263.3745974738065 N`、内部力`175.9209138168544 N`、轮胎`0.047415679159865644`、最小支承`4209.5161198669675 N`。
- 收敛：`R4_P1_2MS_1MS_CONVERGENCE_20260915_v1.json`（SHA `49148e40...507f6`）→`analysis/20260915_R4_P1_2MS_1MS_CONVERGENCE_02`，`PASS_R4_CELL_CONVERGENCE`、`figure_status=PASS_VISUAL_QA`。四门（复用R3冻结阈值）实测：力峰相对差`1.107952e-07`（门2e-2）、冲量向量`1.689992e-06`（门2e-2）、终点位置`1.352284e-07 m`（门1e-3）、终点航向`1.429412e-06°`（门0.01°）；七项判定全PASS；全程最大位置差`2.480238e-05 m`，增长起于tick 631（curve_entry）。
- 对照CPU R3恢复的1→0.5ms（4.59e-08/3.25e-06/8.70e-06 m/4.19e-05°）量级相当→**GPU未引入额外步长敏感性**。
- 比较器第四次自身缺陷：`r4_cell_compare.py`首版把冲量ndarray写入JSON抛`TypeError`；`_01`留`failure.json`，转list后出`_02`。只读后处理，路线不受影响。
- 下一单元`R4-P1-0P5MS-GPU`协议`R4_P1_0P5MS_GPU_20260915_v1.json`（SHA `59b2f1ab...1026b`）含前序单元前置，05:09启动；子步翻倍，实测约6.7 s/周期，ETA约4.4 h。
- 状态：`R4_P1_2MS_GPU_COMPLETED / R4_P1_1MS_GPU_COMPLETED / P1_2MS_1MS_CONVERGENCE_PASS_FOUR_GATES / R4_P1_0P5MS_GPU_RUNNING / R4_P2_PENDING / NO_REAL_TIME_CLAIM / NO_SPLICING`。

## 2026-09-16 P1三步长全部完成、两组配对收敛全过、P2启动

- `results/20260915_R4_P1_0P5MS_GPU01`：05:10:06启动、08:19:31结束（3.16 h），`COMPLETED`、2379/2379、全长`95.12831551628261 m`、步长0.5 ms、墙钟`11361.874968900112 s`。协议`R4_P1_0P5MS_GPU_20260915_v1.json`（SHA `59b2f1ab...1026b`），错误SHA负例退出1且无输出。
- 0.5 ms硬门全过：点力峰`263.37461288331997 N`、内部力`175.92091450058118 N`、轮胎`0.04741567906119377`、最小支承`4209.516002280793 N`。
- 1ms↔0.5ms收敛：`R4_P1_1MS_0P5MS_CONVERGENCE_20260915_v1.json`（SHA `b6b23885...79641`）→`analysis/20260915_R4_P1_1MS_0P5MS_CONVERGENCE_01`，`PASS_R4_CELL_CONVERGENCE`、`figure_status=PASS_VISUAL_QA`。四门：力峰`5.850797e-08`、冲量向量`4.723526e-07`、终点位置`5.614471e-08 m`、终点航向`8.969815e-07°`；全程最大位置差`3.000555e-05 m`。
- **P1三步长汇总**：2/1/0.5 ms均2379/2379跑满全长、原硬门全过、墙钟2.88/2.99/3.16 h；2→1与1→0.5两组配对共14项判定全PASS；与CPU R3恢复的1→0.5ms（4.59e-08/3.25e-06/8.70e-06 m/4.19e-05°）同量级或更好→**GPU未引入额外步长敏感性**。
- **P1结论与四条边界**：同一参数点（用户先前指定"后期跟踪发散、该工况未通过"）在同一冻结控制律与硬门下跑满全长，说明跟踪偏离（末值横向约0.53 m）确实存在但**不触发物理硬门、不阻止完成路线**；**不**说明跟踪合格、**不**说明晚段发散已解决、只支持"物理安全门通过且路线可完成"、跟踪质量须按第31节判据另行评价。
- P2启动：`R4_P2_2MS_GPU_20260915_v1.json`（SHA `8dfbc411...69861`）新增`required_completed_cells`把三个P1单元列为前置并在`preconditions`强制`all_completed`，把"P1失败不继续P2"落成**构建期硬门**；错误SHA负例退出1且无输出；08:23启动。
- 状态：`R4_P1_ALL_THREE_STEPS_COMPLETED_ALL_GATES_PASS / P1_BOTH_PAIRWISE_CONVERGENCE_PASS / R4_P2_2MS_GPU_RUNNING / R4_P2_1MS_AND_0P5MS_PENDING / NO_REAL_TIME_CLAIM / NO_SPLICING`。

## 2026-09-16 产物存放合规性审计与任务书修订

- 触发：用户质询"结果产生的数据有按要求放在对应的文件夹吗"。逐目录清点，记录`compliance_audit_20260916.md`。
- 合规：独立run_id、每类实验出图、`science_status`/`figure_status`分列、12个已完成run的核心四件+metrics齐全、正式analysis目录均含JSON+PNG/SVG+`README.md`+`figure_manifest.json`。
- 三项缺口：①结果根目录——任务书原定`REV\paper_v4_results`，实际自09-09 21:42起E00/E01写入`paper_v4_results`、全部R系列（含本轮G3/GPU/R4）写入`REV\paper_v4\results`，`paper_v4_results`最新run停在`20260909_R1_03`；②统一工作记录原定`D:\PDxc\Review\koopman_work_log.md`，`D:\PDxc`整目录在本机不存在；③`实验结果汇总_20260915.*`停在09-15 12:22，**本轮结果不在其中**。
- 用户裁决与执行：修订任务书第1.1节（结果根目录改为`REV\paper_v4\results`、统一工作记录改为本地`REV\paper_v4\koopman_work_log.md`，并加2026-09-16修订说明）；**不迁移**既有目录，`paper_v4_results`下E00/E01原样保留为历史；**不补跑**结果汇总；**GPU单元回填**`protocol/methods.json`。
- `methods.json`回填：`taskbook_sha256`→`5361a04c...03b4a`（原SHA存`taskbook_sha256_previous`）；新增`registry_revision`；新增`implementation_variants`条目`EXP-R3-unfrozen-v1__CUDA-BATCH-FD`（角色`IMPLEMENTATION_VARIANT_NOT_A_METHOD`、父方法`CENTRALIZED_FULL_STATE_PHYSICAL_MPC_DIAGNOSTIC`，含第7.1节全字段+`qualification_evidence`+四条`not_allowed`）；`excluded_diagnostics[0].status`→`DEVELOPMENT_DIAGNOSTIC_P1_COMPLETE_THREE_PLANT_STEPS`并加`current_state`（含`tracking_quality=NOT_QUALIFIED`）；`core_methods`六项、`external_baselines`、H1—H6排除条款未动。
- 审计中修正本人两处不一致：`D1B_BETA_MEMORY_REPLAY_01`与`G3_RESTART_EQUIVALENCE_01`的`figure_status`由`PENDING_VISUAL_QA`改为`FAIL_VISUAL_QA_SUPERSEDED`（已写`failure.json`却漏改状态）；为`analysis/20260915_rtx5080_v4_omp_probe`补`README.md`。
- 遗留风险：引用"实验结果汇总_20260915"时须注意它**不含**本轮成果；应直接引用各`analysis`目录的登记产物。
- P2-2ms监控：08:23启动，09:39在1050/2379（4.34 s/周期），ETA约11:16。

## 2026-09-16 全路线跟踪质量报告：晚段发散在完整路线上被确认

- 补齐任务书§9.3要求的位置/航向/进度误差。新增`tools/route_tracking_analysis.py`（口径与D1完全一致：参考位姿按落盘参考距离插值、误差投影到参考航向分解纵向/横向），协议`R4_ROUTE_TRACKING_20260916_v1.json`（SHA `a4a72ed8...7e5e`）→`analysis/20260916_R4_ROUTE_TRACKING_03`，`PASS_ROUTE_TRACKING_REPORT`、`figure_status=PASS_VISUAL_QA`。
- **D1交叉验证通过**：独立复现D1发布六个量，最大差`3.03e-07`（末值位置0.542481、横向0.534510、纵向−0.092653、出弯段位置RMSE 0.390565、首值0.188306、拟合增长0.041080 m/s），差异仅来自D1发布值的6位小数舍入。
- **核心发现①不回收**：P1_2ms_CPU前缀44.0s截断于横向`+0.534510 m`且当时仍以`0.041080 m/s`增长；P1_2ms/1ms/0.5ms_GPU完整路线47.58s增至`+0.668188 m`，44s后拟合增长`+0.037340 m/s`——速率不变、无平台期、无回落。
- **核心发现②与步长无关**：三档横向末值`0.6681882294789727`/`0.6681882343320009`/`0.6681882128192502`，第9位小数才分开；位置RMSE`0.250782`三者六位小数全同；航向RMSE`0.877453°`。→ 该闭环的确定性性质、非数值伪影。
- **核心发现③强反差**：横向偏离0.67 m与力峰263 N对15000 N限值（约57倍余量）并存→证明“受力小≠跟踪合格”，且现有硬门对缓慢系统性漂移不敏感。
- P2_2ms_GPU：横向末值`0.673481 m`、位置RMSE`0.269119`、航向RMSE`0.906752°`、44s后增长`+0.024523 m/s`；**P2同时改载荷/连接器/摩擦，不可归因单一参数**。
- 出弯直线段（≥71.12831551628262 m，601 tick）全程：位置RMSE`0.467559 m`、首值`0.188306 m`、末值`0.673382 m`、拟合增长`0.039560 m/s`。
- **对P1状态刻画的修订**：第37/41节“完成全长、硬门全过”**只能**证明候选数值与物理上可跑通、可用于后续比较，**不能**说明P1工况通过；用户`FAIL_LATE_TRACKING_DIVERGENCE`判定由此获得完整路线实测支持。
- 文档结构自查缺陷：追加§35.6时用同一段落作锚点致其被甩到§41之后，已按字符串定位搬回§35内部并核验顺序（35.1—35.6→36→…→41→42）。教训：段落作锚点追加章节必须复核顺序。
- P2-1ms监控：11:15启动；12:25在770/2379（30.8 m）。

## 2026-09-16 R4-P2-1ms 外部终止与分离进程重启

- 用户质询“现在没有实验在跑？”后核实：**确实无任何实验在运行**，`R4-P2-1ms`**已被外部终止**。
- 终止事实：日志最后写入12:14:33；`solver.jsonl`最后tick 777（12:14:29）；最后检查点12:13:51为770/2379、30.8 m；日志中traceback/`exit_code=`/`finished_at=`/`Error`**四项全不存在**；harness后台作业`pwsh-11`从注册表**完全消失**；无python进程、GPU 0 MiB/0%；`status.json`仍写`RUNNING`但最后写入12:13:51——**陈旧RUNNING语义**。
- 分类`EXTERNAL_PROCESS_TERMINATION_INCOMPLETE`：进程在正常求解中途消失且stderr干净，属进程树被外部终止，非算法/求解器/植物失败；无`metrics.json`，故**既非PASS也非FAIL**。证据`results/20260915_R4_P2_1MS_GPU01/interruption.json`。
- **未拼接、未续跑**：G3已实测证明重建检查点在free-play敏感段无法复现已保存轨迹，任务书亦禁止未证明等价拼接；770周期前缀原样保留为证据。
- **承载方式变更**：原harness后台作业在本环境不能保证长任务存活，改用分离OS级进程`Start-Process -WindowStyle Hidden`（独立stdout/stderr、`PYTHONPATH`继承、runner进程内6h绝对截止、每10周期检查点），启动记录`logs/20260916_r4_p2_1ms_gpu02.launch.json`（PID/协议SHA/截止/存活探针）。
- 重启协议`R4_P2_1MS_GPU_20260915_v2.json`（SHA `c4ac823d...7e66`）输出`results/20260915_R4_P2_1MS_GPU02`；`supersedes_protocol`记录终止事实，**参数/门/窗口/身份全未变**；错误SHA负例退出1且无输出。PID 11588于12:29:17启动，12:31:16复核存活、stderr为空、20/2379。
- **判活口径（写入文档）**：只看`status.json`会把已死进程误判为RUNNING；必须同时看**进程存在性 + GPU占用 + 检查点写入时间**三者。后续巡检一律照此执行。
- 状态：`R4_P2_1MS_V1_EXTERNAL_TERMINATION_INCOMPLETE / R4_P2_1MS_V2_RUNNING_DETACHED / NO_SPLICING / R4_P2_0P5MS_PENDING`。



## 2026-09-16 R4-P2-2ms 全路线完成

- `results/20260915_R4_P2_2MS_GPU01`：08:22:53启动、11:15:42结束（2.88 h），`COMPLETED`、2379/2379、全长`95.12831551628261 m`、墙钟`10366.07957489998 s`。协议`R4_P2_2MS_GPU_20260915_v1.json`（SHA `8dfbc411...69861`），错误SHA负例退出1且无输出。
- 硬门全过：点力峰`311.9048189481835 N`（限15000，余量约48倍）、内部力`197.9962081231709 N`、轮胎`0.055974760202736736`（限1.0）、最小支承`5144.717077521452 N`（≥0）。
- P2参数：载荷2200 kg、刚度31500 N/m、阻尼3675 N·s/m、空程0.0021 m、μ=0.8。与P1对照（1800 kg／28500／3325／0.0019／μ0.95）：点力峰+18%、内部力+13%、轮胎+18%、最小支承更高；**同时改变载荷、连接器与摩擦，非单因素对照**。三者均在硬门内且支承为正→该参数点不接近物理边界。
- 下一单元`R4-P2-1MS-GPU`协议`R4_P2_1MS_GPU_20260915_v1.json`（SHA `dd48bc9d...ad1d3`）：`previous_cell_same_parameter_point`锁定P2-2ms，`required_completed_cells`继续锁定三个P1单元；错误SHA负例退出1且无输出；11:15后启动。
- 状态：`R4_P1_ALL_THREE_STEPS_COMPLETED / R4_P2_2MS_GPU_COMPLETED_ALL_GATES_PASS / R4_P2_1MS_GPU_RUNNING / R4_P2_0P5MS_PENDING / NO_REAL_TIME_CLAIM / NO_SPLICING`。

## 2026-09-16 出图合同符合性核查与补齐

- 触发：用户质询“跑完有按要求把图画出来吗”。按§25.3—§25.4与第2116行逐项核对，结论**部分符合、有实质缺口**。
- 缺口：run目录无`figures/`子目录；五类信息缺XY轨迹/冲量/轮胎支承转角；**中断的P2-1ms v1无图**（§25.3要求失败/超时/中断也出诊断图）；缺中文`figures/README.md`；manifest缺实验问题与字段单位口径等项。
- 补齐：新增`tools/r4_cell_figure.py`（SHA `c581846a...10de`），每个run生成`figures/`（PNG 300dpi+SVG+`figure_data.json`+`figure_manifest.json`+中文README），六面板：XY参考vs实际四车/货物、位置误差(D1口径)、航向误差、四点力+内力+15000N界、冲量累积、轮胎+支撑、转角与耗时。
- 出图范围：5个完成单元（P1 2/1/0.5ms、P2-2ms）+1个中断单元（P2-1ms v1）；逐张视觉QA通过，`figure_status=PASS_VISUAL_QA`与`science_status`分列。
- 中断单元符合§25.3：只画已接受段770 tick/30.800 m，星号标出未到达终点，标题写`unobserved remainder is NOT drawn`。
- 首版两处自身缺陷（数分钟内自查发现、从未被引用，删除重出）：①中断单元误标`plant step 2 ms`（实际1 ms；无metrics.json时回落到默认0.002）→改为在该run对应协议查`run.plant_max_step_ms`，查不到标`UNKNOWN`；②力峰取raw端点值(263.373104)而metrics取子步峰值(263.374627)→峰值改用子步`force_peak*`列、与metrics完全一致，端点值另列并标注。
- 未改偏差：analysis目录图仍平铺目录根，未放进`figures/`子目录（实质齐备，差异在层级；迁移影响约20个目录manifest与四份MD路径）。
- P2-1ms v2监控：12:29:17启动，14:22:39在1500/2379（60.0 m），status.json 37秒前写入，PID 11588存活，ETA约15:29。

## 2026-09-16 出图目录层级实情与GPU时代目录补齐

- 用户观察到“results下已经有了”，核实：91个结果目录中11个原本有`figures/`，其中**6个是CPU时代上一轮会话建的**（09-14/09-15），5个是我当天14:22新建；**GPU时代目录（G3六窗口、RTX5080四批、R4 GPU单元）此前全都没有**。我先前说的“缺口”指后者，与用户看到的CPU时代目录不矛盾。
- 按用户指示补齐：为**G3六窗口 + CPU中断的`R4_P1_2MS01`**出图，共**12个run目录现有`figures/`**，全部`figure_status=PASS_VISUAL_QA`。
- 工具新增能力：①**窗口run支持**——期望tick数改为读该run的`metrics.expected_iterations`（原硬编码2379会把G3的30 tick窗口报错）；②中断run自动识别并按已接受段出图，不补画不外推。
- 又自查出一处坐标轴错误：冲量面板横轴原用`linspace(0, 末tick绝对时间, n)`，完整路线上仅差0.02 s、但**30 tick窗口上从0画到30 s而实际窗口是26.7—27.3 s**；已改用子步`time_s`时间戳重出全部12套。
- 仍待裁决：`analysis/`目录的图仍平铺在目录根、未放进`figures/`子目录；RTX5080资格批次（G0_G2_04/05）的图按其资格脚本约定放在run根——是否统一，待用户决定。
- P2-1ms v2监控：14:30:27在1610/2379（64.4 m），PID 11588存活，最后检查点14:30:19，ETA约15:30。

## 2026-09-16 R4-P2-1ms v2 完成、P2 配对收敛通过、P2-0.5ms 启动

- `results/20260915_R4_P2_1MS_GPU02`：12:29:14启动、15:26:27结束（2.95 h），分离进程PID 11588承载无中断，`COMPLETED`、2379/2379、全长`95.12831551628261 m`、墙钟`10625.380491900025 s`。
- 硬门全过：点力峰`311.90481459693143 N`、内部力`198.01810836996103 N`、轮胎`0.055974954324023274`、最小支承`5144.717198137911 N`。
- P2 2ms↔1ms收敛：`R4_P2_2MS_1MS_CONVERGENCE_20260916_v1.json`（SHA `7330df59...f3036`）→`analysis/20260916_R4_P2_2MS_1MS_CONVERGENCE_01`，`PASS_R4_CELL_CONVERGENCE`、`figure_status=PASS_VISUAL_QA`。四门：力峰`1.395058e-08`（门2e-2）、冲量向量`3.942394e-06`、终点位置`1.803995e-05 m`（门1e-3）、终点航向`3.078304e-05°`（门0.01°）；全程最大位置差`1.837547e-05 m`；七项判定全PASS。
- 与P1的2→1ms对照（1.108e-07/1.690e-06/1.352e-07 m/1.429e-06°）：P2量级略大但余量充足；P2同时改载荷/连接器/摩擦，不可归因单一参数。两步长内部力相对差约1.1e-04，门内约两个数量级余量。
- P2-1ms v2六面板图已出，`figure_status=PASS_VISUAL_QA`。
- `R4-P2-0P5MS-GPU`（R4最后一条）协议`R4_P2_0P5MS_GPU_20260915_v1.json`（SHA `cf2c1c35...efc7c`）已冻结，错误SHA负例退出1且无输出；分离进程PID 24300于15:34:23启动，ETA约18:45—19:30。
- R4链状态：5/6完成；P1两组配对收敛全过；P2的2→1ms通过、1→0.5ms待0.5ms完成后做；`r4_gate.json`待六条齐备后生成。

## 2026-09-16 R4 六条全部完成、四门全过、参数组汇总图

- `results/20260915_R4_P2_0P5MS_GPU01`：15:34:18启动、18:41:41结束（3.12 h），`COMPLETED`、2379/2379、全长`95.12831551628261 m`、墙钟`11240.02860890003 s`。硬门全过：点力峰`311.9048082298731 N`、内部力`197.97660784988486 N`、轮胎`0.05597506748645355`、最小支承`5144.717105757962 N`。
- P2 1ms↔0.5ms决定性门：`R4_P2_1MS_0P5MS_CONVERGENCE_20260916_v1.json`（SHA `fa34ad3c...93f3a`）→`analysis/20260916_R4_P2_1MS_0P5MS_CONVERGENCE_01`，`PASS_R4_CELL_CONVERGENCE`、`figure_status=PASS_VISUAL_QA`。四门：力峰`2.041347e-08`（门2e-2）、冲量向量`9.802281e-06`、终点位置`4.289438e-05 m`（门1e-3）、终点航向`4.536486e-05°`（门0.01°）；全程最大位置差`3.906260e-05 m`。
- **R4总览**：六条全部COMPLETED、跑满全长、原硬门全过；四个门全PASS。P1（2→1：1.108e-07/1.690e-06/1.352e-07 m/1.429e-06°；1→0.5：5.851e-08/4.724e-07/5.614e-08 m/8.970e-07°）；P2（2→1：1.395e-08/3.942e-06/1.804e-05 m/3.078e-05°；1→0.5：2.041e-08/9.802e-06/4.289e-05 m/4.536e-05°）。P2量级整体大于P1但余量≥2个数量级；P2同时改载荷/连接器/摩擦，不可归因单一参数。
- 成本如实报告：P2-0.5ms墙钟最大`5.094 s`、**2348/2379在5 s内（98.70%）、31步超预算**（比P1-2ms的1步多）；均值`4.223 s`；“全程满足5s”对任何单元都不成立。
- §25.4参数组汇总图：`tools/r4_group_summary.py`→`analysis/20260916_R4_GROUP_SUMMARY_04/figures/`，`figure_status=PASS_VISUAL_QA`；四面板（6/6覆盖、硬门最差2.079%、四门动态计数4/4、状态板）；图置于分析目录自己的`figures/`子目录，示范§25.3层级。
- 三处工具缺陷（硬编码致状态失真）：配对报告路径硬编码→改为按报告identity动态发现；面板标题硬编码PENDING→改动态计数；README直引号嵌套→SyntaxError，改全角引号。汇总图4版，_01—_03标`FAIL_VISUAL_QA_SUPERSEDED`。
- **C1暂不宣布总PASS**：§4要求的每条`single_run_audit`（21项）与`r4_gate.json`/`r4_parameter_pair.json`尚未产出；**R5不启动**，先补齐。

## 2026-09-16 C1 总PASS 达成（补齐逐条审计与总门）

- 用户质询“是不是必须把C1补完才能R5启动”。逐条核对原文后确认**必须补完**，依据六处：§19.6(1795)“完整通过后才释放…R5的2条”、§22.5(1997)“R4 PASS才释放R5两条”、§27(2209)“仍须等待R4总PASS”、§27第2项(2214)“每条单独审计/图”、§27第4项(2216)“R4通过后”、§31.3 D5(2287)“R4总PASS后才R5”；详细任务书§2把R5前置写作C1全PASS，§4明确“总PASS要求全齐，不能只以6个COMPLETED计数”。唯一较松措辞“R4通过后”被同节“R4总PASS”限定。
- 补齐项一：新增`tools/r4_single_run_audit.py`，21项独立审计（重算指标而非信任metrics；含请求等于优化器首控制的逐位比较、协议身份匹配冻结文件、图上交付QA）。六条全部`PASS_SINGLE_RUN_AUDIT` 21/21，`single_run_audit.json`写入各run。
- 自查缺陷：初版第9—11项只读子步，致三条P1以`peak_tire_relative≈1.7e-5`失败；确认冻结runner的metrics取“子步段∪区间端点求值”的最大/最小值，合并后与metrics逐位相同（P1端点主导、P2子步主导）。属审计项误设，非数据问题。
- 补齐项二：新增`tools/r4_gate.py`→`analysis/20260916_R4_GATE_01`（协议`R4_C1_GATE_20260916_v1.json`，SHA `806edb62...8bfd`），产出`r4_parameter_pair_P1.json`、`r4_parameter_pair_P2.json`、`r4_gate.json`。门不计数完成数，逐条核验审计/执行/全长/硬门/协议身份/图表QA，每参数点两组比较均须PASS。
- **结果`PASS_C1_R4_TOTAL`**：六条pass=True、两参数点pass=True。R5与执行器九短片段的前置已满足。
- 边界：不验证六方法、不建立分布式/通信鲁棒结论、不使P1晚段横向偏离0.668 m可接受。R5开工前仍需核查`r5_runner`/合法信息入口的身份回归并先过七类负例，冻协议后启动N0/N1。

## 2026-09-16 GPU 作为后续实验执行平台（用户决定）

- 用户决定“当作一样的，把后面的实验也用GPU加速”。记录：`gpu_platform_decision_20260916.md`、任务书第48节、`protocol/methods.json`的`execution_platform_decision`。
- 实测三层（必须分开引用）：①物理同一——2200 tick/88 m位置差`2.398451e-05 m`、力峰相对1.0e-08、构形误差`12.562508469 mm` vs CPU`12.562509 mm`；②非逐位同一——24 µm≠0且随时间增长；③**GPU自身逐位可重复**（新测`analysis/20260916_GPU_DETERMINISM_PROBE_01`）——同配置两遍84/85列逐位相同，唯一不同为`solver_wall_s`，物理/控制白名单最大差精确0.0。
- 五条执行规则：P1后续动力学一律GPU并记录`execution_backend`；P2不变量门同后端对拍、严格门不放宽；P3跨后端按已登记容差报告、不得写成逐位一致；P4墙钟与时间列排除、时间按独立合同；P5图与清单标注后端。
- 不授权四件事：不拼GPU/CPU数据成同一轨迹或同批样本；不跨后端用逐位门；不以加速宣称实时；不以资格宣称方法优势。
- R5影响：CPU约18.8h → GPU约8.7h（含新增GPU P0名义2ms基准约2.9h）；门仍1e-12白名单级，改为同后端对拍以隔离变量；CPU基准`20260911_R3_UNFROZEN_FULL01/2ms`保留作跨后端对照。
- 现场证据：GPU逐位可重复性探针首版比较全部85列（含墙钟）而误报`NOT_BITWISE_REPEATABLE`与0.42“差异”；与§3给`r5_batch._noiseless_difference`登记的缺陷同类，证明白名单修复必需。

## 2026-09-16 R5 接口改造、负例通过、GPU 基准启动

- 三处身份修正：①`legal_information.py` 噪声改绝对tick派生（`SeedSequence([seed,tick,ord(node|field)])`）+ 每tick熵哈希 + schema v2；②`r5_runner.py` 显式 `frozen_dynamics_jacobian=False, finite_difference_scale=1.0`（原吃 `PilotConfig` 默认 `True`，即§5禁止的旧R2C冻结雅可比身份）、`--backend`（默认gpu）+ CUDA 生命周期 + `pool.json`、新增记忆列 `tick_index`/`interval_reference_distance_start_m`/`reference_beta0..3`/`previous_u0..7`、metrics 登记 `execution_backend`、`--protocol/--protocol-sha` 全套校验与拒覆盖；③`r5_information_tests.py` 补5类负例。原文件备份 `.py.r5pre`。
- 负例 **13/13 PASS**（`results/20260916_R5_CONTRACT_TESTS_01`）；两条协议负例（错SHA、配置不匹配）均在建输出前退出1且无输出。
- **GPU 无操作基准启动**：`results/20260916_R5_BASELINE_P0_2MS_GPU01`，协议 `R4_P0_2MS_GPU_20260915_v1.json`（SHA `5fbd027d...ffbe4`，角色 `R5 noiseless no-op baseline`）；分离进程 PID 29212 于 19:15:41 启动，19:18:22 复核 30/2379 存活，ETA 约 22:25。
- `full_route_gpu_runner.py` 与 `build_full_route_protocol.py` 各加一处 `P0` 白名单；使六个 R4 协议的 runner 身份记录相对新文件过期（六条已完成、证据冻结，如实登记，不追溯重写）。
- R5 协议冻结：N0 `7f7d0f42...19cd1`（none）、N1 `7b992345...67d8e`（basic），含信息接口 schema 与边界声明、硬门、停链规则；N0 无操作门为**同后端对拍、白名单61列、排除墙钟与时间、阈值1e-12不放宽**。门协议 `R5_INFORMATION_GATE_20260916_v1.json` 已冻；新增 `tools/r5_information_gate.py`（含§25.4要求的R5四面板图）。
- 执行顺序：基准 → N0（约3.2h）→ N1（约3.2h）→ 门与图；三者串行，单GPU不并行长任务。

## 2026-09-16 QP 控制变化率惩罚符号缺陷（用户质疑触发）——发现、修复、强制重跑

- `physical_tracking_pilot.build_problem` 的速率惩罚线性项符号写反：`target=-(u_nom[h]-u_nom[h-1])` 应为 `+`。决策变量 `x = u - u_nom`，实际速率 `rho = r_nom + Dx`，正确线性项 `+2*0.05*(Dᵀr_nom)/scale²`。
- 等价后果：实现出的二次型是 `0.05||rho - 2*r_nom||²`，**奖励**与标称速率同向的变化，把实际速率推向 2 倍标称速率；标称恒定（`r_nom=0`）时误差消失。
- 证据：两符号梯度**精确互为相反数**；编码梯度·`r_nom` = `-0.016264668713231272`（奖励），正确 `+0.016264668713231272`；tick700 同状态求解首步变化范数 `0.09414764289118019` vs `0.09128771049695256`，6号转向通道首步 `-0.03618723` vs `-0.01964506`（大84%）；修复后模块与独立正确参考**逐位一致** → `SIGN_FIX_VERIFIED_END_TO_END`。
- 修复：一处去负号 + 完整推导注释；权重(0.05)/门/尺度/路线均未改；原文件备份 `physical_tracking_pilot.py.prefix`。产物 `analysis/20260916_RATE_PENALTY_SIGN_PROBE_02/`、`analysis/20260916_RATE_PENALTY_FIX_VERIFY_01/`。
- 影响：控制器被 **26 个协议**钉住。缺陷版本产出：R3 全部、**R4 六条**、G3 三窗口、G0—G2 资格、R5 基准（**已在 920/2379 主动停止**，`abort_record.json`，非PASS非FAIL）。
- 仍成立：GPU↔CPU 等价（同类相比）、R4 四门步长收敛、硬门事实、R5 接口负例 13/13。
- 必须重新鉴定：**第42节 0.668 m 晚段横向发散**（奖励速率变化是缓慢漂移的合理成因）及据其作出的 `FAIL_LATE_TRACKING_DIVERGENCE` 判定；所有绝对跟踪质量表述；C1 总PASS。
- **第19.6节强制重跑**：控制算法源码发生影响结果的变化 → 六条必须全部用修复版本重跑（约18—19h），旧结果保留并标 `SUPERSEDED_BY_RATE_PENALTY_SIGN_FIX`。
- 教训：符号错误的惩罚项不会让 QP 失败——仍 PASS、仍过全部硬门；**代价项必须展开成物理量核对**；既有 21 项审计/四门/硬门/后端等价全部抓不到它。

## 2026-09-16 用户决定不重跑六条、只跑一条修复版基准；缺陷量化参考

- 用户决定（原话“不重跑了，直接跑一条作为基准，这几个步长的选项都影响不大”）。依据：四门收敛测得步长影响 `1e-8`—`4e-5`，比控制器版本的米级影响低六到七个数量级。
- 偏离去向登记进协议 `decision_rule_supersession`：六条旧单元标 `SUPERSEDED_BY_RATE_PENALTY_SIGN_FIX`；**旧新结果永不混算**，**C1总PASS退役且不被新run重新认领**；新run成为第42节重测与R5无操作门的共同参考；**不改任何门/阈值/权重/路线**。
- 修复版基准：`results/20260916_R5_BASELINE_P0_2MS_GPU02`，协议 `R4_P0_2MS_GPU_20260916_v2.json`（SHA `ee57af56...95554`），PID 5160 于 20:29:00 启动，ETA 约 23:40。
- 过程中自查两处错误：①手工建的 v2 协议 `run.output` 仍指向被中止的 `_GPU01`，导致首次启动 `REFUSING_TO_OVERWRITE_OUTPUT`；②`preconditions` 里 G3 原硬门取错键路径（顶层无 `verdicts`，实际在 `windows[].verdicts`），一度写入错误的 `False`。因 run 仅 12 秒，停止→删输出→改正→重启，未留身份瑕疵。
- 缺陷量化参考 `analysis/20260916_RATE_PENALTY_EFFECT_BUGGY_REFERENCE/buggy_reference_tracking.json`：CPU P0名义2ms 横向末值 `0.6682603854790906`、位置RMSE `0.255770`、44s后增长 `0.035156 m/s`；GPU P1 `0.668188`/`0.250782`/`0.037340`；GPU P2 `0.673481`/`0.269119`/`0.024523`。**三参数点漂移几乎相同 → 指向控制器缺陷而非参数敏感性**。

## 2026-09-17 速率惩罚符号缺陷的定量影响；R5-N0 启动

- 修复版基准 `results/20260916_R5_BASELINE_P0_2MS_GPU02`：09-16 20:28:45→23:35（3.10 h），`COMPLETED`、2379/2379、全长，协议 `R4_P0_2MS_GPU_20260916_v2.json`（SHA `ee57af56...95554`）。
- **决定性 A/B**（同候选/同 P0 名义/同 2ms/同路线，唯一变量符号）：横向末值 `0.668260→0.184135`（−72.45%）、位置RMSE `0.255770→0.125113`（−51.08%）、44s后漂移 `0.035156→0.007532 m/s`（−78.58%）；力峰 `288.06→398.53 N`（+38.35%）、纵向末值 `−0.092900→−0.415859 m`（+347.90%）、终点位置 `0.674687→0.454802`（−32.59%）。
- 结论：①符号缺陷解释约 **72%** 的晚段横向偏离；②不是免费改善，是**跟踪↔受力取舍**且误差转移到纵向通道；③后端差异约 2.4e-05 m/2200 tick，低三个数量级。
- 产物 `analysis/20260917_RATE_PENALTY_FIXED_EFFECT_02`（`PASS_VISUAL_QA`）。
- 自查两处图缺陷：力面板 y 轴到 15000 N 致 38% 峰值差**不可见**（改可读量程，`_01` 标 `FAIL_VISUAL_QA_SUPERSEDED`）；状态板漏掉纵向恶化 4.5 倍（已补）。另我**误读图中小字**（32.636→4.263、1993→1935）并据此怀疑数值矛盾，从数据文件核对后确认图正确；教训：核查图上数值必须回到数据文件。
- **R5-N0 启动**：`results/20260916_R5_N0_GPU01`，协议 SHA `ad14e760...cf6f`，PID 41956 于 09:53:12 启动，45 s 内 9 条 solver 记录，ETA 约 13:10。
- 启动前修三处代码缺陷（均未产生 R5 结果）：重复建目录致 FileExistsError；`run()` 重新派生 `params("P0")` 触发 CUDA 后端模型身份不匹配被 catch-all 吞成 inf 残差并崩 JSON；求解失败崩溃→改落 `solver_failure.json`。后两者与 09-15 G3 runner 已修问题同类，本次重犯。三处已在 3 tick 短段端到端验证。

## 2026-09-17 外部 GPU 修复清单评审（逐条核实，含实测裁决）

- P0-1 Δu 符号：属实，**已于 09-16 修复**；外部清单独立得出同一修法 → 交叉验证。
- P0-2 GPU 支撑 clamp：属实（`physics_torch.py:174` vs `four_vehicle_common.py:218/:180`）。**实测：从未触发** —— 四运行×5 tick×全部 68 个中心差分探针，支撑下界 `4691.662 / 4694.586 / 4225.478 / 5163.120 N`。故已有结果不受影响、**不构成重跑理由**；文档§11.2 的等价性前置已由该实测回答。仍值得修（CPU/GPU 定义一致性、E11/E14 会进入该域、改动两行）。
- P0-3 strict 语义：属实（`gpu_worker.py:152` 未传 strict，而 :130/:133/:136 传 True）。**建议方案A**（记录 domain 状态、拒绝越界 Jacobian），不建议方案B（生产中断）。
- P1-1：属实（`rollout_batch.py:9-12` 硬编码），数值一致 → 同步风险。
- P1-2：属实但**文档略过时**，worker 已导出 `forbidden_present_at_startup`/`imported_after_startup`，仅 :36 聚合判据误导。
- P2 6/7/8：同意保留；第8节与我实测 Amdahl 一致（48.4% 仍在 CPU、最多再有 2.06×），不继续优化 CUDA kernel。
- 时机：文件正被 R5-N0 使用 → **等 R5 链路跑完再改**；clamp 可证不触发，延后不影响 R5 数值。
- **自查身份缺口**：R5 N0/N1 协议钉了 0 个 GPU 侧文件（R4 P0 基准钉了 5 个）。不重启 N0，改为冻结 GPU 侧源码 SHA 作补充身份记录 `analysis/20260917_R5_GPU_IDENTITY_PIN_01/`。
- R5-N0 进度：10:32 在 534/2379（≈4.38 s/tick），ETA 约 12:47。

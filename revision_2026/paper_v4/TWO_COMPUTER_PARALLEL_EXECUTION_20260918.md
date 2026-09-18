# RTX 5080 + RTX 5060 双机并行实验执行任务书

文档版本：`DUAL-HOST-20260918-v2`  
现场日期：2026-09-18（Asia/Shanghai）  
适用目录：`revision_2026/paper_v4`  
状态：`SUPERSEDED_BY_EXPERIMENT_SECTION_61_AND_THREE_HOST_TASK_PACKS / HISTORICAL_READ_ONLY`

**2026-09-18后续更新**：当前实际机器已变为RTX 5080＋RTX 5060＋RTX 3050。本文件保留为两机方案历史记录，不再作为执行入口。最新权威分工见`experiment.md`第61节和`protocol/three_host_20260918/`下三份独立任务书；不得继续按本文件把全部远端任务交给单台5060。

本文件按当前磁盘产物、正在运行的进程、`experiment.md`、`R5_STRICT_CHAIN_EXECUTION_20260917.md`、`protocol/RTX5060双机V2冻结前执行任务书_20260917.md`和C4/E01证据矩阵重新排产。它只规定两台电脑怎样分工，不改变已有协议、门、阈值、控制律或科学裁决。

旧文件`protocol/RTX5060双机V2冻结前执行任务书_20260917.md`假设执行端是“两台RTX 5060”，且记录的是旧R5状态。本文件取代它在**当前一台RTX 5080加一台RTX 5060**场景下的排产作用；旧文件保留为历史依据，不覆盖、不删除。

---

## 0. 先给执行结论

1. **电脑A（RTX 5080）只跑严格R5主链**：S4严格N0已完成，单条审计、PNG/SVG、视觉QA和无操作门均通过。S5的科学前置已满足，但现有N1 v2是在这些父证据产生前冻结的，缺少硬身份钉住，必须先另冻新版本协议，不能直接启动。N1通过后再做R5总门和最终图。
2. **电脑B（RTX 5060）现在可以并行做四组工作**：环境与树身份快照、设备专属DEV版G0—G2固定样本资格与估时、E16理论反例/负向测试、E00/E17证据来源审计与回拷演练。
3. **N0与N1不能拆到两台电脑**。二者是同一严格求解器设置下的唯一变量对照，N1还受N0审计、N0图QA和无操作门约束。把N1放到5060会同时改变设备和后端数值路径，失去正式对照资格。
4. **5060现在不得跑正式闭环、全路线或E01缺口动力学**。当前树还要在R5结束后完成GPU语义/维护修补并冻结V2；现在跑出的正式动力学会被新身份替代。
5. **每种实验跑完必须立即出对应图**。缺PNG、SVG、`figure_manifest.json`或人工视觉复核的实验一律记为`INCOMPLETE`，不能释放下一步。纯文档准备不算实验，但也要产出清单或覆盖图。

---

## 1. 当前现场证据快照

最新快照时间：**2026-09-18 15:09 +08:00**。N0已完成并通过S4全部后处理门；执行时仍以磁盘最新状态为准，不得只凭进程退出码判定科学通过。

| 项目 | 当前证据 | 当前裁决 | 下一步 |
|---|---|---|---|
| 严格P0基准S3 | `results/20260917_R5_STRICT_BASELINE_P0_2MS_GPU01`，2379/2379，单条审计25/25 PASS，图QA PASS | 科学单条通过；原5 s求解预算未通过：仅755/2379在5 s内，均值5.598 s、最大6.956 s | 作为N0同设备无操作对拍基准保留 |
| 严格R5-N0 S4 | 输出`results/20260917_R5_STRICT_N0_GPU01`；协议`R5_STRICT_N0_GPU_20260918_v2.json`，SHA-256=`9006ec820b4a36be94e1d0794532e20cc1592ac73eabb510a25db32d2664db6d` | **PASS**；2379/2379；单条审计35/35 PASS；单条图QA PASS；相对S3的60列无操作门最大差`0.0`，门图QA PASS | S4已释放S5；保留全部当前与被取代过程证据 |
| 严格R5-N1 S5 | 现有协议`R5_STRICT_N1_GPU_20260918_v2.json`，SHA-256=`6180b51112bc3a8ee3d778e875ee5d9febc3deaad954bdb47a2a24b0bf4c39ed`；目标输出`results/20260917_R5_STRICT_N1_GPU01` | **BLOCKED_FOR_PROTOCOL_REFREEZE / NOT STARTED**；现有29项身份均匹配，但未钉住N0审计、N0图和无操作门父证据 | 保留v2不覆盖；生成并验证带完整父证据的新版本后才可启动 |
| R5总门 | 严格N1未完成 | **BLOCKED** | 等S3/S4/S5全部证据齐全后执行 |
| C4/E01植物门 | `required=33 / covered=9 / outstanding=24 / failed_retained=1` | `PLANT_GATE_NOT_READY` | V2冻结后补24条无通过证据项、单元残差登记、缺图和独立复核 |
| 核心方法对比 | 植物门未通过，E02/E03未释放 | **NOT_STARTED / BLOCKED_BY_GATES** | 不提前做控制方法排名 |

### 1.1 E01尚缺的正式证据

| 缺口 | 数量/状态 | 为什么现在不跑 |
|---|---:|---|
| 作用反作用、投影、力矩等单元残差按归一化`1e-8`登记 | 未完整登记 | 可准备协议；正式登记应绑定V2植物身份 |
| 真实回头弯3参数点×3步长 | 9条要求；1条已执行但`FAIL STOP_ULTIMATE_FORCE`，另8条缺失 | 必须保留失败条，冻结V2协议后重建完整矩阵 |
| 转向切换3参数点×3步长 | 9条正式矩阵均未形成 | 现有短测试/几何结果不能冒充3×3矩阵 |
| 100 ms延迟与0.4 s中断，各3族 | 6条均缺失 | 输入器和身份尚未正式冻结 |
| 图与独立审查 | 回头弯失败接受段、转向切换、通信诊断缺图 | 每条实验完成后必须补图，最后再重建plant gate |

---

## 2. 双机角色与写入边界

| 电脑 | 固定角色 | 现在可做 | 现在禁止 |
|---|---|---|---|
| **A：RTX 5080，当前主机** | R5严格链唯一执行与最终汇总端 | S4 N0；完成后的审计、图、无操作门；S5 N1；R5总门；V2修补与冻结 | N0/N1运行期间并发启动其他GPU动力学；修改本次协议钉住的源码/工具/任务书；接收5060回拷并混入活动目录 |
| **B：RTX 5060，独立工作副本** | 设备资格、理论负例、证据审计；V2后承接E01植物缺口 | B0环境/树身份；B1 DEV G0—G2；B2 E16；B3 E00/E17；B4正式协议草案 | 当前版本的正式闭环/全路线、R4/R5、E01/E02/E03/E05；复用5080资格；修改已有被协议钉住文件 |

### 2.1 单写者规则

- A与B不得同时编辑同一个MD、JSON、脚本或协议。
- B只在**独立完整副本**中工作，所有新增目录带`H5060`和日期；不得把B的输出直接写入A正在使用的网络盘目录。
- B完成后先打包并生成SHA-256清单，保存在B侧。至少等严格N1结束并完成现场身份记录后，A再做只读验包和汇入。
- A上的当前N0协议钉住29个身份文件。N0运行期间不得修改其中任何一个，尤其是`src/paper_v4_core/**`相关runner/GPU后端、四个R5审计绘图工具以及`R5_STRICT_CHAIN_EXECUTION_20260917.md`。

---

## 3. 电脑A（RTX 5080）执行树

### A0：历史动作——S4 N0独占运行（已完成）

N0已完成，本节命令仅保留为历史监控方式。**不要重跑或覆盖N0。**

```powershell
$Paper = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\paper_v4'
Get-Content "$Paper\results\20260917_R5_STRICT_N0_GPU01\status.json" -Raw
Get-Item "$Paper\logs\20260918_r5_strict_n0_gpu01.stderr.log" | Select-Object Length,LastWriteTime
Get-CimInstance Win32_Process | Where-Object ProcessId -in 11084,15728 |
  Select-Object ProcessId,CreationDate,CommandLine
```

仅满足以下任一情况才停止并登记：进程消失且状态不是`COMPLETED`、stderr出现实质错误、协议身份失败、CUDA设备身份失败、科学硬门触发、绝对截止触发。不得因ETA波动或单步超过5 s手工终止；5 s预算应如实统计到结果中。

### A1：N0完成后的S4收口（已完成）

必须按顺序完成，前一项失败就停止：

1. 确认`COMPLETED`、2379/2379、metrics/raw/solver/information/substeps文件齐全。
2. 运行单条科学审计：

   ```powershell
   Set-Location $Paper
   $Python = 'E:\anaconda\envs\pytorch_new\python.exe'
   & $Python -B tools\r5_single_run_audit.py `
     --runs results\20260917_R5_STRICT_N0_GPU01 --write
   ```

3. 生成N0单条图：

   ```powershell
   & $Python -B tools\r4_cell_figure.py `
     --run results\20260917_R5_STRICT_N0_GPU01
   ```

4. 打开PNG人工核对轨迹、误差、点力/内力、冲量、轮胎/支承、请求/实际转角和求解耗时。数值门与图语义均正确后，才登记`PASS_VISUAL_QA`。
5. 运行严格N0相对严格基准的无操作门；比较协议登记的60个有效列，`max_e_g_m`必须纳入，不得排除：

   ```powershell
   $N0Protocol = "$Paper\protocol\R5_STRICT_N0_GPU_20260918_v2.json"
   $N0Sha = (Get-FileHash -LiteralPath $N0Protocol -Algorithm SHA256).Hash.ToLower()
   & $Python -B tools\r5_strict_no_op_gate.py `
     --protocol $N0Protocol --protocol-sha $N0Sha `
     --out analysis\20260918_R5_STRICT_N0_NO_OP_01
   ```

6. 无操作门必须同时交付`no_op.json`、PNG、SVG、`figure_manifest.json`并通过人工图检。

S4释放条件：`PASS_SINGLE_RUN_AUDIT + PASS_VISUAL_QA + PASS_STRICT_NO_OP + no-op图QA PASS`。任一项失败，S5保持`BLOCKED`。

### A2：S5严格N1（科学前置通过，协议重冻待完成）

S4全部科学释放条件已经满足，但复核发现现有N1 v2缺少任务书要求的父证据身份，**不得直接启动**。现有文件保留为历史冻结版本：

- 协议：`protocol/R5_STRICT_N1_GPU_20260918_v2.json`
- 协议SHA：`6180b51112bc3a8ee3d778e875ee5d9febc3deaad954bdb47a2a24b0bf4c39ed`
- 输出：`results/20260917_R5_STRICT_N1_GPU01`
- 唯一变量：`noise=basic`；seed仍为5105；设备、后端、求解器设置和验收容差必须与S3/S4一致。

启动前必须另冻新版本协议，至少把当前N0协议、`metrics.json`、`raw.npz`、35/35审计、当前图manifest、无操作门JSON、无操作门图manifest及生成工具身份钉入。现有`tools/build_r5_strict_protocols.py --stage n1`仍指向旧`GPU02`/`20260917_R5_STRICT_N0_NO_OP_01`分支，不能不加核对地直接运行。新版本需先通过身份检查、输出不存在检查和错误SHA负例，再按统一启动函数执行。

N1结束后执行同样的“科学审计→单条PNG/SVG→人工视觉QA”。图内必须显示请求转角最大值和15°界、实际转角、全子步物理门、点力、构形误差、求解耗时和科学审计状态。任何FAIL都停止，不运行总门。

### A3：R5严格总门与最终图

只有S3、S4、S5都满足“2379/2379 + 科学审计PASS + 图QA PASS”，且S4无操作门PASS，才允许：

1. 冻结新的R5总门协议；
2. 执行`tools/r5_information_gate.py`；
3. 执行`tools/r5_information_figures.py`；
4. 生成总门JSON、PNG、SVG和manifest并人工复核；
5. 最后才可在主实验文档中写`PASS_R5_INFORMATION_GATE`。

R5通过只证明合法信息接口转移和登记噪声条件下的本链证据，不自动释放E05，也不等于实时预算通过。

---

## 4. 电脑B（RTX 5060）现在可并行的工作包

### B0：环境与树身份快照（先做，约30—90 min）

目标：证明B侧设备、环境和完整副本身份，不产生论文动力学结论。

```powershell
hostname
nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv
$TaskPy = '<5060本机Python 3.11路径>'
& $TaskPy -c "import torch,numpy,scipy,osqp; print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0),numpy.__version__,scipy.__version__,osqp.__version__)"
```

要求：

- 使用完整、隔离的`paper_v4`副本，保留`src/`、`tools/`、`protocol/`、固定输入和G0—G2所需父证据；
- 新增只读树审计工具`tools/verify_tree_identity_5060_20260918.py`，不得改已有工具；
- 输出到`analysis/20260918_H5060_PRE_V2_01/`：`host_environment.json`、`tree_identity_audit.json`、`README.md`；
- 协议的`required_device_name`使用`torch.cuda.get_device_name(0)`原字符串，不能用猜测名称；
- 对比A侧相同树快照时，协议状态和文件SHA差异必须逐项解释。无法解释就停止B1。

B0是资格前置检查，不算动力学实验。应额外交付一张环境/身份覆盖图PNG+SVG，便于人工检查设备名、版本差异和匹配/失效协议计数。

### B1：5060设备专属DEV版G0—G2固定样本资格与估时（约1—2 h）

只允许固定样本、无闭环、分钟级运行。新建副本：

- `tools/gpu_g0_g2_qualify_5060_20260918.py`
- `tools/build_rtx5060_g0_g2_protocol_20260918.py`
- `protocol/RTX5060_G0_G2_DEV_20260918_v1.json`

建议输出：`results/20260918_H5060_G0_G2_DEV01/`。

必须检查：

| 子门 | 内容 | 判据处理 |
|---|---|---|
| G0 | CUDA可用、设备名逐字符一致、float64有限 | 身份不一致即停，不改5080协议 |
| G1 | 6个固定物理样本：RHS、RK4 2 ms、20 ms rollout | 使用既有登记容差；不得因5060放宽 |
| G2 | 固定QP：`f0/A/B/qp_matrix/qp_bounds`及非线性复核 | CPU/GPU两侧均须PASS |
| 性能 | GPU端到端、CPU parallel8、显存峰值、5 s原预算 | 性能不佳如实登记；不得伪装成数值失败或科学PASS |

强制图交付：

1. `g0_environment`图：设备、精度、版本和显存；
2. `g1_normalized_error`图：各物理样本归一化误差与门；
3. `g2_qp_and_timing`图：QP误差、非线性复核、CPU/GPU耗时和5 s参考线；
4. 每张均有PNG与SVG，根目录有`figure_manifest.json`并人工登记视觉QA。

结果状态只能写：`DEV_PRE_V2 / NOT_A_FORMAL_QUALIFICATION_UNTIL_V2`。它可用于检查5060能否运行、估计耗时和显存，不能作为V2正式资格，也不能用于论文性能结论。V2冻结后必须在同一5060上重新生成协议并重跑。

### B2：E16理论反例与负向测试（约2—3 h）

该工作与当前闭环树版本弱耦合，可以现在做；只新增文件和目录，不改已有被钉住测试。

输出：`analysis/20260918_H5060_E16_COUNTEREXAMPLES_DEV01/`。

至少包含：

1. 式(13)三分支：`C_U>0`可认证区间、`C_U=0`独立检查、基础块已超界时`NOT_CERTIFIABLE`；
2. 标量反例：证明clip到`gamma=0`不能自动变成认证PASS；
3. 非正规矩阵反例：区分谱半径与诱导范数/瞬态增长；
4. 切换系统反例：各子系统单独稳定不自动推出任意切换稳定。

强制产物：原始JSON/CSV、测试日志、至少三组PNG+SVG（gamma可行域、非正规瞬态、切换轨迹/上界）、`figure_manifest.json`和人工视觉QA。结论边界写成`NEGATIVE_TESTS_ONLY`，不得声称已经证明闭环稳定、递归可行或失联密度界。

### B3：E00/E17来源与证据审计、回拷演练（约2 h）

目标：把后续正式实验所需的来源、身份、缺口和回拷验收列清，不跑动力学。

输出：

- `analysis/20260918_H5060_E00_E17_AUDIT01/source_evidence_audit.json`
- `analysis/20260918_H5060_E00_E17_AUDIT01/collect_checklist.json`
- `analysis/20260918_H5060_E00_E17_AUDIT01/figures/evidence_coverage.{png,svg}`
- `analysis/20260918_H5060_E00_E17_AUDIT01/figure_manifest.json`

覆盖图至少区分：已有原始证据、仅有分析结果、缺协议身份、缺实验、已有失败、缺图、待独立审查。此工作是审计，不得把“找到文件”写成“科学通过”。

回拷演练只使用小型虚拟包：生成相对路径、文件大小、SHA-256和主机名清单；在临时目录验包；不得向A的活动`results/`、`logs/`和`analysis/`写入。

### B4：V2后正式实验的协议与绘图合同准备（约2—4 h，只准备）

状态必须写`PREP_ONLY / NOT_RUN`。准备以下草案，不执行：

1. E01单元残差登记表与归一化`1e-8`门；
2. 回头弯3参数点×3步长的9格协议矩阵，明确保留已有失败条；
3. 转向切换3参数点×3步长的9格协议矩阵；
4. 100 ms延迟与0.4 s中断，各3族，共6条通信植物诊断；
5. 每一格的run ID、seed、输入身份、植物身份、停止规则、数据文件、单条图和汇总图合同；
6. 跨设备短窗探针设计，只规定比较量和容差登记方法，不执行。

这些是准备项，不是实验，因此不要求伪造轨迹图；应交付一张协议覆盖矩阵PNG+SVG，清楚标`NOT_RUN`。

---

## 5. 当前可并行时间线

| 阶段 | 电脑A：RTX 5080 | 电脑B：RTX 5060 | 合流条件 |
|---|---|---|---|
| P0：已完成 | S4 N0、单条审计、N0图QA、无操作门和门图全部PASS | 可独立准备B0 | S4已释放S5 |
| P1：当前 | S4科学前置已通过；补齐N1父证据协议并做身份/拒绝预检，N1尚未启动 | B0环境/树身份，完成后做B1 DEV G0—G2并立即出图 | 两侧不写同一目录；B1只作DEV |
| P2：N1运行 | S5 N1独占运行 | B2 E16或B3审计/B4准备 | 不在A上启动其他GPU动力学 |
| P3：N1结束 | N1审计/图QA；若PASS，做总门和最终图 | B侧完成打包与SHA清单，仍不自动合并 | R5证据闭合后才验收B侧包 |
| P4：R5闭合后 | GPU四项修补、测试、冻结V2；A侧正式资格 | 等待V2整包，重做5060正式G0—G2 | 两机资格和跨设备探针通过 |
| P5：V2资格后 | 审核E01回传、准备E02；不提前跑E02 | 正式执行E01缺口并逐条出图 | `plant_gate=PASS`才释放E02 |

---

## 6. V2冻结后的双机正式分工

### 6.1 先完成V2资格，不直接跑E01

R5严格链关闭后，A先完成任务书已登记的GPU修补与维护项（支撑clamp、严格语义、常量断言、纯度/污染检查），通过测试后冻结唯一V2树。随后：

1. A、B都从同一V2整包开始，记录树清单与环境；
2. A重跑5080 G0—G2正式资格，B重跑5060 G0—G2正式资格；
3. 两机分别生成PNG、SVG和manifest；
4. 用相同短窗执行跨设备探针。跨设备比较采用前瞻性登记的实测容差，禁止使用逐位相等或`1e-12`门，禁止把wall time列混进数值等价性；
5. 两侧均通过后，5060才获得正式动力学执行资格。

### 6.2 正式分工建议

| 电脑 | 正式任务 | 说明 |
|---|---|---|
| RTX 5060 | E01单元残差、回头弯、转向切换、通信植物诊断缺口 | 每条独立目录、审计、PNG/SVG、manifest；失败条保留，不删不改门 |
| RTX 5080 | 验收回传、重建C4证据矩阵与plant gate；同时完成E16/E17非动力学整理和E02协议准备 | 在`plant_gate=PASS`前不得执行E02控制排名 |

E01全部完成且独立审查通过后，才按主任务书释放E02。E02完成并通过后再决定E03的双机分配；本文件不提前把依赖未满足的E03写成可运行任务。

---

## 7. 统一的“实验完成”与出图合同

任一实际运行的实验只有同时具备以下五类证据才算完成：

1. 冻结协议及协议SHA；
2. 原始数据和逐步/子步日志；
3. 科学审计JSON，明确PASS/FAIL及失败原因；
4. 对应PNG与SVG、`figure_manifest.json`；
5. 人工视觉QA记录，科学状态和视觉状态分开。

| 实验类型 | 单条图 | 汇总图 | 图内必须显示 |
|---|---|---|---|
| R5基准/N0/N1 | 六面板PNG+SVG | N0无操作图、R5接口/噪声图 | 轨迹、误差、力、冲量、轮胎/支承、请求/实际转角、耗时、审计状态 |
| G0—G2 | 环境、误差、QP/性能图 | 设备资格状态板 | 设备身份、归一化误差和门、CPU/GPU耗时、显存、DEV/FORMAL状态 |
| E16反例 | 每类反例曲线 | 反例状态板 | 参数、边界、失败/不可认证区域，不画伪PASS |
| E01单元/回头弯/切换/通信 | 每条物理诊断图 | 3×3收敛图、通信配对图、plant覆盖图 | 输入、实际响应、Fx/Fy/Fz、点力/内力、轮胎/支承、失败时刻和接受段 |
| 证据审计 | 无动力学曲线 | 覆盖图PNG+SVG | 已有、缺失、失败保留、缺协议、缺图、待复核 |

图表只有呈现缺陷时允许在新目录重绘，旧图标记`FAIL_VISUAL_QA_SUPERSEDED`并保留。只要数值、阈值、白名单或裁决逻辑改变，就必须另冻协议并重跑，不能借“重绘”修改科学结果。

---

## 8. 双机停止规则

出现以下任一情况，当前工作包立即停止并保留已有证据：

- A侧N0/N1协议身份不一致、CUDA设备不符、输出目录已存在、stderr出现实质错误或硬门触发；
- N0审计、N0图QA或无操作门失败，却仍准备启动N1；
- B侧发现自己实际在A的5080活动工作区、共享写入目录或修改了已有被钉住文件；
- 5060 DEV G0—G2使用了5080资格作为本机资格，或为了过门放宽容差；
- V2冻结前试图运行正式闭环、全路线、E01/E02/E03/E05；
- 跨设备比较使用逐位相等、`1e-12`或把时间列纳入数值等价性；
- 实验结束后缺图、图无manifest、视觉QA未做，却准备释放后续阶段；
- 删除已有失败轨迹、覆盖旧结果或把单seed/单设备结果写成统计鲁棒性结论。

---

## 9. 回拷包与命名规范

B侧统一使用主机标签`H5060`，例如：

```text
analysis/20260918_H5060_PRE_V2_01/
results/20260918_H5060_G0_G2_DEV01/
analysis/20260918_H5060_E16_COUNTEREXAMPLES_DEV01/
analysis/20260918_H5060_E00_E17_AUDIT01/
transfer/20260918_H5060_PRE_V2_PACKAGE01/
```

回拷包必须包含：

- `manifest.json`：相对路径、字节数、SHA-256、生成主机、生成时间；
- `commands.txt`：实际执行命令与退出码；
- `environment.json`：Python、OS、CUDA、GPU、依赖版本；
- 原始JSON/CSV/日志；
- PNG、SVG和所有`figure_manifest.json`；
- `README.md`：逐项区分`PASS`、`FAIL`、`DEV_PRE_V2`、`PREP_ONLY`、`NOT_RUN`。

A只在R5严格链完成并保存现场身份后验包。验包通过也只说明传输完整；DEV结果仍保持DEV，不因回拷而升级为正式资格。

---

## 10. 文档维护说明

1. 当前`experiment.md`中存在重复编号的`## 58`，且旧的5060双机任务书含已过时的R5进度。为避免N0运行期间改动被钉住或被其他流程读取的文档，本次只新增本文件。
2. N0/N1和R5总门闭合后，由A单写者统一清理主文档编号、回填实际完成时间/指标、链接本双机任务书和B侧验包报告。
3. 回填时必须分开写：已完成执行、科学审计、视觉QA、DEV准备、尚未运行。不得把“协议已准备”写成“实验已完成”。

---

## 11. 当前勾选表

### 电脑A：RTX 5080

- [x] S3严格基准2379/2379完成。
- [x] S3单条审计PASS、图QA PASS。
- [x] S4严格N0完成2379/2379。
- [x] S4 N0单条审计35/35 PASS。
- [x] S4 N0单条PNG/SVG与视觉QA PASS。
- [x] S4相对S3无操作门及门图QA PASS（60/60列最大差0.0）。
- [ ] 冻结带完整N0/无操作门父证据的新N1协议并通过身份/拒绝预检。
- [ ] S5严格N1完成、审计PASS、图QA PASS。
- [ ] R5严格总门及最终图PASS。
- [ ] GPU维护修补完成并冻结V2。

### 电脑B：RTX 5060

- [ ] B0环境快照、树身份审计、覆盖图完成。
- [ ] B1 DEV G0—G2、三组图和manifest完成。
- [ ] B1估时与显存报告完成，状态保持`DEV_PRE_V2`。
- [ ] B2 E16负向测试、JSON/CSV、PNG/SVG和manifest完成。
- [ ] B3 E00/E17证据审计、覆盖图和回拷演练完成。
- [ ] B4 E01/V2协议草案和绘图合同完成，状态保持`PREP_ONLY / NOT_RUN`。
- [ ] B侧回拷包与SHA清单完成，等待A侧R5闭合后验收。
- [ ] V2整包同步后重跑5060正式G0—G2资格。
- [ ] 跨设备短窗探针通过后，才启动正式E01缺口实验。

---

## 12. 2026-09-18 现场更新：S4完成，N1协议需补父证据

### 12.1 N0执行结果

`results/20260917_R5_STRICT_N0_GPU01`于09:04启动，11:59完成，`COMPLETED 2379/2379`，墙钟`10466.027920799796 s`（约2.91 h）。

| 指标 | N0结果 | 判定 |
|---|---:|---|
| 点力峰值 | 398.458943 N | 低于15000 N硬门 |
| 内力范数峰值 | 342.755907 N | 记录通过 |
| 轮胎利用率峰值 | 0.0492852 | 低于1.0硬门 |
| 最小支承 | 4686.285219 N | 大于0 |
| 最大构形误差 | 0.0137504 m | 已按真实公式计算 |
| 请求转角最大值 | 15.000000°，越界0 | 登记验收通过 |
| 实际转角最大值 | 14.997707° | 物理边界通过 |
| 求解耗时 | 均值4.263 s，最大5.411 s，2369/2379在5 s内 | 不宣称每步均满足5 s |

### 12.2 审计和图

- 当前科学审计：`results/20260917_R5_STRICT_N0_GPU01/single_run_audit.json`，`PASS_SINGLE_RUN_AUDIT 35/35`。
- 当前单条图：`results/20260917_R5_STRICT_N0_GPU01/figures/`，PNG/SVG齐全，`PASS_VISUAL_QA`。
- 首轮审计在图尚不存在时为34/35，唯一失败是`figures_delivered_and_qa_pass`。该文件保留为`single_run_audit_pre_figure_20260918_01.json`。
- 首轮图虽视觉正确，但显示了该前置审计FAIL状态，已保存在`figures_superseded_pre_final_audit_20260918_01/`并标记`FAIL_VISUAL_QA_SUPERSEDED`；当前图在35/35审计后重新生成，显示最终PASS状态。

### 12.3 严格无操作门

`analysis/20260918_R5_STRICT_N0_NO_OP_01/no_op.json`：

- 状态`PASS_R5_STRICT_N0_NO_OP`；
- 60/60个协议登记列逐位相同；
- 2379个时刻的时间列逐位相同；
- 最大绝对差`0.0`，门为`1e-12`；
- PNG/SVG与manifest齐全，人工视觉QA为`PASS_VISUAL_QA`。

这证明同设备、同后端、同严格求解器设置下，合法信息接口在无噪声条件中对集中全状态基准是精确无操作。它不证明带噪声N1、网络延迟/丢包或统计鲁棒性。

### 12.4 当前唯一主线动作

S4科学释放条件已经满足，但现有`R5_STRICT_N1_GPU_20260918_v2.json`是在N0完成前冻结的。现场复核显示它的29项已有身份均匹配，却没有钉住当前N0协议/metrics/raw/35项审计/当前图manifest及无操作门JSON/图manifest，不符合严格任务书“父证据产生后再冻N1”的要求。

因此当前状态是`S5_SCIENCE_PREREQUISITES_PASS / N1_PROTOCOL_REFREEZE_REQUIRED / NOT_STARTED`。保留v2不覆盖；先生成新的版本化N1协议并把上述父证据列为硬身份，完成正确SHA、错误SHA、已有输出和父证据缺失拒绝测试后，才允许启动。R5总门仍为`BLOCKED`。

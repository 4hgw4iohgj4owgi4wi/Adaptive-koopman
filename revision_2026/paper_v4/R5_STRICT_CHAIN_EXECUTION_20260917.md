# R5严格求解器链启动任务书

版本：`READY-S3-20260917-v2`

状态：`READY_TO_START_S3_BASELINE / S0-S2_PASS / FULL_ROUTE_NOT_STARTED / R5_TOTAL_GATE_BLOCKED`

本文件是下一次启动R5实验的唯一操作入口。S0—S2已经完成并有冻结证据，当前只释放**S3严格P0基准**；S4、S5仍须等待上一条的科学审计与图QA通过后逐条冻结协议。它不把旧N1的`33/34 FAIL`改成通过。当前没有全路线实验进程。

**每种实验跑完都必须立即生成对应PNG/SVG、`figure_manifest.json`并完成视觉QA；缺图、图义错误或图QA失败都不得启动下一种实验。**

## 1. 目标和唯一允许的比较

目标是保持15°请求转角边界和全部原物理门不变，用显式登记的严格求解器设置重新建立一条可比较的R5证据链。

必须依次完成三条全路线：

| 顺序 | 运行 | 信息/噪声 | 与谁比较 |
|---:|---|---|---|
| S3 | 严格修复版P0基准 | 集中全状态、无噪声 | 作为同配置无操作伙伴 |
| S4 | 严格R5-N0 | 合法信息接口、无噪声 | 与S3做无操作门 |
| S5 | 严格R5-N1 | 合法信息接口、基础噪声、seed 5105 | 与S4做唯一变量为噪声的比较 |

不得只重跑N1后与旧N0作正式对照。旧基准/N0/N1使用`eps_abs=eps_rel=2e-4`；收紧设置后，求解器配置本身已成为新变量。

## 2. 冻结不变项与待验证候选

三条全路线共同冻结：

- 参数点：P0；植物最大子步2 ms；控制周期20 ms；总周期2379；路线和参考不变。
- MPC：horizon 20、`lambda_internal=2.0`、`frozen_dynamics_jacobian=false`、`finite_difference_scale=1.0`。
- 后端：RTX 5080的现有CUDA有限差分后端；不得切CPU后仍沿用GPU比较名义。
- N0/N1接口实现相同；N1唯一增加`basic`噪声且seed固定5105。
- 物理门：点力≤15000 N、轮胎利用率≤1、支承载荷≥0；15°请求/实际转角检查不放宽。
- 旧raw、substeps、metrics、审计和图全部只读保留。

首个待探针验证的求解器候选：

```json
{
  "eps_abs": 1e-6,
  "eps_rel": 1e-6,
  "scaled_termination": false,
  "max_iter": 4000,
  "polishing": true
}
```

另在协议的`acceptance_tolerances`中独立冻结：

```json
{
  "requested_steering_acceptance_tolerance_rad": 1e-6,
  "applied_steering_machine_tolerance_rad": 1e-12
}
```

请求转角数值验收阈值不能从`eps_abs`自动推导；15°几何边界、求解器停止设置和任务书验收容差是三个不同字段，审计必须分别报告。该候选已通过第3节固定QP探针，但尚未通过任何新全路线。完整N1开始后不得再根据结果改阈值；任何新候选都必须另建协议版本，从第3节探针重新开始。

## 3. 启动前代码与证据门

### S0：现场和环境冻结（已通过）

使用成功GPU链所对应的环境作为候选：

```powershell
$Paper = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\paper_v4'
$Python = 'E:\anaconda\envs\pytorch_new\python.exe'
Set-Location -LiteralPath $Paper
$env:PYTHONPATH = "$Paper\src"

& $Python -c "import sys,osqp,numpy,scipy,torch; print(sys.executable); print(sys.version); print('osqp',osqp.__version__); print('numpy',numpy.__version__); print('scipy',scipy.__version__); print('torch',torch.__version__); print('cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match 'paper_v4_core' } | Select-Object ProcessId,CommandLine
```

验收：Python路径和依赖版本写入新协议/启动回执；CUDA可用且设备为目标RTX 5080；没有与本链冲突的实验进程。发现活动任务时先核对输出，禁止重复启动或杀死不相关进程。

本机已经核实：`pytorch_new`和base两个环境的OSQP均为1.1.1，默认`scaled_termination=False`。正式运行仍必须显式传值并落盘，不能依赖默认。

### S1：代码修补（已完成）

1. `src/paper_v4_core/controllers/physical_tracking_pilot.py`
   - `PilotConfig`加入`scaled_termination`和`polishing`；
   - `solver.setup`显式传入五项求解器设置；
   - 不改约束、权重、预测模型或控制映射。
2. `src/paper_v4_core/diagnostics/gpu_closed_loop_runner.py`与`full_route_gpu_runner.py`
   - 从冻结协议读取`solver_settings`并传给`PilotConfig`；
   - `metrics.json`记录实际设置；
   - 基准的`max_e_g_m`按R5同一公式计算，不再写死0.0。
3. `src/paper_v4_core/r5_runner.py`
   - 从协议读取同一`solver_settings`；
   - 协议值与运行参数不一致时，在创建输出目录前拒绝；
   - 加入绝对截止并在循环内执行；
   - `metrics.json`和启动回执记录设置及环境。
4. `tools/r5_single_run_audit.py`
   - 从本条metrics/协议读取求解器设置和独立的请求转角验收容差，删除`2e-4`硬编码；
   - 不得把`eps_abs`自动当作未缩放几何越界上限；
   - 同时报告原始`>15°`计数和`>15°+1e-12`实质计数；
   - 缺少设置、设置矛盾、请求越界超过登记阈值时FAIL。
5. `tools/r5_information_gate.py`
   - 读取三条单条审计和三条图manifest；
   - 三条必须为科学审计PASS、图QA PASS；
   - 只比较同一严格求解器身份的基准/N0/N1。
6. `tools/r5_information_figures.py`
   - 接受显式run路径和新输出目录；
   - 不覆盖旧`analysis/20260917_R5_INFORMATION_FIGURES_02`。
7. `tools/r4_single_run_audit.py`与`tools/r5_single_run_audit.py`
   - 科学审计不再把图QA列入自身检查，解除“审计等图、绘图又等审计”的循环依赖；
   - 新顺序统一为：科学审计→绘图（图中读取审计状态）→人工视觉QA；总门再分别硬检查审计与图。
8. `tools/r5_strict_no_op_gate.py`与协议构建器
   - 在生成N1协议前真实比较新N0与新基线的60个登记列及时间列；
   - 无操作门自身也必须生成JSON、PNG、SVG与manifest并通过视觉QA；缺失或失败时构建器拒绝生成N1。

### S2：编译、拒绝测试和固定QP探针（已通过）

完成证据如下：

| 证据 | 结果 | 产物 |
|---|---|---|
| 全部严格链Python文件以`-W error -m py_compile`编译 | PASS | 源码现场复核 |
| 错SHA、非法solver设置、已有输出、R5缺验收容差、R5缺截止时间 | **5/5按预期拒绝**，均未启动动力学 | `analysis/20260917_R5_STRICT_PREFLIGHT_01/preflight.json` |
| 预检图 | `PASS_VISUAL_QA` | 同目录`figures/r5_strict_preflight.{png,svg}`与根目录`figure_manifest.json` |
| 旧N1 15个实质越界tick固定QP重放 | `PASS_R5_STRICT_SOLVER_PROBE` | `analysis/20260917_R5_STRICT_SOLVER_PROBE_01/probe.json` |
| 探针图 | `PASS_VISUAL_QA` | 同目录`figures/r5_strict_solver_probe.{png,svg}`与根目录`figure_manifest.json` |

探针使用旧N1的tick `834, 839, 853, 930, 963, 1112, 1180, 1194, 1298, 1301, 1370, 1384, 1524, 1538, 1549`。旧`2e-4`设置对保存的首控制**最大绝对差为0.0**；新`1e-6`设置15/15均为`solved`且非线性复核PASS，请求转角最大越界为**0.0 rad**，迭代数200—825。探针总墙钟170.477 s，单次严格求解约5.19—5.83 s；这证明数值候选可用，**不证明原5 s实时预算通过**。

探针环境中的`worker_boundary_clean=false`来自`torch`启动时已带入NumPy；决定性字段为`imported_after_startup=[]`且SciPy/OSQP/Pandas未进入worker，因此没有观察到新的父进程/worker污染。后续若`imported_after_startup`非空或CUDA身份门失败才停止。

冻结记录：

- 探针协议v1：`protocol/R5_STRICT_SOLVER_PROBE_20260917_v1.json`，SHA `d7d8511d6bc01f9b00afa470cf001c6329ae836a05827b0023f5c2d7e63acdbd`；
- S3基线协议v2：`protocol/R5_STRICT_BASELINE_P0_2MS_GPU_20260917_v2.json`，SHA `ded690eb5bcf1ea5df3346a530bbb8e44a498ec6f5b9a0406e089ab7c3493477`；
- 未运行的基线协议v1保留但不使用：它继承了旧协议的矛盾/过时说明，且未钉住本次S2通过证据；
- N0、N1协议**不提前冻结**。S3审计和图QA通过后运行`build_r5_strict_protocols.py --stage n0`；S4通过后再运行`--stage n1`，避免协议声称尚未产生的父证据。

S3基线v2已用正确SHA执行只读`validate_protocol()`，34项身份文件一致，正式输出`results/20260917_R5_STRICT_BASELINE_P0_2MS_GPU02`不存在。S2至此完成。

## 4. 全路线统一启动函数

以下PowerShell在S0—S2已经通过后使用。每条协议按上一条证据逐步冻结；每条使用独立日志，隐藏窗口启动，不覆盖现有输出。

```powershell
function Start-PaperRun {
    param(
        [Parameter(Mandatory=$true)][string]$Module,
        [Parameter(Mandatory=$true)][string[]]$RunnerArgs,
        [Parameter(Mandatory=$true)][string]$LogStem,
        [Parameter(Mandatory=$true)][string]$Role,
        [Parameter(Mandatory=$true)][string]$Protocol,
        [Parameter(Mandatory=$true)][string]$ProtocolSha
    )

    $stdout = "$Paper\logs\$LogStem.stdout.log"
    $stderr = "$Paper\logs\$LogStem.stderr.log"
    $receipt = "$Paper\logs\$LogStem.launch.json"
    foreach ($path in @($stdout,$stderr,$receipt)) {
        if (Test-Path -LiteralPath $path) { throw "REFUSING_TO_OVERWRITE: $path" }
    }

    $launchArgs = @('-m',$Module) + $RunnerArgs
    $proc = Start-Process -FilePath $Python -ArgumentList $launchArgs `
        -WorkingDirectory $Paper -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr

    Start-Sleep -Seconds 15
    $alive = [bool](Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)
    [ordered]@{
        role = $Role
        started = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        pid = $proc.Id
        alive_after_15s = $alive
        python = $Python
        module = $Module
        arguments = $launchArgs
        protocol = $Protocol
        protocol_sha256 = $ProtocolSha
        stdout = $stdout
        stderr = $stderr
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receipt -Encoding utf8

    if (-not $alive) { throw "PROCESS_DID_NOT_SURVIVE_STARTUP: $receipt" }
    return $proc.Id
}
```

启动后只做两次短检查：15秒确认进程存活与stderr，约45秒确认首个合法solver/状态记录。合计不超过60秒；随后让分离进程自行运行，不循环监控、不创建计划任务。

## 5. 三条全路线命令与逐条释放

### S3：严格P0基准

```powershell
$BaselineProtocol = "$Paper\protocol\R5_STRICT_BASELINE_P0_2MS_GPU_20260917_v2.json"
$ExpectedBaselineSha = 'ded690eb5bcf1ea5df3346a530bbb8e44a498ec6f5b9a0406e089ab7c3493477'
$BaselineSha = (Get-FileHash -LiteralPath $BaselineProtocol -Algorithm SHA256).Hash.ToLower()
if ($BaselineSha -ne $ExpectedBaselineSha) { throw "BASELINE_PROTOCOL_SHA_MISMATCH: $BaselineSha" }
$Deadline = [DateTimeOffset]::Now.AddHours(5).ToUnixTimeSeconds()

$BaselinePid = Start-PaperRun `
  -Module 'paper_v4_core.diagnostics.full_route_gpu_runner' `
  -RunnerArgs @('--protocol',$BaselineProtocol,'--protocol-sha',$BaselineSha,'--backend','gpu','--deadline-unix',"$Deadline") `
  -LogStem '20260917_r5_strict_baseline_p0_gpu02' `
  -Role 'R5 strict same-backend P0 baseline' `
  -Protocol $BaselineProtocol -ProtocolSha $BaselineSha
```

完成后按“科学审计→出图→人工视觉QA”执行，绘图会把已完成的审计状态写入图和manifest：

```powershell
& $Python tools\r4_single_run_audit.py --runs results/20260917_R5_STRICT_BASELINE_P0_2MS_GPU02 --write
& $Python tools\r4_cell_figure.py --run results/20260917_R5_STRICT_BASELINE_P0_2MS_GPU02
```

打开PNG核对轨迹、误差、力、轮胎/支承、请求/实际转角和墙钟面板；确认无裁切、错标、统计口径混用后，才把`figures/figure_manifest.json`的`figure_status`从`PENDING_VISUAL_QA`改为`PASS_VISUAL_QA`并登记复核说明。只有`COMPLETED 2379/2379`、`PASS_SINGLE_RUN_AUDIT`、PNG/SVG齐全且视觉QA PASS，才运行：

```powershell
& $Python tools\build_r5_strict_protocols.py --stage n0
```

该命令会拒绝缺失/失败父证据并生成N0 v2，禁止手工绕过。

### S4：严格R5-N0

仅在S3全部通过且`--stage n0`成功后执行。`r5_runner`的严格求解器设置由冻结协议读取并写回metrics：

```powershell
$N0Protocol = "$Paper\protocol\R5_STRICT_N0_GPU_20260917_v2.json"
$N0Sha = (Get-FileHash -LiteralPath $N0Protocol -Algorithm SHA256).Hash.ToLower()
$N0Deadline = [DateTimeOffset]::Now.AddHours(5).ToUnixTimeSeconds()

$N0Pid = Start-PaperRun `
  -Module 'paper_v4_core.r5_runner' `
  -RunnerArgs @('--out','results/20260917_R5_STRICT_N0_GPU02','--noise','none','--seed','5105','--backend','gpu','--deadline-unix',"$N0Deadline",'--protocol',$N0Protocol,'--protocol-sha',$N0Sha) `
  -LogStem '20260917_r5_strict_n0_gpu02' `
  -Role 'R5 strict legal-information noiseless' `
  -Protocol $N0Protocol -ProtocolSha $N0Sha
```

`--deadline-unix`是S1必须新增的接口；协议、命令和回执三处必须一致。

完成后执行：

```powershell
& $Python tools\r5_single_run_audit.py --runs results/20260917_R5_STRICT_N0_GPU02 --write
& $Python tools\r4_cell_figure.py --run results/20260917_R5_STRICT_N0_GPU02
```

人工视觉QA通过后执行新N0相对新基线的专用无操作门：

```powershell
$N0Sha = (Get-FileHash -LiteralPath $N0Protocol -Algorithm SHA256).Hash.ToLower()
& $Python tools\r5_strict_no_op_gate.py `
  --protocol $N0Protocol --protocol-sha $N0Sha `
  --out analysis/20260917_R5_STRICT_N0_NO_OP_01
```

该工具比较协议登记的60个有效列和时间列，输出`no_op.json`、PNG、SVG与根目录`figure_manifest.json`。`max_e_g_m`修复后必须纳入比较，不得沿用旧v2门协议对桩值列的排除理由。科学状态通过后还要打开PNG完成视觉QA并登记`PASS_VISUAL_QA`，最后才运行：

```powershell
& $Python tools\build_r5_strict_protocols.py --stage n1
```

构建器会把N0审计、N0单条图、无操作报告及其图manifest全部作为N1硬前置；任一缺失或失败都拒绝生成N1协议。

### S5：严格R5-N1

仅在S4全部通过且`--stage n1`成功后执行：

```powershell
$N1Protocol = "$Paper\protocol\R5_STRICT_N1_GPU_20260917_v2.json"
$N1Sha = (Get-FileHash -LiteralPath $N1Protocol -Algorithm SHA256).Hash.ToLower()
$N1Deadline = [DateTimeOffset]::Now.AddHours(5).ToUnixTimeSeconds()

$N1Pid = Start-PaperRun `
  -Module 'paper_v4_core.r5_runner' `
  -RunnerArgs @('--out','results/20260917_R5_STRICT_N1_GPU02','--noise','basic','--seed','5105','--backend','gpu','--deadline-unix',"$N1Deadline",'--protocol',$N1Protocol,'--protocol-sha',$N1Sha) `
  -LogStem '20260917_r5_strict_n1_gpu02' `
  -Role 'R5 strict legal-information basic noise seed 5105' `
  -Protocol $N1Protocol -ProtocolSha $N1Sha
```

完成后依次执行`r5_single_run_audit.py --write`和`r4_cell_figure.py`，再做人工视觉QA。图中必须同时显示：请求转角最大值、15°边界、实际转角、全子步轮胎/支承门值、点力、构形误差、求解耗时和单条审计状态。任一FAIL时停止，不运行R5总门。

## 6. 总门与最终图

只有S3/S4/S5三条均满足以下条件，才冻结新的R5总门协议；旧v2保留，不覆盖：

- 2379/2379且status=COMPLETED；
- 单条科学审计PASS；
- PNG/SVG及manifest齐全，`figure_status=PASS_VISUAL_QA`；
- 三条solver_settings逐项相同；
- S4相对S3的无操作门通过；
- S5请求转角、实际转角和全部物理门通过；
- 所有身份哈希指向本次新链，不引用旧GPU01/02混合结果。

新门协议建议使用`protocol/R5_INFORMATION_GATE_20260917_v3.json`，但若代码或输入身份在冻结前再改，应递增版本，不强占v3。门工具必须把三条`single_run_audit.json`和三条图manifest列为身份文件。

三条证据齐全后先冻结总门：

```powershell
& $Python tools\build_r5_strict_protocols.py --stage gate
```

门命令形式：

```powershell
$GateProtocol = "$Paper\protocol\R5_INFORMATION_GATE_20260917_v3.json"
$GateSha = (Get-FileHash -LiteralPath $GateProtocol -Algorithm SHA256).Hash.ToLower()
& $Python tools\r5_information_gate.py `
  --protocol $GateProtocol --protocol-sha $GateSha `
  --out analysis/20260917_R5_STRICT_INFORMATION_GATE_01
```

随后以参数化后的绘图工具生成独立最终目录，例如`analysis/20260917_R5_STRICT_INFORMATION_FIGURES_01/figures/`。没有总门JSON、PNG/SVG、manifest和人工视觉检查，不得在`experiment.md`写R5通过。

## 7. 立即停止条件

出现任一项即保存现状并停止依赖项：

- 协议/源码/环境身份不一致，或正式输出目录已存在；
- CUDA设备不是冻结的目标设备，`imported_after_startup`出现新禁止模块，或GPU身份门失败；
- solver非有限、`solved inaccurate`、迭代耗尽、非线性复核失败；
- 请求转角越界超过本次前瞻性登记的数值阈值，或实际转角越过15°机器精度门；
- 点力>15000 N、轮胎利用率>1、支承载荷<0；
- 进程外部终止、超5小时、输出缺项或stderr出现未解释错误；
- 单条审计FAIL、图缺失、图语义错误或视觉QA FAIL；
- 新N0与新基准无操作门失败；
- 任一工具试图覆盖旧证据。

停止后不得自动放宽容差、替换旧run、拼接前缀或继续下一条。先在`experiment.md`与`exp_status.md`登记问题、修法和已达到的效果，再决定是否另冻新版本。

## 8. 完成清单

- [x] S0环境与无冲突进程核实；Python/OSQP/CUDA已登记。
- [x] S1代码修补完成，科学审计与图QA循环依赖已解除。
- [x] S2编译、五项拒绝测试、15 tick固定QP探针及两组图QA通过。
- [x] S3基线v2协议冻结并通过只读身份验证；全路线尚未启动。
- [ ] S3严格基准GPU02完成2379/2379、审计PASS、图QA PASS。
- [ ] S4严格N0 2379/2379、审计PASS、图QA PASS、无操作门PASS。
- [ ] S5严格N1 2379/2379、审计PASS、图QA PASS。
- [ ] 新总门协议身份正确，读取三条审计和三条图manifest。
- [ ] R5严格总门PASS并生成最终PNG/SVG与manifest。
- [ ] `experiment.md`和`exp_status.md`回填实际结果、问题修法与效果。

只有全部勾选后，状态才能从`R5_TOTAL_GATE_BLOCKED`改为`PASS_R5_INFORMATION_GATE`。R5通过也不释放E05；仍须先完成C4/E01的24条无通过证据项、E02预测资格、E03控制/因果门和E04共同架构。

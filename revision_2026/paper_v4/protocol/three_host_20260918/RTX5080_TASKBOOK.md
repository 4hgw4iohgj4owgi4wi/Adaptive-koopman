# RTX 5080本机小任务书：严格R5、V2冻结和中央验收

版本：`H5080-TASK-20260918-v1`  
权威总分工：`experiment.md`第61节  
当前状态：`S4_N0_PASS / N1_V3_READY / PREFLIGHT_PASS / N1_NOT_STARTED`

## 1. 本机只做什么

1. 冻结并验证当前GPU01链的N1 v3父证据协议；
2. 独占RTX 5080运行严格N1；
3. N1结束后完成科学审计、PNG/SVG、人工图检；
4. 三条严格链全部通过后生成R5总门和最终图；
5. R5闭合后实施已登记的GPU维护修补、测试并冻结V2；
6. 作为三机结果的唯一中央汇总端。

本机在N1运行期间不并发G0—G2、E01或其他GPU动力学。N1不能转移到5060或3050。

## 2. 启动前文件

先核对`RTX5080_REQUIRED_FILES.json`。关键文件：

本机备份传输包为`transfer/three_host_20260918/RTX5080_TASK_PACKAGE.zip`，SHA见`package_index.json`；正常情况下无需解压覆盖当前工作树。

- `tools/build_r5_strict_n1_gpu01_v3.py`
- `protocol/R5_STRICT_N1_GPU_20260918_v3.json`
- `protocol/three_host_20260918/RTX5080_PREFLIGHT.ps1`
- N0当前35/35审计、当前图manifest、无操作门JSON和无操作门图manifest

现有`R5_STRICT_N1_GPU_20260918_v2.json`保留历史只读，不用于本次启动。

当前已冻结v3：`protocol/R5_STRICT_N1_GPU_20260918_v3.json`，SHA-256=`5966bd91755abc1c6ffc7e2be03931dcd8440bbf7e0447bddfd9f2c04f4bdf49`，身份文件38项。2026-09-18 15:30本机只读预检已通过；正式启动前仍须再运行一次预检。

若v3尚不存在，只允许运行一次：

```powershell
Set-Location 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\paper_v4'
$Python = 'E:\anaconda\envs\pytorch_new\python.exe'
& $Python -B tools\build_r5_strict_n1_gpu01_v3.py --dry-run
& $Python -B tools\build_r5_strict_n1_gpu01_v3.py
```

若v3已经存在，不再运行构建器，不覆盖协议。

## 3. 唯一预检入口

```powershell
Set-Location 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\paper_v4'
& powershell -ExecutionPolicy Bypass -File protocol\three_host_20260918\RTX5080_PREFLIGHT.ps1
```

只有输出`PASS_RTX5080_PREFLIGHT`才继续。预检会检查RTX 5080、全部协议身份、无实验进程和N1输出不存在。

## 4. N1启动

```powershell
$Paper = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\paper_v4'
$Python = 'E:\anaconda\envs\pytorch_new\python.exe'
$Protocol = "$Paper\protocol\R5_STRICT_N1_GPU_20260918_v3.json"
$Sha = (Get-FileHash -LiteralPath $Protocol -Algorithm SHA256).Hash.ToLower()
$Deadline = [DateTimeOffset]::Now.AddHours(5).ToUnixTimeSeconds()
$Out = 'results/20260917_R5_STRICT_N1_GPU01'
$Stdout = "$Paper\logs\20260918_r5_strict_n1_gpu01.stdout.log"
$Stderr = "$Paper\logs\20260918_r5_strict_n1_gpu01.stderr.log"
$Receipt = "$Paper\logs\20260918_r5_strict_n1_gpu01.launch.json"

foreach($p in @((Join-Path $Paper $Out),$Stdout,$Stderr,$Receipt)) {
    if(Test-Path -LiteralPath $p){ throw "REFUSING_TO_OVERWRITE:$p" }
}
$env:PYTHONPATH = "$Paper\src"
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$proc = Start-Process -FilePath $Python -WorkingDirectory $Paper -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr `
  -ArgumentList @('-B','-m','paper_v4_core.r5_runner','--out',$Out,'--noise','basic','--seed','5105','--backend','gpu','--deadline-unix',"$Deadline",'--protocol',$Protocol,'--protocol-sha',$Sha)
[pscustomobject]@{pid=$proc.Id;started=(Get-Date -Format o);protocol=$Protocol;protocol_sha256=$Sha;output=$Out;deadline_unix=$Deadline;python=$Python} |
  ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Receipt -Encoding utf8
```

20秒后检查进程仍存活、stderr为空；约1分钟后检查首批solver/information记录。任何身份、CUDA、求解或硬门错误立即停止并保留证据。

## 5. N1结束后的强制顺序

1. 确认`COMPLETED 2379/2379`，不得只看退出码；
2. 运行`r5_single_run_audit.py --write`。若唯一失败是图尚不存在，保留该前置审计并改名，不覆盖；
3. 运行`r4_cell_figure.py`生成PNG/SVG；人工打开图，核对轨迹、误差、力、冲量、轮胎/支承、请求/实际转角、耗时和审计状态；
4. 登记`PASS_VISUAL_QA`后重跑最终审计，保留旧审计；
5. 若需重画带最终审计状态的图，把首版图移到`figures_superseded_*`并标原因，再生成当前`figures/`；
6. 任一科学FAIL保持R5总门`BLOCKED`，不得把视觉PASS写成科学PASS。

每个实际实验必须有PNG、SVG和manifest。严格N1通过后，另建版本化R5总门协议；现有旧GPU02构建路径不得直接复用。

## 6. V2和远端回拷

R5总门闭合后才修改GPU实现并冻结V2。冻结后先在本机重做5080正式G0—G2和跨设备参考短窗，再向5060/3050发放同一V2整包。

远端包只进入`transfer/`暂存区；先校验SHA，再导入新目录。传输成功不等于科学通过。C4证据矩阵和plant gate只在本机汇总，必须同时保留远端PASS、FAIL及被取代版本。

## 7. 完成清单

- [x] N1 v3协议已冻结，38项身份全部匹配，当前输出不存在。
- [ ] 正式启动前再次运行只读预检并保存输出。
- [ ] N1完成2379/2379。
- [ ] N1科学审计全部PASS。
- [ ] N1 PNG/SVG与视觉QA PASS。
- [ ] R5总门和最终图PASS。
- [ ] GPU维护修补通过并冻结V2。
- [ ] 5080正式G0—G2及跨设备参考侧完成。
- [ ] 远端回拷按SHA验收，plant gate由本机重建。

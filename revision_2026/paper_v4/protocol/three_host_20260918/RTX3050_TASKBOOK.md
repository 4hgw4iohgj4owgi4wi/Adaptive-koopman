# RTX 3050小任务书：短型资格、E16反例和独立证据审查

版本：`H3050-TASK-20260918-v1`  
权威总分工：`experiment.md`第61节  
当前授权：`DEV_PRE_V2_FIXED_SAMPLE_AND_NON_DYNAMICS_ONLY`

## 1. 本机职责

3050不承担严格R5，也不默认承担全路线。当前负责：环境/树身份、DEV版G0—G2固定样本、E16四类负向例、E00/E17来源与证据审计、回拷校验演练。V2后可承担短型资格、植物单元残差登记和独立图表/证据复核。

## 2. 接收文件并预检

传输文件为`transfer/three_host_20260918/RTX3050_TASK_PACKAGE.zip`，压缩包SHA见`package_index.json`。解压后按`RTX3050_REQUIRED_FILES.json`核对SHA，保持完整`paper_v4`相对层级。

```powershell
Set-Location '<3050上的paper_v4绝对路径>'
$TaskPy = '<3050上的Python 3.11环境python.exe>'
& powershell -ExecutionPolicy Bypass -File protocol\three_host_20260918\RTX3050_PREFLIGHT.ps1 -Python $TaskPy
```

只有`PASS_RTX3050_PREFLIGHT`才继续。把输出保存到`analysis/20260918_H3050_PRE_V2_01/host_preflight.json`。

## 3. DEV版G0—G2

```powershell
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& $TaskPy -B tools\build_device_g0_g2_protocol.py `
  --device-tag RTX3050 --host-tag H3050 --phase DEV_PRE_V2 --date 20260918 `
  --taskbook protocol/three_host_20260918/RTX3050_TASKBOOK.md --dry-run
& $TaskPy -B tools\build_device_g0_g2_protocol.py `
  --device-tag RTX3050 --host-tag H3050 --phase DEV_PRE_V2 --date 20260918 `
  --taskbook protocol/three_host_20260918/RTX3050_TASKBOOK.md

$Protocol = 'protocol\RTX3050_G0_G2_20260918_DEV_PRE_V2_v1.json'
$Sha = (Get-FileHash -LiteralPath $Protocol -Algorithm SHA256).Hash.ToLower()
& $TaskPy -B tools\gpu_g0_g2_qualify_device.py `
  --protocol $Protocol --protocol-sha $Sha `
  --out results\20260918_H3050_G0_G2_DEV_PRE_V2_01
```

人工检查环境、归一化误差、QP/耗时三组PNG；PNG/SVG和manifest缺失即任务未完成。3050性能不达5 s可如实FAIL性能/排产，但不能通过减小正式问题规模或放宽数值门伪装通过。

## 4. E16负向测试

```powershell
& $TaskPy -B tools\e16_negative_cases_three_host.py `
  --spec protocol\three_host_20260918\RTX3050_E16_CASES.json `
  --out analysis\20260918_H3050_E16_NEGATIVE_CASES_01
```

必须交付：`counterexamples.json`、`trajectories.csv`、三组PNG/SVG、`figure_manifest.json`和README。人工检查gamma分支、非正规瞬态和切换增长图后登记视觉QA。

这些结果只证明某些推论不成立：

- `gamma=0`不能修复已经超界的基础块；
- 谱半径小于1不排除非正规瞬态增长；
- 每个模式单独稳定不推出任意切换稳定。

不得写成“闭环稳定性已证明”或“递归可行性已证明”。

## 5. E00/E17审计与V2后工作

当前只读审计来源、许可证、数据角色、协议身份、缺图和独立证据缺口，输出覆盖JSON和PNG/SVG，不运行动力学。回拷演练使用小型虚拟包，记录相对路径、大小和SHA，不直接写5080活动目录。

V2到达后重做3050固定样本资格。3050可执行/复核E01静态平衡、单连接器、匀速平移、纯几何转弯的归一化残差登记，并独立检查5060回传的图注、失败状态和收敛矩阵；正式24格动力学仍由5060保持单设备矩阵。

## 6. 完成清单

- [ ] 3050环境和树身份登记完成。
- [ ] DEV G0—G2、三组图和图QA完成。
- [ ] E16四类负向例全部产生JSON/CSV、PNG/SVG和manifest。
- [ ] E00/E17来源与证据覆盖审计完成。
- [ ] 回拷SHA演练完成。
- [ ] V2后重做短型资格和E01单元残差登记。
- [ ] 对5060正式E01结果完成独立证据与图表复核。

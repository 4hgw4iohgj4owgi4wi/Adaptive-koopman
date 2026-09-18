# RTX 5060小任务书：设备资格与V2后E01正式动力学

版本：`H5060-TASK-20260918-v1`  
权威总分工：`experiment.md`第61节  
当前授权：`DEV_PRE_V2_FIXED_SAMPLE_AND_PREPARATION_ONLY`

## 1. 当前可以做什么

V2冻结前只做：环境/代码树身份、DEV版G0—G2固定样本、性能/显存估时、E01工作包准备。不得跑R5、R4、正式E01、闭环或全路线。

V2冻结且5060正式资格和跨设备短窗通过后，5060成为E01正式动力学执行机，负责回头弯9格、转向切换9格、通信植物诊断6格。

## 2. 接收文件并预检

传输文件为`transfer/three_host_20260918/RTX5060_TASK_PACKAGE.zip`，压缩包SHA见`package_index.json`。解压内容保持`paper_v4`相对层级；按`RTX5060_REQUIRED_FILES.json`逐项核对SHA，不能手工改换行或编码。

```powershell
Set-Location '<5060上的paper_v4绝对路径>'
$TaskPy = '<5060上的Python 3.11环境python.exe>'
& powershell -ExecutionPolicy Bypass -File protocol\three_host_20260918\RTX5060_PREFLIGHT.ps1 -Python $TaskPy
```

只有`PASS_RTX5060_PREFLIGHT`才继续。把输出原样保存到`analysis/20260918_H5060_PRE_V2_01/host_preflight.json`。

## 3. DEV版G0—G2

```powershell
Set-Location '<5060上的paper_v4绝对路径>'
$TaskPy = '<5060上的Python 3.11环境python.exe>'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'

& $TaskPy -B tools\build_device_g0_g2_protocol.py `
  --device-tag RTX5060 --host-tag H5060 --phase DEV_PRE_V2 --date 20260918 `
  --taskbook protocol/three_host_20260918/RTX5060_TASKBOOK.md --dry-run
& $TaskPy -B tools\build_device_g0_g2_protocol.py `
  --device-tag RTX5060 --host-tag H5060 --phase DEV_PRE_V2 --date 20260918 `
  --taskbook protocol/three_host_20260918/RTX5060_TASKBOOK.md

$Protocol = 'protocol\RTX5060_G0_G2_20260918_DEV_PRE_V2_v1.json'
$Sha = (Get-FileHash -LiteralPath $Protocol -Algorithm SHA256).Hash.ToLower()
& $TaskPy -B tools\gpu_g0_g2_qualify_device.py `
  --protocol $Protocol --protocol-sha $Sha `
  --out results\20260918_H5060_G0_G2_DEV_PRE_V2_01
```

必须生成`g0_environment.json`、`g1_physics.json`、`g2_fd_qp.json`、`qualification.json`、三组PNG/SVG、`figure_manifest.json`和README。人工打开三张PNG检查标签、误差门、耗时、显存和设备名后，才能把manifest标为`PASS_VISUAL_QA`。

结果状态保持`DEV_PRE_V2 / NOT_A_FORMAL_QUALIFICATION_UNTIL_V2`。速度慢只影响排产；数值门不能放宽。

## 4. 当前E01准备

读取`RTX5060_E01_WORKPACK_DRAFT.json`，只补充协议草案、run ID和绘图合同，全部写`PREP_ONLY / NOT_RUN`。不得执行其中24格。

准备内容：

- 回头弯P0/P1/P2×2/1/0.5 ms九格；
- 转向切换P0/P1/P2×2/1/0.5 ms九格；
- 100 ms延迟和0.4 s中断，各P0/P1/P2三格；
- 每格协议SHA、输入身份、植物身份、停止规则、数据文件、PNG/SVG合同；
- 旧`HAIRPIN01/P0_2ms`失败保持FAIL，新V2运行必须使用新目录。

## 5. V2后的正式入口

收到5080发出的唯一V2整包后，旧DEV协议和结果保留，不覆盖。使用同一构建器把`--phase`改为`V2_FORMAL`，重新生成协议并重跑G0—G2。随后完成5060侧跨设备短窗；两项均通过且5080明确释放E01后，才执行24格工作包。

每条正式E01实验完成后立即出PNG/SVG和manifest。出现FAIL时保留原目录并停止依赖项；不得删失败或只传回均值。24格结束后打包原始数据、审计和图，生成SHA清单回传5080，由5080重建plant gate。

## 6. 完成清单

- [ ] 5060环境和树身份登记完成。
- [ ] DEV G0—G2数值结果、三组图和图QA完成。
- [ ] 性能/显存估时报告完成，状态保持DEV。
- [ ] E01 24格协议/图合同准备完成，状态保持NOT_RUN。
- [ ] V2到达后重新完成正式G0—G2和跨设备短窗。
- [ ] 得到5080释放后执行24格，逐条审计、出图并保留FAIL。
- [ ] 结果包和SHA清单回传5080。

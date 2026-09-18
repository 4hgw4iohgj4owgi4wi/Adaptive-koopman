# 三机任务包入口

适用机器：本机RTX 5080、远端RTX 5060、远端RTX 3050。权威总分工见`experiment.md`第61节。

| 机器 | 第一入口 | 当前角色 |
|---|---|---|
| RTX 5080 | `RTX5080_TASKBOOK.md` | 严格R5-N1、R5总门、V2冻结和中央验收 |
| RTX 5060 | `RTX5060_TASKBOOK.md` | DEV设备资格；V2后正式E01动力学 |
| RTX 3050 | `RTX3050_TASKBOOK.md` | DEV短型资格、E16反例、E00/E17审计和独立图检 |

RTX 5080当前N1启动协议：`protocol/R5_STRICT_N1_GPU_20260918_v3.json`，SHA-256=`5966bd91755abc1c6ffc7e2be03931dcd8440bbf7e0447bddfd9f2c04f4bdf49`；已通过只读预检，尚未启动。

每台机器先运行自己的`PREFLIGHT.ps1`，再按任务书执行。`REQUIRED_FILES.json`中的SHA是从5080源包生成的传输基准；远端解包后必须逐项核对。三台机器不得共享写入同一个`results/`、`analysis/`或日志目录。

可直接传输的压缩包位于`transfer/three_host_20260918/`：`RTX5080_TASK_PACKAGE.zip`、`RTX5060_TASK_PACKAGE.zip`、`RTX3050_TASK_PACKAGE.zip`。压缩包SHA见同目录`package_index.json`。

共享工具：

- `tools/build_device_g0_g2_protocol.py`：在本机读取真实torch设备名并冻结设备专属协议；
- `tools/gpu_g0_g2_qualify_device.py`：只跑G0—G2固定样本，自动生成PNG/SVG和manifest；
- `tools/e16_negative_cases_three_host.py`：执行E16登记的四类负向例，生成JSON/CSV和三组PNG/SVG；
- `tools/build_r5_strict_n1_gpu01_v3.py`：仅供5080，为当前GPU01链冻结带N0父证据的N1协议。

任务包本身不授权跨越实验门。远端`DEV_PRE_V2`结果不能因传回5080而自动升级为正式证据。

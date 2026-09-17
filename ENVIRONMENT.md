# 环境配置（Environment）

本文档记录实验环境的**精确版本与进程模型**。协议里的 `identity_files` 只钉源码与结果的 SHA，
不钉解释器与库版本，因此环境事实必须单独留痕——换一台机器跑同一份协议，若环境不同，
结果不可直接对比。

> **权威记录**是实验机上的 `results/20260915_RTX5080_G0_G2_05/g0_environment.json`
> （由 `tools/gpu_g0_g2_qualify.py` 的 G0 阶段自动生成）。该文件位于 `results/` 下，
> 按仓库约定不入库。本文档是它的可读转录 + 使用说明；出现分歧时以原文件 SHA 为准。

---

## 1. 硬件与驱动

| 项 | 值 |
|---|---|
| 主机 | `DESKTOP-9IUUGEO` |
| GPU | NVIDIA GeForce RTX 5080 |
| 显存 | 17,094,475,776 B（约 15.92 GiB） |
| Compute capability | `[12, 0]`（Blackwell，sm_120） |
| 驱动 | 595.79 |
| 角色 | 唯一已通过 G0—G2 资格的动力学执行平台 |

两台 RTX 5060 计划加入三机分发，**必须各自跑一遍 G0—G2 取得自己的资格**，
不得复用上表的资格文件（`g0.required_device_name` 与 torch 报出的设备名逐字符比较）。

---

## 2. Python 与依赖（精确版本）

| 项 | 值 |
|---|---|
| Python | 3.11.14 |
| PyTorch | `2.12.0.dev20260304+cu128` |
| torch CUDA 构建 | 12.8 |
| numpy | 2.0.1 |
| scipy | 1.17.1 |
| osqp | 1.1.1 |
| matplotlib | 用于全部出图（Agg 后端） |

本项目 GPU 端**一律 float64**（G0 的 `float64_test_finite = true`，测试结果 3680.0）。
**禁止** float32、AMP、自动微分；G0—G2 资格的 `candidate.forbidden` 里明确列出。

实验机上的解释器路径：`E:\anaconda\envs\pytorch_new\python.exe`（其他机器按自己的路径替换）。

---

## 3. 环境变量

```powershell
$env:PYTHONPATH      = "<paper_v4>\src"
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
```

线程数设为 1 是任务书 §11.2 的要求，目的是让墙钟与并发可比。

---

## 4. 进程模型（GPU 后端）

```
CPU 父进程(1 个)                        常驻 CUDA worker(1 个)
 ├─ 事件分步真实植物 (event_substep)     └─ 批量 float64 有限差分
 ├─ QP 组装 + OSQP                            （每步 85 项：1 名义 + 68 状态探针 + 16 输入探针）
 ├─ 非线性复算 / 硬门校验
 └─ 参考预览、落盘、审计
```

要点：

- **真实植物、QP 组装、OSQP、非线性硬门全部留在 CPU**；GPU 只承担预测线性化。
- worker 是常驻单进程，父进程经 IPC 调用，**不得让父进程 import torch**——
  否则会并排加载第二个 OpenMP 运行库（`libomp.dll` 与 `libiomp5md.dll`），
  在 `numpy.linalg.svd` 里触发 OMP Error #15。这条是 v1—v3 三轮失败的真实根因。
- **不使用** `KMP_DUPLICATE_LIB_OK` 绕过（它只是压制警告，可能静默算错）。

已知未闭合项（登记于 `experiment.md` §52，修复推迟到 R5 链路之后）：
worker 边界审计里 `numpy` 在启动时即存在（torch 自身会 import numpy），
故 `worker_boundary_clean` 判据恒为 False；这是**判据写法**问题，不是数值问题。

---

## 5. 新机器复现与自检

```powershell
$Paper  = "<clone>\revision_2026\paper_v4"
$TaskPy = "<你的 python.exe>"
Set-Location $Paper
$env:PYTHONPATH = "$Paper\src"; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'

# 1) 环境与设备事实
& $TaskPy -c "import torch,numpy,scipy,osqp;print(torch.__version__,torch.version.cuda,torch.cuda.is_available(),torch.cuda.get_device_name(0),torch.cuda.get_device_capability(0),torch.cuda.get_device_properties(0).total_memory,numpy.__version__,scipy.__version__,osqp.__version__)"

# 2) 代码树身份（逐份协议核对 identity_files 的 SHA）
& $TaskPy -B tools\verify_tree_identity.py --out analysis\<run_id>\tree_identity_audit.json

# 3) 设备资格（G0—G2，固定样本、分钟级；新机器必须先做）
& $TaskPy -B tools\gpu_g0_g2_qualify.py --protocol protocol\<协议>.json --protocol-sha <sha> --out results\<run_id>
```

第 3 步产出 `g0_environment.json`、`g1_physics.json`、`g2_fd_qp.json`、`qualification.json`
与三张 PNG/SVG。**只有它返回 `PASS_G0_G2_GPU_QUALIFIED`，该机器才可执行动力学实验。**

---

## 6. 已知环境坑（都踩过）

| 现象 | 根因 | 处置 |
|---|---|---|
| G1 前 `OMP Error #15` 崩溃 | 父进程被 torch 污染，双 OpenMP 运行库 | 单一常驻 worker + worker 内去 NumPy + 禁止父进程 import torch |
| 资格脚本报 `SEC_E_NO_CREDENTIALS`（TLS） | 本机 git 默认用 schannel | 仓库级 `http.sslBackend=openssl` |
| `Filename too long` | 路径最长 187 字符 | `core.longpaths true` + 短路径 clone |
| 协议 SHA 全部对不上 | `core.autocrlf=true` 做 CRLF 转换 | `.gitattributes` 写死 `* -text`，禁止换行符转换 |
| 墙钟被当成物理差异 | 比较时未排除 `solver_wall_s` / `time_s` | 物理/控制白名单比较，时间按独立合同核对 |

---

## 7. 墙钟参考（离线，不是实时）

| 运行 | 墙钟 | 说明 |
|---|---|---|
| GPU 全路线 2 ms（P0 名义） | ≈3.10 h / 2379 周期 | `results/20260916_R5_BASELINE_P0_2MS_GPU02` |
| CPU parallel8 同候选 | ≈9.4 h / 条 | 历史基准，仅作交叉核验 |
| GPU 单次固定 QP（G2） | 4.3216 s | 原 5 s 预算内；加速 3.255976× vs CPU parallel8 |

控制周期 20 ms 是**仿真时间**，与墙钟无关；上述全部为 `OFFLINE_ONLY`，
**不得据此宣称实时性**。

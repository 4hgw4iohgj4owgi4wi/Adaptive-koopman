# Adaptive-koopman

四车—货物协同运输（通信受限）的预测与控制修订工作区。
派生自上游 [Rajpal9/Adaptive-koopman](https://github.com/Rajpal9/Adaptive-koopman)（[arXiv:2405.09101](https://arxiv.org/abs/2405.09101)）；上游原文保留在 `revision_2026/00_baseline/`。

**实验代码、协议与结果全在 `revision_2026/paper_v4/`。** 执行书为 `revision_2026/paper_v4/experiment.md`（当前入口第 52 节）。

---

## 1. 环境

| 项 | 值 |
|---|---|
| Python | 3.11.x |
| PyTorch | `2.12.0.dev20260304+cu128`（CUDA 12.8，float64） |
| 依赖 | numpy 2.0.1、scipy 1.17.1、osqp、matplotlib |

```powershell
$Paper  = "<clone>\revision_2026\paper_v4"
$TaskPy = "<你的 python.exe>"
Set-Location $Paper
$env:PYTHONPATH      = "$Paper\src"
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
```

---

## 2. 克隆（两条硬性注意事项）

```powershell
git config --global core.longpaths true      # 仓库内有最长 187 字符的路径
git clone https://github.com/4hgw4iohgj4owgi4wi/Adaptive-koopman.git D:\ak
```

1. **不要开启换行符转换。** 协议 `protocol/*.json` 用 SHA-256 钉死了被引用文件的字节，CRLF/LF 归一化会让所有身份校验失败。仓库已用 `.gitattributes` 写死 `* -text`，请勿覆盖。
2. **用短路径克隆**，否则 Windows 会报 `Filename too long`。

---

## 3. 怎么运行

### 3.1 先做身份自检

```powershell
& $TaskPy -B tools\verify_tree_identity.py --out analysis\<run_id>\tree_identity_audit.json
```

逐份协议核对 `identity_files`。出现 `STALE` 不一定代表出错（结果文件本就不入库）；判断拷贝/改动是否有害，看**失配清单是否只包含你确实改过的文件**。

### 3.2 闭环运行（都必须显式传协议与协议 SHA）

```powershell
# 计算 6 小时后的截止时间戳
$deadline = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() + 6*3600
$sha = (Get-FileHash protocol\<协议>.json -Algorithm SHA256).Hash.ToLower()

# 全路线（R4）：2/1/0.5 ms，P0/P1/P2
& $TaskPy -B -m paper_v4_core.diagnostics.full_route_gpu_runner `
    --protocol protocol\<协议>.json --protocol-sha $sha --backend gpu --deadline-unix $deadline

# 有界窗口闭环（G3 类诊断）：--window 指定窗口名
& $TaskPy -B -m paper_v4_core.diagnostics.gpu_closed_loop_runner `
    --protocol protocol\<协议>.json --protocol-sha $sha --window force --backend gpu --deadline-unix $deadline

# R5 合法信息接口：--noise none(N0) / basic(N1)
& $TaskPy -B -m paper_v4_core.r5_runner `
    --out results\<run_id> --noise none --seed 5105 --backend gpu `
    --protocol protocol\<协议>.json --protocol-sha $sha

# 早期集中物理 MPC（R2/R3）
& $TaskPy -B -m paper_v4_core.pilot_runner `
    --out results\<run_id> --parameter P1 --max-step-ms 2.0 --lambda-internal 2.0
```

**规则**：输出目录**已存在即拒绝**（`REFUSING_TO_OVERWRITE_OUTPUT`）；重跑必须换新 `run_id`，不得覆盖。
`--backend` 可为 `gpu` / `cpu`（`cpu` 走 parallel8，约为 GPU 的 1/3 速度）。

### 3.3 设备资格（新机器第一次必须先做）

```powershell
& $TaskPy -B tools\build_rtx5080_v4_protocol.py            # 生成协议（自动重算全部 SHA，勿手抄）
& $TaskPy -B tools\gpu_g0_g2_qualify.py `
    --protocol protocol\<协议>.json --protocol-sha $sha --out results\<run_id>
```

资格含 G0（设备/float64）、G1（CPU↔GPU 物理等价）、G2（固定 QP 等价 + 端到端成本）。
**一台机器一份资格，不得复用别的机器的资格文件当父门。**

### 3.4 门与出图

```powershell
& $TaskPy -B tools\r4_single_run_audit.py --runs results\<run1> results\<run2> --write
& $TaskPy -B tools\r4_cell_compare.py  --protocol protocol\<协议>.json --protocol-sha $sha --out analysis\<run_id>
& $TaskPy -B tools\r4_cell_figure.py   --run results\<run_id>
& $TaskPy -B tools\r4_gate.py          --protocol protocol\<协议>.json --protocol-sha $sha --out analysis\<run_id>
& $TaskPy -B tools\r5_information_gate.py --protocol protocol\<协议>.json --protocol-sha $sha --out analysis\<run_id>
& $TaskPy -B tools\full_route_compare.py  --protocol protocol\<协议>.json --protocol-sha $sha --out analysis\<run_id>
```

### 3.5 其他入口

`python -B -m paper_v4_core.<模块> --help` 查看参数：

| 模块 | 用途 |
|---|---|
| `paper_v4_core.e01_100m` / `e01_batch` / `e01_hairpin` | E01 植物诊断（100 m 阶跃、批次、回头弯） |
| `paper_v4_core.physics_tests` / `recorder_probe` / `geometry_probe` / `transition_probe` | 单元与探针测试 |
| `paper_v4_core.identity_audit` / `data_audit` | 身份与数据角色审计 |
| `paper_v4_core.r5_information_tests` | R5 接口契约负例 |
| `paper_v4_core.diagnostics.frozen_input_replay` | 冻结输入短窗重放 |
| `paper_v4_core.cli` | 通用入口（`save` / `sha` 等） |

---

## 4. 后台运行

```powershell
$TaskStart = @{
    FilePath         = $TaskPy
    WorkingDirectory = $Paper
    WindowStyle      = 'Hidden'
    PassThru         = $true
    ArgumentList     = @('-B','-m','paper_v4_core.diagnostics.full_route_gpu_runner',
                         '--protocol','protocol\<协议>.json','--protocol-sha',$sha,
                         '--backend','gpu','--deadline-unix',$deadline)
    RedirectStandardOutput = "$Paper\logs\<run_id>.stdout.log"
    RedirectStandardError  = "$Paper\logs\<run_id>.stderr.log"
}
$TaskProcess = Start-Process @TaskStart
```

启动后写 `logs\<run_id>.launch.json`（PID、开始时间、协议 SHA、角色），最多做两次短检查即结束，不轮询。
进度看 `results\<run_id>\status.json`。

---

## 5. 运行须知（会直接影响结论有效性）

1. **协议即契约**：任何被 `identity_files` 钉住的文件（`src/paper_v4_core/**`、`experiment.md`、`protocol/*.md`、部分 `tools/*.py`）一旦改动，引用它的协议立刻失效，运行会被拒绝。改动前先确认哪些协议会过期，改完必须重新冻结身份；旧结果保留、不覆盖，不得追溯重写。
2. **同版本重跑**：控制算法或植物数值一变，2 / 1 / 0.5 ms 必须用同一新版本重跑，旧的 2 ms 不得与新 1 ms 混用。
3. **逐位门只同机**：1e-12 级别的逐位比较只允许在同一台机器的同一后端内进行；跨设备/跨后端按实测容差报告，不得写"逐位一致"。
4. **时间列不是物理量**：比较时排除 `solver_wall_s` 与 `time_s`，否则会把纯墙钟当成物理违约。
5. **硬件平台**：目前只有 RTX 5080（`DESKTOP-9IUUGEO`）通过资格；其他机器（含 RTX 5060）必须先各自跑第 3.3 节资格，再按各自设备冻结协议。
6. **数据不入库**：`results/`、`analysis/`、`logs/`、模型权重与数据集都在实验机上，以 SHA-256 与协议身份链为证据。

---

## 6. 文档入口

| 文档 | 内容 |
|---|---|
| `revision_2026/paper_v4/experiment.md` | 主执行书（物理、优化、网络、统计门、E00—E17 流程、审稿回应路线） |
| `revision_2026/paper_v4/protocol/后续实验详细任务书_20260915.md` | 接续任务树（C0—C4、K/M/N/B 等节点） |
| `revision_2026/paper_v4/protocol/RTX5060双机V2冻结前执行任务书_20260917.md` | 新机器接入步骤（环境、身份校验、资格、估时、回拷） |
| `revision_2026/paper_v4/koopman_work_log.md` | 统一工作记录（追加式） |
| `README_GIT_SCOPE.md` | 仓库收录范围与 clone 须知 |
| `ENVIRONMENT.md` | 环境配置：硬件、依赖精确版本、进程模型、已知坑 |
| `revision_2026/paper_v4/protocol/three_host_20260918/` | 三机（5080 / 5060 / 3050）任务包：各机小任务书、只读预检、必需文件 SHA 清单 |

---

## 7. 许可与来源

本项目**新增部分**按 [MIT](LICENSE) 授权。

仓库中另有一部分**派生自上游项目** [Rajpal9/Adaptive-koopman](https://github.com/Rajpal9/Adaptive-koopman)
（R. Singh, C. K. Sah, J. Keshavan, *Adaptive Koopman Embedding for Robust Control of Complex
Dynamical Systems*, [arXiv:2405.09101](https://arxiv.org/abs/2405.09101)）：

- 上游仓库**没有 LICENSE 文件**，其授权状态未由作者明确；
- 因此上述 MIT 授权**不覆盖**派生部分，至少包括 `core/`、`models/`、`dynamics/`
  以及根目录的教程 notebook（`Coupled_pendulum_*`、`Serial_Manipulators_*`、
  `Planar_Quadrotor_*`、`single_vehicle_*`、`tf3`—`tf9`、`test_single_lv*`、`testlv7z*`）；
- 具体范围见 [NOTICE.md](NOTICE.md)。若上游作者要求移除或改授，请开 issue。

本仓库还包含未发表的论文稿件（`paper_dcn_tf12_draft/`）与投稿/审稿往来材料
（`revision_2026/00_baseline/`、`revision_2026/connector_r3_4/`、`revision_2026/paper_v4/review/`）。
这些材料的著作权属作者本人；标注为期刊往来函件的内容属保密通信，**请勿转载或引用**。

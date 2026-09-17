# Adaptive-koopman：四车协同运输 · 重投稿修订工作区

> 本仓库是「四车—货物协同运输在通信受限条件下的预测与控制」修订工作的代码与规范集合。
> 它派生自上游开源仓库 [Rajpal9/Adaptive-koopman](https://github.com/Rajpal9/Adaptive-koopman)
> （论文 *Adaptive Koopman Architectures for Control of Complex Nonlinear Systems*，
> [arXiv:2405.09101](https://arxiv.org/abs/2405.09101)）。上游原始 README 与原始稿件
> 保留在 `revision_2026/00_baseline/`。

**当前状态一句话**：实验主线停在 RTX 5080 上的 `R5`（合法信息接口）阶段；速率惩罚符号缺陷已修复并量化，
六条 R4 单元需按新版本重跑；两台 RTX 5060 即将加入三机分发。
入口文档是 [`revision_2026/paper_v4/experiment.md`](revision_2026/paper_v4/experiment.md)（当前入口第 52 节）。

---

## 1. 快速开始

### 1.1 克隆（两条硬性注意事项）

```powershell
git config --global core.longpaths true      # 仓库内有最长 187 字符的路径
git clone https://github.com/4hgw4iohgj4owgi4wi/Adaptive-koopman.git D:\ak   # 目标目录尽量短
```

**绝对不要让 git 做换行符转换。** 本项目的证据是工作树字节本身：
`revision_2026/paper_v4/protocol/*.json` 里的每条 `identity_files` 都钉死了对应文件的
SHA-256。一旦发生 CRLF/LF 归一化，被钉住文件的 SHA 改变，历史协议与结果的身份校验会全部失败。
本仓库已用 `.gitattributes` 写入 `* -text` 并在仓库级设 `core.autocrlf=false`，
现状是**混合**的（`physical_tracking_pilot.py`、`experiment.md` 是 CRLF，
`plant/four_vehicle_common.py` 是 LF），**必须保持原样**。

### 1.2 运行环境

| 项 | 值 |
|---|---|
| Python | 3.11.x（实验机为 3.11.14） |
| PyTorch | `2.12.0.dev20260304+cu128`（CUDA 构建 12.8，float64 计算） |
| 依赖 | numpy 2.0.1、scipy 1.17.1、osqp、matplotlib |
| 线程 | `OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1` |
| 实验机 | `DESKTOP-9IUUGEO`（RTX 5080 16 GB，驱动 595.79） |

```powershell
$env:PYTHONPATH = "<clone>\revision_2026\paper_v4\src"
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
```

### 1.3 自检

```powershell
cd <clone>\revision_2026\paper_v4
python tools\verify_tree_identity.py --out analysis\tree_identity_audit.json
```

该脚本逐份协议核对 `identity_files` 的 SHA。在**代码子集**（本仓库）里必然出现大量 `STALE`——
被钉住的很多文件（`results/**` 的 npz 等）本来就不入库。判断 clone 是否无损的正确基准是：
**与实验机上同一脚本的输出逐字段比对**，而不是看有没有 STALE。

---

## 2. 顶层目录总览

### 2.1 入库情况一览

| 目录 | 作用 | 入库 | 体积 |
|---|---|---|---|
| `revision_2026/` | **当前全部修订工作的根**（含实验主线 paper_v4） | ✅ 2,172 文件 | 32 MB |
| `paper_dcn_tf12_draft/` | LaTeX 稿件与各轮就绪性/架构报告 | ✅ 1,446 文件 | 26 MB |
| `dynamics/` | 被控对象模型（单车、机器人、轨迹生成） | ✅ 37 文件 | 0.2 MB |
| `control_files/` | TF11—TF14 各阶段的控制实现 | ✅ 31 文件 | 0.2 MB |
| `core/` | Koopman 核心与自适应网络 | ✅ 6 文件 | 0.1 MB |
| `models/`、`tuning/`、`paths/` | Koopman 模型封装、MPC 权重调优、路径工具 | ✅ 5 文件 | <0.1 MB |
| 根目录 41 个 `.ipynb` + 14 个 `.py` | 上游教程与本项目各阶段脚本 | ✅ 59 文件 | 194 MB |
| `pinn/` | PINN / ZNN / 反步法等其他选题的资料与代码（704 MB） | ❌ | — |
| `ALL_codehub/` | 代码快照归档（1.1 GB） | ❌ | — |
| `saved_models/` | 各被控对象的模型权重 `.pth`（957 MB） | ❌ | — |
| `saved_data/`、`datasets/` | 训练/测试数据 `.npy`（244 MB） | ❌ | — |
| `results/` | 早期实验产物 | ❌ | 21 MB |
| `tf14_*`（7 个） | 早期 TF14 阶段的分阶段实验输出 | ❌ | 200 MB |
| `paper_ieee_sensors_20260625*` | 上一轮 IEEE Sensors 投稿包与模板 | ❌ | 175 MB |
| `专利/`、`专利撰写参考/` | 专利草稿与参考资料 | ❌ | 213 MB |
| `A1_snapshot_20260418/` | 早期快照 | ❌ | 90 MB |
| `archives/`、`tmp/`、`__pycache__/`、`.ipynb_checkpoints/` | 临时与缓存 | ❌ | — |
| `src/`、`scripts/`、`protocol/`、`config/`、`tests/` | **空目录**（上游模板占位，内容已迁移到 `core/`、`models/`、`dynamics/` 等；git 不跟踪空目录） | — | — |

> **为什么不入库**：整树 26.19 GB / 91,839 文件，其中 `.npz` 13.45 GB、`.csv` 4.03 GB、
> `.pkl` 2.30 GB、`.png` 1.87 GB、`.pdf` 1.62 GB，且有 5 个文件 >100 MB（GitHub 单文件硬限 100 MB）。
> 原始数据、模型权重与运行结果留在实验机上，以 SHA-256 与协议身份链作为证据。
> 详见 [`README_GIT_SCOPE.md`](README_GIT_SCOPE.md)。

### 2.2 分组说明

**① 当前主线 —— `revision_2026/`**
用于稿件 VT-2026-05393 的重投稿修改，不覆盖原 TF14 代码与原有论文材料。
其编号目录（见 `revision_2026/README.md`）：

| 子目录 | 作用 |
|---|---|
| `00_baseline/` | 原稿、审稿意见、任务书、原始代码快照及 SHA-256 清单（含上游原始 README） |
| `01_scope/` | claim–evidence 矩阵、文献定位、贡献去留决策 |
| `02_repro/` | 配置、runner、日志 schema 与统计流水线 |
| `03_irsp/` | 式 (22) 反例、IRSP 修正、测试与预实验 |
| `04_theory/` | 稳定性、递归可行性与证书审计 |
| `05_baselines/` | 强基线实现与公平性协议 |
| `06_experiments/` | 多种子实验与分析 |
| `07_force_validation/` | 连接力代理、Pareto 与高保真 / HIL |
| `08_manuscript/` | 修订论文与投稿材料 |
| `solutions/` | 证据无法支撑时的停止报告与解决方案 |
| `work_log.md` | 变更留痕 |

**② 实验主线 —— `revision_2026/paper_v4/`（最重要）**
当前所有动力学实验、协议与结果都在这里。详见第 3 节。

**③ 论文与稿件**
`paper_dcn_tf12_draft/` 是 LaTeX 稿件工作区：顶层是各轮 `publication_readiness_round*/`、
`comm_architecture_*`、`hairpin_*` 等实验与就绪性报告，`dcn_latex_zh_comm_update_r42_2026-05-14/`
存放正文 tex 与图表源。入库的只有 `.tex/.md/.json/.py` 等文本，`data/` 与图片不入库。

**④ 上游与本项目的建模代码**
`core/`（Koopman 核心、自适应网络 `adapt_net*.py`）、`models/`（`koop_model.py`）、
`dynamics/`（`single_vehicle/`、`robot_models/`、`TrajGen/`、`learned_models_control/`）、
`control_files/`（按 `tf11_a1/ tf12/ tf13/ tf14/` 分阶段的控制器）、`tuning/`（MPC 权重调优）、
`paths/paths.py`。

**⑤ 历史版本迭代（均在 `revision_2026/` 下，多数只入库代码/记录，结果不入库）**
- `paper_v1/ paper_v2/ paper_v3/ paper_v3_results/ paper_v4/ paper_v4_results/`：论文与实验的版本演进
- `koopman_predict_v3*`（`r/s/t/u/v/w/x/y`）、`koopman_predict_v2/auto/next`、`koopman_next*`、
  `koopman_focus*`、`koopman_icr_*`、`koopman_ab_*`、`koopman/`：Koopman 预测器的多轮实现与结果
- `connector_v2/`、`connector_r3*`（含 `_1`—`_4` 与各自的 `_data/_models/_mpc/_results`）：连接器模型迭代
- `model/`（`c1/ c2/ c3/ comm/ force_test/`）：模型侧试验
- `nkca_v1/`：**独立的本地 git 仓库**（分支 `exp/no-koopman-control-v1-20260824`、
  `snapshot/no-koopman-base`，无 remote），未入本仓库，需要时单独推送
- 根级 `koopman_work_log.md`、`exp_status.md`、`exp_solution.md`、`work_log.md` 及
  `koopman_*.md` 系列：各阶段工作记录与审查

**⑥ 根目录 notebook 与脚本**
- 上游教程：`Coupled_pendulum_*.ipynb`、`Serial_Manipulators_*.ipynb`、
  `Planar_Quadrotor_*.ipynb`、`single_vehicle_*.ipynb`
- 本项目阶段：`tf3`—`tf14` 系列、`test_single_lv*.ipynb`、`test_fourth_lv*.ipynb`、`testlv7z*.ipynb`
- 脚本：`tf10_paper_figs.py`、`tf11_a1_*.py`、`tf11_a2_runtime.py`、`tf12_*.py`、
  `tf13_c_runner.py`、`tf14_runtime.py`、`inspect_npz_r3.py`、`cacaNEW.py` 等

---

## 3. `revision_2026/paper_v4/` 详解（当前实验主线）

### 3.1 目录

| 路径 | 作用 |
|---|---|
| `src/paper_v4_core/` | 全部实验代码（见 3.2） |
| `tools/` | 协议生成、比较、审计、出图、门工具（不参与冻结身份的核心计算） |
| `protocol/` | **冻结协议与任务书**：`*.json` 协议钉死 `identity_files` 的 SHA-256；`后续实验详细任务书_20260915.md`、`RTX5060双机V2冻结前执行任务书_20260917.md` 等 |
| `results/` | 每次运行的原子产物（`raw.npz`、`substeps.npz`、`solver.jsonl`、`metrics.json`、`status.json`…），**不入库** |
| `analysis/` | 只读分析与比较产物（含 `figure_manifest.json`），**不入库** |
| `logs/` | 后台启动回执与 stdout/stderr，**不入库** |
| `audit/` `gates/` `review/` | 身份审计、门裁决、审稿映射（小型 JSON，入库） |
| `inputs/` | 冻结输入与历史任务书快照 |
| `tests/` `tests_tmp*/` | 单测与临时测试目录 |
| 根级 `.md` | 执行书与专项记录：`experiment.md`（主执行书）、`exp_status.md`、`exp_solution.md`、`koopman_work_log.md`、`gpu_platform_decision_20260916.md`、`qp_rate_penalty_sign_defect_20260916.md`、`compliance_audit_20260916.md` 等 |
| `run_r3_unfrozen.cmd` | 早期 R3 运行入口脚本 |

### 3.2 `src/paper_v4_core/` 子包与实际实现范围

| 子包 / 文件 | 作用 |
|---|---|
| `plant/` | 冻结植物：`four_vehicle_common.py`（四车—货物模型）、`event_substep.py`（事件分步积分器）、`connector_adapter.py`/`connector_r3.py`/`connector_v1.py`（连接器本构）、`load_transfer.py`（载荷转移）、`internal_force.py`（内力分解）、`steering_allocator.py`（转向分配） |
| `controllers/` | `physical_tracking_pilot.py`（集中全状态物理 MPC，QP 决策 + 非线性复算）、`parallel_fd_backend.py`（CPU parallel8 有限差分后端） |
| `gpu_port/` | CUDA 后端：`physics_torch.py`、`rollout_batch.py`、`gpu_worker.py`（独立 worker 进程）、`ipc_backend.py`（父进程 ⇄ worker 的 IPC 与不变式检查） |
| `information/` | `legal_information.py`：合法信息接口（按绝对 tick 派生噪声、包时间戳与年龄） |
| `diagnostics/` | 各类 runner 与分析：`gpu_closed_loop_runner.py`（有界窗口闭环）、`full_route_gpu_runner.py`（全路线）、`post_r3_r4_runner.py`、`r4b_*`、`r4c_full_runner.py`、`frozen_input_replay.py`、`qp_*` 诊断、`relative_motion.py`、`internal_loading.py` |
| `e01_*.py` | E01 植物诊断：100 m 诊断、回头弯、批次入口与分析 |
| `r5_runner.py` / `r5_information_tests.py` | R5 合法信息闭环 runner 与其契约负例 |
| `r1_diagnose.py` / `r2a_tests.py` / `r3_*.py` / `r4_*.py` | 各阶段（R1—R4）诊断、批次与分析入口 |
| `pilot_runner.py` | 早期集中物理 MPC 闭环 runner（R2/R3 使用） |
| `cli.py` | 通用入口：`save`、`sha` 等工具函数 |
| `references.py` / `reference_geometry.py` | 路线与参考几何（正弦、单移线、回头弯、100 m 诊断） |
| `identity_audit.py` / `candidate_identity.py` / `data_audit.py` | 身份与数据角色审计 |
| `failure_boundary*.py` / `recorder_probe.py` / `geometry_probe.py` / `transition_probe.py` / `dynamic_smoke.py` | 记录边界与探针单测 |

> **尚未实现**：`experiment.md` 第 12 节规划的 `network/`、`robust/`、`estimation/`、
> `faults/`、`models/`（`physical/fixed_linear/lifted/bilinear/guarded_residual/gated`）、
> `theory/` 等模块目前**都还不存在**。请勿把规划中的接口当成已有代码调用——
> 执行书里"应实现"不等于"已实现"。

### 3.3 已核实的实验现场（截至 2026-09-17）

| 项 | 状态 |
|---|---|
| R4 六条（P1/P2 × 2/1/0.5 ms） | 六条**全部完成**过，四个步长配对门全通过；但因速率惩罚符号缺陷（`qp_rate_penalty_sign_defect_20260916.md`）**必须用修复版重跑** |
| C1/R4 总 PASS | 已达成过，但认证的是**缺陷控制器版本**，重跑后需重建 |
| R5-N0（无噪声合法信息） | 运行中（2379 tick 全程） |
| R5-N1（基础噪声） | **协议身份已失效**（`r5_runner.py`、`physical_tracking_pilot.py` 均有改动），启动前必须重生成协议 |
| GPU 资格 G0—G2 | RTX 5080 已 PASS；两台 RTX 5060 需各自重新资格化，**不得复用 5080 的资格文件** |

---

## 4. 关键文档入口

| 文档 | 内容 |
|---|---|
| `revision_2026/paper_v4/experiment.md` | **主执行书**：物理/符号/参考、优化定义、预测方法、网络协议、数据与统计门、E00—E17 逐实验流程、批次预算、审稿逐点回应路线。当前入口为第 52 节 |
| `revision_2026/paper_v4/protocol/后续实验详细任务书_20260915.md` | R3 通过后的接续任务书（C0—C4、K/M/N/B/A/S/V/T/W 节点） |
| `revision_2026/paper_v4/protocol/RTX5060双机V2冻结前执行任务书_20260917.md` | 两台 RTX 5060 的可执行步骤（环境、身份校验、G0—G2、估时、回拷） |
| `revision_2026/paper_v4/koopman_work_log.md` | 统一工作记录（追加式，不覆盖） |
| `revision_2026/paper_v4/exp_status.md` | 状态流水 |
| `revision_2026/README.md` | 修订工作区的目录约定 |
| `README_GIT_SCOPE.md` | 本仓库的收录范围与 clone 须知 |

---

## 5. 上游来源与引用

本仓库的建模代码与教程 notebook 派生自：

- R. Singh, C. K. Sah, J. Keshavan, *Adaptive Koopman Embedding for Robust Control of
  Complex Dynamical Systems*, arXiv:2405.09101 (2024).
  上游仓库：<https://github.com/Rajpal9/Adaptive-koopman>

在上游代码基础上，本仓库增加了四车—货物协同运输的植物模型、事件分步积分器、连接器本构、
集中物理 MPC、CUDA 有限差分后端、合法信息接口、以及配套的协议 / 审计 / 出图工具链。

若在学术工作中使用本代码，请同时引用上游论文与本项目对应的修订稿件。

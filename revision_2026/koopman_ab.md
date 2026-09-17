# Koopman 双路执行书：退化解剖 → 人工决策 → 域回退/场景均衡 → V0/C0

> 文档性质：二次授权执行书（承接 KFIX F4 BLOCKED）。只编写方案，不授权立即执行。
> 编写时间：2026-09-03（Asia/Shanghai）
> 执行机器：5080 工作站 `DESKTOP-9IUUGEO`
> 项目根目录：`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`
> 父任务书：`revision_2026\koopman_fix.md`，SHA256 `64A61DF224EF5F8B56D0A6298D15080B797792DD1B669B295B537ACB73803927`
> 父正式运行：`revision_2026\koopman_predict_v3r_results\runs\20260903_041205_KFIX_R01`（F4 BLOCKED，2026-09-03 09:52）
> 授权边界：以后用户说"按 koopman_ab.md 执行"，默认第一轮只执行 `Q0→Q1` 并在 Q1 后人工停止；Q2 是人工决策；AR/SB/V0/C0 需逐次明确授权。
> 本执行书文件在远端冻结后，其 SHA 进入所有后续 run 的身份链。

---

## 0. 先给结论

1. F4 的干净复验已经确立**本轮唯一要保护的正创新**：等预算多时域残差 Koopman（MH16）相对 S0 的 20 步 macro 改善 **+20.08%**（5/5 折）、D5 困难窗 **+29.8~47.9%**，且 0 发散、力/内部力门全过。它的唯一缺陷是 D10/D11 退化 24–35%。
2. 本执行书**不修改、不否定、不重训 MH16 这一既有发现**，只解决一个问题：**如何把 +20% 变成一个可过 V0/C0 门禁、可写进论文的方法**。两条路：AR（域回退，零训练）与 SB（场景均衡重训，一轮 GPU）。
3. 两条路的共同前置是 **Q1 只读解剖审计**：先搞清楚 D10/D11 退化是"少数窗口的尾部"还是"振荡相位误差"还是"弥散全工况"，再用证据选路——**不允许在没有审计结论时凭感觉选路**。
4. 本执行书内置**冒险预算**：允许"预计成效可量化、失败可止损"的冒险（如单发场景均衡、双臂预注册、40 步预检）；禁止一切以破坏已有正创新、盲 confirm 资产或冻结证据链为代价的冒险。
5. 终点只有一个：某条路线的证据通过 **V0（新 validation）→ C0（盲 confirm）**，或按规则停在负结果并收缩论文主张（方案 C）。confirm 读取计数必须始终保持 0，直到 C0。

---

## 1. 冻结基线与创新资产

### 1.1 冻结身份（Q0 必须复核）

| 对象 | SHA256 / 值 |
|---|---|
| F4 run_id | `20260903_041205_KFIX_R01` |
| v3r source manifest（49 文件） | `DB0EF974024B53F243A7800110D028E917131AF7E52D0BB0E4E2FEFBF72AD3C5` |
| 父任务书 koopman_fix.md | `64A61DF224EF5F8B56D0A6298D15080B797792DD1B669B295B537ACB73803927` |
| F4 protocol | `CAC4D2DD37A90C72524968A6AF7146EDE13D808D2E932DF3F7D63802DE3B7EAC` |
| F4 data manifest | `B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9` |
| N6 S0 `J20_common`（development） | `0.13023504180689485` |
| 新 validation 封存账本 | seed_start `991000`，48 base family，168 条轨迹，**只允许 V0 一次打开** |
| confirm | 96 base family，**读取计数 0**（Q0 复核） |
| 旧 validation | `CONTAMINATED_D5_BY_AF`，永久降级，任何阶段不得用于选择 |

### 1.2 冻结数据事实（Q1 审计的对照基准）

| 工况 | development 20 步窗口数 | S0 J20（development） | 说明 |
|---|---:|---:|---|
| D0 | 448 | 0.044671 | 稳态骨干 |
| D1 | 608 | 0.081258 | 纵向载荷转移 |
| D2 | 3,250 | 0.151906 | 窗口最多（~10 倍于 D7），主导梯度 |
| D3 | 912 | 0.071826 | 稳态弯 |
| D4 | 912 | 0.083234 | 横向过渡 |
| D5 | 1,056 | 0.102492 | 回头弯；困难窗 start∈{100,120} |
| D6 | 816 | 0.075727 | 入弯-稳态-出弯 |
| D7 | 336 | 0.326562 | 窗口最少、第二难 |
| D8 | 672 | 0.081098 | 左右内力 |
| D9 | 672 | 0.190007 | 内力零空间 |
| D10 | 912 | **0.344499** | 最难；8 s chirp，转向包络 8°，纵向正弦 0.12 m/s² |
| D11 | 1,152 | 0.076591 | 窗口第二多但 S0 很简单；10 s 混合正弦 |

F4 冻结裁决（`f4_verdict.json`，Q0 复核）：MH16 macro +20.078%（逐折 21.81/19.61/21.63/16.32/21.02），D5 困难窗逐折 +32.79/+36.80/+46.11/+29.77/+47.88；ONE16 +0.015%（3/5 折）；H1=+20.06、H2=+0.024、H3=-2.39；唯一失败门 `scenario_degradation`（D10/D11 退化 24–35%）。

### 1.3 创新资产保护清单（本轮任何动作不得损害，Q0 逐项核验）

| # | 资产 | 保护规则 |
|---|---|---|
| P1 | MH16 +20% 正结果及其逐窗 rows、best.pt | 只读；SHA 冻结；任何新 run 不得复制其 `.pt`；引用必须带 run_id；禁止用 D10/D11 退化否定整个多时域发现，权衡必须如实但结论分级 |
| P2 | v3r 基础设施（E01–E18 修复 + 57 项测试） | 只读；SB 路线只能在新 `koopman_predict_v3s` 目录改代码；57 项既有测试在 v3s 必须全绿 |
| P3 | confirm 盲区 | 读取计数 0；任何阶段读取即该 run 全链作废 |
| P4 | 新 validation 封存账本（991000） | 只有 V0 授权后一次性打开；打开前不得读取任何状态值/性能信息 |
| P5 | 物理/执行器冻结身份（A3 执行器、R3 连接器、D0–D11 合同、S0 骨干、N6 数据） | 禁止修改；Q0 核 SHA；S0 预测可重新生成但身份必须逐元素比对 |
| P6 | E01–E18 纠错链 | 新代码必须通过防回归测试（见 SB2），禁止旧缺陷（`.item()` 断梯度、best/stop 混淆等）以新形式回归 |
| P7 | 权衡负结果本身（D10/D11 −24~35%） | 论文与报告必须如实保留，任何路线都不得删除失败工况/窗口后再统计 |

---

## 2. 总任务树与授权边界

```text
Q0  现场身份与创新资产核验（只读，30 分钟）
  ↓
Q1  D10/D11 退化解剖审计（只读，2–4 小时；可选 Q1b 40 步预检）
  ↓  ← 人工停止点①：交付 q1_report.md + q1_findings.json
Q2  路线决策（人工，AI 不得自选）
  ├─ 路线 AR（域回退，零训练）：AR1 规则冻结 → AR2 train-CV 复算 → V0 → C0
  ├─ 路线 SB（场景均衡，一轮 GPU）：SB1 实现 → SB2 测试 → SB3 冒烟 → SB4 五折 → V0 → C0
  ├─ 路线 AR+SB 并行（Q2 可授权的冒险，见 3.7）
  └─ 路线 C（收缩论文，放弃 Koopman 创新，直接冻结为负结果档案）
  ↓  ← 人工停止点②：AR2 或 SB4 裁决后
V0  五 seed 全训练 + 新 validation 一次性评价（需第三次授权）
  ↓
C0  confirm 一次性评价（需第四次授权）
```

阶段状态机只有 `NOT_RUN → RUNNING → PASS / BLOCKED`；PASS 文件一次性写入不可覆盖；任何 B/C 级变更必须新 run。

---

## 3. 强制行为约束

### 3.1 每次动作前的六问（答不全不得执行）

1. 当前任务编号是什么；
2. 当前允许读取哪些 split、允许修改哪些目录；
3. 当前源码/协议/任务书/数据 manifest 的 SHA256；
4. 本命令的预期输入、输出、退出码与硬门；
5. 失败时保存什么、停止在哪里；
6. 本动作是否触碰 1.3 保护清单的任何资产（若是，说明如何不损害）。

### 3.2 永久禁止行为（任何一条违反，本轮证据默认无效）

1. 读取 confirm 或新 validation 的任何数值（manifest/计数除外）；
2. 修改、覆盖或删除 F4 及更早任何冻结产物（rows/models/CSV/JSON/complete/SHA）；
3. 在新 run 中复制旧 run 的任何 `.pt/.pth/.ckpt`；
4. 为通过门禁调整任何预注册数值（3%→5%、损失权重、步数、seed、折划分、工况定义）；
5. 删除 D10/D11 或任何失败窗口/工况后重新统计；
6. 扩维（16→32/64/96/128）、增加专家/门控网络、修改 plant/连接器/执行器/ICR/工况合同；
7. 把"域回退"或"残差模态 Schur 稳定"写成"全域更优"或"系统渐近稳定"；
8. V0 失败后回改方法再看同一 validation；
9. 在 Q1 审计结论落盘前启动任何训练或回退规则设计；
10. 两个进程同时写同一 run/fold/输出目录；核心流程中出现 `except Exception: continue/pass`；
11. 手工修改 CSV/JSON/complete 数值；
12. 为赶时间跳过任何硬门或把人工停止点改成自动继续。

### 3.3 修复权限分级（沿用 koopman_fix.md 2.3）

| 级别 | 例子 | 规则 |
|---|---|---|
| A：机械实现 | import 缺失、路径转义、`.cpu()`、JSON 序列化、绘图字体、维数包装 | 可自动修，一次一个根因；记录 diff+SHA；重跑受影响测试与当前 stage |
| B：实验语义 | 损失、采样、早停指标、模型结构、split、步数、阈值、seed、回退规则定义 | 仅本文明确写出的改动可做；其余必须停止并写 solutions.md |
| C：研究边界 | 改 plant、删工况、读 confirm 调参、加专家/维数、改论文主张 | 不可自动修复；必须人工授权 |

### 3.4 小故障处理

- SSH 瞬断/文件占用：原命令最多重试 2 次、每次间隔 ≤30 s，参数不变；
- OOM：仅允许 `micro_batch 64→32→16` 且 `accumulation 4→8→16`（有效 batch 仍 256），仍失败则停止；
- smoke 非有限梯度：仅允许预注册学习率 `3e-4→1e-4` 重做 smoke 一次；正式折开始后 NaN/Inf 不得现场降学习率；
- 中断续跑：仅当 checkpoint 内任务书/源码/数据/protocol SHA、fold、variant、seed、步数、RNG 全部匹配才允许；
- 绘图失败不重训；只从冻结原始表重绘。

### 3.5 Split 访问矩阵（本轮专用）

| 阶段 | train（96 family） | 旧 development | 旧 validation | 新 validation | confirm |
|---|---|---|---|---|---|
| Q0 | 只读 manifest/计数 | 只读历史摘要 | 只记录已污染 | 只核验封存账本 | 只核验计数=0 |
| Q1/Q1b | **允许**（F4 折上 rows + 40 步预检，写入新审计目录） | 只读历史 S0 汇总表（1.2 节） | 禁止 | 禁止 | 禁止 |
| Q2 | 不产生数据 | — | — | — | — |
| AR1/AR2 | 允许（组合 F4 rows） | 禁止 | 禁止 | 禁止 | 禁止 |
| SB1–SB4 | 允许（新 v3s 目录） | 禁止 | 禁止 | 禁止 | 禁止 |
| V0 | 全训练 | 禁止 | 禁止 | **唯一一次评价** | 禁止 |
| C0 | 不训练 | 禁止 | 禁止 | 不再查看 | **唯一一次评价** |

### 3.6 冒险预算（允许"预计成效可量化、失败可止损"的冒险）

| 编号 | 允许的冒险 | 预计成效 | 代价/止损 | 接受条件 |
|---|---|---|---|---|
| R-a | AR 路线使用场景级回退 R1（预注册、新 validation/confirm 上同样触发） | 零训练直达 V0，fallback macro ≈ +25%（24–26%） | 审稿"挑工况"观感 | Q2 人工确认 + 论文同表报告含/不含回退全部数值 |
| R-b | SB16-eq 单发五折（不做权重网格） | 机制级修复，主张更强 | macro 可能跌破 5% 门，一轮 GPU | 失败即停 → 转 A/C，禁止调权重再试 |
| R-c | SB16-up（D10/D11 3× 上权）与 SB16-eq 双臂同时预注册 | 一次性排除"为过门调权重"质疑 | 2 倍 GPU（1.5–8 h） | 仅 Q1 出现 F-A 型发现且 Q2 明确授权 |
| R-d | Q1b 用 F4 既有 best.pt 做 40 步压力预检（新计算、不训练） | 提前暴露 V0 40 步门风险 | 少量 GPU 时 | 只用 train 折、写新审计目录、访问账本 |
| R-e | Q2 授权"AR 先行 + SB 并行" | AR 证据零训练成本，SB 失败时 AR 已就绪 | 管理与审计复杂度 | 两线产物目录隔离、身份各自封存 |
| R-f | AR 路线暂缓 M 层消融（MONO/FREE）直接 V0 | 省一轮 GPU、抢时间 | 论文少一组机制消融 | 论文把机制消融列为 limitation，或后续单独授权补跑 |

**禁止的冒险（等同红线，任何"预期成效"都不能作为理由）：** 触碰 P1–P7 资产；提前开 validation/confirm；跨 run 复用模型；结果不好时改门禁/权重/seed；删失败工况；扩维加专家；以"稳定"扩写有限时域结论；Q1 未完成就训练。

---

## 4. 阶段定义

每个阶段给出：目标 / 前置 / 步骤 / 产物 / 硬门 / 失败→解决方向 / 停止点。

---

### Q0 — 现场身份与创新资产核验（只读）

**目标**：确认 F4 冻结基线完好、confirm 仍 0 读、新 validation 账本未动、无残留进程。

**步骤**（PowerShell 只读）：
1. SSH 核对 hostname = `DESKTOP-9IUUGEO`、项目根、Python 解释器 `E:\anaconda\envs\pytorch_new\python.exe`、CUDA、GPU、D 盘 ≥60 GiB；
2. 列出 Python/MATLAB 进程；未知进程只记录不终止；
3. 重算 1.1 节全部 SHA（F4 run 关键文件：`f4_verdict.json`、`f4_blocked.json`、各折 `rows.parquet`/`best.pt`/`fold_complete.json`、source/protocol/data manifest）并比对；
4. 核验 confirm 访问计数 = 0、旧 validation 状态、新 validation 账本 SHA 未变；
5. 核验 1.3 保护清单 P1–P7 逐项状态并写 `q0_asset_check.json`；
6. 核验 `run_v3r.py` 存在 V0/C0 阶段入口（供 AR 路线使用）；若缺失，属 A 级修复，登记新 manifest 后再进入后续（只新增 stage 入口，不改训练语义）。

**产物**：`koopman_ab_results/runs/<run_id>/q0/{environment.json, processes.txt, identity.json, asset_check.json, split_status.json, complete.json}`

**硬门**：hostname/根/解释器可确认；无身份不明的训练进程；1.1 节 SHA 全部一致；confirm=0；新 validation 账本未变；保护清单无损害项；磁盘 ≥60 GiB。

**失败→方向**：SHA 不一致 → 停止并写差异清单，人工裁决（禁止覆盖）；磁盘不足 → 清理不涉及冻结产物的缓存后重试一次；进程占用 → 记录并等待（禁止 kill 未知进程）。

**停止点**：Q0 PASS 后自动进入 Q1（同一授权链内）。

---

### Q1 — D10/D11 退化解剖审计（只读）

**目标**：用 F4 冻结逐窗 rows 回答"退化是什么、在哪、由什么驱动"，产出选路证据。

**数据**：F4 各折 `rows.parquet`（MH16/MHC16/BCV16/ONE16 + S0）。禁止读取 validation/development/confirm 的任何数值；1.2 节历史汇总表仅作背景。

**审计指标（M1–M9，全部落盘）**：
- **M1 完整性**：每折每变体 rows 存在且行数>0、字段齐全（run/variant/fold/seed、trajectory/base_family/scenario/direction/plant、window class/start、horizon、j_common、e_core/e_relative/e_force4/e_internal/e_yaw、divergent）。缺失 → 按 E14 类处理（见失败方向）。
- **M2 逐工况复算**：重算 scenario×fold 的 J20（候选 vs S0）→ 精确复现"24–35%"声明并给出逐折精确表。
- **M3 退化窗口集合**：退化窗 = 候选逐窗 J20 > S0 逐窗 J20。输出：各工况退化窗数量/占比、按 window_class 分布、按 window_start 直方图。
- **M4 分量归因**：退化窗与改善窗上 e_core/e_relative/e_force4/e_internal/e_yaw 的 delta 均值——哪个物理组驱动退化。
- **M5 尾部结构**：逐窗改善分布（share<0、P50/P90/P95/P99/max）；tail_share = 最差 5% 窗的退化量 / 总退化量。
- **M6 振荡结构（D10/D11 重点）**：误差随 window_start 的曲线；对 D11 激发周期（加速度周期 4 s=200 步、转向周期 5.56 s≈278 步）做自相关检验；与 S0 同曲线比较平坦度。
- **M7 时域剖面**：D10/D11（对照 D7/D9）在 h=1/5/10/20 的逐时域 delta——退化是否随 horizon 增长。
- **M8 力/内部力剖面**：D10/D11 上 e_force4/e_internal 的 delta 及其与状态误差的方向一致性。
- **M9（=Q1b，可选，需 Q2 前单独授权）40 步预检**：加载 F4 的 MH16/S0 `best.pt`，在 train 折 rows 上做 40 步 rollout（新计算、不训练、写 `q1b/` 新目录、访问账本登记）；报告 40 步发散数（候选 vs S0 逐窗对照）与 latent 范数 P95/P99。

**产物**：`q1/{q1_report.md, q1_findings.json, scenario_table.csv, degrading_windows.csv, component_attribution.csv, tail_stats.json, oscillation_analysis.{csv,png}, horizon_profile.csv, force_profile.csv}`；q1b（若授权）：`q1b/{rollout40.csv, complete.json}`。

**硬门**：M1 通过（rows 完整、SHA 一致）；M2 复算与 F4 verdict 一致（macro 与 24–35% 声明的绝对差 ≤1e-12）；全部发现写 q1_findings.json；未读取任何禁止 split（访问账本为证）。

**失败→方向**：
| 问题 | 方向 |
|---|---|
| M1：rows 缺失/字段不全 | 若远端 run 目录有完整 rows 则只读取回；若确实缺失 → **证据链缺陷（E14 类）**，Q1 BLOCKED，写修复方案（用冻结 best.pt 重评 train 折、新审计目录、新账本），人工授权后再继续；**禁止**从"印象"或旧 CSV 代替 |
| M2：复算与 F4 不一致 | 停止；逐折定位差异（口径/分母/窗口集合）；若是审计脚本 bug → A 级修复重跑；若是 F4 统计口径问题 → 记录为 E 类新缺陷，人工裁决 |
| M6：D11 呈振荡相位结构且退化均匀 | → 见 Q2 决策表 F-B 行（指向 AR） |
| M5：tail_share 高（少数窗驱动） | → 见 Q2 决策表 F-A 行（指向 SB-up 或 AR） |
| 出现 20 步发散>0（与 F4 矛盾） | → 全链停止，证据优先，人工裁决 |

**停止点**：Q1（含 Q1b 若授权）完成后**必须人工停止**，交付报告后等待 Q2 决策。禁止 AI 在 Q2 前自行进入 AR/SB。

---

### Q2 — 路线决策（人工）

**输入**：`q1_report.md`、`q1_findings.json`、本执行书 3.6 冒险预算、4.4/4.9 的决策表。

**决策表（发现 → 推荐路线）**：

| 发现编码 | Q1 判定条件 | 推荐 | 说明 |
|---|---|---|---|
| F-A | 退化集中于少数窗（退化窗占比 <20% 且 tail_share >50%） | B（SB16-eq + SB16-up 双臂）或 AR | 尾部结构 → 上权/分层对路 |
| F-B | D11 呈振荡相位结构、D10 均匀退化 | **AR（R1）** | 等权对 D11 是降权（窗口多），SB 预期低 |
| F-C | 退化主要由 e_force4/e_internal 驱动 | AR 且力主张收紧；SB 门不变 | 力组件敏感 → 回退最稳 |
| F-D | 退化仅出现在 h=20（1/5/10 步无退化） | AR 可行；SB-eq 可试；时域权重重定义**本轮禁止**（另立任务书议题） | 多时域权重是 F4 冻结项 |
| F-E | 所有工况少量退化（弥散、无结构） | SB-eq（机制赌注）或 C | 无结构则回退无目标 |
| F-F | M1/M2 证据问题未决 | **禁止选路**，先修证据链 | 任何路线都依赖 F4 rows |

**人工可选动作**（写入 `q2_decision.json` 并注明理由）：
1. 路线 AR（默认回退规则 R1）；2. 路线 SB（eq only）；3. 路线 SB（eq+up，需 F-A）；4. AR 先行 + SB 并行（冒险 R-e）；5. 路线 C（收缩论文主张）；6. 暂停（证据问题）。

**硬门**：决策由人类明确写出；AI 只提交选项与推荐、不得替人类圈选；决策后本任务书 SHA 与授权范围重新登记。

---

### AR1 — 回退规则冻结（A 路线，无训练）

**目标**：把回退规则冻结为不可变 spec，并实现纯 rows 组合器。

**规则默认 R1**（场景级切换）：预测合成时，`scenario ∈ {D10, D11}` 的窗口取 S0 预测，其余取候选（MH16）预测。R2（因果特征检测）与 R3（双模型不一致）仅在 Q2 人工明确选择时替换，且必须附带冻结阈值。

**步骤**：
1. 写 `fallback_spec.json`：rule 类型、触发集合/阈值、S0 rows 身份引用、候选 rows 身份引用、本 spec 的 SHA；
2. 实现 `koopman_ab_audit/compose_fallback.py`（纯后处理：输入两个冻结 rows 集 + spec，输出组合 rows）；不修改 v3r 源码、不触碰任何模型；
3. 单元测试：确定性（同输入两次运行逐位一致）；无未来信息（组合器只读 scenario 标签与已冻结预测，不读任何目标值以外的未来量）；S0 行身份逐元素匹配；组合数学手算用例；同一 spec 对象可在 AR2/V0/C0 复用（hashable）；
4. 预写论文主张模板（按 koopman_fix.md 3.3 分级语言），Q2 人工审阅。

**产物**：`ar1/{fallback_spec.json, compose_fallback.py, test_fallback.py, claim_template.md, complete.json}`

**硬门**：spec 冻结（SHA 登记）；测试全过；组合器确定性；不产生任何新模型文件；访问账本干净。

**失败→方向**：组合数学与手算不符 → A 级修复重跑；规则本身在 AR2 复算中表现出非预期行为 → 回到 Q2 附新发现，人工裁决（B 级，禁止现场改规则）。

---

### AR2 — train-CV 回退复算与全门验证（A 路线，无训练）

**目标**：证明"MH16 + R1 回退"在 F4 折上满足全部 8 项 F4 合格门，并冻结 V0 的 full-train 步数。

**步骤**：
1. 用 AR1 组合器对 F4 各折生成组合 rows；
2. 重算 F4 八门：① 五折有限、20 步发散 0；② 每折 D5 困难窗相对折 S0 退化 ≤3%；③ macro 改善 ≥4/5 折为正；④ 五折汇总改善 ≥5%；⑤ 任一 D0–D11 工况退化 ≤3%（分母 max(J_s^S0,0.02)）；⑥ 四点力/内部力 20 步 macro 退化 ≤5%；⑦ rows 独立复算误差 ≤1e-12；⑧ 访问账本 validation/development/confirm 读取 0；
3. 记录组合 macro（预期 ≈+25%，区间 +24.1~25.9%）与逐工况表；D10/D11 退化应为 0（构造性）；
4. 从 F4 折级产物读取 MH16 各折真实 best_step，取中位数冻结为 V0 full-train 步数（写入 `ar2_frozen_steps.json`）。

**产物**：`ar2/{composed_rows.parquet, gates.json, scenario_table.csv, frozen_steps.json, complete.json}`

**硬门**：八门全过；full-train 步数已冻结；composed 表可独立复算。

**失败→方向**：若组合 macro 显著低于预期区间 → 检查窗口集合口径（A 级）后复算一次；若仍低 → 停止，写 solutions.md 并回 Q2 重决策（说明：回退路线收益不足，可选 SB 或 C）；若 D10/D11 退化非 0 → 组合器或 S0 rows 引用错误（A 级修复）。

**停止点**：AR2 PASS 后**人工停止**；V0 需第三次授权。

---

### SB1 — 场景均衡候选实现（B 路线，新目录 v3s）

**目标**：在**新目录** `revision_2026\koopman_predict_v3s` 中实现 SB16（场景均衡多时域），不动 v3r。

**唯一方法改动**：`step_loss` 中每个窗口的组误差乘以场景权重

```
w_s = N_train / (12 · n_s^train)          （SB16-eq，等场景贡献，均值权重=1）
w'_s = 3·w_s（s∈{D10,D11}），再归一化均值=1   （SB16-up，仅 Q2 按 F-A 授权时实现）
```

其中 `n_s^train` = 本折 train 中场景 s 的窗口数，`N_train` = 本折 train 窗口总数。权重**只来自 train 标签**（不进入模型输入、不用任何未来量）。结构、暖启动、预算、批流、seed、早停 Q_CV、F4 门禁**全部不变**。

**步骤**：
1. 复制 v3r 全部代码/配置/测试到 v3s（不复制任何 results/models/checkpoint/缓存）；
2. `src/train.py::step_loss`：增加 per-window 场景权重通道（batch metadata 已含 scenario）；保持原有 ONE/MH/MHC/BCV 行为在 `scenario_balance.enabled=false` 时逐位不变（回归测试）；
3. `config/protocol_v3s.json`：新增 `loss.scenario_balance = {enabled, mode:"equal_scenario"|"up_weight_d10d11", up_factor:3.0, freeze:{…}}`；所有数值从 protocol 读取并写入 resolved config（E13 规则）；
4. 权重审计：训练开始时计算并落盘 `weights_per_scenario.json`（含 n_s、w_s、归一化校验）；
5. 扩展 `scripts/run_v3s.py` 阶段入口：SB2/SB3/SB4（复用 v3r 的 fold runner 逻辑）；V0 阶段使用冻结 SB16 目标；
6. 新增测试（见 SB2 清单）；source manifest、protocol SHA、本任务书 SHA 全链登记。

**产物**：`koopman_predict_v3s/`（新源码树）+ `sb1/{weights_audit.json, complete.json}`

**硬门**：v3r 历史目录 SHA 无变化；v3s 无任何旧模型/检查点；协议无代码硬编码；关闭 scenario_balance 时与原损失逐位一致（回归测试通过）；权重均值=1（归一化校验 ≤1e-9）。

**失败→方向**：复制遗漏 → A 级补齐重跑；权重公式实现与原损失不一致 → A 级修复；若发现需要改 Q_CV/采样器/结构才能实现 → B/C 级，停止并回 Q2。

---

### SB2 — 单元测试与故障注入（B 路线）

**必测清单**：
1. v3r 既有 57 项测试在 v3s 全绿（防 P2 资产回归）；
2. 权重数学：每场景损失贡献相等（SB16-eq）/ D10+D11 为 3×（SB16-up）；均值=1；
3. 无未来泄漏：权重仅由 train 标签计算，输入任何未来/validation 场景信息必须报错；
4. 批流同一性：SB16 与 MH16 共享同一预计算批流（identity 测试）；
5. 等预算：各变体第二阶段最大步数一致；
6. resume 等价 ≤1e-7（含权重通道）；
7. 梯度分化：SB16 梯度 ≠ MH16 梯度（防 E10 型断线回归）；
8. 关闭 scenario_balance 时与 v3r 损失逐位一致；
9. 人工构造 NaN/发散/权重漂移时选择门必须拒绝；
10. 删除任一产物文件时 artifact 门失败。

**硬门**：全部通过，禁止 `xfail/skip` 隐藏本轮新增测试。

**失败→方向**：单根因 A 级修复 ≤2 轮；同一阻塞第 3 次出现 → BLOCKED，写 solutions.md 等人工；梯度不分化 → 按 E10 流程查 `.item()`/detach 类断线。

---

### SB3 — 小规模冒烟与权重审计（B 路线）

**数据**：仅 train 中 D0/D5 各一个 base family；seed 990100；warm 200 + phase 500；有效 batch 256。

**必须记录**：各变体实际优化步数与 batch ID SHA；加权前后各场景损失贡献占比；`weights_per_scenario.json` 与协议一致性；A0/B0/b0 训练前后 SHA；F 半径、`rho(F)<0.995`、完整 K 谱半径；best/last 差异与恢复；checkpoint 续跑等价 ≤1e-7。

**硬门**：无 NaN/Inf；四变体同 warm SHA；A0/B0/b0 逐字节不变；`rho(F)<0.995`；resume 等价；未读取禁止 split。

**失败→方向**：非有限梯度 → 预注册学习率 3e-4→1e-4 重做一次；仍失败 → BLOCKED（禁止改权重/结构救回）。

---

### SB4 — 五折公平复验与决策（B 路线）

**矩阵**：SB16-eq 五折；SB16-up 五折（仅 Q2 授权时）。共享 warm 2000 + 阶段 ≤15000、seed 990100+fold、折划分 990700、Q_CV 早停（patience 2000）、float32 训练 / float64 评价。

**候选合格门（与 F4 八门逐字一致，不得改动）**：见 AR2 步骤 2。

**决策规则（预注册，禁止现场改）**：
| SB4 结果 | 动作 | 禁止 |
|---|---|---|
| SB16-eq 过全门 | 冻结 SB16-eq 为 M1 候选；best_step 中位数冻结为 V0 步数；停止等待授权 | 不因此再跑 up |
| SB16-eq 失败、SB16-up 过门 | 冻结 SB16-up；**在报告中注明该臂在 Q2 已预注册** | 事后补注册、改 3× 为其他值 |
| 双臂均失败且失败门为 scenario（D10/D11 或新工况） | 停止；回 Q2 决策（AR 或 C） | 继续调权重/上权其他工况 |
| 任一臂出现 D5 困难窗退化 >3% | **立即停止**；多时域 D5 收益是保护资产 P1，禁止用任何权重换掉它 | 换 warm/seed/预算救回 |
| macro <5% 或正折 <4/5 | 停止；SB 路线收益不足 | 改 Q_CV 或早停救回 |
| 出现 20 步发散 >0 | 停止；机制假设失败 | 降学习率/缩时域重跑 |

**产物**：`sb4/{sb4_verdict.json, scenario_table.csv, rows.parquet（各折）, frozen_steps.json, blocked.json（若失败）}`

**停止点**：SB4 结束后无论 PASS/BLOCKED 均**人工停止**。

---

### V0 — 五 seed 全训练 + 新 validation 一次性评价（两路线共用，第三次授权）

**前置**：AR2 或 SB4 PASS；方法已冻结（AR 路线 = MH16 + 冻结回退 spec；SB 路线 = 冻结 SB16 变体）；full-train 步数已冻结；新 validation 账本读取计数仍 0。

**步骤**：
1. 用 96 个 train family、seed 990101–990105 训练 5 个 full-train 模型（AR 路线在 v3r、SB 路线在 v3s）；不在 validation 早停、不因 validation 保存新检查点；
2. 按封存账本（seed 991000）一次性生成新 validation（48 family / 168 条）并**原子性**评价 S0 与冻结方法；AR 路线对预测施加冻结回退规则（与 AR2 同一 spec）；
3. 报告并执行十门：① macro ≥5%；② 2000 次 base-family 配对 bootstrap（seed 990500）95%CI 下界 >0；③ ≥4/5 seed 同向；④ h=1/5/10 不退化 >3%；⑤ D5 整体及困难窗 mean/P95/P99/max 不退化 >3%；⑥ 任一 D0–D11 不退化 >3%；⑦ 四点力/内部力 20 步不退化 >5%；⑧ 1/5/10/20 步发散 0 且 40 步无新增发散；⑨ A0/B0/b0 SHA 不变；⑩ 单窗 20 步 GPU 中位数 <1 ms、P99 <2 ms、CPU 中位数 <5 ms（硬件调度不稳时重复同一计时协议，不改模型）。

**产物**：`v0/{validation_manifest.json, five_seed_rows.parquet, gates.json, bootstrap.csv, complete.json|blocked.json}`

**失败→方向**：
| 问题 | 方向 |
|---|---|
| macro <5% 或 CI 跨 0 | 停止，负结果归档；方向 = 路线 C 或另立新盲验证协议（旧 validation 永久降级，禁止再查） |
| 仅 40 步门失败 | 检查发散窗是否集中于 D10/D11（AR 路线该处为 S0 预测，理论上无新增）或 MH16 侧；把有限时域结论收缩到 20 步并记录；**禁止改模型** |
| D5/工况/力门失败 | 停止；train-CV 结果未迁移到新数据，写 solutions.md；可选方向 = 进一步收缩域（需新预注册）或 C |
| 新 validation 生成失败（分布不符/内存） | 停止；按 koopman_fix.md 6.3 写解决方案，不得用旧 validation 顶替 |

**停止点**：V0 结束**人工停止**；C0 需第四次授权。

---

### C0 — confirm 一次性评价（第四次授权）

**前置**：V0 通过；方法与代码冻结；confirm 计数仍 0。

**动作**：只运行冻结方法与 S0 各一次（96 confirm family），不训练、不调参、不补 seed；报告宏观方向、D5 门、力/内部力、发散。

**失败→方向**：confirm 失败 → 按 koopman_fix.md 3.3 降级论文结论（"在预留确认集上未能复现"），禁止换 confirm、删 family、回 V0 调参。

---

## 5. 关口 → 问题 → 方向总表（速查）

| 关口 | 可能遇到的问题 | 允许的解决方向 | 禁止的动作 |
|---|---|---|---|
| Q0 | SHA 不一致 / confirm 计数非 0 / 保护资产受损 | 差异清单落盘 → 人工裁决；恢复只读副本 | 覆盖冻结文件、假装未发现 |
| Q1 M1 | rows 缺失/字段不全 | 从远端 run 目录只读取回；确缺则按 E14 修复流程重评 train 折（新目录+新账本） | 用旧 CSV/印象替代；读 validation |
| Q1 M6 | D11 振荡相位结构 | 结论 F-B → Q2 推荐 AR | 当场设计新损失 |
| Q1 M5 | 尾部集中 | 结论 F-A → Q2 推荐 SB(up) 或 AR | 直接改 CVaR |
| Q1 M2 | 复算与 F4 不符 | 定位口径差异；脚本 A 级修复重跑 | 修改 F4 verdict 使其"一致" |
| Q2 | 无清晰发现（F-E 弥散） | 选 SB-eq（机制赌注）或 C；人工拍板 | AI 自行选路 |
| AR1 | 组合器数学与手算不符 | A 级修复 ≤2 轮 | 现场改规则定义 |
| AR2 | 组合 macro 明显低于 +24% | 查窗口口径后复算一次；仍低 → 回 Q2 重决策 | 把 D10/D11 从统计中删掉 |
| SB1 | 实现与原损失不一致 | A 级修复（关闭开关时逐位一致测试兜底） | 改 Q_CV/采样器/结构 |
| SB2 | 梯度不分化（E10 回归） | 按 E10 流程查断线，加回归测试 | 跳过测试 |
| SB3 | 非有限梯度 | 预注册 lr 3e-4→1e-4 一次 | 改权重/结构救 smoke |
| SB4 | eq 失败且 up 未预注册 | 停止 → 回 Q2（AR 或 C） | 事后补注册 up |
| SB4 | D5 收益被换掉 | 停止；P1 资产优先 | 换 warm/seed 救回 |
| V0 | macro<5% / CI 跨 0 | 负结果归档 → C 或新盲协议 | 回改方法再看 validation |
| V0 | 40 步新增发散 | 结论收缩到 20 步并记录 | 改模型救门 |
| C0 | confirm 未复现 | 按 3.3 降级结论 | 换 confirm/删 family |

---

## 6. 代码修改与测试清单（全部只发生在新目录）

| 位置 | 内容 | 输入 | 输出 | 测试 |
|---|---|---|---|---|
| `koopman_ab_audit/q1_audit.py`（新） | M1–M8 审计指标 | F4 rows | q1 产物 | 手算样例、行数公式、无禁止 split 访问 |
| `koopman_ab_audit/q1b_rollout.py`（新，条件） | 40 步预检 | 冻结 best.pt + train 折 rows | q1b 产物 | 仅 train、账本登记 |
| `koopman_ab_audit/compose_fallback.py`（新） | 回退组合器 | 两个冻结 rows 集 + fallback_spec | 组合 rows | 确定性/无未来信息/手算/S0 身份 |
| `koopman_ab_audit/recompute_gates.py`（新） | F4 八门与 V0 十门重算 | rows | gates.json | 与 AR2/SB4/V0 一致 |
| `koopman_predict_v3s/src/train.py` | per-window 场景权重通道 | batch+metadata+protocol | 加权损失+审计字段 | 权重数学/无泄漏/关闭开关逐位一致/梯度分化 |
| `koopman_predict_v3s/config/protocol_v3s.json` | `loss.scenario_balance` 块 | — | resolved config | 无硬编码（E13） |
| `koopman_predict_v3s/scripts/run_v3s.py` | SB2/SB3/SB4/V0 阶段入口 | CLI | stage 产物 | 无上游 PASS 不得越级 |
| `koopman_predict_v3s/tests/*` | 5.2 节新增测试 | — | pytest | 全绿且禁止 xfail/skip |

---

## 7. 产物与审计清单

每阶段必须产出：`complete.json` 或 `blocked.json`（二者只存其一）、`identity.json`（源码/协议/任务书/数据/环境 SHA）、`split_access.jsonl`（每次 split 访问的时间/阶段/用途/行数）、`artifact_manifest.json`（文件大小+SHA）、原始 rows/CSV（摘要不得替代原始表）、工作记录追加。任何报告引用的路径缺失则 stage 不得标 PASS（E18 规则）。

必须图件：① D10/D11 逐窗误差曲线（候选 vs S0）；② 12 工况改善热图（正负同一色标）；③ D11 振荡分析图（若 M6 触发）；④ h=1/5/10/20 时域剖面；⑤ 尾部结构直方图；⑥（SB 路线）加权前后各场景损失贡献占比；⑦（AR 路线）回退组合前后逐工况对照。图必须写单位、样本范围、seed、split、数据 SHA，且数值可从原始表再生。

---

## 8. 运行命令模板（仅授权后执行）

```powershell
# 0) 冻结本任务书到 5080 并核对 SHA
$LocalTaskbook = 'D:\PDxc\Review\koopman_ab.md'
$TaskbookHash = (Get-FileHash -LiteralPath $LocalTaskbook -Algorithm SHA256).Hash
scp -- $LocalTaskbook '5080:D:/LEARNING/ZNN/ZNN/Adaptive-koopman/Adaptive-koopman-main/revision_2026/koopman_ab.md'
# 远端重算 SHA，不一致不得进入 Q0

$ProjectRoot = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
$PyExe = 'E:\anaconda\envs\pytorch_new\python.exe'
$AuditRoot = Join-Path $ProjectRoot 'revision_2026\koopman_ab_audit'
$RunId = '<Q0_RETURNED_RUN_ID>'

# Q1 审计（只读）
& $PyExe (Join-Path $AuditRoot 'q1_audit.py') --run-dir (Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3r_results\runs\20260903_041205_KFIX_R01') --out (Join-Path $AuditRoot 'results\runs' $RunId 'q1')

# AR2 复算（A 路线）
& $PyExe (Join-Path $AuditRoot 'compose_fallback.py') --spec (Join-Path $AuditRoot 'results\ar1\fallback_spec.json') --out (Join-Path $AuditRoot 'results\runs' $RunId 'ar2')
& $PyExe (Join-Path $AuditRoot 'recompute_gates.py') --rows (Join-Path $AuditRoot 'results\runs' $RunId 'ar2\composed_rows.parquet') --gates f4 --out (Join-Path $AuditRoot 'results\runs' $RunId 'ar2\gates.json')

# SB2–SB4（B 路线，v3s）
& $PyExe -m pytest (Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3s\tests') -q
& $PyExe (Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3s\scripts\run_v3s.py') --stage SB3 --project-root $ProjectRoot --protocol (Join-Path $ProjectRoot 'revision_2026\koopman_predict_v3s\config\protocol_v3s.json') --taskbook (Join-Path $ProjectRoot 'revision_2026\koopman_ab.md') --resume-run $RunId
# SB4 / V0 / C0 同上改 --stage
```

---

## 9. 资源与时间预估

| 阶段 | 时间 | GPU |
|---|---|---|
| Q0 | ~30 min | 无 |
| Q1（含 M1–M8） | 2–4 h | 无 |
| Q1b（若授权） | ~1 h | 轻 |
| Q2 | 人工，不定 | — |
| AR1+AR2 | 半天 | 无 |
| SB1+SB2 | 2–3 h | 无 |
| SB3 | ~30 min | 轻 |
| SB4（1–2 臂） | 1.5–8 h | 满载 |
| V0 | 2–5 h + validation 生成 | 满载 |
| C0 | ~1 h | 轻 |

时间只是资源计划，不是通过条件；单臂外推超 12 h 先交付成本评估人工决定，不得擅自减 seed/折数。

---

## 10. 工作记录格式

沿用 koopman_fix.md 第 13 节：每阶段一条记录，包含请求/任务编号、授权模式、机器与项目根、读取（含 SHA）、修改（含 diff 与 SHA）、命令与退出码、原始产物路径、关键结果、结论类型（事实/推断/建议）、状态、停止原因、下一允许动作。日志必须引用 `split_access.jsonl`，不允许凭印象写"未读取"。

**本轮完成定义（Definition of Done）**：出现以下任一即本轮结束——① 某路线的 V0+C0 证据落盘（通过或失败）；② 任一阶段 BLOCKED 且 solutions.md 已写、保护清单 P1–P7 无损、confirm 仍 0 读；③ Q2 人工选择路线 C，全部负结果归档并冻结。**三者的共同底线：不破坏任何既有创新资产，不制造新的证据污染。**

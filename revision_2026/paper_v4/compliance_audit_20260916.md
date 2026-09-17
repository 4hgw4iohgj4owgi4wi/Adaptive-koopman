# 产物存放合规性审计（2026-09-16）

审计问题：本次会话产生的结果数据是否按要求放在对应文件夹。审计方式为逐目录清点，不凭记忆。

## 1. 结论速览

| 维度 | 结论 |
|---|---|
| 每类实验独立run_id | ✅ 全部满足，命名`YYYYMMDD_<阶段><单元>_<序号>` |
| 每类实验结束出图 | ✅ 所有正式结果目录都有PNG/SVG |
| `science_status`与`figure_status`分列 | ✅ 所有`figure_manifest.json`都分列；本次补正了两处漏改 |
| run目录证据完整性 | ✅ 12个已完成run均为`raw.npz`+`substeps.npz`+`solver.jsonl`+`status.json`+`metrics.json`(4/4+metrics) |
| analysis目录完整性 | ✅ 正式目录均有JSON+PNG/SVG+`README.md`+`figure_manifest.json` |
| **结果根目录位置** | ❌ **与任务书字面不符**（见第2节） |
| **统一工作记录路径** | ❌ **任务书指定路径在本机不存在**（见第3节） |
| **结果汇总导出** | ❌ **本次会话结果未进入导出文档**（见第4节） |
| **规范登记文件** | ⚠️ 陈旧，未回填本轮方法身份（见第5节） |

## 2. 结果根目录：与任务书字面不符（既存问题，非本轮引入）

任务书第1.1节规定`新结果目录OUT = REV\paper_v4_results`，每批独立run_id。实际分布：

| 根目录 | 条目 | 内容 | 最新 |
|---|---:|---|---|
| `revision_2026\paper_v4_results` | 32个run + 3份汇总文档 | 仅E00/E01早期批次(2026-09-09)与`20260909_R1_01..03` | run目录停在`20260909_R1_03`(09-09 21:55) |
| `revision_2026\paper_v4\results` | 99个条目 | 全部R系列(R0/R1_TEST/R2A/R2B/R2C/R3/R4)以及本轮G3/GPU/R4全部run | `20260915_R4_P2_2MS_GPU01`(09-16 08:23) |

时间线显示分叉自**2026-09-09 21:42**起：E系列写入`paper_v4_results`，R系列从`R0_MOCK01`(21:42)起写入`paper_v4\results`；`R1`两侧都有（`paper_v4_results\20260909_R1_01..03`与`paper_v4\results\20260909_R1_TEST01`）。

**判断**：本轮全部run遵循的是既有R系列约定，未偏离既有实践；但该约定本身与任务书字面不一致，且已持续一周。**需要用户裁决**：统一迁到`paper_v4_results`，还是修订任务书承认`paper_v4\results`。不建议我单方面移动99个目录（会破坏所有已冻结协议里的相对路径与身份哈希）。

## 3. 统一工作记录路径不存在

任务书第1.1节指定统一工作记录为`D:\PDxc\Review\koopman_work_log.md`（追加，不覆盖）。审计结果：**`D:\PDxc`整个目录在本机不存在**，因此该文件不存在。本轮一直追加的是本地`paper_v4\koopman_work_log.md`（186,219字节，最新2026-09-16 08:25），与既有会话做法一致（该文件已积累上千行历史）。

同样不存在的还有任务书引用的`D:\PDxc\Review\describe_review.md`、`control_math.md`、`D:\PDxc\评论家.docx`。

## 4. 结果汇总导出未更新（本轮真实缺口）

`paper_v4_results`下的`实验结果汇总_20260915.md/.docx/.pdf`最后修改时间为**2026-09-15 12:22**，早于本轮全部工作（本轮21:37开始）。因此本轮产出——G0—G2资格、G3三窗口与机理、P1三个步长全路线、两组收敛比较——**都不在导出文档里**。

`paper_v4\tools\export_results_docx.py`（约100 KB）是既有导出管线，本轮未运行。是否现在补导出，需要用户确认（导出会覆盖同名文档，属于"覆盖正式交付物"，不宜自行决定）。

## 5. 规范登记文件陈旧（本轮未回填）

| 文件 | 最后修改 | 本轮新增但未登记的内容 |
|---|---|---|
| `gates/E00.json` | 2026-09-11 15:13 | — |
| `audit/data_roles.json` | 2026-09-11 15:13 | — |
| `protocol/methods.json` | 2026-09-11 10:50 | GPU后端实现、`EXP-R3-unfrozen-v1`的GPU单元 |
| `review/review_matrix.json` | 2026-09-11 10:50 | — |

`methods.json`按任务书应登记"内部键、英文全名、架构、预测器、checkpoint/norm/S0、状态/输入schema、是否在线更新、观测器、时延对齐、误差界、优化器…"等字段。本轮引入了**新的数值实现**（CPU parallel8 → 单CUDA worker），按第7.1节"未激活模块不得写入全名"的精神，GPU单元应作为同一方法的实现变体登记，而不是新方法；但该登记尚未回填。

## 6. 本次审计中已修正的三处

| 位置 | 问题 | 处理 |
|---|---|---|
| `analysis/20260915_D1B_BETA_MEMORY_REPLAY_01` | 已写`failure.json`但`figure_status`仍为`PENDING_VISUAL_QA` | 改为`FAIL_VISUAL_QA_SUPERSEDED` |
| `analysis/20260915_G3_RESTART_EQUIVALENCE_01` | 同上 | 改为`FAIL_VISUAL_QA_SUPERSEDED` |
| `analysis/20260915_rtx5080_v4_omp_probe` | 未登记诊断输出，无说明文件 | 补`README.md`，声明未登记并指向承接它的登记分析`analysis/20260915_G3B_DIVERGENCE_MECHANISM_01` |

另有三个目录只有`failure.json`、无README：`analysis/20260915_R4_P1_2MS_1MS_CONVERGENCE_01`、`analysis/20260915_R4_P1_2MS_GPU_COMPARE_01`、`analysis/20260915_G3_VERDICT_QA_01`。三者均为"空目录+失败记录"或"被取代版本"，保留即可，不补README以免与`failure.json`重复。

## 7. 逐run完整性明细（本轮）

| run目录 | 核心四件 | metrics | 图 | manifest | 说明 |
|---|:--:|:--:|:--:|:--:|---|
| `20260915_RTX5080_G0_G2_04` | 0/4 | ✗ | 2 | ✗ | v4失败：仅G0 JSON与图（资格脚本自身布局） |
| `20260915_RTX5080_G0_G2_05` | 0/4 | ✗ | 6 | ✅ | 资格脚本布局：G0/G1/G2三组JSON+三组图+manifest |
| `20260915_G3_FORCE_GPU01` | 1/4 | ✗ | 0 | ✗ | model身份失败，`failure.json`保留 |
| `20260915_G3_*_GPU02/CPU02` | 4/4 | ✅ | — | — | v3排列缺陷版，保留 |
| `20260915_G3_*_GPU03/CPU03`（6条） | 4/4 | ✅ | — | — | 正式G3窗口 |
| `20260915_R4_P1_2MS_GPU01` | 4/4 | ✅ | — | — | 图在比较目录 |
| `20260915_R4_P1_1MS_GPU01` | 4/4 | ✅ | — | — | 同上 |
| `20260915_R4_P1_0P5MS_GPU01` | 4/4 | ✅ | — | — | 同上 |
| `20260915_R4_P2_2MS_GPU01` | 4/4 | 运行中 | — | — | 08:23启动，未完成 |

注：全路线run目录本身不含图，图在对应的`analysis\..._COMPARE_*`/`..._CONVERGENCE_*`目录，并在那里带`figure_manifest.json`。这符合"每类实验结束出图"（比较是一类实验），但与"每个run目录自带图"的严格读法不同，一并列出供判断。

## 8. 需要用户裁决的四项

1. **结果根目录**：统一到`paper_v4_results`，还是修订任务书承认现状？（我倾向后者：迁移动摇全部冻结协议的身份哈希与相对路径，风险高于收益。）
2. **统一工作记录**：`D:\PDxc`不存在，是否改为以`paper_v4\koopman_work_log.md`为准并修订任务书？
3. **结果汇总导出**：是否现在运行`export_results_docx.py`补出本轮汇总（会覆盖同名文档）？
4. **`methods.json`回填**：是否把GPU单元作为`EXP-R3-unfrozen-v1`的实现变体登记进去？

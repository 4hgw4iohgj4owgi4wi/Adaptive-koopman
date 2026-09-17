# 2026-09-15 更新任务书执行记录

## 当前裁决

`C0_PASS / R4_P1_2MS_RUNNING / R4_P1_1MS_AND_LATER_BLOCKED`

本记录对应`experiment.md`第27—28节和`protocol/后续实验详细任务书_20260915.md`。运行中状态不等于科学PASS；必须等待单条完成、独立审计、PNG/SVG生成及视觉QA全部通过后，才允许冻结下一单元。

## C0接口资格

- 正式协议：`protocol/post_r3_C0_20260915.json`
- 协议SHA-256：`3b12c8cbd532ca6b6909624cfa9a30b0a51d5461d7ef01361f1ba2eaf24664ef`
- 正式结果：`results/20260915_POST_R3_C0_03/c0_report.json`
- 结果状态：`PASS_C0_R4_READY`
- 负例：10/10在结果目录创建前拒绝
- 固定QP：P1/P2的初始静力组与有力组共4组，串行/8进程的QP矩阵、边界、首控制和非线性复核全部PASS
- 有力效果：车辆1世界x方向偏移0.03m时，P1/P2最大点力分别为800.85N、878.85N
- 图表：PNG/SVG覆盖图及manifest/README齐全，打开检查后`figure_status=PASS`

## 问题、解决方法与效果

1. **父证据链未完整锁定**：C0_01通过后发现长runner仅验证C0协议，没有显式验证C0报告与图表manifest。加入父报告状态/SHA、图表状态/SHA门并全量重跑。效果是长任务不能绕过C0科学裁决或图表交付门；C0_01保留为被替代工程证据。
2. **同值参数的容器类型误判**：C0_02之后的R4正式预检把Python元组和JSON数组视为不同，报`ABSOLUTE_PARAMETER_IDENTITY_MISMATCH`。仅将锚点的身份表示统一为JSON数组，没有改变任何参数值、模型或阈值。错误协议在创建输出前退出，C0_03重跑后通过。
3. **旧R4入口不满足新任务书**：旧入口可能回退冻结雅可比，且报告scope/lambda与新门不一致。新增隔离runner/audit/plot/preflight，固定未冻结逐步雅可比、FD=1、parallel8、lambda=2、绝对截止与检查点，并保存端点/子步未平滑连接力分量。效果是C0可独立验证，长任务身份和后续绘图所需数据闭合，同时不改旧冻结证据。

## R4-P1-2ms启动

- 协议：`protocol/R4_P1_2MS_20260915.json`
- 协议SHA-256：`e41b6633785b5bdbd6e294301b5c1938301e49fabff5634c6ea3549243741dd5`
- 结果目录：`results/20260915_R4_P1_2MS01`
- P1：载荷质量1800kg、惯量4350kg·m²、车辆μ=0.95、连接器刚度28500N/m、阻尼3325N·s/m、空程0.0019m
- 负例：错误SHA、错误输出路径均在建输出前拒绝
- 启动：2026-09-15 10:00:08，PID 27780
- 绝对截止：2026-09-15 21:53:02（Asia/Shanghai）
- 当前：进程存活、stderr为空、已保存的solver条目及对应非线性复核为PASS

下一步只在本单元完整结束后执行独立审计、生成六面板PNG/SVG并视觉检查；任一门失败即按任务书停止，不启动P1-1ms。

## 18:41状态变化与用户停止

PID 27780已退出，stderr为空；最后证据闭合检查点为2200/2379周期、44.0s、88.0m。solver共有2210条连续PASS记录，其中末10条没有对应持久化raw/substeps，因此不计入完成周期。结果目录没有`metrics.json`，本批登记为`EXTERNAL_PROCESS_TERMINATION_INCOMPLETE`，不能据此判算法或物理成功/失败。

2210条solver墙钟统计为：平均13.911148s、中位13.739660s、P95 14.870203s、最大22.855401s。当前控制实现每个20ms周期都重新求解20步MPC，并以未冻结动力学雅可比执行有限差分线性化；8进程后端为CPU并行，不使用RTX 5080。按平均值推算2379周期约需9.19h，故运行慢，且原5s/周期预算仍失败。

用户明确指示“别重新跑”。因此不执行检查点拼接或新run_id全量重试，也不启动P1-1ms及后续依赖实验。当前裁决更新为：

`C0_PASS / R4_P1_2MS_EXTERNAL_INTERRUPTION_INCOMPLETE / USER_STOP_NO_RERUN / C1_AND_DESCENDANTS_BLOCKED`

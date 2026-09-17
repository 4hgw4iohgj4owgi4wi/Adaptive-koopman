# AKE-A 严格 baseline 对齐与剩余实验记录（2026-05-12）

## 1. 本轮目标

本轮处理的缺口是：现有稿件中的 `baseline` 主要是 task-aligned AKE-M mechanism comparator，并不是上传论文 `Adaptive Koopman Embedding for Robust Control of Complex Nonlinear Dynamical Systems` 的原文级 AKE-A。因此，若要在投稿中写“相对 Adaptive Koopman baseline 更优”，必须补充严格对齐的 AKE-A 或补强物理/DMPC baseline。

本轮优先选择“复现 AKE-A 的任务对齐版本”，原因是当前代码已经保留 Koopman 在线修正接口，改动最小、风险最低；物理/DMPC baseline 仍需单独接入 raw physical dynamics，不应把已有 ZOH surrogate 写成强物理 DMPC。

## 2. 已完成代码改动

### 2.1 `tf14_runtime.py`

新增 `adapt_cfg_overrides` 可选入口。默认运行完全不变；只有方法配置显式传入该字段时，才复制 `ctx["ADAPT_CFG"]` 并覆盖局部自适应设置。

用途：AKE-A 对齐实验需要关闭本文额外的谱投影在线保护，避免把本文稳定投影机制混入 baseline。

### 2.2 `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py`

新增两个严格 baseline 候选：

| method key | 显示名 | 对齐含义 | 主要配置 |
|---|---|---|---|
| `ake_a_linear_net` | AKE-A linear-net | 对齐原文线性 Koopman + 在线自适应网络修正 | `koopman_structure=linear`, `online_adaptation_mode=linear_net`, 关闭通信、FDI/FTC、phase-role、PPC/progress 等本文模块 |
| `ake_a_bilinear_ridge` | AKE-A bilinear-ridge | 对齐原文双线性 Koopman + 在线矩阵修正的任务版本 | `koopman_structure=bilinear`, `online_adaptation_mode=bilinear_ridge`, 关闭本文新增模块 |

注意：`ake_a_bilinear_ridge` 不是原文神经网络式 bilinear adaptation 的完全复刻，而是当前工程可直接执行的双线性残差矩阵更新版本。论文中必须写成“task-aligned AKE-A reproduction / implementation-level comparator”，不能写成作者原始代码复现实验。

## 3. 已跑实验与结果

输出目录：

`D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\ake_a_alignment_smoke_2026-05-12`

关键文件：

| 文件 | 作用 |
|---|---|
| `data/tf14_remaining_runs.csv` | run-level 结果，含 seed、method、full_path、RMSE、连接、证书等字段 |
| `data/tf14_remaining_summary.csv` | 当前已完成 run 的聚合统计 |
| `data/tf14_remaining_manifest.json` | runner 记录与输出索引 |
| `figures/R0_main_comparison_summary.*` | 主指标柱状图 |
| `figures/R0_error_timeseries.*` | 误差时间序列 |
| `figures/R0_reliability_runtime.*` | 可靠性与运行时间图 |

当前已完成 run 数：

| method | 已完成 run 数 |
|---|---:|
| `ake_a_linear_net` | 4 |
| `ake_a_bilinear_ridge` | 4 |
| `baseline` | 4 |
| `tf14_main` | 4 |
| `tf14_phase_role` | 3 |

当前聚合结果仅覆盖 `sine_mixed_fault_noise`，不是最终投稿统计：

| method | n | full path mean | RMSE_y mean | RMSE_s mean | connection max util. | force peak | cert ok ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| AKE-A bilinear-ridge | 4 | 0.000 | 0.1067 | 14.0474 | 0.3219 | 1611.0 | 0.1774 |
| AKE-A linear-net | 4 | 0.000 | 0.1066 | 14.0707 | 0.3099 | 1507.1 | 0.1774 |
| AKE-M baseline | 4 | 0.500 | 0.0804 | 7.2628 | 0.3010 | 1667.7 | 0.2687 |
| NR-KDCC main | 4 | 0.250 | 0.0982 | 10.8408 | 0.3040 | 1696.2 | 0.3313 |
| NR-KDCC full / phase-role | 3 | 0.333 | 0.0737 | 9.6189 | 0.3767 | 1222.5 | 0.3796 |

## 4. 审稿边界结论

1. 这组 `sine_mixed_fault_noise` 压力设置可以证明 AKE-A 对齐 baseline 在多车载荷 + 通信/故障耦合任务上明显不够，但不能证明本文方法在所有 seeds 上已经全面优于 baseline。
2. 当前 n=4/n=3 小统计显示：NR-KDCC full 的横向 RMSE 与力峰值较有优势，但 full path 完成率仍不足，因此正文不能写“强扰动下稳定完成任务”。
3. 稳定性证书比例相对 AKE-A 提升明显，但仍低于可支撑强稳定 claim 的水平；理论部分应继续写 practical ISS / UUB，而不是全局渐近稳定。
4. 若要把这组场景作为主文实验，必须继续调参或降低压力等级；否则它更适合作为“极端压力边界实验/失败模式分析”放补充材料。

## 5. 后续补实验建议

### P0：严格 baseline 主对比

目标：形成至少 n=20 paired 统计。

推荐命令按 seed shard 运行，避免单次超时：

```powershell
& 'E:\anaconda\envs\pytorch_new\python.exe' 'tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py' `
  --experiments E0 `
  --seeds 2030 2031 2032 2033 2034 `
  --scenarios sine_mixed_fault_noise `
  --methods baseline ake_a_linear_net ake_a_bilinear_ridge tf14_main tf14_phase_role `
  --output-root 'paper_dcn_tf12_draft\publication_readiness_round10_2026-05-11\ake_a_alignment_smoke_2026-05-12' `
  --continue-on-error --reuse-env
```

后续继续跑 `2035..2039`、`2040..2045`。每轮结束后用同一 runner 选择已完成 method 聚合即可。

### P0：压力等级修正

当前 mixed fault/noise 对 proposed 也过强，建议新增一个 `publication_mixed_fault_noise` 场景：

| 参数 | 当前高压 | 建议投稿主场景 |
|---|---:|---:|
| `comm_packet_loss_base` | 0.09 | 0.04-0.06 |
| `comm_packet_loss_gain` | 0.26 | 0.12-0.18 |
| `comm_delay_steps_max` | 4 | 2-3 |
| `fault_ax_scale` | 0.58/0.60 | 0.70-0.78 |
| `fault_delta_scale` | 0.58/0.60 | 0.70-0.80 |

原则：主文场景要能区分方法而不是让所有方法大面积失败；极端场景保留到补充材料。

### P1：物理/DMPC baseline

不能继续把 `zoh_consensus_surrogate` 写成物理 DMPC。若要补强物理 baseline，需要新增：

| baseline | 动力学 | 控制 | 是否可直接投稿 |
|---|---|---|---|
| `phys_dmpc_nominal` | Frenet bicycle + rigid payload equivalent model | distributed MPC，无学习 | 可作为非学习强 baseline |
| `phys_dmpc_delay_comp` | 同上 | 加通信时延预测补偿 | 可对照本文 delay compensation |
| `tube_dmpc_comm_delay` | 同上 | tube tightening / robust invariant set | 可对照本文 safety tightening |

这需要单独接入 raw physical dynamics；不是简单改 `koopman_structure=linear`，因为后者仍然走 Koopman lifted state。

## 6. 论文写法修正

正文中 baseline 相关措辞应改成：

1. “本文与任务对齐的 AKE-A 复现实验、AKE-M 机制对照和非 Koopman surrogate 进行比较”，不能只写“与 AKE baseline 比较”。
2. “AKE-A 在原文中解决单体非线性系统的在线 Koopman 自适应问题；本文进一步处理多车刚性载荷、通信时延/丢包、故障诊断与重构控制的耦合问题。”
3. “当前极端 mixed fault/noise 结果显示本文模块提高证书通过率和部分误差/力指标，但不能支撑所有 seeds 全路径完成的强 claim。”


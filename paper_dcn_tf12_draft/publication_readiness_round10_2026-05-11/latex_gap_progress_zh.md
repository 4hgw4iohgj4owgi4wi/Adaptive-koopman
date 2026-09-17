# Round10 LaTeX 与剩余缺口推进记录

- 日期：2026-05-11
- 本轮目标：在继续推进剩余实验缺口的同时，基于当前 TF14/Round10 中文版本生成 DCN/Elsevier LaTeX 中文初稿。

## 1. 已完成：中文 LaTeX 包

- 输出目录：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11`
- 主文件：`manuscript_zh_round10.tex`
- PDF：`manuscript_zh_round10.pdf`
- 生成脚本：`paper_dcn_tf12_draft/publication_readiness_round10_2026-05-11/build_dcn_latex_zh_round10.py`
- 页面 QA：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages`
- 资产缺失检查：`missing_assets_zh.txt` 为空。

### 当前稿件内容

- 按 DCN 模板建立中文 front matter、摘要、关键词、正文、图表、参考文献。
- 引言按模块组织：Koopman 车辆控制、协同运输、通信退化 DMPC/MPC、鲁棒/容错 MPC。
- 方法从大地坐标系车辆模型、路径误差、刚性载荷连接误差、通信图开始写。
- 写入双线性 Koopman、岭回归、稳定投影、通信质量感知一致性 MPC、FDI/FTC、phase-role 调度和 Lyapunov/UUB 证明。
- 写入当前 Round10 可用实验：E0 mixed、E0 comm-key、E2 mixed、E2 comm-key、E3、E7。
- 明确 claim 边界：AKE-M 不是严格 AKE-A 复现；力峰值不作为改善 claim；no-delay-compensation 当前证据弱；E1 fresh training 和强 baseline 仍未闭合。

### 编译验证

- `latexmk` 不可用，原因是本机 MiKTeX 缺 Perl script engine。
- 已改用直接链路完成编译：
  - `xelatex -interaction=nonstopmode -halt-on-error manuscript_zh_round10.tex`
  - `bibtex manuscript_zh_round10`
  - `xelatex -interaction=nonstopmode -halt-on-error manuscript_zh_round10.tex`
  - `xelatex -interaction=nonstopmode -halt-on-error manuscript_zh_round10.tex`
- 编译结果：成功生成 6 页 PDF。
- 未发现 fatal error、undefined citation、undefined reference。
- 剩余排版警告：
  - DCN 模板首页 logo 区存在 overfull box。
  - SimSun 粗体/斜体替代。
  - 第 5 页为浮动图表页。
  - `xeCJK` 提示未定义 CJK mono family。

## 2. 已完成：参考文献临时清理

- 在 LaTeX 包内对 Round10 bib 做了临时清理，删除 `Author names to be finalized...` 这类 note，补入部分作者元数据。
- 本轮补入作者元数据主要来自已有 Round10 文献映射和公开 DOI/出版社页面检索。
- 仍需正式提交前用 Crossref/IEEE/ScienceDirect/Springer 元数据重新导出 BibTeX，尤其是作者、卷期页码、DOI。

公开页面核验入口：

- `https://doi.org/10.1016/j.robot.2023.104612`
- `https://doi.org/10.1016/j.conengprac.2024.106002`
- `https://doi.org/10.1016/j.mechatronics.2024.103206`
- `https://doi.org/10.1007/s44285-024-00026-z`

## 3. 已启动：E0 nominal/single-fault n=20 主对比

- 目的：补齐 E0 all-scenarios 主对比中 nominal clean 和 single fault 两个缺口。
- 方法：`baseline`、`tf14_main`、`tf14_phase_role`、`zoh_consensus_surrogate`。
- 场景：`sine_nominal_clean`、`sine_single_fault_v2`。
- seeds：2026--2045，分 4 个 shard。
- 进程记录：`e0_nominal_fault_shards_processes.json`
- 当前状态：后台仍在运行；18:53 合并快照显示已完成 `52` 条 run，`minimum_group_n=12`，`final_statistics_ready=false`。
- 18:58 已启动 watcher：`monitor_e0_nominal_fault_completion.py`
- watcher 进程记录：`e0_nominal_fault_monitor_process.json`
- watcher 行为：每 180 秒合并一次 partial 数据；若达到 `160` 条 run 且 `minimum_group_n>=20`，自动运行出图脚本和 gate 脚本；最长运行 8 小时后超时退出。
- watcher 首次快照：`60` 条 run，`minimum_group_n=12`，仍为 partial。

## 4. 已完成：E0 nominal/single-fault 合并与出图脚本

- 合并脚本：`merge_e0_nominal_fault_shards.py`
- 出图脚本：`plot_e0_nominal_single_main.py`
- 当前 partial 合并输出：`e0_n20_nominal_single_fault_main_comparison_merged`
- 注意：该 merged 目录当前只是 partial 快照，不能写入主文。待四个 shard 都完成后重新运行合并、出图、gate。

## 5. 仍未闭合的缺口

1. E0 nominal/single-fault 后台任务未完成，暂不能写入 LaTeX 主文。
2. Delay/dropout dose-response 与 topology recovery 仍未启动，时延补偿独立 claim 仍需降级。
3. E1 Koopman fresh training 多训练 seed 仍未完成，Koopman 预测精度统计不能写强结论。
4. 严格 AKE-A 复现或强物理/DMPC baseline 仍缺，不能写全面优于上传 baseline 原文。
5. C4 FDI/FTC 仍需补近三年直接文献和故障效率估计/控制重分配曲线。

## 6. 2026-05-11 19:40 增量修改：命名、框架图、流程图与新版图表

- 方法名已从本地版本号改为 `NR-KDCC`，中文全称为“网络韧性 Koopman-时延一致性协同运输控制”。正文可见位置已核查，无 `TF14/tf14` 残留；`tf14` 仅保留在本地代码和数据文件夹名中。
- 在方法部分新增“方法总览与命名”，明确逻辑链条：物理建模 -> 离线数据生成 -> 双线性 Koopman 学习 -> 时延补偿一致性 MPC -> FDI/FTC 与证书保护。
- 新增 TikZ 可编辑框架图和在线控制流程图，配色使用蓝/青/橙/玫红/灰蓝，避免把黑色作为主视觉线条。
- 新增论文用支持图生成脚本：`make_nrkdcc_support_figures.py`。
- 新增并插入新版实验图：
  - `fig_nrkdcc_team_center_trajectory.png`：团队中心轨迹对比。
  - `fig_nrkdcc_team_center_errors.png`：团队中心横向/纵向误差。
  - `fig_nrkdcc_vehicle_lateral_errors.png`：四车横向误差。
  - `fig_nrkdcc_mixed_ablation_summary.png`：mixed fault/noise 消融摘要。
  - `fig_nrkdcc_comm_ablation_summary.png`：high-communication-noise 消融摘要。
  - `fig_nrkdcc_certificate_summary.png`：Lyapunov/ISS 证书摘要。
  - `fig_nrkdcc_connection_force_audit.png`：连接安全与受力代价摘要。
- 已移除正文中旧 E0/R2/R3/R7 图的引用，避免旧图内残留本地版本号和黑色主线；旧图片文件仍在 figures 目录中作为历史资产，不在正文使用。
- 所有 `\caption{...}` 已核查，均包含“含义”说明，保证每个图和表都说明其读图/读表目的。
- 已重新编译：`xelatex -> bibtex -> xelatex -> xelatex`，输出 PDF 为 8 页。
- QA 页面已导出到：`paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages_nrkdcc`。
- 当前排版剩余问题：浮动体仍导致第 5--7 页存在浮动页/空白偏多，属于版面压缩问题；后续可通过合并图、缩小图高或改为补充材料解决。

## 7. 2026-05-11 增量修改：框架图与控制流程图细化

- 已将 NR-KDCC 总体框架图从简化模块图扩展为三层结构：离线建模与学习层、在线预测与优化层、安全保护与证据审计层。
- 框架图中补入了关键输入输出与变量含义，包括参考路径与曲率、车辆质量/惯量/轮胎参数、载荷连接几何、Frenet 误差、连接误差、通信质量、丢包/时延、lifted state、双线性 Koopman 预测式、MPC 输入与安全约束。
- 已将在线控制流程图扩展为 9 个执行步骤：状态采集、网络质量更新、邻居状态补偿、Koopman 预测、MPC 构造、优化求解、安全后处理、证书/约束判定、执行与记录。
- 控制流程图新增低链路质量/高残差/证书裕度不足时的保护分支，明确其触发后进入降权、收缩、degraded fallback，再回到优化求解；同时保留下一采样周期闭环。
- 两张图继续采用蓝、青、橙、玫红、灰蓝为主线条颜色，避免以黑色作为主视觉连接线；黑色仅保留为正文和公式文字颜色。
- 校验编译已通过：`xelatex -jobname=manuscript_zh_round10_check -> bibtex -> xelatex -> xelatex`，输出 `manuscript_zh_round10_check.pdf` 共 8 页。
- 已导出 QA 页面到 `paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages_nrkdcc_detail`，第 3 页检查显示两张图完整显示、未被截断。
- 因 `manuscript_zh_round10.pdf` 被其他进程占用，本轮无法覆盖主 PDF；已另存可查看版本为 `manuscript_zh_round10_detailed_diagrams.pdf`。

## 8. 2026-05-11 增量修改：图例位置统一

- 已修改 `make_nrkdcc_support_figures.py`，将所有正文中带图例的 NR-KDCC 论文图统一改为图外顶部居中横排图例，避免图例压住曲线或柱状图。
- 受影响图片包括：团队中心轨迹、团队中心横向/纵向误差、各车横向误差、E7 连接安全与载荷受力审计图。
- 消融柱状图和证书统计图本身没有独立图例，未强行添加图例，避免增加无效视觉负担。
- 已重新生成 `nrkdcc_support_figures/figures` 下的 png/pdf/svg，并同步覆盖 LaTeX 正文使用的 `dcn_latex_zh_round10_2026-05-11/figures/fig_nrkdcc*.png`。
- 已重新编译校验：`xelatex -jobname=manuscript_zh_round10_legendcheck -> bibtex -> xelatex -> xelatex`，输出 7 页 PDF。
- QA 页面已导出到 `paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages_legendcheck`，第 5--7 页检查显示图例与线条不再重叠。
- 主 PDF `manuscript_zh_round10.pdf` 仍被其他进程占用，未能覆盖；本轮可查看版本为 `manuscript_zh_round10_legendfixed.pdf`。

## 9. 2026-05-12 增量修改：第 5/6 章实验分析与浮动体排版修正

- 已确认问题不只是排版：第 5 章实验部分原先有图表，但图表后的机理解释和 claim 边界不够集中；第 6 章讨论已有边界说明，但需要与第 5 章图表分析衔接。
- 已将实验章标题改为“实验结果与分析”，并补强主对比、模块消融、稳定证书与连接安全三类结果的文字分析。
- 表 1 新增“表内解读”，明确 NR-KDCC 的优势不是成功率，而是连接最大利用率和横向 RMSE；同时保留力峰值升高这一负面边界。
- 新增组合诊断图 `fig_nrkdcc_error_diagnostics.png`，把团队中心横向误差、纵向误差和 mixed fault/noise 下四车横向误差放在同一页，用于回答“团队中心改善是否贯穿时间过程、是否由单车过度补偿造成”。
- 已修正组合图图例：方法图例置于顶部，车辆 V0--V3 图例置于底部，不再和线条、子图标题打架。
- 已把浮动页的 `\@fpsep` 和 `\@dblfpsep` 从可伸缩间距改为固定 `10pt`，使第 5 页表格和团队中心轨迹图紧凑堆叠，空白主要留在页底，不再夹在图表中间。
- 已核查生成后的正文无可见 `TF14/tf14` 残留，论文方法名继续统一为 `NR-KDCC`。
- 已重新生成图片和 LaTeX，并完成 `xelatex -> bibtex -> xelatex -> xelatex` 编译，输出 `manuscript_zh_round10_layoutfix2.pdf` 共 9 页。
- QA 页面已导出到 `paper_dcn_tf12_draft/dcn_latex_zh_round10_2026-05-11/qa_pages_layoutfix2`；第 5 页图表间距已压缩，第 6 页图例与曲线/标题无重叠，第 7--8 页实验分析和讨论边界可读。
- 当前仍保留的技术风险：日志中仍有模板/字体引起的 overfull warning，首页 TikZ/模板区域有 overfull vbox；这些不影响 PDF 生成，但投稿前还应做一次最终版式压缩和模板参数清理。

## 10. 2026-05-12 增量修改：Koopman、时延、FDI/FTC 与 Lyapunov 证据链闭合

- 已新增证据链记录文件：`gap_closure_record_zh_2026-05-12.md`。
- 已在 `make_nrkdcc_support_figures.py` 中新增四张图：Koopman 预测/稳定投影审计、通信时延机制与 w/o delay 边界、FDI/FTC 时间线、分模式证书闭合图。
- 已在中文 LaTeX 正文新增“Koopman、时延与 FDI/FTC 机制证据”小节，并逐图说明可支撑结论与不可过度书写边界。
- 已把 Lyapunov 证明从过强的全局稳定表述收缩为分模式 ISS/UUB：加入模式证书裕度公式、有限密度负裕度条件、fallback 可行边界和证书失败解释。
- 已修正证书负裕度叙事：旧版全场景聚合表仍保留用于限制 claim；新增分模式压力场景图显示 high-communication-noise 与 mixed fault/noise 下 nominal/FTC 模式均为正裕度。
- 已补充 FDI/FTC 细节：EWMA+CUSUM 公式、残差阈值、CUSUM 阈值、连续触发/释放步数、双通道效率阈值。
- 已重新生成 LaTeX 包并编译 `manuscript_zh_round10_gapclosure.pdf`，输出 11 页；`missing_assets_zh.txt` 为空，日志无未定义引用/文献，正文可见 `TF14/tf14` 残留为 0。
- 当前风险：E1 仍是缓存审计不是 fresh training 多 seed；时延补偿独立性能优势仍需 dose-response；FDI/FTC 时间线仍需多 seed 检测延迟/误报率统计；模板 overfull warning 仍待最终版式整理。

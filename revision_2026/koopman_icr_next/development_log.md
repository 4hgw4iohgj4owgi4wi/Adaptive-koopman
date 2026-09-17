# Koopman ICR Next 源码修改留痕

> 本文件记录正式 N0 之前、由“按照 `icr_next.md` 修改”所授权的源码准备。正式实验日志将在用户另行明确授权 N0–N2 后，由 runner 新建于 `koopman_icr_next_results/work_log.md`。本记录不代表 N0、N1 或 N2 已运行。

## 20260831 — 建立隔离候选版本

- 授权范围：新建 `koopman_icr_next` 候选源码、协议、测试和正式阶段 runner；不运行正式 N0–N2。
- 父源码 manifest：`B816BD45E795525680637EB612B48409C3689296F72054EE4130C2DFF26BEC2C`。
- 任务书 SHA256：`3DCC36838813DD47D9BDA79485606925E2403C1AC7819B5F075DA295E3957C19`。
- 修改：新增双状态物理门审计、反事实越域首事件、A3→A0 pilot 调度、严格 JSON、安全前序门、N2 图表、切换后 1 s 拉伸绝对冲量、独立复算脚本及语义故障注入测试。
- 未修改：连接器、轮胎、四车动力学、A0–A3 执行器数值方程、D2 工况、seed 和任何门限。
- 事实：本地解释器可完成 Python 语法与轻量合同检查；本地环境未安装 pytest，完整测试必须在 5080 的冻结 Python 环境执行。
- 状态：`PARTIAL / FORMAL_N0_N1_N2_NOT_RUN`。
- 下一允许动作：部署到新的远端隔离目录并执行非正式开发测试；正式阶段仍须用户明确说“执行 N0–N2”或同等含义。

## 20260831 — 5080 非正式开发测试

- 命令：`E:\anaconda\envs\pytorch_new\python.exe -B ...\scripts\dev_verify_icr_next.py`。
- 结果：`45 passed in 1.60s`，退出码 0。
- 事实：只运行单元/合同测试；未运行 N0/N1/N2 runner，未生成正式仿真数据。
- 状态：`PASS_DEVELOPMENT_TESTS / FORMAL_N0_N1_N2_NOT_RUN`。
- 下一允许动作：短时 A3 父身份检查；之后停止并等待正式执行授权。

## 20260831 — A3 短身份检查首次失败与最小修复

- 首次命令：`...\scripts\dev_identity_icr_next.py`。
- 退出码：1；仿真尚未启动。
- 首个失败：`ModuleNotFoundError: No module named 'icr_metrics'`，发生在 `_short_parent_identity()` 冷启动导入 `audit_icr_fix` 时。
- 事实：候选 `src/icr_metrics.py` 存在；入口此前只把 `scripts` 放入 `sys.path`。
- 修复：`scripts/run_icr_next.py::_short_parent_identity()` 在导入前按顺序加入隔离候选 `src` 和 `scripts`。
- 未修改：物理方程、参数、门限、D2 和 seed。
- 重新进入门：完整 pytest 和相同 A3 短身份检查都必须通过。
- 状态：`REPAIR_APPLIED / RETEST_REQUIRED / FORMAL_N0_N1_N2_NOT_RUN`。

## 20260831 — 修复后复验

- 完整 pytest：`45 passed in 1.53s`，退出码 0。
- A3 短身份：父版本和候选版本共同字段 63 个；候选独有字段 0；父独有字段 0；最大逐点绝对差 `0.0`；首个差异 `null`；退出码 0。
- 事实：候选审计/调度修改没有改变这条短 A3 物理轨迹的任何共同字段。
- 正式结果目录：未创建。
- 状态：`PASS_DEVELOPMENT_VERIFICATION / FORMAL_N0_N1_N2_NOT_RUN`。
- 下一允许动作：停止，等待用户明确授权执行 N0–N2。

## 20260831 — N2 必交图静态补全

- 原核对结果：已有 A0–A3 ICR/轮胎/拉伸图，但请求—实际轮角、四车/货物/系统横摆、四点 Fx/Fy 和四点竖直支承的 A0–A3 时序不完整。
- 修改：`scripts/plot_icr_next.py` 增加上述四类 A0–A3 对照图，并在 `figure_manifest.json` 登记候选和父绘图脚本 SHA。
- 边界：只改变未来 N2 的证据绘图；不改原始数组、仿真、审计门、工况或指标。
- 状态：`RETEST_REQUIRED / FORMAL_N0_N1_N2_NOT_RUN`。

## 20260831 — 绘图补全后复验

- Python 语法检查：通过。
- 5080 完整 pytest：`45 passed in 1.53s`，退出码 0。
- A3 短身份复验：共同字段 63，双方独有字段 0，最大逐点绝对差 `0.0`，退出码 0。
- 结果目录：未创建。
- 最终状态：`PASS_DEVELOPMENT_VERIFICATION / FORMAL_N0_N1_N2_NOT_RUN`。

## 20260831 — R0 启动与现场冻结

- 授权范围：按新执行书 `icr_run.md` 执行 `R0→N0→N1→N2→人工停止`；当前只进入 R0。
- 新执行书 SHA：`2DE0F022D281401D5BCD674F1551F090782CF096D27D295944EE0C8CC47BBA95`。
- R0 前候选 manifest：`84A168908E55B9E78F864212E2647C8718683111A724E45288E0F99F29C4D3A6`；R0 前协议 SHA：`CBC86A3A8FF35DDA8B493AD0CFC908A3EEEC460DA80E9DB69893F1FC75A909EF`。
- 现场：主机 `DESKTOP-9IUUGEO`；Python `3.11.14`；GPU `NVIDIA GeForce RTX 5080`；D/E 可用约 `262.594/131.125 GiB`；未知 Python/MATLAB 进程 0；正式结果目录不存在。
- 状态：`R0_IN_PROGRESS / N0–N2 NOT_RUN`。

## 20260831 — R0-A/R0-B 候选修改

- 修改 `scripts/recompute_icr_next.py`：删除对主审计和旧请求归因的导入；直接实现 ICR、G0/G1/G2、轮角/轮胎/支承/连接力、阵列拉伸、内力零空间、A3 父公共字段、身份/哈希/shape/单位检查和主—独立逐指标比较。
- 修改 `scripts/audit_icr_next.py`：主审计增加实际角度峰值和四点支承总和残差，供独立结果交叉比较。
- 修改 `scripts/run_icr_next.py`：N2 只在独立脚本自身、聚合和逐指标比较全部 PASS 时继续。
- 修改测试：覆盖 A0/A1 五类反事实越域、A2 四个硬门和角度报告、A3 六个硬门、十类完整性故障、16 身份缺失/重复/意外/混合状态、轮胎/轮角/哈希篡改、错误单位和必交图清单。
- 修改 `scripts/plot_icr_next.py`：把五类必交图 stem 注册为硬合同。
- 版本同步：旧 `protocol.md` 原样保存为 `protocol_v1.md`；新 `protocol.md` 写入 `icr_run.md`；协议升级为 v2 并冻结独立比较容差。
- 数据限制：现有 raw 只保存货物侧连接力；独立作用—反作用只能按已注册“车辆侧等于货物侧精确负值”合同重构，再与主 summary 比较，不能从两个独立 raw 通道交叉验证。若论文需要双通道原始证据，必须作为后续数据接口变更另立协议。
- 本地命令：Python `py_compile` + ICR 手算/篡改 smoke；退出码 0。
- 当前 v2 协议 SHA：`79D9A6E6A8558C7B35ED924B4AE09D456F1854D51D3B215CE7DF64FE1F6D6D40`。
- 状态：`R0_RETEST_REQUIRED / N0–N2 NOT_RUN`。

## 20260831 — R0 全量测试首次调用失败

- 命令：远端冻结 Python 直接运行 `-B -m pytest <candidate> -q -p no:cacheprovider`。
- 结果：`80 passed, 1 failed in 0.62s`，退出码 1。
- 首个失败：`tests/test_k2_data_contracts.py::test_parallel_pair_executor_smoke` 在仿真前读取 `KOOPMAN_PROJECT_ROOT` 时触发 `KeyError`。
- 分类：L1 调用环境；不是物理、数值或独立复算公式失败。
- 根因：直接 pytest 命令未设置旧测试显式要求的项目根环境变量。
- 替代解释：若设置变量后仍失败，才考虑并行 worker/导入问题。
- 修复：不改源码；用同一冻结 Python、相同测试集和 `KOOPMAN_PROJECT_ROOT=<项目根>` 重跑。
- 状态：`R0_RETEST_REQUIRED / N0–N2 NOT_RUN`。

## 20260831 — R0 修正后验收

- 正确命令：设置 `KOOPMAN_PROJECT_ROOT` 后，用冻结 Python 运行完整候选测试且禁用 cacheprovider。
- 完整测试：`81 passed in 1.92s`，退出码 0。
- 覆盖：独立 ICR 手算/镜像、主—独立轮胎与轮角篡改、raw 哈希篡改、单位/shape/身份聚合、A0–A3 双状态门和必交图清单。
- A3 短身份：共同字段 63；候选独有 0；父独有 0；最大逐点绝对差 `0.0`；退出码 0。
- 父 F3 24 条只读独立请求归因：72 行；G0 峰值最大 `5.551115123125783e-17 m/s`；G2 对父请求最大差 `0.0 rad`；24 条 raw 哈希不一致数 0；父 manifest `C1D430E4718832A27253C2D7C8290678A186EAD570C3948E6D5AC2463C25533B`；退出码 0。
- v2 协议 SHA：`79D9A6E6A8558C7B35ED924B4AE09D456F1854D51D3B215CE7DF64FE1F6D6D40`。
- 最终 R0 source manifest 保存于同目录 `r0_identity.txt`；该 `.txt` 不属于 source manifest 身份集合，写入它不会造成自引用漂移。
- 正式结果目录：仍不存在；未运行 N0/N1/N2。
- 状态：`R0_PASS / N0–N2 NOT_RUN`。
- 下一允许动作：以 `r0_identity.txt` 的冻结 source manifest 从 N0 开始正式执行。

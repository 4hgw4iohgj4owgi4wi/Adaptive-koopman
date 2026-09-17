# Koopman Predict Next 开发记录

## 2026-08-31 — N3 授权与父链预检

- 授权模式：执行实验；本轮只允许建立隔离分支并完成 N3 代码、合同、测试和 126 身份 dry-run，N4 及以后保持 `NOT_RUN`。
- 任务书：`koopman_step.md`，SHA256 `E18CED5E8D3184B6B1FDABC0E489A5FA5B03FC161FA6CCAFE2D1062788889DC2`。
- 主机/项目根：`DESKTOP-9IUUGEO` / `D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main`。
- 父源码实时身份：79 个 manifest 项，SHA256 `F85147D518132C8133876CDCEC9D28DD1989C7A949B7635375700322CDFB4D39`。
- 父 N2：`PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD`；complete/report/data manifest/audit SHA 与任务书一致；人工停止标志为 true。
- 现场：新源码和新结果目录均不存在；Python `3.11.14`；RTX 5080 可见；无 Python/MATLAB 进程；D/E 可用约 `262.555/131.125 GiB`。
- 小问题留痕：第一次只读 Python `-c` manifest 探针的 Windows 双引号被剥离，产生语法错误且退出；未写文件。改用 Python 单引号字面量后得到上述实时身份。
- 参数族解释：任务书只给出“三个参数族”而未给三组人工参数。N3 冻结预留 seed `985000–985002`，沿用父 K2 参数范围和现有 `resolved_params()`；N3 只展开身份，不生成数据或改变物理参数。
- 状态：预检 PASS；开始隔离分支开发。

## 2026-08-31 — N3 接口、合同与测试实现

- 修改 `src/causal_schema.py`：增加 S0/S1/S2 独占状态字段账本，逐字段登记 shape、单位、端点、role、来源与物理分量；合同审计阻断重复物理分量和未来实测量泄漏。
- 修改 `src/data_adapter.py`：增加 `build_sample_variant()` 与各变体输入摘要；S1/S2 当前实际轮角取自 `t_k`，S2 的 `t_{k+1}` 轮角侧车只由当前实际轮角和已知请求经 A3 计算，未来实测轮角仍只在 label。
- 修改 `src/actuator_rollout.py`：增加冻结整数子步的一步与任意时域 A3 递推，输出端点、区间均值、速率、rate mask 和 angle mask。
- 修改 `src/scenarios.py`：保留 D0/D1/D2/D5/D6/D10，增加 D3/D4/D7/D8/D9/D11；冻结边界、左右镜像、D7/D9 零和偏置以及 126 条身份展开。
- 修改 `src/dataset.py`：增加 base-family 不跨 split、train-only 归一化、confirm 不可见和不越轨迹的 20 步窗口合同。
- 修改 `src/contracts.py`：冻结 A3、S0/S1/S2、D0–D11、126/36 计数和 future split seed ledger。
- 新增 `scripts/freeze_predict.py` 与 `scripts/run_koopman_predict.py`：仅授权 N3 dry-run；正式生成 source/protocol/taskbook/environment 清单，硬门失败立即停止，N4–N6 保持 `NOT_RUN`。
- 新增四个任务书指定测试文件：`test_causal_schema.py`、`test_actuator_rollout.py`、`test_scenarios_d0_d11.py`、`test_split_contract.py`。
- 任务书职责→实际函数映射：解析执行器→`rollout_actuator_step/horizon`；接口样本→`build_sample_variant`；身份矩阵→`build_predict_pilot_identities`；划分合同→`validate_base_family_split_contract`。
- 本地静态验证：新增/修改 Python 文件均通过 `py_compile`；S0/S1/S2 输入维数分别为 54/58/70，重复物理量 0、未来实测输入 0；dry-run 展开 126 条、126 个唯一身份、36 个 base family、12 个工况；可见 future base family 192 个，confirm 可见数 0。
- 本地环境限制：系统 Python 3.13 未安装 pytest，`python -m pytest -q` 返回 `No module named pytest`；这不是方法或代码失败，不安装新依赖，完整 pytest 转到任务书指定的 5080 `pytorch_new` 环境执行。
- 状态：本地开发检查通过；尚未写入远程新分支，尚未创建远程新结果，N4 未运行。

## 2026-08-31 — 5080 开发验证

- 新隔离源码已复制到 `revision_2026/koopman_predict_next`；父 `koopman_icr_next` 与父 N2 结果未修改，新结果目录仍未创建。
- 远端完整 pytest：`94 passed in 1.93s`，返回码 0。
- 远端父 A3 公共物理身份：63 个公共字段，candidate-only 0、reference-only 0、最大绝对差 0，PASS。
- 小问题留痕：一次临时只读 Python `-c` A3 探针再次受到 Windows 远程引号剥离影响，语法错误且无持久写入；不把该调用故障解释成模型失败。正式 runner 不使用该脆弱调用路径。
- 缓存管理：远端开发 pytest 产生的 `__pycache__/.pytest_cache` 将在正式冻结前从精确的新隔离目录移除；正式 pytest 禁用 cache provider，并以 `PYTHONDONTWRITEBYTECODE=1` 运行。
- 状态：开发测试 PASS；下一步先同步最终源码与日志、清除新分支缓存，再启动唯一 N3 dry-run。

## 2026-08-31 — 正式冻结前清理

- 已在解析并校验绝对路径位于新隔离源码根后，删除远端 `.pytest_cache` 及 4 个 `__pycache__` 目录；均为可重新生成的缓存，父分支与结果目录未触碰，复查剩余缓存目录数为 0。
- 最终 runner 已设置 `PYTHONDONTWRITEBYTECODE=1` 并禁用 pytest cache provider，缓存和临时结果不进入 source manifest。
- 状态：满足正式 N3 启动条件。

## 2026-09-01 — A0–N6 自主隔离版开发

- 新授权任务书：`koopman_auto.md`，SHA256 `4446B7B4F6DC5FEE648C4F4A0E75971050450AF81B5EA7AE4E788C2E5BFF0182`；自主边界严格止于 N6，C/K/confirm/MPC/network/DoS 均保持禁止。
- 父 N3 身份沿用冻结值：源码 manifest `723D97319F74E0003C8C3151D82F6AA64D01AB7D64AA1DA39DFDFDDA7D36B945`，complete `4B0D2976FFF3C8F0B690D4B4EA240E8B8983B4EEA28B6D57A2DCB671E4763B56`。
- 新增机器可读协议 `config/protocol_predict_auto.json`，冻结 A0/N4-S/N4/N5/N6 转移、6 条 smoke、126 条 N4、672 条 N5 展开、S0/S1/S2、M0/M1、rank/ridge、1/5/10/20 步、四类窗口和硬停止边界。
- 独立判断一：闭式岭回归没有随机“初始化”可言；5+2 个 seed 被如实定义为 train base-family bootstrap 稳定性模型，不能把确定性闭式解伪装成随机初始化复现。
- 独立判断二：N3 接口没有学习 force/internal 输出。N6 对三接口的 `E_force4/E_internal` 统一由预测相对连接位移/速度、冻结参数和连接器定律解析重构；该设计保持方法中立，不静默新增监督输出。
- 任务书用“可接受”描述双线性条件数、发散率和推理成本但没有数值。运行前冻结工程解释：条件数 `<=1e14`、推理时间比 `<=5`、发散率增量 `<=0.01`；这些只约束模块采用，不改变准确率阈值。
- 修改 `src/contracts.py`、`src/scenarios.py`、`src/dataset.py`、`src/evaluation.py`、`src/physics_audit.py`、`scripts/generate_data.py`、`scripts/freeze_predict.py` 和 `scripts/run_koopman_predict.py`；新增 `scripts/auto_data.py`、`scripts/audit_predict_auto.py`、`scripts/auto_pipeline.py`。
- runner 实现唯一 run ID、逐阶段锁、原子 complete、逐轨迹 checkpoint、原始文件恢复、1/2/4 worker 数值身份、阶段硬门和同一 run 断点恢复；硬门失败不创建下一阶段目录。
- 新增 `test_auto_stage_gates.py`、`test_metric_fairness.py`、`test_resume_idempotency.py`，覆盖物理/因果/数据身份故障注入、指标维数公平性、原子写和重复提交。
- N4 原始字段补充四车 `Fx/Fy/Fz`、轮胎/连接合力、四车/货物/系统横摆、作用反作用及内力零空间残差；主审计与独立脚本使用不同聚合路径复算。
- N5 明确区分 192 个可见 base family 与其 672 条方向/植物/成员展开轨迹；confirm 生成/读取数必须为 0，归一化只允许 train。
- 本地静态验证：全部新增/修改 Python 文件通过 `py_compile`。本机 Python 3.13 没有 pytest（`No module named pytest`），不擅自安装依赖；完整测试在 5080 的冻结环境执行。
- 开发期协议当前 SHA256：`5E28720EF95C89C39EB2928B4F18BD2C60E7817778165A33997B00C09203E413`；正式 A0 将记录部署后最终协议和 source manifest SHA。
- 状态：代码完成静态检查，尚未生成 N4/N5 数据或 N6 模型；下一动作是清洁部署到 5080 后执行 A0 硬门。

## 2026-09-01 — A0 最小修复 1/3

- 失败 run：`20260901_004200_AUTO_PREDICT_AUTO_R01_R01`；A0 在 63 字段短探针聚合时抛出 `TypeError: numpy boolean subtract`，后续 `n4_smoke` 目录不存在。
- 事实：错误发生在比较器对两个布尔数组执行减法；尚未得出父物理身份或 A3 物理失败结论。
- 单根因修复：新增 `max_abs_field_difference()`；类别/布尔字段使用 `array_equal`，数值字段保留最大绝对差，形状不同返回无穷大。
- 回归测试：`test_a0_field_comparator_handles_boolean_without_subtraction` 同时覆盖布尔相等和不等。
- 身份处理：保留失败 run 和其 complete/traceback；修改源码后不恢复拼接旧 A0，必须生成新 source manifest 和新 run ID。
- 未修改：协议、任务书、seed、场景、物理参数、硬门阈值和任何原始轨迹。

## 2026-09-01 — N4 审计最小修复 2/3

- 失败 run：`20260901_004439_AUTO_PREDICT_AUTO_R02_R01`；126/126 原始轨迹及126次重放完成，但 N4 正确停止为 `BLOCKED_HUMAN_REQUIRED`，N5 未创建。
- 主审计失败精确集合：仅 D8 的 12 条 `direction` 门；D8 全局虚拟前轮角冻结为0，方向实际由四车 `[+,-,+,-]` 交替轮角偏置编码，通用方向检查读取了错误字段。
- 独立审计：其自身 raw SHA、array SHA、有限值、时间、重放、作用反作用、内力零空间、支承、轮胎和执行器门全部通过；12条失败仅继承旧主审计 false。
- D8 对称性复算：通用几何镜像误差约1.9998；按固定连接点的内部侧向极性反转 `F_right≈-F_left` 时相对误差0.00603，小于冻结0.05。D8不是全局路径左右镜像，不能套用车辆端点几何换位。
- 窗口根因：分类器优先标记 `connector_event`/`switch`，旧覆盖表却只接受 `maneuver`，形成自相矛盾；任务书原文要求稳态、操纵、切换“或”连接事件，动态工况改为接受三类中任一，D0仍强制steady。

## 2026-09-01 N5 repair 1/3: separate smooth maneuvers from discrete switches

- 事实：run `20260901_071606_AUTO_PREDICT_AUTO_R03_R01` 完成全部 672 条 N5 轨迹；11/12 个硬门禁通过，唯一失败项为 `four_window_classes`。旧互斥计数为 steady=1312、connector_event=4764、switch=9768、maneuver=0。
- 根因：`classify_window` 使用 `control_change_atol=1e-12` 作为 switch 的语义阈值。连续斜坡、正弦转向等平滑操纵相邻采样自然不同，因优先级高于 maneuver 而把全部主动操纵吞并为 switch。
- 离线证据：在同一 672 条冻结 raw 上，把 switch 定义为“单步变化超过已冻结活动阈值”，得到 steady=1868、maneuver=8484、switch=728、connector_event=4764；四类均有非边缘覆盖。
- 最小修复：connector_event 优先级不变；switch 使用现有 `acceleration_active_mps2` / `steering_active_rad`，`control_change_atol` 仅作数值下限；新增“平滑主动操纵=maneuver、阶跃=switch”回归测试。
- 复用边界：新增 `--reuse-n5-run`，只接受 672 条 identity 全字段一致且 raw/meta 成对存在的来源；新 run 重新审计、重建窗口 ledger 和 method-neutral cache，不重跑或修改物理 raw，并写 `raw_reuse_provenance.json`。
- 单根因修复范围：只修改 D8 方向字段路由、D8 极性对称复算和与分类优先级一致的覆盖聚合；新增两项回归测试。未修改仿真器、物理参数、D0–D11、seed、阈值或任何raw。
- 恢复策略：保留旧失败 complete；新 source SHA、新 run ID 执行 A0，然后从旧126条raw逐条重算主/独立审计。每条raw/file/array/replay SHA仍验证，不复制或拼接异源轨迹。

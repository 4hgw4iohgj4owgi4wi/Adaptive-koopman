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

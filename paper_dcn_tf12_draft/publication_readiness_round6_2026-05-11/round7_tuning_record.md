# Round7 续调记录

- 时间：2026-05-11
- 目标：继续增强正式 n=20 长批次的稳定运行能力，并保证失败样本也能留下审稿可追溯记录。

## 本轮新增调整

- 给 `tf14_remaining_experiments_20260509/run_tf14_remaining_experiments.py` 增加 `--continue-on-error`。
  - 调试时默认不启用，异常会直接抛出，方便定位。
  - 正式长批次启用后，单个 run 崩溃会写入 `tf14_remaining_runs.csv`，并继续跑后续工况/方法/seed。
- 增加 `--retry-exceptions`。
  - 只忽略历史 CSV 中 `failure_type=runtime_exception` 的旧失败行，让这些 run ID 可以在下一次续跑时自动重试。
  - 不会自动重跑 `path_not_completed` 这类算法本身失败的行，避免 ZOH surrogate 这种弱对照在每次续跑时反复重跑。
- 成功样本增加 `run_status=completed`、`exception_type`、`exception_message` 空字段。
- 异常样本增加 `run_status=exception`、`success=0`、`failure_type=runtime_exception`、`nan_class=runtime_exception`、异常类型、异常消息和异常 log 路径。
- 更新 `run_publication_final_batches.ps1`，正式批处理默认带上 `--continue-on-error --retry-exceptions`。
- 更新 `derive_publication_gate_tables.py`：
  - `group_count_gate_existing_runs.csv` 增加 `num_success`、`success_rate`、`num_runtime_exception`。
  - T1 gate 增加 `required_method_success`，检查非辅助底线方法是否全部成功。
  - ZOH surrogate 属于辅助底线方法，允许它失败而不影响 `required_method_success`，但仍会在 group 表中显示 `success_rate=0`。

## 设计理由

- 正式 n=20 批处理包含多个实验、多个方法、多个工况和 20 个 seed，运行时间较长。单个工况异常不应该导致整批数据完全报废。
- 异常行必须进入 CSV，否则后续 gate 表无法知道哪些样本缺失，也无法向审稿人解释样本数量和失败原因。
- `--retry-exceptions` 只重跑程序异常，不重跑控制效果失败。这样能区分“代码/环境崩溃”和“算法在该工况下失败”。

## 验证结果

- Python 语法检查已通过：
  - `E:\anaconda\envs\pytorch_new\python.exe -m py_compile .\tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py`
  - `E:\anaconda\envs\pytorch_new\python.exe -m py_compile .\paper_dcn_tf12_draft\publication_readiness_round5_2026-05-11\derive_publication_gate_tables.py`
- runner `--help` 已能显示新增参数：`--continue-on-error`、`--retry-exceptions`。
- `run_publication_final_batches.ps1` 已通过 PowerShell AST 解析检查。
- 异常行写出单元测试已通过：
  - 输出文件：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/unit_exception_row.json`
  - 检查结果：`run_status=exception`、`failure_type=runtime_exception`、`success=0`、`exception_type=RuntimeError`。
- 自动生成的 `README_zh.md` 模板已改为中文，后续正式结果记录不会再混入英文说明。
- 空方法快速生成检查已通过：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/empty_readme_check`
  - 结果：`README_zh.md` 标题、状态说明和聚合指标表头均为中文。
- 更新后的 gate 脚本已在 E0 全方法 smoke 上验证：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/gate_check_e0_allmethods_smoke_v2`
  - 结果：`required_method_success=PASS`，ZOH surrogate 单独显示 `success_rate=0.0`，非辅助方法成功率均为 `1.0`。
- gate 派生 Markdown 报告已改为中文：
  - 输出目录：`paper_dcn_tf12_draft/publication_readiness_round6_2026-05-11/gate_check_e0_allmethods_smoke_v3`
  - 结果：报告标题、来源说明、Gate 摘要和使用限制均为中文；`PASS/FAIL/PARTIAL` 作为机器可读状态保留。

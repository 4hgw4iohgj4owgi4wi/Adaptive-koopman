# D2 RTX 5080资格阻断只读审计执行记录

执行日期：2026-09-15。范围为D2只读工程边界核查；没有修改GPU候选、安装软件、执行G1/G2、运行植物或启动闭环。

## 正式身份与结果

- 正式协议：`protocol/D2_GPU_RUNTIME_BLOCKER_AUDIT_20260915_v2.json`。
- 协议SHA-256：`609e45331404d22ff63e248c391d5b9581d840c604e83f0581c8a4b3bd0cc0ed`。
- 正式输出：`analysis/20260915_D2_GPU_RUNTIME_BLOCKER_AUDIT_02`。
- 报告状态：`PASS_READ_ONLY_BLOCKER_LOCALIZED`。
- 决策：`ENGINEERING_FIX_REQUIRED_BUT_REPAIR_BUDGET_NOT_REOPENED / STOP_BEFORE_G1_G2_G3`。
- 错误协议SHA负例退出1且没有创建输出。

## 新定位的高可信候选根因

旧v3把CUDA worker源码改成只显式导入Torch，并将返回值改为Python列表；但CPU端`ipc_backend.py`仍在`rhs`、`rk4`、`rollout`和`linearize`请求中把`numpy.ndarray`直接交给pickle。

因此worker即使没有`import numpy`语句，第一次反序列化G1数组请求时仍可隐式导入NumPy。初始化模型参数已转成列表，所以G0可完成；G1是首次携带NumPy数组的请求，恰与历史“G0通过、G1前发生libomp/libiomp冲突”的停止点一致。本环境同时存在`libomp.dll`和两个位置的`libiomp5md.dll`。

该结论登记为`LIKELY_ROOT_CAUSE_STATIC_AND_TIMING_NOT_YET_INTERVENTION_PROVEN`：静态数据流与停止时序高度一致，但在另行授权修复并复测前不冒充动态因果证明。

另外发现资格脚本`error_stats`仍调用`error.square()`；活动环境NumPy 2.0.1的ndarray没有该方法。即使OpenMP问题被解除，脚本到达误差统计后仍会再次停止。

## 建议的最小修复（本次未实施）

1. 在CPU端发送前，把`rhs/rk4/rollout/linearize`消息里的所有ndarray转换为嵌套Python列表，确保worker反序列化不加载NumPy。
2. 仅把资格报告RMSE表达式从`error.square()`改为`np.square(error)`。
3. 重新冻结源码身份和G0—G2协议；保持float64、现有数值门、CPU OSQP和禁止`KMP_DUPLICATE_LIB_OK`不变。

现任务书已经记录两轮工程修复用尽，且没有重新开放额度，因此本次不实施以上改动、不试跑G1。D3继续阻断。

## 图表问题、解决方法与效果

首版数值报告正确，但零高度柱的`BLOCKED`标签使用白色，落在白色背景上不可读；首版manifest标为`FAIL_VISUAL_QA_SUPERSEDED`并保留。

解决方法是只把零柱标签改为深红色，在新协议和新输出目录重做只读报告。正式PNG/SVG已打开检查，五项状态均清晰可读，`figure_status=PASS_VISUAL_QA`。没有改变审计输入、候选根因等级或任何实验结论。

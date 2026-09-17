# EFD-R1.3工作记录

## P13001 — 根据R1.2方法身份停止结果修订协议

- 时间：2026-08-24
- 新增：`D:\PDxc\Review\efd_r13.md`、`D:\PDxc\Review\efd_r13_log.md`。
- 历史保护：未修改已执行的`efd_r12.md`及其T0/T1停止结果。
- 核查证据：`efd_r12_t0.json`、`efd_r12_t1_identity.json`、`efd_r12_complete.json`、`efd_r12_solution.md`、`actual_irsp_audit.json`、原`compare_pipeline.py`和原稿IRSP/Koopman章节。
- 最新事实：R1.1修复后S2为12/12通过；R1.2 T0通过；T1发现四车compare K3为92维/8输入structured bilinear、无IRSP，而真正IRSP是TF14 31维/2输入模型。
- IRSP审计：采样谱半径最大值约0.998，但`||A+||₂=1.0980`、连续triangle bound=1.3261，目标0.998；连续输入域证书不成立。
- 路线修正：新立链A原论文31/2 IRSP审计和链B四车46/92/8预测实验；唯一ID带维度，禁止再共享K3名称或artifact。
- 路线修正：IRSP不再是四车主实验前置条件，也不新造四车IRSP；当前论文处理为降级为采样谱半径正则化，并依据noIRSP收益决定是否删除。
- 路线修正：R1.3使用231xxx候选seed；221xxx只审计未生成数据，不复用以避免版本混淆。
- 对齐要点：bilinear机制、IRSP证书、force退化、创新结构、family统计和盲确认均有独立关闭证据。
- 本次只修改实验MD和留痕，没有修改5080代码、生成数据或训练模型。
- 文档自检：13个一级章节齐全；两条证据链、唯一维度ID、sampled/continuous分层、链A不误阻断链B和最强简单基线门均已写入。
- 下一允许动作：在5080执行U0方法注册表与历史树冻结；链B真实cache回归U2通过前不得生成新pilot。

## P13002 — U1报告路径小修

- U0已通过，选择`BASE=231000`；唯一方法ID、shape、artifact隔离全部通过。
- U1已完成TF14冻结矩阵只读重算，但报告脚本递归扫描`paper_dcn_tf12_draft`时进入`node_modules`循环装载点，触发`WinError 448`。
- 修正仅将论文IRSP输入CSV查找改为冻结的明确路径；不修改模型、artifact、数据、矩阵、阈值或科学结论。
- `reproduction.json`在异常前已保存；同一结果将被复用，避免无意义重复GPU重算。

## P13003 — U2 H2历史函数签名小修

- U1矩阵复现最终通过：四个矩阵逐元素残差均为0；sampled通过、continuous失败。
- U2已完成D4R缓存和structured CSV复算，进入H2指标复算时发现历史`evaluate`要求显式传入`norms`，适配器漏传一个只读参数。
- 修正调用为`evaluate(model,val,ctx["norms"])`；不修改模型、数据、预测、指标或门槛，使用相同历史validation重跑U2。

## P13004 — U5联合状态truth维度小修

- U2、U3、U4均已通过；U4生成416/416条base且覆盖门全部通过。
- U5历史decoder实际输出30维车辆—货物核心状态，数据适配器误裁为前24维车辆状态，评价时出现`(30,)`与`(24,)`不匹配。
- 修正`s2_four`为完整`state30`；未修改任何模型、ridge、split、seed、物理数据或门槛。

## P13005 — U7基线几何切片小修

- U5结论：fixed-lift linear最优；full/structured bilinear虽使用N项但总体分别恶化约59.5%/46.0%，bilinear主张失败。
- U6结论：P1—P4全部未胜fixed-lift linear，核心回退`V-FL92-U8`。
- U7首跑将候选16维d/v与基线完整46维状态直接比较，触发广播错误；修正基线切片为`30:46`。
- 不修改几何模型、bootstrap、seed、ridge、decoder或门槛，同seed重跑。
# R13-009 U7 输出归一化接口修正

- 核查发现 `symmetric_normalizer` 含“首维为常数输入”的专用钳位，不能用于无常数项的 16 维几何输出。
- 该误用把第一个位移输出强制为均值 0、标准差 1，造成修正前 G2/M 位移、连接力和载荷异常放大。
- 已改为仅对输出均值和标准差做镜像成对平均；输入特征仍保留常数维钳位。
- 修正前的 `results.json` 和 `complete.json` 将分别保存为 `*_pre_output_normalizer_fix.json`，随后使用相同数据和种子重跑 U7。
- 同时将 NumPy 布尔量显式转为 Python `bool`，修复失败报告 JSON 序列化异常。

# R13-010 U7 修正后复跑与硬停止

- 5080 使用原数据和原 5 个 bootstrap 种子完成 U7 复跑；G2 交换子达到数值零，异常放大消失。
- V-M 代表性改善：几何 13.81%、速度 34.24%、力 14.96%、载荷 46.00%；几何未达到 30% 门。
- bootstrap 仅 3/5 为正，236003/236004 显著劣化，未达到至少 4/5 的复现门。
- `M_point_gate_passed=false`，`M_full_gate_passed=false`，`development_read=false`。
- 已为 U8/U9/U10 写入 U7 阻断标记；未读取 development、未生成 confirm、未执行网络/闭环实验。
- 已将远端阶段结果、工作日志和 solutions 拉取到 `D:\PDxc\Review\efd_r13_results`，并新增 `efd_r13_solution.md` 汇总事实、限制、论文影响与另立协议的恢复条件。

# P13006 — R1.3实验冻结与未来方向未启动登记

- 时间：2026-08-24。
- 用户决定：冻结此前Koopman实验；`EPD-Koopman`只作为未来创新方向登记，本次暂不启动。
- 5080冻结对象：`revision_2026/koopman/innovation/efd_r13/`代码树和`revision_2026/koopman/innovation_efd_r13_results/`结果树。
- 新增远端状态标记：结果树中的`FROZEN.md`；该文件在计算结果树哈希前写入并纳入逐文件清单。
- 新增远端冻结目录：`revision_2026/koopman/frozen/efd_r13_20260824/`，包含`freeze_manifest.json`、`file_manifest.csv`、`freeze_r13.ps1`、`verify_freeze.ps1`和本工作记录副本。
- 代码冻结：36个文件、244616字节，tree SHA256=`48A3A48BC11CD400C865CF8D0EF863FA00FA4AA223C4CCFBC4BA8BB265D8437A`。
- 结果冻结：938个文件、825295130字节，tree SHA256=`57D228D1B513F4DAE5B4581925DB5401E49BED2B82707F2D52BBF6FAA067667F`。
- 逐文件清单SHA256=`4E159DDF3B668EFB6CFDFB9C09A641C0235CCE15EF0F9448B08ACFD8A316154A`；清单已同步至`D:\PDxc\Review\efd_r13_freeze\`，本地复算一致。
- 5080二次逐文件验证：974/974通过，0个缺失、0个哈希变化、0个清单外新增文件。
- 进程和目录核对：没有R1.3/EPD-Koopman Python训练进程；没有EPD-Koopman代码目录。
- 状态边界：R1.3执行至U7；U8—U10未执行；development未读；confirm未生成。
- 未来方向字段：`status=NOT_STARTED`、`code_created=false`、`data_generated=false`、`training_started=false`，需用户以后明确授权并另立协议后才能启动。
- 本次未修改任何既有R1.3代码、数据、模型、JSON结果或旧日志内容；只新增冻结标记、清单、验证脚本和本条留痕。

# NR-KDCC four-layer routed-arrow Visio figures

生成文件：

- NRKDCC_nature_framework_flow_route_visio_editable.vsdx：三页 Visio 源文件，第 1 页为四层总体框架图，第 2 页为信号流式控制流程图，第 3 页为论文技术路线/论证链图。
- NRKDCC_framework_nature_style_editable.vsdx：单独的总体框架图 Visio 源文件。
- NRKDCC_control_flow_nature_style_editable.vsdx：单独的在线控制流程图 Visio 源文件。
- NRKDCC_technical_route_reference_style_editable.vsdx：单独的论文技术路线图 Visio 源文件。
- NRKDCC_framework_nature_style.png / .svg：总体框架图预览与投稿用矢量导出。
- NRKDCC_control_flow_nature_style.png / .svg：控制流程图预览与投稿用矢量导出。
- NRKDCC_technical_route_reference_style.png / .svg：技术路线图预览与投稿用矢量导出。

编辑说明：

- .vsdx 文件中的模块框、箭头、标签和车辆--载荷示意均为 Visio 原生形状，可直接移动、改色、改文字。
- 所有包含多个要点的模块均采用“外层模块框 + 内部小要点框”结构；内部每个小框也是 Visio 原生形状，可单独编辑。
- 当前框架图按离线层、上层、下层、安全层组织，并包含四车 4WS 协同搬运示意与单车动力学示意。
- 当前控制流程图采用信号流框图风格：方块表示变量/功能模块，圆形表示代数运算，菱形表示判断。
- 判断节点均保留完整出口：例如 fault? 的 yes 分支进入 FTC 切换，no 分支绕过 FTC 并进入正常命令发布。
- 求和/融合节点均保留多路输入：例如车间通信 raw packet 与质量一致性共同进入 Σ，参考输入与远端预测共同进入 +，投影控制与回退控制共同进入安全层 Σ。
- 已按“线不能穿过模块块体”的要求，将跨层线、反馈线和回退线改为绕块折线；同一条折线只在末尾保留箭头，转折处不放箭头。
- 第 3 页按照用户参考图的“虚线大章节块 + 小模块框 + 方向箭头”组织，用于展示论文逻辑而不是控制时序。
- 当前风格采用 Nature 控制类论文常见的浅底、少色、分层机制、实线主链路和虚线跨层/保护回路。
- 配色避免大面积纯黑：深蓝灰用于文字，蓝色用于模型/车辆执行，橙色用于上层协调，青色用于通信与感知，玫红用于安全保护。

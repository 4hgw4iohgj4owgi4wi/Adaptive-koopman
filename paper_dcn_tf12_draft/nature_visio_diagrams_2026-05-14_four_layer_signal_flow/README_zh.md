# NR-KDCC reference-style two-layer Visio figures

生成文件：

- NRKDCC_nature_framework_flow_route_visio_editable.vsdx：三页 Visio 源文件，第 1 页为参考图风格的上下两层总体框架图，第 2 页为两类通信控制流程图，第 3 页为论文技术路线/论证链图。
- NRKDCC_framework_nature_style_editable.vsdx：单独的总体框架图 Visio 源文件。
- NRKDCC_control_flow_nature_style_editable.vsdx：单独的在线控制流程图 Visio 源文件。
- NRKDCC_technical_route_reference_style_editable.vsdx：单独的论文技术路线图 Visio 源文件。
- NRKDCC_framework_nature_style.png / .svg：总体框架图预览与投稿用矢量导出。
- NRKDCC_control_flow_nature_style.png / .svg：控制流程图预览与投稿用矢量导出。
- NRKDCC_technical_route_reference_style.png / .svg：技术路线图预览与投稿用矢量导出。

编辑说明：

- .vsdx 文件中的模块框、箭头、标签和车辆--载荷示意均为 Visio 原生形状，可直接移动、改色、改文字。
- 所有包含多个要点的模块均采用“外层模块框 + 内部小要点框”结构；内部每个小框也是 Visio 原生形状，可单独编辑。
- 当前版本参考用户给出的车辆控制框架图风格：左侧物理交通场景，上部上层重构/诊断/跨层发布，下部模型驱动的四车维护控制。
- 当前版本按最新代码区分上层协调/参考发布、下层逐车 Koopman-MPC、车间感知通信、上下层参考通信和上下层命令通信。
- 第 3 页按照用户参考图的“虚线大章节块 + 小模块框 + 方向箭头”组织，用于展示论文逻辑而不是控制时序。
- 当前风格采用 Nature 控制类论文常见的浅底、少色、分层机制、实线主链路和虚线跨层/保护回路。
- 配色避免大面积纯黑：深蓝灰用于文字，蓝色用于模型/车辆执行，橙色用于上层协调，青色用于通信与感知，玫红用于安全保护。

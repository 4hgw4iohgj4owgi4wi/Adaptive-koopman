# NR-KDCC review-clean Visio figures

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
- 当前框架图删除右侧大空总线，改为四层之间的短反馈/回退箭头，并加入图内颜色与线型图例。
- 当前框架图左下安全层示意不再使用外层截图式边框，且将原来的安全控制圆形节点改为“保护信号融合”，并接入安全滤波链路，避免和下层执行控制混淆。
- 当前控制流程图已按参考图重画为“上方离线训练块 + 下方在线适应/闭环控制块”的结构。
- 离线训练块展示 nominal system 数据生成、lifting phi、双线性 Koopman 算子 A,B,N_l、输出矩阵 C、训练/rollout 验证，并向在线块下发模型矩阵、lifting 函数和 PPC/ISS 边界。
- 在线闭环块展示 lifting、系统响应、传感器噪声、输入扰动、FDI/FTC 在线模块、模型/约束更新、delay-compensated Koopman-MPC、PPC/cert selector 与执行控制 u_i^{act}。
- 残差通道同时接收 Koopman predicted response 与 actuator/plant response，避免残差来源不明；故障不作为 FDI 的直接输入。
- 框架图中候选控制采用绿色正常控制链路，红色仅表示故障、残差和安全诊断链路。
- 外部故障/退化只作用到通信/执行器/车辆系统，FDI 仅通过 residual/state mismatch/control response 推断故障，避免“使用真实故障标签”的误解。
- 底部反馈合并为 monitoring/logging bus，文本压缩为 trajectory / connection / force / certificate / timing logs，只保留必要反馈线；跨层线、反馈线和回退线尽量绕开模块块体，同一条折线只在末尾保留箭头。
- 第 3 页按照用户参考图的“虚线大章节块 + 小模块框 + 方向箭头”组织，用于展示论文逻辑而不是控制时序。
- 当前风格采用 Nature 控制类论文常见的浅底、少色、分层机制、实线主链路和虚线跨层/保护回路。
- 配色避免大面积纯黑：深蓝灰用于文字，蓝色用于模型/车辆执行，橙色用于上层协调，青色用于通信与感知，玫红用于安全保护。

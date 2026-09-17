# K2线性变量门结果

完整数值见`results.json`，图片为独立test的teacher-free 1--20步NRMSE。

- K2.0：通过；split={'train': 70, 'validation': 15, 'test': 15, 'external': 20}。
- K2.1：raw与lifted linear在test/external均输出有限状态、四点力和张开误差。
- K2.2：S2>S1门=True，S3>S2门=True。
- 下一阶段状态合同：`S4-force-in`；物理输入仍固定为`U1-four`。
- 固定非训练lift下，S5与S3共享同一输入和力监督读出，不能伪装成两个独立模型；真正S4/S5选择留给共享可训练lift。
- 当前只允许进入E-L/E-C/E-T线性专家；不允许提前训练bilinear/MF-IK。

# K3停止：G32状态合同门失败

- trainable/fixed composite：`{'S4-force-in': 0.2266932903021488, 'S5-force-out': 0.22671371559054834}` / `{'S4-force-in': 0.19041097743390345, 'S5-force-out': 0.21332058365135875}`。
- improves fixed：`{'S4-force-in': False, 'S5-force-out': False}`。
- S4相对S5：`{'state': -0.08428172390001173, 'connector': -0.009655337009521536, 'opening': 0.020869607723676867}`；逐轨迹CI见`development/A_results.json`。
- S4传感压力门：`False`。
- S5不劣5%：`True`；S5 external更好：`False`。

按k3.md停止：不训练方案B，不生成confirm，不接入闭环。若两种可训练lift均不优于fixed linear，论文回到旧fixed方案A。

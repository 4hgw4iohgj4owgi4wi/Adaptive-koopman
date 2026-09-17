

## W0053 — 普适性实验T0冻结与历史复现门

- 协议hash=DF6EE9810137687B9C3814040FFF827DB1DC2DFAE1ED2F2045E6F2618F69BCF7；执行脚本hash=0E153987547B683930882FC86C3B3904D40D52517FA25F7B310422BC3D77DD97。
- B0–B5B artifact匹配={'K2': True, 'K3': True, 'K3-r2': True, 'K4': True, 'K5-linear': True, 'K5-bilinear': True}；历史140条confirm文件完整=True。
- 冻结结果只读macro复核={'K0': 0.12513541290453, 'K1': 0.13283731952714745, 'K2': 0.4023273784857165, 'K3': 0.44346566324356557, 'K3-r2': 0.44346566324356557, 'K4': 0.40143743177289654, 'K5-linear': 0.16730901051004596, 'K5-bilinear': 3928981162.612287}；G0=FAIL。
- 本阶段未生成D1/D2、未训练F/H/T/C/A、未启动闭环。


## W0053R — 普适性实验T0冻结与历史复现门

- 协议hash=DF6EE9810137687B9C3814040FFF827DB1DC2DFAE1ED2F2045E6F2618F69BCF7；执行脚本hash=06DF6742D6973853882D45CEC4A1127DC87937640B53FD8688538249D5E76441。
- B0–B5B artifact匹配={'K2': True, 'K3': True, 'K3-r2': True, 'K4': True, 'K5-linear': True, 'K5-bilinear': True}；历史140条confirm文件完整=True。
- 冻结结果只读macro复核={'K0': 0.12513541290453, 'K1': 0.13283731952714745, 'K2': 0.4023273784857165, 'K3': 0.44346566324356557, 'K3-r2': 0.44346566324356557, 'K4': 0.40143743177289654, 'K5-linear': 0.16730901051004596, 'K5-bilinear': 3928981162.612287}；G0=PASS。
- 首次G0因K5-bilinear十位数量级均值的手工常数少保留约4.77e-7而失败；已用冻结JSON经Python计算的精确float修复并保留初始失败文件，未改模型/数据/协议。
- 本阶段未生成D1/D2、未训练F/H/T/C/A、未启动闭环。


## W0054 — 普适性实验T1强受力覆盖门

- 预注册96配置全部运行；合法配置=0/96，失败配置=96。
- 合法峰值连接力=0.00 N（额定力0.00%）；L3配置=0，L3互不重叠20步窗=0。
- G1=FAIL（failed_no_L3_in_coarse_scan）；按冻结协议T2–T9均不适用，未训练F/H/T/C/A、未生成D1/D2、未启动闭环。
- 扫描CSV hash=A094C9C70E5E09A457636C2209877C2783D408CE6780E64AA2E3370EB229AC0F；图片hash=D52613EF94ABD6AF063E7752251E916B1F43ED183874191F72F7ED68E3432324；solutions hash=FFCEF976E39435E9DDAC2FE8AB852DCFD826EEE05A66DD4D68224009802FC9CA。


## W0054 — 普适性实验T1强受力可行性扫描

- 96配置和五seed重复通过；允许继续生成D1。峰值=12994.05 N。


## W0055 — 普适性实验D1数据与完整G1覆盖门

- D1完成=368/368，失败=[]；覆盖={'train': {'L0': 8016, 'L1': 3808, 'L2': 1398, 'L3': 927, 'L4-high': 11, 'R0': 88, 'R1': 2733, 'R2': 11046, 'R3': 2612, 'R4': 1019, 'R5': 5141, 'trajectories': 240}, 'validation': {'L0': 2122, 'L1': 1036, 'L2': 367, 'L3': 249, 'L4-high': 2, 'R0': 24, 'R1': 745, 'R2': 2921, 'R3': 721, 'R4': 242, 'R5': 1397, 'trajectories': 64}, 'development-test': {'L0': 2149, 'L1': 1023, 'L2': 359, 'L3': 235, 'L4-high': 10, 'R0': 17, 'R1': 782, 'R2': 2903, 'R3': 739, 'R4': 296, 'R5': 1361, 'trajectories': 64}}。
- G1完整覆盖门=FAIL；按协议停止T2–T9。
- D1 manifest hash=F9B37C3E0746E15E3EB45EBB0BE4B9A7C3193EF552C8B25187FCE00A2DFDAFDE；solutions hash=20A5E2A6E648551F352C011A26DDC878F71FF5BFF633222B9FF9B7EB11E47518。


## W0056 — 普适性实验G1停止报告固化

- 纠正早期solutions沿用“扫描无L3”模板的错误；真实结论为扫描通过但D1 train L3=927/1000。
- 方向平衡只读审计={'train': {'Q_FR': True, 'Q_LR': True, 'steering': True}, 'validation': {'Q_FR': True, 'Q_LR': True, 'steering': True}, 'development-test': {'Q_FR': True, 'Q_LR': True, 'steering': True}}；D1最大力=9958.97 N，最大ICR残差=3.280e-13 m/s，ultimate步数=0。
- 最终报告hash=41C9F12D34B48ED9042B6B30762624AAF42333F33CCF7BE2D2D66C5445B3A3CD；solutions hash=09DD9AF01B0E972029FE80FB278DC19F9ED610A6833B655F624DE8B9E1A090A7；停止manifest hash=852907BA2F0066C8FC0DBCC56994D9EA3950C4ED01285EF2C2C7F5243F1FA589。
- 未改协议、seed、D1文件或门槛；未训练F/H/RLS/T/C/A，未生成D2，未启动闭环。



## W0057 — 普适性v2 D1覆盖修正

- 保留v1失败并新增冻结强受力轨迹36条；完成=36/36，失败=[]。
- v2覆盖={'train': {'L0': 8646, 'L1': 4033, 'L2': 1631, 'L3': 1275, 'L4-high': 83, 'R0': 88, 'R1': 3032, 'R2': 12233, 'R3': 2891, 'R4': 1274, 'R5': 6017, 'trajectories': 264}, 'validation': {'L0': 2286, 'L1': 1088, 'L2': 396, 'L3': 378, 'L4-high': 5, 'R0': 24, 'R1': 793, 'R2': 3244, 'R3': 765, 'R4': 312, 'R5': 1616, 'trajectories': 70}, 'development-test': {'L0': 2275, 'L1': 1107, 'L2': 476, 'L3': 285, 'L4-high': 10, 'R0': 17, 'R1': 844, 'R2': 3215, 'R3': 797, 'R4': 338, 'R5': 1579, 'trajectories': 70}}；G1=PASS；train L3 20%余量目标=PASS。
- v2协议hash=AF47ED91A5E918159AFFE072F98D5A135ECB7439876E11CF01654A1C5A9EBB94；combined manifest hash=83FC7A6E2AEA7EA4FDD35EE24E1922402D6C7D0B97D6843329B3624112D00797。


## W0058 — 普适性v2 T2骨干审计

- G2合格骨干=[]；排除=['K0', 'K1', 'K2', 'K3', 'K3-r2', 'K4', 'K5-linear', 'K5-bilinear']。
- 所有骨干均在D1-v2 train归一化下只读复算；条件数/秩/发散仅作分支淘汰，不再全局停止。
- backbone audit hash=EDC9143514D8778F8C346DB02194E170FDF73C70BF072098D8CCF3FDA4CD1CFD；结果hash=555756C16E4E5C03F5B3FB92E0EE13B1089852AB836929DECA3835304FC380C3。


## W0059 — G2入口卡口逻辑勘误

- 保留首次G2全排除结果；识别到以长时域性能作为H入口会造成逻辑自锁。
- 按有限值/条件数/有效秩重分类，F/H入口=['K0', 'K1', 'K4', 'K5-linear']；其余骨干只保留诊断。
- 勘误hash=A448DF35D6B0F6EC3ED54356120D0F0596A321FDC3F13CD69709ED557BCBE865；未降低模块后的状态保护、发散或部署门。


## W0060 — v2 T3因果物理受力头

- 在G2重分类骨干['K0', 'K1', 'K4', 'K5-linear']上完成F0/F1/F2；通过8%相对门的家族数=0/4。
- F2只替换8维四点力，Q与因果力变化率统一重构；状态逐元素未改。
- 结果hash=6CF10DC383253F0954708481E314C3B969DEF7D2FC403DBB3276713A10D4900A；模型目录=D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman\universal_v2\t3\models。


## W0061 — F词典序回退冻结

- 发现初版F结果只在F2网格内选择，遗漏S规则要求的原骨干F0回退点；未重训、未改数据或候选。
- 按validation选择并用development门决定BFH头：{'K0': 'F0', 'K1': 'F0', 'K4': 'F0', 'K5-linear': 'F0'}。
- selection hash=0CF3DCC20EDE98C69EBA23EA78DD29A1450413E51D37EBA714F1DE803539DE8A。


## W0062 — v2 T4直接多时域H

- H-LS/H-RLS在四个入口骨干完成；8%+状态保护+发散不增门通过=0/4。
- RLS使用与LS相同特征、标准化、rank、ridge和有序样本；lambda=1与batch解作为必须保留回退。
- 结果hash=6EDAC02A31C7DBC14E10F11B4202E43A3F73682AB51366ED2338CFEBF08D29B7；逐时域CSV hash=80FDF6BCD9D65FD266F00C63CE45A936641BCC796D8636D36ADE7BAD6B6484AE。


## W0063 — 参数任务数据生成

- 冻结38个maximin-LHS参数任务；生成train/validation/development前30任务×3场景=90/90，失败=0。
- 参数表hash=229AF88EC5583FD843BD8E25B262B3B6D2F0DB5C267CE533045AFD294661E822；manifest hash=8070FE8A0EBF7BA4CA732254A9446D204598B5D7FC032978B7DD387C29827F1A。
- 任务失败不替换参数组合或seed；future-confirm 8任务留到D2冻结后生成。


## W0064 — v2 T5时间一致性/重新升维机制门

- 逐骨干潜空间漂移诊断完成；C实际运行=['K1', 'K4', 'K5-linear']。
- T状态=not_applicable_no_nonzero_legal_H；没有合法非零H时不为凑实验强训T。
- 机制hash=E9D6C95C9819FE6D27D58AC1283F29CE54EEB4B9841B4F41887A8F970C34D198；C结果hash=E87CA0FD49067EE5D8A4EAEDCD6ED0C1D00099FA838D95329524684E3B267A6F。


## W0065 — v2 T5参数共享低秩适应

- A0/A1(1/2/5s)/A2-online在4骨干、5个development参数任务上完成；通过=['K5-linear']。
- 共享基底只由20个train参数任务的一步残差学习；validation选rank/prior，development不调参。
- 结果hash=AE50E3E3470DFA484567BFA93028515E0B7DCC51B3D03F9806C44809CCB3785C；CSV hash=7FFE2FBA623DC81BB97E8FDD98D553E8606FC7EA7B9134B532E568DB08F75EEA。


## W0066 — 参数范围实现错误归档

- 首轮参数任务误用了历史external极值范围；90条轨迹和A结果全部移入invalid_parameter_range_20260822，不作为证据。
- 修复为预注册范围：质量0.85–1.15、刚度0.75–1.25、阻尼0.70–1.30、间隙0.70–1.40、附着0.80–1.10；maximin候选恢复100。
- 参数任务、90条轨迹和A必须整批重算；D1/F/H/T/C未依赖该参数集，无需重算。


## W0063 — 参数任务数据生成

- 冻结38个maximin-LHS参数任务；生成train/validation/development前30任务×3场景=90/90，失败=0。
- 参数表hash=3F76F05AD472198249D0223DE9244A8CFBB4140414A3331162C0EDAC9C5BDF1A；manifest hash=5D8FA8DE1902AC2697948AE3F801DE8B87C0ED6F7D4417DB8164671F84E004C9。
- 任务失败不替换参数组合或seed；future-confirm 8任务留到D2冻结后生成。


## W0065 — v2 T5参数共享低秩适应

- A0/A1(1/2/5s)/A2-online在4骨干、5个development参数任务上完成；通过=['K5-linear']。
- 共享基底只由20个train参数任务的一步残差学习；validation选rank/prior，development不调参。
- 结果hash=6D98DB83633AFDC5A5C23E14971CD3A00CC83B2FC1BB804FCA8F549FBBDA588E；CSV hash=1540135F2452C6AC2E6322EB74EEF7EA9277E0665948095286CB1B60C879E5C4。


## W0067 — v2 D2一次性确认集生成

- 冻结后生成internal=160/160、external=24/24、network=40/40；失败=[]。
- network文件复用对应internal plant真值，只叠加mask/AoI/trace；确认文件生成后设只读。
- freeze hash=F198C275370B4E169D461FE6FF5A98C3BA2AF1370AECE9A769BE8C329DEA53DD；manifest hash=E7D3EADF70C36126B76A1C15B3E6AB29039FA40E24AB4820BCE4341528EA23A3。


## W0068 — v2 D2一次性确认

- 一次性评估全部冻结有限候选；internal通过=[]；参数适应复现=['K5-linear']。
- F/H跨家族门未在development通过，因此无论confirm局部结果如何均不授予普适性；绝对部署候选为空。
- 结果hash=FEC238B83167809F8325867151F9DF3C022E646552E4D1ACF3C07519043C14EB；门禁hash=DDA191FD3C563A50368DE95834ED4A847D154031B2F19AC6E31E0674BFD49AEC。


## W0069 — v2诊断闭环

- 绝对部署候选为空，正式闭环=0；统一有限控制集20步适配器完成诊断=230/230，失败=0。
- K0/K1覆盖100m clean、单移线、回头弯以及IID/burst/delay/DoS有无状态传播保护；K5+A只做外部参数回头弯。
- 结果hash=72AF639FF7486444A2ADE9ED461A7D964F2EFA5C01F30C2DD6BC1FF76C91C4AC；全部标记diagnostic_only_offline_gate_failed。


## W0070 — 参数闭环配对补充

- 识别到首轮K5参数闭环持续更新，按事实重标A2-online；补跑K0/K1/K5-A0/K5-A1-2s同seed=40/40，失败=0。
- A1只使用前2s残差后冻结，A2保留持续1步残差更新；不得混写。
- 结果hash=9E613E4A8CE26AA0F91A9B91B944F6807B45022E672D7FFBF242E9B1311EF2EA。


## W0071 — v2最终报告与图表

- 生成12张结果图及对应CSV/JSON；缺失=[]。
- 最终结论：跨骨干普适性不成立；K5 few-shot参数适应为唯一复现的局部信号；正式部署候选=0。
- final report hash=3E7CD3B2AE5D81945CDB44C4A6253311FF789E60E01021495326DED149244790；solutions hash=85A745BD5A3E39B751FCBA548DE3962726E7F7A0391FAE5030882FFD67789BDA。


## W0072 — D2 external A配对统计复核

- 对冻结D2 external按24条轨迹做10000次配对bootstrap并对4骨干Holm校正；通过=['K5-linear']。
- 统计hash=301687B64445E572B53C995C36EBCBFD062D2911949D2747B3F27AA916A8499B；保留初始均值门文件universality_gates_initial.json。
- 未修改模型、候选、D2数据或超参数；只补齐预注册统计判定。


## W0073 — 最终报告external统计补审

- 补齐K5 external A的24轨迹配对bootstrap与4骨干Holm校正；K5 A1-2s均值改善10.01%，95% CI 9.18%–10.88%，统计门通过。
- K0/K1/K4统计门不通过；正式部署候选仍为0，跨骨干普适性结论不变。
- 更新后final report hash=C8FD9D562632DDE8EA439C21933A3E3707ABAD62481CDDC8C993E1519AB93E54；统计hash=301687B64445E572B53C995C36EBCBFD062D2911949D2747B3F27AA916A8499B。


## W0074 — G6恢复确认

- 原D2降级为协议路径变更后的审计集；全新D3完成160 internal+24 external+40 network并一次性评估。
- D3 internal通过=[]；external适应通过=['K5-linear']；正式部署候选仍为0。
- 结果hash=51C1A8745B63A629C39A38E17F461951DF1EBCDDC66FBC3A3166A21B5435F2BC；最终门hash=351B99AC57D68FCE215CA4D62295643831EB6E4058BBAE4A37BDD21C13A19102。


## W0071 — v2最终报告与图表

- 生成12张结果图及对应CSV/JSON；缺失=[]；最终确认版本=D3-recovery。
- 最终结论：跨骨干普适性不成立；K5 few-shot参数适应为唯一复现的局部信号；正式部署候选=0。
- final report hash=483AE5659B765ACF10895D43CC5A7CE959699771B54F85CF9AFAF8A096FC63CE；solutions hash=37B9D1087E35966D1F796EA7F27EF16639B82C5DDA784A992374C130EC36BE3E。


## W0075 — D3最终报告hash复核

- D3 K5 external A的24轨迹配对bootstrap与4骨干Holm校正通过；K5 A1-2s均值改善10.19%，95% CI 9.39%–11.03%。
- K0/K1/K4统计门不通过；正式部署候选仍为0，跨骨干普适性结论不变。
- 更新后final report hash=8660BE7235A7BF9DCB97B440C67034098EB8DB743ADBA73CF1E0AED05B26F9B9；统计hash=07B33719009574CCDE9785B360EA661C7DF6B23A024C4CFEF3324E33258A9F0E。

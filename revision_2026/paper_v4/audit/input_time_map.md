# 原记录器输入时间映射

范围：当前koopman_predict_auto原生产代码的运行级验证，不替代历史生产版本审计。

证据来源：`revision_2026/paper_v4_results/20260909_E00_02`；`recorder.json` SHA256 `B19AF4AB270CC71313F95B8F757886EE53634B7416C9D4F2B6DE752E7E425C28`，`pulse_raw.npz` SHA256 `7323C51DA9A05E9BDE6095BE9A7B30CE06D474B6FED6E550B9F0C2625CAC847D`，`pulse_cache.npz` SHA256 `490D0826CB6DE3DB58FD0F61886A7FDF17552EDED32FBB6C0470BDCA1E046DD0`。本文件于2026-09-11迁入`paper_v4/audit`，未重跑或改写脉冲数据。

## 时间约定

物理时间tick k对应X_k。原记录器在完成区间[k,k+1]后记录raw行k，所以raw.state30[k]=X_(k+1)，raw.requested_control4x2[k]=该区间已执行请求。缓存保留raw状态，不插入initial_state30，因此cache状态j=raw状态j，而cache输入j取raw命令j+1。

| control11列（0起算） | 来源 | 单位 |
|---|---|---|
| 0 | base_acceleration_mps2[1:] | m/s² |
| 1、2 | virtual_front_deg、virtual_rear_deg[1:]转弧度 | rad |
| 3—6 | requested_control4x2[1:,:,1] | rad |
| 7—10 | requested_control4x2[1:,:,0]−base_acceleration_mps2[1:] | m/s² |

## 运行证据

recorder_probe.py向原simulate_trajectory注入预定义0.12s输入，共6个20ms区间。pulse_raw.npz中脉冲在第2行（0起算），pulse_cache.npz中相同区间输入在第1行，正确控制raw状态1→2。逐个缓存区间从原状态和实际转角重放10个2ms植物步，5次下一状态最大绝对差均为0。四车辆请求加速度由虚拟加速度与差分列恢复，误差≤1e-12 m/s²。

结论：当前producer到control11的[1:]对齐正确；不能将其直接判为未来命令泄漏。原始第一段转移X_0→X_1没有进入该缓存，但初态另有记录，不是凭空补造样本。

剩余：历史数据生产冻结身份、完整访问链和正式网络因果测试尚未完成。已知请求序列可用于离线预测验证，不等于在线接收方有权访问未收到的邻车真实未来请求。

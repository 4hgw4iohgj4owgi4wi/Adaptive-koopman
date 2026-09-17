# Koopman 11 维输入协议（附录 B 实施授权书）

> 版本：2026-09-04；状态：APPROVED（用户于 2026-09-04 批准附录 B 修复路线）
> 父任务书：`koopman_refine.md`（SHA D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612）
> 执行机器：5080 `DESKTOP-9IUUGEO`；修订根：`revision_2026`
> KR0 判定：INPUT_CONTRACT_BLOCKED（D7 diff 0.228 m/s²、D9A 0.173，control7 无四车加速度列，
> 相同 control7 行可携带不同差分）→ 本协议批准后解除，输入契约补全先行。

## 1. 输入定义（冻结）

```text
u_k^11 = [(u_k^7)^T, Δa_FL, Δa_FR, Δa_RL, Δa_RR]^T
Δa_{i,k} = a_{i,k}^req − a_k^virtual      （i ∈ {FL,FR,RL,RR}，四车顺序固定）
```

- 四车请求加速度来自 raw `requested_control4x2[:, :, 0]`；虚拟加速度来自 raw `base_acceleration_mps2`。
- 索引对齐：control7 用 `requested[1:]`（u_k 对应 raw 行 k+1 的请求——区间语义），
  control11 差分列同用 `requested[1:, :, 0] − base_acceleration[1:, None]`。
- 使用四个差分（不用三个+零和假设；限幅可能破坏名义零和）。
- 控制序列来自预测起点提供的请求序列；禁止未来实际加速度/未来状态代替请求。
- 状态 x 47 维、潜变量 16 维不变；窗口、划分、力标签、原始物理轨迹全部不变。

## 2. 缓存派生（冻结规则）

- 新目录：`revision_2026/koopman_predict_auto_data/20260901_214725_AUTO_PREDICT_AUTO_R04_R01/n5_cache11/`
- 每个 npz 与 `n5/cache/*.npz` 同名同字段，另加 `control11`（前 7 列与旧 control7 逐项一致，
  后 4 列为差分加速度）。旧 `control7` 缓存永久保留、不改写。
- 派生脚本只读 raw；不重跑植物、不改标签、不生成新轨迹；逐文件 SHA 校验：control11 前 7 列
  与旧 control7 最大绝对差 = 0；差分列可由 control11 与虚拟加速度恢复四车请求加速度
  （重构误差 ≤1e-12 m/s²）。

## 3. 模型接口（冻结改动）

| 位置 | 改动 |
|---|---|
| `lift.py::GroupedResidualEncoder` | 两编码分支输入宽 38/35 → 42/39（各加 4 差分列）；潜变量仍 16 |
| `lift.py::TriangularResidualKoopman` | B0 47×11、G 16×11；x/eta 维数不变；检查点含 `input_schema: "u11"` |
| 归一化/S0 | 新输入归一化只用 fit；S0 用 11 维固定线性重新拟合；coeff 切片按 input_dim 配置（不硬编码 47:54/54） |
| 评价/损失/加速 | 全部按 `input_dim` 构造控制与增广 B；11 维数据不得截断给 7 维模型 |
| 数据契约 | WindowData 携带 input_dim；meta 中文名/phase 引用不传模型 |

## 4. 比较矩阵与基线规则（冻结，B.4 顺序）

1. 单元测试（重构/索引/权限/维数/gamma 回退）。
2. **固定线性 7 维 vs 11 维**（相同 fit/inner 划分，同折 norm/S0 各自拟合）——量化"仅补全已知控制"的收益；
   该收益记为输入契约修复，不当作算子创新。
3. **同预算残差结构 7 维 vs 11 维**（同一 Koopman 残差学习结构，报告参数量差异与优化差异）。
4. 若 11 维使原问题显著缓解：以 **11 维固定线性为新共同基线**，再冻结 koopman_refine.md 的
   aligned/fixed_guard/adaptive_guard 三方法比较（KR3+ 程序不变，基线换 11 维）。
5. 若 11 维仍无改善：按残差方向、力解码、实际转向状态等候选原因诊断；不继续增加传感器/专家。

- 11 维候选对 7 维基线不得直接声称算子更优。
- 原 7 维模型/检查点保留（只读）；7 维 run 产物不改写。
- 训练预算、seed、窗口、55 项保护、验收门与 koopman_refine.md 第 9 节逐字一致（基线 S0 为 11 维拟合）。

## 5. 身份与记录

- 本协议 SHA 进入输入修复链全部 run 身份；control11 缓存 manifest（文件 SHA 表）随 run 冻结。
- 每个改动文件 SHA 与 diff 记录；发现偏离立即停止并写解决方案。
- 本协议不授权：改动力学/连接器/执行器、删工况、改验收门、生成新 validation/confirm。

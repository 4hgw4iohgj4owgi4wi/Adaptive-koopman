# K4最终执行报告

## 1. 术语

历史代码字段`opening`统一解释为**货物拉伸载荷**：

- `Q_FR`：前后向货物拉伸载荷；
- `Q_LR`：左右向货物拉伸载荷；
- 单位为N；`opening NRMSE`是上述两个载荷的预测误差，不是张开距离或材料撕裂概率。

代码和JSON继续保留`opening`字段以保持结果兼容，中文报告不再简称“张开”。

## 2. K4.0证据隔离

- G40：`PASS`；120条K2轨迹hash和`70/15/15/20`数据角色已复核。
- confirm：预注册100 internal + 40 external；生成文件=`0`，查看=`false`。
- fixed复算：M0/M1/M1F相对K2保存结果最大绝对差=`0.000e+00`，门限=`1e-10`。

## 3. K4.1 fixed S4/S5部署合同

- validation clean S4/S5综合NRMSE=`0.18526194/0.20804246`。
- fixed S4相对S5的clean改善=`10.95%`。
- 轻压力逐指标5%门、连接力/货物拉伸载荷paired CI门、有限性门均通过。
- S4/S5 supervisor违反最短5个控制周期驻留和总切换率不超过`0.5 Hz`的门。
- G41：`FAIL`；K4.2唯一合同回退`S5-operational`。

这说明fixed S4存在clean精度价值，但当前supervisor不满足部署切换条件；不能把G41失败简化成“S4所有压力误差都更差”。

## 4. K4.2固定lift多步修正

### 4.1 五seed平均validation结果

| 模型 | 状态NRMSE | 连接力NRMSE | 货物拉伸载荷NRMSE | 综合NRMSE |
|---|---:|---:|---:|---:|
| M1 fixed S5 | 0.03095502 | 0.19977255 | 0.39339982 | 0.20804246 |
| M2 full refit | 0.07169575 | 0.23819190 | 0.42570155 | 0.24519640 |
| M3 anchor | 0.03767341 | 0.17968990 | 0.36337108 | 0.19357813 |

M3相对M1：

- 综合改善`6.95%`，低于预注册8%门；
- 状态误差恶化`21.70%`，超过允许的5%；
- 连接力误差改善`10.05%`；
- 货物拉伸载荷误差改善`7.63%`；
- 5/5 seed的综合方向一致，全部H=20 rollout有限；
- M3优于M2，支持“锚定比全量refit更稳”，但不足以支持整体部署价值。

### 4.2 已查看development结果

| 集合 | M1综合NRMSE | M3综合NRMSE | 说明 |
|---|---:|---:|---|
| `dev_test_old` | 0.21332058 | 0.19802767 | M3改善约7.17%，仍是已查看开发证据 |
| `dev_external_old` | 0.31781940 | 0.30409789 | M3改善约4.32%，不能替代confirm |

### 4.3 G42

- validation综合改善至少8%：`False`；
- 至少4/5 seed方向一致：`True`；
- 任一主要指标不恶化超过5%：`False`；
- development external不恶化超过10%：`True`；
- H=20全部有限：`True`；
- 锚定相对M2有独立价值：`True`；
- confirm未生成/未查看：`True`。

G42：`FAIL`。最终决策=`stop_return_to_M1_fixed_S5`。

## 5. 最终边界

1. 不生成confirm，不接入MPC，不追加网格或训练seed。
2. K4.3、闭环、DoS和H=8/12/16/20实验均未执行。
3. 当前论文与后续控制实验只能采用`M1 fixed S5-operational`作为Koopman predictor。
4. M3只能报告为“连接力/货物拉伸载荷改善，但状态预测显著退化”的开发负结果。
5. 不恢复trainable lift、三专家、bilinear、MF-IK或IRSP贡献。

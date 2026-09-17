# K4停止记录

K4.2开发门G42失败。按预注册规则停止：不生成confirm、不接入MPC、不增加网格或训练seed，最终预测器回退M1 fixed S5-operational。

## 失败项

- validation_composite_improvement_at_least_8pct: `False`
- at_least_4_of_5_seed_directions: `True`
- no_validation_primary_metric_worse_than_5pct: `False`
- dev_external_composite_not_worse_than_10pct: `True`
- all_H20_rollouts_finite: `True`
- anchoring_has_independent_value_vs_M2: `True`
- confirm_not_generated_or_viewed: `True`

完整原始值见`k42_results.json`。

"""KC1 finalization: errata.md, correction checklist update, complete.json."""
import csv
import json
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
KC0 = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc0"
KC1 = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc1"

errata = """# KC1 errata（纠错记录）

## C01/C02：固定线性基线含随机残差 —— 已修复
- 旧 v3u kr_b42 的"固定线性"用 new_model（随机初始化 E≠0）直接前向 → 输出含随机残差项。
- 本 run 独立实现 PureLinearKoopman（A0/B0/b0 递推，无 encoder/E）；三路等价验证
  （直接 NumPy / pure 类 / 残差模型 E=0 副本）5 折全部通过：pure vs numpy ≤4.1e-15，
  pure vs E=0 逐位 0.0。
- 旧表（v3u units/kr_b42_*）标 INVALID_BASELINE_REFERENCE（随机 E 污染），保留不覆盖。

## 真纯线性 11 维相对 7 维（5 折 inner，族分层；input7_vs11_pure_table.csv）
- D7：h1 +67.2%、h20 +74.0%（任务书 1.2 内存复算 71.15—76.75% 区间一致）
- D9 合并两成员：h20 +48.0%（44.77—51.30% 一致）
- D5 回头弯：h20 +16.6%（12.21—23.16% 一致）；D2/D3/D4/D6/D8/D10/D11 亦改善（3—28%）
- D1：h20 −3.8%（3.69—3.91% 一致，11 维更差）；D0：h20 −1.2%（绝对差见表）
- 含义：输入补全收益真实且为纯线性基线可比；收益 = 输入契约修复，非算子创新。

## C03：对角成员 —— 本阶段 inner D9 单族单成员（member 诊断表输出）
- fold0 inner D9 只有一个成员族；KC1 主表保持 12 工况合并。成员分表见 baseline json d9_members。

## C04：checkpoint 身份（b43 fold0 best/last，payload.step 验证）
- dim11 best.pt payload_step=500、last.pt payload_step=6000（best_step=500 仅是选择器历史记录）
- dim7 同；best/last 分表 rows 落盘 checkpoint_rows_dim{7,11}_{best,last}.csv
- 旧 JSON（units/b43/kr_b43_*_fold0.json）对应 last 6000（其 per_scenario 与本次 last 行一致）；
  任务书 1.3 的 best/last 相对纯 11 线性对照（+16.4%/−15.4% 等）可用本次 checkpoint_rows 与
  input11_pure 表复算核对。

## C10：数据范围
- control11 派生覆盖全部 672 manifest 行（机械输入构造）；研究评价仅 train/R3（fold fit/inner/outer）；
  派生未参与任何训练/选点；不宣称 val/dev 数值"从未打开"（raw 控制列被机械读取构造缓存）。
"""
(KC1 / "errata.md").write_text(errata, encoding="utf-8")

# update correction checklist statuses
path = KC0 / "correction_checklist.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
status = {
    "C01": ("CLOSED", "pure_linear.py three-way equivalence max 4.1e-15 / E=0 bitwise 0.0 (5 folds)"),
    "C02": ("CLOSED", "input7_vs11_pure_table.csv matches taskbook 1.2 ranges; old tables marked INVALID_BASELINE_REFERENCE in errata"),
    "C03": ("PARTIAL", "member field read from manifest; D9 fold0 inner single member; member metrics in baseline json; full member split at KC3"),
    "C04": ("CLOSED", "checkpoint_identity_dim{7,11}.csv payload_step 500/6000; best/last separated rows"),
    "C05": ("CLOSED", "scenario_metrics_input{7,11}_pure.csv all 12 scenarios x 1/5/10/20 with components"),
    "C06": ("CLOSED", "layered hierarchy window->trajectory->family->scenario in kc1_merge; flat means not used"),
    "C07": ("CLOSED", "main baseline = per-fold pure 11-dim linear; 7-dim only input-repair contrast"),
    "C08": ("CLOSED", "KC run separate from KR run; legacy kr0 BLOCKED preserved (data_scope_audit)"),
    "C09": ("CLOSED", "KC1 audits write to KC run access log only; historical logs untouched (verified)"),
    "C10": ("CLOSED", "data_scope_audit.json honest about full-manifest derivation; research use train/R3 only"),
    "C11": ("OPEN", "strict schema enforcement tests at KC2 (T05)"),
    "C12": ("OPEN", "given-input-sequence conditional wording in report (KC8)"),
    "C13": ("CLOSED", "condition ~1.3e8 reported as regularized-Gram value; not claimed as excluding ill-conditioning"),
    "C14": ("OPEN", "3-seed pilot at KC4"),
    "C15": ("OPEN", "KC2 full test records"),
    "C16": ("CLOSED", "machine-generated times used; clock_audit.json"),
    "C17": ("CLOSED", "KC1 outputs regenerated from raw caches/checkpoints with SHA (input7_vs11_pure_table.csv, checkpoint_rows, scenario_metrics)"),
    "C18": ("OPEN", "lambda used/after accounting at KC4"),
    "C19": ("OPEN", "force/planar yaw separation enforced in metric docs; no material claims"),
    "C20": ("OPEN", "final state split at KC8"),
}
for r in rows:
    if r["id"] in status:
        r["status"], r["evidence_file"] = status[r["id"]]
with open(path, "w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

(KC1 / "complete.json").write_text(json.dumps({
    "stage": "KC1", "status": "PASS",
    "gates": {
        "pure_linear_three_way_equivalence": True,
        "input7_vs_11_pure_table_complete": True,
        "matches_taskbook_ranges": True,
        "checkpoint_identity_verified": True,
        "polluted_reproduction_recorded": True,
        "all_12_scenarios_4_horizons_exported": True,
        "no_training_run": True,
    },
    "summary": "KC1 evidence closure: true fixed-linear baselines (three-way equiv, E=0 bitwise); 11-over-7 gains match the in-memory review ranges; checkpoint best/last identity fixed; errata and correction checklist updated; C01/C02/C04/C05/C06/C07/C08/C09/C10/C13/C16/C17 closed",
}, indent=1), encoding="utf-8")
print("KC1_FINALIZED")

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import universal_v2_modules as m

out = HERE / "universal_v2"
report = out / "final_report.md"
stats = out / "t7_recovery" / "paired_statistics.json"
m.write_json(out / "t9" / "complete_recovery_reaudited.json", {
    "status": "complete",
    "reason": "added preregistered paired external bootstrap and Holm statistics without changing candidates",
    "final_report_sha256": m.uv2.sha256(report),
    "external_statistics_sha256": m.uv2.sha256(stats),
    "gates_sha256": m.uv2.sha256(out / "universality_gates_final.json"),
})
m.uv2.append_log("W0075", "D3最终报告hash复核", [
    "D3 K5 external A的24轨迹配对bootstrap与4骨干Holm校正通过；K5 A1-2s均值改善10.19%，95% CI 9.39%–11.03%。",
    "K0/K1/K4统计门不通过；正式部署候选仍为0，跨骨干普适性结论不变。",
    f"更新后final report hash={m.uv2.sha256(report)}；统计hash={m.uv2.sha256(stats)}。",
])

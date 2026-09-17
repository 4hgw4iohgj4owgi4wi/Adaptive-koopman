import csv
from collections import Counter

p = r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_auto_results\runs\20260901_214725_AUTO_PREDICT_AUTO_R04_R01\n5\data_manifest.csv"
rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
print("total_rows=", len(rows))
print("split_values=", dict(Counter(r["split"] for r in rows)))
fam = {(r["split"], r["base_family_id"]) for r in rows}
print("split_family_counts=", dict(Counter(s for s, _ in fam)))
print("columns=", list(rows[0].keys()))

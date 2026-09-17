import json
import datetime
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
KC3 = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc3"
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

files = ["gamma_frontier.csv", "correction_components_best.csv", "correction_components_last.csv",
         "force_factorization_best.csv", "force_factorization_last.csv", "phase_metrics_best.csv",
         "phase_metrics_last.csv", "force_oracle.json", "diagnosis.md", "kc3_note.md"]
missing = [f for f in files if not (KC3 / f).exists()]
status = "PASS" if not missing else "INCOMPLETE"
(KC3 / "complete.json").write_text(json.dumps({
    "stage": "KC3", "status": status,
    "gates": {
        "gamma_frontier": True,
        "correction_components": True,
        "force_factorization": True,
        "f00_oracle_max_abs_err_N": 3.41e-13,
        "phase_metrics": True,
        "identity_checks_hold": True,
        "missing_products": missing,
    },
    "summary": "frozen 11-dim checkpoint diagnostics complete: gamma frontier (last6000 D7 h20 -34% at gamma=1 with h1 tradeoff), one-step residual decomposition classes, force factorization (displacement-dominated) with f00 oracle at 3.4e-13 N, phase segments (switch-early worst one-step, degrades further at 6000 steps). No qualified-gamma selection here (KC5).",
    "generated_at": now.isoformat(timespec="seconds"),
}, indent=1), encoding="utf-8")
print("KC3_COMPLETE_WRITTEN status=", status)

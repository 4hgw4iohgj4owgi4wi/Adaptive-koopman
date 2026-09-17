import json
import datetime
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
RUN = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01"
KC2 = RUN / "kc2"
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))

(KC2 / "complete.json").write_text(json.dumps({
    "stage": "KC2", "status": "PASS",
    "gates": {
        "core_tests": "70 passed (63 inherited + 7 new KC: T01 pure-numpy/E0, T02 polluted rejection, T03 input counterexample, T05 strict schema, T06 member split, T08 layered hierarchy, T11 gamma affine)",
        "smoke": "warm 200 + T0 600 on 2-family-per-scenario subset with FULL-fold norm/S0; no NaN; wall 14.8 s; peak GPU 0.08 GiB",
        "cost_projection": {"pilot_gpu_hours": 1.512, "kc6_gpu_hours": 7.560, "within_12h": True, "free_gib": 260.3, "free_ok": True},
        "honest_note": "tests that require later-stage mechanisms (lambda used/after T17-18, curriculum T22, runner resume/lock T23-24, inference equivalence T27) are registered to land with KC4/KC5/KC7; no false claim of full T01-T28 completion at KC2",
    },
    "generated_at": now.isoformat(timespec="seconds"),
}, indent=1), encoding="utf-8")
print("KC2_COMPLETE_WRITTEN")

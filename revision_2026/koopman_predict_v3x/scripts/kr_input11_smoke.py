"""11-dim vertical slice smoke (input protocol B.4 step 1-2 prep):
fold0 fit normalization(control11) + S0 fit (59-wide gram) + model construction
+ one rollout forward on control11 windows.  Read-only; writes nothing except a
small verification json under the run's units dir.
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3U = REV / "koopman_predict_v3u"
sys.path[:0] = [str(V3U / "src"), str(V3U / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, fit_normalization, fit_s0, new_model  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"


def main():
    protocol = read_json(V3U / "config" / "protocol_v3t.json")
    entries = rows(REV / N5 / "data_manifest.csv")
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    # point entries at the control11 caches (same filenames)
    for e in entries:
        e["cache_path"] = str(CACHE11 / Path(e["cache_path"]).name)
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KR_INPUT11_SMOKE")
    fold = 0
    fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
    fit_entries = [e for e in entries if e["trajectory_id"] in fit_ids]
    torch.set_num_threads(1)
    norm = fit_normalization(fit_entries, guard, fold, input_dim=11)
    assert "control11_mean" in norm and norm["control11_mean"].shape[0] == 11
    # control11 first 7 norm columns must equal control7 norm from a 7-dim fit (sanity)
    s0 = fit_s0(fit_entries, norm, guard, fold)
    coeff = s0["coefficients"]
    print("coeff_shape=", coeff.shape, "condition=", float(s0["condition_number"]))
    assert coeff.shape == (59, 47), coeff.shape
    model = new_model(coeff, 990100, input_dim=11).double()
    print("input_schema=", model.input_schema, "B0=", tuple(model.B0.shape), "G=", tuple(model.G.shape))
    assert model.B0.shape == (47, 11) and model.G.shape == (16, 11)
    # one forward from the first fit trajectory cache (through the access guard)
    e = fit_entries[0]
    cache = guard.load(e, fold, "S0")
    rel = np.asarray(cache["relative_state47"], dtype=np.float64)
    u = np.asarray(cache["control11"], dtype=np.float64)
    x0 = torch.as_tensor((rel[0] - norm["relative_state47_mean"]) / norm["relative_state47_scale"], dtype=torch.float64)[None]
    u_seq = torch.as_tensor((u[0:20] - norm["control11_mean"]) / norm["control11_scale"], dtype=torch.float64)[None]
    with torch.no_grad():
        out = model.rollout(x0, u_seq, (1, 5, 20))
    pred = out["xhat"]
    assert pred.shape == (1, 20, 47) and torch.isfinite(pred).all()
    report = {
        "input_dim": 11, "fold": fold, "fit_families": len({e2["base_family_id"] for e2 in fit_entries}),
        "norm_control11": True, "coeff_shape": list(coeff.shape), "condition_number": float(s0["condition_number"]),
        "model_input_schema": model.input_schema, "B0_shape": list(model.B0.shape), "G_shape": list(model.G.shape),
        "rollout_finite": True, "rollout_shape": list(pred.shape),
        "first_trajectory": e["trajectory_id"],
        "note": "11-dim vertical slice OK: normalization/S0/model/rollout all use control11",
    }
    out_dir = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "kr_input11_smoke.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("INPUT11_SMOKE_OK")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

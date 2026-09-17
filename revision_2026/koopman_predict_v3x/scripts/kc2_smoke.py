"""KC2 engineering smoke on v3v: fold0, two fit families per scenario for
training, but normalization/S0 from the FULL fold0 fit (as required).  warm 200
(seed 996900) + T0 600 steps to exercise the training pipeline only (no method
selection).  Reports wall time, peak GPU, disk and a 12 h / 60 GiB projection.
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402
from guard_training import train_phase  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc2"


def main():
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    protocol = read_json(V3V / "config" / "protocol_v3s.json")
    frozen = __import__("frozen", fromlist=["FrozenN6"]).FrozenN6(REV.parent, protocol)
    dec = Decoder(frozen.build_planar_grasp_matrix)
    resolver = lambda e: frozen.resolved_params(int(e["seed"]), protocol)  # noqa: E731
    entries = rows(REV / N5 / "data_manifest.csv")
    for e in entries:
        e["cache_path"] = str(CACHE11 / Path(e["cache_path"]).name)
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC2_SMOKE")
    fold = 0
    fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
    inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
    all_fit = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    # full-fit normalization and S0 (mandatory)
    norm = fit_normalization(all_fit, guard, fold, input_dim=11)
    s0 = fit_s0(all_fit, norm, guard, fold)
    # smoke training subset: two families per scenario by family id order
    fams = {}
    for e in all_fit:
        fams.setdefault(e["scenario"], []).append(e)
    smoke_ids = set()
    for sc, es in sorted(fams.items()):
        for e in sorted(es, key=lambda x: x["base_family_id"])[:2]:
            smoke_ids.add(e["trajectory_id"])
    smoke_fit = [e for e in all_fit if e["trajectory_id"] in smoke_ids]
    fit = WindowData(smoke_fit, norm, guard, fold, "optimize", resolver, dec, "cuda")
    inner = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    model = new_model(s0["coefficients"], 996900, input_dim=11).cuda()
    anchor = __import__("copy").deepcopy(model)
    with torch.no_grad():
        anchor.E.zero_()
    af, _ = evaluate(anchor.double(), fit)
    ai, _ = evaluate(anchor.double(), inner)
    del anchor
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    identity = dict(fold=0, phase="kc2_smoke", input_dim=11)
    warm = train_phase(model, fit, inner, af, ai, "warm", 996900, identity, OUT / "warm",
                       max_steps=200, min_steps=200, patience=200, monitor_every=100)
    state = __import__("copy").deepcopy(model.state_dict())
    t0 = train_phase(model, fit, inner, af, ai, "T0", 996900 + 50000, identity, OUT / "t0",
                     max_steps=600, min_steps=600, patience=601, monitor_every=100)
    wall = time.perf_counter() - started
    peak_gb = torch.cuda.max_memory_allocated() / 2**30
    free_gib = shutil.disk_usage(REV).free / 2**30
    # projection: KC4 pilot = 3 warm(2000) + 9 phase(6000) on full fold0 fit; KC6 = 15 warm + 45/60 phase on 5 folds
    step_s = max(warm["elapsed_s"] / 200, t0["elapsed_s"] / 600)
    full_fit_windows = len(WindowData(all_fit, norm, guard, fold, "fit_monitor", resolver, dec, "cuda").meta)
    smoke_windows = len(fit.meta)
    monitor_scale = full_fit_windows / max(smoke_windows, 1)
    # rough monitor cost per 500 steps from the smoke curve
    monitor_s = max((c.get("monitor_s", 0.0) for c in warm["curve"] + t0["curve"]), default=0.0) * monitor_scale
    formal_steps = 3 * 2000 + 9 * 6000
    formal_s = formal_steps * step_s * monitor_scale  # full fit is heavier; scale by window ratio
    monitor_total = (formal_steps / 500) * monitor_s
    pilot_hours = (formal_s + monitor_total) / 3600
    # KC6 = 5 folds x 3 repeats = 15 warm + 45 phase = 5 x the pilot unit set (fold0 x 3 seeds)
    kc6_hours = pilot_hours * 5.0
    report = {
        "stage": "KC2_SMOKE",
        "warm_steps": warm["step"], "t0_steps": t0["step"],
        "smoke_fit_windows": smoke_windows, "full_fit_windows": full_fit_windows,
        "wall_s": wall, "peak_gpu_gib": peak_gb, "free_gib": free_gib,
        "step_s": step_s, "monitor_s_per_500": monitor_s,
        "projected_pilot_gpu_hours": pilot_hours,
        "projected_kc6_gpu_hours": kc6_hours,
        "within_12h": pilot_hours <= 12 and kc6_hours <= 12,
        "free_ok": free_gib - 5 >= 60,
        "status": "PASS" if (pilot_hours <= 12 and kc6_hours <= 12 and free_gib - 5 >= 60) else "COST_BLOCKED",
    }
    (OUT / "smoke_cost.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    print("KC2_SMOKE_DONE status=", report["status"])


if __name__ == "__main__":
    main()

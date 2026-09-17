"""B.4-3: residual-structure 7-dim vs 11-dim, same budget (fold0, T0 objective).
One dimension per process (single AccessGuard).  warm 2000 (seed 994100) then
T0 phase 6000 (seed 1044900), no early stop; reports inner D7/D9A/D0/D1/D5.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3U = REV / "koopman_predict_v3u"
sys.path[:0] = [str(V3U / "src"), str(V3U / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402
from guard_training import train_phase  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE7 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "cache"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units" / "b43"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, required=True, choices=(7, 11))
    args = ap.parse_args()
    dim = args.dim
    torch.set_num_threads(1)
    protocol = read_json(V3U / "config" / "protocol_v3s.json")
    frozen = __import__("frozen", fromlist=["FrozenN6"]).FrozenN6(REV.parent, protocol)
    dec = Decoder(frozen.build_planar_grasp_matrix)
    resolver = lambda e: frozen.resolved_params(int(e["seed"]), protocol)  # noqa: E731
    cache_dir = CACHE11 if dim == 11 else CACHE7
    entries = rows(REV / N5 / "data_manifest.csv")
    for e in entries:
        e["cache_path"] = str(cache_dir / Path(e["cache_path"]).name)
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    fold = 0
    fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
    inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", f"KR_B43_D{dim}")
    norm = fit_normalization(fite, guard, fold, input_dim=dim)
    s0 = fit_s0(fite, norm, guard, fold)
    fit = WindowData(fite, norm, guard, fold, "optimize", resolver, dec, "cuda")
    inner = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    # anchor (E=0 linear)
    model = new_model(s0["coefficients"], 994100, input_dim=dim).cuda()
    anchor = __import__("copy").deepcopy(model)
    with torch.no_grad():
        anchor.E.zero_()
    anchor_fit, _ = evaluate(anchor.double(), fit)
    anchor_inner, _ = evaluate(anchor.double(), inner)
    del anchor
    identity = dict(fold=fold, phase="b43", input_dim=dim, code="u11" if dim == 11 else "u7")
    warm = train_phase(model, fit, inner, anchor_fit, anchor_inner, "warm", 994100, identity,
                       OUT / f"dim{dim}_warm", max_steps=2000, min_steps=2000, patience=2000, monitor_every=500)
    state = __import__("copy").deepcopy(model.state_dict())
    t0 = train_phase(model, fit, inner, anchor_fit, anchor_inner, "T0", 1044900, identity,
                     OUT / f"dim{dim}_t0", max_steps=6000, min_steps=6000, patience=6001, monitor_every=500)
    with torch.no_grad():
        stats, errors = evaluate(model.double(), inner)
    e = errors.cpu().numpy()
    meta = inner.meta
    scen = np.asarray([m["scenario"] for m in meta])
    h1 = e[:, 0, 0]
    h20 = e[:, 3, 0]
    per = {}
    for s, label in ((7, "D7"), (9, "D9A"), (0, "D0"), (5, "D5"), (1, "D1")):
        mask = scen == s
        if mask.any():
            per[label] = {"n": int(mask.sum()), "h1_mean": float(h1[mask].mean()), "h20_mean": float(h20[mask].mean())}
    report = {"dim": dim, "fold": 0, "method": "T0", "warm_steps": warm["step"], "phase_steps": t0["step"],
              "best_step": t0["best_step"], "status": t0["status"], "per_scenario": per}
    (OUT / f"kr_b43_dim{dim}_fold0.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"B43_DIM{dim}_DONE warm={warm['step']} phase={t0['step']} best={t0['best_step']} " +
          " ".join(f"{k}: h1={v['h1_mean']:.5f} h20={v['h20_mean']:.5f}" for k, v in per.items()))


if __name__ == "__main__":
    main()

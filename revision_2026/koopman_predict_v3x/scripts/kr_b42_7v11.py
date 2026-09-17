"""B.4-2: fixed-linear 7-dim vs 11-dim comparison, ONE dimension per process
(single AccessGuard).  Run with --dim 7 and --dim 11; merge outputs later."""
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

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE7 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "cache"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"


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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", f"KR_B42_D{dim}")
    per_fold = {}
    for fold in range(5):
        fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
        inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
        fite = [e for e in entries if e["trajectory_id"] in fit_ids]
        inne = [e for e in entries if e["trajectory_id"] in inner_ids]
        norm = fit_normalization(fite, guard, fold, input_dim=dim)
        s0 = fit_s0(fite, norm, guard, fold)
        model = new_model(s0["coefficients"], 990100 + fold, input_dim=dim).double().cuda()
        data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
        with torch.no_grad():
            stats, errors = evaluate(model, data)
        e = errors.cpu().numpy()
        meta = data.meta
        scen = np.asarray([m["scenario"] for m in meta])
        h1 = e[:, 0, 0]
        h20 = e[:, 3, 0]
        per = {}
        for s, label in ((7, "D7"), (9, "D9A"), (0, "D0"), (5, "D5"), (1, "D1")):
            mask = scen == s
            if mask.any():
                per[label] = {"n": int(mask.sum()), "h1_mean": float(h1[mask].mean()), "h20_mean": float(h20[mask].mean())}
        per_fold[fold] = {"condition_number": float(s0["condition_number"]), "per_scenario": per}
        print(f"fold{fold} dim{dim}: " + " ".join(f"{k}: h1={v['h1_mean']:.5f} h20={v['h20_mean']:.5f}" for k, v in per.items()))
    report = {"dim": dim, "per_fold": per_fold}
    out = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"kr_b42_dim{dim}_allfolds.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"DIM{dim}_ALLFOLDS_DONE")


if __name__ == "__main__":
    main()

"""KC1: true fixed-linear input baselines (7 vs 11) + polluted-path reproduction.

Replaces the v3u kr_b42 path whose 'fixed linear' model actually carried a
random residual E (C01/C02).  Three-way equivalence: direct NumPy recursion,
PureLinearKoopman, and an E=0 copy of the residual model.  Evaluates inner
windows at 1/5/10/20 with layered hierarchy, all 12 scenarios, per member.

Usage: --dim {7,11} [--mode pure|polluted] [--folds 0..4]
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402
from pure_linear import PureLinearKoopman, numpy_linear_rollout  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE7 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "cache"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc1"
HORIZONS = (1, 5, 10, 20)
SCEN_NAMES = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11"]


def hierarchy_mean_from_errors(errors, meta):
    """Layered window->trajectory->family->scenario mean per horizon/component."""
    from guard_core import hierarchy_mean

    return hierarchy_mean(errors, meta)


def evaluate_pure(model, data, batch=256):
    """Evaluate a PureLinearKoopman (no nn.Module surface) over all windows."""
    parts = []
    with torch.no_grad():
        for start in range(0, len(data.meta), batch):
            ix = np.arange(start, min(start + batch, len(data.meta)))
            errors, _, _ = data.errors(model, ix, smooth=False, dtype=torch.float64)
            parts.append(errors)
    return torch.cat(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, required=True, choices=(7, 11))
    ap.add_argument("--mode", default="pure", choices=("pure", "polluted"))
    ap.add_argument("--folds", default="0,1,2,3,4")
    args = ap.parse_args()
    dim = args.dim
    torch.set_num_threads(1)
    protocol = read_json(V3V / "config" / "protocol_v3s.json")
    frozen = __import__("frozen", fromlist=["FrozenN6"]).FrozenN6(REV.parent, protocol)
    dec = Decoder(frozen.build_planar_grasp_matrix)
    resolver = lambda e: frozen.resolved_params(int(e["seed"]), protocol)  # noqa: E731
    cache_dir = CACHE11 if dim == 11 else CACHE7
    entries = rows(REV / N5 / "data_manifest.csv")
    for e in entries:
        e["cache_path"] = str(cache_dir / Path(e["cache_path"]).name)
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", f"KC1_{args.mode}_D{dim}")
    per_fold = {}
    for fold in [int(f) for f in args.folds.split(",")]:
        fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
        inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
        fite = [e for e in entries if e["trajectory_id"] in fit_ids]
        inne = [e for e in entries if e["trajectory_id"] in inner_ids]
        norm = fit_normalization(fite, guard, fold, input_dim=dim)
        s0 = fit_s0(fite, norm, guard, fold)
        coeff = s0["coefficients"]
        if args.mode == "pure":
            model = PureLinearKoopman(coeff[:47].T, coeff[47:47 + dim].T, coeff[47 + dim], dim)
        else:
            # BUG_REPRODUCTION: the historical 'fixed linear' path kept the random E
            model = new_model(coeff, 990100 + fold, input_dim=dim)
            model = model.double().cuda()
        # three-way equivalence check on the first fit window (pure mode)
        eq = {}
        if args.mode == "pure":
            e0 = fite[0]
            cache = guard.load(e0, fold, "S0")
            rel = np.asarray(cache["relative_state47"], dtype=np.float64)
            ukey = "control11" if dim == 11 else "control7"
            u = np.asarray(cache[ukey], dtype=np.float64)
            x0_n = (rel[0] - norm["relative_state47_mean"]) / norm["relative_state47_scale"]
            u_n = (u[0:20] - norm[f"{ukey}_mean"]) / norm[f"{ukey}_scale"]
            x0t = torch.as_tensor(x0_n, dtype=torch.float64)[None].cuda()
            ut = torch.as_tensor(u_n, dtype=torch.float64)[None].cuda()
            with torch.no_grad():
                pure_out = model.rollout(x0t, ut, HORIZONS)["xhat"][0].cpu().numpy()
            # numpy path on the same normalized inputs
            np_out = numpy_linear_rollout(coeff[:47].T, coeff[47:47 + dim].T, coeff[47 + dim],
                                          x0_n, u_n, 20)
            # residual E=0 copy path
            rm = new_model(coeff, 990100 + fold, input_dim=dim).double().cuda()
            with torch.no_grad():
                rm.E.zero_()
                res_out = rm.rollout(x0t, ut, HORIZONS)["xhat"][0].cpu().numpy()
            eq = {
                "pure_vs_numpy_max_abs": float(np.max(np.abs(pure_out - np_out))),
                "pure_vs_e0_max_abs": float(np.max(np.abs(pure_out - res_out))),
            }
        data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
        with torch.no_grad():
            if args.mode == "pure":
                errors = evaluate_pure(model, data)
                stats = hierarchy_mean_from_errors(errors, data.meta)
            else:
                stats, errors = evaluate(model, data)
        e = errors.cpu().numpy()
        meta = data.meta
        scen = np.asarray([m["scenario"] for m in meta])
        member = np.asarray([m.get("member", "none") for m in meta])
        rows_out = []
        for s in range(12):
            mask = scen == s
            if not mask.any():
                rows_out.append({"fold": fold, "scenario": SCEN_NAMES[s], "n_windows": 0})
                continue
            for hi, h in enumerate(HORIZONS):
                vals = e[mask, hi, :]  # (n, 6 comps)
                rows_out.append({
                    "fold": fold, "scenario": SCEN_NAMES[s], "horizon": h,
                    "n_windows": int(mask.sum()),
                    "j_common": float(vals[:, 0].mean()),
                    "e_core": float(vals[:, 1].mean()),
                    "e_relative": float(vals[:, 2].mean()),
                    "e_force": float(vals[:, 3].mean()),
                    "e_internal": float(vals[:, 4].mean()),
                    "e_yaw": float(vals[:, 5].mean()),
                })
        # member breakdown for D9 (diagonal)
        d9 = {}
        for mem in ("A", "B"):
            mm = (scen == 9) & (member == mem)
            if mm.any():
                d9[mem] = {"n": int(mm.sum()), "h1": float(e[mm, 0, 0].mean()), "h20": float(e[mm, 3, 0].mean())}
        per_fold[fold] = {"rows": rows_out, "equivalence": eq, "condition": float(s0["condition_number"]), "d9_members": d9}
        print(f"fold{fold} dim{dim} {args.mode}: eq={eq}")
    tag = f"input{dim}_{args.mode}"
    with open(OUT / f"scenario_metrics_{tag}.csv", "w", newline="", encoding="utf-8") as fh:
        flat = [r for f in per_fold.values() for r in f["rows"]]
        writer = csv.DictWriter(fh, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)
    (OUT / f"baseline_{tag}.json").write_text(json.dumps({
        "dim": dim, "mode": args.mode, "per_fold": {
            str(k): {"equivalence": v["equivalence"], "condition": v["condition"], "d9_members": v["d9_members"]}
            for k, v in per_fold.items()
        },
        "note": "polluted mode = historical path reproduction with random residual E (BUG_REPRODUCTION, not a baseline)",
    }, indent=1), encoding="utf-8")
    print(f"KC1_{tag}_DONE")


if __name__ == "__main__":
    main()

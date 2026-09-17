"""KC4 summary: load the 9 pilot runs, evaluate best.pt on fit/inner, extract
curve stats (55-constraint violations, lambda used/after, dual updates) and
write pilot_table.csv for KC5 nomination preparation.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, constraints, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
KC4 = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc4"
METHODS = ("aligned", "fixed_guard", "adaptive_guard")
SEEDS = (996100, 996101, 996102)


def main():
    torch.set_num_threads(1)
    protocol = read_json(V3V / "config" / "protocol_v3s.json")
    frozen = __import__("frozen", fromlist=["FrozenN6"]).FrozenN6(REV.parent, protocol)
    dec = Decoder(frozen.build_planar_grasp_matrix)
    resolver = lambda e: frozen.resolved_params(int(e["seed"]), protocol)  # noqa: E731
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    fold = 0
    fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
    inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
    entries = rows(REV / N5 / "data_manifest.csv")
    for e in entries:
        e["cache_path"] = str(CACHE11 / Path(e["cache_path"]).name)
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC4_SUMMARY")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    fit = WindowData(fite, norm, guard, fold, "fit_monitor", resolver, dec, "cuda")
    inner = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    anchor = new_model(s0["coefficients"], 0, input_dim=11).cuda()
    with torch.no_grad():
        anchor.E.zero_()
    af, _ = evaluate(anchor.double(), fit)
    ai, _ = evaluate(anchor.double(), inner)
    anchor_m20_inner = float(ai[:, 3, 0].mean())
    rows_out = []
    for si, seed in enumerate(SEEDS):
        for method in METHODS:
            run_dir = KC4 / f"seed{si}_{method}"
            best_path = run_dir / "best.pt"
            payload = torch.load(best_path, map_location="cpu", weights_only=False)
            step = int(payload["step"])
            model = new_model(s0["coefficients"], seed, input_dim=11).cuda()
            model.load_state_dict(payload["model"])
            with torch.no_grad():
                fs, _ = evaluate(model.double(), fit)
                ins, _ = evaluate(model.double(), inner)
            g_fit = constraints(fs, af.to(fs))
            g_inner = constraints(ins, ai.to(ins))
            m20_inner = float(ins[:, 3, 0].mean())
            m20_fit = float(fs[:, 3, 0].mean())
            curve = payload["curve"]
            max_pos_fit = max((c.get("fit_g") or [0.0]) for c in curve) if any(c.get("fit_g") for c in curve) else None
            lam_max = max((max(c["lambda_values"]) for c in curve), default=0.0)
            used = int(payload.get("dual_updates", 0))
            rows_out.append({
                "seed": seed, "method": method, "best_step": step,
                "m20_inner": m20_inner, "m20_fit": m20_fit,
                "anchor_m20_inner": anchor_m20_inner,
                "i20_improvement_pct": 100.0 * (anchor_m20_inner - m20_inner) / max(anchor_m20_inner, 1e-12),
                "max_pos_inner_violation": float(g_inner.clamp_min(0).max()),
                "max_pos_fit_violation_last": float(g_fit.clamp_min(0).max()),
                "lambda_max": lam_max, "dual_updates": used,
                "inner_protections_ok": bool(g_inner.clamp_min(0).max() <= 0.0),
            })
            print(f"seed{seed} {method}: best={step} I20={100.0 * (anchor_m20_inner - m20_inner) / max(anchor_m20_inner, 1e-12):+.2f}% maxInnerVio={g_inner.clamp_min(0).max():.4f}")
    with open(KC4 / "pilot_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print("KC4_SUMMARY_DONE anchor_m20_inner=", anchor_m20_inner)


if __name__ == "__main__":
    main()

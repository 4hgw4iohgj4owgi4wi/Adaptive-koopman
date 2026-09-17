"""KC5 curriculum arm: residual_curriculum x 3 seeds (fold0).  Same warm state
as the KC4 pilot (loaded from seedX_warm last.pt), same sampler seeds, total
6000 steps: first 1000 one-step residual MSE, then fixed_guard objective;
optimizer never rebuilt.  Then best/6000 model evaluated on fit/inner.
"""
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, constraints, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402
from guard_training import train_phase  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc4"
SEEDS = (996100, 996101, 996102)


def main():
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC5_CURRICULUM")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    fit = WindowData(fite, norm, guard, fold, "optimize", resolver, dec, "cuda")
    inner = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    anchor = new_model(s0["coefficients"], 0, input_dim=11).cuda()
    with torch.no_grad():
        anchor.E.zero_()
    af, _ = evaluate(anchor.double(), fit)
    ai, _ = evaluate(anchor.double(), inner)
    del anchor
    torch.cuda.empty_cache()
    m20_scale = float(af[:, 3, 0].mean())
    anchor_m20_inner = float(ai[:, 3, 0].mean())
    rows_out = []
    for si, seed in enumerate(SEEDS):
        warm_payload = torch.load(OUT / f"seed{si}_warm" / "last.pt", map_location="cpu", weights_only=False)
        model = new_model(s0["coefficients"], seed, input_dim=11).cuda()
        model.load_state_dict(warm_payload["model"])
        run_dir = OUT / f"seed{si}_residual_curriculum"
        identity = dict(fold=fold, phase="residual_curriculum", input_dim=11, seed=seed, run="KC5")
        result = train_phase(model, fit, inner, af, ai, "residual_curriculum", seed + 50000, identity, run_dir,
                             max_steps=6000, min_steps=6000, patience=6001, monitor_every=500, anchor_scale_m20=m20_scale)
        best_payload = torch.load(run_dir / "best.pt", map_location="cpu", weights_only=False)
        bm = new_model(s0["coefficients"], seed, input_dim=11).cuda()
        bm.load_state_dict(best_payload["model"])
        with torch.no_grad():
            ins, _ = evaluate(bm.double(), inner)
        g_inner = constraints(ins, ai.to(ins))
        m20_inner = float(ins[:, 3, 0].mean())
        rows_out.append({
            "seed": seed, "method": "residual_curriculum", "best_step": int(best_payload["step"]),
            "m20_inner": m20_inner, "anchor_m20_inner": anchor_m20_inner,
            "i20_improvement_pct": 100.0 * (anchor_m20_inner - m20_inner) / max(anchor_m20_inner, 1e-12),
            "max_pos_inner_violation": float(g_inner.clamp_min(0).max()),
            "inner_protections_ok": bool(g_inner.clamp_min(0).max() <= 0.0),
        })
        print(f"curriculum seed{seed}: best={int(best_payload['step'])} I20={rows_out[-1]['i20_improvement_pct']:+.2f}% maxVio={rows_out[-1]['max_pos_inner_violation']:.4f}", flush=True)
    (OUT / "curriculum_table.csv").write_text(
        "seed,method,best_step,m20_inner,anchor_m20_inner,i20_improvement_pct,max_pos_inner_violation,inner_protections_ok\n"
        + "".join(f"{r['seed']},{r['method']},{r['best_step']},{r['m20_inner']},{r['anchor_m20_inner']},{r['i20_improvement_pct']},{r['max_pos_inner_violation']},{r['inner_protections_ok']}\n" for r in rows_out),
        encoding="utf-8")
    print("KC5_CURRICULUM_DONE")


if __name__ == "__main__":
    main()

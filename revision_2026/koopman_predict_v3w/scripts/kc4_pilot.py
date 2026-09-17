"""KC4 pilot: fold0 x 3 seeds x 3 methods (aligned / fixed_guard / adaptive_guard)
on the 11-dim pure-linear common baseline.  Shared warm per seed (2000), phase
6000 with lambda update every 500 for adaptive (on the FULL fit set), no early
stop, monitors every 500 + extra 100/250/750 diagnostic-only checkpoints at the
same 500-multiple selection points.  Unit key stage/fold/repeat/method.
"""
import argparse
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
from guard_core import AccessGuard, Decoder, WindowData, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402
from guard_training import train_phase  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc4"
METHODS = ("aligned", "fixed_guard", "adaptive_guard")
SEEDS = (996100, 996101, 996102)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-idx", type=int, default=0, choices=(0, 1, 2))
    ap.add_argument("--quick", action="store_true", help="600-step sanity run (dev only)")
    args = ap.parse_args()
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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC4_PILOT")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    fit = WindowData(fite, norm, guard, fold, "optimize", resolver, dec, "cuda")
    inner = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    seed = SEEDS[args.seed_idx]
    phase_steps = 600 if args.quick else 6000
    warm_steps = 200 if args.quick else 2000
    report = {"fold": fold, "seed": seed, "methods": {}}
    for mi, method in enumerate(METHODS):
        run_dir = OUT / f"seed{args.seed_idx}_{method}"
        # fresh model per method but same warm state (warm trained once per seed)
        warm_dir = OUT / f"seed{args.seed_idx}_warm"
        if mi == 0:
            model = new_model(s0["coefficients"], seed, input_dim=11).cuda()
            anchor = copy.deepcopy(model)
            with torch.no_grad():
                anchor.E.zero_()
            af, _ = evaluate(anchor.double(), fit)
            ai, _ = evaluate(anchor.double(), inner)
            del anchor
            torch.cuda.empty_cache()
            identity = dict(fold=fold, phase="warm", input_dim=11, seed=seed, run="KC4")
            train_phase(model, fit, inner, af, ai, "warm", seed, identity, warm_dir,
                        max_steps=warm_steps, min_steps=warm_steps, patience=warm_steps + 1, monitor_every=500)
            warm_state = copy.deepcopy(model.state_dict())
            m20_scale = float(af[:, 3, 0].mean())
        else:
            model = new_model(s0["coefficients"], seed, input_dim=11).cuda()
            model.load_state_dict(warm_state)
        identity = dict(fold=fold, phase=method, input_dim=11, seed=seed, run="KC4")
        t0 = time.perf_counter()
        result = train_phase(model, fit, inner, af, ai, method, seed + 50000, identity, run_dir,
                             max_steps=phase_steps, min_steps=phase_steps, patience=phase_steps + 1,
                             monitor_every=500, anchor_scale_m20=m20_scale)
        report["methods"][method] = {
            "step": result["step"], "best_step": result["best_step"], "wall_s": time.perf_counter() - t0,
            "dual_updates": result.get("dual_updates", 0), "status": result["status"],
        }
        print(f"{method} done: step={result['step']} best={result['best_step']} dual_updates={result.get('dual_updates')} wall={result['elapsed_s']:.1f}s", flush=True)
    (OUT / f"pilot_seed{args.seed_idx}_summary.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("KC4_PILOT_SEED_DONE")


if __name__ == "__main__":
    main()

"""KC5 precheck: curriculum trigger condition and protection-failure breakdown.

Nomination requires >=2/3 seeds with inner protections (55) + I20>=5% all pass.
Curriculum trigger (only if no nomination): fixed_guard has >=2/3 seeds with a
one-step protection failure on the FULL FIT set at each of the last three
500-step monitors.
"""
import json
import sys
from pathlib import Path

import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
KC4 = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc4"
METHODS = ("aligned", "fixed_guard", "adaptive_guard")

# constraint layout from guard_core.constraints:
# short(3): global h1/h5/h10; scenario(48): 12 x 4 horizons; physical(4): force/int h1,h20
# one-step protections = global short[0] + scenario h1 entries (indexes 3+0..3+11) + physical[0],[2]


def one_step_failures(g):
    """Return True if any one-step protection violated (g>0)."""
    if g is None:
        return None
    import numpy as np

    g = np.asarray(g, dtype=float)
    short = g[:3]
    scen = g[3:51].reshape(12, 4)
    phys = g[51:]
    h1_sel = [short[0]] + list(scen[:, 0]) + [phys[0], phys[2]]
    return max(h1_sel) > 0.0, float(max(h1_sel))


def main():
    out = {}
    for method in METHODS:
        per_seed = {}
        for si in range(3):
            run_dir = KC4 / f"seed{si}_{method}"
            payload = torch.load(run_dir / "last.pt", map_location="cpu", weights_only=False)
            curve = payload["curve"]
            # last three 500-step monitors with fit_g
            fit_pts = [c for c in curve if c.get("fit_g") is not None]
            last3 = fit_pts[-3:]
            fails = []
            for c in last3:
                ok, val = one_step_failures(c["fit_g"])
                fails.append(bool(ok))
            per_seed[si] = {"steps": [c["step"] for c in last3], "one_step_fit_fail": fails,
                            "n_fit_pts": len(fit_pts), "dual_updates": payload.get("dual_updates", 0)}
        out[method] = per_seed
    # summary
    fg = out["fixed_guard"]
    trigger_seeds = sum(1 for si in fg if len(fg[si]["one_step_fit_fail"]) == 3 and all(fg[si]["one_step_fit_fail"]))
    print("curriculum trigger condition: fixed_guard one-step fit failure on last 3 monitors")
    for method in METHODS:
        print(method, {si: out[method][si]["one_step_fit_fail"] for si in range(3)})
    print("fixed_guard seeds satisfying trigger (>=2 needed):", trigger_seeds)
    (KC4 / "kc5_precheck.json").write_text(json.dumps({
        "per_method": out,
        "curriculum_trigger_fixed_guard_seeds": trigger_seeds,
        "trigger_met": trigger_seeds >= 2,
    }, indent=1), encoding="utf-8")
    print("KC5_PRECHECK_DONE")


if __name__ == "__main__":
    main()

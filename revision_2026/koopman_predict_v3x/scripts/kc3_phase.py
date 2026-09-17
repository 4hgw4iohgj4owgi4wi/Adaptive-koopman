"""KC3 phase diagnostics: one-step error by raw command phase segments for the
focus scenarios D7/D9A on the fold0 11-dim best/last checkpoints.

Segments (fixed, from raw command_phase transitions): switch-early 0-0.2 s
after a request-phase change, switch-late 0.2-0.6 s, sustained/recovery.
Prediction starts are labelled by the phase at the start row; a secondary flag
notes whether the 20-step interval crosses a later switch (diagnostic only).
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
from guard_core import AccessGuard, Decoder, WindowData, fit_normalization, fit_s0, new_model  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
B43 = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units" / "b43"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc3"
DT = 0.02


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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_PHASE")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    # phase per inner window from the raw command_phase of its trajectory (raw npz);
    # the existing guard already registers raw_paths, so open raw inside its context
    import numpy as np

    raw_by_traj = {}
    for e in inne:
        if int(e["scenario"][1:]) not in (7, 9):
            continue
        with guard.context(fold, "monitor"):
            with np.load(Path(e["raw_path"]), allow_pickle=False) as z:
                raw_by_traj[str(e["trajectory_id"])] = {k: z[k] for k in z.files}
    scen = np.asarray([m["scenario"] for m in data.meta])
    OUT.mkdir(parents=True, exist_ok=True)
    for kind in ("best", "last"):
        path = B43 / "dim11_t0" / f"{kind}.pt"
        payload = torch.load(path, map_location="cpu", weights_only=False)
        step = int(payload["step"])
        model = new_model(s0["coefficients"], 990100, input_dim=11).cuda()
        model.load_state_dict(payload["model"])
        model = model.double().eval()
        with torch.no_grad():
            pred = model.rollout(data.x.to(torch.float64), data.u.to(torch.float64), (1,))["xhat"][:, 0]
        err1 = torch.sqrt(torch.mean((pred - data.y[:, 0]) ** 2, dim=1)).cpu().numpy()
        rows_out = []
        for i, m in enumerate(data.meta):
            if int(m["scenario"]) not in (7, 9):
                continue
            cache = raw_by_traj.get(m["trajectory"])
            if cache is None or "command_phase" not in cache:
                continue
            ph = np.asarray(cache["command_phase"]).astype(str)
            start = int(m["start"])
            if start >= len(ph):
                continue
            # segment label: distance (in steps) from the most recent phase change
            changed = [k for k in range(1, len(ph)) if ph[k] != ph[k - 1]]
            seg = "sustained_or_recovery"
            since = None
            recent = [k for k in changed if k <= start]
            if recent:
                since = start - recent[-1]
                if since <= 10:
                    seg = "switch_early"
                elif since <= 30:
                    seg = "switch_late"
            future_changes = sum(1 for k in changed if start < k <= start + 20)
            rows_out.append({
                "checkpoint": kind, "payload_step": step,
                "scenario": m["scenario"], "member": m.get("member", "none"),
                "trajectory": m["trajectory"], "start": start,
                "phase_at_start": ph[start], "segment": seg,
                "steps_since_change": since if since is not None else -1,
                "crosses_future_switch": future_changes > 0,
                "h1_state_rmse": float(err1[i]),
            })
        with open(OUT / f"phase_metrics_{kind}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            w.writeheader()
            w.writerows(rows_out)
        agg = {}
        for seg in ("switch_early", "switch_late", "sustained_or_recovery"):
            vals = [r["h1_state_rmse"] for r in rows_out if r["segment"] == seg]
            if vals:
                agg[seg] = {"n": len(vals), "mean": float(np.mean(vals))}
        print(f"{kind} step{step} segment counts={ {s: sum(1 for r in rows_out if r['segment'] == s) for s in ('switch_early', 'switch_late', 'sustained_or_recovery')} }")
        print(f"  segment mean h1 rmse: { {k: round(v['mean'], 5) for k, v in agg.items()} }")
    print("KC3_PHASE_DONE")


if __name__ == "__main__":
    main()

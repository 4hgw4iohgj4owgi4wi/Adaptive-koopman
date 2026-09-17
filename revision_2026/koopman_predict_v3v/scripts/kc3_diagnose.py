"""KC3: frozen 11-dim checkpoint diagnostics (fold0, b43 best500/last6000).

- Gamma frontier: E -> gamma*E on copies (never the saved weights), evaluate
  inner at gamma in {0,.25,.5,.75,1}, 12 scenarios x 1/5/10/20 j_common.
- One-step residual decomposition: r = x_{k+1} - bar_x1 (pure linear), d = E eta0;
  Delta_1 = d'Omega d - 2 r'Omega d with per-window classification
  (unfavorable direction / over-correction / improvement / near-zero).
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
from pure_linear import PureLinearKoopman  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
B43 = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units" / "b43"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc3"

# Omega diagonal: fixed group weights on the 47 normalized states (refine 3.2)
OMEGA = np.zeros(47)
OMEGA[0:3] = 0.30 / 3
OMEGA[3:19] = 0.20 / 16
OMEGA[19:31] = 0.20 / 12
OMEGA[31:47] = 0.30 / 16


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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_DIAG")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    coeff = s0["coefficients"]
    pure = PureLinearKoopman(coeff[:47].T, coeff[47:58].T, coeff[58], 11)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    OUT.mkdir(parents=True, exist_ok=True)
    x = data.x.cpu().numpy()
    u = data.u.cpu().numpy()
    y = data.y.cpu().numpy()
    # pure linear one-step and 20-step references (numpy, batched)
    def linear_roll(x0_b, u_b, h):
        out = [x0_b]
        x = x0_b.copy()
        for t in range(h):
            x = x @ coeff[:47] + u_b[:, t] @ coeff[47:58] + coeff[58]
            out.append(x)
        return out

    pure1 = linear_roll(x, u, 1)[1]  # (N,47) one-step linear prediction
    gamma_rows = []
    for kind in ("best", "last"):
        path = B43 / "dim11_t0" / f"{kind}.pt"
        payload = torch.load(path, map_location="cpu", weights_only=False)
        step = int(payload["step"])
        model = new_model(coeff, 990100, input_dim=11).cuda()
        model.load_state_dict(payload["model"])
        model = model.double().eval()
        saved_E = model.E.detach().clone()
        # gamma frontier over inner windows
        for gamma in (0.0, 0.25, 0.5, 0.75, 1.0):
            with torch.no_grad():
                model.E.data.copy_(gamma * saved_E)
                # one-step residual correction d = E eta0 per window
                x0t = torch.as_tensor(x, dtype=torch.float64, device="cuda")
                ut = torch.as_tensor(u, dtype=torch.float64, device="cuda")
                eta0 = model.encoder(x0t, ut[:, 0])
                d = (eta0 @ model.E.T).cpu().numpy()  # (N,47) at gamma=1 scale; gamma applied below
                pred1 = pure1 + gamma * d
                rollout = model.rollout(x0t, ut, (1, 5, 10, 20))["xhat"].cpu().numpy()
            err1 = np.sqrt(np.mean((pred1 - y[:, 0]) ** 2, axis=1))
            err20 = np.sqrt(np.mean((rollout[:, 19] - y[:, 19]) ** 2, axis=1))
            scen = np.asarray([m["scenario"] for m in data.meta])
            for s in range(12):
                mask = scen == s
                if mask.any():
                    gamma_rows.append({
                        "checkpoint": kind, "payload_step": step, "gamma": gamma, "scenario": s,
                        "n": int(mask.sum()),
                        "rmse_h1": float(err1[mask].mean()),
                        "rmse_h20": float(err20[mask].mean()),
                    })
        # one-step residual decomposition at gamma=1 on inner windows
        with torch.no_grad():
            model.E.data.copy_(saved_E)
            x0t = torch.as_tensor(x, dtype=torch.float64, device="cuda")
            ut = torch.as_tensor(u, dtype=torch.float64, device="cuda")
            eta0 = model.encoder(x0t, ut[:, 0])
            d = (eta0 @ model.E.T).cpu().numpy()
        r = y[:, 0] - pure1
        two_rOd = 2.0 * np.sum(r * (OMEGA[None, :] * d), axis=1)
        dOd = np.sum(d * (OMEGA[None, :] * d), axis=1)
        delta1 = dOd - two_rOd
        tau = 1e-12 * np.maximum(1.0, np.maximum(np.abs(dOd), np.abs(two_rOd)))
        cls = np.full(len(x), "near_zero", dtype=object)
        unfav = np.sum(r * (OMEGA[None, :] * d), axis=1) < -tau
        over = (np.sum(r * (OMEGA[None, :] * d), axis=1) > tau) & (delta1 > tau)
        imp = delta1 < -tau
        cls[unfav] = "unfavorable_direction"
        cls[over] = "over_correction"
        cls[imp] = "improvement"
        with open(OUT / f"correction_components_{kind}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["checkpoint", "payload_step", "scenario", "start", "r_norm", "d_norm", "dOd", "2rOd", "delta1", "class"])
            for i, m in enumerate(data.meta):
                w.writerow([kind, step, m["scenario"], m["start"],
                            float(np.sqrt(np.sum(r[i] ** 2))), float(np.sqrt(np.sum(d[i] ** 2))),
                            float(dOd[i]), float(2.0 * np.sum(r[i] * (OMEGA * d[i]))), float(delta1[i]), cls[i]])
        counts = {c: int((cls == c).sum()) for c in ("unfavorable_direction", "over_correction", "improvement", "near_zero")}
        print(f"{kind} step{step}: classes={counts}")
        model.E.data.copy_(saved_E)
    with open(OUT / "gamma_frontier.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(gamma_rows[0].keys()))
        w.writeheader()
        w.writerows(gamma_rows)
    print("KC3_DONE")


if __name__ == "__main__":
    main()

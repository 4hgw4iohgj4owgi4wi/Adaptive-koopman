"""KC3 force factorization (fold0 11-dim best500/last6000, inner windows).

f00 = D(q, v)      true state  -> force   (oracle: must match cache true force)
f10 = D(q_hat, v)  predicted displacement, true velocity
f01 = D(q, v_hat)  true displacement, predicted velocity
f11 = D(q_hat, v_hat)
effects: displacement = f10-f00 ; velocity = f01-f00 ;
interaction = f11-f10-f01+f00 ; total = f11-f00.
State columns 31:47 are 4 points x [dx, dy, vx, vy] in the payload frame.
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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_FORCE")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    OUT.mkdir(parents=True, exist_ok=True)

    def mixed_state(q_src, v_src, q_from_pred, v_from_pred):
        """Build a state whose 31:47 block uses q/v from chosen sources.
        q_src/v_src: (..., 47) normalized states; returns new (..., 47)."""
        out = q_src.clone()
        blk_p = q_from_pred[..., 31:47].reshape(*q_from_pred.shape[:-1], 4, 4)
        blk_t = v_from_pred[..., 31:47].reshape(*v_from_pred.shape[:-1], 4, 4)
        mixed = torch.empty_like(blk_p)
        mixed[..., :2] = blk_p[..., :2]  # displacement from pred
        mixed[..., 2:] = blk_t[..., 2:]  # velocity from true
        out[..., 31:47] = mixed.reshape(*out.shape[:-1], 16)
        return out

    h20 = 19
    with torch.no_grad():
        y20 = data.y[:, h20].to("cuda")          # true normalized state at h=20
        f00, i00 = data.physical(y20, torch.arange(len(data.meta)))
        f00 = f00[:, 0]
        i00 = i00[:, 0]
        true_f = data.force[:, h20].to("cuda")   # cache true force
        true_i = data.internal[:, h20].to("cuda")
        f00_err = torch.max(torch.abs(f00 - true_f))
        i00_err = torch.max(torch.abs(i00 - true_i))
        oracle = {"f00_max_abs_err_N": float(f00_err), "i00_max_abs_err_N": float(i00_err)}
    print("F00_ORACLE max abs err:", oracle)
    for kind in ("best", "last"):
        path = B43 / "dim11_t0" / f"{kind}.pt"
        payload = torch.load(path, map_location="cpu", weights_only=False)
        step = int(payload["step"])
        model = new_model(s0["coefficients"], 990100, input_dim=11).cuda()
        model.load_state_dict(payload["model"])
        model = model.double().eval()
        with torch.no_grad():
            pred20 = model.rollout(data.x.to(torch.float64), data.u.to(torch.float64), (20,))["xhat"][:, h20]
            f11, i11 = data.physical(pred20, torch.arange(len(data.meta)))
            f11 = f11[:, 0]
            i11 = i11[:, 0]
            s10 = mixed_state(data.y[:, h20].to("cuda"), data.y[:, h20].to("cuda"), pred20, data.y[:, h20].to("cuda"))
            s01 = mixed_state(data.y[:, h20].to("cuda"), pred20, data.y[:, h20].to("cuda"), pred20)
            f10, _ = data.physical(s10, torch.arange(len(data.meta)))
            f01, _ = data.physical(s01, torch.arange(len(data.meta)))
            f10 = f10[:, 0]
            f01 = f01[:, 0]
        disp = f10 - f00
        vel = f01 - f00
        inter = f11 - f10 - f01 + f00
        total = f11 - f00
        with open(OUT / f"force_factorization_{kind}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["checkpoint", "payload_step", "scenario", "start",
                        "disp_effect_norm", "vel_effect_norm", "interaction_norm",
                        "total_decode_norm", "f11_minus_f00_norm", "force8_rmse_N", "internal8_rmse_N"])
            scen = np.asarray([m["scenario"] for m in data.meta])
            for i, m in enumerate(data.meta):
                w.writerow([kind, step, m["scenario"], m["start"],
                            float(torch.linalg.vector_norm(disp[i])),
                            float(torch.linalg.vector_norm(vel[i])),
                            float(torch.linalg.vector_norm(inter[i])),
                            float(torch.linalg.vector_norm(total[i])),
                            float(torch.linalg.vector_norm(f11[i] - f00[i])),
                            float(torch.sqrt(torch.mean((f11[i] - true_f[i]) ** 2))),
                            float(torch.sqrt(torch.mean((i11[i] - true_i[i]) ** 2)))])
        # scenario aggregate for D5/D7/D9
        agg = {}
        for s in (5, 7, 9):
            mask = scen == s
            if mask.any():
                agg[f"D{s}"] = {
                    "n": int(mask.sum()),
                    "disp": float(torch.mean(torch.linalg.vector_norm(disp[mask], dim=1))),
                    "vel": float(torch.mean(torch.linalg.vector_norm(vel[mask], dim=1))),
                    "inter": float(torch.mean(torch.linalg.vector_norm(inter[mask], dim=1))),
                    "total": float(torch.mean(torch.linalg.vector_norm(total[mask], dim=1))),
                    "force8_rmse_N": float(torch.mean(torch.sqrt(torch.mean((f11[mask] - true_f[mask]) ** 2, dim=1)))),
                }
        print(f"{kind} step{step} scenario effects: {agg}")
    (OUT / "force_oracle.json").write_text(json.dumps(oracle, indent=1), encoding="utf-8")
    print("KC3_FORCE_DONE")


if __name__ == "__main__":
    main()

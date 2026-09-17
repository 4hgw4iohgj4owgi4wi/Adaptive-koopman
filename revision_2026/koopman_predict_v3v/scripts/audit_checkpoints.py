"""KC1 audit_checkpoints: load existing best/last checkpoints of the KR b43
fold0 residual runs (dim7/dim11), verify payload.step and identity, evaluate
on inner with the SAME norm/S0 used at training, export best/last separated
rows (C04) with checkpoint_kind/step/sha and per-scenario member detail.
No training.  Checkpoint payloads carry identity + norm-free state.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, evaluate, fit_normalization, fit_s0, new_model  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
B43 = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "units" / "b43"
CACHE7 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "cache"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
OUT = REV / "koopman_predict_v3v_results" / "runs" / "20260904_224212_KC_R01" / "kc1"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--dim", type=int, required=True, choices=(7, 11))
    args = ap.parse_args()
    dim = args.dim
    torch.set_num_threads(1)
    protocol = read_json(V3V / "config" / "protocol_v3s.json")
    frozen = __import__("frozen", fromlist=["FrozenN6"]).FrozenN6(REV.parent, protocol)
    dec = Decoder(frozen.build_planar_grasp_matrix)
    resolver = lambda e: frozen.resolved_params(int(e["seed"]), protocol)  # noqa: E731
    fm = rows(KG_RUN / "g0" / "fold_manifest.csv")
    fold = 0
    fit_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "fit"}
    inner_ids = {r["trajectory"] for r in fm if int(r["fold"]) == fold and r["role"] == "inner"}
    identity_rows = []
    cache_dir = CACHE11 if dim == 11 else CACHE7
    entries = rows(REV / N5 / "data_manifest.csv")
    for e in entries:
        e["cache_path"] = str(cache_dir / Path(e["cache_path"]).name)
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", f"KC1_CKPT_D{dim}")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=dim)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    for kind in ("best", "last"):
            path = B43 / f"dim{dim}_t0" / f"{kind}.pt"
            payload = torch.load(path, map_location="cpu", weights_only=False)
            step = int(payload["step"])
            identity_rows.append({
                "dim": dim, "kind": kind, "path": str(path), "sha256": sha256(path),
                "payload_step": step, "payload_best_step": int(payload["best_step"]),
                "model_input_schema": "u11" if dim == 11 else "u7",
                "checkpoint_kind": kind, "checkpoint_step": step,
            })
            model = new_model(s0["coefficients"], 990100 + fold, input_dim=dim)
            model.load_state_dict(payload["model"])
            model = model.double().cuda()
            with torch.no_grad():
                stats, errors = evaluate(model, data)
            e = errors.cpu().numpy()
            meta = data.meta
            scen = np.asarray([m["scenario"] for m in meta])
            with open(OUT / f"checkpoint_rows_dim{dim}_{kind}.csv", "w", newline="", encoding="utf-8") as fh:
                writer = None
                for i, m in enumerate(meta):
                    for hi, h in enumerate((1, 5, 10, 20)):
                        rec = {
                            "dim": dim, "checkpoint_kind": kind, "checkpoint_step": step,
                            "trajectory": m["trajectory"], "family": m["family"],
                            "scenario": m["scenario"], "member": m.get("member", "none"),
                            "start": m["start"], "horizon": h,
                            "j_common": float(e[i, hi, 0]), "e_core": float(e[i, hi, 1]),
                            "e_relative": float(e[i, hi, 2]), "e_force": float(e[i, hi, 3]),
                            "e_internal": float(e[i, hi, 4]), "e_yaw": float(e[i, hi, 5]),
                        }
                        if writer is None:
                            writer = csv.DictWriter(fh, fieldnames=list(rec.keys()))
                            writer.writeheader()
                        writer.writerow(rec)
            # scenario h20 means for the summary
            per = {}
            for s in range(12):
                mask = scen == s
                if mask.any():
                    per[f"D{s}"] = {"n": int(mask.sum()),
                                    "h1": float(e[mask, 0, 0].mean()),
                                    "h20": float(e[mask, 3, 0].mean())}
            print(f"dim{dim} {kind}: payload_step={step} best_step={payload['best_step']} "
                  + " ".join(f"{k}:1={v['h1']:.4f}/20={v['h20']:.4f}" for k, v in per.items() if k in ("D0", "D1", "D5", "D7", "D9")))
    with open(OUT / f"checkpoint_identity_dim{dim}.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(identity_rows[0].keys()))
        writer.writeheader()
        writer.writerows(identity_rows)
    print("KC1_CHECKPOINTS_DONE")


if __name__ == "__main__":
    main()

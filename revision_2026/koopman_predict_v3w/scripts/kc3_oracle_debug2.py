"""KC3 oracle debug 2: inspect top-error windows in detail."""
import sys
from pathlib import Path

import numpy as np
import torch

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3V = REV / "koopman_predict_v3v"
sys.path[:0] = [str(V3V / "src"), str(V3V / "scripts")]
from run_v3t import N5, read_json, rows  # noqa: E402
from guard_core import AccessGuard, Decoder, WindowData, fit_normalization, fit_s0  # noqa: E402

KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
CACHE11 = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"


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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_DBG2")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    with torch.no_grad():
        yh = data.y[:, 19].to("cuda")
        fh, ih = data.physical(yh, torch.arange(len(data.meta)))
        tf = data.force[:, 19].to("cuda")
    d = torch.max(torch.abs(fh - tf), dim=1).values
    top = torch.topk(d, 3).indices.tolist()
    mean = torch.mean(d).item()
    # fraction of windows where the error is 0
    print(f"mean max|err|={mean:.3f} N; zero-error windows fraction={float((d < 1e-6).float().mean()):.3f}")
    for i in top:
        print(f"--- window {i} scenario={data.meta[i]['scenario']} family={data.meta[i]['family']} start={data.meta[i]['start']}")
        print("  f00    =", [round(float(v), 3) for v in fh[i]])
        print("  true   =", [round(float(v), 3) for v in tf[i]])
        print("  diff   =", [round(float(v), 3) for v in (fh[i] - tf[i])])
        # geometry from the true state at h20
        raw = yh[i] * torch.as_tensor(norm["relative_state47_scale"], device="cuda") + torch.as_tensor(norm["relative_state47_mean"], device="cuda")
        blk = raw[31:47].reshape(4, 4)
        dist = torch.linalg.vector_norm(blk[:, :2], dim=1)
        law = data.law_constants[i].to("cuda")
        print(f"  dist(mm)={[round(float(v) * 1000, 2) for v in dist]} free_mm={float(law[0]) * 1000:.2f} k={float(law[2]):.1f} c={float(law[3]):.1f}")


if __name__ == "__main__":
    main()

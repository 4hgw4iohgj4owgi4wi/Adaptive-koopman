"""KC3 oracle debug 3: verify denormalized y equals the raw cache state."""
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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_DBG3")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    # window 0 meta
    m0 = data.meta[0]
    e0 = [e for e in inne if str(e["trajectory_id"]) == m0["trajectory"]][0]
    cache = guard.load(e0, fold, "monitor")
    rel = np.asarray(cache["relative_state47"], dtype=np.float64)
    start = int(m0["start"])
    # denormalize data.y window0 at several horizons
    scale = torch.as_tensor(norm["relative_state47_scale"], dtype=torch.float64)
    mean = torch.as_tensor(norm["relative_state47_mean"], dtype=torch.float64)
    print(f"window0 trajectory={m0['trajectory']} start={start} scenario={m0['scenario']}")
    for hi, h in enumerate((1, 5, 10, 20)):
        raw = (data.y[0, hi].cpu() * scale + mean).numpy()
        cache_row = rel[start + h]
        diff = np.max(np.abs(raw - cache_row))
        print(f"h={h}: max|denorm_y - cache_state| = {diff:.6e}")
        if h == 20:
            print("  31:47 denorm =", np.round(raw[31:47], 6))
            print("  31:47 cache =", np.round(cache_row[31:47], 6))
            # force at start+20 from cache
            cf = np.asarray(cache["force_payload_body8"], dtype=float)
            print("  cache force at start+20 =", np.round(cf[start + 20], 6))
            print("  data.force window0 h20 =", np.round(data.force[0, 19].cpu().numpy(), 6))


if __name__ == "__main__":
    main()

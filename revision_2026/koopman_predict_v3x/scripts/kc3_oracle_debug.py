"""KC3 oracle debug: why does physical(true state) differ from cached force."""
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
    guard = AccessGuard(entries, fm, KG_RUN / "split_access.jsonl", "KC3_DBG")
    fite = [e for e in entries if e["trajectory_id"] in fit_ids]
    inne = [e for e in entries if e["trajectory_id"] in inner_ids]
    norm = fit_normalization(fite, guard, fold, input_dim=11)
    s0 = fit_s0(fite, norm, guard, fold)
    data = WindowData(inne, norm, guard, fold, "monitor", resolver, dec, "cuda")
    with torch.no_grad():
        # h=1 and h=20 true states -> force, vs cached force
        for h in (0, 19):
            yh = data.y[:, h].to("cuda")
            fh, ih = data.physical(yh, torch.arange(len(data.meta)))
            tf = data.force[:, h].to("cuda")
            ti = data.internal[:, h].to("cuda")
            d = torch.max(torch.abs(fh - tf), dim=1).values
            print(f"h={h + 1}: max|f00-force| per window: top5=", torch.topk(d, 5).values.tolist())
            # first window detail
            print("  window0 f00=", fh[0].tolist())
            print("  window0 true=", tf[0].tolist())
            # raw cache force from the source trajectory of window0
            meta0 = data.meta[0]
            e0 = [e for e in inne if str(e["trajectory_id"]) == meta0["trajectory"]][0]
            cache = guard.load(e0, fold, "S0")
            cf = np.asarray(cache["force_payload_body8"], dtype=float)
            start = int(meta0["start"])
            print(f"  window0 start={start} cache force at start+{h + 1}=", cf[start + h + 1].tolist())
            print("  data.force equals cache?", torch.allclose(tf[0].cpu(), torch.as_tensor(cf[start + 1:start + 21][h])))


if __name__ == "__main__":
    main()

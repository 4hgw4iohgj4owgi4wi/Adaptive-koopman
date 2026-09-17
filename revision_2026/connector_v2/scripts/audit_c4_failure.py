from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}

    for case in ("staged_100m_left", "single_lane_change_left", "hairpin_left"):
        pair = {}
        for plant in ("v1", "v2"):
            z = np.load(root / f"{case}_{plant}.npz")
            d = {k: z[k] for k in z.files}
            fmag = np.linalg.norm(d["force"], axis=-1)
            imax = np.unravel_index(int(np.argmax(fmag)), fmag.shape)
            limit_rows = np.flatnonzero(np.any(d["limits"], axis=1))
            entry = {
                "keys": list(z.files),
                "steps": int(len(fmag)),
                "max_force_step": int(imax[0]),
                "max_force_connector": int(imax[1]),
                "max_force_n": float(fmag[imax]),
                "time_at_max_s": float(imax[0] * 0.002),
                "distance_at_max_m": float(d["distance_m"][imax[0]]),
                "penetration_at_max_m": float(d["penetration"][imax]),
                "normal_speed_at_max_mps": float(d["vn"][imax]),
                "active_fraction": float(np.mean(d["active"])),
                "penetration_quantiles_m": [float(x) for x in np.quantile(d["penetration"], [0.5, 0.9, 0.99, 0.999, 1.0])],
                "force_quantiles_n": [float(x) for x in np.quantile(fmag, [0.5, 0.9, 0.99, 0.999, 1.0])],
                "limit_first_step": None if not len(limit_rows) else int(limit_rows[0]),
                "limit_first_time_s": None if not len(limit_rows) else float(limit_rows[0] * 0.002),
                "limit_first_distance_m": None if not len(limit_rows) else float(d["distance_m"][limit_rows[0]]),
            }
            if plant == "v2":
                # The first limit row is the stop row; retain its local diagnostics.
                i = int(limit_rows[0]) if len(limit_rows) else int(imax[0])
                entry["stop_force_by_connector_n"] = [float(x) for x in fmag[i]]
                entry["stop_penetration_by_connector_m"] = [float(x) for x in d["penetration"][i]]
                entry["stop_vn_by_connector_mps"] = [float(x) for x in d["vn"][i]]
                entry["stop_force_payload_body_n"] = [[float(x) for x in row] for row in d["force"][i]]
                entry["stop_wrench_n_nm"] = [float(x) for x in d["wrench"][i]]
                entry["stop_internal_norm_n"] = float(d["internal_norm"][i])
                entry["stop_tire_utilization"] = [float(x) for x in d["tire"][i]]
            pair[plant] = entry
        report[case] = pair

    (out / "c4_failure_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

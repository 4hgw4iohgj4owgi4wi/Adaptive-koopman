from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


QUANTILES = (0.01, 0.05, 0.50, 0.90, 0.95, 0.99, 1.00)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def qmap(values: np.ndarray) -> dict[str, float]:
    return {f"q{int(round(q * 100)):02d}": float(np.quantile(values, q)) for q in QUANTILES}


def main() -> None:
    old_results = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    events_path = old_results / "r0" / "delta_s_events.csv"
    freeze_path = old_results / "r0" / "delta_s_freeze.json"
    manifest_path = old_results / "r0" / "input_manifest.json"
    for path in (events_path, freeze_path, manifest_path):
        if not path.is_file():
            raise SystemExit(f"missing train-only R0 input: {path}")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (not freeze.get("passed") or freeze.get("development_read") or freeze.get("confirm_read")
            or manifest.get("input_split") != "train" or manifest.get("development_read")
            or manifest.get("confirm_read") or int(manifest.get("base_files", -1)) != 256):
        raise SystemExit("R0 provenance is not a passed 256-base train-only freeze")

    delta_s = float(freeze["smoothing_width_m"])
    rows = []
    with events_path.open("r", newline="", encoding="utf-8") as stream:
        for event_id, row in enumerate(csv.DictReader(stream)):
            speed = float(row["vn_on_mps"])
            delta = float(row["delta_on_m"])
            if not np.isfinite(speed) or not np.isfinite(delta) or speed <= 0.0 or delta <= 0.0:
                raise SystemExit(f"invalid event row {event_id}")
            rows.append({
                "trajectory_id": int(row["trajectory_id"]),
                "event_id": event_id,
                "scenario": row["scenario"],
                "connector_id": int(row["connector_id"]),
                "plant_step": int(row["plant_step"]),
                "vn_on_mps": speed,
                "delta_on_m": delta,
                "tau_nominal_s": delta_s / max(speed, np.finfo(float).tiny),
                "in_smoothing_zone_at_first_sample": bool(delta < delta_s),
            })
    if len(rows) != int(freeze["event_count"]):
        raise SystemExit(f"event count changed: {len(rows)} != {freeze['event_count']}")

    speeds = np.asarray([row["vn_on_mps"] for row in rows])
    taus = np.asarray([row["tau_nominal_s"] for row in rows])
    outdir = output / "r0b"
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / "contact_speed_support.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    speed_quantiles = qmap(speeds)
    tau_quantiles = qmap(taus)
    result = {
        "passed": bool(np.all(np.isfinite(speeds)) and np.all(speeds > 0.0)),
        "classification": "post-R2 train-only support audit",
        "event_count": len(rows),
        "independent_train_bases": 256,
        "smoothing_width_m": delta_s,
        "speed_quantiles_mps": speed_quantiles,
        "tau_nominal_quantiles_s": tau_quantiles,
        "support_test_speeds_mps": {
            key: speed_quantiles[key] for key in ("q05", "q50", "q95", "q99")
        },
        "stress_test_speeds_mps": [0.25, 1.0],
        "fraction_first_sample_inside_smoothing_zone": float(np.mean([row["in_smoothing_zone_at_first_sample"] for row in rows])),
        "source_events_path": str(events_path),
        "source_events_sha256": sha256(events_path),
        "source_freeze_sha256": sha256(freeze_path),
        "source_input_manifest_sha256": sha256(manifest_path),
        "output_csv_sha256": sha256(csv_path),
        "development_read": False,
        "confirm_read": False,
    }
    json_path = outdir / "contact_speed_support.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()


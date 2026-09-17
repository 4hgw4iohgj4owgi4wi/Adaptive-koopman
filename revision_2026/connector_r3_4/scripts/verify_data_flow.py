from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_data_flow import build_sample
from four_vehicle_common import ModelParams
from schema_r3 import build_schema


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    checks = {}
    dimensions = {"s1_team": 12, "s2_four": 30, "s3_deform": 46, "s4_force_in": 64, "u8": 8, "y30": 30}
    for law in ("v1", "r3"):
        with np.load(data_dir / f"dataset_{law}_es.npz") as dataset:
            checks[f"{law}_dimensions"] = all(dataset[key].shape[1] == dimension for key, dimension in dimensions.items())
            checks[f"{law}_finite"] = all(np.all(np.isfinite(dataset[key])) for key in dimensions)
            trajectory = dataset["trajectory_id"]
            split = dataset["split"]
            sets = {name: set(trajectory[split == name].tolist()) for name in ("train", "validation", "test")}
            checks[f"{law}_split_disjoint"] = not (sets["train"] & sets["validation"] or sets["train"] & sets["test"] or sets["validation"] & sets["test"])
            checks[f"{law}_time_order"] = bool(np.all(dataset["target_time_s"] > dataset["sample_time_s"]))
    checks["schema_dimensions"] = all(build_schema(name)["dimension"] == dimension for name, dimension in (("S1_team", 12), ("S2_four", 30), ("S3_deform", 46), ("S4_force_in", 64)))
    with (data_dir / "trajectory_manifest.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        manifest = list(csv.DictReader(stream))
    raw_path = Path(manifest[0]["raw_path"])
    with np.load(raw_path) as raw_file:
        raw = {key: raw_file[key].copy() for key in raw_file.files}
    index = min(5, len(raw["time_s"]) - 2)
    before = build_sample(raw, index, ModelParams())["s4_force_in"]
    raw["force_interval_mean_body_n"][index + 1] += 12345.0
    after = build_sample(raw, index, ModelParams())["s4_force_in"]
    checks["future_interval_perturbation_no_leak"] = bool(np.array_equal(before, after))
    with np.load(data_dir / "network_interface_only.npz") as network:
        checks["network_arrays_separate"] = len(network.files) == 6 and not any("network" in key for key in np.load(data_dir / "dataset_v1_es.npz").files)
    result = {"passed": all(checks.values()), "checks": checks, "trajectory_count": len(manifest)}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()

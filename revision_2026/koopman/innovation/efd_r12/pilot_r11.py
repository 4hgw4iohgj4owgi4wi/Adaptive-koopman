from __future__ import annotations
from pathlib import Path
from typing import Any
import json, numpy as np

from axial_decoder import decode
from mirror_generator import analytic_mirror, mirror_residual, params_from_metadata

SCENARIOS = ("staged_100m", "single_lane_change", "hairpin", "connector_directional")


def jobs(base: int) -> list[dict[str, Any]]:
    local = set(range(base + 1, base + 13))
    long_ids = {base + i for i in (1, 3, 5, 7, 9, 13, 17, 21)}
    return [{"seed": base + i, "trajectory_id": base + i, "base_family_id": f"pilot_{base+i}", "split": "pilot",
             "scenario": SCENARIOS[(i - 1) % 4], "independent_mirror": False,
             "local_mirror": base + i in local, "long_diagnostic": base + i in long_ids} for i in range(1, 25)]


def analytic_oracle(project_s: str, row: dict[str, Any], root_s: str) -> dict[str, Any]:
    project, root = Path(project_s), Path(root_s)
    with np.load(root / row["base_file"], allow_pickle=False) as s:
        base = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}; meta = json.loads(str(s["metadata_json"].item()))
    with np.load(root / row["mirror_file"], allow_pickle=False) as s: mirror = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}
    exact = mirror_residual(mirror, analytic_mirror(base)); params = params_from_metadata(project, meta)
    oracle = decode(base["connector_disp"], base["connector_vel"], params.connector.stiffness_npm, params.connector.damping_nspm, params.connector.free_play_m)
    oracle_max = float(np.max(np.abs(oracle["force_payload"] - base["force_payload"])))
    return {"seed": row["seed"], "scenario": row["scenario"], "exact_max": exact["overall"]["normalized_max"],
            "oracle_max_N": oracle_max, "passed": exact["overall"]["normalized_max"] == 0. and oracle_max <= 2e-3}

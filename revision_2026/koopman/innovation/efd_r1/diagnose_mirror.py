from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

from mirror_generator import mirror_joint_state30, params_from_metadata
from transforms import mirror_control


def main(project: Path, file: Path) -> None:
    with np.load(file, allow_pickle=False) as s:
        a = {k: np.asarray(s[k]) for k in s.files if k != "metadata_json"}; meta = json.loads(str(s["metadata_json"].item()))
    for p in (project / "revision_2026" / "model", project / "revision_2026" / "koopman"):
        if str(p) not in sys.path: sys.path.insert(0, str(p))
    import four_vehicle_coupled as plant
    params = params_from_metadata(project, meta); x = a["initial_state64"]; u = a["control"][0].reshape(4, 2).astype(float)
    f, aux = plant.system_derivative(x, u, params); xm, um = mirror_joint_state30(x), mirror_control(u.reshape(8)).reshape(4, 2)
    fm, auxm = plant.system_derivative(xm, um, params); expected = mirror_joint_state30(f)
    fields = {"initial64_vs_logged32_max": float(np.max(np.abs(x.astype(np.float32) - a["state30"][0]))),
              "control64_vs_logged32_max": float(np.max(np.abs(a["control64"].astype(np.float32) - a["control"]))),
              "derivative_commutator_max": float(np.max(np.abs(fm - expected))),
              "derivative_diff": (fm - expected).reshape(5, 6).tolist(),
              "base_derivative": f.reshape(5, 6).tolist(), "mirror_derivative": fm.reshape(5, 6).tolist(),
              "connector_payload_force_base": aux["connectors"]["force_payload_world_n"].tolist(),
              "connector_payload_force_mirror": auxm["connectors"]["force_payload_world_n"].tolist(),
              "tire_base": [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in t.items()} for t in aux["tire"]],
              "tire_mirror": [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in t.items()} for t in auxm["tire"]]}
    replay = x.copy(); checkpoints = []
    for k, control in enumerate(a["control64"]):
        for _ in range(10): replay = plant.rk4_step(replay, control.reshape(4, 2), .002, params)
        if k in (0, 1, 9, 99, len(a["control64"]) - 1):
            checkpoints.append({"k": k + 1, "max_abs_vs_logged": float(np.max(np.abs(replay.astype(np.float32) - a["state30"][k + 1])))})
    fields["base_open_loop_replay"] = checkpoints
    print(json.dumps(fields, indent=2))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--project", type=Path, required=True); p.add_argument("--file", type=Path, required=True)
    a = p.parse_args(); main(a.project, a.file)

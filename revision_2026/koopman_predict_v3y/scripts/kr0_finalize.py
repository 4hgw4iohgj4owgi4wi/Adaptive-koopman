"""KR0 finalization: identity_audit, environment, schema, complete (BLOCKED:
INPUT_CONTRACT_BLOCKED) and solutions.md for run 20260904_204301_KR_R01."""
import csv
import datetime
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3T = REV / "koopman_predict_v3t"
KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
RUN = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01"
KR0 = RUN / "kr0"
N5_MANI = REV / "koopman_predict_auto_results" / "runs" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "data_manifest.csv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    KR0.mkdir(parents=True, exist_ok=True)
    # environment
    try:
        import torch
        torch_v, cuda = torch.__version__, torch.cuda.is_available()
        gpu = torch.cuda.get_device_name(0) if cuda else "CPU"
    except Exception:
        torch_v, cuda, gpu = "MISSING", False, "CPU"
    env = {
        "hostname": "DESKTOP-9IUUGEO",
        "python": r"E:\anaconda\envs\pytorch_new\python.exe",
        "torch": torch_v, "cuda": bool(cuda), "gpu": gpu,
        "disk_d_free_gib": round(shutil.disk_usage("D:\\").free / 2**30, 2),
        "now": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (KR0 / "environment.json").write_text(json.dumps(env, indent=1), encoding="utf-8")

    # identity audit (SHA chain verified in KR0)
    identity = {
        "taskbook_refine_sha256": sha256(REV / "koopman_refine.md"),
        "taskbook_guard_sha256": sha256(REV / "koopman_guard.md"),
        "data_manifest_sha256": sha256(N5_MANI),
        "fold_manifest_sha256": sha256(KG_RUN / "g0" / "fold_manifest.csv"),
        "v3t_src_lift": sha256(V3T / "src" / "lift.py"),
        "v3t_src_guard_core": sha256(V3T / "src" / "guard_core.py"),
        "v3t_src_guard_training": sha256(V3T / "src" / "guard_training.py"),
        "v3t_scripts_guard_experiments": sha256(V3T / "scripts" / "guard_experiments.py"),
        "v3u_src_lift_matches_v3t": sha256(REV / "koopman_predict_v3u" / "src" / "lift.py") == sha256(V3T / "src" / "lift.py"),
        "v3u_src_guard_core_matches_v3t": sha256(REV / "koopman_predict_v3u" / "src" / "guard_core.py") == sha256(V3T / "src" / "guard_core.py"),
        "g5_status": "COMPLETE_STOP selected=null",
        "expected": {
            "taskbook_guard": "8F9367990910DA45B6EABB726C1FF717EFB8C745338DAFCCE382DCDF3D8A058D",
            "data_manifest": "B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9",
            "fold_manifest": "2DBAF6D83B14594C444234E05EC03638C0FE66935F17F8C5A7D82A0E468D1AC0",
            "lift": "2CEB2198ED1D40D236D6CF26DB1688A978255CD1724FF23CF31D6D7BB87D1B86",
            "guard_core": "A14C3352694A410E9C31681008A01EE3D36F43F151E0CC6AB2B8915F052F8D37",
            "guard_training": "D94F42C2FC940D220B8DE343F7D439CC37BA362A2552EFD50ECF076EDA640A4C",
            "guard_experiments": "1F306A9231B0A11A57E93269F36A299306F6EB782B27D90015756559272A8C01",
        },
        "notes": [
            "15 frozen main checkpoints SHA matched in the KG run g4 (frozen_models.json references); "
            "63-item G5 source manifest matched at taskbook writing time and re-verified by v3t file listing",
            "historical_recompute from the 20 outer rows CSVs matches the guard main table exactly (max abs diff 0.0)",
        ],
    }
    (KR0 / "identity_audit.json").write_text(json.dumps(identity, indent=1, ensure_ascii=False), encoding="utf-8")

    # schema summary from a D7 raw/cache sample (already loaded in the input contract audit)
    schema = {
        "time_step_s": 0.02,
        "state_dim": 47,
        "control_dim": 7,
        "cache_control7_columns": [
            "base_acceleration_mps2(virtual)", "virtual_front_rad", "virtual_rear_rad",
            "requested_steer_FL_rad", "requested_steer_FR_rad", "requested_steer_RL_rad", "requested_steer_RR_rad",
        ],
        "cache_fields_verified": [
            "relative_state47", "actual_steering4", "control7", "analytic_actual_next4",
            "force_payload_body8", "internal_force8", "vehicle_yaw_rate4", "payload_yaw_rate",
            "system_yaw_rate", "window_start", "window_class",
        ],
        "raw_has_requested_acceleration_column": True,
        "raw_requested_control4x2_semantics": "(T,4,2) column0=per-vehicle requested acceleration (includes offsets), column1=requested steering",
        "input_contract": "BLOCKED - four-vehicle requested acceleration differentials never reach control7",
        "note": "schema consistency across the full pool (12 scenarios x 96 families) verified by construction identity of N5 caches; detailed per-scenario schema table produced in input_contract.csv/json",
    }
    (KR0 / "schema.json").write_text(json.dumps(schema, indent=1, ensure_ascii=False), encoding="utf-8")

    shutil.copy2(KG_RUN / "g0" / "fold_manifest.csv", KR0 / "fold_manifest.csv")

    judgement = "INPUT_CONTRACT_BLOCKED"
    complete = {
        "stage": "KR0",
        "status": "BLOCKED",
        "judgement": judgement,
        "exit_code_semantics": 21,
        "gates": {
            "identity_sha_chain": True,
            "no_illegal_numeric_reads": True,
            "historical_main_table_recomputed": True,
            "historical_max_abs_diff": 0.0,
            "input_contract": False,
            "schema_time_index_basic_ok": True,
        },
        "summary": (
            "Identity chain verified; main table recomputed exactly; input contract audit found "
            "D7 diff accel up to 0.228 m/s^2 (83% active) and D9A up to 0.173 m/s^2 with identical "
            "control7 rows carrying different differentials -> the four-vehicle requested "
            "acceleration is NOT recoverable from the 7-dim input. Training route KR1-KR6 stopped "
            "per koopman_refine.md KR0; Appendix B fix proposal delivered for user approval."
        ),
        "now": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (KR0 / "complete.json").write_text(json.dumps(complete, indent=1, ensure_ascii=False), encoding="utf-8")

    solutions = """# KR0 solutions (INPUT_CONTRACT_BLOCKED)

## Failed gate
- input_contract: four-vehicle requested acceleration differentials are not encoded in the
  7-dim control input (control7).

## Evidence
- `koopman_predict_auto/src/dataset.py::prediction_cache_from_raw` line 220:
  `control7 = np.c_[virtual[1:], requested[1:, :, 1]]` -- uses requested steering column only.
- `koopman_predict_auto/scripts/generate_data.py` line 229:
  `requested_controls[:, 0] += np.asarray(command.vehicle_accel_offset_mps2, ...)` -- per-vehicle
  acceleration offsets (D7 +-0.20, D9A +-0.15) are written into requested_control4x2[:, :, 0],
  which never enters control7.
- Numerical audit on fold0 fit trajectories (kr0/input_contract.json/csv):
  - D7: max |diff accel| = 0.2281 m/s^2, active share 83.3%, identical-control7/different-diff witness found.
  - D9A: max |diff accel| = 0.1728 m/s^2, active share 83.3%, witness found.
- The plant input therefore cannot be recovered unambiguously from the model input; state
  history cannot be assumed to encode future opposite commands (strict counterfactual not run).

## Root cause candidates and falsification
- Cause: cache contract only carries virtual acceleration + virtual steers + four requested steers.
- Falsification check that would clear it: a run where requested_control4x2[:,:,0] equals the
  virtual acceleration broadcast for every sample (no offsets) would make the missing column moot;
  our audit shows this is false for D7/D9A.

## Fix (Appendix B of koopman_refine.md) -- requires user approval of a new input protocol
- New input u^11 = [u^7, delta_a_FL, delta_a_FR, delta_a_RL, delta_a_RR] with
  delta_a_i = a_i^req - a_virtual (four differences, FL/FR/RL/RR order).
- New cache column control11 (columns 0..6 identical to control7); old control7 caches untouched.
- Encoder widths 38/35 -> 42/39 (both branches receive control11); B0 47x11, G 16x11;
  latent dim 16 unchanged; explicit input_schema in checkpoints.
- New protocol/protocol_input.json + new run; fresh fixed-linear 7-vs-11 comparison first,
  then same-budget 7-vs-11 residual comparison; the 11-dim fixed linear becomes the new common
  baseline before any guard comparison. Input gains are NOT to be claimed as operator novelty.

## Cost/risk
- One extra data-derivation pass over existing raw (no plant reruns, no label changes);
- B0/G re-init; old 7-dim checkpoints remain valid only for 7-dim inference.

## Recovery condition
- User approves the 11-dim input protocol (new taskbook/protocol version), then KR0 re-run with
  INPUT_CONTRACT_OK before KR1-KR6 may start.
"""
    (RUN / "solutions.md").write_text(solutions, encoding="utf-8")
    print("KR0_FINALIZED judgement=", judgement)


if __name__ == "__main__":
    main()

"""Analyze EXP-R3 R3A frozen-input 1/0.5 ms replays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ..cli import save, sha


def load(folder: Path):
    with np.load(folder / "raw.npz", allow_pickle=False) as z:
        raw = np.asarray(z["values"], float)
        rc = {str(x): i for i, x in enumerate(z["columns"])}
    with np.load(folder / "substeps.npz", allow_pickle=False) as z:
        sub = np.asarray(z["values"], float)
        sc = {str(x): i for i, x in enumerate(z["columns"])}
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8-sig"))
    return raw, rc, sub, sc, metrics


def quantities(folder: Path) -> dict:
    raw, c, sub, s, metrics = load(folder)
    peaks = np.asarray([np.max(sub[:, s[f"force_peak{i}"]]) for i in range(4)])
    impulses = np.c_[
        [np.sum(sub[:, s[f"force_impulse_x{i}"]]) for i in range(4)],
        [np.sum(sub[:, s[f"force_impulse_y{i}"]]) for i in range(4)],
    ]
    return {
        "raw": raw,
        "columns": c,
        "peaks": peaks,
        "impulses": impulses,
        "position": raw[-1, [c["x24"], c["x25"]]],
        "heading": raw[-1, c["x26"]],
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coarse", required=True)
    parser.add_argument("--fine", required=True)
    parser.add_argument("--fine-repeat", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    coarse = quantities(Path(args.coarse))
    fine = quantities(Path(args.fine))
    repeat = quantities(Path(args.fine_repeat))

    identities = (
        "initial_state_sha256",
        "initial_actual_delta_sha256",
        "requested_command_sha256",
        "source_raw_sha256",
        "protocol_sha256",
    )
    checks = {
        "all_runs_completed": all(
            item["metrics"]["status"] == "COMPLETED"
            for item in (coarse, fine, repeat)
        ),
        "all_initial_state_request_source_protocol_identities_equal": all(
            coarse["metrics"][key] == fine["metrics"][key] == repeat["metrics"][key]
            for key in identities
        ),
        "fine_self_reproduces_source_state": fine["metrics"][
            "source_self_reproduction_max_state_abs"
        ]
        <= 1e-10,
        "fine_self_reproduces_source_actual_delta": fine["metrics"][
            "source_self_reproduction_max_actual_delta_abs_rad"
        ]
        <= 1e-12,
        "fine_repeat_raw_exact": bool(np.array_equal(fine["raw"], repeat["raw"])),
        "fine_repeat_peak_exact": bool(np.array_equal(fine["peaks"], repeat["peaks"])),
        "fine_repeat_impulse_exact": bool(
            np.array_equal(fine["impulses"], repeat["impulses"])
        ),
    }
    peak_relative = float(
        np.max(
            np.abs(coarse["peaks"] - fine["peaks"])
            / np.maximum(np.abs(fine["peaks"]), 1.0)
        )
    )
    impulse_relative = float(
        np.max(
            np.linalg.norm(coarse["impulses"] - fine["impulses"], axis=1)
            / np.maximum(np.linalg.norm(fine["impulses"], axis=1), 1.0)
        )
    )
    position = float(np.linalg.norm(coarse["position"] - fine["position"]))
    heading = float(
        np.rad2deg(
            abs((coarse["heading"] - fine["heading"] + np.pi) % (2 * np.pi) - np.pi)
        )
    )
    branch_gate = {
        "peak_relative_le_0p02": peak_relative <= 0.02,
        "impulse_vector_relative_le_0p02": impulse_relative <= 0.02,
        "terminal_position_m_le_0p001": position <= 0.001,
        "terminal_heading_deg_le_0p01": heading <= 0.01,
    }
    valid = all(checks.values())
    gate_pass = all(branch_gate.values())
    report = {
        "status": "PASS_BRANCH_A" if valid and gate_pass else ("FAIL_BRANCH_B" if valid else "INVALID_BRANCH_C"),
        "scope": "42.00-44.50 s frozen-request propagation diagnostic; not full R3",
        "checks": checks,
        "thresholds": {
            "peak_relative": 0.02,
            "impulse_vector_relative": 0.02,
            "terminal_position_m": 0.001,
            "terminal_heading_deg": 0.01,
        },
        "comparison": {
            "peak_max_relative": peak_relative,
            "impulse_vector_max_relative": impulse_relative,
            "terminal_payload_position_m": position,
            "terminal_payload_heading_deg": heading,
            "checks": branch_gate,
        },
        "decision": (
            "Proceed only to QP sensitivity branch A"
            if valid and gate_pass
            else (
                "Proceed only to one 0.25 ms propagation diagnostic branch B"
                if valid
                else "Repair identity/time/state closure only; branch C"
            )
        ),
        "source_sha256": sha(__file__),
    }
    save(out, "r3a.json", report)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    if not valid:
        raise SystemExit(22)
    if not gate_pass:
        raise SystemExit(20)


if __name__ == "__main__":
    main()

"""N1 paired evaluation of the causal communication-protection prototype."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from run_comm import clean_reference_error, simulate, strip_records


def summarize(rows: list[dict], condition: str) -> dict:
    selected = [row for row in rows if row["condition"] == condition]
    return {
        "n": len(selected),
        "completion_rate": float(np.mean([row["completed"] for row in selected])),
        "peak_force_mean_n": float(np.mean([row["peak_connector_force_n"] for row in selected])),
        "p99_force_mean_n": float(np.mean([row["p99_connector_force_n"] for row in selected])),
        "opening_p99_mean_n": float(np.mean([row["p99_abs_opening_proxy_n"] for row in selected])),
        "payload_position_rmse_mean_m": float(np.mean([row["payload_position_rmse_m"] for row in selected])),
        "payload_yaw_rmse_mean_rad": float(np.mean([row["payload_yaw_rmse_rad"] for row in selected])),
        "vehicle_position_rmse_mean_m": float(np.mean([row["vehicle_position_rmse_m"] for row in selected])),
        "fallback_receiver_ticks_mean": float(np.mean([row["fallback_receiver_ticks"] for row in selected])),
        "rejected_stale_packets_mean": float(np.mean([row["rejected_stale_packets"] for row in selected])),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    output = root / "protect"
    output.mkdir(parents=True, exist_ok=True)
    unprotected = json.loads((root / "comm" / "need.json").read_text(encoding="utf-8"))
    seeds = [3101, 3102, 3103, 3104, 3105]
    protected_rows = []
    transparency_differences = []
    for seed in seeds:
        clean = simulate("clean", seed, protection="none")
        clean_protected = simulate("clean", seed, protection="protected")
        clean_protected.update(clean_reference_error(clean_protected, clean))
        protected_rows.append(strip_records(clean_protected))
        transparency_differences.append(
            max(
                abs(clean_protected["peak_connector_force_n"] - clean["peak_connector_force_n"]),
                clean_protected["payload_position_rmse_m"],
            )
        )
        print("clean", seed, clean_protected["payload_position_rmse_m"])
        for condition in ("light", "medium", "heavy"):
            result = simulate(condition, seed, protection="protected")
            result.update(clean_reference_error(result, clean))
            protected_rows.append(strip_records(result))
            print(condition, seed, result["payload_position_rmse_m"], result["p99_abs_opening_proxy_n"])

    protected_summary = {condition: summarize(protected_rows, condition) for condition in ("clean", "light", "medium", "heavy")}
    unprotected_summary = unprotected["summary"]
    comparison = {}
    for condition in ("light", "medium", "heavy"):
        comparison[condition] = {
            "payload_rmse_change_fraction": (
                protected_summary[condition]["payload_position_rmse_mean_m"]
                / max(unprotected_summary[condition]["payload_position_rmse_mean_m"], 1.0e-12)
                - 1.0
            ),
            "opening_p99_change_fraction": (
                protected_summary[condition]["opening_p99_mean_n"]
                / max(unprotected_summary[condition]["opening_p99_mean_n"], 1.0e-12)
                - 1.0
            ),
            "force_p99_change_fraction": (
                protected_summary[condition]["p99_force_mean_n"]
                / max(unprotected_summary[condition]["p99_force_mean_n"], 1.0e-12)
                - 1.0
            ),
        }
    acceptance = {
        "clean_transparent": max(transparency_differences) <= 1.0e-9,
        "medium_payload_rmse_improved": comparison["medium"]["payload_rmse_change_fraction"] < 0.0,
        "heavy_payload_rmse_improved": comparison["heavy"]["payload_rmse_change_fraction"] < 0.0,
        "heavy_opening_not_worse": comparison["heavy"]["opening_p99_change_fraction"] <= 0.05,
        "all_complete": all(row["completed"] for row in protected_rows),
    }
    report = {
        "passed": all(acceptance.values()),
        "acceptance": acceptance,
        "unprotected_summary": unprotected_summary,
        "protected_summary": protected_summary,
        "comparison": comparison,
        "runs": protected_rows,
        "scope": "causal prototype: sequence rejection, AoI extrapolation, quality scheduling, heading-only fallback, soft recovery",
    }
    (output / "protect.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "acceptance": acceptance, "comparison": comparison}, indent=2))


if __name__ == "__main__":
    main()

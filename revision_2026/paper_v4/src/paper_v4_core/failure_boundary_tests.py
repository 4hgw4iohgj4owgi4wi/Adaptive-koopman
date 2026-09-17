"""EXP-R2 R0 mock tests for terminal interval accounting."""
import argparse
from pathlib import Path

import numpy as np
import json

from .cli import save, sha
from .failure_boundary import consume_audit
from .e01_analyze import audit_failure_boundary


def _segment(dt, endpoint=3.0):
    z4 = [0.0] * 4
    z8 = [[0.0, 0.0]] * 4
    return {
        "dt_s": dt,
        "force_start_n": [1.0] * 4,
        "force_midpoint_n": [2.0] * 4,
        "force_endpoint_n": [endpoint] * 4,
        "force_payload_body_n": z8,
        "force_interval_impulse_world_ns": z8,
        "payload_support_load_n": [1.0] * 4,
        "vehicle_total_normal_load_n": [1.0] * 4,
        "tire_raw_utilization": z4,
        "tension_x_n": 0.0,
        "tension_y_n": 0.0,
        "signed_gap_m": z4,
        "smoothing_weight": z4,
    }


def _audit(status, segments, audit_peak=None):
    duration = sum(s["dt_s"] for s in segments)
    return {
        "status": status,
        "interval_segments": segments,
        "accepted_steps": len(segments),
        "duration_actual_s": duration,
        "force_peak_n": np.asarray(audit_peak if audit_peak is not None else ([3.0] * 4)),
    }


def run(out):
    cases = []
    accepted_stop = consume_audit(_audit("STOP_ULTIMATE_FORCE", [_segment(0.001, 15001.0)]), 2.0, [9.0], [0.1], [0.2])
    cases.append({"name": "accepted_1ms_then_stop", "pass": bool(accepted_stop["accepted"] and np.isclose(accepted_stop["t_end_s"], 2.001) and accepted_stop["failure_event_time_s"] == accepted_stop["t_end_s"] and np.allclose(accepted_stop["force_peak_n"], 15001.0) and np.allclose(accepted_stop["state_at_t_end"], [9.0]) and np.allclose(accepted_stop["actuator_state_after"], [0.2]) and accepted_stop["actuator_update_time_s"] == 2.0)})
    rejected = consume_audit(_audit("UNRESOLVED_ZONE_RESOLUTION", [], [0.0] * 4), 3.0, [8.0], [0.2], [0.3])
    cases.append({"name": "failure_without_accept", "pass": bool(not rejected["accepted"] and rejected["t_end_s"] == 3.0 and rejected["accepted_duration_s"] == 0.0 and np.allclose(rejected["state_at_t_end"], [8.0]) and np.allclose(rejected["actuator_state_after"], [0.3]) and rejected["actuator_update_time_s"] == rejected["t_start_s"])})
    normal = consume_audit(_audit("PASS", [_segment(0.002)]), 4.0, [7.0], [0.3], [0.4])
    cases.append({"name": "normal_2ms", "pass": bool(normal["failure_event_time_s"] is None and np.isclose(normal["t_end_s"], 4.002) and np.allclose(normal["actuator_state_after"], [0.4]))})
    endpoint = consume_audit(_audit("STOP_ULTIMATE_FORCE", [_segment(0.002, 15000.5)]), 5.0, [6.0], [0.4], [0.5])
    cases.append({"name": "endpoint_trigger", "pass": bool(endpoint["force_peak_argmax"][0]["source"] == "segment_endpoint:0" and np.isclose(endpoint["force_peak_argmax"][0]["time_s"], 5.002) and np.allclose(endpoint["actuator_state_before"], [0.4]) and np.allclose(endpoint["actuator_state_after"], [0.5]))})
    fixture=Path(out)/"boundary_fixture";fixture.mkdir(parents=True,exist_ok=True)
    rawcols=np.asarray(["time_s","accepted_substeps"]);subcols=np.asarray(["time_s","dt_s"])
    np.savez_compressed(fixture/"raw.npz",values=np.asarray([[0.002,1.]]),columns=rawcols)
    np.savez_compressed(fixture/"substeps.npz",values=np.asarray([[0.002,0.002]]),columns=subcols)
    metrics={"status":"STOP_ULTIMATE_FORCE","integrated_duration_s":0.002,"accepted_substeps":1,"requested_full_trajectory":True,"trajectory_completed":False,"failure_event_time_s":0.002,"state_at_t_end":[1.0],"actuator_state_at_t_end":[0.1]}
    (fixture/"metrics.json").write_text(json.dumps(metrics),encoding="utf-8")
    complete_audit=audit_failure_boundary(fixture)
    cases.append({"name":"complete_terminal_evidence_accepted","pass":complete_audit["status"]=="PASS"})
    np.savez_compressed(fixture/"substeps.npz",values=np.asarray([[0.001,0.001]]),columns=subcols)
    missing_audit=audit_failure_boundary(fixture)
    cases.append({"name":"missing_terminal_segment_rejected","pass":missing_audit["status"]=="FAIL" and not missing_audit["checks"]["duration_matches_terminal"]})
    report = {"status": "PASS" if all(c["pass"] for c in cases) else "FAIL", "tests": cases, "source_sha256": sha(__file__)}
    save(Path(out), "r0_mock_tests.json", report)
    print(report)
    if report["status"] != "PASS":
        raise SystemExit(20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run(args.out)


if __name__ == "__main__":
    main()

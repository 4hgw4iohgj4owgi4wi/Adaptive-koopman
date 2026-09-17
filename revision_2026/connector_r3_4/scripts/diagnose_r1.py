from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connector_adapter import DELTA_S_M, ScalarConnector
from event_substep import EventSubstepConfig, _next_scalar_step, integrate, scalar_two_half_rk4

SPEEDS = {
    "q05": 0.0002041391858023853, "q50": 0.003371584129140294,
    "q95": 0.054984709782141795, "q99": 0.2006325726682664,
    "stress_0p25": 0.25, "stress_1p0": 1.0,
}
EXPECTED_TRUE = {("q95", 12, "R3"), ("stress_0p25", 22, "V1")}


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def dump_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha(path: Path) -> str:
    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


def diagnostic_trace(law: str, q0: float, speed: float, duration: float) -> tuple[list[dict], dict]:
    cfg = EventSubstepConfig(); conn = ScalarConnector(law)
    state = np.array([q0, speed], dtype=float); t = 0.0; outer = 0; rows = []
    while t < duration - cfg.closure_tol_s:
        outer_end = min(duration, (np.floor((t + 1e-15) / cfg.outer_step_s) + 1.0) * cfg.outer_step_s)
        if outer_end <= t + 1e-15: outer_end = min(duration, t + cfg.outer_step_s)
        while t < outer_end - 1e-15:
            remaining = outer_end - t
            if remaining <= cfg.closure_tol_s:
                rows.append({"time_s": t, "remaining_s": remaining, "candidate_dt_s": 0.0,
                             "accepted_dt_s": 0.0, "step_class": "CLOSURE_RESIDUAL",
                             "q_m": state[0], "v_mps": state[1]})
                t = outer_end; break
            q, velocity = float(state[0]), float(state[1]); candidate = min(cfg.probe_step_s, remaining)
            predicted = q + velocity * candidate
            in_zone = (-cfg.surface_tol_m <= q <= cfg.smoothing_width_m + cfg.surface_tol_m or
                       min(q,predicted) <= 0 <= max(q,predicted) or
                       min(q,predicted) <= cfg.smoothing_width_m <= max(q,predicted))
            unresolved = False; cause = "probe_or_remaining"
            if in_zone and abs(velocity) > 0:
                zone = cfg.smoothing_width_m / (cfg.zone_nodes * max(abs(velocity), 1e-12))
                if zone < cfg.min_step_s: unresolved = True
                else:
                    if zone < candidate: cause = "zone_resolution"
                    candidate = min(candidate, zone)
            if abs(velocity) > 1e-14:
                for surface, label in ((0.0,"contact_eta"),(cfg.smoothing_width_m,"smoothing_eta")):
                    eta = (surface-q)/velocity
                    if cfg.min_step_s <= eta <= candidate: candidate, cause = eta, label
            candidate = max(min(candidate, remaining), min(remaining, cfg.min_step_s))
            step_class = "UNRESOLVED_EVENT_SPEED" if unresolved else ("SUBMINIMUM_OUTER_REMAINDER" if candidate < cfg.min_step_s else "REGULAR_STEP")
            mid, end = scalar_two_half_rk4(state, candidate, conn, cfg.reduced_mass_kg)
            md = conn.evaluate(float(mid[0]), float(mid[1]))
            rows.append({"time_s": t, "outer_end_s": outer_end, "remaining_s": remaining,
                         "candidate_dt_s": candidate, "accepted_dt_s": candidate,
                         "step_class": step_class, "selection_cause": cause, "q_m": state[0], "v_mps": state[1],
                         "contact_surface_m": state[0], "smoothing_surface_m": state[0] - DELTA_S_M,
                         "mid_q_m": mid[0], "mid_v_mps": mid[1], "mid_force_n": md["force_n"],
                         "end_q_m": end[0], "end_v_mps": end[1]})
            if unresolved: return rows, {"status": step_class, "time_s": t}
            state = end; t += candidate
        outer += 1
    return rows, {"status": "PASS", "time_s": t, "q_m": state[0], "v_mps": state[1]}


def main(project: Path, out: Path) -> None:
    old_n2 = project / "revision_2026/connector_r3_2_results/n2/single_connector_factorial.csv"
    old_pair = project / "revision_2026/connector_r3_3_results/n2a/reference_pair_checks.csv"
    rows_old = read_csv(old_n2)
    sub2 = [r for r in rows_old if float(r["min_accepted_dt_s"]) < 2e-6]
    closure = [r for r in sub2 if float(r["min_accepted_dt_s"]) <= 1e-12]
    true = [r for r in sub2 if 1e-12 < float(r["min_accepted_dt_s"]) < 2e-6]
    ids = {(r["speed_label"], int(r["phase_index"]), r["law"]) for r in true}
    classification_ok = len(sub2) == 66 and len(closure) == 64 and len(true) == 2 and ids == EXPECTED_TRUE
    dump_csv(out / "sub2us_classification.csv", [dict(r, r34_class=("CLOSURE_RESIDUAL" if float(r["min_accepted_dt_s"]) <= 1e-12 else "TRUE_EVENT_NEIGHBOR")) for r in sub2])

    pair_rows = []; peak_windows = []
    for speed_label, speed in SPEEDS.items():
        duration = max(0.020, DELTA_S_M / speed + 0.012)
        for law in ("V1", "R3"):
            runs = {h: integrate(law, 0.0, speed, duration, "REF", fixed_step_s=h, keep_trace=(h == 0.5e-6)) for h in (2e-6, 1e-6, 0.5e-6)}
            r1, rf = runs[1e-6], runs[0.5e-6]
            pair_rows.append({"speed_label": speed_label, "law": law,
                              "peak_1_0p5": abs(r1["peak_force_n"]-rf["peak_force_n"]),
                              "impulse_1_0p5": abs(r1["impulse_ns"]-rf["impulse_ns"]),
                              "terminal_q_1_0p5": abs(r1["terminal_penetration_m"]-rf["terminal_penetration_m"]),
                              "terminal_v_1_0p5": abs(r1["terminal_speed_mps"]-rf["terminal_speed_mps"]),
                              "statuses": "/".join(runs[h]["status"] for h in (2e-6,1e-6,0.5e-6))})
            tr = rf["trace"]; idx = int(np.argmax(np.asarray(tr["force_n"])))
            for i in range(max(0, idx-10), min(len(tr["time_s"]), idx+11)):
                peak_windows.append({"speed_label": speed_label, "law": law, "relative_index": i-idx,
                                     "time_s": tr["time_s"][i], "q_m": tr["penetration_m"][i],
                                     "v_mps": tr["normal_speed_mps"][i], "force_n": tr["force_n"][i],
                                     "accepted_dt_s": tr["accepted_dt_s"][i]})
    dump_csv(out / "reference_pair_checks_reproduced.csv", pair_rows)
    dump_csv(out / "peak_windows_0p5us.csv", peak_windows)
    prior = read_csv(old_pair)
    prior_map = {(r["speed_label"], r["law"]): r for r in prior}
    deltas = []
    for row in pair_rows:
        p = prior_map[(row["speed_label"], row["law"])]
        deltas.append(max(abs(float(row[k])-float(p[k])) for k in ("peak_1_0p5","impulse_1_0p5","terminal_q_1_0p5","terminal_v_1_0p5")))
    reproduce_ok = max(deltas) <= 1e-14

    trace_summaries = []
    for r in true:
        label, phase, law = r["speed_label"], int(r["phase_index"]), r["law"]
        q0 = -SPEEDS[label] * (EventSubstepConfig().outer_step_s + float(r["phase_s"]))
        tr, summary = diagnostic_trace(law, q0, SPEEDS[label], float(r["duration_s"]))
        name = f"{label}_phase{phase}_{law}"
        dump_csv(out / f"trace_{name}.csv", tr)
        trace_summaries.append(dict(case=name, **summary, min_dt_s=min(x["accepted_dt_s"] for x in tr if x["accepted_dt_s"] > 0), event_alignment_steps=sum(x["step_class"] == "EVENT_ALIGNMENT_STEP" for x in tr)))
    dump_json(out / "true_sub2us_trace_summary.json", trace_summaries)
    complete = {"stage":"R1","passed": bool(classification_ok and reproduce_ok and all(x["status"] == "PASS" for x in trace_summaries)),
                "classification": {"sub2us":len(sub2),"closure":len(closure),"true_event_neighbor":len(true),"ids":sorted(list(ids)),"passed":classification_ok},
                "reproduction": {"prior_sha256":sha(old_pair),"max_metric_abs_delta":max(deltas),"passed":reproduce_ok},
                "trace_summaries":trace_summaries}
    dump_json(out / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False)); raise SystemExit(0 if complete["passed"] else 2)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())

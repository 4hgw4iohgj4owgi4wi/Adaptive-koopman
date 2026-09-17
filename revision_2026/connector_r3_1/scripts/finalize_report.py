from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def percent(value: float) -> str:
    return f"{100.0 * value:.3f}%"


def main() -> None:
    source = Path(sys.argv[1]).resolve()
    results = Path(sys.argv[2]).resolve()
    support = json.loads((results / "r0b" / "contact_speed_support.json").read_text(encoding="utf-8"))
    r2 = json.loads((results / "r2_1" / "r2_1_results.json").read_text(encoding="utf-8"))
    r3_path = results / "r3_dt" / "r3_dt_results.json"
    r3 = json.loads(r3_path.read_text(encoding="utf-8")) if r3_path.is_file() else None
    correction_path = results / "audit_corrections" / "CR3_1_C001" / "correction_record.json"
    correction = json.loads(correction_path.read_text(encoding="utf-8-sig")) if correction_path.is_file() else None
    history = json.loads((results / "s0" / "historical_manifest.json").read_text(encoding="utf-8"))
    protocol_hash = sha256(source / "protocol.md")
    now = datetime.now(timezone.utc).astimezone().isoformat()

    if not r2["passed"]:
        status = "BLOCKED_R3_1_R2_1_GATE"
        failed_stage = "R2.1"
        failed_checks = [key for key, value in r2["checks"].items() if not value]
        passed_stages = ["S0_HISTORY_FREEZE", "S1_TRAIN_SPEED_AUDIT"]
    elif r3 is None:
        status = "R2_1_PASSED_R3A_NOT_RUN"
        failed_stage = None
        failed_checks = []
        passed_stages = ["S0_HISTORY_FREEZE", "S1_TRAIN_SPEED_AUDIT", "S2_R2_1"]
    elif not r3["passed"]:
        status = "BLOCKED_R3_1_PLANT_STEP_RESOLUTION"
        failed_stage = "R3a"
        failed_checks = [key for key, value in r3["checks"].items() if not value]
        passed_stages = ["S0_HISTORY_FREEZE", "S1_TRAIN_SPEED_AUDIT", "S2_R2_1"]
    else:
        status = "R3A_PASSED_READY_FOR_R3B"
        failed_stage = None
        failed_checks = []
        passed_stages = ["S0_HISTORY_FREEZE", "S1_TRAIN_SPEED_AUDIT", "S2_R2_1", "S3_R3A"]

    downstream_state = "NOT_RUN_PRECONDITION_FAILED" if failed_stage else "NOT_RUN_AWAITING_NEXT_STAGE"
    downstream = {
        "R3b_four_vehicle_representative_load": downstream_state,
        "R4_paired_plant": downstream_state,
        "R5_direction_internal_force": downstream_state,
        "D0_D1": downstream_state,
        "Koopman": downstream_state,
        "MPC": downstream_state,
    }
    for name, value in downstream.items():
        folder = results / "downstream" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "NOT_RUN.md").write_text(
            f"# {name}\n\nStatus: `{value}`.\n\nUpstream status: `{status}`.\n",
            encoding="utf-8",
        )

    stage = {
        "status": status,
        "timestamp": now,
        "classification": "post-R2 protocol revision",
        "protocol_sha256": protocol_hash,
        "historical_status_preserved": history["historical_status"],
        "smoothing_width_m_unchanged": support["smoothing_width_m"],
        "passed_stages": passed_stages,
        "failed_stage": failed_stage,
        "failed_checks": failed_checks,
        "development_read": False,
        "confirm_read": False,
        "downstream": downstream,
        "physical_claim_boundary": "numerical-model audit only; no measured connector strength certification",
    }
    (results / "stage_status.json").write_text(json.dumps(stage, indent=2), encoding="utf-8")

    q = support["speed_quantiles_mps"]
    tq = support["tau_nominal_quantiles_s"]
    report = [
        "# Connector R3.1 execution report",
        "",
        f"> Status: `{status}`  ",
        f"> Protocol: `{protocol_hash}`  ",
        "> Classification: post-R2 protocol revision; historical R3 evidence remains immutable.",
        "",
        "## Outcome",
        "",
        f"- Historical files frozen and verified: {len(history['files'])}.",
        f"- Train-only contact events audited: {support['event_count']} from 256 independent bases.",
        f"- R2.1 repaired gate: `{'PASS' if r2['passed'] else 'FAIL'}`.",
        f"- R3a 2 ms resolvability/convergence: `{'NOT_RUN' if r3 is None else ('PASS' if r3['passed'] else 'FAIL')}`.",
        "- Development and confirm were not read.",
        "- The 12/15 kN values are unverified numerical thresholds, not physical strength limits.",
        "",
        "## Train-only support audit",
        "",
        "| Quantile | Contact speed (m/s) | Nominal smoothing time (ms) |",
        "|---:|---:|---:|",
    ]
    for key in ("q01", "q05", "q50", "q90", "q95", "q99", "q100"):
        report.append(f"| {key.upper()} | {q[key]:.9g} | {1000*tq[key]:.9g} |")
    report += [
        "",
        "## R2.1 repaired evidence",
        "",
        "| Support speed | Worst phase-swept first-sample reduction |",
        "|---:|---:|",
    ]
    for key, value in r2["support_worst_first_sample_reduction"].items():
        report.append(f"| {key.upper()} | {percent(value)} |")
    report += [
        "",
        f"E1 activated damping for {r2['e1']['positive_power_samples']} samples; maximum power was "
        f"{r2['e1']['max_damping_power_w']:.6g} W. The maximum energy-balance residual was "
        f"{r2['e1']['energy_balance_max_abs_j']:.6g} J "
        f"(scaled {r2['e1']['energy_balance_max_scaled']:.6g}). The damped and zero-damping "
        "trace hashes differ.",
        "",
        f"E2 integrated positive damping work was {r2['e2']['dissipated_work_j']:.6g} J; "
        f"maximum unloading damping force was {r2['e2']['unloading_max_damping_force_n']:.6g} N.",
        "",
    ]
    if r3 is not None:
        report += [
            "## R3a plant-step resolution",
            "",
            "| Support speed | Speed (m/s) | Nominal width time (ms) | Median 2 ms nodes | Fraction with <=1 node |",
            "|---:|---:|---:|---:|---:|",
        ]
        for key, value in r3["resolution_by_support_speed"].items():
            report.append(
                f"| {key.upper()} | {value['speed_mps']:.9g} | {1000*value['tau_nominal_s']:.9g} | "
                f"{value['node_median']:.3g} | {percent(value['fraction_le_one_node'])} |"
            )
        report += [
            "",
            f"The 2 ms smoothing-zone resolvability gate was `{'PASS' if r3['checks']['support_smoothing_zone_resolvable_at_2ms'] else 'FAIL'}`. "
            "A failure means the mathematical boundary layer is not adequately sampled at the formal plant step; "
            "the four-vehicle and learning chain is therefore not allowed to run.",
            "",
        ]
    report += ["## Figures", ""]
    for path in sorted((results / "figures").glob("*.png")):
        report.append(f"![{path.stem}](figures/{path.name})")
        report.append("")
    report += [
        "## Claim boundary",
        "",
        "These results concern a numerical planar equivalent. They do not establish measured connector "
        "strength, fatigue life, cargo tearing safety, Koopman improvement, or MPC robustness.",
        "",
    ]
    (results / "report.md").write_text("\n".join(report), encoding="utf-8")

    failed_r2 = [key for key, value in r2["checks"].items() if not value]
    resolution_fail = [] if r3 is None else [
        key for key, value in r3["resolution_by_support_speed"].items()
        if not value["median_at_least_two"]
    ]
    solutions = [
        "# Connector R3.1 stop/solution record",
        "",
        f"> Current status: `{status}`  ",
        "> This is a numerical-model decision record, not hardware certification.",
        "",
        "## Verified facts",
        "",
        f"- R3 historical evidence remains frozen as `{history['historical_status']}`.",
        f"- The R3 formula and `delta_s={support['smoothing_width_m']:.15g} m` were not changed.",
        f"- R2.1 failed checks: `{failed_r2}`.",
        f"- Development/confirm access: `false/false`.",
    ]
    if r3 is not None:
        solutions += [
            f"- Support speeds failing the median two-node 2 ms resolution gate: `{resolution_fail}`.",
            f"- R3a numeric-convergence aggregate: `{r3['checks']['all_2ms_numeric_convergence_checks_pass']}`.",
        ]
    solutions += ["", "## Decision", ""]
    if failed_stage == "R2.1":
        solutions += [
            "Stop before R3a/R4. Repair the failed R2.1 evidence without reading development or confirm, "
            "freeze a new revision, and rerun from R2.1.",
        ]
    elif failed_stage == "R3a":
        solutions += [
            "Stop before four-vehicle R3b/R4/R5, data generation, Koopman and MPC. The frozen boundary "
            "regularization is mathematically valid but not sufficiently resolved at the 2 ms plant grid.",
            "",
            "Allowed next routes are: (1) event-aware substepping while keeping the 2 ms controller clock; "
            "(2) a separately versioned time/state activation law with a frozen time constant; or "
            "(3) event-aware data sampling. Each is a new model/protocol and must repeat energy, fairness, "
            "four-point direction and closed-loop gates. Do not widen delta_s by fitting downstream results.",
        ]
    else:
        solutions += ["No hard stop was reached in the executed stages; the next permitted action is R3b/R4 under the frozen protocol."]
    (results / "solutions.md").write_text("\n".join(solutions) + "\n", encoding="utf-8")

    log = [
        "# Connector R3.1 work log",
        "",
        "## CR3.1-L001 historical freeze and protocol isolation",
        "",
        f"- Timestamp: {now}",
        f"- Machine: `{platform.node()}`; interpreter: `{sys.executable}`.",
        f"- Protocol SHA256: `{protocol_hash}`; classification: post-R2 revision.",
        f"- Frozen files: {len(history['files'])}; historical status preserved: `{history['historical_status']}`.",
        "- No historical R0--R2 file was overwritten.",
        "",
        "## CR3.1-L002 train-only speed/time audit",
        "",
        f"- Audited {support['event_count']} events from 256 train bases using the immutable R0 event table.",
        f"- Source event SHA256: `{support['source_events_sha256']}`.",
        f"- Support speeds frozen at Q05/Q50/Q95/Q99: `{support['support_test_speeds_mps']}`.",
        "- development_read=false; confirm_read=false.",
        "",
        "## CR3.1-L003 repaired R2.1",
        "",
        f"- Status: `{'PASS' if r2['passed'] else 'FAIL'}`; checks: `{r2['checks']}`.",
        f"- E1 energy residual: {r2['e1']['energy_balance_max_abs_j']:.9g} J; damped/control hashes differ.",
        f"- E2 dissipated work: {r2['e2']['dissipated_work_j']:.9g} J.",
        "- 2 ms endpoints were retained as support/stress diagnostics, not a universal hard gate.",
    ]
    if r3 is not None:
        log += [
            "",
            "## CR3.1-L004 R3a plant-step audit",
            "",
            f"- Status: `{'PASS' if r3['passed'] else 'FAIL'}`; checks: `{r3['checks']}`.",
            f"- Resolution summary: `{r3['resolution_by_support_speed']}`.",
            f"- Four-vehicle representative load: `{r3['four_vehicle_representative_load']}`.",
        ]
    if correction is not None:
        log += [
            "",
            "## CR3.1-C001 impulse quadrature audit correction",
            "",
            f"- Preserved pre-fix source SHA256: `{correction['pre_source_sha256']}`.",
            f"- Preserved pre-fix result SHA256: `{correction['pre_result_sha256']}`.",
            "- Replaced the historical left-rectangle running diagnostic with trapezoidal force integration.",
            "- Model, data, thresholds and support speeds were unchanged; the Q99 resolution failure remained.",
        ]
    log += [
        "",
        "## Commands",
        "",
        "```text",
        "python scripts/freeze_history.py <project> <source> <results>",
        "python scripts/audit_contact_speed.py <historical_results> <results>",
        "python tests/test_r2_1_single_connector.py <freeze> <support> <r2_1_out>",
        "python tests/test_r3_dt_resolution.py <freeze> <support> <r2_1_json> <r3_out>",
        "python scripts/plot_evidence.py <results>",
        "python scripts/finalize_report.py <source> <results>",
        "```",
        "",
        f"Final stage status: `{status}`. Next permitted action follows `solutions.md`.",
        "",
    ]
    (results / "work_log.md").write_text("\n".join(log), encoding="utf-8")

    source_files = []
    for path in sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        source_files.append({"path": path.relative_to(source).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)})
    result_files = []
    manifest_path = results / "output_manifest.json"
    for path in sorted(p for p in results.rglob("*") if p.is_file() and p != manifest_path):
        result_files.append({"path": path.relative_to(results).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "created": now,
        "status": status,
        "source_root": str(source),
        "result_root": str(results),
        "source_files": source_files,
        "result_files": result_files,
        "source_file_count": len(source_files),
        "result_file_count_excluding_manifest": len(result_files),
        "result_total_bytes_excluding_manifest": sum(row["size"] for row in result_files),
        "manifest_excludes_itself": True,
        "development_read": False,
        "confirm_read": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "source_files": len(source_files), "result_files": len(result_files)}))


if __name__ == "__main__":
    main()

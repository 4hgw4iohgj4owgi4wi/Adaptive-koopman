from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--through-stage", default="N3")
    args = parser.parse_args(); project = args.project_root.resolve(); results = project / "revision_2026" / "connector_r3_3_results"
    stages = {}
    for name in ("n0", "r1", "n1", "n2a", "n2", "n3"):
        path = results / name / "complete.json"
        stages[name.upper()] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passed": False, "status": "NOT_RUN"}
    passed = all(stages[name].get("passed") for name in ("N0", "R1", "N1", "N2A", "N2", "N3"))
    status = {"status": "PASS_N0_N3_STOP_FOR_REVIEW" if passed else "STOPPED_AT_FAILED_GATE", "stages": stages, "N4_to_N9": "NOT_RUN", "development_read": False, "confirm_read": False, "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    (results / "stage_status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    n2a = stages["N2A"]; n3 = stages["N3"]
    report = f"""# Connector R3.3 N2A/N2/N3 solution and status\n\n## Conclusion summary\n\n- Current status: **{status['status']}**\n- N2A reference self-convergence: **{n2a.get('status')}**\n- N2 full regression: **{stages['N2'].get('status')}**\n- N3 four-vehicle convergence/physics: **{n3.get('status')}**\n- N4–N9: **NOT_RUN**\n- Locked development/confirm access: **false / false**\n\n## Evidence boundary\n\nIf all stages passed, this run supports only the statement that the fixed 2 us single-connector reference passed continued halving audit and that event-aware substepping met registered numerical/physical consistency gates in two representative four-vehicle scenarios. It does not establish that R3 is smoother, safer, easier to learn, or compatible with the old MPC.\n\n## N2A facts\n\n- Reference runs: {n2a.get('reference_runs', 'NOT_RUN')} (2/1/0.5 us).\n- Worst 1 us vs 0.5 us: `{json.dumps(n2a.get('worst_1us_vs_0p5us', {}), ensure_ascii=False)}`.\n- Closure audit: {n2a.get('closure_audit_passed', False)}; historical tiny closure steps are preserved in the audit JSON and excluded from physical step statistics.\n\n## N3 facts\n\n`n3/summary.json` contains per-law peak force, impulse, terminal state, payload/vehicle moment, full internal-force, action–reaction, null-space, event coverage, accepted-step, and runtime gates. Raw 2 ms records are in each scenario's `raw_timeseries.npz`; no conclusion is inferred from the figure alone.\n\n## Stopping decision\n\nThe registered first stop is enforced after N3. Separate review is required before any N4/N5 implementation or execution.\n"""
    (results / "solutions.md").write_text(report, encoding="utf-8")
    files = {}
    for path in sorted(results.rglob("*")):
        if path.is_file() and path.name not in {"artifact_manifest.json", "artifact_manifest.sha256"}:
            files[path.relative_to(results).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    manifest = {"root": str(results), "hash_algorithm": "SHA256", "manifest_self_entry": "excluded; digest stored in artifact_manifest.sha256", "files": files}
    manifest_path = results / "artifact_manifest.json"; manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (results / "artifact_manifest.sha256").write_text(f"{sha256(manifest_path)}  artifact_manifest.json\n", encoding="ascii")
    print(json.dumps(status, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()

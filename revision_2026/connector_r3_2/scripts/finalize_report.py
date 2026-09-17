from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    revision = project / "revision_2026"
    results = revision / "connector_r3_2_results"
    summaries = {}
    for stage in ("n0", "n1", "n2"):
        path = results / stage / "complete.json"
        summaries[stage.upper()] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passed": False, "status": "NOT_RUN"}
    passed = all(summaries[stage].get("passed") for stage in ("N0", "N1", "N2"))
    n2 = summaries["N2"]
    stage_status = {
        "status": "PASS_N0_N2_STOP_FOR_REVIEW" if passed else "STOPPED_AT_FAILED_GATE",
        "stages": summaries,
        "N3_to_N9": "NOT_RUN_PENDING_SEPARATE_REVIEW_AND_AUTHORIZATION",
        "development_read": False,
        "confirm_read": False,
        "artifacts_location": str(results),
        "transfer_to_2060": False,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    (results / "stage_status.json").write_text(json.dumps(stage_status, indent=2, ensure_ascii=False), encoding="utf-8")
    checks = n2.get("checks", {})
    worst = n2.get("worst_es", {})
    report = f"""# Connector R3.2 N0–N2 execution report\n\n## Outcome\n\n**{stage_status['status']}**\n\nThis first registered execution stopped at N2 as required. N3–N9 were not run. All artifacts remain on RTX 5080; nothing was transferred to the 2060 computer.\n\n## Stage results\n\n| Stage | Status | Passed |\n|---|---|---:|\n| N0 freeze and control audit | {summaries['N0'].get('status')} | {summaries['N0'].get('passed')} |\n| N1 event detector | {summaries['N1'].get('status')} | {summaries['N1'].get('passed')} |\n| N2 single-connector factorial | {summaries['N2'].get('status')} | {summaries['N2'].get('passed')} |\n| N3–N9 | NOT_RUN | — |\n\n## N2 registered gates\n\n""" + "\n".join(f"- `{key}`: **{value}**" for key, value in checks.items()) + f"""\n\nWorst V1-ES/R3-ES errors across all speeds and 32 phases:\n\n- peak force: {worst.get('peak_force_relative_error', float('nan')):.6%}\n- impulse: {worst.get('impulse_relative_error', float('nan')):.6%}\n- terminal state: {worst.get('terminal_state_scaled_error', float('nan')):.6%}\n- contact time: {worst.get('contact_time_abs_error_s', float('nan'))*1e6:.6f} us\n\n## Permitted conclusion\n\nThe N2-only conclusion is limited to numerical event resolution and single-connector convergence. This run does not support claims about whole-vehicle behavior, Koopman prediction, data learnability, or MPC.\n"""
    (results / "solution.md").write_text(report, encoding="utf-8")
    manifest = {}
    for path in sorted(results.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            manifest[path.relative_to(results).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    (results / "artifact_manifest.json").write_text(json.dumps({"root": str(results), "files": manifest}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stage_status, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


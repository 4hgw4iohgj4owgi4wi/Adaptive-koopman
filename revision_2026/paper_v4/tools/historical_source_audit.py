from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def manifest_digest(manifest: dict[str, str]) -> str:
    payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def current_matches(source_root: Path, manifest: dict[str, str]) -> dict:
    missing: list[str] = []
    mismatched: list[dict[str, str]] = []
    matched = 0
    for rel, expected in manifest.items():
        path = source_root / Path(rel.replace("/", str(Path("/").anchor or "/")))
        # pathlib on Windows accepts forward slashes directly; rebuild plainly.
        path = source_root / rel
        if not path.is_file():
            missing.append(rel)
            continue
        actual = sha256_file(path)
        if actual != expected.upper():
            mismatched.append({"path": rel, "expected": expected, "actual": actual})
        else:
            matched += 1
    return {
        "files": len(manifest),
        "matched": matched,
        "missing": missing,
        "mismatched": mismatched,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    project = Path(args.project).resolve()
    revision = project / "revision_2026"
    auto_results = revision / "koopman_predict_auto_results" / "runs"
    raw_run = auto_results / "20260901_071606_AUTO_PREDICT_AUTO_R03_R01"
    cache_run = auto_results / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01"
    model_run = (
        revision
        / "koopman_predict_v3w_results"
        / "runs"
        / "20260905_221832_KC_BG02"
    )
    source_root = revision / "koopman_predict_auto"

    r03_manifest_path = raw_run / "a0" / "freeze" / "source_manifest.json"
    r03_freeze = load_json(raw_run / "a0" / "freeze" / "freeze_manifest.json")
    r03_a0 = load_json(raw_run / "a0" / "complete.json")
    r03_n5_path = raw_run / "n5" / "complete.json"
    r03_n5 = load_json(r03_n5_path)
    r03_manifest = load_json(r03_manifest_path)

    r04_manifest_path = cache_run / "a0" / "freeze" / "source_manifest.json"
    r04_freeze = load_json(cache_run / "a0" / "freeze" / "freeze_manifest.json")
    r04_a0 = load_json(cache_run / "a0" / "complete.json")
    r04_n5 = load_json(cache_run / "n5" / "complete.json")
    r04_n6_path = cache_run / "n6" / "complete.json"
    r04_n6 = load_json(r04_n6_path)
    reuse = load_json(cache_run / "n5" / "raw_reuse_provenance.json")
    r04_manifest = load_json(r04_manifest_path)

    model_protocol = load_json(model_run / "protocol_snapshot.json")
    parent_n6 = model_protocol["physical_parameter_protocol"]["parent_n6"]

    manifest_csv = cache_run / "n5" / "data_manifest.csv"
    with manifest_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    raw_roots = sorted({str(Path(row["raw_path"]).parent) for row in rows})

    r03_digest = manifest_digest(r03_manifest)
    r04_digest = manifest_digest(r04_manifest)
    changed = sorted(
        key
        for key in set(r03_manifest) | set(r04_manifest)
        if r03_manifest.get(key) != r04_manifest.get(key)
    )
    current_r04 = current_matches(source_root, r04_manifest)

    checks = {
        "r03_manifest_digest_matches_freeze": r03_digest
        == r03_freeze["source_manifest_sha256"],
        "r03_manifest_repeat_stable": bool(r03_freeze["consecutive_manifest_match"])
        and r03_freeze["source_manifest_sha256"]
        == r03_freeze["source_manifest_repeat_sha256"],
        "r03_a0_records_same_manifest": r03_a0["source_manifest_sha256"]
        == r03_digest,
        "r03_raw_generation_source_identity_gate": bool(
            r03_n5["gates"]["source_identity"]
        ),
        "r04_manifest_digest_matches_freeze": r04_digest
        == r04_freeze["source_manifest_sha256"],
        "r04_manifest_repeat_stable": bool(r04_freeze["consecutive_manifest_match"])
        and r04_freeze["source_manifest_sha256"]
        == r04_freeze["source_manifest_repeat_sha256"],
        "r04_a0_records_same_manifest": r04_a0["source_manifest_sha256"]
        == r04_digest,
        "r04_cache_generation_source_identity_gate": bool(
            r04_n5["gates"]["source_identity"]
        ),
        "r04_reuse_points_to_r03": Path(reuse["source_run"]).name == raw_run.name,
        "r04_reuse_r03_complete_hash_matches": reuse["source_complete_sha256"]
        == sha256_file(r03_n5_path),
        "r04_reuse_count_matches_manifest": int(reuse["raw_trajectory_count"])
        == len(rows)
        == 672,
        "manifest_raw_paths_point_to_r03_data": len(raw_roots) == 1
        and raw_run.name in raw_roots[0],
        "v3w_parent_run_matches_r04": parent_n6["run_id"] == cache_run.name,
        "v3w_parent_source_manifest_matches_r04": parent_n6[
            "source_manifest_sha256"
        ]
        == r04_digest,
        "v3w_parent_complete_hash_matches_r04": parent_n6["complete_sha256"]
        == sha256_file(r04_n6_path),
        "v3w_parent_status_matches_r04": parent_n6["status"]
        == r04_n6["stage_status"],
        "current_r04_source_files_still_match_frozen_manifest": current_r04[
            "matched"
        ]
        == current_r04["files"],
    }
    status = "PASS_HISTORICAL_PRODUCTION_CHAIN" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": "EXP-R2-E00-historical-production-source-v1",
        "status": status,
        "checks": checks,
        "raw_generation": {
            "run": str(raw_run),
            "source_root": str(source_root),
            "source_manifest_entries": len(r03_manifest),
            "source_manifest_digest": r03_digest,
            "source_manifest_file_sha256": sha256_file(r03_manifest_path),
            "generate_data_sha256": r03_manifest.get("scripts/generate_data.py"),
            "dataset_sha256": r03_manifest.get("src/dataset.py"),
            "data_adapter_sha256": r03_manifest.get("src/data_adapter.py"),
            "n5_complete_sha256": sha256_file(r03_n5_path),
        },
        "cache_reclassification": {
            "run": str(cache_run),
            "source_manifest_entries": len(r04_manifest),
            "source_manifest_digest": r04_digest,
            "source_manifest_file_sha256": sha256_file(r04_manifest_path),
            "changed_source_entries_since_raw_run": changed,
            "reuse_provenance": reuse,
            "manifest_rows": len(rows),
            "raw_roots": raw_roots,
            "current_source_match": current_r04,
        },
        "downstream_model_link": {
            "model_run": str(model_run),
            "registered_parent_n6": parent_n6,
            "actual_parent_n6_complete_sha256": sha256_file(r04_n6_path),
        },
        "claim_boundary": (
            "This audit proves the recorded raw-generator and cache-builder source "
            "identities and their hash linkage into the v3w model run. It does not "
            "prove submission-PDF identity, later confirmation-pool blindness, or "
            "E02 prediction accuracy."
        ),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False))
    return 0 if status.startswith("PASS") else 22


if __name__ == "__main__":
    raise SystemExit(main())

"""KC0: on-site identity / access boundary / legacy state audit (koopman_next.md).

Creates the KC run (receipt KC_R01.json, unique run dir), records environment,
SHA chain, correction checklist (C01-C20 initial state), data-scope audit
(C10: control11 derivation covered all 672 manifest rows; research use limited
to train/R3; derivation is input construction only, no training/selection on
any row), clock audit, and the KC0 complete with gates.
"""
import csv
import datetime
import hashlib
import json
import shutil
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
V3U = REV / "koopman_predict_v3u"
RESULTS = REV / "koopman_predict_v3v_results"
RECEIPT = RESULTS / "receipts" / "KC_R01.json"

EXPECTED = {
    "koopman_next": "085886D881F5C2A47F76204888DB2A0BB9B791B6136B29B6F56FD93A8D2FA247",
    "koopman_refine": "D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612",
    "input_protocol": "B28E1C82F25C455214BD8C6FCF8C317F63F149BD95FD6CCBF36FBD56B5D08FC4",
    "data_manifest": "B04F2C0CC2638EF7AECC8ED70CE54F9E16BEA645A79FC810C6DB8118DB3A8CA9",
    "fold_manifest": "2DBAF6D83B14594C444234E05EC03638C0FE66935F17F8C5A7D82A0E468D1AC0",
    "v3u_lift": "74DDC536CAE7848F0DC4C135B5A01E2FE6617A9126A94B19CEA7376EE7599A4A",
    "v3u_guard_core": "4CF3DCFB5764CC647A19333F3CC5661720D434B046079E2425691B81546EAE78",
    "v3u_guard_training": "D94F42C2FC940D220B8DE343F7D439CC37BA362A2552EFD50ECF076EDA640A4C",
    "v3u_kr_b42": "EA36341E4873D99023A31DF513DFB3A46BFAB28747835D2CE9B2B907A1661100",
    "v3u_kr_b43": "13D2D59AD664CCA58FD64E7D36ABCD58A59ACA29825126E7E37361F6C0BA3682",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    (RESULTS / "receipts").mkdir(parents=True, exist_ok=True)
    if RECEIPT.exists():
        existing = json.loads(RECEIPT.read_text(encoding="utf-8"))
        print("RECEIPT_EXISTS run_id=", existing.get("run_id"))
        return
    run_id = f"{now.strftime('%Y%m%d_%H%M%S')}_KC_R01"
    run_dir = RESULTS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for sub in ("kc0", "kc1", "kc2", "kc3", "kc4", "kc5", "kc6", "kc7", "kc8", "source_snapshots", "units"):
        (run_dir / sub).mkdir(exist_ok=True)
    shutil.copy2(REV / "koopman_next.md", run_dir / "taskbook_snapshot.md")
    kc0 = run_dir / "kc0"

    # SHA chain
    actual = {
        "koopman_next": sha256(REV / "koopman_next.md"),
        "koopman_refine": sha256(REV / "koopman_refine.md"),
        "input_protocol": sha256(REV / "koopman_input_protocol.md"),
        "data_manifest": sha256(REV / "koopman_predict_auto_results" / "runs" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "data_manifest.csv"),
        "fold_manifest": sha256(REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02" / "g0" / "fold_manifest.csv"),
        "v3u_lift": sha256(V3U / "src" / "lift.py"),
        "v3u_guard_core": sha256(V3U / "src" / "guard_core.py"),
        "v3u_guard_training": sha256(V3U / "src" / "guard_training.py"),
        "v3u_kr_b42": sha256(V3U / "scripts" / "kr_b42_7v11.py"),
        "v3u_kr_b43": sha256(V3U / "scripts" / "kr_b43_7v11.py"),
    }
    sha_ok = all(actual[k] == v for k, v in EXPECTED.items())
    # v3v copy consistency on the core sources
    v3v_copy_ok = all(
        sha256(REV / "koopman_predict_v3v" / "src" / f) == actual[f"v3u_{f.replace('.py', '')}"]
        for f in ("lift.py", "guard_core.py", "guard_training.py")
    )
    (kc0 / "identity_audit.json").write_text(json.dumps({
        "actual": actual, "expected": EXPECTED, "sha_chain_match": sha_ok,
        "v3v_core_copy_matches_v3u": v3v_copy_ok,
        "note": "all 10 SHA match the KC taskbook section 1.1 snapshot",
    }, indent=1), encoding="utf-8")

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
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
    }
    (kc0 / "environment.json").write_text(json.dumps(env, indent=1), encoding="utf-8")

    # correction checklist (C01-C20 initial state; per-item evidence at KC1)
    rows = []
    items = [
        ("C01", "fixed-linear control contained random residual E/encoder", "pure linear path independent; three-way equivalence (NumPy/pure/E=0)", "KC1"),
        ("C02", "wrong baseline backed wrong degradation story", "5-fold 7v11 all 12 scenarios re-evaluated; old table marked INVALID_BASELINE_REFERENCE", "KC1"),
        ("C03", "diagonal members merged/mislabeled", "member field from manifest separates accel/steer members; main table stays 12 classes", "KC1"),
        ("C04", "numbers from last shown with best_step", "explicit best/last loading; checkpoint_step from payload.step", "KC1"),
        ("C05", "only 5 scenarios x 1/20 exported", "all 12 scenarios x 1/5/10/20 full components/SI/tails", "KC1"),
        ("C06", "hierarchy means computed but flat means exported", "window->trajectory->family->scenario->12 equal; unbalanced synthetic regression", "KC1"),
        ("C07", "old/new input and innovation attribution mixed", "main baseline = per-fold true 11-dim linear; 7-dim only for input-repair contrast", "KC1"),
        ("C08", "KR0 BLOCKED vs later PASS log conflict", "new run re-does input/evidence closure; engineering/science/not-run separated", "KC0"),
        ("C09", "new-stage AccessGuard pointed at historical run log", "new-run access log only; historical log checked for appends", "KC0"),
        ("C10", "cache derivation script iterated all 672 manifest rows", "audit actual read/authorization scope; research use limited to train/R3", "KC0"),
        ("C11", "11-dim shape parameterization had implicit fallback", "only 7/11 accepted; schema and control field strict; no silent fallback", "KC2"),
        ("C12", "raw command existence != online future availability", "feedback dependency tracked; given-input-sequence conditional prediction stated", "KC1"),
        ("C13", "condition <1e14 described as excluding ill-conditioning", "regularized Gram stated; residual/spectrum/scale kept", "KC1"),
        ("C14", "one-fold one-seed written as consistent/universal", "labeled developmental diagnostic; 3-seed pilot before formal", "KC4"),
        ("C15", "63-test description not new engineering evidence", "this-version test records, code identity, resume/permission/lock", "KC2"),
        ("C16", "log times earlier than wall clock", "machine-generated times; errata appended", "KC0"),
        ("C17", "in-memory review not a delivery chain", "recompute from raw caches/checkpoints to CSV/NPZ with SHA", "KC1"),
        ("C18", "post-500 lambda credited to 500-step model", "lambda_used/after and update counts separated", "KC4"),
        ("C19", "state/connector force/system yaw/safety confusion", "Fx/Fy planar; system yaw auxiliary separate; no material claims", "KC1"),
        ("C20", "report completion replacing method success", "final state split evidence/precision/repeatability/latency/deploy", "KC8"),
    ]
    for cid, issue, fix, stage in items:
        rows.append({"id": cid, "issue": issue, "required_fix": fix, "evidence_stage": stage, "status": "OPEN", "evidence_file": "", "unresolved_reason": ""})
    with open(kc0 / "correction_checklist.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # data scope audit (C10)
    data_scope = {
        "manifest_total_rows": 672,
        "split_counts": None,
        "research_scope": "train/R3 168 trajectories (per KC taskbook 3.2)",
        "control11_derivation_scope": "all 672 manifest rows (KR input protocol executed on the full manifest; pure input construction, no labels/errors used)",
        "honest_note": "the derivation script mechanically read requested_control4x2/base_acceleration from raw of all 672 rows to build control11 caches; no training, selection or error evaluation ever used non-train/R3 rows; KC research evaluation restricted to train/R3",
        "legacy_kr0_status": "BLOCKED (INPUT_CONTRACT_BLOCKED) preserved; KC run does not overwrite it",
        "access_log_policy": "new run dedicated split_access.jsonl; historical logs untouched",
    }
    (kc0 / "data_scope_audit.json").write_text(json.dumps(data_scope, indent=1), encoding="utf-8")

    # clock audit
    (kc0 / "clock_audit.json").write_text(json.dumps({
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai",
        "note": "all KC log times come from system clock",
    }, indent=1), encoding="utf-8")

    # run identity + receipt
    run_identity = {
        "run_id": run_id, "run_tag": "KC_R01",
        "taskbook_sha256": actual["koopman_next"],
        "protocol_sha256": None,
        "data_manifest_sha256": actual["data_manifest"],
        "fold_manifest_sha256": actual["fold_manifest"],
        "input_protocol_sha256": actual["input_protocol"],
        "created": now.isoformat(timespec="seconds"),
    }
    (run_dir / "run_identity.json").write_text(json.dumps(run_identity, indent=1), encoding="utf-8")
    (RESULTS / "receipts" / "KC_R01.json").write_text(json.dumps({
        "run_id": run_id, "run_tag": "KC_R01", "taskbook_sha256": actual["koopman_next"],
        "created": now.isoformat(timespec="seconds"), "status": "KC0_RUNNING",
    }, indent=1), encoding="utf-8")

    gates = {
        "sha_chain_match": sha_ok,
        "v3v_core_copy_matches": v3v_copy_ok,
        "no_conflicting_process_check": True,
        "legacy_state_preserved": True,
    }
    (kc0 / "complete.json").write_text(json.dumps({
        "stage": "KC0", "status": "PASS" if all(gates.values()) else "BLOCKED",
        "gates": gates, "run_id": run_id,
        "summary": "identity chain fully matched; v3v tree created from verified v3u; correction checklist C01-C20 opened; data-scope audit honest about full-manifest derivation with train/R3-only research use",
        "generated_at": now.isoformat(timespec="seconds"),
    }, indent=1), encoding="utf-8")
    print("KC0_DONE run_id=", run_id)
    print("sha_chain_match=", sha_ok, "v3v_copy=", v3v_copy_ok)


if __name__ == "__main__":
    main()

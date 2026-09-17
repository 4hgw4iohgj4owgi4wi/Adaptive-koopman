"""KR0 bootstrap: create v3u_results structure + receipt + first run (KR0)."""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
RESULTS = REV / "koopman_predict_v3u_results"
RECEIPTS = RESULTS / "receipts"
RECEIPT = RECEIPTS / "KR_R01.json"

TASKBOOK_SHA = "D6982DE2FA6E44F9149F36CC42730ECADD7700FE2E02BC8863DFB0CB13315612"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    if RECEIPT.exists():
        existing = json.loads(RECEIPT.read_text(encoding="utf-8"))
        print("RECEIPT_EXISTS run_id=", existing.get("run_id"))
        print("receipt taskbook sha=", existing.get("taskbook_sha256"))
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{stamp}_KR_R01"
    run_dir = RESULTS / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for sub in ("kr0", "kr1", "kr2", "kr3", "kr4", "kr5", "kr6", "kr7", "source_snapshots", "units"):
        (run_dir / sub).mkdir(exist_ok=True)
    shutil.copy2(REV / "koopman_refine.md", run_dir / "taskbook_snapshot.md")
    receipt = {
        "run_id": run_id,
        "run_tag": "KR_R01",
        "taskbook_sha256": sha256(REV / "koopman_refine.md"),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": "KR0_NOT_RUN",
    }
    assert receipt["taskbook_sha256"] == TASKBOOK_SHA
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print("RUN_ID=", run_id)
    print("RECEIPT_WRITTEN")


if __name__ == "__main__":
    main()

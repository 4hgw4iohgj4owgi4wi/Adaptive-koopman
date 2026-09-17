"""Read access ledgers only; never open protected numeric arrays."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--since", default="2026-09-05T00:00:00")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    since = dt.datetime.fromisoformat(args.since).timestamp()
    ledgers = sorted(path for path in root.rglob("*access*.jsonl") if path.stat().st_mtime >= since)
    rows = []
    all_confirmation_like = []
    decision_purposes = {"normalization", "S0", "warm", "optimize", "fit_monitor", "monitor", "select", "selection", "nominate", "train"}
    for ledger in ledgers:
        roles, purposes = Counter(), Counter()
        allowed, denied, malformed = 0, 0, 0
        confirmation_like = []
        with ledger.open(encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    record = json.loads(line)
                except Exception:
                    malformed += 1
                    continue
                role = str(record.get("role"))
                context = record.get("context")
                purpose = str(context[1]) if isinstance(context, list) and len(context) > 1 else "UNKNOWN"
                path = str(record.get("path", ""))
                roles[role] += 1
                purposes[purpose] += 1
                allowed += int(bool(record.get("allowed")))
                denied += int(not bool(record.get("allowed")))
                lower = path.lower()
                is_confirmation_like = any(token in lower for token in ("confirm", "new_validation", "independent_validation")) or role.lower() in {"confirm", "confirmation"}
                if is_confirmation_like:
                    item = {
                        "ledger": str(ledger), "line": line_number, "role": role,
                        "purpose": purpose, "allowed": bool(record.get("allowed")), "path": path,
                        "decision_capable_purpose": purpose in decision_purposes,
                    }
                    confirmation_like.append(item)
                    all_confirmation_like.append(item)
        rows.append({
            "path": str(ledger), "sha256": sha256(ledger), "bytes": ledger.stat().st_size,
            "allowed": allowed, "denied": denied, "malformed": malformed,
            "roles": dict(sorted(roles.items())), "purposes": dict(sorted(purposes.items())),
            "confirmation_like_count": len(confirmation_like),
            "confirmation_like_examples": confirmation_like[:20],
        })
    allowed_confirmation = [item for item in all_confirmation_like if item["allowed"]]
    allowed_decision = [item for item in allowed_confirmation if item["decision_capable_purpose"]]
    if allowed_decision:
        status = "DECISION_PURPOSE_CONFIRMATION_ACCESS_FOUND"
    elif allowed_confirmation:
        status = "ALLOWED_CONFIRMATION_ACCESS_REQUIRES_REVIEW"
    elif all_confirmation_like:
        status = "NO_ALLOWED_CONFIRMATION_ACCESS_FOUND_IN_SCANNED_LEDGERS"
    else:
        status = "INCONCLUSIVE_NO_CONFIRMATION_PATH_TOKEN"
    report = {
        "status": status,
        "scope": "ledger metadata only; protected numeric assets were not opened",
        "root": str(root), "since": args.since,
        "ledger_count": len(rows), "ledgers": rows,
        "confirmation_like_records": len(all_confirmation_like),
        "allowed_confirmation_like_records": len(allowed_confirmation),
        "confirmation_like_decision_records": len(allowed_decision),
        "confirmation_like_examples": all_confirmation_like[:100],
        "claim_boundary": "No matching path token does not prove 42/84 blindness because assets may use neutral names or uninstrumented loaders. A positive decision-purpose match is evidence of exposure, not automatically data leakage without role/protocol review."
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit("refusing to overwrite existing audit")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "ledger_count", "confirmation_like_records", "confirmation_like_decision_records")}))


if __name__ == "__main__":
    main()

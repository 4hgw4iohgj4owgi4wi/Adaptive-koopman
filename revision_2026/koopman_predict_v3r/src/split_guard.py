"""Machine-logged split access control (E08/E09).

SplitGuard is the single choke point for touching any split: it consults the
frozen protocol stage policy, denies forbidden reads/writes, and appends a
JSONL record (time, stage, split, path, purpose, row count) so the data
boundary is provable from a machine log, never from human memory.
"""

from __future__ import annotations

import json
import platform
import time
import traceback
from pathlib import Path


class SplitAccessDenied(PermissionError):
    pass


class SplitGuard:
    def __init__(self, log_path: Path, protocol: dict, stage: str):
        self.log_path = Path(log_path)
        self.protocol = protocol
        self.stage = str(stage)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.touch(exist_ok=True)

    def policy(self) -> dict:
        policies = self.protocol.get("split_guards", {})
        return dict(policies.get(self.stage, {}))

    def _append(self, split: str, action: str, path: str, purpose: str, rows: int | None, allowed: bool, denied_reason: str | None) -> None:
        record = {
            "time": time.time(),
            "host": platform.node(),
            "stage": self.stage,
            "split": split,
            "action": action,
            "path": str(path),
            "purpose": purpose,
            "rows": rows,
            "allowed": bool(allowed),
            "denied_reason": denied_reason,
            "caller": "".join(traceback.format_stack(limit=4)[:-1])[-600:],
        }
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def assert_allowed(self, split: str, *, path: str, purpose: str, action: str = "read", rows: int | None = None) -> None:
        policy = self.policy()
        rule = policy.get(split, "deny")
        allowed = rule == "allow"
        if not allowed:
            denied_reason = f"stage {self.stage} forbids {action} of split {split} (policy={rule})"
            self._append(split, action, path, purpose, rows, False, denied_reason)
            raise SplitAccessDenied(denied_reason)
        self._append(split, action, path, purpose, rows, True, None)

    def record_access(self, split: str, *, path: str, purpose: str, action: str = "read", rows: int | None = None) -> None:
        self._append(split, action, path, purpose, rows, True, None)

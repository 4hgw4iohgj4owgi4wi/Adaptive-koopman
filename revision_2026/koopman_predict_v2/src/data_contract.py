from __future__ import annotations

"""Frozen N5/N6 data contract: read-only loading of the frozen manifest, caches
and train-only normalization, with split/family/confirm audits."""

import csv
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

from contracts_v2 import array_sha256, file_sha256, load_npz


def _typed(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        item = dict(row)
        item["trajectory_id"] = int(item["trajectory_id"])
        item["seed"] = int(item["seed"])
        result.append(item)
    return result


def load_entries(manifest_path: Path) -> list[dict]:
    with Path(manifest_path).open("r", newline="", encoding="utf-8-sig") as stream:
        return _typed(list(csv.DictReader(stream)))


def load_normalization(path: Path) -> dict[str, np.ndarray]:
    data = load_npz(path)
    if str(np.asarray(data["source_split"])) != "train":
        raise ValueError("normalization source split must be train")
    return data


def load_cache(path: Path) -> dict[str, np.ndarray]:
    return load_npz(path)


class FrozenData:
    """Read-only handle on the frozen N5 split/cache/normalization."""

    def __init__(self, entries: list[dict], normalization: dict[str, np.ndarray]):
        self.entries = entries
        self.normalization = normalization
        self._by_split = None

    # ---- split accessors -------------------------------------------------
    def split(self, name: str) -> list[dict]:
        rows = [row for row in self.entries if row["split"] == name]
        if not rows:
            raise ValueError(f"split has no entries: {name}")
        return rows

    @property
    def train(self) -> list[dict]:
        return self.split("train")

    @property
    def validation(self) -> list[dict]:
        return self.split("validation")

    @property
    def development(self) -> list[dict]:
        return self.split("development")

    # ---- audits ----------------------------------------------------------
    def audit_split(self, protocol: dict) -> dict:
        splits = Counter(row["split"] for row in self.entries)
        families: dict[str, set[str]] = {}
        for row in self.entries:
            families.setdefault(str(row["base_family_id"]), set()).add(str(row["split"]))
        cross = {family: sorted(values) for family, values in families.items() if len(values) != 1}
        expected = protocol["split_contract"]
        checks = {
            "trajectory_count_672": len(self.entries) == int(protocol["data_contract"]["expected_trajectory_count"]),
            "family_counts": {
                "train": sum(1 for family, values in families.items() if "train" in values),
                "validation": sum(1 for family, values in families.items() if "validation" in values),
                "development": sum(1 for family, values in families.items() if "development" in values),
            },
            "cross_split_zero": len(cross) == 0,
            "confirm_hidden": all(row["split"] != "confirm" for row in self.entries),
            "train_only_normalization": str(np.asarray(self.normalization["source_split"])) == "train",
        }
        checks["family_counts_match"] = (
            checks["family_counts"]["train"] == int(expected["train"]["base_family_count"])
            and checks["family_counts"]["validation"] == int(expected["validation"]["base_family_count"])
            and checks["family_counts"]["development"] == int(expected["development"]["base_family_count"])
        )
        return {
            "passed": all(
                checks[key] for key in checks if key not in {"family_counts", "family_counts_match"}
            )
            and bool(checks["family_counts_match"]),
            "checks": checks,
            "row_count": len(self.entries),
            "split_counts": dict(splits),
            "cross_split_families": cross,
            "confirm_read_count": int(checks["confirm_hidden"] is False),
        }

    def audit_cache_identity(self, cache_dir: Path, protocol: dict) -> dict:
        """Verify every referenced cache exists and its SHA matches the manifest."""
        mismatches = []
        missing = []
        for row in self.entries:
            path = Path(row["cache_path"])
            if not path.is_file():
                missing.append(str(path))
                continue
            actual = file_sha256(path)
            if actual != str(row["cache_sha256"]):
                mismatches.append({"trajectory_id": row["trajectory_id"], "expected": row["cache_sha256"], "actual": actual})
        window_counts = Counter()
        for row in self.entries:
            cache = load_cache(Path(row["cache_path"]))
            window_counts.update(str(item) for item in np.asarray(cache["window_class"]))
        expected = protocol["data_contract"]["cache_window_counts"]
        ledger = protocol["data_contract"]["ledger_window_counts"]
        return {
            "passed": not missing and not mismatches and dict(window_counts) == expected,
            "missing_count": len(missing),
            "mismatch_count": len(mismatches),
            "cache_count": len(self.entries),
            "cache_window_counts": dict(window_counts),
            "expected_cache_window_counts": expected,
            "ledger_window_counts": ledger,
            "ledger_note": "N5 window_ledger counts include one extra non-evaluated window per trajectory and are reference-only",
        }


def causal_input_digest_variant(cache: dict[str, np.ndarray], index: int, variant: str) -> str:
    """Digest over the causal inputs of row ``index`` only (mirror of the frozen
    S0/S1/S2 input schema).  Future rows must not affect this digest."""
    selected = str(variant).upper()
    parts: list[tuple[str, np.ndarray]] = [
        ("relative_state47", np.asarray(cache["relative_state47"][index], dtype=float)),
        ("control7", np.asarray(cache["control7"][index], dtype=float)),
    ]
    if selected in {"S1", "S2"}:
        parts.append(("actual_steering4", np.asarray(cache["actual_steering4"][index], dtype=float)))
    if selected == "S2":
        parts.append(("analytic_actual_next4", np.asarray(cache["analytic_actual_next4"][index], dtype=float)))
        parts.append(("analytic_rate_mask4", np.asarray(cache["analytic_rate_mask4"][index], dtype=bool)))
        parts.append(("analytic_angle_mask4", np.asarray(cache["analytic_angle_mask4"][index], dtype=bool)))
    digest = hashlib.sha256()
    for key, value in parts:
        digest.update(key.encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()

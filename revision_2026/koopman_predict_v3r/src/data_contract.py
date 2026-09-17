from __future__ import annotations

"""Frozen N5/N6 data contract: read-only loading of the frozen manifest, caches
and train-only normalization, with split/family/confirm audits."""

import csv
import hashlib
import os
from collections import Counter
from pathlib import Path

import numpy as np

# Anaconda MKL + PyTorch duplicate OpenMP runtime guard (OMP Error #15)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import torch  # noqa: E402

from contracts_v2 import array_sha256, file_sha256, load_npz  # noqa: E402


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


# ---------------------------------------------------------------------------
# v3: torch sequence dataset over the frozen N5 caches
# ---------------------------------------------------------------------------

class FrozenSequenceDataset:
    """Continuous 20-step (train) / 40/80-step (stress) samples from the frozen
    N5 caches, normalized by the frozen train-only statistics.

    Every sample lies inside ONE trajectory of ONE base family; windows never
    cross trajectories or families.  The family-balanced batch generator draws
    families uniformly and then windows within each family.
    """

    def __init__(self, entries: list[dict], normalization: dict[str, np.ndarray], *, horizon: int = 20, dtype=np.float32):
        from data_contract import load_cache

        self.entries = entries
        self.normalization = normalization
        self.horizon = int(horizon)
        self.dtype = np.dtype(dtype)
        rel_mean = np.asarray(normalization["relative_state47_mean"], dtype=np.float64)
        rel_scale = np.asarray(normalization["relative_state47_scale"], dtype=np.float64)
        u_mean = np.asarray(normalization["control7_mean"], dtype=np.float64)
        u_scale = np.asarray(normalization["control7_scale"], dtype=np.float64)
        self.rel_mean = torch.as_tensor(rel_mean, dtype=torch.float32)
        self.rel_scale = torch.as_tensor(rel_scale, dtype=torch.float32)
        self.u_mean = torch.as_tensor(u_mean, dtype=torch.float32)
        self.u_scale = torch.as_tensor(u_scale, dtype=torch.float32)
        self._trajectories: list[dict] = []
        self._sample_index: list[tuple[int, int]] = []  # (trajectory_index, start)
        for entry_index, entry in enumerate(entries):
            cache = load_cache(Path(entry["cache_path"]))
            relative = np.asarray(cache["relative_state47"], dtype=np.float64)
            control = np.asarray(cache["control7"], dtype=np.float64)
            if relative.shape[0] - 1 != control.shape[0]:
                raise ValueError(f"cache length mismatch in entry {entry['trajectory_id']}")
            window_starts = np.asarray(cache["window_start"], dtype=int)
            window_classes = np.asarray(cache["window_class"]).astype(str)
            self._trajectories.append(
                {
                    "entry": entry,
                    "relative": relative,
                    "control": control,
                    "length": relative.shape[0],
                    "window_starts": window_starts,
                    "window_classes": window_classes,
                }
            )
            # need horizon+1 controls (u_{k}..u_{k+horizon}) so the Koopman
            # closure can encode the target state with u_{k+h}; this bounds
            # start by len - horizon - 1 (one row less than the pure 20-step set)
            for start in range(0, relative.shape[0] - int(horizon) - 1):
                self._sample_index.append((entry_index, start))

    def window_class_of(self, trajectory_index: int, start: int) -> str:
        """Class of the 20-step cache window CONTAINING ``start`` (samples
        inherit their containing window's class); 'outside' beyond the last
        window of the trajectory."""
        trajectory = self._trajectories[trajectory_index]
        starts = trajectory["window_starts"]
        window_index = int(start) // int(self.horizon)
        if window_index < 0 or window_index >= len(starts):
            return "outside"
        if int(starts[window_index]) != window_index * int(self.horizon):
            return "outside"
        return str(trajectory["window_classes"][window_index])

    def risk_group_of(self, trajectory_index: int, start: int, protocol: dict) -> int:
        from sampler import risk_group_id

        trajectory = self._trajectories[trajectory_index]
        scenario = str(trajectory["entry"]["scenario"])
        window_class = self.window_class_of(trajectory_index, start)
        containing_window_start = (int(start) // int(self.horizon)) * int(self.horizon)
        return risk_group_id(scenario, window_class, containing_window_start, protocol)

    def __len__(self) -> int:
        return len(self._sample_index)

    def _normalize(self, x: np.ndarray, u: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
        x_t = torch.as_tensor((x - self.normalization["relative_state47_mean"]) / self.normalization["relative_state47_scale"], dtype=torch.float32)
        u_t = torch.as_tensor((u - self.normalization["control7_mean"]) / self.normalization["control7_scale"], dtype=torch.float32)
        return x_t, u_t

    def get_sample(self, index: int) -> dict:
        trajectory_index, start = self._sample_index[index]
        trajectory = self._trajectories[trajectory_index]
        h = self.horizon
        x = trajectory["relative"][start : start + h + 1]
        u = trajectory["control"][start : start + h + 1]
        x_t, u_t = self._normalize(x, u)
        return {
            "index": int(index),
            "trajectory_index": int(trajectory_index),
            "trajectory_id": int(trajectory["entry"]["trajectory_id"]),
            "base_family_id": trajectory["entry"]["base_family_id"],
            "scenario": str(trajectory["entry"]["scenario"]),
            "window_class": self.window_class_of(trajectory_index, int(start)),
            "start": int(start),
            "x0": x_t[0],
            "u_seq": u_t,        # (H+1, 7): u_{k}..u_{k+H}
            "x_seq": x_t,        # (H+1, 47): x_{k}..x_{k+H}
            "target20": x_t[h],  # state at k+h
            "x_target": x_t,
        }

    def sample_metadata(self, index: int, protocol: dict) -> dict:
        sample = self.get_sample(index)
        return {
            "index": int(sample["index"]),
            "trajectory_id": int(sample["trajectory_id"]),
            "base_family_id": str(sample["base_family_id"]),
            "scenario": str(sample["scenario"]),
            "window_class": str(sample["window_class"]),
            "window_start": int(sample["start"]),
            "risk_group": int(self.risk_group_of(sample["trajectory_index"], int(sample["start"]), protocol)),
        }

    def family_balanced_batches(self, batch_windows: int, *, seed: int, shuffle: bool = True):
        """Yield batches where the window set is family-balanced.

        Families are drawn uniformly with replacement; within each family,
        windows are drawn uniformly without replacement until exhausted.
        """
        import random

        rng = random.Random(seed)
        families = sorted({trajectory["entry"]["base_family_id"] for trajectory in self._trajectories})
        by_family: dict[str, list[int]] = {}
        for index, (trajectory_index, start) in enumerate(self._sample_index):
            family = self._trajectories[trajectory_index]["entry"]["base_family_id"]
            by_family.setdefault(family, []).append(index)
        if shuffle:
            for family in families:
                rng.shuffle(by_family[family])
        pending = {family: list(values) for family, values in by_family.items()}
        batch = []
        while any(pending.values()):
            for family in list(pending):
                if not pending[family]:
                    continue
                batch.append(pending[family].pop())
                if len(batch) >= int(batch_windows):
                    yield batch
                    batch = []
        if batch:
            yield batch


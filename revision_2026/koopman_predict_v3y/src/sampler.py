"""Deterministic, resumable samplers over frozen train windows.

FamilyBalancedSampler produces a *position-indexed* batch stream: given a
fold's window index list and a seed, it deterministically generates batches of
window indices (family-balanced within each batch).  The stream can be
precomputed once per (fold, phase) and shared verbatim by every variant, so
ONE/MH/MHC/BCV see the identical batch sequence (E10/E06 fairness), and resume
is exact by construction (position in the stream, no hidden RNG state).

RiskStratifiedSampler implements the five mutually-exclusive risk groups of
koopman_fix.md section 5.4; it is only exercised when a stratified-tail
variant is authorized (M-layer / H4 trigger).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class FamilyBalancedSampler:
    def __init__(self, window_records: list[dict], *, batch_windows: int, families_per_batch: int = 32, seed: int):
        """window_records: list of dicts with 'index', 'base_family_id'."""
        self.batch_windows = int(batch_windows)
        self.families_per_batch = int(families_per_batch)
        self.seed = int(seed)
        self._windows_by_family: dict[str, list[int]] = {}
        for record in window_records:
            self._windows_by_family.setdefault(str(record["base_family_id"]), []).append(int(record["index"]))
        self._families = sorted(self._windows_by_family)
        if not self._families:
            raise ValueError("empty family set for sampler")
        self._rng = np.random.default_rng(int(seed))

    def next_batch(self) -> list[int]:
        """One batch of window indices: ~families_per_batch families, windows
        drawn with replacement within family so short families are supported."""
        batch: list[int] = []
        family_pool = self._families
        families_in_batch = min(self.families_per_batch, len(family_pool))
        chosen = self._rng.choice(len(family_pool), size=families_in_batch, replace=False)
        windows_per_family = int(np.ceil(self.batch_windows / families_in_batch))
        for family_position in chosen:
            family = family_pool[int(family_position)]
            windows = self._windows_by_family[family]
            take = self._rng.choice(len(windows), size=windows_per_family, replace=True)
            batch.extend(int(windows[int(index)]) for index in take)
        while len(batch) < self.batch_windows:
            family = family_pool[int(self._rng.integers(0, len(family_pool)))]
            windows = self._windows_by_family[family]
            batch.append(int(windows[int(self._rng.integers(0, len(windows)))]))
        return batch[: self.batch_windows]

    def precompute(self, batches: int, out_path: Path | None = None) -> list[list[int]]:
        """Deterministically generate `batches` batches (position-indexed)."""
        stream = [self.next_batch() for _ in range(int(batches))]
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "seed": self.seed,
                "batch_windows": self.batch_windows,
                "families_per_batch": self.families_per_batch,
                "batch_count": len(stream),
                "stream": stream,
            }
            temporary = out_path.with_suffix(out_path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            import os

            os.replace(temporary, out_path)
        return stream

    @staticmethod
    def load_stream(path: Path) -> list[list[int]]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return [list(batch) for batch in payload["stream"]]


# risk groups: R0 D5-hard, R1 connector_event, R2 switch, R3 maneuver, R4 steady
def risk_group_id(scenario: str, window_class: str, window_start: int, protocol: dict) -> int:
    if scenario == "D5" and int(window_start) in [int(v) for v in protocol["scenarios"]["d5_hard_windows"]]:
        return 0
    if window_class == "connector_event":
        return 1
    if window_class == "switch":
        return 2
    if window_class == "maneuver":
        return 3
    return 4


class RiskStratifiedSampler:
    """Five mutually-exclusive risk groups, family-balanced per batch.

    Each batch draws families_per_batch families uniformly, then, for each
    family, draws from its windows with per-group quotas proportional to the
    family's group composition, ensuring every group appears when present.
    """

    def __init__(self, window_records: list[dict], *, batch_windows: int, families_per_batch: int = 32, seed: int, protocol: dict):
        self.batch_windows = int(batch_windows)
        self.families_per_batch = int(families_per_batch)
        self.seed = int(seed)
        self.protocol = protocol
        self._by_family: dict[str, dict[int, list[int]]] = {}
        for record in window_records:
            family = str(record["base_family_id"])
            group = int(record["risk_group"])
            self._by_family.setdefault(family, {}).setdefault(group, []).append(int(record["index"]))
        self._families = sorted(self._by_family)
        self._rng = np.random.default_rng(int(seed) + 100_000)

    def next_batch(self) -> list[int]:
        batch: list[int] = []
        families_in_batch = min(self.families_per_batch, len(self._families))
        chosen = self._rng.choice(len(self._families), size=families_in_batch, replace=False)
        windows_per_family = int(np.ceil(self.batch_windows / families_in_batch))
        for family_position in chosen:
            family = self._families[int(family_position)]
            groups = self._by_family[family]
            for group in sorted(groups):
                windows = groups[group]
                quota = max(1, int(np.ceil(windows_per_family * len(windows) / max(sum(len(g) for g in groups.values()), 1))))
                take = self._rng.choice(len(windows), size=min(quota, windows_per_family), replace=True)
                batch.extend(int(windows[int(index)]) for index in take)
        while len(batch) < self.batch_windows:
            family = self._families[int(self._rng.integers(0, len(self._families)))]
            group = int(self._rng.integers(0, 5))
            windows = self._by_family[family].get(group)
            if not windows:
                continue
            batch.append(int(windows[int(self._rng.integers(0, len(windows)))]))
        return batch[: self.batch_windows]

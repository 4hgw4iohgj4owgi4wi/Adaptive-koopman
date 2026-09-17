"""Minimal contract tests for EXP-R3 R3A frozen-input extraction."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from paper_v4_core.diagnostics.frozen_input_replay import extract_window


def source(path: Path, *, missing: str | None = None, nonfinite: bool = False) -> None:
    columns = (
        ["time_s"]
        + [f"x{i}" for i in range(30)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
        + [f"actual_delta{i}" for i in range(4)]
    )
    if missing:
        columns.remove(missing)
    values = np.zeros((4, len(columns)), dtype=float)
    c = {name: i for i, name in enumerate(columns)}
    values[:, c["time_s"]] = (41.98, 42.00, 42.02, 42.04)
    for row in range(4):
        for i in range(30):
            if f"x{i}" in c:
                values[row, c[f"x{i}"]] = 1000 * row + i
        for i in range(4):
            if f"request_accel{i}" in c:
                values[row, c[f"request_accel{i}"]] = 10 * row + i
            if f"request_delta{i}" in c:
                values[row, c[f"request_delta{i}"]] = 100 * row + i
            if f"actual_delta{i}" in c:
                values[row, c[f"actual_delta{i}"]] = 1000 * row + i
    if nonfinite:
        values[2, c["x0"]] = np.nan
    np.savez_compressed(path, values=values, columns=np.asarray(columns))


def rejects(function) -> None:
    try:
        function()
    except ValueError:
        return
    raise AssertionError("invalid input was accepted")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        valid = root / "valid.npz"
        source(valid)
        a = extract_window(valid, 42.00, 42.04)
        b = extract_window(valid, 42.00, 42.04)
        assert a["start_row"] == 1
        assert a["end_rows"].tolist() == [2, 3]
        assert a["initial_state"][0] == 1000
        # Interleaved physical command: [a_i, delta_i], not a flat reshape.
        assert a["commands"][0].tolist() == [
            [20, 200], [21, 201], [22, 202], [23, 203]
        ]
        assert a["initial_state"].tobytes() == b["initial_state"].tobytes()
        assert a["commands"].tobytes() == b["commands"].tobytes()
        missing = root / "missing.npz"
        source(missing, missing="actual_delta3")
        rejects(lambda: extract_window(missing, 42.00, 42.04))
        bad = root / "bad.npz"
        source(bad, nonfinite=True)
        rejects(lambda: extract_window(bad, 42.00, 42.04))
        rejects(lambda: extract_window(valid, 42.01, 42.04))
        rejects(lambda: extract_window(valid, 42.00, 42.03))
    print("PASS: frozen-input extraction, time alignment, interleaving, identity, missing/nonfinite rejection")


if __name__ == "__main__":
    main()

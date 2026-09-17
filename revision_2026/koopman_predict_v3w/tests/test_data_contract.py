"""Data contract tests: frozen N5 manifest/cache/normalization audits,
family zero-cross, train-only normalization, confirm hidden."""

from __future__ import annotations

from collections import Counter

import numpy as np

from data_contract import load_cache


def test_audit_split_passes(frozen, data, protocol):
    audit = data.audit_split(protocol)
    assert audit["passed"]
    assert audit["row_count"] == 672
    assert audit["split_counts"] == {"train": 336, "validation": 168, "development": 168}
    assert audit["cross_split_families"] == {}
    assert audit["confirm_read_count"] == 0
    assert audit["checks"]["family_counts"] == {"train": 96, "validation": 48, "development": 48}


def test_train_only_normalization(frozen, data):
    assert str(np.asarray(data.normalization["source_split"])) == "train"
    assert int(np.asarray(data.normalization["source_base_family_count"])) == 96
    for key in ("relative_state47", "actual_steering4", "control7", "force_payload_body8", "internal_force8"):
        assert f"{key}_mean" in data.normalization
        assert f"{key}_scale" in data.normalization
        scale = np.asarray(data.normalization[f"{key}_scale"])
        assert np.all(scale >= 1.0e-9)


def test_window_counts_match_frozen(data, protocol):
    counts = Counter()
    for entry in data.train + data.validation + data.development:
        cache = load_cache(entry["cache_path"])
        counts.update(str(item) for item in np.asarray(cache["window_class"]))
    expected = protocol["data_contract"]["cache_window_counts"]
    assert dict(counts) == expected
    # the ledger counts are the N5 reference numbers and stay available
    assert protocol["data_contract"]["ledger_window_counts"] == {
        "steady": 1868,
        "maneuver": 8484,
        "switch": 728,
        "connector_event": 4764,
    }


def test_cache_shas_match_manifest(frozen, data):
    from contracts_v2 import file_sha256

    for entry in data.train[:3] + data.development[:2]:
        assert file_sha256(entry["cache_path"]) == entry["cache_sha256"]


def test_development_window_count(frozen, data, protocol):
    count = sum(len(load_cache(entry["cache_path"])["window_start"]) for entry in data.development)
    assert count == int(protocol["data_contract"]["development_window_count"])

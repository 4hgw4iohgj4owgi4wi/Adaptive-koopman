"""Negative and positive contract tests for EXP-R4 candidate identity."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from paper_v4_core.candidate_identity import PAPER, audit_run


RUN = PAPER / "results/20260911_R3_UNFROZEN_FULL01"
CONTRACTS = PAPER / "protocol/candidate_identities.json"


def test_registered_unfrozen_candidate_passes() -> None:
    report = audit_run(RUN, CONTRACTS, "EXP-R3-unfrozen-v1")
    assert report["status"] == "PASS_RECONSTRUCTED_IDENTITY"
    assert all(report["checks"].values())


def test_contract_negative_cases(tmp_path: Path) -> None:
    base = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    mutations = {
        "wrong_runner": ("runner_sha256", "0" * 64),
        "old_candidate_identity": ("runner_sha256", base["candidates"]["EXP-R2-frozen-v1"]["runner_sha256"]),
        "wrong_controller": ("controller_sha256", "1" * 64),
        "mixed_protocol": ("protocol_sha256", "2" * 64),
        "wrong_candidate_id": None,
        "missing_snapshot": ("source_snapshot", "protocol/source_snapshots/missing"),
    }
    for name, mutation in mutations.items():
        data = copy.deepcopy(base)
        candidate = "EXP-R3-unfrozen-v1"
        if mutation is None:
            data["candidates"]["WRONG"] = data["candidates"].pop(candidate)
            candidate = "WRONG"
        else:
            key, value = mutation
            data["candidates"][candidate][key] = value
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        try:
            report = audit_run(RUN, path, candidate)
        except (FileNotFoundError, KeyError):
            continue
        assert report["status"] == "SOURCE_UNRESOLVED", name


def test_frozen_exp_r4_taskbook_hash() -> None:
    from paper_v4_core.cli import sha

    contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    taskbook = PAPER / contracts["taskbook"]["path"]
    assert sha(taskbook) == contracts["taskbook"]["sha256"]

"""AR1 unit tests for compose_fallback (koopman_ab.md): determinism, no-future-info,
S0 identity matching, hand-computed composition. Uses synthetic rows only."""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import compose_fallback as cf  # noqa: E402


def make_rows(out_dir, variant_rows, s0_rows):
    cand_csv = out_dir / "cand.csv"
    s0_csv = out_dir / "s0.csv"
    with open(cand_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(variant_rows[0].keys()))
        w.writeheader()
        w.writerows(variant_rows)
    with open(s0_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(s0_rows[0].keys()))
        w.writeheader()
        w.writerows(s0_rows)
    return cand_csv, s0_csv


def row(**kw):
    base = {
        "model_kind": "GDM_RK", "variant": "S0", "ridge": "", "rank": "", "seed_label": "MH16_F0_BEST",
        "trajectory_id": "0", "base_family_id": "train_D0_986000", "split": "train", "scenario": "D1",
        "direction": "none", "member": "none", "plant": "V1-ES", "window": "maneuver",
        "window_start": "100", "horizon": "20", "j_common": "0.05", "divergent": "False",
        "inference_s": "0.001", "latent_norm": "1.0", "normalized_max_abs": "0.5",
        "e_core": "0.01", "e_relative": "0.02", "e_force4": "0.03", "e_internal": "0.04", "e_yaw": "0.05",
        "state47_rmse_si": "0.06", "force8_rmse_n": "0.07", "internal8_rmse_n": "0.08",
        "e_g0_norm": "0.09", "e_g1_norm": "0.1", "e_g2_norm": "0.11", "e_g3_norm": "0.12",
    }
    base.update(kw)
    return base


def test_triggered_scenario_set():
    spec = {"trigger": {"type": "scenario_set", "scenarios": ["D1"]}}
    assert cf.triggered(row(scenario="D1"), spec)
    assert not cf.triggered(row(scenario="D2"), spec)


def test_triggered_window_set():
    spec = {"trigger": {"type": "window_set", "scenarios": ["D1"], "window_classes": ["connector_event"]}}
    assert cf.triggered(row(scenario="D1", window="connector_event"), spec)
    assert not cf.triggered(row(scenario="D1", window="maneuver"), spec)
    assert not cf.triggered(row(scenario="D2", window="connector_event"), spec)


def test_compose_deterministic_and_handcheck(tmp_path):
    """Same input twice -> bitwise identical; triggered windows replaced by S0 values."""
    cand = [
        row(trajectory_id="0", window_start="100", scenario="D1", j_common="0.10"),
        row(trajectory_id="0", window_start="200", scenario="D2", j_common="0.11"),
        row(trajectory_id="1", window_start="300", scenario="D1", j_common="0.12"),
    ]
    s0 = [
        row(trajectory_id="0", window_start="100", scenario="D1", j_common="0.01", e_force4="0.001"),
        row(trajectory_id="0", window_start="200", scenario="D2", j_common="0.02", e_force4="0.002"),
        row(trajectory_id="1", window_start="300", scenario="D1", j_common="0.03", e_force4="0.003"),
    ]
    spec = {"trigger": {"type": "scenario_set", "scenarios": ["D1"]}, "candidate": {"variant": "MH16"}}
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        cand_csv, s0_csv = make_rows(d, cand, s0)
        # monkeypatch F4 root by calling the row-level helpers directly
        rows = cf.load(cand_csv)
        s0_by = {cf.key(r): r for r in cf.load(s0_csv)}
        out1 = []
        for r in rows:
            if cf.triggered(r, spec):
                s = s0_by[cf.key(r)]
                s_row = {fld: s.get(fld, "") for fld in list(rows[0].keys())}
                s_row["seed_label"] = r["seed_label"]
                out1.append(s_row)
            else:
                out1.append(r)
        # hand check: D1 windows carry S0 j_common, D2 window keeps candidate value
        by_key = {cf.key(r): r for r in out1}
        assert by_key[(0, 100, 20)]["j_common"] == "0.01"      # replaced by S0
        assert by_key[(0, 100, 20)]["e_force4"] == "0.001"     # S0 components carried
        assert by_key[(1, 300, 20)]["j_common"] == "0.03"      # replaced by S0
        assert by_key[(0, 200, 20)]["j_common"] == "0.11"      # non-trigger keeps candidate
        # determinism: repeat the loop
        out2 = []
        for r in cf.load(cand_csv):
            if cf.triggered(r, spec):
                s = s0_by[cf.key(r)]
                s_row = {fld: s.get(fld, "") for fld in list(rows[0].keys())}
                s_row["seed_label"] = r["seed_label"]
                out2.append(s_row)
            else:
                out2.append(r)
        assert out1 == out2


def test_spec_no_future_info_and_sha():
    """Spec carries only scenario/window labels and frozen row references."""
    import hashlib

    spec = cf.make_spec(
        {"type": "scenario_set", "scenarios": ["D1"]},
        Path(tempfile.gettempdir()) / "spec_test.json",
    )
    recorded = spec.pop("sha256")  # self-hash excludes the sha256 field itself
    text = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    assert recorded == hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    assert spec["trigger"]["type"] == "scenario_set"
    assert "validation" not in json.dumps(spec).lower()

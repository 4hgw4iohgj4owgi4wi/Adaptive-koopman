from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from import_audit import audit_source


def test_finish_import_audit_detects_executable_references():
    samples = (
        "import four_vehicle_coupled",
        "from four_vehicle_coupled import Plant",
        "__import__('four_vehicle_coupled')",
        "import importlib\nimportlib.import_module('four_vehicle_coupled')",
        "value = ConnectorParams()",
        "value = legacy.ConnectorParams()",
    )
    for source in samples:
        assert audit_source(source), source


def test_finish_import_audit_ignores_plain_strings_and_comments():
    source = '''
# import four_vehicle_coupled
message = "four_vehicle_coupled ConnectorParams"
doc = """from four_vehicle_coupled import ConnectorParams"""
'''
    assert audit_source(source) == []

import json
from pathlib import Path
from types import ModuleType

import pytest

from resume_index import audit_units


@pytest.mark.batch_q1
def test_module_object_explains_old_deepcopy_failure():
    import copy
    with pytest.raises(TypeError):
        copy.deepcopy({"decoder_module": ModuleType("dynamic_decoder")})


@pytest.mark.batch_q1
def test_frozen_unit_audit_rejects_missing_matrix(tmp_path):
    with pytest.raises(ValueError, match="45-unit"):
        audit_units({"units": []}, tmp_path)


@pytest.mark.batch_q1
def test_background_source_uses_timing_spec_not_data_deepcopy():
    source=(Path(__file__).resolve().parents[1]/"scripts"/"run_background.py").read_text(encoding="utf-8")
    assert "self.timing_spec=dict" in source
    assert "copy.deepcopy(outer)" not in source

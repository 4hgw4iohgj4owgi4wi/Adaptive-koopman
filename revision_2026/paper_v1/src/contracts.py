import json
from pathlib import Path


def validate_protocol(path):
    cfg=json.loads(Path(path).read_text(encoding="utf-8-sig"))
    required={"version","batch","taskbook_sha256","old_run","predictor_source","candidate_states",
              "frozen_models","training_allowed","minimum_free_gib","wall_budget_hours","next_stage"}
    missing=sorted(required-set(cfg))
    if missing: raise ValueError(f"protocol fields missing: {missing}")
    if cfg["batch"]!="Q1" or cfg["candidate_states"]!=90 or cfg["frozen_models"]!=45:
        raise ValueError("Q1 matrix differs")
    if cfg["training_allowed"] is not False or cfg["next_stage"]!="STOP_AFTER_K1_VERDICT":
        raise ValueError("Q1 authority boundary differs")
    return cfg

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def source_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or any(
            part in {
                "__pycache__",
                ".pytest_cache",
                "runs",
                "results",
                "models",
                "checkpoints",
            }
            for part in path.parts
        ):
            continue
        if path.suffix.lower() in {".pyc", ".tmp", ".lock", ".partial"}:
            continue
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        result[path.relative_to(root).as_posix()] = sha256(path)
    return result


@dataclass(frozen=True)
class RunContract:
    project_root: Path
    source_root: Path
    results_root: Path
    protocol_path: Path

    @property
    def protocol(self) -> dict:
        return json.loads(self.protocol_path.read_text(encoding="utf-8"))

    def input_identity(self) -> dict:
        manifest = source_manifest(self.source_root)
        return {
            "protocol_sha256": sha256(self.protocol_path),
            "source_manifest": manifest,
            "source_manifest_sha256": json_sha256(manifest),
        }

    def require_previous(self, stage: str) -> None:
        required = {
            "F0": (),
            "F1": ("F0",),
            "F2": ("F0", "F1"),
            "F3": ("F0", "F1", "F2"),
        }.get(stage)
        if stage not in {"F0", "F1", "F2", "F3"}:
            raise ValueError(f"stage is outside current authorization: {stage}")
        if not required:
            return
        status_path = self.results_root / "stage_status.json"
        if not status_path.exists():
            raise RuntimeError(f"missing prior stage status for {stage}")
        status = json.loads(status_path.read_text(encoding="utf-8-sig"))
        current = self.input_identity()
        for prior_stage in required:
            prior = status.get("stages", {}).get(prior_stage, {})
            if prior.get("status") != "PASS":
                raise RuntimeError(f"{stage} requires {prior_stage}=PASS, found {prior}")
            complete_path = Path(prior.get("run_dir", "")) / "complete.json"
            if not complete_path.exists():
                raise RuntimeError(f"{stage} cannot verify {prior_stage}: missing {complete_path}")
            complete = json.loads(complete_path.read_text(encoding="utf-8-sig"))
            for key in ("protocol_sha256", "source_manifest_sha256"):
                if complete.get(key) != current[key]:
                    raise RuntimeError(
                        f"{stage} requires current-identity {prior_stage}; {key} "
                        f"expected {current[key]}, found {complete.get(key)}"
                    )


def validate_predict_protocol(protocol: dict) -> dict:
    """Validate the N3 frozen constants before any result directory is created."""

    expected = {
        "protocol_id": "koopman_predict_next_n3_v1",
        "authorized_stages": ["N3"],
    }
    for key, value in expected.items():
        if protocol.get(key) != value:
            raise ValueError(f"predict protocol drift for {key}: {protocol.get(key)!r}")
    actuator = protocol.get("actuator", {})
    actuator_expected = {
        "mode": "A3",
        "model_step_s": 0.02,
        "plant_step_s": 0.002,
        "substeps_per_model_step": 10,
        "tau_delta_s": 0.12,
        "rate_max_radps": 1.2,
        "angle_max_deg": 15.0,
        "endpoint_atol_rad": 1.0e-12,
        "horizon_steps": 20,
    }
    for key, value in actuator_expected.items():
        if actuator.get(key) != value:
            raise ValueError(f"actuator contract drift for {key}: {actuator.get(key)!r}")
    if int(round(actuator["model_step_s"] / actuator["plant_step_s"])) != int(
        actuator["substeps_per_model_step"]
    ):
        raise ValueError("actuator substep contract is inconsistent")
    if protocol.get("interfaces", {}).get("variants") != ["S0", "S1", "S2"]:
        raise ValueError("S0/S1/S2 interface order drift")
    scenarios = protocol.get("scenarios", {})
    expected_order = [f"D{index}" for index in range(12)]
    expected_directional = ["D2", "D3", "D4", "D5", "D6", "D8", "D10", "D11"]
    if scenarios.get("order") != expected_order:
        raise ValueError("D0-D11 scenario order drift")
    if scenarios.get("directional") != expected_directional:
        raise ValueError("directional scenario contract drift")
    if scenarios.get("d9_members") != ["A", "B"]:
        raise ValueError("D9 member contract drift")
    if len(protocol.get("n4_parameter_families", [])) != 3:
        raise ValueError("N4 parameter-family count drift")
    if protocol.get("plants") != [
        {"plant": "V1-ES", "law": "V1"},
        {"plant": "R3-ES", "law": "R3"},
    ]:
        raise ValueError("plant identity contract drift")
    n3 = protocol.get("n3", {})
    counts = {
        "expected_saved_trajectory_count": 126,
        "expected_base_family_count": 36,
        "expected_schema_variant_count": 3,
        "expected_scenario_count": 12,
    }
    for key, value in counts.items():
        if n3.get(key) != value:
            raise ValueError(f"N3 count drift for {key}: {n3.get(key)!r}")
    forbidden = set(protocol.get("forbidden_without_later_authorization", []))
    if not {"N4", "N5", "N6", "C1", "C2"}.issubset(forbidden):
        raise ValueError("later-stage stop contract is incomplete")
    return {
        "passed": True,
        "protocol_id": protocol["protocol_id"],
        "authorized_stages": list(protocol["authorized_stages"]),
        "scenario_count": len(expected_order),
        "variant_count": 3,
        "expected_dry_run_trajectory_count": 126,
    }


def build_future_split_ledger(protocol: dict, *, include_confirm: bool = False) -> dict:
    """Declare future base families while keeping confirm identities invisible."""

    if include_confirm:
        raise PermissionError("confirm split identities are invisible before K7 authorization")
    scenarios = tuple(protocol["scenarios"]["order"])
    config = protocol["future_split_contract"]
    rows: list[dict] = []
    for split in ("train", "validation", "development"):
        selected = config[split]
        count = int(selected["base_family_count_per_scenario"])
        seed = int(selected["seed_start"])
        expected_end = int(selected["seed_end"])
        for scenario in scenarios:
            for member_index in range(count):
                rows.append(
                    {
                        "base_family_id": f"{split}_{scenario}_{seed}",
                        "split": split,
                        "scenario": scenario,
                        "seed": seed,
                        "member_index": member_index,
                    }
                )
                seed += 1
        if seed - 1 != expected_end:
            raise ValueError(
                f"{split} seed block drift: ended {seed - 1}, expected {expected_end}"
            )
    identities = [row["base_family_id"] for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate future base-family identity")
    return {
        "visible_rows": rows,
        "visible_splits": ["train", "validation", "development"],
        "confirm": {
            "visible": False,
            "base_family_count_per_scenario": int(
                config["confirm"]["base_family_count_per_scenario"]
            ),
            "reason": "confirm identities and data remain hidden until later authorization",
        },
        "audit": {
            "passed": True,
            "visible_base_family_count": len(rows),
            "confirm_visible_row_count": 0,
            "cross_split_family_count": 0,
        },
    }


class StageDecision(str, Enum):
    PASS_CONTINUE = "PASS_CONTINUE"
    PASS_WITH_WARNING_CONTINUE = "PASS_WITH_WARNING_CONTINUE"
    REPAIR_CURRENT_STAGE = "REPAIR_CURRENT_STAGE"
    BLOCKED_HUMAN_REQUIRED = "BLOCKED_HUMAN_REQUIRED"


AUTONOMY_POLICY = {
    "stage_order": ("A0", "N4-S", "N4", "N5", "N6"),
    "allowed_next": {
        "A0": "N4-S",
        "N4-S": "N4",
        "N4": "N5",
        "N5": "N6",
        "N6": None,
    },
    "blocking_gate_kinds": ("physics", "causality", "data_identity", "raw_missing"),
    "repairable_gate_kinds": ("cli", "path", "serialization", "report", "oom_schedule"),
    "forbidden_stage_prefixes": ("C", "K", "MPC", "NETWORK", "DOS", "CONFIRM"),
}


def decide_stage_status(
    *,
    hard_gates: dict[str, bool],
    warnings: list[str] | tuple[str, ...] = (),
    failure_kinds: dict[str, str] | None = None,
) -> StageDecision:
    """Map explicit gates to the only four autonomy states.

    Physics, causality, data-identity and missing-raw failures always require a
    human stop.  A repair state is available only when every failed gate is
    explicitly registered as a non-scientific implementation failure.
    """

    failed = [name for name, passed in hard_gates.items() if not bool(passed)]
    if not failed:
        return (
            StageDecision.PASS_WITH_WARNING_CONTINUE
            if warnings
            else StageDecision.PASS_CONTINUE
        )
    kinds = failure_kinds or {}
    failed_kinds = {str(kinds.get(name, "unclassified")) for name in failed}
    if failed_kinds and failed_kinds.issubset(set(AUTONOMY_POLICY["repairable_gate_kinds"])):
        return StageDecision.REPAIR_CURRENT_STAGE
    return StageDecision.BLOCKED_HUMAN_REQUIRED


def require_stage_transition(current: str, requested_next: str | None) -> None:
    current = str(current)
    if current not in AUTONOMY_POLICY["allowed_next"]:
        raise PermissionError(f"stage is outside autonomy package: {current}")
    expected = AUTONOMY_POLICY["allowed_next"][current]
    if requested_next != expected:
        raise PermissionError(
            f"invalid autonomous transition: {current} -> {requested_next}; expected {expected}"
        )


def assert_stage_allowed(stage: str) -> None:
    selected = str(stage).upper()
    if selected not in AUTONOMY_POLICY["stage_order"]:
        raise PermissionError(f"stage is forbidden by autonomy policy: {stage}")


def validate_predict_auto_protocol(protocol: dict) -> dict:
    if protocol.get("protocol_id") != "koopman_predict_auto_a0_n6_v1":
        raise ValueError("auto protocol id drift")
    if tuple(protocol.get("authorized_stages", [])) != AUTONOMY_POLICY["stage_order"]:
        raise ValueError("auto stage order drift")
    if protocol.get("autonomy", {}).get("states") != [item.value for item in StageDecision]:
        raise ValueError("auto state enumeration drift")
    if protocol.get("autonomy", {}).get("human_stop_after") != "N6":
        raise ValueError("human stop must remain after N6")
    if protocol.get("interfaces", {}).get("variants") != ["S0", "S1", "S2"]:
        raise ValueError("variant order drift")
    if protocol.get("training", {}).get("ranks") != [1, 2, 4]:
        raise ValueError("rank grid drift")
    if protocol.get("training", {}).get("ridge_grid") != [1e-8, 1e-6, 1e-4, 1e-2]:
        raise ValueError("ridge grid drift")
    if protocol.get("training", {}).get("horizons") != [1, 5, 10, 20]:
        raise ValueError("horizon grid drift")
    if set(protocol.get("autonomy", {}).get("forbidden_stages", [])) < {
        "C1", "C2", "K1", "K7", "MPC", "NETWORK", "DOS", "CONFIRM"
    }:
        raise ValueError("forbidden-stage boundary drift")
    return {"passed": True, "stage_order": list(AUTONOMY_POLICY["stage_order"])}

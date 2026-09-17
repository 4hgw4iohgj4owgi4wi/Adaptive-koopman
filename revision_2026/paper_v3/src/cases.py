"""Deterministic case expansion and deduplication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .reference import build_reference, event_ticks, reference_sha, write_reference
from .network import generate_trace, trace_sha256, topology_edges


@dataclass(frozen=True)
class Case:
    case_id: str
    scenario: str
    profile: str
    family: int
    topology_slot: int
    k_event: int
    k_s: int
    k_e: int
    reference_sha256: str
    trace_sha256: str
    network_seed: int
    physical_seed: int
    ticks: int


def expand_cases(config: dict, out: Path, profiles: list[str], families: int, ticks: int) -> list[Case]:
    cases: list[Case] = []
    references = {}
    for scenario in config["scenarios"]:
        ref = build_reference(scenario, ticks, float(config["dt_s"]))
        ev = event_ticks(ref, scenario)
        references[scenario] = (ref, ev)
        write_reference(out / f"reference_{scenario}.csv", ref)
        (out / f"events_{scenario}.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
    for scenario in config["scenarios"]:
        ref, ev = references[scenario]
        for family in range(int(families)):
            topology_slot = family % 3
            for profile in profiles:
                profile_slot = {name: index for index, name in enumerate(config["profiles"] + ["DELAY60", "DELAY180", "JITTER100", "MIX_INDEPENDENT", "MIX_SHARED"])}[profile]
                network_seed = int(config["seed_roots"]["network"] + family * 101 + profile_slot * 1009 + config["scenarios"].index(scenario) * 100003)
                physical_seed = int(config["seed_roots"]["physical"] + family * 17 + config["scenarios"].index(scenario))
                trace = generate_trace(profile, network_seed, ticks, ev["k_s"], topology_slot)
                payload = f"{scenario}|{profile}|{family}|{topology_slot}|{reference_sha(ref)}|{trace_sha256(trace)}".encode()
                cid = hashlib.sha256(payload).hexdigest()[:16].upper()
                cases.append(Case(f"C_{cid}", scenario, profile, family, topology_slot, ev["k_event"], ev["k_s"], ev["k_e"], reference_sha(ref), trace_sha256(trace), network_seed, physical_seed, ticks))
    with (out / "cases.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases: handle.write(json.dumps(asdict(case), ensure_ascii=False, sort_keys=True) + "\n")
    return cases

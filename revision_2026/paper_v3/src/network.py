"""Pre-generated directed communication traces with causal replay."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import numpy as np

NODES = (0, 1, 2, 3)
EDGES = tuple((i, j) for i in NODES for j in NODES if i != j)


def topology_edges(slot: int) -> set[tuple[int, int]]:
    slot = int(slot) % 3
    if slot == 0:
        victim = 0
        return {(sender, victim) for sender in NODES if sender != victim}
    if slot == 1:
        left = {0, 2}; right = {1, 3}
        return {(a, b) for a, b in EDGES if (a in left) != (b in left)}
    return set(EDGES)


@dataclass(frozen=True)
class Event:
    sender: int
    receiver: int
    sent_tick: int
    arrival_tick: int
    dropped: bool
    transport_delay: int
    payload_bytes: int = 30 * 8 + 64


def _dos(profile: str, tick: int, ks: int, blocked: set[tuple[int, int]]) -> bool:
    if profile == "DOS200": return ks <= tick < ks + 10
    if profile == "DOS400": return ks <= tick < ks + 20
    if profile == "DOS800": return ks <= tick < ks + 40
    if profile == "DOS_REPEAT":
        return any(ks + 50 * r <= tick < ks + 50 * r + 10 for r in range(5))
    return False


def generate_trace(profile: str, seed: int, ticks: int, ks: int, topology_slot: int = 2) -> list[Event]:
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 17, int(topology_slot)]))
    blocked = topology_edges(topology_slot)
    states = {edge: False for edge in EDGES}
    events: list[Event] = []
    for tick in range(int(ticks)):
        for edge_index, (sender, receiver) in enumerate(EDGES):
            delay = 1
            dropped = False
            if _dos(profile, tick, ks, blocked) and (sender, receiver) in blocked:
                dropped = True
            elif profile == "DELAY60": delay = 3
            elif profile == "DELAY100": delay = 5
            elif profile == "DELAY180": delay = 9
            elif profile == "JITTER100": delay = int(rng.integers(1, 10))
            elif profile == "LOSS10": dropped = bool(rng.random() < 0.10)
            elif profile == "LOSS30": dropped = bool(rng.random() < 0.30)
            elif profile == "BURST10":
                p_gb, p_bg = 0.02, 0.20
                states[(sender, receiver)] = bool(rng.random() < (p_bg if states[(sender, receiver)] else p_gb)) if tick else bool(rng.random() < 0.02)
                dropped = bool(rng.random() < (0.90 if states[(sender, receiver)] else 0.02))
            elif profile == "MIX_INDEPENDENT":
                delay = int(rng.integers(1, 10)); dropped = bool(rng.random() < 0.10)
            elif profile == "MIX_SHARED":
                if edge_index == 0:
                    states[(-1, -1)] = bool(rng.random() < (0.20 if states.get((-1, -1), False) else 0.02))
                delay = int(rng.integers(1, 10)); dropped = bool(rng.random() < (0.90 if states.get((-1, -1), False) else 0.02))
            events.append(Event(sender, receiver, tick, tick + delay, dropped, delay))
    return events


def trace_sha256(events: list[Event]) -> str:
    payload = json.dumps([e.__dict__ for e in events], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest().upper()


class Replay:
    def __init__(self, events: list[Event], initial_state: np.ndarray):
        self.events_by_arrival: dict[int, list[Event]] = {}
        for event in events:
            self.events_by_arrival.setdefault(event.arrival_tick, []).append(event)
        self.sent: dict[int, np.ndarray] = {}
        self.initial = np.asarray(initial_state, dtype=float).copy()
        # Common initialization is a frozen k=0 snapshot.  It is not a
        # same-tick network delivery and therefore cannot leak a new state.
        self.latest: dict[int, dict[int, tuple[np.ndarray, int]]] = {
            n: {sender: (self.initial.copy(), 0) for sender in NODES if sender != n} for n in NODES
        }
        self.received = 0

    def deliver(self, tick: int) -> None:
        for event in self.events_by_arrival.get(int(tick), []):
            if event.dropped or event.sent_tick not in self.sent:
                continue
            old = self.latest[event.receiver].get(event.sender)
            if old is None or event.sent_tick >= old[1]:
                self.latest[event.receiver][event.sender] = (self.sent[event.sent_tick].copy(), event.sent_tick)
                self.received += 1

    def send(self, tick: int, state: np.ndarray) -> None:
        self.sent[int(tick)] = np.asarray(state, dtype=float).copy()

    def view(self, receiver: int) -> dict[int, tuple[np.ndarray, int]]:
        return {k: (v[0].copy(), int(v[1])) for k, v in self.latest[int(receiver)].items()}

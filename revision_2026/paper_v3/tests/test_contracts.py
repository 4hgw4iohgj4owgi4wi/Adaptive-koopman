from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import plant
from src.network import EDGES, generate_trace, topology_edges, trace_sha256
from src.reference import build_reference, event_ticks


def test_plant_shape_and_finite():
    state = plant.initialize(2.0)
    assert state.shape == (30,)
    assert state.dtype.kind == "f"


def test_topology_counts():
    assert len(EDGES) == 12
    assert [len(topology_edges(i)) for i in range(3)] == [3, 8, 12]


def test_trace_is_deterministic_and_delayed():
    a = generate_trace("DELAY100", 1, 20, 5, 2)
    b = generate_trace("DELAY100", 1, 20, 5, 2)
    assert trace_sha256(a) == trace_sha256(b)
    assert all(event.transport_delay == 5 for event in a)


def test_reference_event_window():
    rows = build_reference("100m_accel_turn", 1200, 0.02)
    ev = event_ticks(rows, "100m_accel_turn")
    assert ev["k_event"] < ev["k_e"] < len(rows) - 1
    assert ev["candidate_3"] < len(rows)


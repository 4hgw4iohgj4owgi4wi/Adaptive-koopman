import numpy as np

from channel import CONDITIONS, generate_trace


def signature(trace):
    return [
        (tick, p["receiver"], p["sender"], p["sequence"], p["arrival_tick"])
        for tick, packets in trace["sends"].items()
        for p in packets
    ]


def main():
    for condition in CONDITIONS:
        first = generate_trace(condition, 3101, 300)
        second = generate_trace(condition, 3101, 300)
        assert signature(first) == signature(second)
        assert 0.0 <= first["packet_delivery_ratio"] <= 1.0
        for tick, packets in first["sends"].items():
            for packet in packets:
                assert packet["arrival_tick"] >= tick
                assert packet["receiver"] != packet["sender"]
    clean = generate_trace("clean", 3101, 300)
    assert clean["packet_delivery_ratio"] == 1.0
    assert clean["mean_delay_ticks_delivered"] == 0.0
    heavy = generate_trace("heavy", 3101, 300)
    assert heavy["packet_delivery_ratio"] < clean["packet_delivery_ratio"]
    assert heavy["mean_delay_ticks_delivered"] > 0.0
    print("PASS: deterministic traces, directed links, clean transparency, degraded loss/delay")


if __name__ == "__main__":
    main()

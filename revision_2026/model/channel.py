"""Deterministic directed-link traces for delay, loss and burst loss."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ChannelConfig:
    name: str
    delay_min_ticks: int
    delay_max_ticks: int
    independent_loss: float
    p_good_to_bad: float
    p_bad_to_good: float
    bad_loss: float


CONDITIONS = {
    "clean": ChannelConfig("clean", 0, 0, 0.0, 0.0, 1.0, 0.0),
    "light": ChannelConfig("light", 0, 1, 0.02, 0.001, 0.20, 0.50),
    "medium": ChannelConfig("medium", 1, 3, 0.05, 0.010, 0.05, 0.80),
    "heavy": ChannelConfig("heavy", 3, 6, 0.10, 0.020, 0.02, 0.90),
}


def generate_trace(condition: str, seed: int, ticks: int, receivers: int = 4, senders: int = 5) -> dict:
    cfg = CONDITIONS[condition]
    rng = np.random.default_rng(seed)
    links = [(receiver, sender) for receiver in range(receivers) for sender in range(senders) if sender != receiver]
    bad = {link: False for link in links}
    seq = {link: 0 for link in links}
    sends: dict[int, list[dict]] = {tick: [] for tick in range(ticks)}
    loss_count = 0
    delay_values = []
    for tick in range(ticks):
        for link in links:
            if bad[link]:
                if rng.random() < cfg.p_bad_to_good:
                    bad[link] = False
            elif rng.random() < cfg.p_good_to_bad:
                bad[link] = True
            loss_probability = cfg.bad_loss if bad[link] else cfg.independent_loss
            sequence = seq[link]
            seq[link] += 1
            lost = bool(rng.random() < loss_probability)
            if lost:
                loss_count += 1
                continue
            delay = int(rng.integers(cfg.delay_min_ticks, cfg.delay_max_ticks + 1))
            delay_values.append(delay)
            sends[tick].append(
                {
                    "receiver": link[0],
                    "sender": link[1],
                    "sequence": sequence,
                    "sent_tick": tick,
                    "arrival_tick": tick + delay,
                }
            )
    total = ticks * len(links)
    return {
        "condition": condition,
        "seed": seed,
        "sends": sends,
        "links": links,
        "packet_delivery_ratio": 1.0 - loss_count / max(total, 1),
        "mean_delay_ticks_delivered": float(np.mean(delay_values)) if delay_values else np.nan,
        "total_packets": total,
        "lost_packets": loss_count,
    }

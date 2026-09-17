"""Plot the registered case_plan artifacts for one ablation batch."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def save(fig, out: Path, name: str, rows: list[dict]) -> None:
    fig.tight_layout()
    fig.savefig(out / f"{name}.png", dpi=180)
    fig.savefig(out / f"{name}.pdf")
    write_csv(out / f"{name}.csv", rows)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    case_plan = args.case_plan.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    reference = read_csv(case_plan / "reference.csv")
    events = read_csv(case_plan / "events.csv")
    cases = [json.loads(line) for line in (case_plan / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    scenarios = ["100m_accel_turn", "single_lane_change", "hairpin"]
    colors = {"100m_accel_turn": "#1f77b4", "single_lane_change": "#ff7f0e", "hairpin": "#2ca02c"}

    # 1. Reference trajectory, speed and curvature, with the common event window.
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    reference_rows = []
    for row, scenario in enumerate(scenarios):
        q = [r for r in reference if r["scenario"] == scenario]
        t = np.array([float(r["t_s"]) for r in q])
        x = np.array([float(r["x_m"]) for r in q])
        y = np.array([float(r["y_m"]) for r in q])
        speed = np.array([float(r["speed_mps"]) for r in q])
        curvature = np.array([float(r["curvature"]) for r in q])
        ev = next(e for e in events if e["scenario"] == scenario)
        ks, ke = float(ev["k_s"]) * 0.02, float(ev["k_e"]) * 0.02
        axes[row, 0].plot(x, y, color=colors[scenario], linewidth=1.5)
        axes[row, 0].set_title(f"{scenario}: reference path")
        axes[row, 0].set_xlabel("x (m)"); axes[row, 0].set_ylabel("y (m)"); axes[row, 0].axis("equal"); axes[row, 0].grid(alpha=.25)
        axes[row, 1].plot(t, speed, color=colors[scenario], label="speed")
        axes[row, 1].plot(t, curvature, color="#9467bd", label="curvature")
        axes[row, 1].axvspan(ks, ke, color="#d62728", alpha=.15, label="common event window")
        axes[row, 1].set_title(f"{scenario}: speed / curvature")
        axes[row, 1].set_xlabel("time (s)"); axes[row, 1].grid(alpha=.25)
        if row == 0: axes[row, 1].legend(fontsize=8)
        for r in q[::max(1, len(q)//20)]:
            reference_rows.append({"scenario": scenario, "t_s": r["t_s"], "x_m": r["x_m"], "y_m": r["y_m"], "speed_mps": r["speed_mps"], "curvature": r["curvature"], "event_k_s": ev["k_s"], "event_k_e": ev["k_e"]})
    save(fig, out, "case_plan_reference_overview", reference_rows)

    # 2. Registered event windows and candidate timestamps.
    fig, ax = plt.subplots(figsize=(12, 4.5))
    event_rows = []
    for idx, scenario in enumerate(scenarios):
        e = next(e for e in events if e["scenario"] == scenario)
        ks, ke = int(e["k_s"]), int(e["k_e"])
        ax.hlines(idx, 0, 1200, color="#bbbbbb", linewidth=1)
        ax.axvspan(ks, ke, ymin=(idx + .18) / 3.3, ymax=(idx + .82) / 3.3, color=colors[scenario], alpha=.28)
        ax.scatter([int(e["k_event"])], [idx], color="#d62728", marker="o", s=55, label="k_event" if idx == 0 else None, zorder=3)
        candidates = [int(e["candidate_1"]), int(e["candidate_2"]), int(e["candidate_3"])]
        ax.scatter(candidates, [idx] * 3, color="#111111", marker="|", s=180, label="candidate" if idx == 0 else None, zorder=3)
        ax.text(ks, idx + .16, f"k_s={ks}", fontsize=8, ha="left")
        ax.text(ke, idx - .18, f"k_e={ke}", fontsize=8, ha="right")
        event_rows.append({"scenario": scenario, "k_s": ks, "k_event": int(e["k_event"]), "k_e": ke, "candidate_1": candidates[0], "candidate_2": candidates[1], "candidate_3": candidates[2], "duration_s": e["duration_s"], "threshold": e["threshold"]})
    ax.set_yticks(range(3), scenarios); ax.set_xlim(0, 1200); ax.set_xlabel("tick (20 ms / tick)"); ax.set_title("ABL-COMMON registered event windows"); ax.grid(axis="x", alpha=.25); ax.legend()
    save(fig, out, "case_plan_event_windows", event_rows)

    # 3. Case-family, topology and profile coverage.
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    profiles = sorted({c["profile"] for c in cases})
    topology = sorted({int(c["topology_slot"]) for c in cases})
    for scenario in scenarios:
        q = [c for c in cases if c["scenario"] == scenario]
        for profile in profiles:
            qq = [c for c in q if c["profile"] == profile]
            axes[0].scatter([int(c["family"]) for c in qq], [int(c["topology_slot"]) + .12 * profiles.index(profile) for c in qq], s=13, alpha=.65, label=f"{scenario}/{profile}")
    axes[0].set_xlabel("family"); axes[0].set_ylabel("topology slot"); axes[0].set_title("Registered case coverage"); axes[0].set_yticks(topology); axes[0].grid(alpha=.25); axes[0].legend(fontsize=7, ncol=2)
    matrix = np.zeros((len(scenarios), len(profiles)), dtype=int)
    summary_rows = []
    for i, scenario in enumerate(scenarios):
        for j, profile in enumerate(profiles):
            q = [c for c in cases if c["scenario"] == scenario and c["profile"] == profile]
            matrix[i, j] = len(q)
            summary_rows.append({"scenario": scenario, "profile": profile, "case_count": len(q), "families": len({c["family"] for c in q}), "topology_slots": len({c["topology_slot"] for c in q})})
    image = axes[1].imshow(matrix, cmap="Blues", vmin=0)
    axes[1].set_xticks(range(len(profiles)), profiles, rotation=25); axes[1].set_yticks(range(len(scenarios)), scenarios); axes[1].set_title("Case count by scenario/profile")
    for i in range(len(scenarios)):
        for j in range(len(profiles)): axes[1].text(j, i, str(matrix[i, j]), ha="center", va="center")
    fig.colorbar(image, ax=axes[1], label="cases")
    save(fig, out, "case_plan_coverage", summary_rows)

    # 4. Seed/fingerprint identity counts: useful for checking the paired design.
    fig, ax = plt.subplots(figsize=(10, 5))
    counts = Counter((c["profile"], int(c["topology_slot"])) for c in cases)
    labels = [f"{p}/T{t}" for p, t in sorted(counts)]
    values = [counts[key] for key in sorted(counts)]
    ax.bar(labels, values, color="#4c78a8"); ax.set_ylabel("case count"); ax.set_title("ABL-COMMON profile/topology identity counts"); ax.tick_params(axis="x", rotation=35); ax.grid(axis="y", alpha=.25)
    save(fig, out, "case_plan_identity_counts", [{"profile": p, "topology_slot": t, "case_count": counts[(p, t)]} for p, t in sorted(counts)])

    manifest = {"case_plan": str(case_plan), "figures": sorted(p.name for p in out.glob("case_plan_*.png")), "case_count": len(cases), "reference_rows": len(reference), "event_rows": len(events)}
    (out / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()

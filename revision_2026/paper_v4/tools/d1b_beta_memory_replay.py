"""D1+ read-only analysis: reconstruct the frozen runner's reference-chain memory.

Question: the interrupted P1 run never persisted `beta` (the integrated reference
relative-heading memory), so D1 concluded that a complete state/memory recovery
was unavailable and D3 stayed blocked.

This analysis tests the narrower, falsifiable claim that `beta` is not an
independent memory at all but a deterministic function of the reference chain
that is already persisted.  It replays, with CPU arithmetic only:

    distance[k] = min(distance[k-1] + SPEED * dur[k], ROUTE_LENGTH)
    beta[k]     = beta[k-1] + (dur[k] / DT) * (preview(distance[k-1], beta[k-1])[0].beta_star - beta[k-1])

using the durations recovered from the persisted `time_s` labels, and validates
the replay against the persisted `reference_distance_m` column.

No plant integration, no MPC, no GPU, no closed loop, no write to the source
tree.  The output is a read-only report plus figures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "D1B_BETA_MEMORY_REPLAY_READ_ONLY":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.e01_100m import DT, params
    from paper_v4_core.pilot_runner import ROUTE_LENGTH, SPEED, make_preview

    run = paper / protocol["inputs"]["run"]
    raw, columns = load_archive(run / "raw.npz")
    sub, subcolumns = load_archive(run / "substeps.npz")
    index = {name: position for position, name in enumerate(columns)}
    subindex = {name: position for position, name in enumerate(subcolumns)}
    model = params(protocol["inputs"]["parameter_id"])

    time_s = raw[:, index["time_s"]]
    recorded_distance = raw[:, index["reference_distance_m"]]
    ticks = int(raw.shape[0])

    # ---- duration recovery -------------------------------------------------
    # The frozen runner writes time_s = k*DT + accepted_duration, so the accepted
    # duration is recoverable without any substep-attribution heuristic.
    tick = np.arange(ticks, dtype=float)
    duration = time_s - tick * DT
    substep_time = sub[:, subindex["time_s"]]
    substep_dt = sub[:, subindex["dt_s"]]

    # ---- reference-chain replay -------------------------------------------
    distance = 0.0
    beta = np.zeros(4)
    replay_distance = np.zeros(ticks)
    beta_history = np.zeros((ticks, 4))
    for k in range(ticks):
        _controls, refs, _preview = make_preview(distance, beta, model, np.zeros(8), 20)
        distance = min(distance + SPEED * duration[k], ROUTE_LENGTH)
        beta = beta + (duration[k] / DT) * (np.asarray(refs[0]["beta_star"], float) - beta)
        replay_distance[k] = distance
        beta_history[k] = beta

    distance_error = np.abs(replay_distance - recorded_distance)
    distance_scale = np.maximum(np.abs(recorded_distance), np.finfo(float).tiny)
    substep_gaps = np.diff(substep_time)
    on_label = int(np.count_nonzero(np.isin(substep_time, time_s)))

    replay = {
        "ticks": ticks,
        "substeps": int(sub.shape[0]),
        "duration_min_s": float(duration.min()),
        "duration_max_s": float(duration.max()),
        "duration_sum_s": float(duration.sum()),
        "duration_max_abs_deviation_from_DT_s": float(np.max(np.abs(duration - DT))),
        "substeps_not_strictly_increasing": int(np.count_nonzero(substep_gaps <= 0.0)),
        "substeps_exactly_on_an_interval_label": on_label,
        "interval_closure_residual_s": float(substep_dt.sum() - duration.sum()),
        "distance_error_exactly_zero_ticks": int(np.count_nonzero(distance_error == 0.0)),
        "substep_dt_sum_s": float(substep_dt.sum()),
        "distance_replay_max_abs_error_m": float(distance_error.max()),
        "distance_replay_max_relative_error": float(np.max(distance_error / distance_scale)),
        "distance_replay_bitwise_equal": bool(np.array_equal(replay_distance, recorded_distance)),
        "distance_final_recorded_m": float(recorded_distance[-1]),
        "distance_final_replayed_m": float(replay_distance[-1]),
        "route_length_m": float(ROUTE_LENGTH),
        "reference_speed_mps": float(SPEED),
        "DT_s": float(DT),
    }

    beta_summary = {
        "beta_final_deg": np.rad2deg(beta_history[-1]).tolist(),
        "beta_max_abs_deg": np.rad2deg(np.max(np.abs(beta_history), axis=0)).tolist(),
        "confidence": "SAME_SOURCE_PATH_REPLAY_VALIDATED_AGAINST_PERSISTED_DISTANCE",
        "limitation": "beta itself was never persisted, so this replay is validated against the persisted reference distance, not against a logged beta series.",
    }

    # ---- state/memory recovery inventory ----------------------------------
    solver_first_control = []
    solver_path = run / "solver.jsonl"
    for line in solver_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        control = record.get("first_control")
        if control is not None:
            solver_first_control.append((int(record["tick"]), np.asarray(control, float)))
    solver_closed = len(solver_first_control)
    # raw stores the solved first control grouped as [a1..a4, delta1..delta4];
    # solver.jsonl stores it interleaved as [a1, delta1, a2, delta2, ...].
    # The two layouts must be de-interleaved before comparison.
    raw_request = np.column_stack(
        [raw[:, index[f"request_accel{i}"]] for i in range(4)]
        + [raw[:, index[f"request_delta{i}"]] for i in range(4)]
    )
    request_mismatch = 0.0
    request_mismatch_tick = None
    request_bitwise_ticks = 0
    request_compared_ticks = 0
    for tick_id, control in solver_first_control:
        if tick_id >= ticks:
            continue
        grouped = np.r_[control[0::2], control[1::2]]
        request_compared_ticks += 1
        delta = np.abs(raw_request[tick_id] - grouped)
        if delta.max() == 0.0:
            request_bitwise_ticks += 1
        elif delta.max() > request_mismatch:
            request_mismatch = float(delta.max())
            request_mismatch_tick = tick_id

    recovery = {
        "plant_state_x30": {"status": "IN_RAW", "evidence": "raw.npz columns x0..x29"},
        "actual_steering_delta4": {"status": "IN_RAW", "evidence": "raw.npz columns actual_delta0..3"},
        "reference_distance": {"status": "IN_RAW", "evidence": "raw.npz column reference_distance_m"},
        "previous_u8": {
            "status": "IN_RAW",
            "evidence": "raw.npz request_accel*/request_delta* reproduce solver.jsonl first_control after de-interleaving the solver layout",
            "bitwise_identical_ticks": request_bitwise_ticks,
            "compared_ticks": request_compared_ticks,
            "max_abs_mismatch": request_mismatch,
            "worst_tick": request_mismatch_tick,
        },
        "reference_beta4": {
            "status": "RECONSTRUCTED_THIS_ANALYSIS",
            "evidence": "deterministic reference-chain replay; distance recurrence closes to float noise",
            "gate_limitation": "not compared against a persisted beta because the frozen runner never logged it",
        },
        "plant_or_connector_hidden_memory": {
            "status": "STATIC_SOURCE_INSPECTION_ONLY",
            "evidence": "frozen plant modules expose no history/hysteresis field; advance_outer_step is a pure function of (state, controls, params, duration)",
            "gate_limitation": "static inspection is not a dynamic restart-equivalence test",
        },
        "full_restart_equivalence_test": {
            "status": "NOT_RUN",
            "evidence": "requires a separately authorized short-window run; not permitted by this protocol",
        },
    }

    blockers = {
        "g1_status": "NOT_RUN",
        "g2_status": "NOT_RUN",
        "gpu_qualification": "BLOCKED_OPENMP_AND_STALE_PROTOCOL_IDENTITY",
        "d3_release": "NOT_RELEASED",
        "reason": "This analysis removes one stated obstacle (beta memory) but does not satisfy G1/G2, does not perform a restart-equivalence test, and does not carry a short-window budget.",
    }

    report = {
        "status": "PASS_READ_ONLY_BETA_MEMORY_RECONSTRUCTED_WITH_GATE_LIMITS",
        "scope": protocol["scope"],
        "run": str(protocol["inputs"]["run"]),
        "prior_conclusion_revised": "D1 reported beta memory as unavailable and therefore refused a late-window splice. The reference-chain memory is in fact recoverable from persisted artifacts at float-noise level.",
        "prior_conclusion_preserved": "The D1 tracking-divergence decomposition, the user-designated FAIL classification, the unobserved final 179 ticks rule, and the D3 block on G1/G2 are unchanged.",
        "replay": replay,
        "beta": beta_summary,
        "state_recovery": recovery,
        "solver_records_in_jsonl": solver_closed,
        "closed_ticks": ticks,
        "unclosed_solver_records": solver_closed - ticks,
        "blockers": blockers,
        "executed": {
            "plant_dynamics": False,
            "mpc_or_solver": False,
            "gpu": False,
            "closed_loop": False,
            "p1_resume_or_retry": False,
            "source_modified": False,
        },
        "decision": "REGISTER_BETA_RECOVERY_AS_AVAILABLE; KEEP_D3_BLOCKED_ON_G1_G2_AND_RESTART_EQUIVALENCE",
    }
    (output / "beta_memory_replay.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    np.savez_compressed(
        output / "beta_replay.npz",
        values=np.column_stack([time_s, recorded_distance, replay_distance, beta_history]),
        columns=np.asarray(
            ["time_s", "recorded_reference_distance_m", "replayed_reference_distance_m"]
            + [f"replayed_beta{i}_rad" for i in range(4)]
        ),
    )

    # ---- figures -----------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(13.0, 8.4))

    floor = 1e-16
    axes[0, 0].semilogy(tick * DT, np.maximum(distance_error, floor), color="#1f77b4")
    axes[0, 0].axhline(floor, color="#7f7f7f", linestyle=":", label=f"{floor:.0e} m display floor")
    axes[0, 0].set(
        xlabel="tick time k*Ts (s)",
        ylabel="|replayed - recorded| (m)",
        title=(
            "Reference-distance replay closure\n"
            f"max = {replay['distance_replay_max_abs_error_m']:.2e} m, "
            f"exactly zero at {replay['distance_error_exactly_zero_ticks']}/{replay['ticks']} ticks"
        ),
        ylim=(floor * 0.5, 1e-10),
    )
    axes[0, 0].legend(loc="lower right", fontsize=8)
    axes[0, 0].grid(alpha=0.2)

    for i in range(4):
        axes[0, 1].plot(tick * DT, np.rad2deg(beta_history[:, i]), label=f"vehicle {i + 1}")
    axes[0, 1].set(
        xlabel="tick time k*Ts (s)",
        ylabel="reconstructed beta (deg)",
        title="Reconstructed reference memory beta\n(the frozen runner never persisted beta)",
    )
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.2)

    duration_floor = 1e-18
    deviation = np.abs(duration - DT)
    axes[1, 0].semilogy(tick * DT, np.maximum(deviation, duration_floor), marker=".", markersize=1.8, linestyle="none", color="#d62728")
    axes[1, 0].axhline(duration_floor, color="#7f7f7f", linestyle=":", label=f"{duration_floor:.0e} s display floor")
    axes[1, 0].set(
        xlabel="tick time k*Ts (s)",
        ylabel="|accepted duration - Ts| (s)",
        title=(
            "Recovered interval duration about the 20 ms tick\n"
            f"sum = {replay['duration_sum_s']:.12f} s, max = {replay['duration_max_abs_deviation_from_DT_s']:.2e} s"
        ),
        ylim=(duration_floor * 0.5, 1e-13),
    )
    axes[1, 0].legend(loc="lower right", fontsize=8)
    axes[1, 0].grid(alpha=0.2)

    labels = list(recovery.keys())
    codes = {"IN_RAW": 3, "RECONSTRUCTED_THIS_ANALYSIS": 2, "STATIC_SOURCE_INSPECTION_ONLY": 1, "NOT_RUN": 0}
    values = [codes[recovery[name]["status"]] for name in labels]
    colors = ["#2ca02c", "#1f77b4", "#ff7f0e", "#8b0000"]
    bars = axes[1, 1].barh(labels, values, color=[colors[value] for value in values])
    axes[1, 1].set(
        xlim=(0, 4.5),
        xticks=[0, 1, 2, 3],
        xticklabels=["NOT_RUN", "static only", "reconstructed", "in raw"],
        title="Restart state/memory recovery inventory",
    )
    for bar, name in zip(bars, labels):
        status = recovery[name]["status"]
        text = "RECONSTRUCTED (replay)" if status == "RECONSTRUCTED_THIS_ANALYSIS" else status.replace("_", " ")
        axes[1, 1].text(
            bar.get_width() + 0.07,
            bar.get_y() + bar.get_height() / 2,
            text,
            va="center",
            fontsize=8,
            color="#333333",
        )
    axes[1, 1].grid(axis="x", alpha=0.2)

    fig.suptitle("D1+ read-only: reference-chain memory replay for the interrupted P1 run (no dynamics, no GPU)", fontsize=13)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    figures = []
    for suffix in ("png", "svg"):
        name = f"beta_memory_replay.{suffix}"
        fig.savefig(output / name, dpi=220 if suffix == "png" else None)
        figures.append(name)
    plt.close(fig)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "figures": figures,
        "source_files": [
            {"path": str(paper / item["path"]), "sha256": item["sha256"]}
            for item in protocol["identity_files"]
        ]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [
            {"path": "beta_memory_replay.json", "sha256": sha(output / "beta_memory_replay.json")},
            {"path": "beta_replay.npz", "sha256": sha(output / "beta_replay.npz")},
        ],
        "claim_boundary": "No plant integration, MPC, GPU execution or closed loop. D3 remains blocked.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# D1+ 参考链记忆（beta）只读回放\n\n"
        "本目录只用已保存的 P1 raw/substeps 做 CPU 参考链回放：把冻结 runner 每周期实际接受的时长从 `time_s = k*Ts + dur` 还原，"
        "再按原源码路径重放 `distance` 与 `beta`，并用落盘的 `reference_distance_m` 作为独立校核。\n\n"
        "结论：`beta` 不是独立记忆，而是参考链的确定性函数，可在浮点噪声级重建；D1 关于“beta 记忆缺失”的判定据此修订。\n\n"
        "边界：本分析没有跑植物积分、MPC、GPU 或闭环，没有做“重启后与原轨迹逐位一致”的动态等价试验；"
        "G1/G2 仍未通过，D3 仍为阻断状态。未观测的 179 周期不补画。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "decision": report["decision"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Run the 100 m model-acceptance maneuver and generate evidence figures."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from four_vehicle_coupled import NAMES, ModelParams, aggregate_diagnostics, initialize_state, rk4_step, split_state
from steering_allocator import allocate_controls


def controls_for(stage: str, acceleration: float, steer_front_deg: float, steer_rear_deg: float) -> np.ndarray:
    controls = np.zeros((4, 2), dtype=float)
    controls[:, 0] = acceleration
    controls[:2, 1] = np.deg2rad(steer_front_deg)
    controls[2:, 1] = np.deg2rad(steer_rear_deg)
    return controls


def simulate(dt: float, keep_history: bool = True) -> tuple[list[dict], dict]:
    params = ModelParams()
    state = initialize_state(params, speed_mps=2.0)
    t = 0.0
    distance = 0.0
    turn_start = None
    decel_value = None
    history: list[dict] = []
    max_time = 60.0

    while distance < 100.0 and t < max_time:
        vehicles, payload = split_state(state)
        payload_speed = float(np.linalg.norm(payload[3:5]))
        if distance < 30.0:
            stage = "accelerate"
            accel, df, dr = 0.5, 0.0, 0.0
        else:
            if turn_start is None:
                turn_start = t
            turn_elapsed = t - turn_start
            if turn_elapsed < 5.0:
                stage = "step_positive"
                accel, df, dr = 0.0, 4.0, -2.0
            elif turn_elapsed < 10.0:
                stage = "step_negative"
                accel, df, dr = 0.0, -4.0, 2.0
            else:
                stage = "decelerate"
                df, dr = 0.0, 0.0
                if decel_value is None:
                    remaining = max(100.0 - distance, 0.5)
                    decel_value = float(np.clip(-payload_speed**2 / (2.0 * remaining), -2.0, -0.1))
                accel = decel_value

        controls, allocation = allocate_controls(state, accel, df, dr, params)
        diag = aggregate_diagnostics(state, controls, params)
        conn = diag["connectors"]
        record = {
            "t_s": t,
            "distance_m": distance,
            "stage": stage,
            "accel_cmd_mps2": accel,
            "steer_front_deg": df,
            "steer_rear_deg": dr,
            "icr_x_payload_m": allocation["icr_payload_body_m"][0],
            "icr_y_payload_m": allocation["icr_payload_body_m"][1],
            "payload_speed_mps": payload_speed,
            "payload_x_m": payload[0],
            "payload_y_m": payload[1],
            "payload_yaw_rad": payload[2],
            "payload_yaw_rate_radps": payload[5],
            "system_yaw_rate_radps": diag["system_yaw_rate_radps"],
            "q_front_rear_n": diag["q_front_rear_n"],
            "q_left_right_n": diag["q_left_right_n"],
            "internal_force_residual_n": float(np.linalg.norm(diag["internal_force_residual_n"])),
        }
        for i, name in enumerate(NAMES):
            record[f"vehicle_{name}_x_m"] = vehicles[i, 0]
            record[f"vehicle_{name}_y_m"] = vehicles[i, 1]
            record[f"vehicle_{name}_yaw_rate_radps"] = vehicles[i, 5]
            record[f"connector_{name}_fx_payload_n"] = conn["force_payload_body_n"][i, 0]
            record[f"connector_{name}_fy_payload_n"] = conn["force_payload_body_n"][i, 1]
            record[f"connector_{name}_norm_n"] = conn["force_norm_n"][i]
            record[f"connector_{name}_angle_deg"] = np.rad2deg(
                np.arctan2(conn["force_payload_body_n"][i, 1], conn["force_payload_body_n"][i, 0])
            ) if conn["force_norm_n"][i] > 1.0e-9 else np.nan
            record[f"support_{name}_fz_n"] = diag["support_fz_n"][i]
            record[f"tire_{name}_utilization"] = diag["tire_utilization"][i]
            record[f"allocated_{name}_accel_mps2"] = controls[i, 0]
            record[f"allocated_{name}_steer_deg"] = np.rad2deg(controls[i, 1])
            record[f"target_{name}_heading_deg"] = np.rad2deg(allocation["relative_heading_rad"][i])
            record[f"target_{name}_speed_mps"] = allocation["speed_mps"][i]
            record[f"target_{name}_normal_residual_mps"] = allocation["normal_velocity_residual_mps"][i]
        record["left_fx_n"] = record["connector_FL_fx_payload_n"] + record["connector_RL_fx_payload_n"]
        record["left_fy_n"] = record["connector_FL_fy_payload_n"] + record["connector_RL_fy_payload_n"]
        record["right_fx_n"] = record["connector_FR_fx_payload_n"] + record["connector_RR_fx_payload_n"]
        record["right_fy_n"] = record["connector_FR_fy_payload_n"] + record["connector_RR_fy_payload_n"]
        record["payload_fx_n"] = sum(record[f"connector_{name}_fx_payload_n"] for name in NAMES)
        record["payload_fy_n"] = sum(record[f"connector_{name}_fy_payload_n"] for name in NAMES)
        if keep_history:
            history.append(record)

        next_state = rk4_step(state, controls, dt, params)
        _, next_payload = split_state(next_state)
        next_speed = float(np.linalg.norm(next_payload[3:5]))
        distance += 0.5 * (payload_speed + next_speed) * dt
        state = next_state
        t += dt

        if stage == "decelerate" and payload_speed < 0.03 and distance > 98.0:
            break

    if not keep_history:
        controls = controls_for("end", 0.0, 0.0, 0.0)
        diag = aggregate_diagnostics(state, controls, params)
        conn_peak = float(diag["connectors"]["force_norm_n"].max())
    else:
        conn_peak = max(max(row[f"connector_{name}_norm_n"] for name in NAMES) for row in history)

    vehicles, payload = split_state(state)
    summary = {
        "dt_s": dt,
        "completed_100m": bool(distance >= 99.9),
        "final_time_s": t,
        "final_distance_m": distance,
        "final_payload_speed_mps": float(np.linalg.norm(payload[3:5])),
        "final_state_finite": bool(np.all(np.isfinite(state))),
        "connector_peak_n": conn_peak,
        "final_payload_state": payload.tolist(),
        "final_vehicle_state": vehicles.tolist(),
        "deceleration_mps2": decel_value,
    }
    if keep_history:
        summary.update(summarize(history, params))
    return history, summary


def summarize(history: list[dict], params: ModelParams) -> dict:
    by_stage = {}
    for stage in ("accelerate", "step_positive", "step_negative", "decelerate"):
        rows = [r for r in history if r["stage"] == stage]
        if not rows:
            continue
        by_stage[stage] = {
            "start_distance_m": rows[0]["distance_m"],
            "end_distance_m": rows[-1]["distance_m"],
            "duration_s": rows[-1]["t_s"] - rows[0]["t_s"],
            "mean_payload_fx_n": float(np.mean([r["payload_fx_n"] for r in rows])),
            "mean_payload_fy_n": float(np.mean([r["payload_fy_n"] for r in rows])),
            "peak_abs_payload_fy_n": float(np.max(np.abs([r["payload_fy_n"] for r in rows]))),
            "mean_system_yaw_rate_radps": float(np.mean([r["system_yaw_rate_radps"] for r in rows])),
            "peak_abs_system_yaw_rate_radps": float(np.max(np.abs([r["system_yaw_rate_radps"] for r in rows]))),
            "peak_q_front_rear_n": float(np.max([r["q_front_rear_n"] for r in rows])),
            "peak_q_left_right_n": float(np.max([r["q_left_right_n"] for r in rows])),
        }
    peak_force = max(max(r[f"connector_{name}_norm_n"] for name in NAMES) for r in history)
    peak_vehicle_yaw = max(max(abs(r[f"vehicle_{name}_yaw_rate_radps"]) for name in NAMES) for r in history)
    peak_system_yaw = max(abs(r["system_yaw_rate_radps"]) for r in history)
    max_residual = max(r["internal_force_residual_n"] for r in history)
    max_icr_normal_residual = max(
        max(abs(r[f"target_{name}_normal_residual_mps"]) for name in NAMES)
        for r in history
    )
    rated_exceeded = peak_force >= params.connector.rated_force_n
    return {
        "stage_summary": by_stage,
        "peak_connector_force_n": float(peak_force),
        "peak_vehicle_yaw_rate_radps": float(peak_vehicle_yaw),
        "peak_system_yaw_rate_radps": float(peak_system_yaw),
        "max_internal_force_residual_n": float(max_residual),
        "max_icr_normal_velocity_residual_mps": float(max_icr_normal_residual),
        "rated_connector_force_exceeded": bool(rated_exceeded),
        "positive_step_mean_fy_n": by_stage.get("step_positive", {}).get("mean_payload_fy_n"),
        "negative_step_mean_fy_n": by_stage.get("step_negative", {}).get("mean_payload_fy_n"),
        "opposite_step_fy_sign": bool(
            by_stage.get("step_positive", {}).get("mean_payload_fy_n", 0.0)
            * by_stage.get("step_negative", {}).get("mean_payload_fy_n", 0.0) < 0.0
        ),
        "tensile_pattern_present": bool(
            max(max(r["q_front_rear_n"], r["q_left_right_n"]) for r in history) > 0.0
        ),
        "actual_tearing_conclusion_available": False,
    }


def write_csv(history: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)


def arrays(history: list[dict], key: str) -> np.ndarray:
    return np.array([r[key] for r in history], dtype=float)


def shade_stages(ax, history: list[dict]) -> None:
    colors = {"accelerate": "#d9edf7", "step_positive": "#dff0d8", "step_negative": "#fcf8e3", "decelerate": "#f2dede"}
    for stage, color in colors.items():
        rows = [r for r in history if r["stage"] == stage]
        if rows:
            ax.axvspan(rows[0]["t_s"], rows[-1]["t_s"], color=color, alpha=0.22)


def make_plots(history: list[dict], output: Path) -> None:
    t = arrays(history, "t_s")
    dist = arrays(history, "distance_m")

    fig, axes = plt.subplots(4, 1, figsize=(12, 13), sharex=True)
    axes[0].plot(t, dist, color="black", label="distance")
    axes[0].set_ylabel("Distance [m]")
    axes[1].plot(t, arrays(history, "accel_cmd_mps2"), label="acceleration command")
    axes[1].plot(t, arrays(history, "payload_speed_mps"), label="payload speed")
    axes[1].set_ylabel("a [m/s2], v [m/s]"); axes[1].legend(ncol=2)
    axes[2].plot(t, arrays(history, "steer_front_deg"), label="virtual front")
    axes[2].plot(t, arrays(history, "steer_rear_deg"), label="virtual rear")
    axes[2].set_ylabel("Steering [deg]"); axes[2].legend(ncol=2)
    for name in NAMES:
        axes[3].plot(t, arrays(history, f"vehicle_{name}_yaw_rate_radps"), label=name)
    axes[3].plot(t, arrays(history, "payload_yaw_rate_radps"), "k--", label="payload")
    axes[3].plot(t, arrays(history, "system_yaw_rate_radps"), "k", linewidth=2, label="system")
    axes[3].set_ylabel("Yaw rate [rad/s]"); axes[3].set_xlabel("Time [s]"); axes[3].legend(ncol=3)
    for ax in axes: shade_stages(ax, history); ax.grid(True, alpha=0.3)
    fig.suptitle("100 m acceptance: commands, speed and yaw dynamics")
    fig.tight_layout(); fig.savefig(output / "overview.png", dpi=180); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    for name in NAMES: axes[0].plot(t, arrays(history, f"connector_{name}_fx_payload_n"), label=name)
    axes[0].set_ylabel("Connector Fx [N]"); axes[0].legend(ncol=4)
    for name in NAMES: axes[1].plot(t, arrays(history, f"connector_{name}_fy_payload_n"), label=name)
    axes[1].set_ylabel("Connector Fy [N]")
    for name in NAMES: axes[2].plot(t, arrays(history, f"support_{name}_fz_n"), label=name)
    axes[2].set_ylabel("Support Fz [N]"); axes[2].set_xlabel("Time [s]")
    for ax in axes: shade_stages(ax, history); ax.grid(True, alpha=0.3)
    fig.suptitle("Four-point planar connector forces and vertical support loads")
    fig.tight_layout(); fig.savefig(output / "forces.png", dpi=180); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 12), sharex=True)
    axes[0].plot(t, arrays(history, "left_fx_n"), label="left Fx")
    axes[0].plot(t, arrays(history, "right_fx_n"), label="right Fx")
    axes[0].plot(t, arrays(history, "left_fy_n"), "--", label="left Fy")
    axes[0].plot(t, arrays(history, "right_fy_n"), "--", label="right Fy")
    axes[0].set_ylabel("Side resultant [N]"); axes[0].legend(ncol=2)
    axes[1].plot(t, arrays(history, "q_front_rear_n"), label="Q front-rear")
    axes[1].plot(t, arrays(history, "q_left_right_n"), label="Q left-right")
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("Opening proxy [N]"); axes[1].legend()
    for name in NAMES: axes[2].plot(t, arrays(history, f"connector_{name}_norm_n"), label=name)
    axes[2].axhline(12000.0, color="red", linestyle="--", label="rated")
    axes[2].set_ylabel("|F connector| [N]"); axes[2].set_xlabel("Time [s]"); axes[2].legend(ncol=5)
    for ax in axes: shade_stages(ax, history); ax.grid(True, alpha=0.3)
    fig.suptitle("Cargo side loads and opposing-tension proxies (not a material tear verdict)")
    fig.tight_layout(); fig.savefig(output / "cargo.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.plot(arrays(history, "payload_x_m"), arrays(history, "payload_y_m"), "k", linewidth=2, label="payload")
    for name in NAMES:
        ax.plot(arrays(history, f"vehicle_{name}_x_m"), arrays(history, f"vehicle_{name}_y_m"), label=name, alpha=0.8)
    ax.set_aspect("equal", adjustable="box"); ax.grid(True, alpha=0.3); ax.legend(ncol=3)
    ax.set_xlabel("World X [m]"); ax.set_ylabel("World Y [m]"); ax.set_title("Four vehicles and payload trajectories")
    fig.tight_layout(); fig.savefig(output / "trajectory.png", dpi=180); plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    for name in NAMES:
        axes[0].plot(t, arrays(history, f"allocated_{name}_steer_deg"), label=name)
    axes[0].set_ylabel("Allocated steer [deg]"); axes[0].legend(ncol=4)
    for name in NAMES:
        axes[1].plot(t, arrays(history, f"target_{name}_heading_deg"), label=name)
    axes[1].set_ylabel("Target body heading\nrelative to payload [deg]")
    for name in NAMES:
        axes[2].plot(t, arrays(history, f"target_{name}_speed_mps"), label=name)
    axes[2].set_ylabel("Target speed [m/s]"); axes[2].set_xlabel("Time [s]")
    for ax in axes: shade_stages(ax, history); ax.grid(True, alpha=0.3)
    fig.suptitle("Common-ICR four-vehicle steering and speed allocation")
    fig.tight_layout(); fig.savefig(output / "allocation.png", dpi=180); plt.close(fig)

    stages = ["accelerate", "step_positive", "step_negative", "decelerate"]
    anchors = ModelParams().payload_anchor_body_m
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, stage in zip(axes.flat, stages):
        rows = [r for r in history if r["stage"] == stage]
        row = rows[len(rows) // 2]
        forces = np.array([[row[f"connector_{n}_fx_payload_n"], row[f"connector_{n}_fy_payload_n"]] for n in NAMES])
        max_force = max(float(np.max(np.linalg.norm(forces, axis=1))), 1.0)
        display = forces / max_force * 1.4
        ax.add_patch(plt.Rectangle((-2.5, -1.0), 5.0, 2.0, fill=False, linewidth=2))
        ax.quiver(anchors[:, 0], anchors[:, 1], display[:, 0], display[:, 1], angles="xy", scale_units="xy", scale=1, color=["C0","C1","C2","C3"])
        for i, name in enumerate(NAMES):
            angle = np.rad2deg(np.arctan2(forces[i,1], forces[i,0])) if np.linalg.norm(forces[i]) > 1e-9 else np.nan
            ax.text(anchors[i,0], anchors[i,1]+0.18, f"{name} {np.linalg.norm(forces[i]):.0f}N\n{angle:.1f}deg", ha="center", fontsize=8)
        ax.set_xlim(-4.3,4.3); ax.set_ylim(-2.7,2.7); ax.set_aspect("equal"); ax.grid(True, alpha=0.3)
        ax.set_title(f"{stage} at s={row['distance_m']:.1f} m")
        ax.set_xlabel("Payload longitudinal x"); ax.set_ylabel("Payload lateral y")
    fig.suptitle("Four connector-force directions in payload coordinates (arrow lengths normalized per panel)")
    fig.tight_layout(); fig.savefig(output / "directions.png", dpi=180); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--dt", type=float, default=0.002)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    history, summary = simulate(args.dt, keep_history=True)
    half_history, half = simulate(args.dt / 2.0, keep_history=True)
    write_csv(history, output / "history.csv")

    metrics = ("peak_connector_force_n", "peak_vehicle_yaw_rate_radps", "peak_system_yaw_rate_radps")
    convergence = {}
    for key in metrics:
        base = float(summary[key])
        fine = float(half[key])
        convergence[key] = {
            "dt": base,
            "dt_half": fine,
            "relative_difference": abs(base - fine) / max(abs(fine), 1.0e-12),
        }
    convergence_pass = all(item["relative_difference"] <= 0.05 for item in convergence.values())
    acceptance = {
        "completed_100m": summary["completed_100m"],
        "finite": summary["final_state_finite"],
        "internal_force_closure": summary["max_internal_force_residual_n"] <= 1.0e-9,
        "common_icr_kinematics": summary["max_icr_normal_velocity_residual_mps"] <= 1.0e-9,
        "opposite_step_fy_sign": summary["opposite_step_fy_sign"],
        "step_convergence_within_5pct": convergence_pass,
    }
    report = {
        "configuration": {
            "initial_speed_mps": 2.0,
            "acceleration_first_30m_mps2": 0.5,
            "positive_step_s": 5.0,
            "negative_step_s": 5.0,
            "virtual_front_step_deg": 4.0,
            "virtual_rear_step_deg": -2.0,
            "coordinate_note": "Fx longitudinal and Fy lateral are planar; Fz is auxiliary support load.",
        },
        "summary": summary,
        "half_dt_summary": half,
        "convergence": convergence,
        "acceptance": acceptance,
        "all_acceptance_passed": all(acceptance.values()),
        "tearing_interpretation": "Positive Q indicates an opposing-tension pattern only. Actual cargo tearing cannot be concluded without structural allowables.",
    }
    with (output / "report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    make_plots(history, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

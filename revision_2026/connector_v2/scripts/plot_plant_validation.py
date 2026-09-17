from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DT = 0.002
NAMES = ["FL", "FR", "RL", "RR"]
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7"]


def load(path: Path) -> dict[str, np.ndarray]:
    z = np.load(path)
    return {k: z[k] for k in z.files}


def save(fig: plt.Figure, out: Path, name: str) -> None:
    fig.tight_layout()
    fig.savefig(out / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def mag(a: dict[str, np.ndarray]) -> np.ndarray:
    return np.linalg.norm(a["force"], axis=-1)


def main() -> None:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    v1 = load(root / "staged_100m_left_v1.npz")
    v2 = load(root / "staged_100m_left_v2.npz")

    # 1. Initial contact establishment (same initial condition/control).
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for a, ls, label in ((v1, "--", "V1"), (v2, "-", "V2")):
        n = min(len(a["time_s"]), int(0.8 / DT))
        ax.plot(a["time_s"][:n], np.max(mag(a)[:n], axis=1), ls, lw=1.5, label=label)
    ax.set(xlabel="Time (s)", ylabel="Maximum connector force (N)", title="Contact establishment, identical inputs")
    ax.grid(alpha=0.25); ax.legend()
    save(fig, out, "01_contact_establishment.png")

    # 2. Constitutive trajectories actually visited by the four-vehicle system.
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.5))
    for a, marker, label in ((v1, ".", "V1"), (v2, ".", "V2")):
        stride = max(1, len(a["penetration"]) // 5000)
        axs[0].scatter(a["penetration"][::stride].ravel() * 1e3, mag(a)[::stride].ravel(), s=2, alpha=.25, label=label)
        axs[1].scatter(a["vn"][::stride].ravel(), mag(a)[::stride].ravel(), s=2, alpha=.25, label=label)
    axs[0].set(xlabel="Penetration (mm)", ylabel="Connector force (N)", title="Force--penetration")
    axs[1].set(xlabel="Normal speed (m/s)", ylabel="Connector force (N)", title="Force--normal-speed")
    for ax in axs: ax.grid(alpha=.2); ax.legend(markerscale=4)
    save(fig, out, "02_force_relations.png")

    # 3. Stored energy and damping power.
    fig, axs = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    for a, ls, label in ((v1, "--", "V1"), (v2, "-", "V2")):
        axs[0].plot(a["time_s"], np.sum(a["energy"], axis=1), ls, lw=1, label=label)
        axs[1].plot(a["time_s"], np.sum(a["damping"], axis=1), ls, lw=1, label=label)
    axs[0].set(ylabel="Stored energy (J)", title="Connector energy (V2 stops on ultimate-force limit)")
    axs[1].set(xlabel="Time (s)", ylabel="Damping power (W)")
    for ax in axs: ax.grid(alpha=.2); ax.legend()
    save(fig, out, "03_energy_dissipation.png")

    # 4. Four connector components and force directions for failed 100 m case.
    fig, axs = plt.subplots(4, 1, figsize=(11, 9), sharex=True)
    x = v2["distance_m"]
    for j, ax in enumerate(axs):
        ax.plot(x, v2["force"][:, j, 0], color=COLORS[j], lw=1, label=f"{NAMES[j]} Fx")
        ax.plot(x, v2["force"][:, j, 1], color=COLORS[j], lw=1, ls="--", label=f"{NAMES[j]} Fy")
        ax.axhline(0, color="black", lw=.4); ax.grid(alpha=.2); ax.legend(ncol=2, loc="upper left")
        ax.set_ylabel("N")
    axs[0].set_title("V2 four-point force components; run stopped at 75.587 m")
    axs[-1].set_xlabel("Distance (m)")
    save(fig, out, "04_100m_four_point_forces.png")

    fig, axs = plt.subplots(2, 2, figsize=(10, 8), sharex=True, sharey=True)
    take = np.unique(np.linspace(0, len(x) - 1, 36).astype(int))
    for j, ax in enumerate(axs.ravel()):
        f = v2["force"][take, j]
        scale = np.maximum(np.linalg.norm(f, axis=1).max(), 1.0)
        ax.quiver(x[take], np.zeros(len(take)), f[:, 0] / scale, f[:, 1] / scale,
                  angles="xy", scale_units="xy", scale=0.12, width=.004, color=COLORS[j])
        ax.set_title(f"{NAMES[j]} force direction (normalized by {scale:.0f} N)")
        ax.grid(alpha=.2); ax.set_ylim(-1.1, 1.1)
    for ax in axs[-1]: ax.set_xlabel("Distance (m)")
    for ax in axs[:, 0]: ax.set_ylabel("Normalized Fy")
    save(fig, out, "05_100m_force_directions.png")

    # 5. Vehicle/payload/system yaw rates.
    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for j in range(4):
        axs[0].plot(v2["time_s"], v2["state"][:, j * 6 + 5], lw=.8, color=COLORS[j], label=NAMES[j])
    for a, ls, label in ((v1, "--", "V1"), (v2, "-", "V2")):
        axs[1].plot(a["time_s"], a["state"][:, 29], ls, lw=1, label=label)
        axs[2].plot(a["time_s"], a["system_yaw"], ls, lw=1, label=label)
    axs[0].set(ylabel="Vehicle yaw rate (rad/s)", title="Yaw response under identical controls")
    axs[1].set(ylabel="Payload yaw rate (rad/s)")
    axs[2].set(xlabel="Time (s)", ylabel="System yaw rate (rad/s)")
    for ax in axs: ax.grid(alpha=.2); ax.legend(ncol=4)
    save(fig, out, "06_yaw_rates.png")

    # 6. Legacy projections versus complete internal-force norm.
    fig, axs = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    axs[0].plot(v2["time_s"], v2["q"][:, 0], lw=.9, label="Q_FR")
    axs[0].plot(v2["time_s"], v2["q"][:, 1], lw=.9, label="Q_LR")
    axs[1].plot(v2["time_s"], v2["internal_norm"], color="#D55E00", lw=1, label="Complete internal-force norm")
    axs[0].set(ylabel="Legacy projection (N)", title="Legacy Q projections do not span complete internal loading")
    axs[1].set(xlabel="Time (s)", ylabel="Internal force norm (N)")
    for ax in axs: ax.grid(alpha=.2); ax.legend()
    save(fig, out, "07_q_vs_complete_internal_force.png")


if __name__ == "__main__":
    main()

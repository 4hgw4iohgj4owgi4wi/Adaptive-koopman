import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib import transforms
from matplotlib.patches import Rectangle


def _wrap_angle(ang):
    return (np.asarray(ang, dtype=float) + np.pi) % (2.0 * np.pi) - np.pi


def _interp_ref_psi(s_vals, s_ref_path, psi_ref_path):
    s_clip = np.clip(s_vals, float(np.min(s_ref_path)), float(np.max(s_ref_path)))
    return np.interp(s_clip, s_ref_path, psi_ref_path)


def _build_global_histories(
    *,
    xt_actual_vehicles,
    ref_vehicle_histories,
    actual_sim_steps,
    s_ref_path,
    x_path,
    y_ref_path,
    psi_ref_path,
    frenet_to_global,
):
    veh_data = []
    n_vehicle = int(len(xt_actual_vehicles))
    n_frames = 0

    s_min = float(np.min(s_ref_path)) - 10.0
    s_max = float(np.max(s_ref_path)) + 10.0

    for v in range(n_vehicle):
        x_hist = np.asarray(xt_actual_vehicles[v], dtype=float)
        n_hist = int(min(actual_sim_steps + 1, x_hist.shape[0]))
        if n_hist <= 1:
            continue

        s = np.clip(x_hist[:n_hist, 0], s_min, s_max)
        ey = x_hist[:n_hist, 1]
        epsi = x_hist[:n_hist, 2]
        xg, yg = frenet_to_global(s, ey, s_ref_path, x_path, y_ref_path, psi_ref_path)
        psi_g = _wrap_angle(_interp_ref_psi(s, s_ref_path, psi_ref_path) + epsi)

        xr = np.array([], dtype=float)
        yr = np.array([], dtype=float)
        if ref_vehicle_histories is not None and v < len(ref_vehicle_histories):
            ref_hist = np.asarray(ref_vehicle_histories[v], dtype=float)
            if ref_hist.ndim == 2 and ref_hist.shape[0] > 1 and ref_hist.shape[1] >= 2:
                n_ref = int(min(ref_hist.shape[0], n_hist))
                s_ref_v = np.clip(ref_hist[:n_ref, 0], s_min, s_max)
                ey_ref_v = ref_hist[:n_ref, 1]
                xr, yr = frenet_to_global(
                    s_ref_v, ey_ref_v, s_ref_path, x_path, y_ref_path, psi_ref_path
                )

        n_frames = max(n_frames, n_hist)
        veh_data.append(
            {
                "vehicle_index": v,
                "n_hist": n_hist,
                "x": np.asarray(xg, dtype=float),
                "y": np.asarray(yg, dtype=float),
                "psi": np.asarray(psi_g, dtype=float),
                "x_ref": np.asarray(xr, dtype=float),
                "y_ref": np.asarray(yr, dtype=float),
            }
        )

    if len(veh_data) == 0:
        raise RuntimeError("No valid vehicle history for animation.")
    return veh_data, n_frames


def animate_a1_tracking_rectangles(
    *,
    xt_actual_vehicles,
    ref_vehicle_histories,
    actual_sim_steps,
    s_ref_path,
    x_path,
    y_ref_path,
    psi_ref_path,
    frenet_to_global,
    dt=0.02,
    vehicle_length=4.4,
    vehicle_width=1.9,
    tail_points=120,
    frame_step=1,
    interval_ms=None,
    figsize=(12, 8),
    dark_theme=True,
    show_vehicle_refs=True,
    repeat=False,
):
    """Animate TF11-A1 four-vehicle tracking with rotated rectangle vehicles.

    Returns:
        fig, anim
    """
    veh_data, n_frames = _build_global_histories(
        xt_actual_vehicles=xt_actual_vehicles,
        ref_vehicle_histories=ref_vehicle_histories,
        actual_sim_steps=actual_sim_steps,
        s_ref_path=s_ref_path,
        x_path=x_path,
        y_ref_path=y_ref_path,
        psi_ref_path=psi_ref_path,
        frenet_to_global=frenet_to_global,
    )

    colors = ["tab:blue", "tab:purple", "tab:green", "tab:red"]
    labels = ["车1(前左)", "车2(前右)", "车3(后左)", "车4(后右)"]

    frame_step = max(1, int(frame_step))
    if interval_ms is None:
        interval_ms = max(15, int(1000.0 * float(dt) * frame_step))

    if dark_theme:
        plt.style.use("dark_background")

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(x_path, y_ref_path, color="white" if dark_theme else "black", linewidth=2.4, label="货物中心参考路径")

    # Compute axis ranges from all vehicle tracks + reference path.
    x_all = [np.asarray(x_path, dtype=float)]
    y_all = [np.asarray(y_ref_path, dtype=float)]
    for vd in veh_data:
        x_all.append(vd["x"])
        y_all.append(vd["y"])
        if show_vehicle_refs:
            x_all.append(vd["x_ref"])
            y_all.append(vd["y_ref"])
    x_concat = np.concatenate(x_all)
    y_concat = np.concatenate(y_all)
    x_pad = 2.8
    y_pad = 2.2
    ax.set_xlim(float(np.min(x_concat) - x_pad), float(np.max(x_concat) + x_pad))
    ax.set_ylim(float(np.min(y_concat) - y_pad), float(np.max(y_concat) + y_pad))
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.30)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("TF11-A1 四车刚性搬运路径跟踪（矩形车身实时动画）")

    trace_lines = []
    ref_lines = []
    rect_patches = []
    center_dots = []

    for vd in veh_data:
        vid = int(vd["vehicle_index"])
        c = colors[vid % len(colors)]
        lab = labels[vid] if vid < len(labels) else f"车{vid + 1}"

        ref_line = ax.plot(
            vd["x_ref"],
            vd["y_ref"],
            linestyle=":",
            linewidth=1.0,
            alpha=0.55,
            color=c,
            label=f"{lab} 参考",
            zorder=1,
        )[0]
        ref_lines.append(ref_line)
        if not show_vehicle_refs:
            ref_line.set_visible(False)

        tr = ax.plot([], [], linestyle="-", linewidth=1.8, color=c, label=lab, zorder=2)[0]
        trace_lines.append(tr)

        rect = Rectangle(
            xy=(-0.5 * vehicle_length, -0.5 * vehicle_width),
            width=vehicle_length,
            height=vehicle_width,
            angle=0.0,
            facecolor=c,
            edgecolor="white" if dark_theme else "black",
            linewidth=1.2,
            alpha=0.72,
            zorder=4,
        )
        ax.add_patch(rect)
        rect_patches.append(rect)

        dot = ax.plot([], [], marker="o", markersize=4.0, color=c, zorder=5)[0]
        center_dots.append(dot)

    time_text = ax.text(
        0.02, 0.96, "", transform=ax.transAxes, fontsize=10, verticalalignment="top"
    )
    ax.legend(loc="upper right", fontsize=9, ncol=2)

    def _update(k):
        frame_idx = int(np.clip(k, 0, n_frames - 1))
        for i, vd in enumerate(veh_data):
            idx = min(frame_idx, vd["n_hist"] - 1)
            i0 = max(0, idx - int(tail_points))
            trace_lines[i].set_data(vd["x"][i0 : idx + 1], vd["y"][i0 : idx + 1])
            center_dots[i].set_data([vd["x"][idx]], [vd["y"][idx]])

            trans = (
                transforms.Affine2D()
                .rotate(float(vd["psi"][idx]))
                .translate(float(vd["x"][idx]), float(vd["y"][idx]))
                + ax.transData
            )
            rect_patches[i].set_transform(trans)

        time_text.set_text(f"t = {frame_idx * float(dt):.2f} s")
        artists = trace_lines + center_dots + rect_patches + [time_text]
        return artists

    frame_indices = np.arange(0, n_frames, frame_step, dtype=int)
    if frame_indices[-1] != (n_frames - 1):
        frame_indices = np.append(frame_indices, n_frames - 1)

    anim = animation.FuncAnimation(
        fig,
        _update,
        frames=frame_indices,
        interval=int(interval_ms),
        blit=False,
        repeat=bool(repeat),
    )
    anim._a1_frame_indices = frame_indices
    return fig, anim


def live_plot_a1_tracking_rectangles(
    *,
    xt_actual_vehicles,
    ref_vehicle_histories,
    actual_sim_steps,
    s_ref_path,
    x_path,
    y_ref_path,
    psi_ref_path,
    frenet_to_global,
    dt=0.02,
    playback_speed=1.0,
    **kwargs,
):
    """Play A1 tracking in pseudo real-time (plt.pause loop) with car rectangles.

    Notes:
    - Best with an interactive backend (Qt/Tk).
    - In Jupyter, run `%matplotlib qt` for smoother live playback.
    """
    fig, anim = animate_a1_tracking_rectangles(
        xt_actual_vehicles=xt_actual_vehicles,
        ref_vehicle_histories=ref_vehicle_histories,
        actual_sim_steps=actual_sim_steps,
        s_ref_path=s_ref_path,
        x_path=x_path,
        y_ref_path=y_ref_path,
        psi_ref_path=psi_ref_path,
        frenet_to_global=frenet_to_global,
        dt=dt,
        **kwargs,
    )
    # Stop automatic event source, then manually step for real-time feeling.
    anim.event_source.stop()
    plt.show(block=False)

    frame_indices = getattr(anim, "_a1_frame_indices", None)
    if frame_indices is None:
        n_frames = int(anim.save_count) if anim.save_count is not None else int(actual_sim_steps + 1)
        frame_indices = np.arange(0, n_frames, dtype=int)

    pause_dt = max(0.001, float(dt) / max(float(playback_speed), 1e-6))
    update_fn = anim._func
    for k in frame_indices:
        update_fn(int(k))
        fig.canvas.draw_idle()
        plt.pause(pause_dt)
    return fig, anim

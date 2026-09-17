import numpy as np

from dynamics.sync_pendulum import FK_solver


def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    """
    Generate nominal and changed trajectories for single-vehicle path tracking.

    Returns
    -------
    X_1 : nominal trajectories, shape (num_traj, num_snaps, n)
    X_2 : changed trajectories, shape (num_traj, num_snaps, n)
    U   : control inputs, shape (num_traj, num_snaps-1, m)
    """
    n = pars['num_states']
    m = pars['num_inputs']
    dt = pars['dt']

    delta_max = pars.get('delta_max', 0.08)
    ax_max = pars.get('ax_max', 2.0)

    X_1 = np.zeros((num_traj, num_snaps, n))
    X_2 = np.zeros((num_traj, num_snaps, n))
    U = np.zeros((num_traj, num_snaps - 1, m))

    for i in range(num_traj):
        # initial condition near path-tracking equilibrium
        x0 = np.array([
            np.random.uniform(-0.5, 0.5),   # e_y
            np.random.uniform(-0.1, 0.1),   # e_psi
            np.random.uniform(-0.5, 0.5),   # v_y
            np.random.uniform(-0.2, 0.2),   # r
            np.random.uniform(-2.0, 2.0),   # e_v
        ])

        X_1[i, 0, :] = x0
        X_2[i, 0, :] = x0.copy()

        num_list = np.linspace(1, 10, 10)
        seed_1 = np.random.choice(num_list)
        seed_2 = np.random.choice(num_list)

        for j in range(num_snaps - 1):
            if pars.get("U_type", "random") == "random":
                delta = np.random.uniform(-delta_max, delta_max)
                a_x = np.random.uniform(-ax_max, ax_max)
                U[i, j, :] = np.array([delta, a_x])

            elif pars.get("U_type", "random") == "sinusoidal":
                delta = delta_max * np.sin(seed_1 * np.pi * j * dt)
                a_x = ax_max * np.cos(seed_2 * np.pi * j * dt)
                U[i, j, :] = np.array([delta, a_x])

            X_1[i, j + 1, :] = FK_solver(X_1[i, j, :], U[i, j, :], pars)
            X_2[i, j + 1, :] = FK_solver(
                X_2[i, j, :], U[i, j, :], pars_new, sensor_noise, SNR_DB, j
            )

    return X_1, X_2, U


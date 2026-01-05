import numpy as np

def moving_average(x, window_samples):
    if window_samples <= 1:
        return x.copy()

    kernel = np.ones(window_samples) / window_samples
    y = np.convolve(x, kernel, mode="same")
    return y

def estimate_flow(t_s, mass_g_filt):
    dm_dt = np.gradient(mass_g_filt, t_s)
    flow_ml_s = -dm_dt
    return flow_ml_s


def detect_void(
    t_s: np.ndarray,
    flow_ml_s: np.ndarray,
    flow_thr: float,
    t_start_s: float = 1.0,
    t_stop_s: float = 2.0,
):
    """
    Detect a single void interval using threshold + hysteresis.

    Returns:
      start_t_s, stop_t_s, start_idx, stop_idx

    If not found:
      (None, None, None, None)

    Notes:
    - Void "start" = flow > flow_thr continuously for >= t_start_s
    - Void "stop"  = after start, flow <= flow_thr continuously for >= t_stop_s
    """
    t_s = np.asarray(t_s)
    flow_ml_s = np.asarray(flow_ml_s)

    if t_s.ndim != 1 or flow_ml_s.ndim != 1 or len(t_s) != len(flow_ml_s):
        raise ValueError("t_s and flow_ml_s must be 1D arrays of the same length")
    if len(t_s) < 3:
        return None, None, None, None

    dt = np.diff(t_s)
    if not np.all(dt > 0):
        raise ValueError("t_s must be strictly increasing")

    fs = 1.0 / float(np.median(dt))
    n_start = max(1, int(np.ceil(t_start_s * fs)))
    n_stop = max(1, int(np.ceil(t_stop_s * fs)))

    above = flow_ml_s > flow_thr
    start_idx = None

    # Find first run of 'above' long enough
    run = 0
    for i, a in enumerate(above):
        run = run + 1 if a else 0
        if run >= n_start:
            start_idx = i - n_start + 1
            break

    if start_idx is None:
        return None, None, None, None

    # After start, find first run of 'not above' long enough (stop condition)
    run = 0
    stop_idx = None
    for i in range(start_idx, len(above)):
        run = run + 1 if (not above[i]) else 0
        if run >= n_stop:
            # stop at the first sample of the below-threshold run
            stop_idx = i - n_stop + 1
            break

    if stop_idx is None or stop_idx <= start_idx:
        return None, None, None, None

    return float(t_s[start_idx]), float(t_s[stop_idx]), int(start_idx), int(stop_idx)


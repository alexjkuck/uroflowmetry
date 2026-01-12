import numpy as np

def moving_average(x, window_samples):
    if window_samples <= 1:
        return x.copy()

    kernel = np.ones(window_samples) / window_samples
    y = np.convolve(x, kernel, mode="same")
    return y

def estimate_flow(t_s, mass_g_filt):
    """
    Estimate flow rate from filtered mass signal.
    
    Uses gradient for derivative. For high noise scenarios, mass_g_filt should
    be heavily smoothed before calling this function.
    """
    dm_dt = np.gradient(mass_g_filt, t_s)
    flow_ml_s = -dm_dt
    return flow_ml_s


def detect_seated(
    t_s: np.ndarray,
    mass_g_filt: np.ndarray,
    baseline_window_s: float = 3.0,
    seated_threshold_g: float = 1000.0,
    persistence_s: float = 0.5,
) -> float | None:
    """
    Detect when person sits down by detecting sustained mass increase above baseline.
    
    Returns:
        seated_t_s: time when seated (or None if not detected)
    
    Method:
        - Estimate baseline from first baseline_window_s seconds
        - Find first time mass > baseline + seated_threshold_g for >= persistence_s
    """
    t_s = np.asarray(t_s)
    mass_g_filt = np.asarray(mass_g_filt)
    
    if len(t_s) < 2 or len(t_s) != len(mass_g_filt):
        return None
    
    dt = np.diff(t_s)
    if len(dt) == 0 or not np.all(dt > 0):
        return None
    
    fs = 1.0 / float(np.median(dt))
    
    # Estimate baseline from initial window
    baseline_end_idx = int(np.searchsorted(t_s, baseline_window_s))
    if baseline_end_idx < 2:
        baseline_end_idx = min(2, len(mass_g_filt))
    
    baseline = np.median(mass_g_filt[:baseline_end_idx])
    threshold = baseline + seated_threshold_g
    
    # Find persistent rise above threshold
    above = mass_g_filt > threshold
    n_persist = max(1, int(np.ceil(persistence_s * fs)))
    
    run = 0
    for i in range(len(above)):
        run = run + 1 if above[i] else 0
        if run >= n_persist:
            seated_idx = i - n_persist + 1
            return float(t_s[seated_idx])
    
    return None


def detect_void(
    t_s: np.ndarray,
    flow_ml_s: np.ndarray,
    flow_thr: float,
    t_start_s: float = 1.0,
    t_stop_s: float = 2.0,
    search_start_s: float = 0.0,
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

    flow_use = np.maximum(flow_ml_s, 0.0)
    above = flow_use > flow_thr
    start_idx = None

    # Find first run of 'above' long enough
    start_search_idx = int(np.searchsorted(t_s, search_start_s))

    run = 0
    for i in range(start_search_idx, len(above)):
        run = run + 1 if above[i] else 0
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


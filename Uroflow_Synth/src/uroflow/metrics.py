import numpy as np

def compute_metrics(
    t_s: np.ndarray,
    mass_g_filt: np.ndarray,
    flow_ml_s: np.ndarray,
    start_idx: int | None,
    stop_idx: int | None,
):
    """
    Compute uroflow metrics within [start_idx, stop_idx).
    Returns a dict. If interval is invalid, returns dict with None values.
    """
    t_s = np.asarray(t_s)
    mass_g_filt = np.asarray(mass_g_filt)
    flow_ml_s = np.asarray(flow_ml_s)

    out = {
        "total_volume_ml": None,
        "q_max_ml_s": None,
        "q_avg_ml_s": None,
        "void_duration_s": None,
        "time_to_qmax_s": None,
        "start_t_s": None,
        "stop_t_s": None,
    }

    if start_idx is None or stop_idx is None:
        return out
    if not (0 <= start_idx < stop_idx <= len(t_s)):
        return out

    # Slice interval (stop is exclusive)
    ti = t_s[start_idx:stop_idx]
    mi = mass_g_filt[start_idx:stop_idx]
    fi = flow_ml_s[start_idx:stop_idx]

    if len(ti) < 2: 
        return out

    fs = 1.0 / float(np.median(np.diff(t_s)))

    start_t = float(t_s[start_idx])
    # stop_idx is exclusive, so use t_s[stop_idx] if valid, otherwise last sample
    if stop_idx < len(t_s):
        stop_t = float(t_s[stop_idx])
    else:
        stop_t = float(t_s[-1])
    duration = float(stop_t - start_t)
    if duration <= 0:
        return out

    # Volume: positive decrease in mass over interval
    # Sanity check: mass should decrease during void (mi[-1] < mi[0])
    # If mass increased, this suggests wrong interval detection (e.g., detected seated step)
    mass_change = mi[-1] - mi[0]
    if mass_change > 0:
        # Mass increased over interval - this is wrong for a void!
        # Return None to flag invalid detection
        return out
    
    volume = float(-mass_change)  # g ~ mL

    # Windowed flow for Qmax (physiological definition)
    qmax_window_s = 0.5  # 500 ms window
    qmax_w = max(1, int(qmax_window_s * fs))

    kernel = np.ones(qmax_w) / qmax_w
    fi_smooth = np.convolve(fi, kernel, mode="same")

    # Qmax and timing
    qmax = float(np.max(fi_smooth))
    imax = int(np.argmax(fi_smooth))
    t_to_qmax = float(ti[imax] - ti[0])


    # Qavg
    qavg = float(volume / duration)

    out.update({
        "total_volume_ml": volume,
        "q_max_ml_s": qmax,
        "q_avg_ml_s": qavg,
        "void_duration_s": duration,
        "time_to_qmax_s": t_to_qmax,
        "start_t_s": start_t,
        "stop_t_s": stop_t,
    })
    return out

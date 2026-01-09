import numpy as np
from uroflow.io import load_raw_session, load_timebase
from uroflow.processing import moving_average, estimate_flow, detect_seated, detect_void
from uroflow.metrics import compute_metrics

# Load data
t_ms, raw = load_raw_session("sessions/test")
t_s, dt_s, fs = load_timebase(t_ms)

# Process
w = max(1, int(0.5 * fs))
mass_g_filt = moving_average(raw, w)
flow = estimate_flow(t_s, mass_g_filt)

# Detect seated time to derive search window
seated_t = detect_seated(t_s, mass_g_filt, baseline_window_s=3.0, seated_threshold_g=1000.0, persistence_s=0.5)
if seated_t is None:
    print("Warning: Could not detect seated time, using start of recording")
    search_start_s = 0.0
else:
    settle_s = 1.5  # wait for person to settle after sitting
    search_start_s = seated_t + settle_s
    print(f"Detected seated at {seated_t:.2f}s, searching from {search_start_s:.2f}s")

# Compute threshold from flow after seated (or from beginning if not detected)
if seated_t is not None:
    search_start_idx = int(np.searchsorted(t_s, search_start_s))
    search_end_idx = min(search_start_idx + int(60 * fs), len(flow))  # next 60s or until end
    if search_start_idx < search_end_idx:
        flow_region = flow[search_start_idx:search_end_idx]
    else:
        flow_region = flow
else:
    flow_region = flow

pos_max = np.max(np.maximum(flow_region, 0.0))

start_t, stop_t, i0, i1 = detect_void(
    t_s,
    flow,
    flow_thr=0.15 * pos_max,
    t_start_s=0.3,
    t_stop_s=0.3,
    search_start_s=search_start_s,
)

if i0 is None or i1 is None:
    print("Detected: no void interval")
else:
    print(
        f"Detected void: start={start_t:.2f}s, "
        f"stop={stop_t:.2f}s, i0={i0}, i1={i1}"
    )

# Metrics
metrics = compute_metrics(t_s, mass_g_filt, flow, i0, i1)
print("Metrics:")

def _fmt(v, nd=2):
    return "None" if v is None else f"{v:.{nd}f}"

print(f"  total_volume_ml   = {_fmt(metrics['total_volume_ml'], 1)} mL")
print(f"  q_max_ml_s        = {_fmt(metrics['q_max_ml_s'], 1)} mL/s")
print(f"  q_avg_ml_s        = {_fmt(metrics['q_avg_ml_s'], 1)} mL/s")
print(f"  void_duration_s   = {_fmt(metrics['void_duration_s'], 2)} s")
print(f"  time_to_qmax_s    = {_fmt(metrics['time_to_qmax_s'], 2)} s")
print(f"  start_t_s         = {_fmt(metrics['start_t_s'], 2)} s")
print(f"  stop_t_s          = {_fmt(metrics['stop_t_s'], 2)} s")

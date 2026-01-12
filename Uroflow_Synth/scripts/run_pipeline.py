import numpy as np
from uroflow.io import load_raw_session, load_timebase
from uroflow.processing import moving_average, estimate_flow, detect_seated, detect_void
from uroflow.metrics import compute_metrics
import sys

session_dir = sys.argv[1] if len(sys.argv) > 1 else "sessions/sim_nominal"
print("Running session:", session_dir)

# Load data
t_ms, raw = load_raw_session(session_dir)
t_s, dt_s, fs = load_timebase(t_ms)

# Detect seated time on RAW signal (before filtering to avoid filter delay artifacts)
seated_t = detect_seated(t_s, raw, baseline_window_s=3.0, seated_threshold_g=1000.0, persistence_s=0.5)

# Process (filter after detection)
# Use very aggressive filtering for high noise scenarios
# Multiple passes of filtering to reduce gradient noise amplification
w1 = max(1, int(1.5 * fs))  # First pass: 1.5s window
mass_temp = moving_average(raw, w1)
w2 = max(1, int(1.0 * fs))  # Second pass: 1.0s window  
mass_g_filt = moving_average(mass_temp, w2)

flow_raw = estimate_flow(t_s, mass_g_filt)

# Smooth flow signal aggressively to reduce noise spikes
flow_smooth_w = max(1, int(1.0 * fs))  # 1.0s window for flow smoothing
flow = moving_average(flow_raw, flow_smooth_w)
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

print("fs:", fs)
print("search_start_s:", search_start_s)
print("t_s range:", float(t_s[0]), "to", float(t_s[-1]))
print("flow stats (signed):", float(np.min(flow)), float(np.max(flow)))
flow_pos = np.maximum(flow, 0.0)
print("flow_pos max:", float(np.max(flow_pos)))
print("flow_pos p90:", float(np.percentile(flow_pos, 90)))


flow_pos_region = np.maximum(flow_region, 0.0)

# Robust threshold computation: use median-based approach to ignore noise spikes
# Trim extreme outliers before computing threshold (more robust than raw percentiles)
p95 = np.percentile(flow_pos_region, 95)  # cap at 95th percentile
flow_pos_trimmed = np.minimum(flow_pos_region, p95)
median_flow = np.median(flow_pos_trimmed)

# Threshold: use 30% of trimmed median or 75th percentile, whichever is higher
# This captures typical flow level while ignoring extreme spikes
p75 = np.percentile(flow_pos_trimmed, 75)
flow_thr = max(1.0, max(median_flow * 0.3, p75 * 0.2))




start_t, stop_t, i0, i1 = detect_void(
    t_s,
    flow,
    flow_thr,
    t_start_s=0.3,  # Increased from 0.2s for more robustness
    t_stop_s=0.4,   # Increased from 0.3s for more robustness
    search_start_s=search_start_s,
)

# Sanity check: ensure void doesn't start before seated (shouldn't happen, but check anyway)
if i0 is not None and seated_t is not None:
    if t_s[i0] < seated_t:
        print(f"WARNING: Detected void start ({t_s[i0]:.2f}s) before seated time ({seated_t:.2f}s) - rejecting")
        start_t, stop_t, i0, i1 = None, None, None, None


# Reject obviously implausible detections
MIN_VOID_S = 5.0
MIN_VOID_ML = 50.0

if i0 is not None and i1 is not None:
    dur_s = float(t_s[i1] - t_s[i0]) if i1 < len(t_s) else float(t_s[-1] - t_s[i0])
    vol_ml = float(-(mass_g_filt[i1 - 1] - mass_g_filt[i0])) if (i1 - 1) >= i0 else 0.0

    if dur_s < MIN_VOID_S or vol_ml < MIN_VOID_ML:
        print(f"Rejecting detection (dur={dur_s:.2f}s, vol={vol_ml:.1f}mL) as implausible")
        start_t, stop_t, i0, i1 = None, None, None, None



if i0 is None or i1 is None:
    print("Detected: no void interval")
else:
    print(
        f"Detected void: start={start_t:.2f}s, "
        f"stop={stop_t:.2f}s, i0={i0}, i1={i1}"
    )
    # Diagnostic: check mass values at interval boundaries
    if i0 < len(mass_g_filt) and i1 <= len(mass_g_filt):
        mass_start = mass_g_filt[i0]
        mass_end = mass_g_filt[i1 - 1] if i1 > 0 else mass_g_filt[i0]
        mass_drop = mass_start - mass_end
        print(f"  Mass at start: {mass_start:.1f}g, at end: {mass_end:.1f}g, drop: {mass_drop:.1f}g")

# --- Post-hoc consistency check: did a void likely occur anyway? ---
# Compare end mass to seated baseline (not overall drop)
LIKELY_VOID_ML = 100.0
baseline_idx = int(np.searchsorted(t_s, search_start_s))
baseline_idx = min(max(baseline_idx, 0), len(mass_g_filt) - 1)

# Baseline mass: median over 2 seconds after seated baseline
baseline_window_s = 2.0
baseline_end_idx = baseline_idx + int(baseline_window_s * fs)
baseline_end_idx = min(baseline_end_idx, len(mass_g_filt))
baseline_mass = np.median(mass_g_filt[baseline_idx:baseline_end_idx])

# End mass: median of last few samples
end_window_samples = min(50, len(mass_g_filt))
mass_end = np.median(mass_g_filt[-end_window_samples:])

total_mass_drop_ml = float(baseline_mass - mass_end)

if i0 is None and total_mass_drop_ml >= LIKELY_VOID_ML:
    print(
        f"WARNING: Likely void missed by detector "
        f"(mass drop from seated baseline ≈ {total_mass_drop_ml:.1f} mL). "
        "Signal may be too noisy or thresholds too strict."
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

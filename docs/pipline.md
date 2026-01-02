# Processing Pipeline – Seat Load → Uroflow Metrics (v0.1)

## 0. Goal
Transform raw seat-load sensor readings into:
1) a cleaned mass-equivalent signal over time
2) an estimated flow-rate signal over time
3) a detected void interval (start/stop)
4) summary uroflowmetry metrics

This pipeline assumes the desired signal is a decrease in seat-load during voiding.

## 1. Inputs and Outputs

### 1.1 Input (from raw.csv)
- t_ms: integer, milliseconds since session start
- raw: numeric, sensor reading (counts or similar)

### 1.2 Intermediate Signals
- mass_g(t): calibrated mass-equivalent (g)
- mass_g_filt(t): filtered mass
- flow_ml_s(t): estimated flow rate (mL/s), defined positive during voiding

Definition:
- flow_ml_s(t) ≈ - d(mass_g_filt)/dt   using 1 g ≈ 1 mL

### 1.3 Output Artifacts
- processed.csv columns:
  - t_ms, mass_g, mass_g_filt, flow_ml_s, state, flags
- metrics.json fields:
  - total_volume_ml, q_max_ml_s, q_avg_ml_s, void_duration_s, time_to_qmax_s, start_t_ms, stop_t_ms

## 2. Pipeline Stages (v0.1)

### Stage A — Validate & Normalize Timebase
Purpose: ensure clean timestamps and compute dt.

Steps:
- Verify t_ms is strictly increasing (or repair by dropping duplicates)
- Compute dt_s between consecutive samples
- Estimate sample_rate_hz from median(dt_s)

Flags:
- non_monotonic_time
- large_time_gap

### Stage B — Calibration (raw → mass_g)
Purpose: map raw sensor units to mass-equivalent grams.

v0.1 options:
- If calibration.scale and calibration.offset exist:
  - mass_g = (raw - offset) * scale
- Else:
  - mass_g = raw (treated as arbitrary units; metrics invalid, but pipeline can be debugged)

Flags:
- uncalibrated

### Stage C — Presence / Seated Detection (state machine base)
Purpose: determine when someone is seated vs empty.

Simple v0.1 method:
- Estimate empty baseline from an initial window (e.g., first N seconds)
- If mass_g rises above baseline + threshold → state = seated
- If mass_g returns near baseline for sustained period → state = empty

Notes:
- This is preliminary; void detection happens later.

Flags:
- no_clear_empty_baseline

### Stage D — Filtering (prepare for differentiation)
Purpose: reduce noise while preserving uroflow-relevant dynamics.

v0.1 filtering approach (choose one, document the choice in code):
- Moving average on mass_g over a short window
OR
- Median filter (for spikes) + moving average

Output:
- mass_g_filt(t)

Flags:
- none (unless filter fails due to missing data)

### Stage E — Flow Estimation (differentiate safely)
Purpose: compute flow_ml_s(t) from filtered mass.

Steps:
- Compute derivative of mass_g_filt with respect to time
- Convert to flow:
  - flow_ml_s = - d(mass_g_filt)/dt_s
- Clamp negative flow to 0 outside voiding OR keep signed flow but interpret later
  (v0.1 recommendation: keep signed flow, but metrics use void interval masking)

Flags:
- derivative_unstable (if dt_s too noisy)

### Stage F — Void Detection (start/stop)
Purpose: identify the void interval robustly.

v0.1 method (threshold + hysteresis):
- Define a flow threshold: flow_thr (mL/s)
- Start time = first time flow exceeds flow_thr for >= T_start seconds
- Stop time = after start, first time flow stays below flow_thr for >= T_stop seconds
- If no valid interval found → no_void_detected

Notes:
- Posture steps can cause spikes; filtering and persistence windows reduce false triggers.

Flags:
- no_void_detected
- multiple_candidates (if logic finds more than one; keep the best by duration/area)

### Stage G — Metric Computation (within void interval)
Compute using samples within [start_t, stop_t]:

- total_volume_ml:
  - total decrease in mass_g_filt over interval (positive value):
    volume = -(mass_g_filt(stop) - mass_g_filt(start))
- q_max_ml_s:
  - max(flow_ml_s) within interval
- q_avg_ml_s:
  - volume / void_duration
- void_duration_s:
  - (stop_t_ms - start_t_ms)/1000
- time_to_qmax_s:
  - time from start to argmax(flow)

Quality checks:
- volume should be > 0
- duration should be within plausible bounds (e.g., 2–120 s for v0.1 sanity check)
- q_max should be plausible (flag if extreme)

Flags:
- implausible_duration
- implausible_qmax
- negative_volume (should not happen if sign convention correct)

### Stage H — State Labeling
Purpose: provide a simple per-sample label for plotting/debugging.

States:
- empty
- seated
- voiding
- postvoid

Rules:
- empty/seated from Stage C
- voiding only within [start, stop]
- postvoid = seated but not voiding after stop

## 3. Parameters (v0.1 defaults)
These will become constants in code and later configurable.

- empty_window_s: 3.0
- seated_threshold_g: TBD
- filter_window_s: 0.3 to 1.0 (depends on sample rate)
- flow_thr_ml_s: TBD
- T_start_s: 1.0
- T_stop_s: 2.0

## 4. Testing Strategy (must be implemented)
Minimum tests before hardware:
1. Synthetic monotonic decrease with known flow → metrics match expected
2. Add gaussian noise → still detects void interval
3. Add posture step (sudden offset) → does not false-trigger or explode derivative

## 5. Known Limitations (v0.1)
- Presence detection may fail without a clear empty baseline at session start
- Posture shifts can mimic voiding if sustained
- Calibration may drift; no drift correction in v0.1

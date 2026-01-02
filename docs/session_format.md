# Session Format – Uroflowmetry Seat Load Prototype

## 1. Purpose
Define the on-disk format for a single recorded “session” (one sit/void event),
including raw sensor data, processed signals, computed metrics, and metadata.

Design goals:
- Preserve raw data for future reprocessing
- Make sessions easy to load in Python (pandas)
- Keep format simple and versioned

## 2. Directory Layout
A single session is stored as one folder:

sessions/
  <session_id>/
    meta.json
    raw.csv
    processed.csv
    metrics.json

Example session_id:
- 2026-01-01T20-15-33Z_001

## 3. File Definitions

### 3.1 meta.json (required)
Contains context needed to interpret the data.

Required fields (v0.1):
- format_version: "0.1"
- session_id: string
- created_utc: ISO-8601 string
- device_id: string (or "unknown")
- sample_rate_hz: number (measured or configured)
- units:
  - raw: string (e.g., "counts")
  - mass: string (e.g., "g")
  - flow: string (e.g., "mL/s")
- calibration:
  - method: string (e.g., "linear")
  - scale: number (g per count) OR null if unknown
  - offset: number (counts) OR null if unknown
- notes: string (optional)

Optional fields (v0.1):
- user_tag: string (anonymous label, optional)
- toilet_model: string
- sensor_config:
  - num_sensors: integer
  - placement: string

### 3.2 raw.csv (required)
Raw time series from acquisition.

Columns (v0.1):
- t_ms: integer (milliseconds since session start)
- raw: integer or float (raw sensor reading)

If multiple sensors later:
- raw_0, raw_1, raw_2, raw_3 ...

Constraints:
- t_ms is monotonic increasing
- no missing column headers
- NaNs allowed but should be flagged later

### 3.3 processed.csv (required)
Processed time series after calibration/filtering and flow estimation.

Columns (v0.1):
- t_ms: integer
- mass_g: float (estimated seat-load mass-equivalent)
- mass_g_filt: float (filtered mass)
- flow_ml_s: float (estimated flow; expected positive during voiding)
- state: string (one of: "empty", "seated", "voiding", "postvoid")
- flags: string (semicolon-separated flags; empty if none)

Notes:
- flow_ml_s is defined as: flow_ml_s ≈ - d(mass_g_filt)/dt  (1 g ≈ 1 mL)
- state is produced by a detection/state-machine step

### 3.4 metrics.json (required)
Summary outputs computed from processed data.

Required fields (v0.1):
- total_volume_ml: float
- q_max_ml_s: float
- q_avg_ml_s: float
- void_duration_s: float
- time_to_qmax_s: float
- start_t_ms: integer
- stop_t_ms: integer

Optional fields:
- confidence: float (0–1)
- warnings: list of strings (e.g., "posture_shift_detected")

## 4. Versioning Rules
- format_version increments when schema changes
- New fields may be added without breaking old readers
- Columns/fields must not be renamed without bumping format_version

## 5. Rationale (Why This Format)
- CSV is universally readable and pandas-friendly
- Separate raw vs processed preserves the ability to improve algorithms later
- JSON keeps metadata/metrics structured and explicit

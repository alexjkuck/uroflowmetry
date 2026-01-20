"""
Robust void detection for high-noise load-cell data.

This module implements a robust void detection algorithm designed for noisy
10 Hz load-cell data with spikes, oscillations, and posture shifts.

Key approach:
- Resample to uniform grid
- Despike using Hampel filter
- Smooth with Savitzky-Golay
- Estimate robust slopes (Theil-Sen)
- Detect artifacts using rolling MAD
- FSM-based void detection with persistence requirements
"""

import numpy as np
from scipy import signal
from scipy import stats
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class DetectionParams:
    """Parameters for robust void detection."""
    fs: float = 10.0
    baseline_seconds: float = 8.0
    
    # Despike
    hampel_window: int = 5
    hampel_n_sigmas: float = 3.0
    
    # Smoothing
    savgol_window: int = 11
    savgol_poly: int = 2
    
    # Slope estimation
    slope_window: int = 21
    slope_method: str = "theil_sen"  # "theil_sen" or "ols"
    
    # Artifact detection
    artifact_mad_window: int = 10
    artifact_mad_percentile: float = 99.0
    artifact_mad_multiplier: float = 1.5
    artifact_max_slope_g_s: float = 200.0
    
    # FSM thresholds
    enter_window_s: float = 3.0
    exit_window_s: float = 3.0
    duty_cycle_req: float = 0.70
    D_enter_g: float = 40.0
    
    # Guards
    min_void_duration_s: float = 6.0
    min_total_drop_g: float = 80.0
    merge_intervals_gap_s: float = 2.0


def preprocess_and_resample(t_ms: np.ndarray, mass_g: np.ndarray, fs: float = 10.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Resample irregular time series to uniform grid.
    
    Args:
        t_ms: Timestamps in milliseconds (may be irregular)
        mass_g: Mass values in grams
        fs: Target sampling rate in Hz
    
    Returns:
        t_s_uniform: Uniform time grid in seconds
        mass_uniform: Resampled mass values
    """
    t_ms = np.asarray(t_ms)
    mass_g = np.asarray(mass_g)
    
    if len(t_ms) != len(mass_g):
        raise ValueError("t_ms and mass_g must have same length")
    if len(t_ms) < 2:
        raise ValueError("Need at least 2 samples")
    
    # Convert to seconds
    t_s = t_ms / 1000.0
    
    # Remove duplicates by averaging
    unique_t, unique_indices = np.unique(t_s, return_index=True)
    if len(unique_t) < len(t_s):
        # Average duplicate timestamps
        t_s_unique = []
        mass_unique = []
        for t_val in unique_t:
            mask = t_s == t_val
            t_s_unique.append(t_val)
            mass_unique.append(np.mean(mass_g[mask]))
        t_s = np.array(t_s_unique)
        mass_g = np.array(mass_unique)
    else:
        # Sort if needed
        sort_idx = np.argsort(t_s)
        t_s = t_s[sort_idx]
        mass_g = mass_g[sort_idx]
    
    # Create uniform grid
    dt_s = 1.0 / fs
    t_start = t_s[0]
    t_end = t_s[-1]
    t_s_uniform = np.arange(t_start, t_end + dt_s, dt_s)
    
    # Linear interpolation
    mass_uniform = np.interp(t_s_uniform, t_s, mass_g)
    
    return t_s_uniform, mass_uniform


def hampel_filter(x: np.ndarray, window: int = 5, n_sigmas: float = 3.0) -> np.ndarray:
    """
    Hampel filter for outlier detection and removal.
    
    For each point, compute median and MAD of surrounding window.
    Replace outliers (beyond n_sigmas * MAD) with median.
    
    Args:
        x: Input signal
        window: Window size (should be odd)
        n_sigmas: Number of MADs for threshold
    
    Returns:
        x_despiked: Signal with outliers replaced
    """
    x = np.asarray(x)
    n = len(x)
    
    if window <= 1:
        return x.copy()
    
    # Ensure odd window
    if window % 2 == 0:
        window += 1
    
    half = window // 2
    x_despiked = x.copy()
    
    for i in range(n):
        # Window bounds
        i_start = max(0, i - half)
        i_end = min(n, i + half + 1)
        window_data = x[i_start:i_end]
        
        # Compute median and MAD
        median_val = np.median(window_data)
        mad = np.median(np.abs(window_data - median_val))
        
        # Scale MAD to approximate standard deviation
        mad_scaled = 1.4826 * mad if mad > 0 else 1.0
        
        # Replace outlier
        if abs(x[i] - median_val) > n_sigmas * mad_scaled:
            x_despiked[i] = median_val
    
    return x_despiked


def savgol_smooth(x: np.ndarray, window: int = 11, poly: int = 2) -> np.ndarray:
    """
    Apply Savitzky-Golay smoothing filter.
    
    Args:
        x: Input signal
        window: Window size (must be odd and > poly)
        poly: Polynomial order
    
    Returns:
        x_smooth: Smoothed signal
    """
    x = np.asarray(x)
    
    if len(x) < window:
        return x.copy()
    
    # Ensure odd window
    if window % 2 == 0:
        window += 1
    
    # Ensure window > poly
    if window <= poly:
        window = poly + 1
        if window % 2 == 0:
            window += 1
    
    return signal.savgol_filter(x, window, poly)


def rolling_mad(x: np.ndarray, window: int = 10) -> np.ndarray:
    """
    Compute rolling Median Absolute Deviation (MAD).
    
    Args:
        x: Input signal
        window: Window size
    
    Returns:
        mad_series: Rolling MAD values
    """
    x = np.asarray(x)
    n = len(x)
    mad_series = np.zeros(n)
    
    half = window // 2
    
    for i in range(n):
        i_start = max(0, i - half)
        i_end = min(n, i + half + 1)
        window_data = x[i_start:i_end]
        
        median_val = np.median(window_data)
        mad = np.median(np.abs(window_data - median_val))
        mad_series[i] = mad
    
    return mad_series


def compute_slope_series(
    t_s: np.ndarray,
    mass_smooth: np.ndarray,
    method: str = "theil_sen",
    window: int = 21,
) -> np.ndarray:
    """
    Compute local slope series using robust estimator.
    
    Args:
        t_s: Time in seconds (uniform grid)
        mass_smooth: Smoothed mass signal
        method: "theil_sen" or "ols"
        window: Window size for slope estimation
    
    Returns:
        slope_g_s: Slope values in g/s
    """
    t_s = np.asarray(t_s)
    mass_smooth = np.asarray(mass_smooth)
    
    if len(t_s) != len(mass_smooth):
        raise ValueError("t_s and mass_smooth must have same length")
    
    n = len(t_s)
    slope_g_s = np.zeros(n)
    
    # Ensure odd window
    if window % 2 == 0:
        window += 1
    
    half = window // 2
    
    for i in range(n):
        i_start = max(0, i - half)
        i_end = min(n, i + half + 1)
        
        t_window = t_s[i_start:i_end]
        m_window = mass_smooth[i_start:i_end]
        
        if len(t_window) < 2:
            slope_g_s[i] = 0.0
            continue
        
        if method == "theil_sen":
            # Theil-Sen estimator: median of pairwise slopes
            slopes = []
            for j in range(len(t_window)):
                for k in range(j + 1, len(t_window)):
                    dt = t_window[k] - t_window[j]
                    if dt > 0:
                        slope = (m_window[k] - m_window[j]) / dt
                        slopes.append(slope)
            
            if slopes:
                slope_g_s[i] = np.median(slopes)
            else:
                # Fallback to OLS
                slope_g_s[i] = np.polyfit(t_window, m_window, 1)[0]
        
        elif method == "ols":
            # Ordinary least squares
            slope_g_s[i] = np.polyfit(t_window, m_window, 1)[0]
        
        else:
            raise ValueError(f"Unknown method: {method}")
    
    return slope_g_s


def detect_artifacts(
    mass_despiked: np.ndarray,
    slope_g_s: np.ndarray,
    t_s: np.ndarray,
    params: DetectionParams,
) -> np.ndarray:
    """
    Detect motion artifacts using rolling MAD and slope thresholds.
    
    Args:
        mass_despiked: Despiked mass signal
        slope_g_s: Slope series
        t_s: Time in seconds
        params: Detection parameters
    
    Returns:
        artifact_mask: Boolean array, True where artifact detected
    """
    # Compute rolling MAD
    rolling_mad_vals = rolling_mad(mass_despiked, params.artifact_mad_window)
    
    # Baseline MAD from first baseline_seconds
    baseline_end_idx = int(np.searchsorted(t_s, params.baseline_seconds))
    baseline_end_idx = min(baseline_end_idx, len(rolling_mad_vals))
    
    if baseline_end_idx > 0:
        baseline_mad = rolling_mad_vals[:baseline_end_idx]
        baseline_mad_threshold = np.percentile(baseline_mad, params.artifact_mad_percentile)
        artifact_threshold = baseline_mad_threshold * params.artifact_mad_multiplier
    else:
        # Fallback: use median + 3 MAD
        median_mad = np.median(rolling_mad_vals)
        mad_of_mad = np.median(np.abs(rolling_mad_vals - median_mad))
        artifact_threshold = median_mad + 3.0 * 1.4826 * mad_of_mad
    
    # Artifact mask from MAD
    artifact_mask_mad = rolling_mad_vals > artifact_threshold
    
    # Artifact mask from excessive slope
    artifact_mask_slope = np.abs(slope_g_s) > params.artifact_max_slope_g_s
    
    # Combine
    artifact_mask = artifact_mask_mad | artifact_mask_slope
    
    return artifact_mask


def detect_void_fsm(
    t_s: np.ndarray,
    mass_smooth: np.ndarray,
    slope_g_s: np.ndarray,
    artifact_mask: np.ndarray,
    params: DetectionParams,
) -> List[Tuple[int, int]]:
    """
    Detect void intervals using finite state machine.
    
    Args:
        t_s: Time in seconds
        mass_smooth: Smoothed mass signal
        slope_g_s: Slope series
        artifact_mask: Artifact mask
        params: Detection parameters
    
    Returns:
        intervals: List of (start_idx, stop_idx) tuples
    """
    n = len(t_s)
    if n < params.slope_window:
        return []
    
    # Compute adaptive thresholds from baseline
    baseline_end_idx = int(np.searchsorted(t_s, params.baseline_seconds))
    baseline_end_idx = min(baseline_end_idx, n)
    
    if baseline_end_idx < 10:
        return []
    
    baseline_slope = slope_g_s[:baseline_end_idx]
    baseline_median = np.median(baseline_slope)
    baseline_mad = np.median(np.abs(baseline_slope - baseline_median))
    baseline_mad_scaled = 1.4826 * baseline_mad if baseline_mad > 0 else 1.0
    
    thr_enter = baseline_median - 3.5 * baseline_mad_scaled
    thr_exit = baseline_median - 1.0 * baseline_mad_scaled
    
    # Convert window sizes to samples
    enter_window_samples = int(params.enter_window_s * params.fs)
    exit_window_samples = int(params.exit_window_s * params.fs)
    cumulative_drop_window_samples = int(5.0 * params.fs)  # 5 seconds
    
    # FSM
    state = "IDLE"
    intervals = []
    current_start = None
    
    for i in range(n):
        if artifact_mask[i]:
            # Skip artifacts
            continue
        
        if state == "IDLE":
            # Check enter conditions
            # 1. Duty cycle in enter window
            window_start = max(0, i - enter_window_samples + 1)
            window_slopes = slope_g_s[window_start:i+1]
            window_artifacts = artifact_mask[window_start:i+1]
            valid_slopes = window_slopes[~window_artifacts]
            
            if len(valid_slopes) > 0:
                duty_cycle = np.sum(valid_slopes < thr_enter) / len(valid_slopes)
            else:
                duty_cycle = 0.0
            
            # 2. Cumulative drop over last 5 seconds
            drop_window_start = max(0, i - cumulative_drop_window_samples + 1)
            if drop_window_start < i:
                mass_start_window = mass_smooth[drop_window_start]
                mass_end_window = mass_smooth[i]
                cumulative_drop = mass_start_window - mass_end_window
            else:
                cumulative_drop = 0.0
            
            # Enter VOIDING if conditions met
            if (duty_cycle >= params.duty_cycle_req and 
                cumulative_drop >= params.D_enter_g):
                state = "VOIDING"
                current_start = i
        
        elif state == "VOIDING":
            # Check exit conditions
            window_start = max(current_start, i - exit_window_samples + 1)
            window_slopes = slope_g_s[window_start:i+1]
            window_artifacts = artifact_mask[window_start:i+1]
            valid_slopes = window_slopes[~window_artifacts]
            
            if len(valid_slopes) > 0:
                duty_cycle = np.sum(valid_slopes > thr_exit) / len(valid_slopes)
            else:
                duty_cycle = 0.0
            
            # Exit if conditions met and min duration satisfied
            duration = t_s[i] - t_s[current_start]
            if (duty_cycle >= params.duty_cycle_req and 
                duration >= params.min_void_duration_s):
                # Check minimum drop
                mass_drop = mass_smooth[current_start] - mass_smooth[i]
                if mass_drop >= params.min_total_drop_g:
                    intervals.append((current_start, i))
                state = "IDLE"
                current_start = None
    
    # Handle case where void extends to end
    if state == "VOIDING" and current_start is not None:
        duration = t_s[-1] - t_s[current_start]
        if duration >= params.min_void_duration_s:
            mass_drop = mass_smooth[current_start] - mass_smooth[-1]
            if mass_drop >= params.min_total_drop_g:
                intervals.append((current_start, n - 1))
    
    # Merge close intervals
    if len(intervals) > 1:
        merged = []
        current = intervals[0]
        for next_interval in intervals[1:]:
            gap = t_s[next_interval[0]] - t_s[current[1]]
            if gap <= params.merge_intervals_gap_s:
                # Merge
                current = (current[0], next_interval[1])
            else:
                merged.append(current)
                current = next_interval
        merged.append(current)
        intervals = merged
    
    return intervals


def compute_metrics(
    t_s: np.ndarray,
    mass_smooth: np.ndarray,
    slope_g_s: np.ndarray,
    interval: Tuple[int, int],
) -> Dict[str, float]:
    """
    Compute metrics for a void interval.
    
    Args:
        t_s: Time in seconds
        mass_smooth: Smoothed mass signal
        slope_g_s: Slope series
        interval: (start_idx, stop_idx)
    
    Returns:
        Dictionary with metrics
    """
    i0, i1 = interval
    
    if i0 >= i1 or i0 < 0 or i1 >= len(t_s):
        return {
            "void_duration_s": 0.0,
            "total_volume_ml": 0.0,
            "q_avg_ml_s": 0.0,
            "q_max_ml_s": 0.0,
            "time_to_qmax_s": 0.0,
            "start_t_s": 0.0,
            "stop_t_s": 0.0,
        }
    
    # Duration
    duration = t_s[i1] - t_s[i0]
    
    # Volume: mass drop
    mass_start = mass_smooth[i0]
    mass_end = mass_smooth[i1]
    mass_drop = mass_start - mass_end
    total_volume_ml = max(0.0, mass_drop)  # 1 g ≈ 1 mL
    
    # Average flow
    q_avg_ml_s = total_volume_ml / duration if duration > 0 else 0.0
    
    # Instantaneous flow (negative slope)
    q_inst = np.maximum(0.0, -slope_g_s[i0:i1+1])
    
    # Max flow (95th percentile)
    if len(q_inst) > 0:
        q_max_ml_s = np.percentile(q_inst, 95)
        
        # Time to max flow
        q_max_idx = np.argmax(q_inst)
        time_to_qmax_s = t_s[i0 + q_max_idx] - t_s[i0]
    else:
        q_max_ml_s = 0.0
        time_to_qmax_s = 0.0
    
    return {
        "void_duration_s": float(duration),
        "total_volume_ml": float(total_volume_ml),
        "q_avg_ml_s": float(q_avg_ml_s),
        "q_max_ml_s": float(q_max_ml_s),
        "time_to_qmax_s": float(time_to_qmax_s),
        "start_t_s": float(t_s[i0]),
        "stop_t_s": float(t_s[i1]),
    }


def run_detect(
    t_ms: np.ndarray,
    mass_g: np.ndarray,
    flow_truth: Optional[np.ndarray] = None,
    params: Optional[DetectionParams] = None,
) -> Dict[str, Any]:
    """
    Main detection function: run full pipeline.
    
    Args:
        t_ms: Timestamps in milliseconds
        mass_g: Mass values in grams
        flow_truth: Optional ground truth flow (for evaluation only)
        params: Detection parameters (uses defaults if None)
    
    Returns:
        Dictionary with:
            - intervals: List of (start_idx, stop_idx) tuples
            - metrics: List of metric dicts per interval
            - debug: Dictionary with intermediate signals
    """
    if params is None:
        params = DetectionParams()
    
    # Resample to uniform grid
    t_s, mass_resampled = preprocess_and_resample(t_ms, mass_g, params.fs)
    
    # Despike
    mass_despiked = hampel_filter(mass_resampled, params.hampel_window, params.hampel_n_sigmas)
    
    # Smooth
    mass_smooth = savgol_smooth(mass_despiked, params.savgol_window, params.savgol_poly)
    
    # Compute slopes
    slope_g_s = compute_slope_series(t_s, mass_smooth, params.slope_method, params.slope_window)
    
    # Detect artifacts
    artifact_mask = detect_artifacts(mass_despiked, slope_g_s, t_s, params)
    
    # Compute thresholds for debug
    baseline_end_idx = int(np.searchsorted(t_s, params.baseline_seconds))
    baseline_end_idx = min(baseline_end_idx, len(slope_g_s))
    if baseline_end_idx > 0:
        baseline_slope = slope_g_s[:baseline_end_idx]
        baseline_median = np.median(baseline_slope)
        baseline_mad = np.median(np.abs(baseline_slope - baseline_median))
        baseline_mad_scaled = 1.4826 * baseline_mad if baseline_mad > 0 else 1.0
        thr_enter = baseline_median - 3.5 * baseline_mad_scaled
        thr_exit = baseline_median - 1.0 * baseline_mad_scaled
    else:
        thr_enter = 0.0
        thr_exit = 0.0
    
    # Detect voids
    intervals = detect_void_fsm(t_s, mass_smooth, slope_g_s, artifact_mask, params)
    
    # Compute metrics per interval
    metrics_list = [compute_metrics(t_s, mass_smooth, slope_g_s, interval) for interval in intervals]
    
    # Resample flow_truth if provided
    flow_truth_resampled = None
    if flow_truth is not None:
        t_s_original = t_ms / 1000.0
        flow_truth_resampled = np.interp(t_s, t_s_original, flow_truth)
    
    return {
        "intervals": intervals,
        "metrics": metrics_list,
        "debug": {
            "t_s": t_s,
            "mass_raw_resampled": mass_resampled,
            "mass_despiked": mass_despiked,
            "mass_smooth": mass_smooth,
            "slope_g_s": slope_g_s,
            "artifact_mask": artifact_mask,
            "thr_enter": thr_enter,
            "thr_exit": thr_exit,
            "flow_truth_resampled": flow_truth_resampled,
        },
    }


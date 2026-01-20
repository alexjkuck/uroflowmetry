#!/usr/bin/env python3
"""
Apply the same preprocessing/filtering used by the robust detector to a raw.csv file
and dump the intermediate signals for validation.

This runs:
  - Resampling to 10 Hz
  - Hampel despiking
  - Savitzky–Golay smoothing
  - Slope and artifact computation (for convenience)

Usage:
    python apply_filters.py <raw_csv_file> [output_file]

Examples:
    python apply_filters.py sessions/sim_nominal/raw.csv
    python apply_filters.py sessions/sim_nominal/raw.csv robust_filtered.csv
"""

import sys
import pandas as pd
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uroflow.detect_robust import (  # type: ignore[import]
    DetectionParams,
    preprocess_and_resample,
    hampel_filter,
    savgol_smooth,
    compute_slope_series,
    detect_artifacts,
)


def apply_filter_to_csv(
    raw_csv_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    Load raw.csv, apply the robust preprocessing/filtering pipeline, and save signals.

    This mirrors the filtering path used in `detect_robust.run_detect`:
      - Resample to uniform 10 Hz grid
      - Hampel despike
      - Savitzky–Golay smoothing
      - Robust slope estimation
      - Artifact mask

    Args:
        raw_csv_path: Path to raw.csv file (must contain 't_ms' and 'raw' columns)
        output_path: Output file path (defaults to 'robust_filtered.csv' in same directory)

    Returns:
        Path to the output file.
    """
    raw_csv_path = Path(raw_csv_path)

    if not raw_csv_path.exists():
        raise FileNotFoundError(f"File not found: {raw_csv_path}")

    print(f"Loading: {raw_csv_path}")
    df = pd.read_csv(raw_csv_path)

    if "t_ms" not in df.columns or "raw" not in df.columns:
        raise ValueError("CSV must have 't_ms' and 'raw' columns for robust filtering")

    t_ms = df["t_ms"].to_numpy()
    mass_g = df["raw"].to_numpy()

    # Use the same default parameters as the robust detector
    params = DetectionParams()
    print(f"Using robust detector parameters: fs={params.fs} Hz")

    # 1) Resample to uniform grid
    t_s_uniform, mass_resampled = preprocess_and_resample(t_ms, mass_g, fs=params.fs)

    # 2) Despike (Hampel)
    mass_despiked = hampel_filter(
        mass_resampled,
        window=params.hampel_window,
        n_sigmas=params.hampel_n_sigmas,
    )

    # 3) Smooth (Savitzky–Golay)
    mass_smooth = savgol_smooth(
        mass_despiked,
        window=params.savgol_window,
        poly=params.savgol_poly,
    )

    # 4) Robust slope
    slope_g_s = compute_slope_series(
        t_s_uniform,
        mass_smooth,
        method=params.slope_method,
        window=params.slope_window,
    )

    # 5) Artifact mask
    artifact_mask = detect_artifacts(
        mass_despiked,
        slope_g_s,
        t_s_uniform,
        params,
    )

    # Determine output file path
    if output_path is None:
        output_path = raw_csv_path.parent / "robust_filtered.csv"
    else:
        output_path = Path(output_path)

    # Build output DataFrame with validation-friendly columns
    out_df = pd.DataFrame(
        {
            "t_s": t_s_uniform,
            "mass_raw_resampled": mass_resampled,
            "mass_despiked": mass_despiked,
            "mass_smooth": mass_smooth,
            "slope_g_s": slope_g_s,
            "artifact_mask": artifact_mask.astype(int),
        }
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False)
    print(f"Saved robust-filtered data to: {output_path}")

    return output_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    raw_csv = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        apply_filter_to_csv(raw_csv, output_file)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


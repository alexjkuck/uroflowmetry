#!/usr/bin/env python3
"""
convert_collab_csv.py

Convert collaborator-exported CSV format:

  Time__sec, Weight__g, Flow__mLPmin, FlowsensorError_Air, FlowsensorError_Overflow

into the format your existing pipeline expects:

  raw.csv with columns: t_ms, raw

Optionally also writes truth.csv with columns:
  t_ms, truth_flow_ml_s, air_error, overflow_error

Usage:
  PYTHONPATH=Uroflow_Synth/src python Uroflow_Synth/scripts/convert_collab_csv.py \
      --in sessions/real_001/collab.csv \
      --out-dir sessions/real_001 \
      --write-truth

Or, if you want it to overwrite/create raw.csv in that session folder:
  PYTHONPATH=Uroflow_Synth/src python Uroflow_Synth/scripts/convert_collab_csv.py \
      --in sessions/real_001/raw_from_gui.csv \
      --out-dir sessions/real_001 \
      --raw-name raw.csv \
      --write-truth
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


REQUIRED_COLS = [
    "Time__sec",
    "Weight__g",
    "Flow__mLPmin",
    "FlowsensorError_Air",
    "FlowsensorError_Overflow",
]


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            "Input CSV missing required columns.\n"
            f"Missing: {missing}\n"
            f"Found: {list(df.columns)}"
        )


def _seconds_to_ms_int(t_sec: pd.Series) -> pd.Series:
    # Convert seconds -> milliseconds as int, rounding to nearest millisecond.
    t_ms = (t_sec.astype(float) * 1000.0).round().astype("int64")
    return t_ms


def _enforce_strictly_increasing(t_ms: pd.Series) -> None:
    dt = t_ms.diff().dropna()
    if (dt <= 0).any():
        # Show a small diagnostic window
        bad_idx = dt[dt <= 0].index[:10].tolist()
        raise ValueError(
            "t_ms is not strictly increasing after conversion. "
            "This breaks the pipeline's timebase assumptions.\n"
            f"First problematic indices (in the dataframe): {bad_idx}"
        )


def convert(
    in_csv: Path,
    out_dir: Path,
    raw_name: str = "raw.csv",
    write_truth: bool = False,
    truth_name: str = "truth.csv",
) -> tuple[Path, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_csv)
    _validate_columns(df)

    # Build raw.csv for your pipeline
    t_ms = _seconds_to_ms_int(df["Time__sec"])
    _enforce_strictly_increasing(t_ms)

    raw_out = out_dir / raw_name
    raw_df = pd.DataFrame(
        {
            "t_ms": t_ms,
            "raw": df["Weight__g"].astype(float),
        }
    )
    raw_df.to_csv(raw_out, index=False)

    truth_out: Path | None = None
    if write_truth:
        # Flow__mLPmin = mL per minute; convert to mL per second
        truth_flow_ml_s = df["Flow__mLPmin"].astype(float) / 60.0

        truth_out = out_dir / truth_name
        truth_df = pd.DataFrame(
            {
                "t_ms": t_ms,
                "truth_flow_ml_s": truth_flow_ml_s,
                "air_error": df["FlowsensorError_Air"].astype(float),
                "overflow_error": df["FlowsensorError_Overflow"].astype(float),
            }
        )
        truth_df.to_csv(truth_out, index=False)

    return raw_out, truth_out


def main() -> None:
    p = argparse.ArgumentParser(description="Convert collaborator CSV to pipeline format.")
    p.add_argument("--in", dest="in_csv", required=True, help="Path to collaborator CSV.")
    p.add_argument("--out-dir", required=True, help="Output session directory.")
    p.add_argument("--raw-name", default="raw.csv", help="Filename for pipeline raw CSV.")
    p.add_argument(
        "--write-truth",
        action="store_true",
        help="Also write truth.csv derived from Flow__mLPmin and error flags.",
    )
    p.add_argument("--truth-name", default="truth.csv", help="Filename for truth CSV.")
    args = p.parse_args()

    raw_out, truth_out = convert(
        in_csv=Path(args.in_csv),
        out_dir=Path(args.out_dir),
        raw_name=args.raw_name,
        write_truth=args.write_truth,
        truth_name=args.truth_name,
    )

    print(f"Wrote pipeline input: {raw_out}")
    if truth_out is not None:
        print(f"Wrote truth file:     {truth_out}")


if __name__ == "__main__":
    main()

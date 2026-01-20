#!/usr/bin/env python3
"""
Slice and filter an existing CSV file to create a new CSV.

Usage:
    python make_csv_from_paste.py <input_csv> <output_csv> [start_time] [end_time]

Examples:
    python make_csv_from_paste.py sessions/real_003/collab.csv sessions/real_003/collab_slice.csv 10 35
    python make_csv_from_paste.py sessions/real_003/collab.csv sessions/real_003/raw.csv
"""

import sys
import pandas as pd
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    input_csv = Path(sys.argv[1])
    output_csv = Path(sys.argv[2])
    
    # Optional time range arguments
    start_time = float(sys.argv[3]) if len(sys.argv) > 3 else None
    end_time = float(sys.argv[4]) if len(sys.argv) > 4 else None
    
    # Check input file exists
    if not input_csv.exists():
        print(f"ERROR: Input file not found: {input_csv}", file=sys.stderr)
        sys.exit(1)
    
    # Resolve paths
    if not input_csv.is_absolute():
        input_csv = Path.cwd() / input_csv
    if not output_csv.is_absolute():
        output_csv = Path.cwd() / output_csv
    
    input_csv = input_csv.resolve()
    output_csv = output_csv.resolve()
    
    print(f"Input CSV:  {input_csv}", file=sys.stderr)
    print(f"Output CSV: {output_csv}", file=sys.stderr)
    
    try:
        # Load original CSV
        print(f"Loading: {input_csv}", file=sys.stderr)
        df = pd.read_csv(input_csv)
        
        print(f"Loaded {len(df)} rows, {len(df.columns)} columns", file=sys.stderr)  # type: ignore
        print(f"Columns: {', '.join(df.columns)}", file=sys.stderr)  # type: ignore
        
        # Slice by time if time range provided
        if start_time is not None or end_time is not None:
            if "Time__sec" not in df.columns:
                print("WARNING: 'Time__sec' column not found. Available columns:", file=sys.stderr)
                print(f"  {', '.join(df.columns)}", file=sys.stderr)
                print("Skipping time filtering.", file=sys.stderr)
            else:
                original_len = len(df)
                if start_time is not None:
                    df = df[df["Time__sec"] >= start_time].copy()
                    print(f"Filtered: Time >= {start_time}", file=sys.stderr)
                if end_time is not None:
                    df = df[df["Time__sec"] <= end_time].copy()
                    print(f"Filtered: Time <= {end_time}", file=sys.stderr)
                print(f"After time filtering: {len(df)} rows (removed {original_len - len(df)})", file=sys.stderr)
        
        # Keep only required columns (if they exist)
        required_cols = ["Time__sec", "Weight__g"]
        available_cols = [col for col in required_cols if col in df.columns]  # type: ignore
        
        if available_cols:
            df = df[available_cols].copy()
            print(f"Kept columns: {', '.join(available_cols)}", file=sys.stderr)
        else:
            print("WARNING: None of the required columns found. Keeping all columns.", file=sys.stderr)
        
        # Create output directory if needed
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        
        # Write trimmed CSV
        print(f"Writing to: {output_csv}", file=sys.stderr)
        df.to_csv(output_csv, index=False)  # type: ignore
        
        print(f"\n✓ SUCCESS: Created CSV with {len(df)} row(s) at: {output_csv}", file=sys.stderr)
        print(f"  File size: {output_csv.stat().st_size} bytes", file=sys.stderr)
        
    except FileNotFoundError:
        print(f"ERROR: File not found: {input_csv}", file=sys.stderr)
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"ERROR: Input CSV is empty: {input_csv}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

from pathlib import Path
import numpy as np
import pandas as pd

def load_raw_session(session_dir: str | Path):
    session_dir = Path(session_dir)
    raw_path = session_dir / "raw.csv"

    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw.csv at: {raw_path}")

    df = pd.read_csv(raw_path)

    # validate columns
    required_cols = ["t_ms", "raw"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # extract arrays
    t_ms = df["t_ms"].to_numpy()
    raw = df["raw"].to_numpy()
    
    # validate monotonic t_ms
    if not np.all(np.diff(t_ms) > 0):
        raise ValueError("t_ms must be monotonically increasing")
    
    return t_ms, raw

def load_timebase(t_ms: np.ndarray):
    t_s = t_ms / 1000.0
    dt_s = np.diff(t_s)
    fs_hz = 1.0 / np.median(dt_s)
    return t_s, dt_s, fs_hz
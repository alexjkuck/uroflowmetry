# scripts/simulate_session.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


# -----------------------------
# Scenario configs (the "big 6")
# -----------------------------
SCENARIOS = {
    # Nominal adult void: ~20s, ~380 mL, moderate noise
    "sim_nominal": dict(
        fs=50,
        empty_s=5,
        total_s=55,
        seated_load_g=75000,
        void_start_s=10,   # seconds from t=0
        void_s=20,
        volume_ml=380,
        noise_sigma_g=8,
    ),
    # Small void: lower volume and shorter duration
    "sim_small_void": dict(
        fs=50,
        empty_s=5,
        total_s=45,
        seated_load_g=75000,
        void_start_s=10,
        void_s=10,
        volume_ml=160,
        noise_sigma_g=8,
    ),
    # No void: seated, but no ramp
    "sim_no_void": dict(
        fs=50,
        empty_s=5,
        total_s=45,
        seated_load_g=75000,
        void_start_s=10,
        void_s=0,
        volume_ml=0,
        noise_sigma_g=8,
    ),
    # Long void: longer duration and higher volume
    "sim_long_void": dict(
        fs=50,
        empty_s=5,
        total_s=75,
        seated_load_g=75000,
        void_start_s=10,
        void_s=45,
        volume_ml=650,
        noise_sigma_g=8,
    ),
    # High noise: same as nominal but noisier
    "sim_high_noise": dict(
        fs=50,
        empty_s=5,
        total_s=55,
        seated_load_g=75000,
        void_start_s=10,
        void_s=20,
        volume_ml=380,
        noise_sigma_g=30,
    ),
    # Slow void: similar volume, longer duration (lower flow)
    "sim_slow_void": dict(
        fs=50,
        empty_s=5,
        total_s=75,
        seated_load_g=75000,
        void_start_s=10,
        void_s=40,
        volume_ml=380,
        noise_sigma_g=8,
    ),
}


def generate_session(name: str, cfg: dict, out_root: Path, seed: int | None = None) -> Path:
    rng = np.random.default_rng(seed)

    fs = int(cfg["fs"])
    empty_s = float(cfg["empty_s"])
    total_s = float(cfg["total_s"])
    seated_load_g = float(cfg["seated_load_g"])
    void_start_s = float(cfg["void_start_s"])
    void_s = float(cfg["void_s"])
    volume_ml = float(cfg["volume_ml"])
    noise_sigma_g = float(cfg["noise_sigma_g"])

    # time
    t_s = np.arange(0.0, total_s, 1.0 / fs)
    t_ms = (t_s * 1000.0).astype(np.int64)

    # signal
    raw = np.zeros_like(t_s, dtype=float)

    # seated step at empty_s
    seat_idx = int(round(empty_s * fs))
    seat_idx = min(max(seat_idx, 0), len(raw))
    raw[seat_idx:] += seated_load_g

    # voiding ramp (downward mass change)
    if void_s > 0 and volume_ml > 0:
        i0 = int(round(void_start_s * fs))
        i1 = int(round((void_start_s + void_s) * fs))
        i0 = min(max(i0, 0), len(raw))
        i1 = min(max(i1, 0), len(raw))

        if i1 > i0 + 2:
            ramp = np.linspace(0.0, volume_ml, i1 - i0, endpoint=False)
            raw[i0:i1] -= ramp
            raw[i1:] -= volume_ml  # remains decreased after void

    # noise
    raw += rng.normal(0.0, noise_sigma_g, size=len(raw))

    # write outputs
    session_dir = out_root / name
    session_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({"t_ms": t_ms, "raw": raw})
    raw_path = session_dir / "raw.csv"
    df.to_csv(raw_path, index=False)

    truth = {
        "scenario": name,
        "fs_hz": float(fs),
        "true_void_start_s": float(void_start_s) if (void_s > 0 and volume_ml > 0) else None,
        "true_void_duration_s": float(void_s),
        "true_volume_ml": float(volume_ml),
        "empty_s": float(empty_s),
        "total_s": float(total_s),
        "seated_load_g": float(seated_load_g),
        "noise_sigma_g": float(noise_sigma_g),
    }
    truth_path = session_dir / "truth.json"
    truth_path.write_text(json.dumps(truth, indent=2))

    print(f"[{name}] wrote {raw_path} and {truth_path}")
    return session_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "scenario",
        nargs="?",
        default=None,
        help=f"One of: {', '.join(SCENARIOS.keys())}",
    )
    ap.add_argument("--all", action="store_true", help="Generate all scenarios")
    ap.add_argument("--out_root", default="sessions", help="Output root directory")
    ap.add_argument("--seed", type=int, default=None, help="Random seed (reproducible noise)")
    args = ap.parse_args()

    out_root = Path(args.out_root)

    if args.all:
        for name, cfg in SCENARIOS.items():
            generate_session(name, cfg, out_root, seed=args.seed)
        return

    if args.scenario is None:
        raise SystemExit(f"Provide a scenario name or use --all. Options: {', '.join(SCENARIOS.keys())}")

    if args.scenario not in SCENARIOS:
        raise SystemExit(f"Unknown scenario '{args.scenario}'. Options: {', '.join(SCENARIOS.keys())}")

    generate_session(args.scenario, SCENARIOS[args.scenario], out_root, seed=args.seed)


if __name__ == "__main__":
    main()

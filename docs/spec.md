# Uroflowmetry Project – System Specification

## 1. Purpose
This project measures urine flow using a weight-based method and computes
standard uroflowmetry metrics (e.g. flow rate vs time, Qmax, total volume).

This is an engineering prototype, not a certified medical device.

## 2. User Flow
1. User sits on toilet as normal
2. System detects presence and establishes baseline
3. During voiding, system measures mass change over time
4. System isolates urine mass from body-weight noise
5. Metrics are computed automatically
6. Results are stored and optionally displayed

## 3. Outputs
The system must compute:
- Total voided volume (mL)
- Flow rate vs time (mL/s)
- Maximum flow rate (Qmax)
- Average flow rate (Qavg)
- Total voiding time (s)

## 4. Inputs
- Load measurements over time from load cells mounted under the toilet seat
- Timestamps for each measurement

## 5. Assumptions
- Urine density ≈ 1 g/mL
- User remains seated during voiding
- Seat load changes due to posture shifts are slow relative to urine flow
- Structural mounting transmits load reliably to sensors

## 6. Performance Targets (Initial)
- Sampling rate: TBD (target 10–50 Hz)
- Flow resolution: TBD
- Latency: non-critical (offline acceptable for v0.1)

## 7. Non-Goals (For Now)
- Medical certification
- Cloud backend
- Advanced ML analysis
- Multi-user accounts
- User identification or authentication

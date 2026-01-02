# Signal Model – Seat-Integrated Uroflowmetry

## 1. Overview
This document describes the physical signals measured by the system,
their sources, and how they relate to urine flow.

Sensors mounted under the toilet seat measure total load over time.
The desired signal (urine mass change) must be extracted from other load components.

## 2. Measured Quantity
The sensors measure:

- Total vertical load transmitted through the toilet seat
- Units: Arbitrary sensor units --> converted to force or mass
- Sampled at a fixed rate

This measured load is a superposition of multiple physical effects.

L(t) = L_static + L_posture(t) + L_void(t) + L_noise(t)

## 3. Load Components
The total measured load consists of:

### 3.1 Static Components
- User body weight
- Toilet seat and mounting structure weight

### 3.2 Slowly Varying Components
- Posture shifts
- Muscle tension changes
- Minor seat flex or redistribution of load

### 3.3 Desired Signal
- During voiding, mass leaves the user
- If the user remains seated and the support distribution is stable, L(t) should exhibit a
  gradual decrease over the void

### 3.4 Noise Sources
- Sensor noise
- Mechanical vibration
- Environmental disturbances

## 4. Signal Characteristics (Qualitative)
- Urine mass change is smooth and continuous
- Flow rate varies over seconds, not milliseconds
- Body motion tends to be lower-frequency and non-monotonic

## 5. Implications for Processing
- Absolute load is not useful; changes over time are key
- Baseline detection is required before voiding
- Differentiation amplifies noise and must be handled carefully
- Filtering must preserve physiologically relevant time scales

## 6. Open Questions
- Typical magnitude of urine mass vs body-weight fluctuations
- Required sampling rate to capture flow dynamics
- Best method for detecting start and end of void
- Mechanical coupling: does seat transmit consistent fraction of body weight across users?

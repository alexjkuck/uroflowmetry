import numpy as np
import pandas as pd

fs = 50
empty_s = 5
seated_s = 5

void_s = 3
void_start_s = empty_s + 1
volume_ml = 300  # total mass lost during void (g ≈ mL)


# time
t = np.arange(0, empty_s + seated_s, 1/fs)
t_ms = (t * 1000).astype(int)

# signal
raw = np.zeros_like(t)

# seated step
seated_load = 75000  # g-equivalent
raw[int(empty_s * fs):] += seated_load

# voiding: gradual decrease in seat load
i0 = int(void_start_s * fs)
i1 = int((void_start_s + void_s) * fs)

ramp = np.linspace(0, volume_ml, i1 - i0, endpoint=False)
raw[i0:i1] -= ramp
raw[i1:] -= volume_ml  # remain decreased after void


# noise
raw += np.random.normal(0, 5, size=len(raw))

df = pd.DataFrame({"t_ms": t_ms, "raw": raw})
df.to_csv("sessions/test/raw.csv", index=False)

print("Wrote sessions/test/raw.csv")

import numpy as np, pandas as pd
rng = np.random.default_rng(42)
d = pd.read_csv('data.csv')
bad = d[(d.label == 'abnormal') &
        ~(((d.temp > 52) | (d.temp < 43)) |
          ((d.pressure > 1.08) | (d.pressure < 0.97)) |
          (d.vibration > 0.07))]
print('non-breaching abnormal rows:', len(bad))
print(bad[['timestamp', 'temp', 'pressure', 'vibration']].head(10).to_string())
import pandas as pd
from preprocessing import preprocess

d = pd.read_csv('data/sensor_data.csv')
c = preprocess(d)

print('report:', c.report)
print('rows in -> out:', len(d), '->', len(c.raw))
print('NaNs left:', c.raw[['temp','pressure','vibration']].isna().sum().sum())
print('z means (~0):', c.standardized.mean().round(6).to_dict())
print('z stds  (~1):', c.standardized.std(ddof=0).round(6).to_dict())
print('raw still physical? temp mean =', round(c.raw.temp.mean(), 2))
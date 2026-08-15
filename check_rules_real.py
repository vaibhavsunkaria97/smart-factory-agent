import pandas as pd
from preprocessing import preprocess
from detectors import RuleDetector

c = preprocess(pd.read_csv('data/sensor_data.csv'))
r = RuleDetector()
flagged = sum(1 for i in range(len(c.raw)) if r.check(c.raw.iloc[i]))
print('flagged by rules :', flagged, 'of', len(c.raw))
print('labelled abnormal:', (c.raw.label == 'abnormal').sum())
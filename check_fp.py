import pandas as pd
from preprocessing import preprocess
from detectors import RuleDetector

df = pd.read_csv('data/sensor_data.csv')
truth = dict(zip(pd.to_datetime(df['timestamp']).astype(str), df['label']))
c = preprocess(df)
rd = RuleDetector()

for i in range(len(c.raw)):
    row = c.raw.iloc[i]
    b = rd.check(row)
    lab = truth.get(str(pd.to_datetime(row['timestamp'])))
    if b and lab == 'normal':
        print(f"row {i} {row['timestamp']} labelled NORMAL but breaches {b}")
        # was this row imputed?
        orig = df[pd.to_datetime(df.timestamp) == row['timestamp']]
        print('   original values:', orig[['temp','pressure','vibration']].to_dict('records'))
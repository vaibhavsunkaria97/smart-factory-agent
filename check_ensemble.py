import pandas as pd
from preprocessing import preprocess
from detectors import AnomalyEnsemble

c = preprocess(pd.read_csv('data/sensor_data.csv'))
ens = AnomalyEnsemble()
dets = ens.detect(c.raw, c.standardized)

print('detections:', len(dets))
print('scores in [0,1]:', all(0 <= d.score <= 1 for d in dets))
print('severities:', {s: sum(1 for d in dets if d.severity == s)
                      for s in ['LOW','MEDIUM','HIGH','CRITICAL']})
d = max(dets, key=lambda x: x.score)
print(f'\nworst: {d.timestamp} score={d.score:.3f} {d.severity}')
print('  breached:', d.breached)
print('  by rules:', d.rule_flag, '| by ML:', d.iforest_flag)
import pandas as pd
from preprocessing import preprocess
from detectors import AnomalyEnsemble
from llm_backend import Reasoner

c = preprocess(pd.read_csv('data/sensor_data.csv'))
dets = AnomalyEnsemble().detect(c.raw, c.standardized)

r = Reasoner()
print('backend:', r.backend)

for d in sorted(dets, key=lambda x: -x.score)[:3]:
    e = r.explain(d)
    print(f"\n{d.severity}  {d.timestamp}  score={d.score:.2f}")
    print('  breached :', [(s, dirn) for s, dirn, _ in d.breached])
    print('  diagnosis:', e['diagnosis'][:130])
    print('  action   :', e['action'][:130])
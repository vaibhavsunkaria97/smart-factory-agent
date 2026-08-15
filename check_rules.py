import pandas as pd
from detectors import RuleDetector
r = RuleDetector()
print('3 breaches:', r.check(pd.Series({'temp':60,'pressure':1.20,'vibration':0.10})))
print('1 breach:  ', r.check(pd.Series({'temp':60,'pressure':1.02,'vibration':0.03})))
print('0 breaches:', r.check(pd.Series({'temp':47,'pressure':1.02,'vibration':0.03})))
print('low temp:  ', r.check(pd.Series({'temp':40,'pressure':1.02,'vibration':0.03})))
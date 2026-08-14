import pandas as pd
d = pd.read_csv('data/sensor_data.csv')
print('shape:', d.shape)
print('labels:', d.label.value_counts().to_dict())
print('missing cells:', d[['temp','pressure','vibration']].isna().sum().sum())
print('dup timestamps:', d.timestamp.duplicated().sum())
n = d[d.label == 'normal']
a = d[d.label == 'abnormal']
print('\nabnormal rows - how many breach each limit:')
print('  temp  >52 or <43 :', ((a.temp > 52) | (a.temp < 43)).sum())
print('  press >1.08/<0.97:', ((a.pressure > 1.08) | (a.pressure < 0.97)).sum())
print('  vib   >0.07      :', (a.vibration > 0.07).sum())
print('  rows with NO breach:', (~(((a.temp>52)|(a.temp<43)) | ((a.pressure>1.08)|(a.pressure<0.97)) | (a.vibration>0.07))).sum())
print('\nnormal ranges:')
for c in ['temp', 'pressure', 'vibration']:
    print(f'  {c:<10} {n[c].min():.3f} .. {n[c].max():.3f}')
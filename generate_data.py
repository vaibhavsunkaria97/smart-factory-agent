import numpy as np
import pandas as pd
import argparse
from datetime import datetime, timedelta

def generate_data(rows, seed, out):
    np.random.seed(seed)
    data = {
        'timestamp': [],
        'temp': [],
        'pressure': [],
        'vibration': [],
        'label': []
    }

    start_time = datetime(2024, 6, 3, 19, 0, 0)
    for i in range(rows):
        timestamp = start_time + timedelta(minutes=i)
        data['timestamp'].append(timestamp)

        # Generate normal data
        temp = np.random.uniform(45, 50)
        pressure = np.random.uniform(1.00, 1.05)
        vibration = np.random.uniform(0.02, 0.04)
        label = 'normal'

        # Introduce abnormalities
        if np.random.rand() < 0.12:
            label = 'abnormal'
            abnormal_channels = np.random.choice(['temp', 'pressure', 'vibration'], size=np.random.randint(1, 4), replace=False)
            if 'temp' in abnormal_channels:
                temp = np.random.uniform(38.0, 42.5) if np.random.rand() < 0.5 else np.random.uniform(52.5, 58.0)
            if 'pressure' in abnormal_channels:
                pressure = np.random.uniform(0.90, 0.96) if np.random.rand() < 0.5 else np.random.uniform(1.09, 1.18)
            if 'vibration' in abnormal_channels:
                vibration = np.random.uniform(0.075, 0.15)

        data['temp'].append(temp)
        data['pressure'].append(pressure)
        data['vibration'].append(vibration)
        data['label'].append(label)

    # Inject missing values into normal rows only
    n_missing = max(3, int(0.02 * rows * 3))  # 3 sensor columns
    normal_indices = [i for i, label in enumerate(data['label']) if label == 'normal']
    # Create list of all (row, col) pairs for normal rows
    cells = [(i, col) for i in normal_indices for col in ['temp', 'pressure', 'vibration']]
    # If n_missing exceeds available cells, reduce it
    n_missing = min(n_missing, len(cells))
    if n_missing > 0:
        chosen_indices = np.random.choice(len(cells), size=n_missing, replace=False)
        for idx in chosen_indices:
            row_idx, col = cells[idx]
            data[col][row_idx] = np.nan

    # Introduce duplicate timestamps (exactly 2 duplicates)
    duplicate_indices = np.random.choice(rows, size=2, replace=False)
    for index in duplicate_indices:
        data['timestamp'].append(data['timestamp'][index])
        data['temp'].append(data['temp'][index])
        data['pressure'].append(data['pressure'][index])
        data['vibration'].append(data['vibration'][index])
        data['label'].append(data['label'][index])

    df = pd.DataFrame(data)
    df.to_csv(out, index=False)

    print(f"Generated {rows} rows of data with ~12% abnormalities and ~2% missing values.")
    print(f"Data saved to {out}")
    
    # Self-check: assert every abnormal row breaches at least one threshold
    for i in range(len(data['label'])):
        if data['label'][i] == 'abnormal':
            assert (data['temp'][i] < 43 or data['temp'][i] > 52 or 
                    data['pressure'][i] < 0.97 or data['pressure'][i] > 1.08 or 
                    data['vibration'][i] > 0.07), f"Abnormal row {i} does not breach any threshold"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="data/sensor_data.csv")
    args = parser.parse_args()
    generate_data(args.rows, args.seed, args.out)

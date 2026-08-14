from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from sklearn.preprocessing import StandardScaler

SENSOR_COLS = ["temp", "pressure", "vibration"]

@dataclass
class CleanResult:
    """Holds both the raw and standardized data, as well as a report on the cleaning process.
    The raw and standardized data are kept separate to allow for easy comparison and 
    to prevent accidental use of standardized data when physical units are required."""
    raw: pd.DataFrame
    standardized: pd.DataFrame
    report: dict

def preprocess(df):
    # Parse timestamps with errors="coerce" and drop unparseable rows
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp'])

    # Drop duplicate timestamps, keeping the first
    df = df.drop_duplicates(subset='timestamp', keep='first')

    # Fill missing sensor values using time-aware interpolation, then forward and back fill for gaps at the edges
    df_sensor = df[SENSOR_COLS].copy()
    df_sensor = df_sensor.set_index('timestamp')
    df_sensor = df_sensor.interpolate(method='time')
    df_sensor = df_sensor.fillna(method='ffill')
    df_sensor = df_sensor.fillna(method='bfill')
    df[SENSOR_COLS] = df_sensor.reset_index(drop=True)

    # Create a separate z-score standardized copy of only the sensor columns
    sensor_columns = [col for col in df.columns if col != 'timestamp']
    scaler = StandardScaler()
    standardized_df = pd.DataFrame(scaler.fit_transform(df[sensor_columns]), columns=sensor_columns, index=df.index)

    # Create a report dict with counts of duplicates removed and values imputed
    report = {
        'duplicates_removed': len(df) - len(df.drop_duplicates(subset='timestamp', keep='first')),
        'values_imputed': df.isnull().sum().sum() - standardized_df.isnull().sum().sum()
    }

    return CleanResult(df.reset_index(), standardized_df, report)

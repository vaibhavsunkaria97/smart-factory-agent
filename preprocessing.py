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
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="first")

    missing_before = int(df[SENSOR_COLS].isna().sum().sum())

    df = df.set_index("timestamp")
    df[SENSOR_COLS] = df[SENSOR_COLS].interpolate(method="time").ffill().bfill()
    df = df.reset_index()

    # Create a separate z-score standardized copy of only the sensor columns
    sensor_columns = [col for col in df.columns if col != 'timestamp']
    scaler = StandardScaler()
    standardized_df = pd.DataFrame(scaler.fit_transform(df[sensor_columns]), columns=sensor_columns, index=df.index)

    # Create a report dict with counts of duplicates removed and values imputed
    report = {
        'duplicates_removed': len(df) - len(df.drop_duplicates(subset='timestamp', keep='first')),
        'values_imputed': missing_before - int(standardized_df[SENSOR_COLS].isna().sum().sum())
    }

    return CleanResult(df.reset_index(), standardized_df, report)

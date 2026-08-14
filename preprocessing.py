"""
preprocessing.py
================
Cleans raw sensor data and prepares it for detection.

Returns TWO views of the data, deliberately kept separate:

  raw          - cleaned, in original physical units (48.9 C, 1.02 bar).
                 Used by the rule detector and by anything a human reads,
                 because "54.5 C exceeds the 52 C limit" is actionable.

  standardized - z-scored sensor columns only. Used by the ML detector,
                 which needs features on a comparable scale.

Merging them would mean either comparing 0.4 against a 52 C threshold, or
printing "temperature 1.87" to an operator. Hence two frames.
"""
from dataclasses import dataclass

import pandas as pd

SENSOR_COLS = ["temp", "pressure", "vibration"]


@dataclass
class CleanResult:
    raw: pd.DataFrame           # physical units
    standardized: pd.DataFrame  # z-scores, sensor columns only
    report: dict                # what the cleaning step did


def preprocess(df: pd.DataFrame) -> CleanResult:
    """Clean df and return raw + standardized frames plus a report."""
    report = {}
    df = df.copy()

    # 1. Timestamps. errors="coerce" turns unparseable values into NaT
    #    instead of raising, so one bad row can't kill the pipeline.
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    report["bad_timestamps_dropped"] = int(df["timestamp"].isna().sum())
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

    # 2. Duplicate timestamps - two readings can't share an instant.
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp"], keep="first")
    report["duplicates_removed"] = before - len(df)

    # 3. Missing values. Note: interpolation uses the value AFTER the gap,
    #    so it looks into the future. Fine for a saved file, invalid for a
    #    live stream - that is why the streaming path never re-imputes.
    report["missing_values_imputed"] = int(df[SENSOR_COLS].isna().sum().sum())
    df = df.set_index("timestamp")
    df[SENSOR_COLS] = df[SENSOR_COLS].interpolate(method="time").ffill().bfill()
    df = df.reset_index()

    # 4. Standardize ONLY the sensor columns. ddof=0 matches sklearn's
    #    StandardScaler; replace(0, 1) guards against a flatlined sensor.
    means = df[SENSOR_COLS].mean()
    stds = df[SENSOR_COLS].std(ddof=0).replace(0, 1.0)
    standardized = (df[SENSOR_COLS] - means) / stds

    report["rows_out"] = len(df)
    report["scaler_mean"] = means.round(4).to_dict()
    report["scaler_std"] = stds.round(4).to_dict()

    return CleanResult(
        raw=df.reset_index(drop=True),
        standardized=standardized.reset_index(drop=True),
        report=report,
    )
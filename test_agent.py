import pytest
import pandas as pd
import numpy as np
from generate_data import generate_data
from preprocessing import preprocess, SENSOR_COLS
from detectors import RuleDetector, AnomalyEnsemble, Detection, THRESHOLDS


@pytest.fixture
def generated_data(tmp_path):
    """Generate a small dataset and return the DataFrame."""
    out_file = tmp_path / "sensor_data.csv"
    generate_data(rows=100, seed=42, out=str(out_file))
    df = pd.read_csv(out_file)
    return df


def test_generate_columns_and_labels(generated_data):
    df = generated_data
    expected_cols = ["timestamp", "temp", "pressure", "vibration", "label"]
    assert list(df.columns) == expected_cols
    assert set(df["label"].unique()).issubset({"normal", "abnormal"})


def test_generate_injects_missing_values(generated_data):
    df = generated_data
    # At least one NaN in sensor columns
    assert df[SENSOR_COLS].isna().sum().sum() > 0


def test_abnormal_rows_breach_threshold(generated_data):
    df = generated_data
    for _, row in df.iterrows():
        if row["label"] == "abnormal":
            temp_breach = row["temp"] < THRESHOLDS["temp"]["low"] or row["temp"] > THRESHOLDS["temp"]["high"]
            pressure_breach = row["pressure"] < THRESHOLDS["pressure"]["low"] or row["pressure"] > THRESHOLDS["pressure"]["high"]
            vibration_breach = row["vibration"] > THRESHOLDS["vibration"]["high"]
            assert temp_breach or pressure_breach or vibration_breach, f"Row {row.name} labeled abnormal but no threshold breached"


def test_preprocess_removes_nans(generated_data):
    clean = preprocess(generated_data)
    assert clean.raw[SENSOR_COLS].isna().sum().sum() == 0
    assert clean.standardized.isna().sum().sum() == 0


def test_preprocess_removes_duplicate_timestamps(generated_data):
    clean = preprocess(generated_data)
    assert clean.raw["timestamp"].is_unique


def test_standardized_zero_mean_unit_variance(generated_data):
    clean = preprocess(generated_data)
    means = clean.standardized.mean()
    stds = clean.standardized.std(ddof=0)
    for col in SENSOR_COLS:
        assert means[col] == pytest.approx(0.0, abs=1e-10)
        assert stds[col] == pytest.approx(1.0, abs=1e-10)


def test_rule_detector_flags_high_temp():
    detector = RuleDetector()
    row = pd.Series({"temp": 55.0, "pressure": 1.02, "vibration": 0.03})
    breaches = detector.check(row)
    assert any(sig == "temp" and direction == "high" for sig, direction, _ in breaches)


def test_rule_detector_normal_row_returns_empty():
    detector = RuleDetector()
    row = pd.Series({"temp": 48.0, "pressure": 1.02, "vibration": 0.03})
    breaches = detector.check(row)
    assert breaches == []


def test_rule_detector_finds_all_three_breaches():
    detector = RuleDetector()
    row = pd.Series({
        "temp": 60.0,          # high
        "pressure": 0.90,      # low
        "vibration": 0.10      # high
    })
    breaches = detector.check(row)
    assert len(breaches) == 3
    signals = {sig for sig, _, _ in breaches}
    assert signals == {"temp", "pressure", "vibration"}


def test_detection_score_and_severity_valid(generated_data):
    clean = preprocess(generated_data)
    ensemble = AnomalyEnsemble(contamination=0.12, random_state=42)
    detections = ensemble.detect(clean.raw, clean.standardized)
    for det in detections:
        assert 0.0 <= det.score <= 1.0
        assert det.severity in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def test_regression_single_row_score_matches_batch(generated_data):
    clean = preprocess(generated_data)
    ensemble = AnomalyEnsemble(contamination=0.12, random_state=42)
    # Fit on the whole standardized set
    ensemble.fit(clean.standardized)

    # Run detect on the full batch to get reference scores
    full_detections = ensemble.detect(clean.raw, clean.standardized)
    full_scores = {det.index: det.score for det in full_detections}

    # Test each row individually using the same fitted ensemble
    for idx in clean.raw.index:
        raw_one = clean.raw.loc[[idx]]
        std_one = clean.standardized.loc[[idx]]
        single_detections = ensemble.detect(raw_one, std_one)

        if idx in full_scores:
            assert len(single_detections) == 1
            single_score = single_detections[0].score
            full_score = full_scores[idx]
            assert single_score == pytest.approx(full_score, rel=1e-6), (
                f"Score mismatch for index {idx}: single={single_score}, batch={full_score}"
            )
        else:
            # Row not flagged in full batch should not be flagged in single batch either
            assert len(single_detections) == 0, f"Row {idx} flagged in single but not in batch"

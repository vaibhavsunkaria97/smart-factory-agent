import pandas as pd

THRESHOLDS = {
    'temp': {'high': 52.0, 'low': 43.0},
    'pressure': {'high': 1.08, 'low': 0.97},
    'vibration': {'high': 0.07, 'low': None}
}

class RuleDetector:
    """
    A class used to detect breaches of sensor data against predefined thresholds.

    Attributes:
    ----------
    None

    Methods:
    -------
    check(row): Checks a pandas Series against the thresholds and returns a list of breaches.
    """

    def check(self, row: pd.Series) -> list:
        """
        Checks a pandas Series against the thresholds and returns a list of breaches.

        Parameters:
        ----------
        row : pd.Series
            A pandas Series containing sensor data.

        Returns:
        -------
        list
            A list of tuples, each containing the signal, direction, and value of a breach.
        """
        breaches = []
        for signal, limits in THRESHOLDS.items():
            value = row[signal]
            if limits['high'] is not None and value > limits['high']:
                breaches.append((signal, 'high', value))
            if limits['low'] is not None and value < limits['low']:
                breaches.append((signal, 'low', value))
        return breaches
from dataclasses import dataclass
from sklearn.ensemble import IsolationForest
import numpy as np

@dataclass
class Detection:
    index: int
    timestamp: str
    values: dict
    breached: list
    rule_flag: bool
    iforest_flag: bool
    score: float
    severity: str

class AnomalyEnsemble:
    def __init__(self, contamination=0.12, random_state=42):
        self.detector = RuleDetector()
        self.iforest = IsolationForest(n_estimators=200, contamination=contamination, random_state=random_state)
        self._fitted = False
        self._lo = None
        self._hi = None

    def fit(self, standardized):
        self.iforest.fit(standardized.values)
        raw_scores = -self.iforest.score_samples(standardized.values)
        self._lo = np.percentile(raw_scores, 5)
        self._hi = np.percentile(raw_scores, 99)
        self._fitted = True

    def _normalise(self, raw_scores):
        return np.clip((raw_scores - self._lo) / (self._hi - self._lo), 0, 1)

    @staticmethod
    def _severity(n_breaches, score):
        if score >= 0.85 or n_breaches >= 2:
            return 'CRITICAL'
        elif score >= 0.6 or n_breaches == 1:
            return 'HIGH'
        elif score >= 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'

    def detect(self, raw, standardized):
        if not self._fitted:
            self.fit(standardized)
        ml_scores = -self.iforest.score_samples(standardized.values)  # Note: sklearn returns LOWER values for MORE anomalous points, hence the negation.
        normalised_ml_scores = self._normalise(ml_scores)
        iforest_flags = self.iforest.predict(standardized.values) == -1
        detections = []
        for i in range(len(raw)):
            row = raw.iloc[i]
            breached = self.detector.check(row)
            rule_flag = len(breached) > 0
            iforest_flag = iforest_flags[i]
            if not rule_flag and not iforest_flag:
                continue
            rule_component = min(1.0, 0.55 + 0.25*len(breached)) if breached else 0.0
            normalised_ml_score = normalised_ml_scores[i]
            score = max(rule_component, normalised_ml_score)
            severity = self._severity(len(breached), score)
            detection = Detection(
                index=row.name,
                timestamp=row['timestamp'],
                values=dict(row),
                breached=breached,
                rule_flag=rule_flag,
                iforest_flag=iforest_flag,
                score=score,
                severity=severity
            )
            detections.append(detection)
        return detections

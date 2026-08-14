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

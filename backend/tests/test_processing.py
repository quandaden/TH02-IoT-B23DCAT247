from __future__ import annotations

import unittest

import pandas as pd

from iot_pipeline.processing import preprocess_frame


class ProcessingTests(unittest.TestCase):
    def test_resampling_missing_values_outliers_and_features(self) -> None:
        times = pd.to_datetime(
            [
                "2026-09-29T10:00:00Z",
                "2026-09-29T10:00:10Z",
                "2026-09-29T10:00:30Z",
                "2026-09-29T10:00:40Z",
                "2026-09-29T10:00:50Z",
                "2026-09-29T10:01:00Z",
                "2026-09-29T10:01:10Z",
            ]
        )
        frame = pd.DataFrame(
            {
                "_time": times,
                "device_id": ["esp32-test"] * len(times),
                "sequence": [1, 2, 3, 4, 5, 6, 7],
                "uptime_s": [5, 10, 20, 25, 30, 35, 40],
                "temperature": [20, 21, 22, 23, 24, 25, 80],
                "humidity": [40, 41, 42, 43, 44, 45, 46],
                "distance_cm": [50, 51, 52, 53, 54, 55, 56],
                "rssi": [-70] * len(times),
                "latency_ms": [20, 25, 21, 22, 24, 23, 26],
                "gap_count": [0] * len(times),
            }
        )

        result = preprocess_frame(frame, frequency="10s", rolling_window=3)

        self.assertEqual(len(result), 8)
        self.assertTrue(result["temperature_missing"].any())
        self.assertTrue(result["temperature_outlier"].iloc[-1])
        self.assertIn("temperature_clean", result.columns)
        self.assertIn("temperature_rolling_mean", result.columns)
        self.assertIn("temperature_delta", result.columns)
        self.assertIn("temperature_normalized", result.columns)
        self.assertFalse(result["temperature_clean"].isna().any())

    def test_missing_required_column_is_reported(self) -> None:
        frame = pd.DataFrame(
            {
                "_time": pd.to_datetime(["2026-09-29T10:00:00Z"]),
                "device_id": ["esp32-test"],
                "sequence": [1],
            }
        )
        with self.assertRaisesRegex(ValueError, "missing columns"):
            preprocess_frame(frame)


if __name__ == "__main__":
    unittest.main()


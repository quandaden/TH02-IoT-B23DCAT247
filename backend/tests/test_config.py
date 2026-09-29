from __future__ import annotations

import unittest

from iot_pipeline.config import _duration_seconds


class DurationParsingTests(unittest.TestCase):
    def test_accepts_plain_seconds(self) -> None:
        self.assertEqual(_duration_seconds("604800", 0), 604800)

    def test_accepts_duration_suffixes(self) -> None:
        self.assertEqual(_duration_seconds("604800s", 0), 604800)
        self.assertEqual(_duration_seconds("10m", 0), 600)
        self.assertEqual(_duration_seconds("2h", 0), 7200)
        self.assertEqual(_duration_seconds("7d", 0), 604800)


if __name__ == "__main__":
    unittest.main()

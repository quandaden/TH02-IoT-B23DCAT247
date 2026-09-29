from __future__ import annotations

import unittest

from iot_pipeline.sequence_tracker import SequenceTracker


class SequenceTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = SequenceTracker()

    def test_normal_sequence_and_gap(self) -> None:
        self.assertEqual(self.tracker.observe("device", 1, 5).status, "first")
        self.assertEqual(self.tracker.observe("device", 2, 10).status, "normal")
        gap = self.tracker.observe("device", 5, 15)
        self.assertEqual(gap.status, "gap")
        self.assertEqual(gap.gap_count, 2)

    def test_duplicate_is_not_stored(self) -> None:
        self.tracker.observe("device", 1, 5)
        duplicate = self.tracker.observe("device", 1, 5)
        self.assertEqual(duplicate.status, "duplicate")
        self.assertFalse(duplicate.should_store)

    def test_restart_is_detected(self) -> None:
        self.tracker.observe("device", 20, 100)
        restart = self.tracker.observe("device", 1, 5)
        self.assertEqual(restart.status, "restart")
        self.assertTrue(restart.should_store)


if __name__ == "__main__":
    unittest.main()


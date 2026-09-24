import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from generator.freshness import snapshot_needs_update


TZ = ZoneInfo("Asia/Shanghai")


class SnapshotFreshnessTests(unittest.TestCase):
    def test_scheduled_retry_skips_a_complete_snapshot_from_today(self):
        payload = {
            "dataDate": "2026-09-24",
            "coverage": {"available": 78, "total": 78},
        }

        self.assertFalse(snapshot_needs_update(
            payload, "schedule", datetime(2026, 9, 24, 17, 0, tzinfo=TZ),
        ))

    def test_scheduled_retry_runs_for_stale_or_incomplete_snapshots(self):
        now = datetime(2026, 9, 24, 17, 0, tzinfo=TZ)
        stale = {"dataDate": "2026-09-23", "coverage": {"available": 78, "total": 78}}
        incomplete = {"dataDate": "2026-09-24", "coverage": {"available": 77, "total": 78}}

        self.assertTrue(snapshot_needs_update(stale, "schedule", now))
        self.assertTrue(snapshot_needs_update(incomplete, "schedule", now))

    def test_manual_and_push_runs_are_always_forced(self):
        payload = {
            "dataDate": "2026-09-24",
            "coverage": {"available": 78, "total": 78},
        }
        now = datetime(2026, 9, 24, 17, 0, tzinfo=TZ)

        self.assertTrue(snapshot_needs_update(payload, "workflow_dispatch", now))
        self.assertTrue(snapshot_needs_update(payload, "push", now))


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone

from app.lab import context


class ContextTests(unittest.TestCase):
    def test_blackout_window_around_fomc(self):
        utc = timezone.utc
        self.assertIn("FOMC", context.macro_blackout(datetime(2026, 10, 28, 8, 0, tzinfo=utc)))
        self.assertIsNone(context.macro_blackout(datetime(2026, 10, 27, 5, 0, tzinfo=utc)))
        self.assertIsNone(context.macro_blackout(datetime(2026, 10, 29, 1, 0, tzinfo=utc)))
        self.assertEqual(context.next_event(datetime(2026, 10, 29, 1, 0, tzinfo=utc))["evento"], "CPI EE. UU.")

    def test_snapshot_degrades_when_a_source_fails(self):
        class Down:
            def get(self, *a, **k):
                raise OSError("sin red")

        snap = context.snapshot(Down())
        self.assertTrue(snap["fear_greed"].startswith("no disponible"))
        self.assertTrue(snap["BTCUSDT"].startswith("no disponible"))


if __name__ == "__main__":
    unittest.main()

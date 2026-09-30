import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from collect_market_snapshots import collect_snapshot


class CollectMarketSnapshotsTest(unittest.TestCase):
    @patch(
        "collect_market_snapshots.fetch_exchange_quotes"
    )
    def test_collect_snapshot_keeps_market_quotes(
        self,
        fetch_mock,
    ) -> None:
        fetch_mock.return_value = [
            {
                "exchange": "binance",
                "status": "ok",
                "ask_price": "100",
                "bid_price": "99",
            }
        ]

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

        result = collect_snapshot(
            symbol="btcusdt",
            timestamp=timestamp,
        )

        self.assertEqual(
            result["symbol"],
            "btcusdt",
        )
        self.assertEqual(
            len(result["quotes"]),
            1,
        )
        fetch_mock.assert_called_once_with(
            "btcusdt"
        )

    def test_output_parent_can_be_created_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = (
                Path(temp_dir)
                / "nested"
                / "data"
                / "snapshots.jsonl"
            )

            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with output.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write("{}\n")

            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()

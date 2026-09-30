import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.strategy_lab_service import (
    Snapshot,
    StrategyConfig,
    backtest,
    grid_search,
    split_time_series,
)


def quote(exchange: str, ask: str, bid: str) -> dict:
    return {
        "exchange": exchange,
        "symbol": "BTCUSDT",
        "quote_currency": "USDT",
        "status": "ok",
        "ask_price": ask,
        "bid_price": bid,
        "ask_quantity": "1",
        "bid_quantity": "1",
        "last_price": bid,
        "volume_24h": "100000",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


class StrategyLabTest(unittest.TestCase):
    def make_snapshots(self) -> list[Snapshot]:
        base = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        return [
            Snapshot(
                timestamp=base,
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=2),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=4),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
        ]

    def make_adverse_snapshots(self) -> list[Snapshot]:
        base = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        return [
            Snapshot(
                timestamp=base,
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=2),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "105", "104"),
                    quote("bybit", "105.2", "104.1"),
                ],
            ),
        ]

    def test_backtest_uses_same_exchanges_after_latency(self) -> None:
        result = backtest(
            self.make_adverse_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
            ),
        )

        self.assertEqual(result.executable_candidates, 1)
        self.assertEqual(result.survived_samples, 0)
        self.assertLess(result.total_proxy_profit_usd, Decimal("0"))

    def test_max_drawdown_tracks_losses(self) -> None:
        result = backtest(
            self.make_adverse_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
            ),
        )

        self.assertGreater(result.max_drawdown_usd, Decimal("0"))

    def test_backtest_produces_positive_proxy_result(self) -> None:
        result = backtest(
            self.make_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
                cooldown_seconds=0,
            ),
        )

        self.assertGreaterEqual(result.snapshots, 3)
        self.assertGreater(result.survived_samples, 0)
        self.assertGreater(result.total_proxy_profit_usd, Decimal("0"))

    def test_grid_search_returns_ranked_results(self) -> None:
        snapshots = self.make_snapshots()
        configs = [
            StrategyConfig(min_profit_percent=Decimal("0.01")),
            StrategyConfig(min_profit_percent=Decimal("0.50")),
        ]
        results = grid_search(snapshots, configs)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(
            results[0].total_proxy_profit_usd,
            results[1].total_proxy_profit_usd,
        )

    def test_time_split_is_chronological(self) -> None:
        train, validation, test = split_time_series(self.make_snapshots())
        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertTrue(test)
        self.assertLessEqual(train[-1].timestamp, validation[0].timestamp)
        self.assertLessEqual(validation[-1].timestamp, test[0].timestamp)

    def test_time_split_keeps_small_dataset_partitions_non_empty(self) -> None:
        train, validation, test = split_time_series(self.make_snapshots())
        self.assertEqual(len(train), 1)
        self.assertEqual(len(validation), 1)
        self.assertEqual(len(test), 1)


if __name__ == "__main__":
    unittest.main()
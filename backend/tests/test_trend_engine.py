"""Regla de tendencia diaria: dentro solo si close > SMA50 y > SMA200."""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.signal_engine import Candle, SignalAction
from app.domain.trend_engine import TrendConfig, evaluate_trend

NOW = datetime(2026, 10, 16, 1, 0)


def daily(closes: list[str], *, include_today: bool = False) -> list[Candle]:
    """Velas 1d que terminan ayer (o hoy, si include_today)."""
    last_day = NOW.date() if include_today else NOW.date() - timedelta(days=1)
    start = datetime.combine(last_day, datetime.min.time()) - timedelta(
        days=len(closes) - 1
    )
    return [
        Candle(
            open_time=start + timedelta(days=i),
            open=Decimal(c),
            high=Decimal(c),
            low=Decimal(c),
            close=Decimal(c),
            volume=Decimal("1"),
        )
        for i, c in enumerate(closes)
    ]


CFG = TrendConfig(fast=2, slow=4)


class TrendEngineTests(unittest.TestCase):
    def test_inside_when_close_above_both_smas(self) -> None:
        result = evaluate_trend(daily(["10", "11", "12", "13"]), NOW, CFG)
        self.assertEqual(result.action, SignalAction.BUY)
        self.assertEqual(result.metrics["sma_fast"], "12.50000000")
        self.assertEqual(result.metrics["sma_slow"], "11.50000000")
        self.assertEqual(result.metrics["candle_date"], "2026-10-15")

    def test_outside_when_below_fast_sma(self) -> None:
        result = evaluate_trend(daily(["10", "11", "14", "12"]), NOW, CFG)
        self.assertEqual(result.action, SignalAction.SELL)

    def test_tie_with_sma_counts_as_outside(self) -> None:
        result = evaluate_trend(daily(["10", "10", "10", "10"]), NOW, CFG)
        self.assertEqual(result.action, SignalAction.SELL)

    def test_insufficient_data_holds(self) -> None:
        result = evaluate_trend(daily(["10", "11", "12"]), NOW, CFG)
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "insufficient_daily_data")

    def test_candle_in_progress_is_ignored(self) -> None:
        # Hoy se dispararía a 100 (look-ahead); solo cuentan las cerradas.
        candles = daily(["10", "11", "14", "12", "100"], include_today=True)
        result = evaluate_trend(candles, NOW, CFG)
        self.assertEqual(result.action, SignalAction.SELL)
        self.assertEqual(result.metrics["close"], "12")

    def test_defaults_are_50_200(self) -> None:
        self.assertEqual((TrendConfig().fast, TrendConfig().slow), (50, 200))
        with self.assertRaises(ValueError):
            TrendConfig(fast=200, slow=50)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.signal_engine import Candle
from app.domain.trend_filter import (
    closed_hourly_candles,
    compute_ema,
    trend_allows,
)

HOUR = timedelta(hours=1)


def _candle(open_time: datetime, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        open_time=open_time,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=Decimal("1"),
    )


class ComputeEmaTests(unittest.TestCase):
    def test_known_case_seed_sma(self) -> None:
        closes = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        ema = compute_ema(closes, period=3)
        self.assertEqual(ema, Decimal("4"))

    def test_fewer_than_period_returns_none(self) -> None:
        closes = [Decimal("1"), Decimal("2")]
        self.assertIsNone(compute_ema(closes, period=3))

    def test_exact_period_is_sma(self) -> None:
        closes = [Decimal("2"), Decimal("4"), Decimal("6")]
        ema = compute_ema(closes, period=3)
        self.assertEqual(ema, Decimal("4"))

    def test_invalid_period_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_ema([Decimal("1")], period=0)


class ClosedHourlyCandlesTests(unittest.TestCase):
    def test_excludes_unclosed_candle(self) -> None:
        base = datetime(2026, 1, 1, 10, 0)
        hourly = [_candle(base, "100"), _candle(base + HOUR, "101")]
        as_of = base + HOUR + timedelta(minutes=30)
        closed = closed_hourly_candles(hourly, as_of)
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].open_time, base)

    def test_includes_candle_closed_exactly_at_as_of(self) -> None:
        base = datetime(2026, 1, 1, 10, 0)
        hourly = [_candle(base, "100")]
        as_of = base + HOUR
        closed = closed_hourly_candles(hourly, as_of)
        self.assertEqual(len(closed), 1)

    def test_none_returns_empty(self) -> None:
        self.assertEqual(closed_hourly_candles(None, datetime(2026, 1, 1)), [])


class TrendAllowsTests(unittest.TestCase):
    def _hourly(self, count: int) -> list[Candle]:
        base = datetime(2026, 1, 1, 0, 0)
        return [_candle(base + i * HOUR, str(100 + i)) for i in range(count)]

    def test_fail_closed_when_fewer_than_period(self) -> None:
        hourly = self._hourly(49)
        as_of = datetime(2026, 1, 3, 2, 0)
        allowed, metrics = trend_allows(Decimal("200"), hourly, as_of, period=50)
        self.assertFalse(allowed)
        self.assertIsNone(metrics["trend_filter_ema50"])

    def test_fail_closed_when_none(self) -> None:
        allowed, _ = trend_allows(Decimal("100"), None, datetime(2026, 1, 1))
        self.assertFalse(allowed)

    def test_rejects_when_close_below_ema(self) -> None:
        hourly = self._hourly(50)
        as_of = datetime(2026, 1, 3, 2, 0)
        allowed, _ = trend_allows(Decimal("50"), hourly, as_of)
        self.assertFalse(allowed)

    def test_allows_when_close_at_or_above_ema(self) -> None:
        hourly = self._hourly(50)
        as_of = datetime(2026, 1, 3, 2, 0)
        allowed, metrics = trend_allows(Decimal("1000"), hourly, as_of)
        self.assertTrue(allowed)
        self.assertEqual(metrics["trend_filter_closed_candles"], 50)


if __name__ == "__main__":
    unittest.main()

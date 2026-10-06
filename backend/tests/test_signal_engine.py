import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.domain.signal_engine import (
    Candle,
    SignalAction,
    SignalResult,
    StrategyConfig,
    evaluate,
)

TEST_CONFIG = StrategyConfig(
    ema_short_period=3,
    ema_long_period=6,
    rsi_period=4,
    rsi_buy_max=Decimal("90"),
    rsi_sell_min=Decimal("95"),
    volume_factor=Decimal("1.2"),
    volume_avg_period=5,
)


def _candles(closes, volumes=None):
    base = datetime(2026, 1, 1, 0, 0)
    if volumes is None:
        volumes = [Decimal("100")] * len(closes)
    return [
        Candle(
            open_time=base + timedelta(minutes=15 * i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=volumes[i],
        )
        for i, c in enumerate(closes)
    ]


# Bajista con final en rally: produce cruce alcista con RSI aún < 90.
BUY_CLOSES = [
    100, 98, 96, 94, 92, 90, 88, 86, 84, 82, 83, 85, 88, 92,
]
BUY_VOLUMES = [
    Decimal("100")] * 13 + [Decimal("200")]

# Tendencia alcista sostenida: RSI llega a ~100 (sobrecomprado).
SELL_OVERBOUGHT_CLOSES = [100 + 3 * i for i in range(30)]

# Alza y después caída: el cruce bajista ocurre justo en la última vela.
SELL_CROSS_CLOSES = [100 + 2 * i for i in range(20)] + [130, 122]


class DeterminismTests(unittest.TestCase):
    def test_deterministic_signal(self) -> None:
        candles = _candles(BUY_CLOSES, BUY_VOLUMES)
        results = [evaluate(candles, TEST_CONFIG) for _ in range(3)]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(results[0].metrics, results[2].metrics)
        self.assertIsInstance(results[0], SignalResult)
        self.assertEqual(results[0].action, SignalAction.BUY)

    def test_same_signal_from_equivalent_input(self) -> None:
        first = evaluate(_candles(BUY_CLOSES, BUY_VOLUMES), TEST_CONFIG)
        second = evaluate(_candles(BUY_CLOSES, BUY_VOLUMES), TEST_CONFIG)
        self.assertEqual(first, second)


class BuySellCasesTests(unittest.TestCase):
    def test_buy_case(self) -> None:
        result = evaluate(_candles(BUY_CLOSES, BUY_VOLUMES), TEST_CONFIG)
        self.assertEqual(result.action, SignalAction.BUY)
        self.assertEqual(result.reason, "cross_up_rsi_zone_volume")
        for key in ("ema_short", "ema_long", "rsi", "volume_ratio", "cross"):
            self.assertIn(key, result.metrics)
        self.assertEqual(result.metrics["cross"], "up")

    def test_sell_case_rsi_overbought(self) -> None:
        result = evaluate(_candles(SELL_OVERBOUGHT_CLOSES), TEST_CONFIG)
        self.assertEqual(result.action, SignalAction.SELL)
        self.assertEqual(result.reason, "rsi_overbought")

    def test_sell_case_cross_down(self) -> None:
        result = evaluate(_candles(SELL_CROSS_CLOSES), TEST_CONFIG)
        self.assertEqual(result.action, SignalAction.SELL)
        self.assertEqual(result.reason, "cross_down")
        self.assertEqual(result.metrics["cross"], "down")

    def test_buy_requires_all_conditions(self) -> None:
        strict = StrategyConfig(
            ema_short_period=3,
            ema_long_period=6,
            rsi_period=4,
            rsi_buy_max=Decimal("60"),
            rsi_sell_min=Decimal("95"),
            volume_factor=Decimal("1.2"),
            volume_avg_period=5,
        )
        result = evaluate(_candles(BUY_CLOSES, BUY_VOLUMES), strict)
        self.assertNotEqual(result.action, SignalAction.BUY)

        low_volume = _candles(
            BUY_CLOSES,
            [Decimal("100")] * 13 + [Decimal("101")],
        )
        result_low_volume = evaluate(low_volume, TEST_CONFIG)
        self.assertNotEqual(result_low_volume.action, SignalAction.BUY)


class HoldCasesTests(unittest.TestCase):
    def test_not_enough_data(self) -> None:
        result = evaluate(_candles([100, 101, 102]), TEST_CONFIG)
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "not_enough_data")

    def test_no_signal_flat_market(self) -> None:
        closes = [Decimal("100")] * 30
        result = evaluate(_candles(closes), TEST_CONFIG)
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "no_signal")


class PurityTests(unittest.TestCase):
    def test_engine_module_has_no_io_dependencies(self) -> None:
        source = Path("app/domain/signal_engine.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("httpx", "sqlalchemy", "requests", "fastapi"):
            self.assertNotIn(forbidden, source)


class ConfigValidationTests(unittest.TestCase):
    def test_invalid_periods_rejected(self) -> None:
        with self.assertRaises(ValueError):
            StrategyConfig(ema_short_period=0)
        with self.assertRaises(ValueError):
            StrategyConfig(rsi_period=0)
        with self.assertRaises(ValueError):
            StrategyConfig(volume_avg_period=0)
        with self.assertRaises(ValueError):
            StrategyConfig(ema_short_period=10, ema_long_period=5)
        with self.assertRaises(ValueError):
            StrategyConfig(rsi_buy_max=Decimal("90"), rsi_sell_min=Decimal("50"))

    def test_candle_requires_decimal_amounts(self) -> None:
        with self.assertRaises(TypeError):
            Candle(
                open_time=datetime(2026, 1, 1),
                open=1.5,  # type: ignore[arg-type]
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
            )


if __name__ == "__main__":
    unittest.main()

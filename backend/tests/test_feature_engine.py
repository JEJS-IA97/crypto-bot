"""Tests rojos — Spec 006: feature_engine (RF-5).

Features deterministas en Decimal, sin look-ahead y con `null` honesto
ante datos insuficientes.
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.signal_engine import Candle

BASE = datetime(2026, 10, 5, 0, 0)


def _candle(
    index: int,
    close: str,
    *,
    high: str | None = None,
    low: str | None = None,
    volume: str = "100",
    base: datetime = BASE,
) -> Candle:
    value = Decimal(close)
    return Candle(
        open_time=base + timedelta(minutes=5 * index),
        open=value,
        high=Decimal(high) if high else value + Decimal("1"),
        low=Decimal(low) if low else value - Decimal("1"),
        close=value,
        volume=Decimal(volume),
    )


def _rising(n: int, *, volume: str = "100") -> list[Candle]:
    return [
        _candle(index, str(100 + index), volume=volume)
        for index in range(n)
    ]


class FeatureTests(unittest.TestCase):
    def test_known_series_values(self) -> None:
        from app.domain.feature_engine import (
            FeaturePeriods,
            compute_features,
        )

        candles = [
            _candle(0, "100"),
            _candle(1, "101"),
            _candle(2, "102"),
            _candle(3, "103"),
            _candle(4, "104"),
            _candle(5, "105"),
        ]
        periods = FeaturePeriods(
            return_period=3,
            volatility_period=4,
            volume_period=4,
            ema_short_period=3,
            ema_long_period=4,
            rsi_period=3,
        )
        features = compute_features(
            candles, now=BASE + timedelta(minutes=25), periods=periods
        )

        # Retorno de 3 velas: (105-102)/102*100.
        self.assertEqual(
            features.return_pct.quantize(Decimal("0.0001")),
            Decimal("2.9412"),
        )
        # Posición en el rango: (105-99)/(106-99)*100 = 600/7.
        self.assertEqual(
            features.range_position_pct.quantize(Decimal("0.0001")),
            Decimal("85.7143"),
        )
        # Volumen constante → z-score no definido (nunca se inventa).
        self.assertIsNone(features.volume_zscore)
        # Volatilidad: variación positiva presente.
        self.assertIsNotNone(features.volatility_pct)
        self.assertGreaterEqual(features.volatility_pct, Decimal("0"))
        # Tendencia: EMA corta > larga en serie ascendente.
        self.assertGreater(features.ema_spread_pct, Decimal("0"))
        # RSI en subida sin bajadas → 100 exacto.
        self.assertEqual(features.rsi, Decimal("100"))

        for field in (
            features.return_pct,
            features.volatility_pct,
            features.range_position_pct,
            features.ema_spread_pct,
            features.rsi,
        ):
            self.assertIsInstance(field, Decimal)

    def test_insufficient_data_gives_none_not_estimates(self) -> None:
        from app.domain.feature_engine import compute_features

        # 3 velas con los períodos por defecto (20/21/14): todo null
        # salvo el rango, que sí puede calcularse.
        features = compute_features(
            _rising(3), now=BASE + timedelta(minutes=10)
        )
        self.assertIsNone(features.return_pct)
        self.assertIsNone(features.volatility_pct)
        self.assertIsNone(features.volume_zscore)
        self.assertIsNone(features.ema_spread_pct)
        self.assertIsNone(features.rsi)
        self.assertIsNotNone(features.range_position_pct)

    def test_future_candles_are_ignored(self) -> None:
        from app.domain.feature_engine import (
            FeaturePeriods,
            compute_features,
        )

        periods = FeaturePeriods(
            return_period=3,
            volatility_period=4,
            volume_period=4,
            ema_short_period=3,
            ema_long_period=4,
            rsi_period=3,
        )
        past = [
            _candle(0, "100"),
            _candle(1, "101"),
            _candle(2, "102"),
            _candle(3, "103"),
            _candle(4, "104"),
        ]
        # Vela futura con precios extremos: si mirara el futuro, el rango
        # y el retorno cambiarían.
        future = _candle(9, "999", high="1000", low="998")
        now = BASE + timedelta(minutes=20)  # 10:00 → la vela 9 es futura

        baseline = compute_features(past, now=now, periods=periods)
        with_future = compute_features(
            past + [future], now=now, periods=periods
        )
        self.assertEqual(
            baseline.return_pct.quantize(Decimal("0.0001")),
            Decimal("2.9703"),
        )
        self.assertEqual(with_future, baseline)

    def test_range_uses_available_slice_only(self) -> None:
        from app.domain.feature_engine import compute_features

        candles = [
            _candle(0, "100", high="110", low="90"),
            _candle(1, "105", high="106", low="99"),
        ]
        features = compute_features(
            candles, now=BASE + timedelta(minutes=5)
        )
        # (105-90)/(110-90)*100 = 75.
        self.assertEqual(features.range_position_pct, Decimal("75"))


if __name__ == "__main__":
    unittest.main()

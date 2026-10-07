"""Deterministic feature engine for candidate scoring (spec 006, RF-5).

Pure module: no network, no database, no framework imports. Every feature is
computed in ``Decimal`` from candles with ``open_time <= now`` (no
look-ahead) and is ``None`` when the available data is insufficient — never
estimated.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.signal_engine import Candle, _ema, _rsi

_HUNDRED = Decimal("100")


@dataclass(frozen=True)
class FeaturePeriods:
    """Window lengths for each feature (RF-5); defaults come from the spec."""

    return_period: int = 3
    volatility_period: int = 20
    volume_period: int = 20
    ema_short_period: int = 9
    ema_long_period: int = 21
    rsi_period: int = 14

    def __post_init__(self) -> None:
        for name in (
            "return_period",
            "volatility_period",
            "volume_period",
            "ema_short_period",
            "ema_long_period",
            "rsi_period",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")


@dataclass(frozen=True)
class FeatureVector:
    """One feature set; ``None`` means 'not computable', never an estimate."""

    return_pct: Decimal | None = None
    volatility_pct: Decimal | None = None
    range_position_pct: Decimal | None = None
    volume_zscore: Decimal | None = None
    ema_spread_pct: Decimal | None = None
    rsi: Decimal | None = None


def _pct_change(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return (current - previous) / previous * _HUNDRED


def _stdev(values: list[Decimal]) -> Decimal:
    """Population standard deviation in Decimal (deterministic)."""
    mean = sum(values) / Decimal(len(values))
    variance = sum((value - mean) ** 2 for value in values) / Decimal(
        len(values)
    )
    return variance.sqrt()


def compute_features(
    candles: list[Candle],
    *,
    now: datetime,
    periods: FeaturePeriods = FeaturePeriods(),
) -> FeatureVector:
    """Return the feature vector for the slice of candles up to ``now``."""
    visible = [candle for candle in candles if candle.open_time <= now]
    if not visible:
        return FeatureVector()

    closes = [candle.close for candle in visible]

    return_pct: Decimal | None = None
    if len(visible) >= periods.return_period + 1:
        return_pct = _pct_change(
            closes[-1], closes[-1 - periods.return_period]
        )

    volatility_pct: Decimal | None = None
    volatility_window = periods.volatility_period + 1
    if len(visible) >= volatility_window:
        window = closes[-volatility_window:]
        changes = [
            change
            for change in (
                _pct_change(current, previous)
                for previous, current in zip(window, window[1:])
            )
            if change is not None
        ]
        if changes:
            volatility_pct = _stdev(changes)

    range_position_pct: Decimal | None = None
    top = max(candle.high for candle in visible)
    bottom = min(candle.low for candle in visible)
    if top > bottom:
        range_position_pct = (closes[-1] - bottom) / (top - bottom) * _HUNDRED

    volume_zscore: Decimal | None = None
    if len(visible) >= periods.volume_period:
        volumes = [
            candle.volume for candle in visible[-periods.volume_period :]
        ]
        deviation = _stdev(volumes)
        if deviation > 0:
            mean_volume = sum(volumes) / Decimal(len(volumes))
            volume_zscore = (volumes[-1] - mean_volume) / deviation

    ema_spread_pct: Decimal | None = None
    short_last = _ema(closes, periods.ema_short_period)[-1]
    long_last = _ema(closes, periods.ema_long_period)[-1]
    if short_last is not None and long_last is not None and long_last != 0:
        ema_spread_pct = (short_last - long_last) / long_last * _HUNDRED

    try:
        rsi: Decimal | None = _rsi(closes, periods.rsi_period)
    except ValueError:
        rsi = None

    return FeatureVector(
        return_pct=return_pct,
        volatility_pct=volatility_pct,
        range_position_pct=range_position_pct,
        volume_zscore=volume_zscore,
        ema_spread_pct=ema_spread_pct,
        rsi=rsi,
    )

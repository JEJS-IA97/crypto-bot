"""Deterministic technical signal engine (spec 001, RF-7).

Pure module: no network, no database, no framework imports. Same candles and
same config always produce the same signal, verified by tests.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

_HUNDRED = Decimal("100")
_METRIC_PLACES = Decimal("0.00000001")


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Candle:
    """One OHLCV candle. All amounts must be Decimal (constitution #11)."""

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close", "volume"):
            if not isinstance(getattr(self, name), Decimal):
                raise TypeError(f"candle field {name!r} must be Decimal")


@dataclass(frozen=True)
class StrategyConfig:
    """Rule parameters; final values come from the backtest grid (plan M11)."""

    ema_short_period: int = 20
    ema_long_period: int = 50
    rsi_period: int = 14
    rsi_buy_max: Decimal = Decimal("70")
    rsi_sell_min: Decimal = Decimal("80")
    volume_factor: Decimal = Decimal("1.2")
    volume_avg_period: int = 20

    def __post_init__(self) -> None:
        for name in ("ema_short_period", "rsi_period", "volume_avg_period"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.ema_short_period >= self.ema_long_period:
            raise ValueError("ema_short_period must be < ema_long_period")
        if self.rsi_buy_max >= self.rsi_sell_min:
            raise ValueError("rsi_buy_max must be < rsi_sell_min")
        if self.volume_factor <= 0:
            raise ValueError("volume_factor must be > 0")


@dataclass(frozen=True)
class SignalResult:
    action: SignalAction
    reason: str
    metrics: dict[str, str]


def _ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * (period - 1)
    if len(values) < period:
        result.extend([None] * len(values))
        return result
    seed = sum(values[:period]) / Decimal(period)
    result.append(seed)
    k = Decimal(2) / Decimal(period + 1)
    one_minus_k = Decimal(1) - k
    previous = seed
    for value in values[period:]:
        current = value * k + previous * one_minus_k
        result.append(current)
        previous = current
    return result


def _rsi(values: list[Decimal], period: int) -> Decimal:
    if len(values) <= period:
        raise ValueError("not enough values for RSI")
    gains = Decimal(0)
    losses = Decimal(0)
    for index in range(1, period + 1):
        change = values[index] - values[index - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    average_gain = gains / Decimal(period)
    average_loss = losses / Decimal(period)
    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = change if change > 0 else Decimal(0)
        loss = -change if change < 0 else Decimal(0)
        average_gain = (
            average_gain * Decimal(period - 1) + gain
        ) / Decimal(period)
        average_loss = (
            average_loss * Decimal(period - 1) + loss
        ) / Decimal(period)
    if average_loss == 0:
        if average_gain == 0:
            return Decimal("50")
        return _HUNDRED
    if average_gain == 0:
        return Decimal(0)
    ratio = average_gain / average_loss
    return _HUNDRED - _HUNDRED / (Decimal(1) + ratio)


def _metric(value: Decimal) -> str:
    return str(value.quantize(_METRIC_PLACES))


def evaluate(candles: list[Candle], config: StrategyConfig) -> SignalResult:
    """Return BUY/SELL/HOLD for the last candle, deterministically (RF-7)."""
    required = max(
        config.ema_long_period,
        config.rsi_period,
        config.volume_avg_period,
    ) + 1
    if len(candles) < required:
        return SignalResult(
            SignalAction.HOLD,
            "not_enough_data",
            {},
        )

    closes = [candle.close for candle in candles]
    volumes = [candle.volume for candle in candles]

    short_series = _ema(closes, config.ema_short_period)
    long_series = _ema(closes, config.ema_long_period)
    rsi = _rsi(closes, config.rsi_period)

    average_volume = sum(
        volumes[-config.volume_avg_period:]
    ) / Decimal(config.volume_avg_period)
    last_volume = volumes[-1]
    if average_volume > 0:
        volume_ratio = last_volume / average_volume
    else:
        volume_ratio = Decimal(0)

    previous_short = short_series[-2]
    last_short = short_series[-1]
    previous_long = long_series[-2]
    last_long = long_series[-1]
    if (
        last_short is None
        or last_long is None
        or previous_short is None
        or previous_long is None
    ):
        return SignalResult(SignalAction.HOLD, "not_enough_data", {})

    if last_short > last_long and previous_short <= previous_long:
        cross = "up"
    elif last_short < last_long and previous_short >= previous_long:
        cross = "down"
    else:
        cross = "none"

    metrics = {
        "ema_short": _metric(last_short),
        "ema_long": _metric(last_long),
        "rsi": _metric(rsi),
        "volume_ratio": _metric(volume_ratio),
        "cross": cross,
    }

    volume_ok = average_volume > 0 and volume_ratio >= config.volume_factor

    if cross == "up" and rsi <= config.rsi_buy_max and volume_ok:
        return SignalResult(
            SignalAction.BUY,
            "cross_up_rsi_zone_volume",
            metrics,
        )
    if cross == "down":
        return SignalResult(SignalAction.SELL, "cross_down", metrics)
    if rsi >= config.rsi_sell_min:
        return SignalResult(SignalAction.SELL, "rsi_overbought", metrics)
    return SignalResult(SignalAction.HOLD, "no_signal", metrics)

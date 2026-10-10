from datetime import datetime, timedelta
from decimal import Decimal

from app.domain.signal_engine import Candle

HOUR = timedelta(hours=1)


def compute_ema(closes: list[Decimal], period: int) -> Decimal | None:
    """EMA exponencial (alpha = 2/(n+1)), semilla = media aritmetica.

    Devuelve None si hay menos closes que ``period`` (fail-closed).
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    if len(closes) < period:
        return None

    seed = sum(closes[:period]) / Decimal(period)
    if len(closes) == period:
        return seed

    alpha = Decimal(2) / Decimal(period + 1)
    one_minus = Decimal(1) - alpha
    ema = seed
    for value in closes[period:]:
        ema = alpha * value + one_minus * ema
    return ema


def closed_hourly_candles(
    hourly_candles: list[Candle] | None,
    as_of: datetime,
) -> list[Candle]:
    """Solo velas 1h completamente cerradas antes de ``as_of`` (sin look-ahead)."""
    if not hourly_candles:
        return []
    return [
        candle
        for candle in hourly_candles
        if candle.open_time + HOUR <= as_of
    ]


def trend_allows(
    close_price: Decimal,
    hourly_candles: list[Candle] | None,
    as_of: datetime,
    period: int = 50,
) -> tuple[bool, dict]:
    """True si ``close_price`` >= EMA(``period``) de velas 1h cerradas.

    Fail-closed: con menos de ``period`` velas cerradas devuelve False.
    """
    closed = closed_hourly_candles(hourly_candles, as_of)
    ema = compute_ema([candle.close for candle in closed], period)

    metrics = {
        "trend_filter_close": str(close_price),
        "trend_filter_ema50": str(ema) if ema is not None else None,
        "trend_filter_closed_candles": len(closed),
    }

    if ema is None:
        return False, metrics

    return close_price >= ema, metrics

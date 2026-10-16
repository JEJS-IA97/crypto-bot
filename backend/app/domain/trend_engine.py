"""Daily trend rule: hold an asset only above its SMA50 and SMA200.

Pure module (no network, no database). Evaluated on CLOSED daily candles:
the signal of day t sets the position for day t+1, so the candle still in
progress is always dropped (no look-ahead).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.signal_engine import Candle, SignalAction, SignalResult

_PCT_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class TrendConfig:
    fast: int = 50
    slow: int = 200

    def __post_init__(self) -> None:
        if not 1 <= self.fast < self.slow:
            raise ValueError("trend periods must satisfy 1 <= fast < slow")


def closed_daily_candles(candles: list[Candle], now: datetime) -> list[Candle]:
    """Daily candles whose UTC day already ended (drops today's candle)."""
    return [c for c in candles if c.open_time.date() < now.date()]


def _sma(candles: list[Candle], period: int) -> Decimal:
    return sum((c.close for c in candles[-period:]), Decimal(0)) / period


def _distance_pct(close: Decimal, level: Decimal) -> str:
    return str(((close - level) / level * 100).quantize(_PCT_PLACES))


def evaluate_trend(
    candles: list[Candle],
    now: datetime,
    config: TrendConfig | None = None,
) -> SignalResult:
    """BUY = be in the asset, SELL = be in USDT, HOLD = not enough data."""
    cfg = config or TrendConfig()
    closed = closed_daily_candles(candles, now)
    if len(closed) < cfg.slow:
        return SignalResult(
            SignalAction.HOLD,
            "insufficient_daily_data",
            {"closed_candles": str(len(closed)), "required": str(cfg.slow)},
        )
    last = closed[-1]
    sma_fast = _sma(closed, cfg.fast)
    sma_slow = _sma(closed, cfg.slow)
    inside = last.close > sma_fast and last.close > sma_slow
    metrics = {
        "candle_date": last.open_time.date().isoformat(),
        "close": str(last.close),
        "sma_fast": str(sma_fast.quantize(Decimal("0.00000001"))),
        "sma_slow": str(sma_slow.quantize(Decimal("0.00000001"))),
        "dist_fast_pct": _distance_pct(last.close, sma_fast),
        "dist_slow_pct": _distance_pct(last.close, sma_slow),
    }
    if inside:
        return SignalResult(SignalAction.BUY, "trend_above_smas", metrics)
    return SignalResult(SignalAction.SELL, "trend_below_sma", metrics)

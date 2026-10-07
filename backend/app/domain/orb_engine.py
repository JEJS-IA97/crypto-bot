"""Opening range breakout signal engine (spec 001 v3, RF-7).

Pure module: no network, no database, no framework imports. Same candles,
same instant and same config always produce the same signal, verified by
tests (constitution #11: amounts are Decimal, never float).

Rules (D-12…D-14):
- The range is built from the six 5m candles opened between 9:00 and 9:30
  AM ``America/New_York`` (daylight saving included) of the current NY day.
- Between 9:30 and 10:00 AM NY, a close above the range high emits BUY;
  a close below the range low emits HOLD (Binance Spot has no shorts).
- Outside the window, with an incomplete range or without the breakout
  candle, the result is HOLD with an auditable reason (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.domain.signal_engine import Candle, SignalAction, SignalResult

NEW_YORK_TIMEZONE = "America/New_York"
CANDLE_MINUTES = 5


@dataclass(frozen=True)
class OrbConfig:
    """Rule parameters; final values come from the backtest grid (plan M11)."""

    range_start_hour: int = 9
    range_minutes: int = 30
    breakout_minutes: int = 30
    timezone_name: str = NEW_YORK_TIMEZONE

    def __post_init__(self) -> None:
        if not isinstance(self.range_start_hour, int) or isinstance(
            self.range_start_hour, bool
        ):
            raise TypeError("range_start_hour must be int")
        if not 0 <= self.range_start_hour <= 23:
            raise ValueError("range_start_hour must be in 0..23")
        if not isinstance(self.range_minutes, int) or isinstance(
            self.range_minutes, bool
        ):
            raise TypeError("range_minutes must be int")
        if self.range_minutes <= 0 or self.range_minutes % CANDLE_MINUTES != 0:
            raise ValueError(
                "range_minutes must be a positive multiple of 5"
            )
        if not isinstance(self.breakout_minutes, int) or isinstance(
            self.breakout_minutes, bool
        ):
            raise TypeError("breakout_minutes must be int")
        if self.breakout_minutes <= 0:
            raise ValueError("breakout_minutes must be > 0")
        try:
            ZoneInfo(self.timezone_name)
        except (KeyError, ValueError, OSError) as exc:
            raise ValueError(
                f"invalid timezone_name: {self.timezone_name!r}"
            ) from exc


def _as_utc_naive(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("now must be a datetime")
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_ny(value: datetime, tz: ZoneInfo) -> datetime:
    """Naive UTC instant (or candle open) → wall time in New York."""
    return value.replace(tzinfo=timezone.utc).astimezone(tz)


def _ny_window(
    now: datetime, active: OrbConfig, tz: ZoneInfo
) -> tuple[datetime, datetime, datetime, datetime]:
    """(now NY, range open, range close, window close) for ``now``."""
    now_ny = _to_ny(_as_utc_naive(now), tz)
    range_open = now_ny.replace(
        hour=active.range_start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    range_close = range_open + timedelta(minutes=active.range_minutes)
    window_close = range_close + timedelta(minutes=active.breakout_minutes)
    return now_ny, range_open, range_close, window_close


def in_orb_window(now: datetime, config: OrbConfig | None = None) -> bool:
    """True while the ORB session is live: 9:00–10:00 AM NY (RF-6).

    During this window the loop must download 5m candles for the ORB
    symbols: the range (9:00–9:30) plus the breakout evaluation (9:30–10:00).
    """
    active = config if config is not None else OrbConfig()
    tz = ZoneInfo(active.timezone_name)
    now_ny, range_open, _, window_close = _ny_window(now, active, tz)
    return range_open <= now_ny < window_close


def ny_day_start_utc(
    now: datetime, config: OrbConfig | None = None
) -> datetime:
    """Naive UTC instant of 00:00 AM New York of ``now``'s NY day (RF-27).

    Technical decisions with ``created_at >=`` this instant belong to the
    current New York day and deduplicate the daily ORB evaluation.
    """
    active = config if config is not None else OrbConfig()
    tz = ZoneInfo(active.timezone_name)
    now_ny = _to_ny(_as_utc_naive(now), tz)
    ny_midnight = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    return ny_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def ny_datetime(
    value: datetime, config: OrbConfig | None = None
) -> datetime:
    """UTC instant (naive or aware) → aware wall time in New York.

    The ORB backtest (RF-15) groups and filters candles with the very same
    conversion used by :func:`evaluate_orb`, so live and backtest sessions
    cannot drift apart.
    """
    active = config if config is not None else OrbConfig()
    tz = ZoneInfo(active.timezone_name)
    return _to_ny(_as_utc_naive(value), tz)


def session_bounds(
    day: date, config: OrbConfig | None = None
) -> tuple[datetime, datetime, datetime]:
    """(range open, range close, window close) in New York for ``day``.

    Aware wall times, daylight saving included: the backtest derives the
    per-day ORB session from this single source of truth (RF-15).
    """
    active = config if config is not None else OrbConfig()
    tz = ZoneInfo(active.timezone_name)
    range_open = datetime(
        day.year,
        day.month,
        day.day,
        active.range_start_hour,
        0,
        0,
        0,
        tzinfo=tz,
    )
    range_close = range_open + timedelta(minutes=active.range_minutes)
    window_close = range_close + timedelta(minutes=active.breakout_minutes)
    return range_open, range_close, window_close


def evaluate_orb(
    candles: list[Candle],
    now: datetime,
    config: OrbConfig | None = None,
) -> SignalResult:
    """Return BUY/HOLD for the ORB window at ``now``, deterministically (RF-7).

    ``now`` is a naive or aware datetime; candles carry naive UTC open times.
    """
    active = config if config is not None else OrbConfig()
    tz = ZoneInfo(active.timezone_name)
    now_ny, range_open, range_close, window_close = _ny_window(
        now, active, tz
    )

    if now_ny < range_close:
        return SignalResult(SignalAction.HOLD, "before_range_close", {})
    if now_ny >= window_close:
        return SignalResult(SignalAction.HOLD, "breakout_window_closed", {})

    expected_opens = [
        range_open + timedelta(minutes=CANDLE_MINUTES * index)
        for index in range(active.range_minutes // CANDLE_MINUTES)
    ]
    by_open = {_to_ny(candle.open_time, tz): candle for candle in candles}

    range_candles = [by_open[moment] for moment in expected_opens if moment in by_open]
    if len(range_candles) != len(expected_opens):
        return SignalResult(
            SignalAction.HOLD,
            "range_incomplete",
            {
                "expected_candles": str(len(expected_opens)),
                "found_candles": str(len(range_candles)),
            },
        )

    range_high = max(candle.high for candle in range_candles)
    range_low = min(candle.low for candle in range_candles)
    range_metrics = {
        "range_high": str(range_high),
        "range_low": str(range_low),
        "range_size": str(range_high - range_low),
    }

    breakout_candidates = [
        candle
        for open_ny, candle in (
            (_to_ny(candle.open_time, tz), candle) for candle in candles
        )
        if range_close <= open_ny < window_close and open_ny <= now_ny
    ]
    if not breakout_candidates:
        return SignalResult(
            SignalAction.HOLD,
            "breakout_candle_missing",
            dict(range_metrics),
        )

    breakout = max(breakout_candidates, key=lambda candle: candle.open_time)
    metrics = dict(range_metrics)
    metrics["breakout_price"] = str(breakout.close)

    if breakout.close > range_high:
        return SignalResult(SignalAction.BUY, "orb_breakout_up", metrics)
    if breakout.close < range_low:
        return SignalResult(SignalAction.HOLD, "breakdown_no_short", metrics)
    return SignalResult(SignalAction.HOLD, "no_breakout", metrics)

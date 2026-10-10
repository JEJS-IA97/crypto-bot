"""Fixtures de klines 5m para la spec 011 (walk-forward ORB).

Genera series sintéticas deterministas con la sesión ORB de Nueva York
(9:00–9:30 rango + rompimiento 9:30–10:00) poblada, en el mismo formato
del JSONL de ``collect_klines.py`` (Decimal como texto, open_time en ms).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.signal_engine import Candle

_NY_TZ = ZoneInfo("America/New_York")


def orb_candle(
    day: date,
    hour: int,
    minute: int,
    open_: str,
    high: str,
    low: str,
    close: str,
) -> Candle:
    open_time = (
        datetime(day.year, day.month, day.day, hour, minute, tzinfo=_NY_TZ)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    return Candle(
        open_time=open_time,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("100"),
    )


def range_candles(day: date) -> list[Candle]:
    """Rango 9:00–9:25 AM NY: alto 99.5, bajo 98.5."""
    return [
        orb_candle(day, 9, minute, "99", "99.5", "98.5", "99")
        for minute in (0, 5, 10, 15, 20, 25)
    ]


def breakout_day(day: date, *, pump: bool = False) -> list[Candle]:
    """Día con sesión ORB completa y entrada en largo.

    ``pump=True`` produce un cierre de rompimiento gigante (trampa de
    look-ahead para el test de selección de parámetros).
    """
    candles = range_candles(day)
    if pump:
        candles.append(orb_candle(day, 9, 30, "99", "500", "98.9", "499"))
        candles.append(orb_candle(day, 9, 35, "499", "500", "498", "499"))
        return candles
    candles.append(orb_candle(day, 9, 30, "99", "100.5", "98.9", "100"))
    candles.append(orb_candle(day, 9, 35, "100", "103", "99.4", "102"))
    return candles


def ranging_win_day(day: date) -> list[Candle]:
    """Día que favorece TP=1: toca ~+1 % y cierra plano (no llega a TP=1.5)."""
    candles = range_candles(day)
    candles.append(orb_candle(day, 9, 30, "99", "100.5", "98.9", "100"))
    candles.append(orb_candle(day, 9, 35, "100", "101.4", "99.4", "101.2"))
    for minute in (40, 45, 50):
        candles.append(orb_candle(day, 9, minute, "101.2", "101.3", "99.7", "99.8"))
    candles.append(orb_candle(day, 9, 55, "99.8", "99.9", "99.6", "99.8"))
    return candles


def sl_loss_day(day: date) -> list[Candle]:
    """Día perdedor: rompe al alza y tagged de SL (~-1 %) en la 9:35."""
    candles = range_candles(day)
    candles.append(orb_candle(day, 9, 30, "99", "100.5", "98.9", "100"))
    candles.append(orb_candle(day, 9, 35, "100", "100.4", "98.95", "99.2"))
    for minute in (40, 45, 50, 55):
        candles.append(orb_candle(day, 9, minute, "99.2", "99.4", "98.9", "99.2"))
    return candles


def walk_forward_dataset(
    days: int,
    start: date,
    *,
    pump_days: tuple[date, ...] = (),
) -> list[Candle]:
    """Serie de ``days`` días calendario consecutivos desde ``start``."""
    candles: list[Candle] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        candles += breakout_day(day, pump=day in pump_days)
    return candles


def write_klines_jsonl(path: Path, candles: list[Candle]) -> None:
    """Escribe el JSONL en el formato de ``collect_klines.py``."""
    with path.open("w", encoding="utf-8") as handle:
        for candle in candles:
            payload = {
                "open_time": int(
                    candle.open_time.replace(tzinfo=timezone.utc).timestamp()
                    * 1000
                ),
                "open": str(candle.open),
                "high": str(candle.high),
                "low": str(candle.low),
                "close": str(candle.close),
                "volume": str(candle.volume),
            }
            handle.write(json.dumps(payload) + "\n")

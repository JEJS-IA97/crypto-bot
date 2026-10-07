"""Dominio ORB (spec 001 v3, RF-7).

Rango de apertura 9:00–9:30 AM `America/New_York` sobre velas 5m; ventana
de rompimiento 9:30–10:00 AM NY. Módulo puro: sin red, sin BD, sin framework.
"""

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.orb_engine import (
    OrbConfig,
    evaluate_orb,
    in_orb_window,
    ny_datetime,
    ny_day_start_utc,
    session_bounds,
)
from app.domain.signal_engine import Candle, SignalAction, SignalResult

WINTER_DAY = date(2026, 1, 15)  # EST (UTC-5)
SUMMER_DAY = date(2026, 7, 15)  # EDT (UTC-4)

# Rango: máximo 105, mínimo 95, tamaño 10.
RANGE_SPECS = [
    (9, 0, "100", "102", "99", "101"),
    (9, 5, "101", "103", "100", "102"),
    (9, 10, "102", "105", "101", "103"),
    (9, 15, "103", "104", "95", "100"),
    (9, 20, "100", "101", "97", "99"),
    (9, 25, "99", "100", "96", "98"),
]
BREAKOUT_UP_SPEC = (9, 30, "98", "107", "97", "106")
BREAKOUT_DOWN_SPEC = (9, 30, "98", "99", "94", "94")
NO_BREAKOUT_SPEC = (9, 30, "98", "103", "97", "102")


def _ny(day: date, hour: int, minute: int) -> datetime:
    return datetime(
        day.year, day.month, day.day, hour, minute,
        tzinfo=ZoneInfo("America/New_York"),
    )


def _to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _now_ny(day: date, hour: int, minute: int, second: int = 0) -> datetime:
    """Instante en UTC naive equivalente a la hora dada en Nueva York."""
    moment = _ny(day, hour, minute).replace(second=second)
    return _to_utc_naive(moment)


def _build(day: date, specs) -> list[Candle]:
    candles = []
    for hour, minute, open_, high, low, close in specs:
        candles.append(
            Candle(
                open_time=_to_utc_naive(_ny(day, hour, minute)),
                open=Decimal(open_),
                high=Decimal(high),
                low=Decimal(low),
                close=Decimal(close),
                volume=Decimal("100"),
            )
        )
    return candles


def _session(
    day: date,
    breakout_spec=BREAKOUT_UP_SPEC,
    extra_specs=(),
) -> list[Candle]:
    return _build(day, list(RANGE_SPECS) + [breakout_spec] + list(extra_specs))


class OrbConfigTests(unittest.TestCase):
    def test_invalid_timezone_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OrbConfig(timezone_name="Not/AZone")

    def test_invalid_window_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OrbConfig(range_minutes=0)
        with self.assertRaises(ValueError):
            OrbConfig(range_minutes=7)  # no alineado a velas de 5m
        with self.assertRaises(ValueError):
            OrbConfig(breakout_minutes=0)
        with self.assertRaises(ValueError):
            OrbConfig(range_start_hour=24)

    def test_default_config_is_new_york(self) -> None:
        config = OrbConfig()
        self.assertEqual(config.timezone_name, "America/New_York")
        self.assertEqual(config.range_start_hour, 9)
        self.assertEqual(config.range_minutes, 30)
        self.assertEqual(config.breakout_minutes, 30)


class OrbBreakoutTests(unittest.TestCase):
    def test_buy_on_breakout_above_range_high(self) -> None:
        result = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 9, 32)
        )
        self.assertIsInstance(result, SignalResult)
        self.assertEqual(result.action, SignalAction.BUY)
        self.assertEqual(result.reason, "orb_breakout_up")
        self.assertEqual(result.metrics["range_high"], "105")
        self.assertEqual(result.metrics["range_low"], "95")
        self.assertEqual(result.metrics["range_size"], "10")
        self.assertEqual(result.metrics["breakout_price"], "106")

    def test_hold_without_breakout(self) -> None:
        result = evaluate_orb(
            _session(WINTER_DAY, NO_BREAKOUT_SPEC),
            _now_ny(WINTER_DAY, 9, 32),
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "no_breakout")
        self.assertEqual(result.metrics["breakout_price"], "102")

    def test_hold_on_breakdown_never_sell(self) -> None:
        result = evaluate_orb(
            _session(WINTER_DAY, BREAKOUT_DOWN_SPEC),
            _now_ny(WINTER_DAY, 9, 32),
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "breakdown_no_short")
        self.assertNotEqual(result.action, SignalAction.SELL)

    def test_breakout_on_later_candle_inside_window(self) -> None:
        # La vela de las 9:30 no rompió; la de las 9:35 sí.
        result = evaluate_orb(
            _session(
                WINTER_DAY,
                breakout_spec=NO_BREAKOUT_SPEC,
                extra_specs=[(9, 35, "102", "108", "101", "106")],
            ),
            _now_ny(WINTER_DAY, 9, 37),
        )
        self.assertEqual(result.action, SignalAction.BUY)
        self.assertEqual(result.reason, "orb_breakout_up")
        self.assertEqual(result.metrics["breakout_price"], "106")

    def test_missing_breakout_candle_fails_closed(self) -> None:
        result = evaluate_orb(
            _build(WINTER_DAY, RANGE_SPECS),
            _now_ny(WINTER_DAY, 9, 31),
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "breakout_candle_missing")

    def test_candle_opened_after_now_is_ignored(self) -> None:
        future = (9, 40, "98", "200", "97", "199")
        result = evaluate_orb(
            _session(WINTER_DAY, NO_BREAKOUT_SPEC, extra_specs=[future]),
            _now_ny(WINTER_DAY, 9, 32),
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "no_breakout")

    def test_previous_day_session_is_ignored(self) -> None:
        yesterday = date(2026, 1, 14)
        candles = _build(yesterday, RANGE_SPECS + [BREAKOUT_UP_SPEC])
        candles += _build(WINTER_DAY, RANGE_SPECS)
        result = evaluate_orb(candles, _now_ny(WINTER_DAY, 9, 32))
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "breakout_candle_missing")


class OrbWindowTests(unittest.TestCase):
    def test_hold_before_range_close(self) -> None:
        result = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 9, 15)
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "before_range_close")
        self.assertEqual(result.metrics, {})

    def test_hold_when_window_closed(self) -> None:
        result = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 10, 0)
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "breakout_window_closed")

        later = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 10, 5)
        )
        self.assertEqual(later.reason, "breakout_window_closed")


class OrbRangeTests(unittest.TestCase):
    def test_hold_when_range_candle_missing(self) -> None:
        incomplete = [c for c in RANGE_SPECS if c[1] != 15]
        result = evaluate_orb(
            _build(WINTER_DAY, incomplete + [BREAKOUT_UP_SPEC]),
            _now_ny(WINTER_DAY, 9, 32),
        )
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "range_incomplete")
        self.assertEqual(result.metrics["expected_candles"], "6")
        self.assertEqual(result.metrics["found_candles"], "5")

    def test_hold_with_no_candles(self) -> None:
        result = evaluate_orb([], _now_ny(WINTER_DAY, 9, 32))
        self.assertEqual(result.action, SignalAction.HOLD)
        self.assertEqual(result.reason, "range_incomplete")


class OrbDstTests(unittest.TestCase):
    def test_same_logic_in_summer_time(self) -> None:
        # EDT (UTC-4): 9:32 AM NY = 13:32 UTC, una hora que en invierno
        # sería 14:32 UTC. Misma señal con la misma estructura de velas.
        winter = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 9, 32)
        )
        summer = evaluate_orb(
            _session(SUMMER_DAY), _now_ny(SUMMER_DAY, 9, 32)
        )
        self.assertEqual(winter.action, SignalAction.BUY)
        self.assertEqual(summer.action, SignalAction.BUY)
        self.assertEqual(winter.metrics, summer.metrics)

        winter_close = evaluate_orb(
            _session(WINTER_DAY), _now_ny(WINTER_DAY, 10, 0)
        )
        summer_close = evaluate_orb(
            _session(SUMMER_DAY), _now_ny(SUMMER_DAY, 10, 0)
        )
        self.assertEqual(winter_close.reason, "breakout_window_closed")
        self.assertEqual(summer_close.reason, "breakout_window_closed")


class DownloadWindowTests(unittest.TestCase):
    """RF-6: los 5m se descargan de 9:00 a 10:00 AM NY (rango + rompimiento)."""

    def test_window_covers_range_and_breakout(self) -> None:
        self.assertTrue(in_orb_window(_now_ny(WINTER_DAY, 9, 0)))
        self.assertTrue(in_orb_window(_now_ny(WINTER_DAY, 9, 15)))
        self.assertTrue(in_orb_window(_now_ny(WINTER_DAY, 9, 30)))
        self.assertTrue(in_orb_window(_now_ny(WINTER_DAY, 9, 59)))

    def test_outside_window(self) -> None:
        self.assertFalse(in_orb_window(_now_ny(WINTER_DAY, 8, 59)))
        self.assertFalse(in_orb_window(_now_ny(WINTER_DAY, 10, 0)))
        self.assertFalse(in_orb_window(_now_ny(WINTER_DAY, 12, 0)))

    def test_window_in_summer_time(self) -> None:
        self.assertTrue(in_orb_window(_now_ny(SUMMER_DAY, 9, 0)))
        self.assertFalse(in_orb_window(_now_ny(SUMMER_DAY, 10, 0)))

    def test_custom_config_shifts_window(self) -> None:
        config = OrbConfig(
            range_start_hour=8, range_minutes=15, breakout_minutes=15
        )
        self.assertTrue(in_orb_window(_now_ny(WINTER_DAY, 8, 5), config))
        self.assertFalse(in_orb_window(_now_ny(WINTER_DAY, 9, 0), config))


class NyDayStartTests(unittest.TestCase):
    """RF-27: el límite del dedup es la medianoche de Nueva York."""

    def test_summer_day_starts_at_four_utc(self) -> None:
        start = ny_day_start_utc(_now_ny(SUMMER_DAY, 9, 32))
        self.assertEqual(start, datetime(2026, 7, 15, 4, 0))
        self.assertIsNone(start.tzinfo)

    def test_winter_day_starts_at_five_utc(self) -> None:
        start = ny_day_start_utc(_now_ny(WINTER_DAY, 9, 32))
        self.assertEqual(start, datetime(2026, 1, 15, 5, 0))

    def test_same_start_throughout_the_day(self) -> None:
        early = ny_day_start_utc(_now_ny(WINTER_DAY, 0, 30))
        late = ny_day_start_utc(_now_ny(WINTER_DAY, 23, 30))
        self.assertEqual(early, late)
        self.assertEqual(early, datetime(2026, 1, 15, 5, 0))

    def test_aware_now_matches_naive_now(self) -> None:
        aware = ny_day_start_utc(_ny(WINTER_DAY, 9, 32))
        naive = ny_day_start_utc(_now_ny(WINTER_DAY, 9, 32))
        self.assertEqual(aware, naive)


class SessionBoundsTests(unittest.TestCase):
    """RF-15: el backtest reutiliza la ventana de Nueva York del dominio."""

    def test_winter_bounds(self) -> None:
        range_open, range_close, window_close = session_bounds(WINTER_DAY)
        self.assertEqual(range_open, _ny(WINTER_DAY, 9, 0))
        self.assertEqual(range_close, _ny(WINTER_DAY, 9, 30))
        self.assertEqual(window_close, _ny(WINTER_DAY, 10, 0))

    def test_summer_bounds(self) -> None:
        range_open, range_close, window_close = session_bounds(SUMMER_DAY)
        self.assertEqual(range_open, _ny(SUMMER_DAY, 9, 0))
        self.assertEqual(window_close, _ny(SUMMER_DAY, 10, 0))

    def test_custom_config_bounds(self) -> None:
        config = OrbConfig(
            range_start_hour=8, range_minutes=15, breakout_minutes=15
        )
        range_open, range_close, window_close = session_bounds(
            WINTER_DAY, config
        )
        self.assertEqual(range_open, _ny(WINTER_DAY, 8, 0))
        self.assertEqual(range_close, _ny(WINTER_DAY, 8, 15))
        self.assertEqual(window_close, _ny(WINTER_DAY, 8, 30))


class NyDatetimeTests(unittest.TestCase):
    def test_naive_utc_converts_to_new_york(self) -> None:
        # 14:32 UTC en invierno = 9:32 AM NY (EST).
        result = ny_datetime(datetime(2026, 1, 15, 14, 32))
        self.assertEqual(result, _ny(WINTER_DAY, 9, 32))

    def test_aware_utc_matches_naive(self) -> None:
        naive = ny_datetime(datetime(2026, 7, 15, 13, 32))
        aware = ny_datetime(
            datetime(2026, 7, 15, 13, 32, tzinfo=timezone.utc)
        )
        self.assertEqual(naive, aware)
        self.assertEqual(naive, _ny(SUMMER_DAY, 9, 32))


class DeterminismTests(unittest.TestCase):
    def test_deterministic_signal(self) -> None:
        candles = _session(WINTER_DAY)
        now = _now_ny(WINTER_DAY, 9, 32)
        results = [evaluate_orb(candles, now) for _ in range(3)]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(results[0].metrics, results[2].metrics)

    def test_aware_now_matches_naive_now(self) -> None:
        candles = _session(WINTER_DAY)
        naive = evaluate_orb(candles, _now_ny(WINTER_DAY, 9, 32))
        aware = evaluate_orb(
            candles, _ny(WINTER_DAY, 9, 32)
        )
        self.assertEqual(naive, aware)

    def test_non_datetime_now_rejected(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_orb(_session(WINTER_DAY), "2026-01-15 14:32")


class PurityTests(unittest.TestCase):
    def test_orb_engine_module_has_no_io_dependencies(self) -> None:
        source = Path("app/domain/orb_engine.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("httpx", "sqlalchemy", "requests", "fastapi"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

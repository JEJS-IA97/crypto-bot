import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.domain.signal_engine import (
    Candle,
    SignalAction,
    StrategyConfig as SignalConfig,
    evaluate,
)
from app.services.strategy_lab_service import (
    KlineBacktestConfig,
    OrbBacktestConfig,
    Snapshot,
    StrategyConfig,
    backtest,
    backtest_candles,
    backtest_orb,
    grid_search,
    grid_search_candles,
    grid_search_orb,
    load_klines_jsonl,
    split_candles,
    split_time_series,
)


def quote(exchange: str, ask: str, bid: str) -> dict:
    return {
        "exchange": exchange,
        "symbol": "BTCUSDT",
        "quote_currency": "USDT",
        "status": "ok",
        "ask_price": ask,
        "bid_price": bid,
        "ask_quantity": "1",
        "bid_quantity": "1",
        "last_price": bid,
        "volume_24h": "100000",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


class StrategyLabTest(unittest.TestCase):
    def make_snapshots(self) -> list[Snapshot]:
        base = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        return [
            Snapshot(
                timestamp=base,
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=2),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=4),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
        ]

    def make_adverse_snapshots(self) -> list[Snapshot]:
        base = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        return [
            Snapshot(
                timestamp=base,
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "100", "99.9"),
                    quote("bybit", "100.2", "101"),
                ],
            ),
            Snapshot(
                timestamp=base + timedelta(seconds=2),
                symbol="BTCUSDT",
                quotes=[
                    quote("binance", "105", "104"),
                    quote("bybit", "105.2", "104.1"),
                ],
            ),
        ]

    def test_backtest_uses_same_exchanges_after_latency(self) -> None:
        result = backtest(
            self.make_adverse_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
            ),
        )

        self.assertEqual(result.executable_candidates, 1)
        self.assertEqual(result.survived_samples, 0)
        self.assertLess(result.total_proxy_profit_usd, Decimal("0"))

    def test_max_drawdown_tracks_losses(self) -> None:
        result = backtest(
            self.make_adverse_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
            ),
        )

        self.assertGreater(result.max_drawdown_usd, Decimal("0"))

    def test_backtest_produces_positive_proxy_result(self) -> None:
        result = backtest(
            self.make_snapshots(),
            StrategyConfig(
                capital_usd=Decimal("5"),
                min_profit_usd=Decimal("0.01"),
                min_profit_percent=Decimal("0.01"),
                taker_slippage_percent=Decimal("0"),
                assumed_latency_seconds=2,
                cooldown_seconds=0,
            ),
        )

        self.assertGreaterEqual(result.snapshots, 3)
        self.assertGreater(result.survived_samples, 0)
        self.assertGreater(result.total_proxy_profit_usd, Decimal("0"))

    def test_grid_search_returns_ranked_results(self) -> None:
        snapshots = self.make_snapshots()
        configs = [
            StrategyConfig(min_profit_percent=Decimal("0.01")),
            StrategyConfig(min_profit_percent=Decimal("0.50")),
        ]
        results = grid_search(snapshots, configs)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(
            results[0].total_proxy_profit_usd,
            results[1].total_proxy_profit_usd,
        )

    def test_time_split_is_chronological(self) -> None:
        train, validation, test = split_time_series(self.make_snapshots())
        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertTrue(test)
        self.assertLessEqual(train[-1].timestamp, validation[0].timestamp)
        self.assertLessEqual(validation[-1].timestamp, test[0].timestamp)

    def test_time_split_keeps_small_dataset_partitions_non_empty(self) -> None:
        train, validation, test = split_time_series(self.make_snapshots())
        self.assertEqual(len(train), 1)
        self.assertEqual(len(validation), 1)
        self.assertEqual(len(test), 1)


def _build_series() -> list[Candle]:
    """Serie determinista con un BUY y un SELL del motor de señales.

    Fase D (bajista) → fase U (reversión alcista, cruce alcista con volumen
    disparado → BUY) → fase R (declive, cruce bajista → SELL). Si el motor
    deja de emitir las señales, el helper falla y el test avisa.
    """
    candles: list[Candle] = []
    start = datetime(2026, 1, 1)
    close = Decimal("100")
    index = 0
    strategy = SignalConfig()

    def add(step: Decimal, volume: Decimal = Decimal("100")) -> None:
        nonlocal close, index
        previous = close
        close = close + step
        candles.append(
            Candle(
                open_time=start + timedelta(minutes=15 * index),
                open=previous,
                high=max(previous, close) + Decimal("0.5"),
                low=min(previous, close) - Decimal("0.5"),
                close=close,
                volume=volume,
            )
        )
        index += 1

    # Fase D: tendencia bajista con zigzag (semilla de pérdidas para el RSI).
    for k in range(60):
        add(Decimal("-0.8") if k % 3 != 2 else Decimal("0.3"))

    # Fase U: reversión alcista hasta el primer BUY.
    buy_index = None
    for _ in range(150):
        add(Decimal("-0.5") if index % 3 == 2 else Decimal("0.7"))
        result = evaluate(candles, strategy)
        if result.metrics.get("cross") == "up":
            last = candles[-1]
            candles[-1] = Candle(
                open_time=last.open_time,
                open=last.open,
                high=last.high,
                low=last.low,
                close=last.close,
                volume=Decimal("500"),
            )
            if evaluate(candles, strategy).action == SignalAction.BUY:
                buy_index = len(candles) - 1
                break
    if buy_index is None:
        raise AssertionError("la serie no produjo ninguna señal BUY")

    # La tendencia sube más (la posición renta)…
    for _ in range(40):
        add(Decimal("-0.5") if index % 3 == 2 else Decimal("0.7"))

    # Fase R: declive hasta el SELL.
    sell_index = None
    for _ in range(120):
        add(Decimal("0.3") if index % 3 == 2 else Decimal("-0.6"))
        if evaluate(candles, strategy).action == SignalAction.SELL:
            sell_index = len(candles) - 1
            break
    if sell_index is None:
        raise AssertionError("la serie no produjo ninguna señal SELL")

    for _ in range(5):
        add(Decimal("0"))
    return candles


class KlineBacktestTest(unittest.TestCase):
    """Backtest sobre klines: comisiones, slippage, grid y splits (RF-15)."""

    def test_fees_and_slippage(self) -> None:
        candles = _build_series()
        capital = Decimal("20")

        free = backtest_candles(
            candles,
            SignalConfig(),
            KlineBacktestConfig(
                fee_rate=Decimal("0"),
                slippage_pct=Decimal("0"),
                capital_usd=capital,
            ),
        )
        charged = backtest_candles(
            candles,
            SignalConfig(),
            KlineBacktestConfig(
                fee_rate=Decimal("0.001"),
                slippage_pct=Decimal("0"),
                capital_usd=capital,
            ),
        )
        slipped = backtest_candles(
            candles,
            SignalConfig(),
            KlineBacktestConfig(
                fee_rate=Decimal("0.001"),
                slippage_pct=Decimal("0.5"),
                capital_usd=capital,
            ),
        )

        self.assertGreater(free.trades, 0)
        self.assertEqual(free.fees_usd, Decimal("0"))
        self.assertGreater(charged.fees_usd, Decimal("0"))

        # Sin slippage las entradas/salidas son idénticas: la diferencia
        # entre ambos PnL es exactamente la comisión cobrada (0.1%×2).
        difference = free.net_pnl_usd - charged.net_pnl_usd
        self.assertLess(
            abs(difference - charged.fees_usd),
            Decimal("0.00001"),
        )
        self.assertLess(charged.net_pnl_usd, free.net_pnl_usd)

        # Slippage configurable: siempre empeora el resultado neto.
        self.assertLess(slipped.net_pnl_usd, charged.net_pnl_usd)

        # Rentabilidad neta y drawdown coherentes con la operación ganadora.
        self.assertGreater(charged.return_pct, Decimal("0"))
        self.assertGreaterEqual(charged.max_drawdown_pct, Decimal("0"))
        self.assertGreaterEqual(charged.win_rate_pct, Decimal("0"))
        self.assertEqual(
            charged.strategy["ema_short_period"],
            SignalConfig().ema_short_period,
        )

    def test_grid_ranking(self) -> None:
        candles = _build_series()
        never_buys = SignalConfig(rsi_buy_max=Decimal("10"))
        configs = [
            SignalConfig(),
            SignalConfig(volume_factor=Decimal("1.0")),
            never_buys,
        ]

        results = grid_search_candles(candles, configs)

        self.assertEqual(len(results), 3)
        nets = [result.net_pnl_usd for result in results]
        self.assertEqual(nets, sorted(nets, reverse=True))

        # La configuración que nunca compra no opera ni gana ni pierde.
        dead = [
            result
            for result in results
            if result.strategy["rsi_buy_max"] == Decimal("10")
        ][0]
        self.assertEqual(dead.trades, 0)
        self.assertEqual(dead.net_pnl_usd, Decimal("0"))

        # La mejor configuración de la rejilla sí llegó a operar.
        self.assertGreater(results[0].trades, 0)

    def test_candle_split_is_chronological(self) -> None:
        candles = _build_series()
        train, validation, test = split_candles(candles)

        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertTrue(test)
        self.assertEqual(
            len(train) + len(validation) + len(test),
            len(candles),
        )
        self.assertLessEqual(train[-1].open_time, validation[0].open_time)
        self.assertLessEqual(
            validation[-1].open_time,
            test[0].open_time,
        )

    def test_load_klines_jsonl(self) -> None:
        # Formato del recolector T14: open_time en ms e importes como texto.
        tmpdir = tempfile.mkdtemp(prefix="klines-load-")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        path = Path(tmpdir) / "BTCUSDT.jsonl"
        rows = [
            {
                "open_time": 1_700_000_900_000,
                "open": "100.1",
                "high": "101.0",
                "low": "99.5",
                "close": "100.5",
                "volume": "10.25",
                "close_time": 1_700_001_799_999,
                "quote_volume": "1025.5",
                "trades": 42,
            },
            {
                "open_time": 1_700_000_000_000,
                "open": "99.0",
                "high": "100.0",
                "low": "98.0",
                "close": "99.5",
                "volume": "8.5",
                "close_time": 1_700_000_899_999,
                "quote_volume": "845.75",
                "trades": 30,
            },
        ]
        path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )

        candles = load_klines_jsonl(path)

        self.assertEqual(len(candles), 2)
        # Orden cronológico aunque el fichero venga desordenado.
        self.assertEqual(
            candles[0].open_time,
            datetime.fromtimestamp(
                1_700_000_000_000 / 1000, tz=timezone.utc
            ).replace(tzinfo=None),
        )
        self.assertIsInstance(candles[0].close, Decimal)
        self.assertEqual(candles[1].close, Decimal("100.5"))
        self.assertEqual(candles[1].volume, Decimal("10.25"))
        self.assertEqual(candles[1].open, Decimal("100.1"))


_NY_TZ = ZoneInfo("America/New_York")


def _orb_candle(
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


def _range_candles(day: date, skip_minute: int | None = None) -> list[Candle]:
    """Rango 9:00–9:25 AM NY: alto 99.5, bajo 98.5."""
    candles = []
    for minute in (0, 5, 10, 15, 20, 25):
        if minute == skip_minute:
            continue
        candles.append(_orb_candle(day, 9, minute, "99", "99.5", "98.5", "99"))
    return candles


def _breakout(
    day: date,
    close: str = "100",
    high: str = "100.5",
    low: str = "98.9",
) -> Candle:
    return _orb_candle(day, 9, 30, "99", high, low, close)


def _orb_series() -> list[Candle]:
    """Serie ORB determinista: 3 operaciones (TP, SL, cierre de ventana).

    - Día A (10-05): TP 102 en la vela 9:35 (+0.4 sin costes); velas
      posteriores con cierre > rango (sólo 1 entrada por día, RF-27).
    - Día B (10-06): SL 98 en la 9:35 (−0.4 sin costes).
    - Día C (10-07): sin TP/SL → cierre forzado al cerrar la ventana
      en 100.5 (+0.1).
    - Día D (10-08): sin rompimiento + vela de 10:05 fuera de ventana.
    - Día E (10-09): rango incompleto → el día se ignora (fail-closed).
    """
    day_a, day_b, day_c, day_d, day_e = (
        date(2026, 10, 5),
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
        date(2026, 10, 9),
    )
    candles: list[Candle] = []

    candles += _range_candles(day_a)
    candles.append(_breakout(day_a))
    candles.append(_orb_candle(day_a, 9, 35, "100", "103", "99.4", "102"))
    candles.append(_orb_candle(day_a, 9, 40, "102", "103", "101", "101"))
    candles.append(_orb_candle(day_a, 9, 55, "101", "101.5", "100.5", "101"))

    candles += _range_candles(day_b)
    candles.append(_breakout(day_b))
    candles.append(_orb_candle(day_b, 9, 35, "99.5", "99.9", "97", "98.5"))
    candles.append(_orb_candle(day_b, 9, 40, "98.5", "101", "98", "101"))

    candles += _range_candles(day_c)
    candles.append(_breakout(day_c))
    for minute in (35, 40, 45, 50):
        candles.append(_orb_candle(day_c, 9, minute, "100", "101", "99", "100"))
    candles.append(_orb_candle(day_c, 9, 55, "100", "101", "99", "100.5"))

    candles += _range_candles(day_d)
    candles.append(_breakout(day_d, close="99", high="99.4", low="98.9"))
    candles.append(_orb_candle(day_d, 9, 35, "99", "99.4", "98.6", "99"))
    candles.append(_orb_candle(day_d, 10, 5, "99", "200", "98", "200"))

    candles += _range_candles(day_e, skip_minute=15)
    candles.append(_breakout(day_e))
    candles.append(_orb_candle(day_e, 9, 35, "100", "103", "99", "102"))

    return candles


class OrbKlineBacktestTest(unittest.TestCase):
    """Backtest ORB: TP/SL 1:1, una sesión al día y costes (RF-15, D-11)."""

    def test_take_profit_stop_loss_and_window_exit(self) -> None:
        series = _orb_series()
        result = backtest_orb(
            series,
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
        )

        self.assertEqual(result.trades, 3)
        self.assertEqual(result.winning_trades, 2)
        self.assertEqual(result.candles, len(series))
        self.assertEqual(result.net_pnl_usd, Decimal("0.1"))
        self.assertEqual(result.return_pct, Decimal("0.5"))
        self.assertEqual(result.max_drawdown_usd, Decimal("0.4"))
        self.assertEqual(result.max_drawdown_pct, Decimal("1.96"))
        self.assertEqual(result.win_rate_pct, Decimal("66.67"))
        self.assertEqual(result.fees_usd, Decimal("0"))

    def test_fees_and_slippage(self) -> None:
        series = _orb_series()
        charged = backtest_orb(
            series,
            OrbBacktestConfig(
                fee_rate=Decimal("0.001"), slippage_pct=Decimal("0")
            ),
        )
        slipped = backtest_orb(
            series,
            OrbBacktestConfig(
                fee_rate=Decimal("0.001"), slippage_pct=Decimal("0.5")
            ),
        )

        self.assertEqual(charged.trades, 3)
        self.assertEqual(charged.net_pnl_usd, Decimal("-0.0201"))
        self.assertEqual(charged.fees_usd, Decimal("0.1201"))
        # El slippage configurable siempre empeora el neto.
        self.assertLess(slipped.net_pnl_usd, charged.net_pnl_usd)

    def test_forced_window_exit_closes_open_position(self) -> None:
        day = date(2026, 10, 7)
        candles = _range_candles(day) + [_breakout(day)]
        for minute in (35, 40, 45, 50, 55):
            close = "100.5" if minute == 55 else "100"
            candles.append(
                _orb_candle(day, 9, minute, "100", "101", "99", close)
            )

        result = backtest_orb(
            candles,
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
        )

        self.assertEqual(result.trades, 1)
        self.assertEqual(result.winning_trades, 1)
        self.assertEqual(result.net_pnl_usd, Decimal("0.1"))

    def test_one_entry_per_day_only(self) -> None:
        # El día A tiene tres velas con cierre > rango tras salir: sólo
        # cuenta la primera entrada (RF-27: una operación al día).
        day = date(2026, 10, 5)
        candles = _range_candles(day) + [_breakout(day)]
        candles.append(_orb_candle(day, 9, 35, "100", "103", "99.4", "102"))
        candles.append(_orb_candle(day, 9, 40, "102", "103", "101", "101"))
        candles.append(_orb_candle(day, 9, 45, "101", "104", "100", "103"))
        candles.append(_orb_candle(day, 9, 55, "103", "104", "102", "103"))

        result = backtest_orb(
            candles,
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
        )

        self.assertEqual(result.trades, 1)

    def test_incomplete_range_skips_the_day(self) -> None:
        day = date(2026, 10, 9)
        candles = _range_candles(day, skip_minute=15)
        candles.append(_breakout(day))
        candles.append(_orb_candle(day, 9, 35, "100", "103", "99", "102"))

        result = backtest_orb(candles)

        self.assertEqual(result.trades, 0)
        self.assertEqual(result.net_pnl_usd, Decimal("0"))

    def test_candle_after_window_close_is_ignored(self) -> None:
        day = date(2026, 10, 8)
        candles = _range_candles(day)
        candles.append(_breakout(day, close="99", high="99.4", low="98.9"))
        candles.append(_orb_candle(day, 10, 5, "99", "200", "98", "200"))

        result = backtest_orb(candles)

        self.assertEqual(result.trades, 0)

    def test_stop_checked_before_target_when_both_touched(self) -> None:
        day = date(2026, 10, 12)
        candles = _range_candles(day) + [_breakout(day)]
        # La misma vela toca el TP (103) y el SL (97): manda el SL
        # (conservador).
        candles.append(_orb_candle(day, 9, 35, "100", "103", "97", "100"))

        result = backtest_orb(
            candles,
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
        )

        self.assertEqual(result.trades, 1)
        self.assertEqual(result.winning_trades, 0)
        self.assertEqual(result.net_pnl_usd, Decimal("-0.4"))

    def test_winter_session_uses_est_offset(self) -> None:
        day = date(2026, 1, 15)
        candles = _range_candles(day) + [_breakout(day)]
        candles.append(_orb_candle(day, 9, 35, "100", "103", "99.4", "102"))

        result = backtest_orb(
            candles,
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
        )

        self.assertEqual(result.trades, 1)
        self.assertEqual(result.net_pnl_usd, Decimal("0.4"))

    def test_default_config_is_one_to_one_reward(self) -> None:
        result = backtest_orb(_orb_series())

        self.assertEqual(result.strategy["stop_loss_pct"], Decimal("2.0"))
        self.assertEqual(result.strategy["take_profit_pct"], Decimal("2.0"))
        self.assertEqual(result.strategy["fee_rate"], Decimal("0.001"))
        self.assertEqual(result.strategy["orb"]["range_start_hour"], 9)

    def test_invalid_config_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OrbBacktestConfig(fee_rate=Decimal("-0.001"))
        with self.assertRaises(ValueError):
            OrbBacktestConfig(slippage_pct=Decimal("-1"))
        with self.assertRaises(ValueError):
            OrbBacktestConfig(capital_usd=Decimal("0"))
        with self.assertRaises(ValueError):
            OrbBacktestConfig(stop_loss_pct=Decimal("0"))
        with self.assertRaises(ValueError):
            OrbBacktestConfig(take_profit_pct=Decimal("0"))
        with self.assertRaises(TypeError):
            OrbBacktestConfig(fee_rate=0.001)  # type: ignore[arg-type]

    def test_empty_candles_rejected(self) -> None:
        with self.assertRaises(ValueError):
            backtest_orb([])

    def test_grid_search_orb_is_ranked_by_net(self) -> None:
        configs = [
            OrbBacktestConfig(
                fee_rate=Decimal("0"), slippage_pct=Decimal("0")
            ),
            OrbBacktestConfig(
                fee_rate=Decimal("0.001"), slippage_pct=Decimal("0.5")
            ),
        ]

        results = grid_search_orb(_orb_series(), configs)

        self.assertEqual(len(results), 2)
        nets = [result.net_pnl_usd for result in results]
        self.assertEqual(nets, sorted(nets, reverse=True))
        self.assertEqual(results[0].trades, 3)

    def test_orb_split_is_chronological(self) -> None:
        train, validation, test = split_candles(_orb_series())

        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertTrue(test)
        self.assertEqual(
            len(train) + len(validation) + len(test),
            len(_orb_series()),
        )
        self.assertLessEqual(train[-1].open_time, validation[0].open_time)
        self.assertLessEqual(
            validation[-1].open_time,
            test[0].open_time,
        )


if __name__ == "__main__":
    unittest.main()
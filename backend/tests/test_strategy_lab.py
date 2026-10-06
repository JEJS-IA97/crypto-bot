import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.domain.signal_engine import (
    Candle,
    SignalAction,
    StrategyConfig as SignalConfig,
    evaluate,
)
from app.services.strategy_lab_service import (
    KlineBacktestConfig,
    Snapshot,
    StrategyConfig,
    backtest,
    backtest_candles,
    grid_search,
    grid_search_candles,
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


if __name__ == "__main__":
    unittest.main()
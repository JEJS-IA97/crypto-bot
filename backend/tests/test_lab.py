"""Laboratorio: contabilidad long/short, estrategias, régimen, backtest y vivo."""

import json
import shutil
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.lab import live, models as lab_models  # noqa: F401
from app.lab.backtest import run_strategy
from app.lab.bars import Bar, resample
from app.lab.engine import FEE_RATE, SLIPPAGE, Account
from app.lab.metrics import summarize
from app.lab.models import LabTrade
from app.lab.regime import RegimeLookup, regime_series
from app.lab.strategies import ALL_STRATEGIES, OrbNY, Signal, Strategy
from app.main import app
from app.services.risk_guard_service import get_runtime

D = Decimal
NY = ZoneInfo("America/New_York")
H = 3_600_000


def bar(ts, o, h, low, c, v=1.0):
    return Bar(ts, o, h, low, c, v)


class EngineTests(unittest.TestCase):
    def test_long_win_pays_fees_and_slippage(self):
        acc = Account("x", D("100"))
        pos = acc.open(symbol="BTC", side="LONG", price=D("100"), stop=D("98"),
                       take_profit=D("104"), ts=0, regime="r")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.entry, D("100") * (1 + SLIPPAGE))
        trade = acc.close("BTC", D("104"), 1, "tp")
        exit_price = D("104") * (1 - SLIPPAGE)
        expected = pos.qty * exit_price * (1 - FEE_RATE) - pos.notional - pos.entry_fee
        self.assertEqual(trade.pnl, expected.quantize(D("0.00000001")))
        self.assertGreater(trade.pnl, 0)
        self.assertEqual(acc.cash, D("100") + expected)

    def test_short_profits_when_price_falls(self):
        acc = Account("x", D("100"))
        acc.open(symbol="ETH", side="SHORT", price=D("100"), stop=D("102"),
                 take_profit=D("96"), ts=0, regime="r")
        trade = acc.close("ETH", D("96"), 1, "tp")
        self.assertGreater(trade.pnl, 0)
        self.assertGreater(trade.r_multiple, D("1.5"))
        self.assertEqual(acc.positions, {})

    def test_risk_is_two_percent_but_never_leveraged(self):
        acc = Account("x", D("100"))
        wide = acc.open(symbol="A", side="LONG", price=D("100"), stop=D("80"),
                        take_profit=D("140"), ts=0, regime="r")
        self.assertAlmostEqual(float(wide.risk_usd), 2.0, places=1)
        acc2 = Account("x", D("100"))
        tight = acc2.open(symbol="A", side="LONG", price=D("100"), stop=D("99.9"),
                          take_profit=D("101"), ts=0, regime="r")
        self.assertLessEqual(tight.notional + tight.entry_fee, D("100"))

    def test_below_binance_minimum_is_skipped(self):
        acc = Account("x", D("20"))
        acc.open(symbol="A", side="LONG", price=D("100"), stop=D("99"), take_profit=D("102"),
                 ts=0, regime="r")  # se lleva casi todo el efectivo
        second = acc.open(symbol="B", side="LONG", price=D("100"), stop=D("99"),
                          take_profit=D("102"), ts=0, regime="r")
        self.assertIsNone(second)
        self.assertEqual(acc.skipped, 1)

    def test_hit_prefers_stop_when_bar_touches_both(self):
        acc = Account("x", D("100"))
        pos = acc.open(symbol="A", side="LONG", price=D("100"), stop=D("98"),
                       take_profit=D("103"), ts=0, regime="r")
        self.assertEqual(pos.hit(D("97"), D("104"))[0], "stop")
        self.assertEqual(pos.hit(D("99"), D("104"))[0], "tp")
        self.assertIsNone(pos.hit(D("99"), D("101")))


class StrategyAndRegimeTests(unittest.TestCase):
    def test_all_strategies_run_on_flat_data_without_errors(self):
        bars = [bar(i * 300_000, 100, 101, 99, 100) for i in range(1200)]
        for strategy in ALL_STRATEGIES:
            self.assertEqual(len(strategy.signals(bars)), len(bars), strategy.name)

    def test_orb_long_on_breakout_after_ten_ny(self):
        day = datetime(2026, 10, 14, 9, 30, tzinfo=NY)
        start = int(day.timestamp() * 1000)
        bars = [bar(start + i * 300_000, 100, 101, 99, 100) for i in range(6)]  # 9:30–9:55
        bars.append(bar(start + 6 * 300_000, 100, 103, 100, 102.5))  # 10:00 rompe
        signals = OrbNY().signals(bars)
        self.assertEqual(signals[6].side, "LONG")
        self.assertEqual(signals[6].stop, 100)
        self.assertAlmostEqual(signals[6].take_profit, 107.5)

    def test_regime_labels_trend_and_range(self):
        trending = [bar(i * H, 100 + i, 101 + i, 99 + i, 100 + i) for i in range(100)]
        ranging = [bar(i * H, 100, 101, 99, 100 + (1 if i % 2 else -1)) for i in range(100)]
        self.assertTrue(regime_series(trending)[-1].startswith("tendencia"))
        self.assertTrue(regime_series(ranging)[-1].startswith("rango"))
        self.assertEqual(RegimeLookup(trending).at(-1), "sin datos")

    def test_resample_drops_incomplete_bucket(self):
        five = [bar(i * 300_000, 1, 2, 0.5, 1.5) for i in range(7)]
        self.assertEqual(len(resample(five, 15)), 2)


class AlwaysLong(Strategy):
    name = "always_long"
    timeframe = "1h"

    def signals(self, bars):
        return [Signal("LONG", b.c * 0.98, b.c * 1.02) for b in bars]


class BacktestTests(unittest.TestCase):
    def test_runs_three_capitals_and_reports_regimes(self):
        bars = [bar(i * H, 100 + i * 0.5, 101 + i * 0.5, 99.9 + i * 0.5, 100.5 + i * 0.5) for i in range(200)]
        accounts = run_strategy(AlwaysLong(), {"BTC": bars}, {"BTC": RegimeLookup(bars)})
        self.assertEqual([a.capital for a in accounts], [D("20"), D("50"), D("100")])
        self.assertTrue(all(a.trades for a in accounts))
        report = summarize(accounts[2].trades, accounts[2].capital, days=8)
        self.assertGreater(report["win_rate"], 50)
        self.assertIn("by_regime", report)


class LiveRunnerTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        self.runner = live.LabRunner(session_factory=self.factory, market=object())
        self.runner.restore()
        self.runner.bars[("BTCUSDT", "1h")] = [bar(i * H, 100, 101, 99, 100) for i in range(30)]

    def _kline(self, symbol, tf, ts, close):
        return {"data": {"e": "kline", "s": symbol, "k": {
            "t": ts, "i": tf, "o": str(close), "h": str(close), "l": str(close),
            "c": str(close), "v": "1", "x": True}}}

    def test_signal_opens_and_ticker_closes_at_take_profit(self):
        with patch.object(live, "STRATEGIES", [AlwaysLong()]):
            self.runner.strategies = [AlwaysLong()]
            self.runner.accounts = {k: v for k, v in self.runner.accounts.items() if k[0] == "always_long"}
            from app.lab import store
            with self.factory() as db:
                self.runner.accounts = store.load_accounts(db, ["always_long"], [D("100")])
            self.runner.handle(self._kline("BTCUSDT", "1h", 30 * H, 100))
            with self.factory() as db:
                (row,) = db.scalars(select(LabTrade)).all()
                self.assertEqual(row.status, "OPEN")
            self.runner.handle({"data": {"e": "24hrMiniTicker", "s": "BTCUSDT", "c": "103"}})
            with self.factory() as db:
                (row,) = db.scalars(select(LabTrade)).all()
                self.assertEqual((row.status, row.reason), ("CLOSED", "tp"))
                self.assertGreater(row.pnl, 0)

    def test_principal_copies_only_proven_long_sources(self):
        from app.lab import store
        from app.lab.engine import Trade

        def t(name, side, pnl, i):
            return Trade(name, D("100"), "BTCUSDT", side, D("1"), D("1"), D("1"), i, i + 1, D(str(pnl)), D("0"), None, "r", "tp")

        winners = [t("a", "LONG", 2, i) for i in range(4)] + [t("a", "LONG", -1, 9)]
        shorts = [t("b", "SHORT", 2, i) for i in range(6)]
        dupes = [t("c", "LONG", 1, 0)] * 6  # la misma operación en 3 cuentas no cuenta 3 veces
        self.assertEqual(live.champions(winners + shorts + dupes, set()), {"a"})
        self.assertEqual(live.champions(winners, {"a"}), set())

        with patch.object(live, "STRATEGIES", [AlwaysLong()]), patch.object(live.context, "macro_blackout", lambda: None):
            self.runner.strategies = [AlwaysLong()]
            with self.factory() as db:
                self.runner.accounts = store.load_accounts(db, ["always_long"], [D("100")])
                self.runner.accounts.update(store.load_accounts(db, [live.PRINCIPAL], [self.runner.principal_capital]))
            self.runner.prices["BTCUSDT"] = D("100")
            self.runner.champions = {"always_long"}
            self.runner.bars[("BTCUSDT", "1d")] = [bar(i * 86_400_000, 1, 1, 1, 1 + i) for i in range(20)]
            self.runner.handle(self._kline("BTCUSDT", "1h", 30 * H, 100))
            self.assertIn("BTCUSDT", self.runner.principal.positions)
            self.runner.handle({"data": {"e": "24hrMiniTicker", "s": "BTCUSDT", "c": "103"}})
        with self.factory() as db:
            rows = {r.strategy: r for r in db.scalars(select(LabTrade))}
        self.assertEqual(rows[live.PRINCIPAL].status, "CLOSED")
        self.assertEqual(rows[live.PRINCIPAL].regime, "always_long")
        self.assertGreater(rows[live.PRINCIPAL].pnl, 0)

    def test_orphan_positions_of_retired_strategies_get_closed(self):
        from app.lab import store
        from app.lab.engine import Account

        old = Account("retired", D("100"))
        pos = old.open(symbol="BTCUSDT", side="LONG", price=D("100"), stop=D("95"), take_profit=None, ts=1, regime="r")
        with self.factory() as db:
            store.load_accounts(db, ["retired"], [D("100")])
            store.save_open(db, old, pos)
        self.runner.prices["BTCUSDT"] = D("110")
        self.assertEqual(self.runner.close_orphans(), 1)
        with self.factory() as db:
            row = db.scalars(select(LabTrade)).one()
        self.assertEqual((row.status, row.reason), ("CLOSED", "retirada"))
        self.assertGreater(row.pnl, 0)

    def test_losing_streak_pauses_strategy_48h(self):
        for i in range(10):
            self.runner._record("x", i >= 5, 1000 + i)  # 5 pérdidas y 5 ganancias
        self.assertTrue(self.runner.paused("x", 1009 + 3_600_000))
        self.assertFalse(self.runner.paused("x", 1009 + 49 * 3_600_000))
        self.assertEqual(self.runner.streak["x"], [])

    def test_kill_switch_blocks_new_entries(self):
        with self.factory() as db:
            get_runtime(db).running = False
            db.commit()
        with patch.object(live, "STRATEGIES", [AlwaysLong()]):
            from app.lab import store
            with self.factory() as db:
                self.runner.accounts = store.load_accounts(db, ["always_long"], [D("100")])
            self.runner.handle(self._kline("BTCUSDT", "1h", 30 * H, 100))
        with self.factory() as db:
            self.assertEqual(db.scalars(select(LabTrade)).all(), [])


class LabApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="lab-api-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        engine = create_engine(f"sqlite:///{Path(tmp) / 'lab.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        patcher = patch("app.database.SessionLocal", sessionmaker(bind=engine))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.report = Path(tmp) / "lab-backtest.json"
        report_patch = patch("app.api.routes.lab.REPORT_JSON", self.report)
        report_patch.start()
        self.addCleanup(report_patch.stop)
        self.client = TestClient(app)

    def test_backtest_missing_then_served(self):
        self.assertEqual(self.client.get("/api/lab/backtest").status_code, 404)
        self.report.write_text(json.dumps({"rows": [{"strategy": "x"}]}), encoding="utf-8")
        self.assertEqual(self.client.get("/api/lab/backtest").json()["rows"][0]["strategy"], "x")

    def test_live_board_without_runner(self):
        with patch.object(live, "runner", None):
            body = self.client.get("/api/lab/live").json()
        self.assertFalse(body["feed"]["connected"])
        self.assertEqual(body["rows"], [])
        self.assertEqual([s["name"] for s in self.client.get("/api/lab/strategies").json()], ["bollinger_trend_1h", "sesion_16utc_futuros", "reversion_4h_futuros", "momentum_48h_corto", "ruptura_7d_1h", "momentum_48h_1h", "ema_rsi_4h"])


if __name__ == "__main__":
    unittest.main()

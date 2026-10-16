"""Núcleo de tendencia en el loop: compra al entrar, vende al salir, sin SL/TP."""

import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
from app.models import DecisionStatus, PositionStatus, PositionV2, SignalDecision
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import SymbolRules
from app.services.bot_loop import run_once
from app.services.simulation_service import create_simulation_account

NOW = datetime(2026, 10, 16, 1, 0)


def _candle(open_time: datetime, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        open_time=open_time,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=Decimal("10"),
    )


def daily(last_close: str, base: str = "100") -> list[Candle]:
    """200 cierres planos en `base` hasta anteayer + ayer en `last_close`
    + la vela en curso de hoy (que debe ignorarse)."""
    yesterday = datetime.combine(NOW.date(), datetime.min.time()) - timedelta(days=1)
    candles = [
        _candle(yesterday - timedelta(days=200 - i), base) for i in range(200)
    ]
    candles.append(_candle(yesterday, last_close))
    candles.append(_candle(yesterday + timedelta(days=1), "1"))
    return candles


def intraday(price: str) -> list[Candle]:
    return [_candle(NOW - timedelta(minutes=15 * (3 - i)), price) for i in range(3)]


class FakeMarket:
    def __init__(self, daily_by_symbol: dict, price_by_symbol: dict) -> None:
        self.daily = daily_by_symbol
        self.price = price_by_symbol

    def get_klines(self, symbol, interval="15m", limit=200):
        if interval == "1d":
            return list(self.daily[symbol])
        return intraday(self.price[symbol])

    def get_exchange_info(self, symbol):
        return SymbolRules(
            symbol=symbol,
            status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.0001"),
            min_notional=Decimal("5"),
        )


@patch.object(settings, "risk_max_total_exposure_pct", Decimal("100"))
@patch.object(settings, "configured_capital_usd", Decimal("40"))
@patch.object(settings, "trend_enabled", True)
class TrendLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(name="trend", initial_balance_usd=Decimal("40")),
        )

    def tearDown(self) -> None:
        self.db.close()

    def _run(self, market: FakeMarket, *, now: datetime = NOW, symbols=None):
        return run_once(
            self.db,
            market_data=market,
            symbols=symbols or ["BTCUSDT"],
            account_id=self.account.id,
            now=now,
        )

    def _positions(self) -> list[PositionV2]:
        return list(self.db.scalars(select(PositionV2)).all())

    def test_inside_buys_half_the_capital_without_stop(self) -> None:
        report = self._run(FakeMarket({"BTCUSDT": daily("110")}, {"BTCUSDT": "110"}))

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 1)
        (position,) = self._positions()
        self.assertEqual(position.status, PositionStatus.OPEN)
        self.assertIsNone(position.stop_price)
        notional = position.quantity * position.average_entry_price
        self.assertLessEqual(notional, Decimal("20"))
        self.assertGreater(notional, Decimal("19"))
        decision = self.db.get(SignalDecision, position.decision_id)
        self.assertEqual(json.loads(decision.config_json)["slow"], 200)

    def test_holding_inside_does_not_trade_again(self) -> None:
        market = FakeMarket({"BTCUSDT": daily("110")}, {"BTCUSDT": "110"})
        self._run(market)
        report = self._run(market, now=NOW + timedelta(minutes=10))

        self.assertEqual(report.opened, 0)
        self.assertEqual(len(self._positions()), 1)

    def test_outside_sells_the_trend_position(self) -> None:
        self._run(FakeMarket({"BTCUSDT": daily("110")}, {"BTCUSDT": "110"}))
        report = self._run(
            FakeMarket({"BTCUSDT": daily("90")}, {"BTCUSDT": "90"}),
            now=NOW + timedelta(days=1),
        )

        self.assertEqual(report.closed, 1)
        (position,) = self._positions()
        self.assertNotEqual(position.status, PositionStatus.OPEN)
        decision = self.db.get(SignalDecision, position.decision_id)
        self.assertEqual(decision.status, DecisionStatus.CLOSED)
        self.assertLess(decision.pnl_usd, 0)

    def test_outside_and_flat_does_nothing(self) -> None:
        report = self._run(FakeMarket({"BTCUSDT": daily("90")}, {"BTCUSDT": "90"}))

        self.assertEqual((report.opened, report.closed), (0, 0))
        self.assertEqual(list(self.db.scalars(select(SignalDecision)).all()), [])

    def test_btc_and_eth_both_open_without_correlation_resize(self) -> None:
        market = FakeMarket(
            {"BTCUSDT": daily("110"), "ETHUSDT": daily("110")},
            {"BTCUSDT": "110", "ETHUSDT": "110"},
        )
        report = self._run(market, symbols=["BTCUSDT", "ETHUSDT"])

        self.assertEqual(report.opened, 2)
        for position in self._positions():
            notional = position.quantity * position.average_entry_price
            self.assertGreater(notional, Decimal("15"))

    def test_rejected_buy_is_not_retried_the_same_day(self) -> None:
        market = FakeMarket({"BTCUSDT": daily("110")}, {"BTCUSDT": "110"})
        with patch.object(settings, "trend_allocation_pct", Decimal("1")):
            first = self._run(market)  # 0.40 USD < min_notional
            second = self._run(market, now=NOW + timedelta(minutes=10))

        self.assertEqual((first.rejected, second.rejected), (1, 0))
        self.assertEqual(len(self.db.scalars(select(SignalDecision)).all()), 1)

    def test_disabled_trend_never_fetches_daily(self) -> None:
        class NoDaily(FakeMarket):
            def get_klines(self, symbol, interval="15m", limit=200):
                if interval == "1d":
                    raise AssertionError("1d klines requested")
                return super().get_klines(symbol, interval, limit)

        with patch.object(settings, "trend_enabled", False):
            report = self._run(NoDaily({}, {"BTCUSDT": "110"}))
        self.assertEqual(report.status, "ok")


if __name__ == "__main__":
    unittest.main()

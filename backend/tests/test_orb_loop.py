"""Integración ORB en el loop (spec 001 v3, RF-6/RF-7/RF-27, D-11/D-12).

El loop descarga velas 5m solo en la ventana ORB (9:00–10:00 AM NY) para
los 4 pares ORB, evalúa el rompimiento de las 9:30, emite como máximo una
decisión técnica por par por día de Nueva York y nunca cierra posiciones
con señal técnica (cierres por stop/tp RF-13 o externa RF-8).
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import SymbolRules
from app.services.bot_loop import run_once
from app.services.simulation_service import create_simulation_account

NY = ZoneInfo("America/New_York")
SESSION_DAY = date(2026, 10, 5)  # EDT (UTC-4)


def _ny_utc(hour: int, minute: int, day: date = SESSION_DAY) -> datetime:
    moment = datetime(
        day.year, day.month, day.day, hour, minute, tzinfo=NY
    )
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


NOW_IN_WINDOW = _ny_utc(9, 35)  # 9:35 AM NY — ventana de rompimiento
NOW_OUTSIDE = _ny_utc(12, 0)  # mediodía NY — fuera de la ventana


def range_candles(breakout_close: str = "106") -> list[Candle]:
    """Rango 9:00–9:25 (high 100.5 / low 99.5) + vela de las 9:30."""
    candles = []
    for minute in (0, 5, 10, 15, 20, 25):
        candles.append(
            Candle(
                open_time=_ny_utc(9, minute),
                open=Decimal("100"),
                high=Decimal("100.5"),
                low=Decimal("99.5"),
                close=Decimal("100"),
                volume=Decimal("100"),
            )
        )
    candles.append(
        Candle(
            open_time=_ny_utc(9, 30),
            open=Decimal("100"),
            high=Decimal("106.5"),
            low=Decimal("99.8"),
            close=Decimal(breakout_close),
            volume=Decimal("200"),
        )
    )
    return candles


def candles_15m() -> list[Candle]:
    base = datetime(2026, 10, 5, 0, 0)
    return [
        Candle(
            open_time=base + timedelta(minutes=15 * index),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("100"),
        )
        for index in range(60)
    ]


class FakeMarketData:
    def __init__(
        self,
        candles_15m_by_symbol: dict,
        candles_5m_by_symbol: dict | None = None,
    ) -> None:
        self._candles_15m = candles_15m_by_symbol
        self._candles_5m = candles_5m_by_symbol or {}
        self.kline_calls: list[tuple[str, str]] = []

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        self.kline_calls.append((symbol, interval))
        if interval == "5m":
            return list(self._candles_5m.get(symbol, []))
        return list(self._candles_15m[symbol])

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol=symbol,
            status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )


class OrbLoopTestCase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="orb-loop",
                initial_balance_usd=Decimal("50"),
            ),
        )

    def tearDown(self) -> None:
        self.db.close()

    def _run(
        self,
        market: FakeMarketData,
        *,
        now: datetime,
        symbols: list[str] | None = None,
        account_id: int | None = None,
    ):
        return run_once(
            self.db,
            market_data=market,
            symbols=symbols if symbols is not None else ["BTCUSDT"],
            account_id=(
                account_id if account_id is not None else self.account.id
            ),
            now=now,
        )

    def _decisions(self) -> list[SignalDecision]:
        return list(self.db.scalars(select(SignalDecision)).all())

    def _external(
        self,
        side: TradeSide,
        client_order_id: str,
        *,
        symbol: str = "BTCUSDT",
        created_at: datetime | None = None,
    ) -> SignalDecision:
        decision = SignalDecision(
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            origin=DecisionOrigin.EXTERNAL,
            source="copia-proveedor",
            status=DecisionStatus.PENDING,
            config_json="{}",
            market_snapshot_json="{}",
            created_at=created_at or NOW_IN_WINDOW,
        )
        self.db.add(decision)
        self.db.commit()
        return decision


class OrbBreakoutLoopTests(OrbLoopTestCase):
    def test_breakout_buys_with_range_snapshot(self) -> None:
        market = FakeMarketData(
            {"BTCUSDT": candles_15m()}, {"BTCUSDT": range_candles()}
        )
        report = self._run(market, now=NOW_IN_WINDOW)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 1)
        # RF-6: 15m siempre; 5m solo en la ventana ORB para el par ORB.
        self.assertEqual(
            market.kline_calls,
            [("BTCUSDT", "15m"), ("BTCUSDT", "5m")],
        )

        decisions = self._decisions()
        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision.origin, DecisionOrigin.TECHNICAL)
        self.assertEqual(decision.status, DecisionStatus.OPENED)

        snapshot = json.loads(decision.market_snapshot_json)
        indicators = snapshot["indicators"]
        self.assertEqual(indicators["range_high"], "100.5")
        self.assertEqual(indicators["range_low"], "99.5")
        self.assertEqual(indicators["breakout_price"], "106")

        config = json.loads(decision.config_json)
        self.assertEqual(config["range_start_hour"], 9)
        self.assertEqual(config["range_minutes"], 30)
        self.assertEqual(config["timezone_name"], "America/New_York")

        position = self.db.scalars(select(PositionV2)).one()
        self.assertEqual(position.status, PositionStatus.OPEN)
        # D-11: RR 1:1 — stop y take-profit simétricos al 2%.
        self.assertEqual(position.stop_price, Decimal("98"))
        self.assertEqual(position.take_profit_price, Decimal("102"))

    def test_one_technical_decision_per_ny_day(self) -> None:
        # Capital mínimo: el sizing descarta la orden y la decisión técnica
        # queda REJECTED — el primer intento agota el día NY (RF-27).
        poor = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="orb-dedup",
                initial_balance_usd=Decimal("1"),
            ),
        )
        market = FakeMarketData(
            {"BTCUSDT": candles_15m()}, {"BTCUSDT": range_candles()}
        )

        first = self._run(market, now=NOW_IN_WINDOW, account_id=poor.id)
        self.assertEqual(first.status, "ok")
        self.assertEqual(first.opened, 0)
        decisions = self._decisions()
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].origin, DecisionOrigin.TECHNICAL)
        self.assertEqual(decisions[0].status, DecisionStatus.REJECTED)
        self.assertEqual(
            decisions[0].rejection_reason, "insufficient_balance"
        )

        second = self._run(market, now=NOW_IN_WINDOW, account_id=poor.id)
        self.assertEqual(second.status, "ok")
        self.assertEqual(second.opened, 0)
        self.assertEqual(len(self._decisions()), 1)
        # Sin segunda evaluación tampoco hay una segunda descarga 5m.
        downloads_5m = [
            call for call in market.kline_calls if call[1] == "5m"
        ]
        self.assertEqual(downloads_5m, [("BTCUSDT", "5m")])

    def test_decision_from_previous_ny_day_does_not_block(self) -> None:
        stale = SignalDecision(
            client_order_id="bot-orb-yesterday-0001",
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            status=DecisionStatus.REJECTED,
            rejection_reason="prior_day",
            config_json="{}",
            market_snapshot_json="{}",
            created_at=datetime(2026, 10, 4, 12, 0),
        )
        self.db.add(stale)
        self.db.commit()

        market = FakeMarketData(
            {"BTCUSDT": candles_15m()}, {"BTCUSDT": range_candles()}
        )
        report = self._run(market, now=NOW_IN_WINDOW)

        self.assertEqual(report.opened, 1)
        decisions = self._decisions()
        technical = [
            item for item in decisions if item.origin == DecisionOrigin.TECHNICAL
        ]
        self.assertEqual(len(technical), 2)
        self.assertEqual(technical[-1].status, DecisionStatus.OPENED)

    def test_breakdown_holds_without_emitting(self) -> None:
        market = FakeMarketData(
            {"BTCUSDT": candles_15m()},
            {"BTCUSDT": range_candles(breakout_close="99")},
        )
        report = self._run(market, now=NOW_IN_WINDOW)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 0)
        self.assertEqual(report.rejected, 0)
        self.assertEqual(self._decisions(), [])
        self.assertEqual(
            market.kline_calls,
            [("BTCUSDT", "15m"), ("BTCUSDT", "5m")],
        )


class OrbWindowAndScopeTests(OrbLoopTestCase):
    def test_outside_window_skips_5m_download(self) -> None:
        market = FakeMarketData(
            {"BTCUSDT": candles_15m()}, {"BTCUSDT": range_candles()}
        )
        report = self._run(market, now=NOW_OUTSIDE)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 0)
        self.assertEqual(self._decisions(), [])
        self.assertEqual(market.kline_calls, [("BTCUSDT", "15m")])

    def test_non_orb_symbol_never_evaluates(self) -> None:
        # D-12: XRP solo opera con señales externas, incluso en la ventana.
        market = FakeMarketData(
            {"XRPUSDT": candles_15m()}, {"XRPUSDT": range_candles()}
        )
        report = self._run(
            market, now=NOW_IN_WINDOW, symbols=["XRPUSDT"]
        )

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 0)
        self.assertEqual(self._decisions(), [])
        self.assertEqual(market.kline_calls, [("XRPUSDT", "15m")])

    def test_empty_5m_klines_fails_the_cycle(self) -> None:
        # RNF-6: sin datos 5m en ventana → ciclo fallido, sin órdenes.
        market = FakeMarketData({"BTCUSDT": candles_15m()}, {})
        report = self._run(market, now=NOW_IN_WINDOW)

        self.assertEqual(report.status, "failed")
        self.assertIn("Empty ORB klines", report.error)
        self.assertEqual(self._decisions(), [])
        self.assertEqual(self.db.scalars(select(PositionV2)).all(), [])

    def test_open_position_is_only_managed_by_stop_or_external(self) -> None:
        # Posición abierta por externa: el ciclo no cierra con señal técnica
        # y la externa SELL sigue mandando (RF-7/RF-8, plan paso 9).
        self._external(TradeSide.BUY, "bot-external-btc-0001")
        market = FakeMarketData(
            {"BTCUSDT": candles_15m()},
            {"BTCUSDT": range_candles(breakout_close="99")},
        )

        opened = self._run(market, now=NOW_IN_WINDOW)
        self.assertEqual(opened.opened, 1)
        self.assertEqual(opened.closed, 0)
        position = self.db.scalars(select(PositionV2)).one()
        self.assertEqual(position.status, PositionStatus.OPEN)

        managed = self._run(market, now=NOW_IN_WINDOW)
        self.assertEqual(managed.opened, 0)
        self.assertEqual(managed.closed, 0)
        self.db.refresh(position)
        self.assertEqual(position.status, PositionStatus.OPEN)
        # Solo existe la decisión externa: la técnica no emitió.
        self.assertEqual(len(self._decisions()), 1)

        self._external(TradeSide.SELL, "bot-external-btc-0002")
        closed = self._run(market, now=NOW_IN_WINDOW)
        self.assertEqual(closed.closed, 1)
        self.db.refresh(position)
        self.assertEqual(position.status, PositionStatus.CLOSED)


if __name__ == "__main__":
    unittest.main()

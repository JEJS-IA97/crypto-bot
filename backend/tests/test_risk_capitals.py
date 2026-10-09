"""Tests rojos — Spec 008: matriz de capitales (RF-8, D-9 / Tabla 1).

Sesiones simuladas deterministas (velas fijas, sin red) con capital
10 / 20 / 50 / 100 / 1000 USD: invariantes de la constitución por capital y
conducta esperada del resize correlacionado.
"""

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    SystemEvent,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import SymbolRules
from app.services.bot_loop import run_once
from app.services.risk_guard_service import (
    DAILY_LOSS_LIMIT_PCT,
    MAX_OPENS_PER_DAY,
    get_daily_state,
)
from app.services.simulation_service import create_simulation_account

NY = ZoneInfo("America/New_York")
SESSION_DAY = date(2026, 10, 5)
NOW_IN_WINDOW = datetime(
    SESSION_DAY.year, SESSION_DAY.month, SESSION_DAY.day,
    9, 35, tzinfo=NY,
).astimezone(timezone.utc).replace(tzinfo=None)

CAPITALS = (
    Decimal("10"),
    Decimal("20"),
    Decimal("50"),
    Decimal("100"),
    Decimal("1000"),
)

# Tabla 1: notional del sizing de la 001 (min 5, share 25%, tope de riesgo 50).
SESSION_A_NOTIONAL = {
    10: Decimal("5"),
    20: Decimal("5"),
    50: Decimal("12.5"),
    100: Decimal("25"),
    1000: Decimal("50"),
}

# Tabla 1: resultado de la segunda apertura correlacionada (r ≥ 0.7).
# (acción, cantidad esperada de BTCUSDT o None si bloqueada)
SESSION_B_EXPECTED = {
    10: ("blocked", None),
    20: ("allow", Decimal("0.05")),
    50: ("resized", Decimal("0.062")),
    100: ("resized", Decimal("0.125")),
    1000: ("allow", Decimal("0.5")),
}


def _ny_utc(hour: int, minute: int) -> datetime:
    moment = datetime(
        SESSION_DAY.year, SESSION_DAY.month, SESSION_DAY.day,
        hour, minute, tzinfo=NY,
    )
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _flat_candles(count: int = 60) -> list[Candle]:
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
        for index in range(count)
    ]


def _varied_candles(count: int = 60) -> list[Candle]:
    """Serie con varianza, idéntica entre símbolos (corr = 1), cierre final 100."""
    base = datetime(2026, 10, 5, 0, 0)
    return [
        Candle(
            open_time=base + timedelta(minutes=15 * index),
            open=Decimal(100 + (index + 1) % 10),
            high=Decimal(101 + (index + 1) % 10),
            low=Decimal(99 + (index + 1) % 10),
            close=Decimal(100 + (index + 1) % 10),
            volume=Decimal("100"),
        )
        for index in range(count)
    ]


def range_candles(breakout_close: str = "106") -> list[Candle]:
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


class FakeMarketData:
    def __init__(
        self,
        candles_15m_by_symbol: dict,
        candles_5m_by_symbol: dict | None = None,
    ) -> None:
        self._candles_15m = candles_15m_by_symbol
        self._candles_5m = candles_5m_by_symbol or {}

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
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


class CapitalMatrixBase(unittest.TestCase):
    def _fresh(self, capital: Decimal):
        """DB + cuenta con el capital dado. Devuelve (db, account, engine)."""
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        db = factory()
        account = create_simulation_account(
            db,
            SimulationAccountCreate(
                name=f"capital-{capital}",
                initial_balance_usd=capital,
            ),
        )
        return db, account, engine

    def _insert_open_position(
        self,
        db: Session,
        account_id: int,
        *,
        symbol: str,
        quantity: Decimal,
        created_at: datetime,
    ) -> None:
        decision = SignalDecision(
            client_order_id=f"seed-{symbol}",
            symbol=symbol,
            side=TradeSide.BUY,
            origin=DecisionOrigin.EXTERNAL,
            status=DecisionStatus.OPENED,
            config_json="{}",
            market_snapshot_json="{}",
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(decision)
        db.commit()
        db.add(
            PositionV2(
                account_id=account_id,
                decision_id=decision.id,
                symbol=symbol,
                quantity=quantity,
                average_entry_price=Decimal("100"),
                stop_price=None,
                take_profit_price=None,
                status=PositionStatus.OPEN,
            )
        )
        db.commit()

    def _risk_event(self, db: Session) -> SystemEvent | None:
        return db.scalars(
            select(SystemEvent)
            .where(SystemEvent.event == "risk.evaluated")
            .order_by(SystemEvent.id.desc())
            .limit(1)
        ).one_or_none()

    def _btc_decision(self, db: Session) -> SignalDecision:
        return db.scalars(
            select(SignalDecision)
            .where(
                SignalDecision.symbol == "BTCUSDT",
                SignalDecision.origin == DecisionOrigin.TECHNICAL,
            )
            .order_by(SignalDecision.id.desc())
        ).first()


class SingleOpenSessionTests(CapitalMatrixBase):
    """Sesión A: una apertura por capital ⇒ invariantes de la constitución."""

    def test_single_open_invariants_per_capital(self) -> None:
        for capital in CAPITALS:
            with self.subTest(capital=str(capital)):
                db, account, engine = self._fresh(capital)
                try:
                    with patch.object(
                        settings, "configured_capital_usd", capital
                    ):
                        market = FakeMarketData(
                            {"BTCUSDT": _flat_candles()},
                            {"BTCUSDT": range_candles()},
                        )
                        report = run_once(
                            db,
                            market_data=market,
                            symbols=["BTCUSDT"],
                            account_id=account.id,
                            now=NOW_IN_WINDOW,
                        )

                    self.assertEqual(report.status, "ok")
                    self.assertEqual(report.opened, 1)

                    position = db.scalars(
                        select(PositionV2).where(
                            PositionV2.symbol == "BTCUSDT"
                        )
                    ).one()
                    notional = (
                        position.quantity * position.average_entry_price
                    )

                    # Invariantes (§17/RF-8).
                    loss = notional * Decimal("0.02")
                    self.assertLessEqual(loss, Decimal("1"))
                    cap = capital * Decimal("0.75")
                    self.assertLessEqual(notional, cap)

                    open_positions = db.scalars(
                        select(PositionV2).where(
                            PositionV2.status == PositionStatus.OPEN
                        )
                    ).all()
                    self.assertLessEqual(len(open_positions), 3)

                    state = get_daily_state(db, SESSION_DAY, capital)
                    self.assertLessEqual(state.opens_count, MAX_OPENS_PER_DAY)
                    self.assertEqual(DAILY_LOSS_LIMIT_PCT, Decimal("5"))

                    event = self._risk_event(db)
                    self.assertIsNotNone(event)
                    self.assertEqual(event.result, "allow")

                    # Sizing esperado de la Tabla 1 (sesión A).
                    self.assertEqual(notional, SESSION_A_NOTIONAL[int(capital)])
                finally:
                    db.close()
                    engine.dispose()


class CorrelatedSecondOpenTests(CapitalMatrixBase):
    """Sesión B: segunda apertura correlacionada ⇒ Tabla 1 (RF-5)."""

    def test_correlated_second_open_matches_table(self) -> None:
        for capital in CAPITALS:
            expected_action, expected_quantity = SESSION_B_EXPECTED[
                int(capital)
            ]
            with self.subTest(capital=str(capital)):
                db, account, engine = self._fresh(capital)
                try:
                    seed_quantity = SESSION_A_NOTIONAL[int(capital)] / Decimal(
                        "100"
                    )
                    self._insert_open_position(
                        db,
                        account.id,
                        symbol="ETHUSDT",
                        quantity=seed_quantity,
                        created_at=NOW_IN_WINDOW - timedelta(days=1),
                    )

                    market = FakeMarketData(
                        {
                            "BTCUSDT": _varied_candles(),
                            "ETHUSDT": _varied_candles(),
                        },
                        {
                            "BTCUSDT": range_candles(),
                            "ETHUSDT": range_candles(),
                        },
                    )

                    with patch.object(
                        settings, "configured_capital_usd", capital
                    ):
                        report = run_once(
                            db,
                            market_data=market,
                            symbols=["BTCUSDT", "ETHUSDT"],
                            account_id=account.id,
                            now=NOW_IN_WINDOW,
                        )

                    event = self._risk_event(db)
                    self.assertIsNotNone(event)
                    self.assertEqual(event.result, expected_action)

                    btc_positions = db.scalars(
                        select(PositionV2).where(
                            PositionV2.symbol == "BTCUSDT"
                        )
                    ).all()

                    if expected_action == "blocked":
                        # 10 USD: committed 5 + requested 5 > tope 7.5.
                        self.assertEqual(report.opened, 0)
                        self.assertEqual(btc_positions, [])
                        decision = self._btc_decision(db)
                        self.assertEqual(
                            decision.status, DecisionStatus.REJECTED
                        )
                        self.assertEqual(
                            decision.rejection_reason, "max_exposure"
                        )
                        payload = event.payload_json
                        self.assertIn("max_exposure", payload)
                    else:
                        self.assertEqual(report.opened, 1)
                        self.assertEqual(len(btc_positions), 1)
                        position = btc_positions[0]
                        self.assertEqual(
                            position.quantity, expected_quantity
                        )

                        notional = (
                            position.quantity * position.average_entry_price
                        )
                        self.assertLessEqual(
                            notional * Decimal("0.02"), Decimal("1")
                        )

                        open_positions = db.scalars(
                            select(PositionV2).where(
                                PositionV2.status == PositionStatus.OPEN
                            )
                        ).all()
                        self.assertLessEqual(len(open_positions), 3)
                        committed = sum(
                            row.quantity * row.average_entry_price
                            for row in open_positions
                        )
                        self.assertLessEqual(
                            committed, capital * Decimal("0.75")
                        )

                        state = get_daily_state(db, SESSION_DAY, capital)
                        self.assertLessEqual(
                            state.opens_count, MAX_OPENS_PER_DAY
                        )

                        if expected_action == "resized":
                            self.assertIn("resize_applied\": true", event.payload_json)
                        else:
                            # allow con correlación anotada (D-3: suelo de
                            # mínimo en 20, ya ≤ mitad del share en 1000).
                            self.assertIn(
                                '"max_correlation"', event.payload_json
                            )
                finally:
                    db.close()
                    engine.dispose()


if __name__ == "__main__":
    unittest.main()

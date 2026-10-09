"""Tests rojos — Spec 008: risk engine v2 (RF-1…RF-5, RF-7, RF-9).

El motor envuelve al risk_guard de la 001 (D-1), añade los vetos de
posiciones/exposición (D-5/D-6) y la redimensión por correlación (D-2/D-3),
todo auditable con el evento `risk.evaluated` (D-4).
"""

import dataclasses
import importlib
import inspect
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

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
from app.services.risk_engine_service import (
    REASON_CORRELATED_EXPOSURE,
    REASON_MAX_EXPOSURE,
    REASON_MAX_OPEN_POSITIONS,
    RiskAction,
    RiskAssessment,
    evaluate_open,
)
from app.services.risk_guard_service import get_daily_state
from app.services.simulation_service import create_simulation_account

NY = ZoneInfo("America/New_York")
SESSION_DAY = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 13, 35)
DAY = date(2026, 10, 5)


def _ny_utc(hour: int, minute: int) -> datetime:
    moment = datetime(
        SESSION_DAY.year, SESSION_DAY.month, SESSION_DAY.day,
        hour, minute, tzinfo=NY,
    )
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


NOW_IN_WINDOW = _ny_utc(9, 35)


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
    """Velas con varianza (corr = 1 entre sí) y último cierre en 100."""
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


def _falling_candles(count: int = 60) -> list[Candle]:
    base = datetime(2026, 10, 5, 0, 0)
    return [
        Candle(
            open_time=base + timedelta(minutes=15 * index),
            open=Decimal(200 - index),
            high=Decimal(201 - index),
            low=Decimal(199 - index),
            close=Decimal(200 - index),
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


class RiskEngineBase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine)
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="risk-engine",
                initial_balance_usd=Decimal("1000"),
            ),
        )
        self.state = get_daily_state(self.db, DAY, Decimal("20"))

    def tearDown(self) -> None:
        self.db.close()

    def _decision(
        self,
        symbol: str,
        *,
        origin: DecisionOrigin = DecisionOrigin.TECHNICAL,
        status: DecisionStatus = DecisionStatus.PENDING,
        created_at: datetime = NOW,
    ) -> SignalDecision:
        decision = SignalDecision(
            client_order_id=f"dec-{symbol}-{created_at.timestamp()}",
            symbol=symbol,
            side=TradeSide.BUY,
            origin=origin,
            status=status,
            config_json="{}",
            market_snapshot_json="{}",
            created_at=created_at,
            updated_at=created_at,
        )
        self.db.add(decision)
        self.db.commit()
        return decision

    def _open_position(
        self,
        symbol: str,
        *,
        quantity: str = "0.05",
        price: str = "100",
        status: PositionStatus = PositionStatus.OPEN,
        created_at: datetime = NOW - timedelta(days=1),
        stop_price: Decimal | None = None,
        take_profit_price: Decimal | None = None,
    ) -> PositionV2:
        decision = self._decision(
            symbol,
            origin=DecisionOrigin.EXTERNAL,
            status=DecisionStatus.OPENED,
            created_at=created_at,
        )
        position = PositionV2(
            account_id=self.account.id,
            decision_id=decision.id,
            symbol=symbol,
            quantity=Decimal(quantity),
            average_entry_price=Decimal(price),
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            status=status,
        )
        self.db.add(position)
        self.db.commit()
        return position

    def _evaluate(self, **overrides) -> RiskAssessment:
        params = {
            "symbol": "BTCUSDT",
            "now": NOW,
            "state": self.state,
            "account_id": self.account.id,
            "quantity": Decimal("0.05"),
            "price": Decimal("100"),
            "candles": _flat_candles(),
            "other_candles": {},
            "step_size": Decimal("0.001"),
            "min_notional_usd": Decimal("5"),
            "available_usd": Decimal("20"),
            "correlation_id": "corr-risk",
        }
        params.update(overrides)
        return evaluate_open(self.db, **params)

    def _risk_events(self) -> list[SystemEvent]:
        return list(
            self.db.scalars(
                select(SystemEvent)
                .where(SystemEvent.event == "risk.evaluated")
                .order_by(SystemEvent.id)
            ).all()
        )

    def _payload(self, row: SystemEvent) -> dict:
        return json.loads(row.payload_json)


class AssessmentContractTests(RiskEngineBase):
    def test_action_values(self) -> None:
        self.assertEqual(RiskAction.ALLOW.value, "allow")
        self.assertEqual(RiskAction.RESIZED.value, "resized")
        self.assertEqual(RiskAction.BLOCKED.value, "blocked")

    def test_assessment_is_frozen(self) -> None:
        assessment = self._evaluate()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            assessment.action = RiskAction.BLOCKED  # type: ignore[misc]

    def test_reason_constants(self) -> None:
        self.assertEqual(REASON_MAX_OPEN_POSITIONS, "max_open_positions")
        self.assertEqual(REASON_MAX_EXPOSURE, "max_exposure")
        self.assertEqual(REASON_CORRELATED_EXPOSURE, "correlated_exposure")


class DelegationTests(RiskEngineBase):
    """RF-2: las cuatro razones de la 001 llegan intactas (D-1)."""

    def test_daily_loss_is_delegated(self) -> None:
        self.state.blocked = True
        self.state.block_reason = "daily_loss_limit"
        self.db.commit()

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, "daily_loss_limit")
        self.assertEqual(assessment.allowed_usd, Decimal("0"))
        self.assertIsNone(assessment.allowed_quantity)

    def test_daily_open_limit_is_delegated(self) -> None:
        self.state.opens_count = 10
        self.db.commit()

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, "daily_open_limit")

    def test_cooldown_is_delegated(self) -> None:
        self._decision(
            "BTCUSDT",
            status=DecisionStatus.OPENED,
            created_at=NOW - timedelta(seconds=100),
        )

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, "cooldown")

    def test_position_error_is_delegated(self) -> None:
        self._open_position("SOLUSDT", status=PositionStatus.ERROR)

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, "position_error")

    def test_clean_state_allows(self) -> None:
        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(assessment.reason, "")
        self.assertEqual(assessment.allowed_usd, assessment.requested_usd)
        self.assertEqual(assessment.allowed_quantity, Decimal("0.05"))


class PositionLimitTests(RiskEngineBase):
    """RF-3: RF-12 (≤3 posiciones) enchufado por fin (D-5)."""

    def test_two_open_positions_still_allow(self) -> None:
        self._open_position("ETHUSDT")
        self._open_position("SOLUSDT")

        assessment = self._evaluate()
        self.assertNotEqual(assessment.reason, REASON_MAX_OPEN_POSITIONS)
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(assessment.open_positions, 2)

    def test_three_open_positions_block(self) -> None:
        self._open_position("ETHUSDT")
        self._open_position("SOLUSDT")
        self._open_position("BNBUSDT")

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, REASON_MAX_OPEN_POSITIONS)
        self.assertEqual(assessment.open_positions, 3)


class ExposureTests(RiskEngineBase):
    """RF-4: committed + requested ≤ 75% del capital aportado (D-6)."""

    def test_cap_is_75pct_of_configured_capital(self) -> None:
        assessment = self._evaluate()
        self.assertEqual(assessment.exposure_cap_usd, Decimal("15"))

    def test_allowed_exactly_at_cap(self) -> None:
        # committed 10 (2 × 5) + requested 5 = 15 == tope ⇒ permitido.
        self._open_position("ETHUSDT")
        self._open_position("SOLUSDT")

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(
            assessment.committed_usd + assessment.requested_usd,
            Decimal("15"),
        )

    def test_one_cent_over_cap_blocks(self) -> None:
        self._open_position("ETHUSDT")
        self._open_position("SOLUSDT")

        assessment = self._evaluate(quantity=Decimal("0.055"))
        self.assertEqual(assessment.action, RiskAction.BLOCKED)
        self.assertEqual(assessment.reason, REASON_MAX_EXPOSURE)
        self.assertEqual(assessment.allowed_usd, Decimal("0"))

    def test_cap_follows_configured_capital(self) -> None:
        self._open_position("ETHUSDT", quantity="0.25")
        self._open_position("SOLUSDT", quantity="0.25")

        with patch.object(
            settings, "configured_capital_usd", Decimal("100")
        ):
            inside = self._evaluate(quantity=Decimal("0.25"))
            self.assertEqual(inside.exposure_cap_usd, Decimal("75"))
            self.assertEqual(inside.action, RiskAction.ALLOW)

            outside = self._evaluate(quantity=Decimal("0.26"))
            self.assertEqual(outside.action, RiskAction.BLOCKED)
            self.assertEqual(outside.reason, REASON_MAX_EXPOSURE)

    def test_allowed_never_exceeds_requested(self) -> None:
        for quantity in ("0.01", "0.05", "0.25", "0.5"):
            with self.subTest(quantity=quantity):
                assessment = self._evaluate(quantity=Decimal(quantity))
                self.assertLessEqual(
                    assessment.allowed_usd, assessment.requested_usd
                )
                if assessment.action == RiskAction.BLOCKED:
                    self.assertEqual(assessment.allowed_usd, Decimal("0"))


class CorrelationTests(RiskEngineBase):
    """RF-5: correlación ≥0.7 ⇒ resize (D-2/D-3), sin datos ⇒ unknown."""

    def _correlated(self, capital: str = "100") -> RiskAssessment:
        self._open_position(
            "ETHUSDT", stop_price=None, take_profit_price=None
        )
        with patch.object(
            settings, "configured_capital_usd", Decimal(capital)
        ):
            return self._evaluate(
                quantity=Decimal("0.25") if capital == "100" else Decimal("0.05"),
                candles=_varied_candles(),
                other_candles={"ETHUSDT": _varied_candles()},
            )

    def test_no_other_positions_means_no_correlation(self) -> None:
        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertIsNone(assessment.max_correlation)
        self.assertEqual(assessment.correlations, {})
        self.assertFalse(assessment.resize_applied)

    def test_missing_candles_is_unknown_and_does_not_act(self) -> None:
        self._open_position("ETHUSDT")

        assessment = self._evaluate()
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(assessment.correlations, {"ETHUSDT": None})
        self.assertIsNone(assessment.max_correlation)
        self.assertFalse(assessment.resize_applied)

    def test_short_window_is_unknown(self) -> None:
        self._open_position("ETHUSDT")

        assessment = self._evaluate(
            candles=_varied_candles(60),
            other_candles={"ETHUSDT": _varied_candles(10)},
        )
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(assessment.correlations, {"ETHUSDT": None})

    def test_flat_candles_are_unknown(self) -> None:
        self._open_position("ETHUSDT")

        assessment = self._evaluate(
            other_candles={"ETHUSDT": _flat_candles()},
        )
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertEqual(assessment.correlations, {"ETHUSDT": None})

    def test_correlated_resizes_to_half_share_at_100(self) -> None:
        assessment = self._correlated("100")

        self.assertEqual(assessment.action, RiskAction.RESIZED)
        self.assertEqual(assessment.reason, REASON_CORRELATED_EXPOSURE)
        # mitad del share: 100 × 25% / 2 = 12.5; qty floor(12.5/100) = 0.125.
        self.assertEqual(assessment.allowed_quantity, Decimal("0.125"))
        self.assertEqual(assessment.allowed_usd, Decimal("12.5"))
        self.assertLess(assessment.allowed_usd, assessment.requested_usd)
        self.assertGreaterEqual(assessment.allowed_usd, Decimal("5"))
        self.assertTrue(assessment.resize_applied)
        self.assertIsNotNone(assessment.max_correlation)
        self.assertGreaterEqual(assessment.max_correlation, Decimal("0.7"))
        self.assertGreaterEqual(
            Decimal(assessment.correlations["ETHUSDT"]), Decimal("0.7")
        )
        # invariante: la pérdida estimada en el resize sigue ≤1 USD.
        self.assertLessEqual(
            assessment.allowed_usd * Decimal("0.02"), Decimal("1")
        )

    def test_correlated_below_min_notional_keeps_original(self) -> None:
        # capital 20: mitad del share = 2.5 < mínimo 5 ⇒ resize no ejecutable.
        assessment = self._correlated("20")

        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertFalse(assessment.resize_applied)
        self.assertEqual(assessment.allowed_usd, assessment.requested_usd)
        self.assertIsNotNone(assessment.max_correlation)
        self.assertGreaterEqual(assessment.max_correlation, Decimal("0.7"))

    def test_uncorrelated_pair_allows_without_resize(self) -> None:
        self._open_position("ETHUSDT")

        assessment = self._evaluate(
            candles=_varied_candles(),
            other_candles={"ETHUSDT": _falling_candles()},
        )
        self.assertEqual(assessment.action, RiskAction.ALLOW)
        self.assertFalse(assessment.resize_applied)
        self.assertIsNotNone(assessment.correlations["ETHUSDT"])
        self.assertLess(
            Decimal(assessment.correlations["ETHUSDT"]), Decimal("0.7")
        )


class EventTests(RiskEngineBase):
    """RF-7: un `risk.evaluated` por evaluación con payload completo (D-4)."""

    def test_allow_emits_info_event(self) -> None:
        self._evaluate()

        rows = self._risk_events()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.level, "INFO")
        self.assertEqual(row.result, RiskAction.ALLOW.value)
        self.assertEqual(row.service, "risk_engine")
        self.assertEqual(row.asset, "BTCUSDT")
        self.assertEqual(row.correlation_id, "corr-risk")

        payload = self._payload(row)
        for key in (
            "symbol",
            "action",
            "reason",
            "requested_usd",
            "allowed_usd",
            "committed_usd",
            "exposure_cap_usd",
            "open_positions",
            "correlations",
            "max_correlation",
            "resize_applied",
            "limits",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["requested_usd"], "5")
        self.assertIsInstance(payload["requested_usd"], str)
        self.assertEqual(payload["limits"]["max_open_positions"], 3)

    def test_blocked_emits_warning_event(self) -> None:
        self.state.blocked = True
        self.state.block_reason = "daily_loss_limit"
        self.db.commit()

        self._evaluate()
        row = self._risk_events()[0]
        self.assertEqual(row.level, "WARNING")
        self.assertEqual(row.result, RiskAction.BLOCKED.value)
        self.assertEqual(self._payload(row)["reason"], "daily_loss_limit")

    def test_resized_emits_warning_event(self) -> None:
        self._open_position("ETHUSDT")
        with patch.object(
            settings, "configured_capital_usd", Decimal("100")
        ):
            self._evaluate(
                quantity=Decimal("0.25"),
                candles=_varied_candles(),
                other_candles={"ETHUSDT": _varied_candles()},
            )

        row = self._risk_events()[0]
        self.assertEqual(row.level, "WARNING")
        self.assertEqual(row.result, RiskAction.RESIZED.value)
        payload = self._payload(row)
        self.assertEqual(payload["reason"], REASON_CORRELATED_EXPOSURE)
        self.assertTrue(payload["resize_applied"])
        self.assertEqual(payload["allowed_usd"], "12.5")

    def test_one_event_per_evaluation(self) -> None:
        self._evaluate()
        self._evaluate()
        self.assertEqual(len(self._risk_events()), 2)


class LoopIntegrationTests(RiskEngineBase):
    """RF-1/RF-2: el bucle evalúa antes de ordenar (D-1)."""

    def _run(self, market: FakeMarketData, symbols: list[str]):
        return run_once(
            self.db,
            market_data=market,
            symbols=symbols,
            account_id=self.account.id,
            now=NOW_IN_WINDOW,
        )

    def test_blocked_open_is_rejected_without_order(self) -> None:
        self._open_position("ETHUSDT")
        self._open_position("SOLUSDT")
        self._open_position("BNBUSDT")

        market = FakeMarketData(
            {"BTCUSDT": _flat_candles()}, {"BTCUSDT": range_candles()}
        )
        report = self._run(market, ["BTCUSDT"])

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 0)
        self.assertEqual(report.rejected, 1)

        decision = self.db.scalars(
            select(SignalDecision).where(
                SignalDecision.symbol == "BTCUSDT",
                SignalDecision.origin == DecisionOrigin.TECHNICAL,
            )
        ).one()
        self.assertEqual(decision.status, DecisionStatus.REJECTED)
        self.assertEqual(decision.rejection_reason, REASON_MAX_OPEN_POSITIONS)

        sent = self.db.scalars(
            select(SystemEvent).where(SystemEvent.event == "order.sent")
        ).all()
        self.assertEqual(list(sent), [])

        evaluated = [
            row for row in self._risk_events() if row.asset == "BTCUSDT"
        ]
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].result, RiskAction.BLOCKED.value)

    def test_resized_order_uses_allowed_quantity(self) -> None:
        self._open_position(
            "ETHUSDT", stop_price=None, take_profit_price=None
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
            settings, "configured_capital_usd", Decimal("100")
        ):
            report = self._run(market, ["BTCUSDT", "ETHUSDT"])

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 1)

        position = self.db.scalars(
            select(PositionV2).where(PositionV2.symbol == "BTCUSDT")
        ).one()
        # pedido 25 → resize a 12.5 → qty floor(0.125, 0.001) = 0.125.
        self.assertEqual(position.quantity, Decimal("0.125"))

        decision = self.db.get(SignalDecision, position.decision_id)
        self.assertEqual(decision.status, DecisionStatus.OPENED)
        self.assertEqual(decision.quantity, Decimal("0.125"))

        evaluated = [
            row for row in self._risk_events() if row.asset == "BTCUSDT"
        ]
        self.assertEqual(len(evaluated), 1)
        self.assertEqual(evaluated[0].result, RiskAction.RESIZED.value)

    def test_loop_calls_the_engine(self) -> None:
        module = importlib.import_module("app.services.bot_loop")
        source = inspect.getsource(module)
        self.assertIn("evaluate_open", source)


class IsolationTests(unittest.TestCase):
    """RF-9: el motor no importa IA (007) ni httpx (D-8)."""

    def test_engine_has_no_ai_or_httpx(self) -> None:
        module = importlib.import_module("app.services.risk_engine_service")
        source = inspect.getsource(module).lower()
        self.assertNotIn("httpx", source)
        self.assertNotIn("gemini", source)
        self.assertNotIn("ai_advisor", source)
        self.assertNotIn("aievaluation", source)

    def test_portfolio_math_is_pure(self) -> None:
        module = importlib.import_module("app.domain.portfolio_math")
        source = inspect.getsource(module).lower()
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("httpx", source)
        self.assertNotIn("app.services", source)


if __name__ == "__main__":
    unittest.main()

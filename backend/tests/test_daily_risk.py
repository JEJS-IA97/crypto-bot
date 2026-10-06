import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,)
from app.services.risk_guard_service import (
    COOLDOWN_SECONDS,
    DAILY_LOSS_LIMIT_PCT,
    MAX_OPENS_PER_DAY,
    can_open,
    get_daily_state,
    record_realized_pnl,
    register_open,
)

NOW = datetime(2026, 10, 1, 12, 0, 0)
DAY = date(2026, 10, 1)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class DailyRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.session = self.session_factory()

    def tearDown(self) -> None:
        self.session.close()

    def test_blocks_after_5pct_loss(self) -> None:
        state = get_daily_state(self.session, DAY, Decimal("20"))
        self.assertEqual(state.start_equity_usd, Decimal("20"))
        self.assertFalse(state.blocked)

        record_realized_pnl(self.session, state, Decimal("-0.99"))
        self.assertFalse(state.blocked)

        record_realized_pnl(self.session, state, Decimal("-0.01"))
        self.assertTrue(state.blocked)
        self.assertEqual(state.block_reason, "daily_loss_limit")

        allowed, reason = can_open(self.session, state, "BTCUSDT", NOW)
        self.assertFalse(allowed)
        self.assertEqual(reason, "daily_loss_limit")

        # El estado persiste entre sesiones (RF-4: se recalcula al arrancar).
        with self.session_factory() as fresh:
            persisted = get_daily_state(fresh, DAY, Decimal("20"))
            self.assertTrue(persisted.blocked)
            self.assertEqual(
                persisted.realized_pnl_usd, Decimal("-1.00")
            )

    def test_state_is_created_once_per_day(self) -> None:
        first = get_daily_state(self.session, DAY, Decimal("20"))
        second = get_daily_state(self.session, DAY, Decimal("999"))
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.start_equity_usd, Decimal("20"))

    def test_loss_limit_pct_is_five_percent(self) -> None:
        self.assertEqual(DAILY_LOSS_LIMIT_PCT, Decimal("5"))

    def test_rejects_non_decimal_amounts(self) -> None:
        state = get_daily_state(self.session, DAY, Decimal("20"))
        with self.assertRaises(TypeError):
            record_realized_pnl(self.session, state, -0.5)  # type: ignore[arg-type]


class OpenLimitAndCooldownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.session = self.session_factory()
        self.state = get_daily_state(self.session, DAY, Decimal("20"))

    def tearDown(self) -> None:
        self.session.close()

    def test_open_limit_and_cooldown(self) -> None:
        self.assertEqual(MAX_OPENS_PER_DAY, 10)
        self.assertEqual(COOLDOWN_SECONDS, 300)

        # Apertura reciente en BTCUSDT → cooldown activo solo para ese par.
        self.session.add(
            SignalDecision(
                client_order_id="dec-btc-recent",
                symbol="BTCUSDT",
                side=TradeSide.BUY,
                origin=DecisionOrigin.TECHNICAL,
                status=DecisionStatus.OPENED,
                config_json="{}",
                market_snapshot_json="{}",
                created_at=NOW - timedelta(seconds=100),
                updated_at=NOW - timedelta(seconds=100),
            )
        )
        self.session.commit()

        allowed, reason = can_open(self.session, self.state, "BTCUSDT", NOW)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cooldown")

        allowed, _ = can_open(self.session, self.state, "ETHUSDT", NOW)
        self.assertTrue(allowed)

        # Apertura antigua → el cooldown ya expiró.
        allowed, _ = can_open(
            self.session, self.state, "BTCUSDT", NOW + timedelta(seconds=301)
        )
        self.assertTrue(allowed)

        # Diez aperturas al día → límite diario.
        for index in range(MAX_OPENS_PER_DAY):
            register_open(self.session, self.state, "BTCUSDT")
        self.assertEqual(self.state.opens_count, MAX_OPENS_PER_DAY)
        allowed, reason = can_open(self.session, self.state, "ETHUSDT", NOW)
        self.assertFalse(allowed)
        self.assertEqual(reason, "daily_open_limit")

    def test_cooldown_uses_latest_opened_buy(self) -> None:
        self.session.add_all(
            [
                SignalDecision(
                    client_order_id="dec-btc-old",
                    symbol="BTCUSDT",
                    side=TradeSide.BUY,
                    origin=DecisionOrigin.TECHNICAL,
                    status=DecisionStatus.CLOSED,
                    config_json="{}",
                    market_snapshot_json="{}",
                    created_at=NOW - timedelta(seconds=900),
                    updated_at=NOW - timedelta(seconds=900),
                ),
                SignalDecision(
                    client_order_id="dec-btc-new",
                    symbol="BTCUSDT",
                    side=TradeSide.BUY,
                    origin=DecisionOrigin.EXTERNAL,
                    status=DecisionStatus.OPENED,
                    config_json="{}",
                    market_snapshot_json="{}",
                    created_at=NOW - timedelta(seconds=50),
                    updated_at=NOW - timedelta(seconds=50),
                ),
            ]
        )
        self.session.commit()

        allowed, reason = can_open(self.session, self.state, "BTCUSDT", NOW)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cooldown")

    def test_reentry_after_exit(self) -> None:
        # Pérdida por debajo del límite → no bloquea (RF-26).
        record_realized_pnl(self.session, self.state, Decimal("-0.50"))
        self.assertFalse(self.state.blocked)

        register_open(self.session, self.state, "ETHUSDT")
        allowed, _ = can_open(self.session, self.state, "ETHUSDT", NOW)
        self.assertTrue(allowed)

        # Tras cerrar con beneficio puede reabrir (sin bloqueo).
        record_realized_pnl(self.session, self.state, Decimal("0.20"))
        self.assertFalse(self.state.blocked)
        allowed, reason = can_open(self.session, self.state, "ADAUSDT", NOW)
        self.assertTrue(allowed, reason)

        # Pero el límite de aperturas del día sigue vigente.
        for _ in range(MAX_OPENS_PER_DAY - self.state.opens_count):
            register_open(self.session, self.state, "SOLUSDT")
        allowed, reason = can_open(self.session, self.state, "ADAUSDT", NOW)
        self.assertFalse(allowed)
        self.assertEqual(reason, "daily_open_limit")

    def test_rejected_decisions_do_not_start_cooldown(self) -> None:
        self.session.add(
            SignalDecision(
                client_order_id="dec-rejected",
                symbol="BNBUSDT",
                side=TradeSide.BUY,
                origin=DecisionOrigin.TECHNICAL,
                status=DecisionStatus.REJECTED,
                rejection_reason="daily_open_limit",
                config_json="{}",
                market_snapshot_json="{}",
                created_at=NOW - timedelta(seconds=10),
                updated_at=NOW - timedelta(seconds=10),
            )
        )
        self.session.commit()
        allowed, reason = can_open(self.session, self.state, "BNBUSDT", NOW)
        self.assertTrue(allowed, reason)

    def test_state_query_returns_single_row(self) -> None:
        rows = self.session.execute(
            select(type(self.state)).where(type(self.state).day == DAY)
        ).scalars().all()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()

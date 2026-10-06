import time
import unittest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    DailyRiskState,
    DecisionOrigin,
    DecisionStatus,
    PositionV2,
    SimulationMarketPrice,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.decision_store import get_metrics, record_decision
from app.services.simulation_service import create_simulation_account

DAY = date(2026, 10, 5)
HOUR_1 = datetime(2026, 10, 5, 10, 0, 0)
HOUR_2 = datetime(2026, 10, 5, 11, 0, 0)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class MetricsPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="metrics",
                initial_balance_usd=Decimal("50"),
            ),
        )

    def tearDown(self) -> None:
        self.db.close()

    def _closed_decision(
        self,
        *,
        symbol: str,
        pnl: Decimal,
        closed_at: datetime,
    ) -> None:
        decision = record_decision(
            self.db,
            symbol=symbol,
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
        )
        decision.status = DecisionStatus.CLOSED
        decision.pnl_usd = pnl
        decision.closed_at = closed_at
        self.db.commit()

    def test_metrics_payload(self) -> None:
        # PnL realizado + curva de equity para drawdown (RF-17):
        # 50 → 60 (pico) → 44 → drawdown = (60 − 44) / 60 = 26.67%.
        self._closed_decision(
            symbol="BTCUSDT",
            pnl=Decimal("10"),
            closed_at=HOUR_1,
        )
        self._closed_decision(
            symbol="ETHUSDT",
            pnl=Decimal("-16"),
            closed_at=HOUR_2,
        )

        # Posición abierta con precio de mercado → PnL no realizado.
        decision = record_decision(
            self.db,
            symbol="SOLUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
            quantity=Decimal("2"),
            price=Decimal("10"),
        )
        position = PositionV2(
            account_id=self.account.id,
            decision_id=decision.id,
            symbol="SOLUSDT",
            quantity=Decimal("2"),
            average_entry_price=Decimal("10"),
        )
        self.db.add(position)
        self.db.add(
            SimulationMarketPrice(
                symbol="SOLUSDT",
                price_usd=Decimal("12"),
                updated_at=HOUR_2,
            )
        )
        self.db.commit()

        # Estado del día con bloqueo → visible en el panel (RF-17/RF-4).
        self.db.add(
            DailyRiskState(
                day=DAY,
                start_equity_usd=Decimal("50"),
                realized_pnl_usd=Decimal("-4"),
                opens_count=3,
                blocked=True,
                block_reason="daily_loss_limit",
            )
        )
        self.db.commit()

        started = time.monotonic()
        payload = get_metrics(
            self.db,
            account_id=self.account.id,
            day=DAY,
            initial_equity=Decimal("50"),
        )
        elapsed = time.monotonic() - started

        # RF-17: latencia ≤5 s (consultas locales, sin red).
        self.assertLess(elapsed, 5)

        for key in (
            "generated_at",
            "available_usd",
            "market_value_usd",
            "balance_usd",
            "open_positions",
            "realized_pnl_usd",
            "unrealized_pnl_usd",
            "drawdown_pct",
            "opens_today",
            "daily_realized_pnl_usd",
            "daily_loss_usd",
            "daily_blocked",
            "block_reason",
        ):
            self.assertIn(key, payload)

        # Valores monetarios siempre Decimal (constitución #11).
        for key in (
            "available_usd",
            "market_value_usd",
            "balance_usd",
            "realized_pnl_usd",
            "unrealized_pnl_usd",
            "drawdown_pct",
            "daily_realized_pnl_usd",
            "daily_loss_usd",
        ):
            self.assertIsInstance(payload[key], Decimal, key)

        self.assertEqual(payload["available_usd"], Decimal("50"))
        self.assertEqual(payload["open_positions"], 1)
        # Suma neta de decisiones cerradas (RF-10): 10 − 16.
        self.assertEqual(payload["realized_pnl_usd"], Decimal("-6"))
        # 2 × (12 − 10) con precio de mercado disponible.
        self.assertEqual(payload["unrealized_pnl_usd"], Decimal("4"))
        self.assertEqual(payload["market_value_usd"], Decimal("24"))
        self.assertEqual(payload["balance_usd"], Decimal("74"))
        self.assertEqual(payload["drawdown_pct"], Decimal("26.67"))
        self.assertEqual(payload["opens_today"], 3)
        self.assertEqual(
            payload["daily_realized_pnl_usd"],
            Decimal("-4"),
        )
        self.assertEqual(payload["daily_loss_usd"], Decimal("4"))
        self.assertTrue(payload["daily_blocked"])
        self.assertEqual(
            payload["block_reason"],
            "daily_loss_limit",
        )


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.decision_store import (
    list_decisions,
    mark_rejected,
    record_decision,
)
from app.services.exchange_executor import OrderRequest
from app.services.order_lifecycle import check_exits, protection_after_fill
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import create_simulation_account

TICK = Decimal("0.01")


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class SnapshotAndResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="audit",
                initial_balance_usd=Decimal("50"),
            ),
        )
        self.executor = SimulationExecutor(self.db, self.account.id)

    def tearDown(self) -> None:
        self.db.close()

    def test_snapshot_and_result(self) -> None:
        # Emitir (RF-10, primer momento): snapshot de mercado + config.
        decision = record_decision(
            self.db,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={
                "ema_short_period": 20,
                "rsi_buy_max": Decimal("70"),
            },
            snapshot={
                "price": Decimal("100"),
                "candles": [
                    {"open": "99", "close": "100", "volume": "12.5"},
                ],
                "indicators": {
                    "ema_short": "101.5",
                    "ema_long": "99.25",
                    "rsi": "63.4",
                    "volume_ratio": "1.35",
                    "cross": "up",
                },
            },
            quantity=Decimal("0.1"),
            price=Decimal("100"),
        )
        self.assertEqual(decision.status, DecisionStatus.PENDING)
        self.assertTrue(decision.client_order_id.startswith("bot-"))
        self.assertLessEqual(len(decision.client_order_id), 36)
        self.assertIsNotNone(decision.created_at)
        self.assertIsNone(decision.rejection_reason)

        stored = self.db.get(SignalDecision, decision.id)
        config_back = json.loads(stored.config_json)
        self.assertEqual(config_back["ema_short_period"], 20)
        self.assertEqual(config_back["rsi_buy_max"], "70")
        snapshot_back = json.loads(stored.market_snapshot_json)
        self.assertEqual(snapshot_back["price"], "100")
        self.assertEqual(snapshot_back["indicators"]["cross"], "up")
        self.assertEqual(snapshot_back["candles"][0]["volume"], "12.5")

        # Cada decisión tiene su propio client_order_id (RF-25, idempotencia).
        other = record_decision(
            self.db,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
        )
        self.assertNotEqual(other.client_order_id, decision.client_order_id)
        listed = list_decisions(self.db)
        self.assertEqual(
            {item.id for item in listed},
            {decision.id, other.id},
        )

        # Cerrar (RF-10, segundo momento): el resultado va a la MISMA fila.
        fill = self.executor.place_order(
            OrderRequest(
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                quantity=Decimal("0.1"),
                price=Decimal("100"),
                client_order_id=decision.client_order_id,
            )
        )
        position = PositionV2(
            account_id=self.account.id,
            decision_id=decision.id,
            symbol="BTCUSDT",
            quantity=fill.executed_quantity,
            average_entry_price=fill.average_price,
            entry_fee_usd=fill.fee or Decimal("0"),
        )
        self.db.add(position)
        self.db.commit()
        position = protection_after_fill(
            self.db,
            position=position,
            decision=decision,
            fill=fill,
            tick_size=TICK,
        )
        self.assertEqual(decision.status, DecisionStatus.OPENED)

        closed = check_exits(
            self.db,
            position=position,
            decision=decision,
            executor=self.executor,
            current_price=Decimal("104"),
        )
        self.assertIsNotNone(closed)

        self.db.refresh(decision)
        self.assertEqual(decision.status, DecisionStatus.CLOSED)
        self.assertIsNotNone(decision.filled_at)
        self.assertIsNotNone(decision.closed_at)
        # Take-profit a 102 (D-11): comisiones y PnL del cierre en 102.
        self.assertEqual(decision.fees_usd, Decimal("0.0202"))
        self.assertEqual(decision.pnl_usd, Decimal("0.1798"))

        # El snapshot emitido queda intacto tras el cierre.
        after = json.loads(decision.market_snapshot_json)
        self.assertEqual(after, snapshot_back)

    def test_rejected_decision_keeps_reason(self) -> None:
        decision = record_decision(
            self.db,
            symbol="BTCUSDT",
            side=TradeSide.SELL,
            origin=DecisionOrigin.EXTERNAL,
            source="copia-proveedor",
            config={},
            snapshot={"price": "100"},
        )
        marked = mark_rejected(
            self.db,
            decision,
            "signal_expired",
        )
        self.assertEqual(marked.status, DecisionStatus.REJECTED)
        self.assertEqual(marked.rejection_reason, "signal_expired")

        rejected = list_decisions(
            self.db,
            status=DecisionStatus.REJECTED,
        )
        self.assertEqual([item.id for item in rejected], [decision.id])


if __name__ == "__main__":
    unittest.main()

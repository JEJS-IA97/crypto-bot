import unittest
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    DecisionOrigin,
    PositionV2,
    SimulationTrade,
    TradeSide,
)
from app.schemas import (
    SimulationAccountCreate,
    SimulationOrderRequest,
    TradeHistoryResponse,
    TradeResponse,
)
from app.services.decision_store import record_decision
from app.services.exchange_executor import OrderRequest
from app.services.order_lifecycle import check_exits, protection_after_fill
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import (
    create_simulation_account,
    execute_order,
    get_trades,
)

TICK = Decimal("0.01")


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TradeDecisionLinkTests(unittest.TestCase):
    """RF-7 (009): el trade de equity enlaza con su decisión."""

    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="link",
                initial_balance_usd=Decimal("50"),
            ),
        )
        self.executor = SimulationExecutor(self.db, self.account.id)

    def tearDown(self) -> None:
        self.db.close()

    def test_bot_open_and_close_link_trades_to_decision(self) -> None:
        decision = record_decision(
            self.db,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={
                "price": "100",
                "correlation_id": "corr-link-1",
            },
            quantity=Decimal("0.1"),
            price=Decimal("100"),
        )

        entry_fill = self.executor.place_order(
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
            quantity=entry_fill.executed_quantity,
            average_entry_price=entry_fill.average_price,
            entry_fee_usd=entry_fill.fee or Decimal("0"),
        )
        self.db.add(position)
        self.db.commit()
        position = protection_after_fill(
            self.db,
            position=position,
            decision=decision,
            fill=entry_fill,
            tick_size=TICK,
        )
        self.assertEqual(position.status.value, "OPEN")

        entry_trade_id = int(entry_fill.raw["simulation_trade_id"])
        entry_trade = self.db.get(SimulationTrade, entry_trade_id)
        self.assertEqual(entry_trade.decision_id, decision.id)

        closed = check_exits(
            self.db,
            position=position,
            decision=decision,
            executor=self.executor,
            current_price=Decimal("104"),
        )
        self.assertIsNotNone(closed)

        trades = get_trades(self.db, self.account.id)
        self.assertEqual(len(trades), 2)
        sides = {trade.side: trade for trade in trades}
        self.assertEqual(
            sides[TradeSide.BUY].decision_id, decision.id
        )
        self.assertEqual(
            sides[TradeSide.SELL].decision_id, decision.id
        )

        payload = TradeHistoryResponse.model_validate(
            sides[TradeSide.BUY]
        )
        self.assertEqual(payload.decision_id, decision.id)

    def test_manual_order_without_decision_stays_unlinked(
        self,
    ) -> None:
        trade = execute_order(
            self.db,
            self.account.id,
            SimulationOrderRequest(
                symbol="BTCUSDT",
                side=TradeSide.BUY,
                quantity=Decimal("0.05"),
                price=Decimal("100"),
            ),
        )
        self.assertIsNone(trade.decision_id)

        payload = TradeResponse.model_validate(trade)
        self.assertIsNone(payload.decision_id)

        listed = get_trades(self.db, self.account.id)
        self.assertEqual(len(listed), 1)
        self.assertIsNone(listed[0].decision_id)


if __name__ == "__main__":
    unittest.main()

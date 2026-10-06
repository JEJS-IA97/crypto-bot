import json
import unittest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.risk_math import estimated_loss_usd
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.exchange_executor import OrderRequest
from app.services.order_lifecycle import (
    check_exits,
    close_position,
    has_position_error,
    list_incidents,
    protection_after_fill,
)
from app.services.risk_guard_service import can_open, get_daily_state
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import (
    create_simulation_account,
    get_balance_record,
)

TICK = Decimal("0.01")
NOW = datetime(2026, 10, 5, 12, 0, 0)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class OrderLifecycleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="lifecycle",
                initial_balance_usd=Decimal("50"),
            ),
        )
        self.executor = SimulationExecutor(self.db, self.account.id)
        self._counter = 0

    def tearDown(self) -> None:
        self.db.close()

    def _make_decision(
        self, symbol: str, *, price: Decimal, quantity: Decimal
    ) -> SignalDecision:
        self._counter += 1
        decision = SignalDecision(
            client_order_id=f"lc-{self._counter}",
            symbol=symbol,
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            status=DecisionStatus.PENDING,
            config_json="{}",
            market_snapshot_json="{}",
            price=price,
            quantity=quantity,
        )
        self.db.add(decision)
        self.db.commit()
        return decision

    def _open_position(
        self,
        *,
        symbol: str,
        quantity: Decimal,
        fill_price: Decimal,
        decision_price: Decimal | None = None,
    ) -> tuple[SignalDecision, PositionV2, object]:
        decision = self._make_decision(
            symbol,
            price=(
                decision_price if decision_price is not None else fill_price
            ),
            quantity=quantity,
        )
        fill = self.executor.place_order(
            OrderRequest(
                symbol=symbol,
                side="BUY",
                order_type="LIMIT",
                quantity=quantity,
                price=fill_price,
                client_order_id=decision.client_order_id,
            )
        )
        position = PositionV2(
            account_id=self.account.id,
            decision_id=decision.id,
            symbol=symbol,
            quantity=fill.executed_quantity,
            average_entry_price=fill.average_price,
            entry_fee_usd=fill.fee or Decimal("0"),
        )
        self.db.add(position)
        self.db.commit()
        return decision, position, fill

    def _protect(
        self,
        decision: SignalDecision,
        position: PositionV2,
        fill=None,
        placer=None,
    ) -> PositionV2:
        return protection_after_fill(
            self.db,
            position=position,
            decision=decision,
            fill=fill,
            tick_size=TICK,
            placer=placer,
        )


class StopTakeProtectionTests(OrderLifecycleTestCase):
    def test_stop_loss_and_take_profit_mutual_cancel(self) -> None:
        dec_btc, pos_btc, fill_btc = self._open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        pos_btc = self._protect(dec_btc, pos_btc, fill=fill_btc)

        self.assertEqual(pos_btc.stop_price, Decimal("98"))
        self.assertEqual(pos_btc.take_profit_price, Decimal("104"))
        self.assertEqual(
            pos_btc.stop_order_id, f"sim-stop-{pos_btc.id}"
        )
        self.assertEqual(pos_btc.tp_order_id, f"sim-tp-{pos_btc.id}")
        self.assertEqual(pos_btc.status, PositionStatus.OPEN)
        self.assertEqual(dec_btc.status, DecisionStatus.OPENED)
        self.assertIsNotNone(dec_btc.filled_at)
        self.assertEqual(dec_btc.stop_price, Decimal("98"))
        self.assertEqual(dec_btc.take_profit_price, Decimal("104"))

        dec_eth, pos_eth, fill_eth = self._open_position(
            symbol="ETHUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        pos_eth = self._protect(dec_eth, pos_eth, fill=fill_eth)

        # El stop salta primero → se cancela el take-profit (RF-13).
        closed = check_exits(
            self.db,
            position=pos_btc,
            decision=dec_btc,
            executor=self.executor,
            current_price=Decimal("97.5"),
        )
        self.assertIsNotNone(closed)
        self.assertEqual(closed.status, PositionStatus.STOPPED)
        self.assertEqual(
            closed.stop_order_id, f"sim-stop-{pos_btc.id}"
        )
        self.assertIsNone(closed.tp_order_id)
        self.assertIsNotNone(closed.closed_at)
        self.assertEqual(dec_btc.status, DecisionStatus.CLOSED)
        self.assertIsNotNone(dec_btc.closed_at)
        self.assertIsNotNone(dec_btc.pnl_usd)
        self.assertIsNotNone(dec_btc.fees_usd)

        # El take-profit salta primero → se cancela el stop (RF-13).
        closed_eth = check_exits(
            self.db,
            position=pos_eth,
            decision=dec_eth,
            executor=self.executor,
            current_price=Decimal("105"),
        )
        self.assertIsNotNone(closed_eth)
        self.assertEqual(closed_eth.status, PositionStatus.TAKE_PROFIT)
        self.assertEqual(
            closed_eth.tp_order_id, f"sim-tp-{pos_eth.id}"
        )
        self.assertIsNone(closed_eth.stop_order_id)
        self.assertEqual(dec_eth.status, DecisionStatus.CLOSED)

        # Posición que no toca ninguno → sigue abierta con ambas órdenes.
        dec_sol, pos_sol, fill_sol = self._open_position(
            symbol="SOLUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        pos_sol = self._protect(dec_sol, pos_sol, fill=fill_sol)
        untouched = check_exits(
            self.db,
            position=pos_sol,
            decision=dec_sol,
            executor=self.executor,
            current_price=Decimal("101"),
        )
        self.assertIsNone(untouched)
        self.assertEqual(pos_sol.status, PositionStatus.OPEN)
        self.assertIsNotNone(pos_sol.stop_order_id)
        self.assertIsNotNone(pos_sol.tp_order_id)

    def test_stop_loss_capped_1usd(self) -> None:
        # 0.6 × (100 − 98) = 1.2 USD de pérdida con stop > 1 USD →
        # el ciclo de vida reduce el tamaño (RF-13).
        decision = self._make_decision(
            "BTCUSDT",
            price=Decimal("100"),
            quantity=Decimal("0.6"),
        )
        position = PositionV2(
            account_id=self.account.id,
            decision_id=decision.id,
            symbol="BTCUSDT",
            quantity=Decimal("0.6"),
            average_entry_price=Decimal("100"),
        )
        self.db.add(position)
        self.db.commit()

        position = self._protect(decision, position)

        self.assertEqual(position.quantity, Decimal("0.5"))
        self.assertEqual(decision.quantity, Decimal("0.5"))
        self.assertEqual(position.stop_price, Decimal("98"))
        self.assertEqual(position.status, PositionStatus.OPEN)

        loss = estimated_loss_usd(
            entry_price=position.average_entry_price,
            stop_price=position.stop_price,
            quantity=position.quantity,
        )
        self.assertLessEqual(loss, Decimal("1"))

    def test_error_without_stop(self) -> None:
        def failing_placer(position, stop_price, tp_price):
            raise RuntimeError("OCO rejected")

        decision, position, fill = self._open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        position = self._protect(
            decision, position, fill=fill, placer=failing_placer
        )

        self.assertEqual(position.status, PositionStatus.ERROR)
        self.assertIsNone(position.stop_order_id)
        self.assertIsNone(position.tp_order_id)
        self.assertEqual(decision.status, DecisionStatus.ERROR)
        self.assertIsNotNone(decision.filled_at)

        incidents = list_incidents(self.db)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].kind, "stop_placement_failed")
        self.assertEqual(incidents[0].symbol, "BTCUSDT")
        details = json.loads(incidents[0].details)
        self.assertIn("OCO rejected", details["error"])

        # Sin stop no se abren posiciones nuevas hasta resolverlo (RF-13).
        self.assertTrue(has_position_error(self.db))
        state = get_daily_state(self.db, date(2026, 10, 5), Decimal("20"))
        ok, reason = can_open(self.db, state, "SOLUSDT", NOW)
        self.assertFalse(ok)
        self.assertEqual(reason, "position_error")

        # Reintentar la colocación resuelve el bloqueo.
        position = self._protect(decision, position)
        self.assertEqual(position.status, PositionStatus.OPEN)
        self.assertIsNotNone(position.stop_order_id)
        self.assertIsNotNone(position.tp_order_id)
        self.assertEqual(decision.status, DecisionStatus.OPENED)
        self.assertFalse(has_position_error(self.db))
        ok, reason = can_open(self.db, state, "SOLUSDT", NOW)
        self.assertTrue(ok)
        self.assertEqual(reason, "")


class FeesAndSlippageTests(OrderLifecycleTestCase):
    def test_fees_in_pnl(self) -> None:
        decision, position, fill = self._open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        position = self._protect(decision, position, fill=fill)
        self.assertEqual(position.entry_fee_usd, Decimal("0.01"))

        closed = check_exits(
            self.db,
            position=position,
            decision=decision,
            executor=self.executor,
            current_price=Decimal("104"),
        )
        self.assertEqual(closed.status, PositionStatus.TAKE_PROFIT)

        self.assertEqual(decision.status, DecisionStatus.CLOSED)
        self.assertIsNotNone(decision.closed_at)
        # Comisión 0.1% por lado: 0.01 (compra) + 0.0104 (venta).
        self.assertEqual(decision.fees_usd, Decimal("0.0204"))
        # PnL neto: 0.1 × (104 − 100) − 0.01 − 0.0104 = 0.3796.
        self.assertEqual(decision.pnl_usd, Decimal("0.3796"))

        # El saldo confirma la comisión en ambos lados:
        # 50 − 10.01 + 10.4 − 0.0104 = 50.3796.
        balance = get_balance_record(self.db, self.account.id)
        self.assertEqual(
            balance.available_usd, Decimal("50.3796")
        )

    def test_slippage_reported(self) -> None:
        # Fill de entrada a 100 con precio esperado 99.4 → 0.6% > 0.5%.
        dec_a, pos_a, fill_a = self._open_position(
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
            decision_price=Decimal("99.4"),
        )
        self._protect(dec_a, pos_a, fill=fill_a)

        incidents = list_incidents(self.db)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].kind, "slippage_exceeded")
        details = json.loads(incidents[0].details)
        self.assertEqual(details["phase"], "entry")
        self.assertEqual(Decimal(details["expected"]), Decimal("99.4"))
        self.assertEqual(Decimal(details["executed"]), Decimal("100"))

        # Salida con slippage 0.61% > 0.5% → incidente, sin abortar
        # el cierre (RF-24: el stop ya protege la posición).
        dec_b, pos_b, fill_b = self._open_position(
            symbol="ETHUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        pos_b = self._protect(dec_b, pos_b, fill=fill_b)
        self.assertEqual(len(list_incidents(self.db)), 1)

        closed = close_position(
            self.db,
            position=pos_b,
            decision=dec_b,
            executor=self.executor,
            exit_price=Decimal("97.4"),
            expected_price=pos_b.stop_price,
            reason="stop",
        )
        self.assertEqual(closed.status, PositionStatus.STOPPED)
        self.assertEqual(dec_b.status, DecisionStatus.CLOSED)

        incidents = list_incidents(self.db)
        self.assertEqual(len(incidents), 2)
        details = json.loads(incidents[1].details)
        self.assertEqual(details["phase"], "exit")
        self.assertEqual(
            Decimal(details["expected"]), pos_b.stop_price
        )
        self.assertEqual(
            Decimal(details["executed"]), Decimal("97.4")
        )

        # Slippage exactamente 0.5% → no supera el máximo, sin incidente.
        dec_c, pos_c, fill_c = self._open_position(
            symbol="SOLUSDT",
            quantity=Decimal("0.1"),
            fill_price=Decimal("100"),
        )
        pos_c = self._protect(dec_c, pos_c, fill=fill_c)
        closed = close_position(
            self.db,
            position=pos_c,
            decision=dec_c,
            executor=self.executor,
            exit_price=Decimal("97.51"),
            expected_price=pos_c.stop_price,
            reason="stop",
        )
        self.assertEqual(closed.status, PositionStatus.STOPPED)
        self.assertEqual(len(list_incidents(self.db)), 2)


if __name__ == "__main__":
    unittest.main()

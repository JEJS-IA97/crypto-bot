import unittest
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    BotPhaseName,
    DailyRiskState,
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)

NEW_TABLES = (
    "signal_decisions",
    "position_v2s",
    "daily_risk_states",
    "bot_phases",
    "bot_runtimes",
    "system_events",
    "source_health",
)

FROZEN_TABLES = {
    "simulation_arbitrages": {
        "id", "account_id", "symbol", "base_asset", "quote_currency",
        "buy_exchange", "sell_exchange", "quantity", "buy_price", "sell_price",
        "buy_total_usd", "buy_fee_usd", "sell_total_usd", "sell_fee_usd",
        "net_profit_usd", "executed_at",
    },
    "simulation_bot_cycles": {
        "id", "account_id", "executed_at", "decision", "reason",
        "evaluated_symbols_json", "trade_candidates", "best_symbol",
        "best_profit_usd", "best_profit_percent",
    },
}


class NewModelTablesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.inspector = inspect(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_tables_created_and_frozen_untouched(self) -> None:
        names = set(self.inspector.get_table_names())
        for table in NEW_TABLES:
            self.assertIn(table, names)
        for table, expected_columns in FROZEN_TABLES.items():
            self.assertIn(table, names)
            actual = {c["name"] for c in self.inspector.get_columns(table)}
            self.assertEqual(actual, expected_columns)

    def test_client_order_id_unique(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO signal_decisions "
                "(client_order_id, symbol, side, origin, status, config_json, "
                " market_snapshot_json, created_at, updated_at) "
                "VALUES ('dec-1', 'BTCUSDT', 'BUY', 'TECHNICAL', 'PENDING', '{}', "
                " '{}', '2026-10-01 00:00:00', '2026-10-01 00:00:00')"
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO signal_decisions "
                "(client_order_id, symbol, side, origin, status, config_json, "
                " market_snapshot_json, created_at, updated_at) "
                "VALUES ('dec-1', 'ETHUSDT', 'BUY', 'EXTERNAL', 'PENDING', '{}', "
                " '{}', '2026-10-01 00:00:01', '2026-10-01 00:00:01')"
            )

    def test_daily_risk_day_unique(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO daily_risk_states "
                "(day, start_equity_usd, realized_pnl_usd, opens_count, blocked) "
                "VALUES ('2026-10-01', 20.0, 0.0, 0, 0)"
            )
        with self.assertRaises(IntegrityError), self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO daily_risk_states "
                "(day, start_equity_usd, realized_pnl_usd, opens_count, blocked) "
                "VALUES ('2026-10-01', 20.0, 0.0, 0, 0)"
            )

    def test_position_requires_valid_decision(self) -> None:
        with self.assertRaises(IntegrityError), self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO position_v2s "
                "(account_id, decision_id, symbol, quantity, average_entry_price, "
                " entry_fee_usd, status, opened_at) "
                "VALUES (1, 999, 'BTCUSDT', 0.001, 50000.0, 0.0, 'OPEN', "
                " '2026-10-01 00:00:00')"
            )

    def test_defaults(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO bot_runtimes (id, running, breaker_active, "
                "consecutive_failures, updated_at) "
                "VALUES (1, 1, 0, 0, '2026-10-01 00:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO bot_phases (phase, changed_at, evidence_json, "
                "changed_by) VALUES ('SIMULATION', '2026-10-01 00:00:00', "
                " '{}', 'system')"
            )
            running = conn.exec_driver_sql(
                "SELECT running, breaker_active FROM bot_runtimes"
            ).fetchone()
            phase = conn.exec_driver_sql(
                "SELECT phase FROM bot_phases"
            ).fetchone()
        self.assertEqual(running[0], 1)
        self.assertEqual(running[1], 0)
        self.assertEqual(phase[0], "SIMULATION")

    def test_orm_models_use_enums_and_decimal(self) -> None:
        self.assertEqual(TradeSide.BUY.value, "BUY")
        self.assertEqual(DecisionOrigin.EXTERNAL.value, "EXTERNAL")
        self.assertEqual(DecisionStatus.REJECTED.value, "REJECTED")
        self.assertEqual(PositionStatus.STOPPED.value, "STOPPED")
        self.assertEqual(BotPhaseName.LIVE.value, "LIVE")
        self.assertIs(
            SignalDecision.__table__.columns["client_order_id"].unique,
            True,
        )
        self.assertIs(
            DailyRiskState.__table__.columns["day"].unique,
            True,
        )
        self.assertIs(
            PositionV2.__table__.columns["quantity"].type.asdecimal,
            True,
        )
        self.assertIs(
            SignalDecision.__table__.columns["pnl_usd"].type.asdecimal,
            True,
        )

    def test_persisted_amounts_come_back_as_decimal(self) -> None:
        from sqlalchemy import select
        from sqlalchemy.orm import sessionmaker

        session_factory = sessionmaker(bind=self.engine)
        with session_factory() as session:
            session.add(
                DailyRiskState(
                    day=date(2026, 10, 1),
                    start_equity_usd=Decimal("20.00000000"),
                    realized_pnl_usd=Decimal("-0.05000000"),
                    opens_count=1,
                    blocked=False,
                )
            )
            session.commit()

        with session_factory() as session:
            row = session.execute(
                select(DailyRiskState)
            ).scalar_one()

        self.assertIsInstance(row.start_equity_usd, Decimal)
        self.assertIsInstance(row.realized_pnl_usd, Decimal)
        self.assertEqual(row.realized_pnl_usd, Decimal("-0.05"))


if __name__ == "__main__":
    unittest.main()

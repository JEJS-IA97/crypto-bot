import unittest
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    BotPhase,
    BotPhaseName,
    DailyRiskState,
    DecisionOrigin,
    TradeSide,
    utc_now,
)
from app.schemas import SimulationAccountCreate
from app.services.decision_store import mark_rejected, record_decision
from app.services.report_service import build_daily_report
from app.services.risk_guard_service import get_runtime
from app.services.simulation_service import create_simulation_account

ACCOUNT_ID = settings.simulation_bot_account_id


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def _seed_account(self) -> None:
        account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="report",
                initial_balance_usd=Decimal("20"),
            ),
        )
        self.assertEqual(account.id, ACCOUNT_ID)

    def test_empty_database_report_shows_sin_datos(self) -> None:
        report = build_daily_report(self.db)
        lines = report.splitlines()
        self.assertTrue(lines[0].startswith("Informe diario — crypto-bot — "))
        self.assertTrue(lines[0].endswith(" (UTC)"))
        self.assertIn("Fase: SIMULATION", report)
        self.assertIn("Estado: activo", report)
        self.assertIn("Balance: sin datos", report)
        self.assertIn("PnL: sin datos", report)
        self.assertIn("Día UTC: sin datos", report)
        self.assertIn("Últimas 24 h: sin datos", report)
        self.assertIn("Breaker: inactivo", report)

    def test_report_shows_metrics_and_daily_state(self) -> None:
        self._seed_account()
        today = utc_now().date()
        self.db.add(
            DailyRiskState(
                day=today,
                start_equity_usd=Decimal("20"),
                realized_pnl_usd=Decimal("-0.5"),
                opens_count=5,
                blocked=True,
                block_reason="pérdida diaria ≥5%",
            )
        )
        self.db.commit()

        report = build_daily_report(self.db)
        self.assertIn("Fase: SIMULATION", report)
        self.assertIn("Estado: activo", report)
        self.assertIn("disponible 20.00000000 USDT", report)
        self.assertIn("posiciones 0.00000000 USDT", report)
        self.assertIn("total 20.00000000 USDT", report)
        self.assertIn("realizado 0.00000000 USDT", report)
        self.assertIn("no realizado 0.00000000 USDT", report)
        self.assertIn("drawdown 0.00%", report)
        self.assertIn("pérdida 0.50000000 USDT", report)
        self.assertIn("bloqueado: sí", report)
        self.assertIn("pérdida diaria ≥5%", report)
        self.assertIn("aperturas 5/10", report)
        self.assertIn("posiciones abiertas 0/3", report)

    def test_last_24h_summary_counts_and_reasons(self) -> None:
        self._seed_account()
        now = utc_now()

        old = record_decision(
            self.db,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
        )
        old.created_at = now - timedelta(hours=25)
        self.db.commit()

        rejected = record_decision(
            self.db,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.EXTERNAL,
            config={},
            snapshot={},
        )
        mark_rejected(self.db, rejected, "precio fuera de rango")

        opened = record_decision(
            self.db,
            symbol="SOLUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
        )
        opened.status = opened.status.OPENED
        self.db.commit()

        report = build_daily_report(self.db, now=now)
        self.assertIn("Últimas 24 h: 2 decisiones", report)
        self.assertIn("ejecutadas 1", report)
        self.assertIn("rechazadas 1", report)
        self.assertIn("precio fuera de rango", report)

    def test_state_and_breaker_lines(self) -> None:
        runtime = get_runtime(self.db)
        runtime.breaker_active = True
        runtime.breaker_reason = "5 fallos consecutivos"
        runtime.consecutive_failures = 5
        self.db.commit()

        report = build_daily_report(self.db)
        self.assertIn("Estado: bloqueado (5 fallos consecutivos)", report)
        self.assertIn("Breaker: activo (5 fallos consecutivos)", report)

        runtime.breaker_active = False
        runtime.running = False
        runtime.breaker_reason = None
        runtime.consecutive_failures = 0
        self.db.commit()

        report = build_daily_report(self.db)
        self.assertIn("Estado: detenido", report)
        self.assertIn("Breaker: inactivo", report)

    def test_phase_line_reflects_database(self) -> None:
        phase = self.db.get(BotPhase, 1)
        if phase is None:
            phase = BotPhase(id=1, phase=BotPhaseName.SIMULATION)
            self.db.add(phase)
        phase.phase = BotPhaseName.TESTNET
        self.db.commit()

        report = build_daily_report(self.db)
        self.assertIn("Fase: TESTNET", report)


if __name__ == "__main__":
    unittest.main()

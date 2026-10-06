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
from app.services.report_service import build_daily_report, build_daily_report_html
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


class ReportHtmlTests(unittest.TestCase):
    """Spec 004: informe HTML con el diseño del panel (design.json)."""

    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def test_html_structure_and_frontend_palette(self) -> None:
        html = build_daily_report_html(self.db)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        for token in (
            "#1d1e21",
            "#202124",
            "#27e7cf",
            "#929292",
            "#303236",
            "#f2f2f2",
        ):
            self.assertIn(token, html)
        self.assertIn("Informe diario", html)
        self.assertIn("SIMULATION", html)
        self.assertIn("Breaker", html)

    def test_html_shows_sin_datos_on_empty_database(self) -> None:
        html = build_daily_report_html(self.db)
        self.assertIn("sin datos", html)
        self.assertIn("inactivo", html)

    def test_html_shows_same_values_as_text_report(self) -> None:
        account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="report-html",
                initial_balance_usd=Decimal("20"),
            ),
        )
        self.assertEqual(account.id, ACCOUNT_ID)
        self.db.add(
            DailyRiskState(
                day=utc_now().date(),
                start_equity_usd=Decimal("20"),
                realized_pnl_usd=Decimal("-0.5"),
                opens_count=5,
                blocked=True,
                block_reason="pérdida diaria ≥5%",
            )
        )
        self.db.commit()

        text = build_daily_report(self.db)
        html = build_daily_report_html(self.db)

        for fragment in (
            "20.00000000",
            "0.50000000",
            "pérdida diaria ≥5%",
            "5/10",
        ):
            self.assertIn(fragment, text)
            self.assertIn(fragment, html)

    def test_html_escapes_dynamic_values_from_database(self) -> None:
        runtime = get_runtime(self.db)
        runtime.breaker_active = True
        runtime.breaker_reason = "<script>alert('x')</script>"
        self.db.commit()

        html = build_daily_report_html(self.db)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_text_report_contract_unchanged(self) -> None:
        report = build_daily_report(self.db)
        self.assertIn("Fase: SIMULATION", report)
        self.assertIn("Balance: sin datos", report)


if __name__ == "__main__":
    unittest.main()

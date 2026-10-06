"""Tests del servicio de fases (spec 001, RF-16, RF-2 / D-9, D-7)."""

import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    BotPhase,
    BotPhaseName,
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,
    utc_now,
)
from app.services.phase_service import (
    get_phase,
    live_trading_blockers,
    request_phase_change,
)

BACKTEST_EVIDENCE = {
    "backtest_validation_net_pnl": "1.2",
    "backtest_test_net_pnl": "0.8",
}


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class PhaseServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def _add_ops(
        self,
        count: int,
        *,
        created_days_ago: int,
        pnl_each: Decimal,
        closed_days_ago: int = 0,
    ) -> None:
        """Inserta `count` decisiones cerradas (operaciones completadas)."""
        now = utc_now()
        created = now - timedelta(days=created_days_ago)
        closed = now - timedelta(days=closed_days_ago)
        for index in range(count):
            self.db.add(
                SignalDecision(
                    client_order_id=f"bot-phase-{created_days_ago}-{index}",
                    symbol="BTCUSDT",
                    side=TradeSide.BUY,
                    origin=DecisionOrigin.TECHNICAL,
                    config_json="{}",
                    market_snapshot_json="{}",
                    status=DecisionStatus.CLOSED,
                    pnl_usd=pnl_each,
                    created_at=created,
                    closed_at=closed,
                )
            )
        self.db.commit()

    def _add_drawdown_ops(self) -> None:
        """15 ops, 31 días, PnL total >0 pero drawdown >10% (D-9)."""
        now = utc_now()
        created = now - timedelta(days=31)
        pnls = [Decimal("2"), Decimal("-3")] + [Decimal("0.3")] * 13
        for index, pnl in enumerate(pnls):
            self.db.add(
                SignalDecision(
                    client_order_id=f"bot-dd-{index}",
                    symbol="BTCUSDT",
                    side=TradeSide.BUY,
                    origin=DecisionOrigin.TECHNICAL,
                    config_json="{}",
                    market_snapshot_json="{}",
                    status=DecisionStatus.CLOSED,
                    pnl_usd=pnl,
                    created_at=created,
                    closed_at=now - timedelta(minutes=5),
                )
            )
        self.db.commit()

    @staticmethod
    def _criteria(result: dict) -> list[str]:
        return [item["criterion"] for item in result["missing"]]

    def test_requires_30d_15ops_drawdown(self) -> None:
        # Pocos días y pocas operaciones → bloquea con el detalle (RF-16).
        self._add_ops(3, created_days_ago=5, pnl_each=Decimal("0.1"))
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.TESTNET,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertFalse(result["ok"])
        criteria = self._criteria(result)
        self.assertIn("paper_days", criteria)
        self.assertIn("operations", criteria)
        self.assertEqual(get_phase(self.db).phase, BotPhaseName.SIMULATION)

        # 30 días y 15 ops con PnL>0, pero drawdown >10% y sin backtest.
        self.db.rollback()
        self._add_drawdown_ops()
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.TESTNET,
            evidence=None,
        )
        self.assertFalse(result["ok"])
        criteria = self._criteria(result)
        self.assertIn("drawdown_pct", criteria)
        self.assertIn("backtest_validation", criteria)
        self.assertIn("backtest_test", criteria)
        self.assertNotIn("paper_days", criteria)
        self.assertNotIn("operations", criteria)
        self.assertEqual(get_phase(self.db).phase, BotPhaseName.SIMULATION)

    def test_promotes_when_criteria_met(self) -> None:
        # Todo el criterio D-9 cumplido → la fase cambia y guarda la evidencia.
        self._add_ops(15, created_days_ago=31, pnl_each=Decimal("0.1"))
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.TESTNET,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertTrue(result["ok"], result)
        phase = get_phase(self.db)
        self.assertEqual(phase.phase, BotPhaseName.TESTNET)
        self.assertIn("paper_days", phase.evidence_json)
        self.assertIn("backtest_test_net_pnl", phase.evidence_json)

    def test_refuses_live_without_capital(self) -> None:
        # Fase no real con ALLOW_LIVE_TRADING=true → rechazo visible (RF-2).
        phase = get_phase(self.db)
        phase.phase = BotPhaseName.TESTNET
        self.db.commit()
        with patch.object(settings, "allow_live_trading", True):
            blockers = live_trading_blockers(self.db)
        self.assertIn(
            "phase_not_live",
            [blocker["reason"] for blocker in blockers],
        )

        # Sin aporte configurado → también bloquea el real (RF-2, D-7:
        # el límite es sobre lo aportado; aportar más es subir CONFIGURED).
        phase.phase = BotPhaseName.LIVE
        self.db.commit()
        with patch.object(
            settings, "allow_live_trading", True
        ), patch.object(settings, "configured_capital_usd", Decimal("0")):
            blockers = live_trading_blockers(self.db)
        self.assertIn(
            "no_capital_configured",
            [blocker["reason"] for blocker in blockers],
        )

        # Fase real y aporte configurado → ningún bloqueo.
        with patch.object(settings, "allow_live_trading", True):
            self.assertEqual(live_trading_blockers(self.db), [])

    def test_live_requires_profitable_testnet(self) -> None:
        # Entra en TESTNET con métricas de papel cumplidas.
        self._add_ops(15, created_days_ago=31, pnl_each=Decimal("0.1"))
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.TESTNET,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertTrue(result["ok"], result)

        # Sin operaciones rentables durante TESTNET → bloquea (RF-16).
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.LIVE,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertFalse(result["ok"])
        self.assertIn("testnet_profitable", self._criteria(result))
        self.assertEqual(get_phase(self.db).phase, BotPhaseName.TESTNET)

        # Operaciones cerradas dentro de TESTNET con PnL>0 → pasa a LIVE.
        now = utc_now()
        for index in range(3):
            self.db.add(
                SignalDecision(
                    client_order_id=f"bot-tn-{index}",
                    symbol="ETHUSDT",
                    side=TradeSide.BUY,
                    origin=DecisionOrigin.TECHNICAL,
                    config_json="{}",
                    market_snapshot_json="{}",
                    status=DecisionStatus.CLOSED,
                    pnl_usd=Decimal("0.2"),
                    created_at=now - timedelta(days=1),
                    closed_at=now,
                )
            )
        self.db.commit()
        # La fase TESTNET se registró hace instantes; las ops nuevas cierran
        # después → PnL de testnet > 0.
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.LIVE,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(get_phase(self.db).phase, BotPhaseName.LIVE)

    def test_rejects_non_consecutive_phase(self) -> None:
        result = request_phase_change(
            self.db,
            new_phase=BotPhaseName.LIVE,
            evidence=BACKTEST_EVIDENCE,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "non_consecutive_phase")
        self.assertEqual(
            db_phase_count(self.db),
            1,
        )


def db_phase_count(db) -> int:
    return db.scalar(select(func.count()).select_from(BotPhase)) or 0


if __name__ == "__main__":
    unittest.main()

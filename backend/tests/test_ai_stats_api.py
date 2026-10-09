"""Tests rojos — Spec 009: agregados de IA para el header (RF-1).

``GET /api/bot/ai/stats``: consultas, coste y latencia de las últimas 24 h.
Solo lectura → sin token; ceros explícitos sin datos; coste como texto
(Decimal, nunca float).
"""

import shutil
import tempfile
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.models import AiEvaluation, utc_now


class AiStatsApiBase(unittest.TestCase):
    """BD temporal aislada + TestClient sin lifespan (el loop no arranca)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="ai-stats-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "ai.db"
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.engine = engine
        self.addCleanup(engine.dispose)
        self.factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
        patcher = patch("app.database.SessionLocal", self.factory)
        patcher.start()
        self.addCleanup(patcher.stop)

        token_patcher = patch.object(settings, "api_token", "")
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

        self.client = TestClient(app)

    def _seed(self, **overrides) -> None:
        params = {
            "symbol": "BTCUSDT",
            "trigger": "cycle",
            "status": "OK",
        }
        params.update(overrides)
        db = self.factory()
        try:
            db.add(AiEvaluation(**params))
            db.commit()
        finally:
            db.close()


class AiStatsApiTests(AiStatsApiBase):
    def test_200_without_token(self) -> None:
        response = self.client.get("/api/bot/ai/stats")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in (
            "queries_24h",
            "cost_usd_24h",
            "avg_latency_ms",
            "by_status",
            "by_decision",
            "generated_at",
        ):
            self.assertIn(key, body)

    def test_empty_returns_explicit_zeros(self) -> None:
        body = self.client.get("/api/bot/ai/stats").json()
        self.assertEqual(body["queries_24h"], 0)
        self.assertEqual(Decimal(body["cost_usd_24h"]), Decimal("0"))
        self.assertIsNone(body["avg_latency_ms"])
        self.assertEqual(body["by_status"], {})
        self.assertEqual(body["by_decision"], {})

    def test_aggregates_last_24h(self) -> None:
        self._seed(
            decision="BUY",
            latency_ms=100,
            cost_usd=Decimal("0.001"),
            created_at=utc_now(),
        )
        self._seed(
            decision="WAIT",
            latency_ms=200,
            cost_usd=Decimal("0.002"),
            created_at=utc_now(),
        )
        self._seed(
            status="ERROR",
            decision=None,
            latency_ms=None,
            cost_usd=Decimal("0"),
            error="cuota agotada",
            created_at=utc_now(),
        )
        # Fuera de la ventana de 24 h: no cuenta.
        self._seed(
            decision="SELL",
            latency_ms=9999,
            cost_usd=Decimal("5"),
            created_at=utc_now() - timedelta(hours=25),
        )

        body = self.client.get("/api/bot/ai/stats").json()
        self.assertEqual(body["queries_24h"], 3)
        self.assertEqual(Decimal(body["cost_usd_24h"]), Decimal("0.003"))
        # Media de las filas con latencia (100 y 200); la ERROR no aporta.
        self.assertEqual(body["avg_latency_ms"], 150)
        self.assertEqual(body["by_status"], {"OK": 2, "ERROR": 1})
        self.assertEqual(
            body["by_decision"], {"BUY": 1, "WAIT": 1}
        )

    def test_cost_is_serialized_as_text(self) -> None:
        self._seed(cost_usd=Decimal("0.00125"), latency_ms=50)
        body = self.client.get("/api/bot/ai/stats").json()
        self.assertIsInstance(body["cost_usd_24h"], str)
        self.assertEqual(
            Decimal(body["cost_usd_24h"]), Decimal("0.00125")
        )


if __name__ == "__main__":
    unittest.main()

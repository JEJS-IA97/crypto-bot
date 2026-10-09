"""Tests rojos — Spec 009: panel "Why?" de una decisión (RF-4).

``GET /api/bot/decisions/{id}/why``: decisión + factores (AI
``supporting/contradicting_factors`` + indicadores crudos del snapshot) +
riesgo (evento ``risk.evaluated``) + resultado. Lo no persistido va en
``unavailable`` con motivo; nunca 500 ni texto inventado.
"""

import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.models import (
    AiEvaluation,
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,
)
from app.services.observability_service import record_event

CORRELATION = "11111111-2222-4333-8444-555555555555"


class WhyApiBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="why-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "why.db"
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

    def _decision(self, snapshot: dict | None = None, **overrides) -> int:
        params = {
            "client_order_id": "why-1",
            "symbol": "BTCUSDT",
            "side": TradeSide.BUY,
            "origin": DecisionOrigin.TECHNICAL,
            "status": DecisionStatus.OPENED,
            "config_json": "{}",
            "market_snapshot_json": json.dumps(
                snapshot if snapshot is not None else {}
            ),
            "quantity": Decimal("0.5"),
            "price": Decimal("101.2"),
        }
        params.update(overrides)
        db = self.factory()
        try:
            decision = SignalDecision(**params)
            db.add(decision)
            db.commit()
            return decision.id
        finally:
            db.close()

    def _seed_ai(self, correlation_id: str | None, **overrides) -> None:
        params = {
            "symbol": "BTCUSDT",
            "trigger": "cycle",
            "status": "OK",
            "decision": "BUY",
            "direction": "LONG",
            "confidence": Decimal("0.75"),
            "correlation_id": correlation_id,
            "model": "gemini-2.5-flash",
            "prompt_version": "v3",
            "latency_ms": 321,
            "cost_usd": Decimal("0.0021"),
            "response_json": json.dumps(
                {
                    "decision": "BUY",
                    "direction": "LONG",
                    "confidence": 0.75,
                    "risk_flags": [],
                    "supporting_factors": [
                        "Rango definido",
                        "Volumen creciente",
                    ],
                    "contradicting_factors": ["Sesgo macro debil"],
                }
            ),
        }
        params.update(overrides)
        db = self.factory()
        try:
            db.add(AiEvaluation(**params))
            db.commit()
        finally:
            db.close()

    def _seed_risk(
        self, correlation_id: str | None, **overrides
    ) -> None:
        params = {
            "level": "INFO",
            "service": "risk_engine",
            "event": "risk.evaluated",
            "result": "ALLOW",
            "correlation_id": correlation_id,
            "payload": {
                "action": "ALLOW",
                "reason": "ok",
                "requested_usd": "12.5",
                "allowed_usd": "12.5",
                "committed_usd": "12.5",
                "open_positions": 1,
            },
        }
        params.update(overrides)
        db = self.factory()
        try:
            record_event(db, **params)
        finally:
            db.close()


class WhyPayloadTests(WhyApiBase):
    def test_full_payload_with_ai_and_risk(self) -> None:
        decision_id = self._decision(
            snapshot={
                "correlation_id": CORRELATION,
                "price": "100",
                "indicators": {"range_size": "2.5"},
            }
        )
        self._seed_ai(CORRELATION)
        self._seed_risk(CORRELATION)

        response = self.client.get(
            f"/api/bot/decisions/{decision_id}/why"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body["decision"]["symbol"], "BTCUSDT")
        self.assertEqual(body["decision"]["quantity"], "0.5")
        self.assertEqual(body["decision"]["price"], "101.2")
        self.assertEqual(body["decision"]["status"], "OPENED")

        self.assertEqual(
            body["factors"]["positive"],
            ["Rango definido", "Volumen creciente"],
        )
        self.assertEqual(
            body["factors"]["negative"], ["Sesgo macro debil"]
        )
        self.assertEqual(
            body["factors"]["indicators"], {"range_size": "2.5"}
        )

        self.assertIsNotNone(body["ai"])
        self.assertEqual(body["ai"]["decision"], "BUY")
        self.assertIsInstance(body["ai"]["confidence"], str)
        self.assertEqual(Decimal(body["ai"]["confidence"]), Decimal("0.75"))
        self.assertEqual(body["ai"]["model"], "gemini-2.5-flash")
        self.assertEqual(body["ai"]["latency_ms"], 321)

        self.assertIsNotNone(body["risk"])
        self.assertEqual(body["risk"]["action"], "ALLOW")
        self.assertEqual(body["risk"]["reason"], "ok")
        self.assertEqual(body["risk"]["allowed_usd"], "12.5")

        self.assertEqual(body["outcome"]["status"], "OPENED")
        self.assertIn("pnl_usd", body["outcome"])
        self.assertEqual(body["unavailable"], [])

    def test_without_ai_marks_unavailable(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION}
        )
        self._seed_risk(CORRELATION)

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/why"
        ).json()
        self.assertIsNone(body["ai"])
        ai_flags = [
            entry for entry in body["unavailable"]
            if entry["section"] == "ai"
        ]
        self.assertEqual(len(ai_flags), 1)
        self.assertIn("IA", ai_flags[0]["reason"])
        self.assertTrue(ai_flags[0]["reason"])

    def test_without_correlation_id_marks_unavailable(self) -> None:
        decision_id = self._decision(snapshot={})

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/why"
        ).json()
        self.assertIsNone(body["ai"])
        self.assertIsNone(body["risk"])
        sections = {entry["section"] for entry in body["unavailable"]}
        self.assertIn("ai", sections)
        self.assertIn("risk", sections)
        for entry in body["unavailable"]:
            with self.subTest(section=entry["section"]):
                self.assertIn("correlation_id", entry["reason"])

    def test_rejected_decision_reports_reason(self) -> None:
        decision_id = self._decision(
            status=DecisionStatus.REJECTED,
            rejection_reason="daily_loss_limit",
        )

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/why"
        ).json()
        self.assertEqual(body["decision"]["status"], "REJECTED")
        self.assertEqual(
            body["decision"]["rejection_reason"], "daily_loss_limit"
        )
        self.assertEqual(
            body["outcome"]["status"], "REJECTED"
        )

    def test_unknown_decision_is_404(self) -> None:
        response = self.client.get("/api/bot/decisions/9999/why")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

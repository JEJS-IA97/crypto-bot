"""Tests rojos — Spec 009: vista de replay de una decisión (RF-5).

``GET /api/bot/decisions/{id}/replay``: reconstrucción determinista desde
datos persistidos (snapshot, eventos por correlation_id, evaluación IA,
posición, resultado). Secciones no disponibles → ``unavailable`` con
motivo; orden temporal ascendente; decisión inexistente → 404.
"""

import json
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
from app.models import (
    AiEvaluation,
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
    utc_now,
)
from app.schemas import SimulationAccountCreate
from app.services.observability_service import record_event
from app.services.simulation_service import create_simulation_account

CORRELATION = "11111111-2222-4333-8444-555555555555"


class ReplayApiBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="replay-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "replay.db"
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

        db = self.factory()
        try:
            self.account = create_simulation_account(
                db,
                SimulationAccountCreate(
                    name="replay-api",
                    initial_balance_usd=Decimal("20"),
                ),
            )
        finally:
            db.close()

        self.client = TestClient(app)

    def _decision(
        self,
        snapshot: dict | None = None,
        config_json: str = "{}",
        **overrides,
    ) -> int:
        params = {
            "client_order_id": "replay-1",
            "symbol": "BTCUSDT",
            "side": TradeSide.BUY,
            "origin": DecisionOrigin.TECHNICAL,
            "status": DecisionStatus.OPENED,
            "config_json": config_json,
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

    def _seed_event(
        self,
        correlation_id: str | None,
        event: str,
        created_at,
        **overrides,
    ) -> None:
        params = {
            "level": "INFO",
            "service": "bot_loop",
            "event": event,
            "result": "ok",
            "correlation_id": correlation_id,
            "created_at": created_at,
        }
        params.update(overrides)
        db = self.factory()
        try:
            record_event(db, **params)
        finally:
            db.close()

    def _seed_ai(
        self, correlation_id: str | None, created_at=None, **overrides
    ) -> None:
        params = {
            "symbol": "BTCUSDT",
            "trigger": "cycle",
            "status": "OK",
            "decision": "BUY",
            "direction": "LONG",
            "confidence": Decimal("0.75"),
            "correlation_id": correlation_id,
            "model": "gemini-2.5-flash",
            "latency_ms": 321,
            "cost_usd": Decimal("0.0021"),
            "response_json": json.dumps(
                {
                    "decision": "BUY",
                    "supporting_factors": ["Tendencia alcista"],
                    "contradicting_factors": [],
                }
            ),
        }
        if created_at is not None:
            params["created_at"] = created_at
        params.update(overrides)
        db = self.factory()
        try:
            db.add(AiEvaluation(**params))
            db.commit()
        finally:
            db.close()


class ReplayPayloadTests(ReplayApiBase):
    def test_deterministic_response(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION, "price": "100"}
        )
        self._seed_event(CORRELATION, "order.sent", utc_now())
        self._seed_ai(CORRELATION)

        first = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        )
        second = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())

    def test_events_are_ordered_ascending(self) -> None:
        base = utc_now()
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION}
        )
        # Insertados en orden desordenado a propósito.
        self._seed_event(
            CORRELATION, "cycle.completed", base + timedelta(seconds=3)
        )
        self._seed_event(
            CORRELATION, "order.sent", base + timedelta(seconds=1)
        )
        self._seed_event(
            CORRELATION, "order.filled", base + timedelta(seconds=2)
        )

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        self.assertEqual(
            [event["event"] for event in body["events"]],
            ["order.sent", "order.filled", "cycle.completed"],
        )
        timestamps = [event["created_at"] for event in body["events"]]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_snapshot_config_and_candles_roundtrip(self) -> None:
        snapshot = {
            "correlation_id": CORRELATION,
            "price": "100.5",
            "timestamp": "2026-10-07T12:00:00+00:00",
            "indicators": {"range_size": "2.5"},
            "candles": [
                {"open_time": 1, "open": "99", "close": "100.5"}
            ],
        }
        decision_id = self._decision(
            snapshot=snapshot,
            config_json='{"range_minutes": 15}',
        )

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        stored = body["snapshot"]
        self.assertEqual(stored["correlation_id"], CORRELATION)
        self.assertEqual(stored["price"], "100.5")
        self.assertEqual(stored["timestamp"], "2026-10-07T12:00:00+00:00")
        self.assertEqual(
            stored["indicators"], {"range_size": "2.5"}
        )
        self.assertEqual(
            stored["candles"],
            [{"open_time": 1, "open": "99", "close": "100.5"}],
        )
        self.assertEqual(stored["config"], {"range_minutes": 15})

    def test_latest_ai_evaluation_is_included(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION}
        )
        self._seed_ai(
            CORRELATION,
            created_at=utc_now() - timedelta(minutes=5),
            decision="WAIT",
        )
        self._seed_ai(CORRELATION, decision="BUY")

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        self.assertIsNotNone(body["ai_evaluation"])
        self.assertEqual(body["ai_evaluation"]["decision"], "BUY")
        self.assertEqual(body["ai_evaluation"]["model"], "gemini-2.5-flash")

    def test_position_is_included(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION}
        )
        db = self.factory()
        try:
            db.add(
                PositionV2(
                    account_id=self.account.id,
                    decision_id=decision_id,
                    symbol="BTCUSDT",
                    quantity=Decimal("0.5"),
                    average_entry_price=Decimal("101.2"),
                    stop_price=Decimal("99"),
                    take_profit_price=Decimal("105"),
                    status=PositionStatus.OPEN,
                )
            )
            db.commit()
        finally:
            db.close()

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        self.assertIsNotNone(body["position"])
        position = body["position"]
        self.assertEqual(
            Decimal(position["quantity"]), Decimal("0.5")
        )
        self.assertEqual(
            Decimal(position["average_entry_price"]), Decimal("101.2")
        )
        self.assertEqual(Decimal(position["stop_price"]), Decimal("99"))
        self.assertEqual(
            Decimal(position["take_profit_price"]), Decimal("105")
        )
        self.assertEqual(position["status"], "OPEN")

    def test_outcome_reports_pnl_as_text(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION},
            status=DecisionStatus.CLOSED,
            pnl_usd=Decimal("-0.42"),
            closed_at=utc_now(),
        )
        self._seed_event(CORRELATION, "order.sent", utc_now())
        self._seed_ai(CORRELATION)

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        self.assertEqual(body["outcome"]["status"], "CLOSED")
        self.assertIsInstance(body["outcome"]["pnl_usd"], str)
        self.assertEqual(
            Decimal(body["outcome"]["pnl_usd"]), Decimal("-0.42")
        )
        self.assertEqual(body["unavailable"], [])


class ReplayUnavailableTests(ReplayApiBase):
    def test_without_correlation_id_sections_unavailable(self) -> None:
        decision_id = self._decision(snapshot={})

        response = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["snapshot"]["correlation_id"])
        self.assertEqual(body["events"], [])
        self.assertIsNone(body["ai_evaluation"])
        sections = {entry["section"] for entry in body["unavailable"]}
        self.assertIn("events", sections)
        self.assertIn("ai", sections)
        for entry in body["unavailable"]:
            with self.subTest(section=entry["section"]):
                self.assertIn("correlation_id", entry["reason"])

    def test_missing_events_marked_as_retention(self) -> None:
        decision_id = self._decision(
            snapshot={"correlation_id": CORRELATION}
        )

        body = self.client.get(
            f"/api/bot/decisions/{decision_id}/replay"
        ).json()
        self.assertEqual(body["events"], [])
        event_flags = [
            entry for entry in body["unavailable"]
            if entry["section"] == "events"
        ]
        self.assertEqual(len(event_flags), 1)
        self.assertIn("retención", event_flags[0]["reason"])

    def test_unknown_decision_is_404(self) -> None:
        response = self.client.get(
            "/api/bot/decisions/9999/replay"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

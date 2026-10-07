"""Tests rojos — Spec 005: endpoints de observabilidad (RF-5, RF-6, RF-7).

`GET /api/bot/events` (filtros + clamps), `GET /api/bot/sources` y
`GET /api/bot/observability`. Solo lectura → sin token (RF-20 de la 001).
"""

import json
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.models import utc_now
from app.services.observability_service import (
    KNOWN_SOURCES,
    mark_source,
    record_event,
)


class ObservabilityApiBase(unittest.TestCase):
    """BD temporal aislada + TestClient sin lifespan (el loop no arranca)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="obs-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "obs.db"
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
            "level": "INFO",
            "service": "bot_loop",
            "event": "cycle.completed",
            "result": "ok",
        }
        params.update(overrides)
        db = self.factory()
        try:
            record_event(db, **params)
        finally:
            db.close()


class EventsEndpointTests(ObservabilityApiBase):
    """RF-6: consulta de eventos con filtros y clamps."""

    def test_empty_returns_200_with_empty_list(self) -> None:
        response = self.client.get("/api/bot/events")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"], [])

    def test_returns_events_newest_first(self) -> None:
        self._seed(event="oldest", created_at=utc_now().replace(microsecond=1))
        self._seed(
            event="newest", created_at=utc_now().replace(microsecond=3)
        )
        response = self.client.get("/api/bot/events")
        self.assertEqual(response.status_code, 200)
        events = response.json()["events"]
        self.assertEqual(
            [e["event"] for e in events], ["newest", "oldest"]
        )

    def test_filters_by_level_asset_and_correlation(self) -> None:
        correlation = "11111111-2222-4333-8444-555555555555"
        self._seed(
            level="ERROR",
            event="order.failed",
            asset="ETHUSDT",
            result="failed",
        )
        self._seed(
            level="INFO",
            event="cycle.completed",
            correlation_id=correlation,
            asset="BTCUSDT",
        )

        errors = self.client.get(
            "/api/bot/events", params={"level": "ERROR"}
        ).json()["events"]
        self.assertEqual([e["event"] for e in errors], ["order.failed"])

        btc = self.client.get(
            "/api/bot/events", params={"asset": "BTCUSDT"}
        ).json()["events"]
        self.assertEqual([e["event"] for e in btc], ["cycle.completed"])

        linked = self.client.get(
            "/api/bot/events",
            params={"correlation_id": correlation},
        ).json()["events"]
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["correlation_id"], correlation)

    def test_limit_is_clamped(self) -> None:
        for index in range(3):
            self._seed(event=f"e{index}")
        # Límite bajo → clamped a 1.
        low = self.client.get(
            "/api/bot/events", params={"limit": 0}
        ).json()["events"]
        self.assertEqual(len(low), 1)
        # Límite alto → aceptado sin error (clamp a 200).
        high = self.client.get(
            "/api/bot/events", params={"limit": 5000}
        )
        self.assertEqual(high.status_code, 200)
        self.assertLessEqual(len(high.json()["events"]), 200)

    def test_payload_is_json_object_without_secrets(self) -> None:
        self._seed(
            event="order.sent",
            payload={"api_key": "NO-DEBE-APARECER", "symbol": "BTCUSDT"},
        )
        events = self.client.get("/api/bot/events").json()["events"]
        payload = events[0]["payload"]
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertEqual(payload["api_key"], "[REDACTED]")
        raw = json.dumps(events)
        self.assertNotIn("NO-DEBE-APARECER", raw)


class SourcesEndpointTests(ObservabilityApiBase):
    """RF-5: estado de fuentes expuesto por API."""

    def test_sources_lists_known_registry(self) -> None:
        db = self.factory()
        try:
            mark_source(db, "binance_klines", ok=True)
            mark_source(
                db, "database", ok=False, error="connection refused"
            )
        finally:
            db.close()

        response = self.client.get("/api/bot/sources")
        self.assertEqual(response.status_code, 200)
        sources = {s["name"]: s for s in response.json()["sources"]}
        self.assertEqual(sources["binance_klines"]["state"], "HEALTHY")
        self.assertEqual(sources["database"]["state"], "ERROR")
        self.assertEqual(
            sources["binance_ticker"]["state"], "DISABLED"
        )
        self.assertEqual(len(sources), len(KNOWN_SOURCES))
        self.assertIn("last_success_at", sources["binance_klines"])
        self.assertIn("updated_at", sources["binance_klines"])


class ObservabilityEndpointTests(ObservabilityApiBase):
    """RF-7: métricas técnicas de las últimas 24 h."""

    def test_payload_shape_and_counts(self) -> None:
        self._seed(level="INFO", event="cycle.completed", result="ok")
        self._seed(
            level="ERROR",
            event="cycle.completed",
            result="failed",
            payload={"error": "boom"},
        )
        self._seed(level="WARNING", event="order.failed", result="failed")
        # Fuera de la ventana de 24 h: no cuenta.
        self._seed(
            level="ERROR",
            event="stale.error",
            result="failed",
            created_at=utc_now() - timedelta(hours=25),
        )

        response = self.client.get("/api/bot/observability")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in (
            "events_by_level",
            "cycles_by_result",
            "last_error",
            "sources_by_state",
        ):
            self.assertIn(key, body)
        self.assertEqual(body["events_by_level"]["INFO"], 1)
        self.assertEqual(body["events_by_level"]["WARNING"], 1)
        self.assertEqual(body["events_by_level"]["ERROR"], 1)
        self.assertEqual(body["cycles_by_result"]["ok"], 1)
        self.assertEqual(body["cycles_by_result"]["failed"], 1)
        self.assertIsNotNone(body["last_error"])
        self.assertEqual(body["last_error"]["event"], "cycle.completed")
        self.assertEqual(
            body["sources_by_state"].get("DISABLED"), len(KNOWN_SOURCES)
        )

    def test_empty_system_returns_stable_shape(self) -> None:
        body = self.client.get("/api/bot/observability").json()
        self.assertEqual(
            body["events_by_level"],
            {"INFO": 0, "WARNING": 0, "ERROR": 0},
        )
        self.assertEqual(body["cycles_by_result"], {})
        self.assertIsNone(body["last_error"])


if __name__ == "__main__":
    unittest.main()

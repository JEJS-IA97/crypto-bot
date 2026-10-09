"""Tests rojos — Spec 009: canvas de nodos del pipeline (RF-2).

``GET /api/bot/pipeline``: catálogo fijo de 22 nodos (brief §13) con
estado derivado de ``source_health`` (005) y de los últimos eventos del
servicio. Todo ``DISABLED`` lleva motivo; sin red ni token (solo lectura).
"""

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
from app.services.observability_service import mark_source, record_event

CATALOG_IDS: tuple[str, ...] = (
    "exchange",
    "market_data",
    "order_book",
    "trades",
    "derivatives",
    "funding",
    "open_interest",
    "options",
    "dex",
    "news",
    "macro",
    "sentiment",
    "feature_engine",
    "regime_detector",
    "candidate_filter",
    "portfolio_analyzer",
    "ai_analyst",
    "risk_engine",
    "execution",
    "position",
    "learning",
    "memory",
)

STUB_IDS: frozenset[str] = frozenset(
    {
        "trades",
        "derivatives",
        "funding",
        "open_interest",
        "options",
        "dex",
        "sentiment",
        "regime_detector",
        "portfolio_analyzer",
        "learning",
    }
)

VALID_STATES = frozenset(
    {"HEALTHY", "DEGRADED", "STALE", "ERROR", "DISABLED"}
)
VALID_KINDS = frozenset({"source", "pipeline", "stub"})
NODE_KEYS = {
    "id",
    "label",
    "kind",
    "state",
    "backing",
    "last_update",
    "reason",
    "last_event",
}


class PipelineApiBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="pipeline-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "pipeline.db"
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

    def _call(self) -> dict:
        response = self.client.get("/api/bot/pipeline")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _nodes(self) -> dict[str, dict]:
        return {node["id"]: node for node in self._call()["nodes"]}

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


class PipelineCatalogTests(PipelineApiBase):
    def test_catalog_is_complete(self) -> None:
        nodes = self._call()["nodes"]
        self.assertEqual(len(nodes), len(CATALOG_IDS))
        self.assertEqual(
            [node["id"] for node in nodes], list(CATALOG_IDS)
        )
        for node in nodes:
            with self.subTest(node=node["id"]):
                self.assertEqual(set(node.keys()), NODE_KEYS)
                self.assertIn(node["state"], VALID_STATES)
                self.assertIn(node["kind"], VALID_KINDS)
                self.assertTrue(node["label"])
                if node["state"] == "DISABLED":
                    self.assertTrue(node["reason"])

    def test_stubs_are_disabled_with_reason(self) -> None:
        nodes = self._nodes()
        for stub in STUB_IDS:
            with self.subTest(node=stub):
                node = nodes[stub]
                self.assertEqual(node["state"], "DISABLED")
                self.assertTrue(node["reason"])
                self.assertEqual(node["backing"], [])

    def test_backing_is_declared(self) -> None:
        nodes = self._nodes()
        self.assertEqual(
            nodes["market_data"]["backing"],
            ["binance_klines", "binance_ticker"],
        )
        self.assertEqual(
            nodes["memory"]["backing"], ["database"]
        )
        self.assertEqual(
            nodes["candidate_filter"]["backing"],
            ["candidate_service"],
        )
        self.assertEqual(nodes["risk_engine"]["backing"], ["risk_engine"])
        self.assertEqual(nodes["feature_engine"]["backing"], ["bot_loop"])

    def test_empty_system_default_states(self) -> None:
        nodes = self._nodes()
        for source_node in (
            "market_data",
            "exchange",
            "order_book",
            "news",
            "macro",
            "ai_analyst",
            "memory",
        ):
            with self.subTest(node=source_node):
                node = nodes[source_node]
                self.assertEqual(node["state"], "DISABLED")
                self.assertIn("registro", node["reason"])
        for pipeline_node in (
            "feature_engine",
            "candidate_filter",
            "risk_engine",
            "execution",
            "position",
        ):
            with self.subTest(node=pipeline_node):
                node = nodes[pipeline_node]
                self.assertEqual(node["state"], "DISABLED")
                self.assertIn("actividad", node["reason"])

    def test_deterministic_response(self) -> None:
        self.assertEqual(self._call(), self._call())


class PipelineSourceNodesTests(PipelineApiBase):
    def _mark(self, name: str, ok: bool, error: str = "") -> None:
        db = self.factory()
        try:
            mark_source(db, name, ok=ok, error=error)
        finally:
            db.close()

    def test_healthy_source_drives_node(self) -> None:
        # binance_ticker sin fila no empeora: solo cuentan las fuentes
        # con registro.
        self._mark("binance_klines", ok=True)
        nodes = self._nodes()
        self.assertEqual(nodes["market_data"]["state"], "HEALTHY")
        self.assertEqual(nodes["memory"]["state"], "DISABLED")

    def test_error_source_drives_node(self) -> None:
        self._mark("database", ok=False, error="connection refused")
        nodes = self._nodes()
        self.assertEqual(nodes["memory"]["state"], "ERROR")

    def test_ai_node_worst_of_source_and_service(self) -> None:
        self._mark("gemini", ok=False, error="quota")
        nodes = self._nodes()
        self.assertEqual(nodes["ai_analyst"]["state"], "ERROR")

        # Fuente sana + evento reciente del servicio ERROR ⇒ ERROR.
        self._mark("gemini", ok=True)
        self._seed(
            level="ERROR",
            service="ai_advisor",
            event="ai.consultation",
            result="failed",
        )
        nodes = self._nodes()
        self.assertEqual(nodes["ai_analyst"]["state"], "ERROR")


class PipelineServiceNodesTests(PipelineApiBase):
    def test_healthy_event_drives_node_with_last_event(self) -> None:
        self._seed(
            service="candidate_service",
            event="config.ignored",
            latency_ms=12,
            correlation_id="11111111-2222-4333-8444-555555555555",
        )
        node = self._nodes()["candidate_filter"]
        self.assertEqual(node["state"], "HEALTHY")
        self.assertIsNotNone(node["last_update"])
        self.assertEqual(node["last_event"]["event"], "config.ignored")
        self.assertEqual(node["last_event"]["service"], "candidate_service")
        self.assertEqual(node["last_event"]["latency_ms"], 12)
        self.assertEqual(
            node["last_event"]["correlation_id"],
            "11111111-2222-4333-8444-555555555555",
        )

    def test_warning_and_error_map_states(self) -> None:
        self._seed(
            service="candidate_service",
            event="config.ignored",
            level="WARNING",
            result="ignored",
        )
        self.assertEqual(
            self._nodes()["candidate_filter"]["state"], "DEGRADED"
        )

        self._seed(
            service="bot_loop",
            event="order.failed",
            level="ERROR",
            result="failed",
        )
        node = self._nodes()["execution"]
        self.assertEqual(node["state"], "ERROR")
        self.assertEqual(node["last_event"]["event"], "order.failed")

    def test_old_event_becomes_stale(self) -> None:
        self._seed(
            service="candidate_service",
            event="config.ignored",
            created_at=utc_now() - timedelta(seconds=360),
        )
        self.assertEqual(
            self._nodes()["candidate_filter"]["state"], "STALE"
        )

    def test_execution_ignores_cycle_events(self) -> None:
        # cycle.completed alimenta FEATURE ENGINE, no EXECUTION.
        self._seed(service="bot_loop", event="cycle.completed")
        nodes = self._nodes()
        self.assertEqual(nodes["feature_engine"]["state"], "HEALTHY")
        self.assertEqual(nodes["execution"]["state"], "DISABLED")

    def test_execution_tracks_order_events(self) -> None:
        self._seed(
            service="order_lifecycle",
            event="order.filled",
            latency_ms=45,
        )
        node = self._nodes()["execution"]
        self.assertEqual(node["state"], "HEALTHY")
        self.assertEqual(node["last_event"]["latency_ms"], 45)

    def test_risk_engine_reports_result(self) -> None:
        self._seed(
            service="risk_engine",
            event="risk.evaluated",
            result="ALLOW",
            level="INFO",
        )
        node = self._nodes()["risk_engine"]
        self.assertEqual(node["state"], "HEALTHY")
        self.assertEqual(node["last_event"]["result"], "ALLOW")


if __name__ == "__main__":
    unittest.main()

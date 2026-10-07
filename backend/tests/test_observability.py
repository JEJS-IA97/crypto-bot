"""Tests rojos — Spec 005: observabilidad estructurada.

RF-1 logging JSON fail-open · RF-2 correlation_id por ciclo · RF-3 eventos en
`system_events` · RF-4 redacción de secretos · RF-5 salud de fuentes ·
RF-7 agregados 24 h · RF-8 retención. Los endpoints (RF-6/RF-7) se prueban en
`test_observability_api.py`.
"""

import io
import json
import logging
import re
import unittest
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.models import SystemEvent, utc_now
from app.schemas import SimulationAccountCreate
from app.services.observability_service import (
    KNOWN_SOURCES,
    PAYLOAD_MAX_BYTES,
    STALE_AFTER_SECONDS,
    aggregates_24h,
    mark_source,
    purge_old_events,
    record_event,
    sources_state,
)
from app.services.simulation_service import create_simulation_account
from app.services.structured_log import (
    JsonFormatter,
    configure_logging,
    emit,
    redact,
)

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class _LoggedRecord:
    """Una línea JSON emitida por ``JsonFormatter`` en un stream capturado."""

    def __init__(self, payload: dict) -> None:
        self.data = payload


def _capture(service: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    logger = logging.getLogger(service)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger, stream


def _lines(stream: io.StringIO) -> list[_LoggedRecord]:
    return [
        _LoggedRecord(json.loads(line))
        for line in stream.getvalue().splitlines()
        if line.strip()
    ]


class StructuredLogTests(unittest.TestCase):
    """RF-1: una línea JSON por evento con campos obligatorios; fail-open."""

    def test_emit_writes_one_json_line_with_required_fields(self) -> None:
        logger, stream = _capture("svc.rf1")
        try:
            emit(
                service="svc.rf1",
                event="cycle.completed",
                result="ok",
                mode="SIMULATION",
                correlation_id=str(uuid.uuid4()),
                asset="BTCUSDT",
                latency_ms=42,
            )
            emit(service="svc.rf1", event="system.started", result="ok")
        finally:
            logger.handlers.clear()

        records = _lines(stream)
        self.assertEqual(len(records), 2)

        first = records[0].data
        for field in (
            "timestamp",
            "level",
            "service",
            "event",
            "mode",
            "result",
            "correlation_id",
            "asset",
            "latency_ms",
            "strategy_version",
        ):
            self.assertIn(field, first, f"falta el campo {field}")
        self.assertEqual(first["service"], "svc.rf1")
        self.assertEqual(first["event"], "cycle.completed")
        self.assertEqual(first["level"], "INFO")
        self.assertEqual(first["mode"], "SIMULATION")
        self.assertEqual(first["result"], "ok")
        self.assertEqual(first["asset"], "BTCUSDT")
        self.assertEqual(first["latency_ms"], 42)
        self.assertEqual(first["strategy_version"], settings.strategy_version)
        self.assertTrue(UUID_RE.match(first["correlation_id"]))

        second = records[1].data
        self.assertIsNone(second["correlation_id"])
        self.assertIsNone(second["asset"])
        # ISO 8601 UTC en timestamp.
        self.assertTrue(second["timestamp"].endswith("Z"))

    def test_emit_without_db_never_raises(self) -> None:
        logger, stream = _capture("svc.failopen")
        try:
            emit(service="svc.failopen", event="noop", result="ok")
        finally:
            logger.handlers.clear()
        self.assertEqual(len(_lines(stream)), 1)

    def test_emit_survives_broken_session(self) -> None:
        """D-3/RF-1: un fallo de persistencia no interrumpe al llamador."""

        class BrokenSession:
            def add(self, *_args, **_kwargs) -> None:
                raise RuntimeError("db caida")

            def commit(self) -> None:
                raise RuntimeError("db caida")

            def rollback(self) -> None:
                pass

        logger, stream = _capture("svc.broken")
        try:
            emit(
                service="svc.broken",
                event="cycle.completed",
                result="ok",
                db=BrokenSession(),  # type: ignore[arg-type]
            )
        finally:
            logger.handlers.clear()
        self.assertEqual(len(_lines(stream)), 1)

    def test_configure_logging_is_idempotent(self) -> None:
        root = logging.getLogger()
        original = list(root.handlers)
        try:
            configure_logging()
            configure_logging()
            added = [
                h
                for h in root.handlers
                if h not in original
            ]
            self.assertEqual(len(added), 1)
            self.assertIsInstance(added[0].formatter, JsonFormatter)
        finally:
            for handler in list(root.handlers):
                if handler not in original:
                    root.removeHandler(handler)


class RedactionTests(unittest.TestCase):
    """RF-4: claves y tokens nunca llegan ni a stdout ni a la BD."""

    def test_redact_masks_forbidden_fields_recursively(self) -> None:
        cleaned = redact(
            {
                "symbol": "BTCUSDT",
                "api_key": "AKIA123",
                "nested": {
                    "authorization": "Bearer xyz",
                    "secret": "shh",
                    "price": "100",
                },
                "BINANCE_API_SECRET": "top",
            }
        )
        self.assertEqual(cleaned["symbol"], "BTCUSDT")
        self.assertEqual(cleaned["api_key"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["authorization"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["secret"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["price"], "100")
        self.assertEqual(cleaned["BINANCE_API_SECRET"], "[REDACTED]")

    def test_emit_redacts_payload_on_stdout(self) -> None:
        logger, stream = _capture("svc.redact")
        try:
            emit(
                service="svc.redact",
                event="order.sent",
                result="ok",
                payload={
                    "binance_api_key": "AKIA999",
                    "token": "abc123",
                    "symbol": "BTCUSDT",
                },
            )
        finally:
            logger.handlers.clear()

        raw = stream.getvalue()
        self.assertNotIn("AKIA999", raw)
        self.assertNotIn("abc123", raw)
        self.assertIn("[REDACTED]", raw)
        self.assertIn("BTCUSDT", raw)

    def test_record_event_redacts_payload_json(self) -> None:
        db = _session_factory()()
        try:
            record_event(
                db,
                level="INFO",
                service="test",
                event="order.sent",
                result="ok",
                payload={"api_token": "super-secreto", "symbol": "ETHUSDT"},
            )
            row = db.execute(select(SystemEvent)).scalars().one()
            self.assertNotIn("super-secreto", row.payload_json)
            self.assertIn("[REDACTED]", row.payload_json)
            self.assertIn("ETHUSDT", row.payload_json)
        finally:
            db.close()


class EventPersistenceTests(unittest.TestCase):
    """RF-3: tabla `system_events` con todos los campos y payload acotado."""

    def setUp(self) -> None:
        self.db = _session_factory()()

    def tearDown(self) -> None:
        self.db.close()

    def test_record_event_stores_all_columns(self) -> None:
        now = utc_now()
        correlation = str(uuid.uuid4())
        record_event(
            self.db,
            level="WARNING",
            service="bot_loop",
            event="source.error",
            result="failed",
            asset="BTCUSDT",
            correlation_id=correlation,
            mode="SIMULATION",
            latency_ms=1234,
            payload={"detail": "timeout"},
            created_at=now,
        )
        row = self.db.execute(select(SystemEvent)).scalars().one()
        self.assertEqual(row.level, "WARNING")
        self.assertEqual(row.service, "bot_loop")
        self.assertEqual(row.event, "source.error")
        self.assertEqual(row.result, "failed")
        self.assertEqual(row.asset, "BTCUSDT")
        self.assertEqual(row.correlation_id, correlation)
        self.assertEqual(row.mode, "SIMULATION")
        self.assertEqual(row.latency_ms, 1234)
        self.assertEqual(row.created_at, now)
        self.assertEqual(json.loads(row.payload_json)["detail"], "timeout")

    def test_payload_json_truncated_at_limit(self) -> None:
        record_event(
            self.db,
            level="INFO",
            service="test",
            event="huge.payload",
            result="ok",
            payload={"blob": "x" * (PAYLOAD_MAX_BYTES * 3)},
        )
        row = self.db.execute(select(SystemEvent)).scalars().one()
        encoded = row.payload_json.encode("utf-8")
        self.assertLessEqual(len(encoded), PAYLOAD_MAX_BYTES)
        parsed = json.loads(row.payload_json)
        self.assertTrue(parsed.get("truncated"))
        self.assertGreater(len(parsed.get("preview", "")), 0)

    def test_event_without_optional_fields(self) -> None:
        record_event(
            self.db,
            level="INFO",
            service="main",
            event="system.started",
            result="ok",
        )
        row = self.db.execute(select(SystemEvent)).scalars().one()
        self.assertIsNone(row.asset)
        self.assertIsNone(row.correlation_id)
        self.assertIsNone(row.latency_ms)


class SourceHealthTests(unittest.TestCase):
    """RF-5: estados de fuente y derivación STALE/DISABLED."""

    def setUp(self) -> None:
        self.db = _session_factory()()

    def tearDown(self) -> None:
        self.db.close()

    def test_mark_source_success_then_error(self) -> None:
        mark_source(self.db, "binance_klines", ok=True)
        states = {s["name"]: s for s in sources_state(self.db)}
        self.assertEqual(states["binance_klines"]["state"], "HEALTHY")
        self.assertIsNotNone(states["binance_klines"]["last_success_at"])

        mark_source(
            self.db, "binance_klines", ok=False, error="timeout 504"
        )
        states = {s["name"]: s for s in sources_state(self.db)}
        self.assertEqual(states["binance_klines"]["state"], "ERROR")
        self.assertEqual(states["binance_klines"]["last_error"], "timeout 504")

    def test_never_touched_source_is_disabled(self) -> None:
        states = {s["name"]: s for s in sources_state(self.db)}
        for name in KNOWN_SOURCES:
            self.assertIn(name, states)
            self.assertEqual(
                states[name]["state"],
                "DISABLED",
                f"{name} deberia empezar DISABLED",
            )

    def test_stale_when_success_is_old(self) -> None:
        mark_source(self.db, "binance_ticker", ok=True)
        from app.models import SourceHealth

        row = self.db.get(SourceHealth, "binance_ticker")
        assert row is not None
        row.last_success_at = utc_now() - timedelta(
            seconds=STALE_AFTER_SECONDS + 60
        )
        self.db.commit()

        states = {s["name"]: s for s in sources_state(self.db)}
        self.assertEqual(states["binance_ticker"]["state"], "STALE")


class RetentionTests(unittest.TestCase):
    """RF-8: purga por EVENT_RETENTION_DAYS; no-op con tabla vacía."""

    def setUp(self) -> None:
        self.db = _session_factory()()

    def tearDown(self) -> None:
        self.db.close()

    def test_purge_removes_only_expired_events(self) -> None:
        retention_days = settings.event_retention_days
        record_event(
            self.db,
            level="INFO",
            service="test",
            event="old.event",
            result="ok",
            created_at=utc_now()
            - timedelta(days=retention_days + 1),
        )
        record_event(
            self.db,
            level="INFO",
            service="test",
            event="recent.event",
            result="ok",
            created_at=utc_now() - timedelta(hours=1),
        )
        removed = purge_old_events(self.db)
        self.assertEqual(removed, 1)
        rows = self.db.execute(select(SystemEvent)).scalars().all()
        self.assertEqual([r.event for r in rows], ["recent.event"])

    def test_purge_empty_table_is_noop(self) -> None:
        self.assertEqual(purge_old_events(self.db), 0)


class AggregatesTests(unittest.TestCase):
    """RF-7: agregados de las últimas 24 h para /api/bot/observability."""

    def setUp(self) -> None:
        self.db = _session_factory()()

    def tearDown(self) -> None:
        self.db.close()

    def test_aggregates_counts_and_last_error(self) -> None:
        record_event(
            self.db,
            level="INFO",
            service="bot_loop",
            event="cycle.completed",
            result="ok",
            latency_ms=10,
        )
        record_event(
            self.db,
            level="ERROR",
            service="bot_loop",
            event="cycle.completed",
            result="failed",
            payload={"error": "boom"},
        )
        record_event(
            self.db,
            level="WARNING",
            service="execution",
            event="order.failed",
            result="failed",
        )
        # Fuera de la ventana de 24 h: no cuenta.
        record_event(
            self.db,
            level="ERROR",
            service="old",
            event="cycle.completed",
            result="failed",
            created_at=utc_now() - timedelta(hours=25),
        )

        stats = aggregates_24h(self.db)
        self.assertEqual(
            stats["events_by_level"],
            {"INFO": 1, "WARNING": 1, "ERROR": 1},
        )
        self.assertEqual(
            stats["cycles_by_result"], {"ok": 1, "failed": 1}
        )
        self.assertIsNotNone(stats["last_error"])
        self.assertEqual(stats["last_error"]["event"], "cycle.completed")
        self.assertIn("sources_by_state", stats)
        self.assertEqual(
            stats["sources_by_state"].get("DISABLED"),
            len(KNOWN_SOURCES),
        )


class CorrelationIdTests(unittest.TestCase):
    """RF-2: un correlation_id por ciclo une evento y decisión."""

    def setUp(self) -> None:
        self.db = _session_factory()()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="obs", initial_balance_usd=Decimal("50")
            ),
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_cycle_event_and_decision_share_correlation_id(self) -> None:
        from test_orb_loop import (
            NOW_IN_WINDOW,
            FakeMarketData,
            candles_15m,
            range_candles,
        )
        from app.services.bot_loop import run_once

        market = FakeMarketData(
            candles_15m_by_symbol={"BTCUSDT": candles_15m()},
            candles_5m_by_symbol={"BTCUSDT": range_candles()},
        )
        report = run_once(
            self.db,
            market_data=market,
            symbols=["BTCUSDT"],
            account_id=self.account.id,
            now=NOW_IN_WINDOW,
        )
        self.assertEqual(report.status, "ok", report.error)

        cycle = self.db.execute(
            select(SystemEvent)
            .where(SystemEvent.event == "cycle.completed")
            .order_by(SystemEvent.id.desc())
        ).scalars().first()
        self.assertIsNotNone(cycle, "falta el evento cycle.completed")
        assert cycle is not None
        self.assertIsNotNone(cycle.correlation_id)
        self.assertTrue(UUID_RE.match(cycle.correlation_id or ""))
        self.assertIsNotNone(cycle.latency_ms)
        self.assertIn(cycle.result, {"ok", "failed", "stopped", "breaker"})
        self.assertEqual(cycle.mode, "SIMULATION")

        from app.models import SignalDecision

        decision = self.db.execute(
            select(SignalDecision).order_by(SignalDecision.id.desc())
        ).scalars().first()
        self.assertIsNotNone(decision, "el ciclo deberia emitir decision")
        assert decision is not None
        snapshot = json.loads(decision.market_snapshot_json)
        self.assertEqual(snapshot["correlation_id"], cycle.correlation_id)

        emitted = self.db.execute(
            select(SystemEvent).where(
                SystemEvent.event == "decision.emitted"
            )
        ).scalars().all()
        self.assertTrue(emitted)
        self.assertTrue(
            all(
                e.correlation_id == cycle.correlation_id
                for e in emitted
            )
        )
        self.assertTrue(any(e.asset == "BTCUSDT" for e in emitted))

    def test_quiet_cycle_still_records_correlation(self) -> None:
        from test_orb_loop import (
            NOW_OUTSIDE,
            FakeMarketData,
            candles_15m,
        )
        from app.services.bot_loop import run_once

        market = FakeMarketData(
            candles_15m_by_symbol={"BTCUSDT": candles_15m()},
        )
        run_once(
            self.db,
            market_data=market,
            symbols=["BTCUSDT"],
            account_id=self.account.id,
            now=NOW_OUTSIDE,
        )
        cycle = self.db.execute(
            select(SystemEvent)
            .where(SystemEvent.event == "cycle.completed")
            .order_by(SystemEvent.id.desc())
        ).scalars().first()
        self.assertIsNotNone(cycle)
        assert cycle is not None
        self.assertTrue(UUID_RE.match(cycle.correlation_id or ""))


if __name__ == "__main__":
    unittest.main()

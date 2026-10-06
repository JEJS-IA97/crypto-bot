import asyncio
import shutil
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
from app.main import app
from app.models import (
    BotPhaseName,
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,
    utc_now,
)
from app.schemas import SimulationAccountCreate
from app.services import bot_loop
from app.services.binance_market_data_client import BinanceMarketDataClient, SymbolRules
from app.services.bot_loop import CycleReport
from app.services.decision_store import mark_rejected, record_decision
from app.services.phase_service import get_phase
from app.services.risk_guard_service import get_runtime
from app.services.simulation_service import create_simulation_account

CYCLE_SECONDS = 1.5

RULES = SymbolRules(
    symbol="BTCUSDT",
    status="TRADING",
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
)

CANDLES = [
    Candle(
        open_time=utc_now() - timedelta(minutes=30),
        open=Decimal("99"),
        high=Decimal("101"),
        low=Decimal("98"),
        close=Decimal("100"),
        volume=Decimal("1000"),
    ),
    Candle(
        open_time=utc_now() - timedelta(minutes=15),
        open=Decimal("100"),
        high=Decimal("101"),
        low=Decimal("99"),
        close=Decimal("100.5"),
        volume=Decimal("1200"),
    ),
]


class BotApiTestBase(unittest.TestCase):
    """BD temporal aislada + TestClient sin lifespan (el loop no arranca)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="bot-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "bot_api.db"
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

        # Aísla el token ambiental del .env: RF-20 se testea aparte.
        token_patcher = patch.object(settings, "api_token", "")
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

        db = self.factory()
        self.account = create_simulation_account(
            db,
            SimulationAccountCreate(
                name="api",
                initial_balance_usd=Decimal("20"),
            ),
        )
        db.close()

        self.client = TestClient(app)


class ApiResponsiveDuringLoopTests(BotApiTestBase):
    def test_api_responsive_during_loop(self) -> None:
        calls: list[float] = []

        def slow_cycle(db, **kwargs) -> CycleReport:
            # Simula un ciclo largo: el loop está "evaluando".
            calls.append(time.monotonic())
            time.sleep(CYCLE_SECONDS)
            return CycleReport(status="ok")

        def loop_main() -> None:
            asyncio.run(
                bot_loop.run(
                    session_factory=self.factory,
                    cycle_runner=slow_cycle,
                    interval_seconds=60,
                    symbols=["BTCUSDT"],
                    account_id=1,
                )
            )

        thread = threading.Thread(target=loop_main, daemon=True)
        thread.start()

        deadline = time.monotonic() + 5
        while not calls and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(calls, "el loop no llegó a evaluar")

        client = self.client

        # RNF-3: la API responde mientras el loop evalúa (≤5 s).
        started = time.monotonic()
        status = client.get("/api/bot/status")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["running"])

        started = time.monotonic()
        response = client.post("/api/bot/stop")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["running"])

        # El ciclo en vuelo termina y el loop queda detenido sin reiniciar:
        # no entra en ningún ciclo nuevo.
        time.sleep(2.5)
        self.assertEqual(len(calls), 1)

        # Arrancar de nuevo despierta el loop al instante (sin reinicio).
        started = time.monotonic()
        response = client.post("/api/bot/start")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["running"])

        deadline = time.monotonic() + 5
        while len(calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual(len(calls), 2)

        # Limpieza: no dejar ciclos detrás del test.
        client.post("/api/bot/stop")


class BotApiRoutesTests(BotApiTestBase):
    def test_status_and_history(self) -> None:
        # Una decisión rechazada con motivo, visible en el historial (RF-18).
        db = self.factory()
        decision = record_decision(
            db,
            symbol="BTCUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={"rsi_period": 14},
            snapshot={"price": "100"},
        )
        mark_rejected(db, decision, "signal_expired")
        db.close()

        status = self.client.get("/api/bot/status")
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertEqual(body["fase"], "SIMULATION")
        self.assertIn("running", body)
        self.assertIn("breaker_active", body)
        self.assertIn("live_blockers", body)
        self.assertFalse(body["breaker_active"])

        # Estado "bloqueado + motivo" visible en el panel (RF-18/RF-22).
        db = self.factory()
        runtime = get_runtime(db)
        runtime.running = False
        runtime.breaker_active = True
        runtime.breaker_reason = "5 fallos consecutivos"
        db.commit()
        db.close()

        blocked = self.client.get("/api/bot/status").json()
        self.assertFalse(blocked["running"])
        self.assertTrue(blocked["breaker_active"])
        self.assertEqual(
            blocked["breaker_reason"],
            "5 fallos consecutivos",
        )

        db = self.factory()
        runtime = get_runtime(db)
        runtime.breaker_active = False
        runtime.breaker_reason = None
        db.commit()
        db.close()

        history = self.client.get(
            "/api/signals/decisions",
            params={"status": "REJECTED"},
        )
        self.assertEqual(history.status_code, 200)
        items = history.json()["decisiones"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "REJECTED")
        self.assertEqual(items[0]["rejection_reason"], "signal_expired")
        self.assertIn("pnl_usd", items[0])
        self.assertEqual(items[0]["snapshot"], {"price": "100"})

        by_symbol = self.client.get(
            "/api/signals/decisions",
            params={"symbol": "ETHUSDT"},
        )
        self.assertEqual(by_symbol.json()["decisiones"], [])

        today = self.client.get(
            "/api/signals/decisions",
            params={"day": utc_now().date().isoformat()},
        )
        self.assertEqual(len(today.json()["decisiones"]), 1)

        old = self.client.get(
            "/api/signals/decisions",
            params={"day": "2020-01-01"},
        )
        self.assertEqual(old.json()["decisiones"], [])

        metrics = self.client.get("/api/bot/metrics")
        self.assertEqual(metrics.status_code, 200)
        payload = metrics.json()
        # RF-17: saldo, posiciones, PnL, drawdown, día y bloqueo.
        for key in (
            "generated_at",
            "available_usd",
            "market_value_usd",
            "balance_usd",
            "open_positions",
            "realized_pnl_usd",
            "unrealized_pnl_usd",
            "drawdown_pct",
            "opens_today",
            "daily_loss_usd",
            "daily_blocked",
            "block_reason",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["opens_today"], 0)
        self.assertFalse(payload["daily_blocked"])
        self.assertIsNone(payload["block_reason"])

        phase = self.client.get("/api/bot/phase")
        self.assertEqual(phase.status_code, 200)
        self.assertEqual(phase.json()["fase"], "SIMULATION")

        # Sin criterios D-9 el cambio de fase queda bloqueado (RF-16).
        change = self.client.post(
            "/api/bot/phase",
            json={"phase": "TESTNET"},
        )
        self.assertEqual(change.status_code, 409)
        blocked = change.json()
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["motivo"], "criteria_not_met")
        self.assertTrue(blocked["falta"])

    def test_start_resets_breaker(self) -> None:
        # RF-22: reinicio manual — «Arrancar» cierra el breaker abierto.
        db = self.factory()
        runtime = get_runtime(db)
        runtime.running = False
        runtime.breaker_active = True
        runtime.consecutive_failures = 5
        runtime.breaker_reason = "5 consecutive cycle failures"
        db.commit()
        db.close()

        response = self.client.post("/api/bot/start")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["running"])

        status = self.client.get("/api/bot/status").json()
        self.assertTrue(status["running"])
        self.assertFalse(status["breaker_active"])
        self.assertEqual(status["consecutive_failures"], 0)
        self.assertIsNone(status["breaker_reason"])

    def test_start_without_breaker_keeps_state(self) -> None:
        # Empezar sin breaker no altera el estado de riesgo.
        db = self.factory()
        runtime = get_runtime(db)
        runtime.running = False
        runtime.breaker_active = False
        runtime.consecutive_failures = 0
        runtime.breaker_reason = None
        db.commit()
        db.close()

        response = self.client.post("/api/bot/start")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["running"])

        status = self.client.get("/api/bot/status").json()
        self.assertTrue(status["running"])
        self.assertFalse(status["breaker_active"])
        self.assertEqual(status["consecutive_failures"], 0)

    def test_start_stop_and_signal(self) -> None:
        with patch.object(
            BinanceMarketDataClient,
            "get_klines",
            return_value=CANDLES,
        ), patch.object(
            BinanceMarketDataClient,
            "get_exchange_info",
            return_value=RULES,
        ):
            accepted = self.client.post(
                "/api/signals/external",
                json={
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "source": "copy",
                },
            )
            self.assertEqual(accepted.status_code, 200)
            body = accepted.json()
            self.assertEqual(body["estado"], "aceptada")
            self.assertEqual(body["symbol"], "BTCUSDT")
            self.assertIsNotNone(body["quantity"])

            # RF-20: webhook con el mismo contrato que el panel.
            hook = self.client.post(
                "/api/webhooks/signal",
                json={
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "source": "copy",
                },
            )
            self.assertEqual(hook.status_code, 200)
            self.assertEqual(hook.json()["estado"], "rechazada")
            self.assertEqual(hook.json()["motivo"], "duplicate_signal")

            expired = self.client.post(
                "/api/signals/external",
                json={
                    "symbol": "ETHUSDT",
                    "side": "BUY",
                    "source": "copy",
                    "issued_at": (
                        utc_now() - timedelta(seconds=600)
                    ).isoformat(),
                },
            )
            self.assertEqual(expired.status_code, 200)
            self.assertEqual(expired.json()["estado"], "rechazada")
            self.assertEqual(expired.json()["motivo"], "signal_expired")

            unknown = self.client.post(
                "/api/signals/external",
                json={
                    "symbol": "FOOUSDT",
                    "side": "BUY",
                    "source": "copy",
                },
            )
            self.assertEqual(unknown.status_code, 200)
            self.assertEqual(unknown.json()["motivo"], "unknown_symbol")

            bad_side = self.client.post(
                "/api/signals/external",
                json={
                    "symbol": "BTCUSDT",
                    "side": "HOLD",
                    "source": "copy",
                },
            )
            self.assertEqual(bad_side.status_code, 200)
            self.assertEqual(bad_side.json()["motivo"], "invalid_side")

        # La aceptada queda en cola PENDING para el loop (RF-8/RF-10).
        db = self.factory()
        pending = list(
            db.scalars(
                select(SignalDecision).where(
                    SignalDecision.status == DecisionStatus.PENDING,
                    SignalDecision.origin == DecisionOrigin.EXTERNAL,
                )
            ).all()
        )
        rejected = list(
            db.scalars(
                select(SignalDecision).where(
                    SignalDecision.status == DecisionStatus.REJECTED
                )
            ).all()
        )
        db.close()
        self.assertEqual(len(pending), 1)
        self.assertIsNotNone(pending[0].quantity)
        self.assertEqual(len(rejected), 4)
        reasons = {row.rejection_reason for row in rejected}
        self.assertEqual(
            reasons,
            {
                "duplicate_signal",
                "signal_expired",
                "unknown_symbol",
                "invalid_side",
            },
        )

        stop = self.client.post("/api/bot/stop")
        self.assertEqual(stop.status_code, 200)
        self.assertFalse(stop.json()["running"])
        start = self.client.post("/api/bot/start")
        self.assertEqual(start.status_code, 200)
        self.assertTrue(start.json()["running"])

    def test_token_required_in_live(self) -> None:
        with patch.object(settings, "api_token", "sekret"):
            # Fase TESTNET directa en BD (el cambio está bloqueado sin D-9).
            db = self.factory()
            phase = get_phase(db)
            phase.phase = BotPhaseName.TESTNET
            db.commit()
            db.close()

            denied = self.client.post("/api/bot/stop")
            self.assertEqual(denied.status_code, 401)

            wrong = self.client.post(
                "/api/bot/stop",
                headers={"Authorization": "Bearer otra-clave"},
            )
            self.assertEqual(wrong.status_code, 401)

            hook_denied = self.client.post(
                "/api/webhooks/signal",
                json={"symbol": "BTCUSDT", "side": "BUY", "source": "x"},
            )
            self.assertEqual(hook_denied.status_code, 401)

            ok_header = self.client.post(
                "/api/bot/stop",
                headers={"Authorization": "Bearer sekret"},
            )
            self.assertEqual(ok_header.status_code, 200)
            self.assertFalse(ok_header.json()["running"])

            ok_query = self.client.post("/api/bot/start?token=sekret")
            self.assertEqual(ok_query.status_code, 200)
            self.assertTrue(ok_query.json()["running"])

            # Lectura abierta sin token (RF-20 protege operación/reconfig).
            status = self.client.get("/api/bot/status")
            self.assertEqual(status.status_code, 200)

            # Con token configurado, también protege en simulación.
            db = self.factory()
            phase = get_phase(db)
            phase.phase = BotPhaseName.SIMULATION
            db.commit()
            db.close()
            sim_denied = self.client.post("/api/bot/stop")
            self.assertEqual(sim_denied.status_code, 401)
            sim_ok = self.client.post("/api/bot/stop?token=sekret")
            self.assertEqual(sim_ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()

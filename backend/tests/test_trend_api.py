"""GET /api/bot/trend: qué hará el bot hoy, sin token y sin red real."""

import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import bot as bot_routes
from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.models import DecisionOrigin, PositionV2, TradeSide
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import MarketDataUnavailable
from app.services.decision_store import record_decision
from app.services.simulation_service import create_simulation_account
from test_trend_loop import NOW, daily


class TrendApiTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.mkdtemp(prefix="trend-api-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        engine = create_engine(
            f"sqlite:///{Path(tmp) / 'api.db'}",
            connect_args={"check_same_thread": False},
        )
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        self.factory = sessionmaker(bind=engine)
        for target, value in (
            ("app.database.SessionLocal", self.factory),
            ("app.api.routes.bot.utc_now", lambda: NOW),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        db = self.factory()
        self.account = create_simulation_account(
            db, SimulationAccountCreate(name="t", initial_balance_usd=Decimal("40"))
        )
        db.close()
        self.client = TestClient(app)

    def _get(self, klines):
        with (
            patch.object(settings, "trend_symbols", "BTCUSDT,ETHUSDT"),
            patch.object(settings, "simulation_bot_account_id", self.account.id),
            patch.object(bot_routes.trend_market, "get_klines", side_effect=klines),
        ):
            response = self.client.get("/api/bot/trend")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_reports_signal_and_next_action_per_pair(self) -> None:
        db = self.factory()
        decision = record_decision(
            db,
            symbol="ETHUSDT",
            side=TradeSide.BUY,
            origin=DecisionOrigin.TECHNICAL,
            config={},
            snapshot={},
        )
        db.add(
            PositionV2(
                account_id=self.account.id,
                decision_id=decision.id,
                symbol="ETHUSDT",
                quantity=Decimal("0.01"),
                average_entry_price=Decimal("2000"),
            )
        )
        db.commit()
        db.close()
        series = {"BTCUSDT": daily("110"), "ETHUSDT": daily("90")}
        body = self._get(lambda symbol, **_: series[symbol])

        btc, eth = body["pairs"]
        self.assertEqual((btc["signal"], btc["action"]), ("DENTRO", "Comprará en el próximo ciclo"))
        self.assertEqual((eth["signal"], eth["action"]), ("FUERA", "Venderá en el próximo ciclo"))
        self.assertEqual(btc["candle_date"], "2026-10-15")
        self.assertEqual(body["next_decision_utc"], "2026-10-17T00:00:00")

    def test_market_error_is_shown_not_raised(self) -> None:
        def fail(symbol, **_):
            raise MarketDataUnavailable("Binance caído")

        body = self._get(fail)
        self.assertEqual(body["pairs"][0]["signal"], "SIN DATOS")


if __name__ == "__main__":
    unittest.main()

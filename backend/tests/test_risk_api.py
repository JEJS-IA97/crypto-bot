"""Tests rojos — Spec 008: endpoint de exposición (RF-6).

``GET /api/bot/risk/exposure``: 200 sin token, decimales como texto,
exposición total/por activo/por dirección y límites vigentes; nunca 500.
"""

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
from app.database import Base
from app.main import app
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.simulation_service import create_simulation_account


class ExposureEndpointBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="risk-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "risk.db"
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        self.engine = engine
        self.addCleanup(engine.dispose)
        factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
        patcher = patch("app.database.SessionLocal", factory)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = factory()

        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="risk-api",
                initial_balance_usd=Decimal("1000"),
            ),
        )
        for field, value in (
            ("api_token", "super-secret-token"),
            ("simulation_bot_account_id", self.account.id),
        ):
            field_patcher = patch.object(settings, field, value)
            field_patcher.start()
            self.addCleanup(field_patcher.stop)

        self.client = TestClient(app)

    def _insert_open_position(
        self, symbol: str, quantity: str, price: str = "100"
    ) -> None:
        decision = SignalDecision(
            client_order_id=f"api-{symbol}",
            symbol=symbol,
            side=TradeSide.BUY,
            origin=DecisionOrigin.EXTERNAL,
            status=DecisionStatus.OPENED,
            config_json="{}",
            market_snapshot_json="{}",
        )
        self.db.add(decision)
        self.db.commit()
        self.db.add(
            PositionV2(
                account_id=self.account.id,
                decision_id=decision.id,
                symbol=symbol,
                quantity=Decimal(quantity),
                average_entry_price=Decimal(price),
                status=PositionStatus.OPEN,
            )
        )
        self.db.commit()


class ExposureEndpointTests(ExposureEndpointBase):
    def test_200_without_token(self) -> None:
        response = self.client.get("/api/bot/risk/exposure")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["capital_usd"], "20")
        self.assertEqual(body["committed_usd"], "0")
        self.assertEqual(body["available_usd"], "1000")
        self.assertEqual(body["open_positions"], 0)
        self.assertEqual(body["max_open_positions"], 3)

    def test_decimals_are_serialized_as_text(self) -> None:
        body = self.client.get("/api/bot/risk/exposure").json()
        for key in (
            "capital_usd",
            "committed_usd",
            "available_usd",
            "exposure_cap_usd",
            "exposure_pct",
            "headroom_usd",
        ):
            with self.subTest(key=key):
                self.assertIsInstance(body[key], str)

    def test_snapshot_reflects_open_positions(self) -> None:
        self._insert_open_position("ETHUSDT", "0.05")

        body = self.client.get("/api/bot/risk/exposure").json()
        self.assertEqual(body["committed_usd"], "5")
        self.assertEqual(body["open_positions"], 1)
        self.assertEqual(body["by_asset"], {"ETHUSDT": "5"})
        self.assertEqual(body["by_direction"]["LONG"], "5")
        self.assertEqual(body["by_direction"]["NEUTRAL"], "0")
        self.assertEqual(body["exposure_cap_usd"], "15")
        self.assertEqual(body["headroom_usd"], "10")
        self.assertEqual(Decimal(body["exposure_pct"]), Decimal("25"))

    def test_limits_are_reported(self) -> None:
        body = self.client.get("/api/bot/risk/exposure").json()
        limits = body["limits"]
        self.assertEqual(limits["max_open_positions"], 3)
        self.assertEqual(Decimal(limits["daily_loss_limit_pct"]), Decimal("5"))
        self.assertEqual(limits["max_opens_per_day"], 10)
        self.assertEqual(
            Decimal(limits["max_loss_per_trade_usd"]), Decimal("1")
        )
        self.assertEqual(
            Decimal(limits["max_total_exposure_pct"]), Decimal("75")
        )
        self.assertEqual(
            Decimal(limits["correlation_threshold"]), Decimal("0.7")
        )

    def test_missing_account_is_200_not_500(self) -> None:
        with patch.object(settings, "simulation_bot_account_id", 999):
            response = self.client.get("/api/bot/risk/exposure")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["available_usd"])
        self.assertEqual(body["committed_usd"], "0")


if __name__ == "__main__":
    unittest.main()

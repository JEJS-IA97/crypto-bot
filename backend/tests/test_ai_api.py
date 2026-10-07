"""Tests rojos — Spec 007: endpoints del analista IA (RF-7).

``POST /api/bot/ai/analyze`` y ``GET /api/bot/ai/recommendations``: 200
por estado (sin token), 404 fuera del universo y nunca 500.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.domain.signal_engine import Candle
from app.main import app
from app.services.binance_market_data_client import (
    DepthBook,
    Ticker24,
)

BASE = datetime(2026, 10, 7, 12, 0)

DEPTH_OK = DepthBook(
    last_update_id=1,
    bids=((Decimal("100"), Decimal("5")),),
    asks=((Decimal("100.5"), Decimal("5")),),
)

TICKER_OK = Ticker24(
    last_price=Decimal("100.4"),
    price_change_pct=Decimal("1.25"),
    quote_volume_24h=Decimal("123456.78"),
)

VALID_RESPONSE = {
    "decision": "WAIT",
    "direction": "LONG",
    "confidence": 0.64,
    "setup_quality": 0.71,
    "risk_flags": [],
    "supporting_factors": ["ema_trend_up"],
    "contradicting_factors": [],
    "invalidating_conditions": ["close_below_range_low"],
    "time_horizon": "4h",
    "suggested_entry_zone": None,
    "suggested_stop_zone": None,
    "suggested_take_profit_zone": None,
    "reason_codes": ["trend_aligned"],
    "required_next_check": "volume_on_breakout",
    "data_quality": {"order_book": "fresh", "news": "disabled"},
}


def _candles(count: int) -> list[Candle]:
    return [
        Candle(
            open_time=BASE + timedelta(minutes=15 * index),
            open=Decimal(100 + index),
            high=Decimal(101 + index),
            low=Decimal(99 + index),
            close=Decimal(100 + index),
            volume=Decimal(10 + index),
        )
        for index in range(count)
    ]


class FakeKlineMarket:
    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        return _candles(30)

    def get_depth(self, symbol: str, limit: int = 5) -> DepthBook:
        return DEPTH_OK

    def get_ticker_24h(self, symbol: str) -> Ticker24:
        return TICKER_OK


class AiApiBase(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import market_context_service
        from app.services.ai_advisor_service import reset_state

        market_context_service.clear_cache()
        self.addCleanup(market_context_service.clear_cache)

        self.tmpdir = tempfile.mkdtemp(prefix="ai-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "ai.db"
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
        self.Session = factory
        self.db = factory()

        # Token presente pero NO requerido por la IA (RF-7).
        for field, value in (
            ("api_token", "super-secret-token"),
            ("gemini_api_key", "test-key"),
            ("gemini_daily_query_limit", 100),
            ("gemini_cache_seconds", 0),
            ("fear_greed_url", ""),
            ("news_rss_feeds", ""),
        ):
            field_patcher = patch.object(settings, field, value)
            field_patcher.start()
            self.addCleanup(field_patcher.stop)

        reset_state()
        self.addCleanup(reset_state)

        market_patcher = patch(
            "app.services.ai_advisor_service.BinanceMarketDataClient",
            return_value=FakeKlineMarket(),
        )
        market_patcher.start()
        self.addCleanup(market_patcher.stop)

        gemini_patcher = patch(
            "app.services.ai_advisor_service.GeminiClient"
        )
        self.gemini_cls = gemini_patcher.start()
        self.addCleanup(gemini_patcher.stop)
        self.gemini_instance = MagicMock()
        self.gemini_cls.return_value = self.gemini_instance
        self.gemini_instance.generate.return_value = SimpleNamespace(
            text=json.dumps(VALID_RESPONSE),
            input_tokens=100,
            output_tokens=40,
            model=settings.gemini_model,
            request_id="req-api",
            latency_ms=15,
        )

        self.client = TestClient(app)

    def _post(self, payload: dict, **kwargs):
        return self.client.post(
            "/api/bot/ai/analyze", json=payload, **kwargs
        )

    def _insert_evaluations(self, count: int) -> None:
        from app.models import AiEvaluation

        for index in range(count):
            self.db.add(
                AiEvaluation(
                    symbol="BTCUSDT",
                    trigger="manual",
                    status="OK",
                    decision="WAIT",
                    confidence=Decimal("0.5"),
                    request_id=f"req-{index}",
                    correlation_id=f"corr-{index}",
                    model=settings.gemini_model,
                    prompt_version="v-test",
                    latency_ms=10,
                    input_tokens=1,
                    output_tokens=1,
                    cost_usd=Decimal("0"),
                    created_at=BASE + timedelta(seconds=index),
                )
            )
        self.db.commit()


class AnalyzeEndpointTests(AiApiBase):
    def test_analyze_ok_without_token(self) -> None:
        response = self._post({"symbol": "BTCUSDT"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "OK")
        self.assertFalse(body["cached"])
        recommendation = body["recommendation"]
        self.assertEqual(recommendation["decision"], "WAIT")
        self.assertEqual(recommendation["direction"], "LONG")
        self.assertAlmostEqual(
            float(recommendation["confidence"]), 0.64, places=9
        )
        evaluation = body["evaluation"]
        self.assertEqual(evaluation["symbol"], "BTCUSDT")
        self.assertEqual(evaluation["trigger"], "manual")
        self.assertEqual(evaluation["status"], "OK")
        self.assertEqual(evaluation["model"], settings.gemini_model)
        self.assertTrue(evaluation["prompt_version"])
        self.assertEqual(evaluation["latency_ms"], 15)
        self.assertEqual(float(Decimal(str(evaluation["coste_usd"]))), 0.0)
        self.assertTrue(evaluation["request_id"])
        self.assertGreater(evaluation["id"], 0)

    def test_second_call_is_cached(self) -> None:
        first = self._post({"symbol": "BTCUSDT"})
        second = self._post({"symbol": "BTCUSDT"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["cached"])
        self.assertEqual(self.gemini_instance.generate.call_count, 1)

    def test_unknown_symbol_is_404(self) -> None:
        response = self._post({"symbol": "XMRUSDT"})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "symbol_not_in_universe")
        self.gemini_instance.generate.assert_not_called()

    def test_missing_body_is_422(self) -> None:
        response = self._post({})

        self.assertEqual(response.status_code, 422)

    def test_disabled_returns_200_with_null_recommendation(self) -> None:
        with patch.object(settings, "gemini_api_key", ""):
            response = self._post({"symbol": "BTCUSDT"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "DISABLED")
        self.assertIsNone(body["recommendation"])
        self.assertIsNone(body["evaluation"])
        self.gemini_cls.assert_not_called()

    def test_quota_exceeded_returns_200_not_500(self) -> None:
        with patch.object(settings, "gemini_daily_query_limit", 0):
            response = self._post({"symbol": "BTCUSDT"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "QUOTA_EXCEEDED")
        self.assertIsNone(body["recommendation"])

    def test_client_failure_returns_200_not_500(self) -> None:
        from app.services.gemini_client import GeminiUnavailable

        self.gemini_instance.generate.side_effect = GeminiUnavailable("down")
        response = self._post({"symbol": "BTCUSDT"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "ERROR")


class RecommendationsEndpointTests(AiApiBase):
    def _get(self, **params):
        return self.client.get(
            "/api/bot/ai/recommendations", params=params
        )

    def test_listing_returns_latest_first(self) -> None:
        self._insert_evaluations(3)

        response = self._get()

        self.assertEqual(response.status_code, 200)
        items = response.json()["recommendations"]
        self.assertEqual(len(items), 3)
        self.assertGreater(items[0]["id"], items[1]["id"])
        first = items[0]
        for key in (
            "id",
            "symbol",
            "created_at",
            "trigger",
            "status",
            "decision",
            "confidence",
            "coste_usd",
            "model",
            "prompt_version",
            "latency_ms",
        ):
            self.assertIn(key, first)
        self.assertIsInstance(float(first["confidence"]), float)
        self.assertIsInstance(first["coste_usd"], str)

    def test_symbol_filter_and_unknown_symbol_404(self) -> None:
        self._insert_evaluations(2)

        filtered = self._get(symbol="BTCUSDT", limit=1)
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(
            len(filtered.json()["recommendations"]), 1
        )

        unknown = self._get(symbol="XMRUSDT")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(
            unknown.json()["detail"], "symbol_not_in_universe"
        )

    def test_limit_clamps(self) -> None:
        self._insert_evaluations(55)

        minimum = self._get(limit=0)
        self.assertEqual(minimum.status_code, 200)
        self.assertEqual(len(minimum.json()["recommendations"]), 1)

        maximum = self._get(limit=5000)
        self.assertEqual(len(maximum.json()["recommendations"]), 50)

        default = self._get()
        self.assertEqual(len(default.json()["recommendations"]), 20)


if __name__ == "__main__":
    unittest.main()

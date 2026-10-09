"""Tests rojos — Spec 007: servicio de asesoría IA (RF-1/RF-3/RF-4/RF-6).

Estados DISABLED/cuota/presupuesto/breaker/caché, contexto honesto
(006 + cartera + riesgo), persistencia en ``ai_evaluations``, evento
``ai.consultation`` y fuente ``gemini`` en el health de 005.
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

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.domain.signal_engine import Candle
from app.services.binance_market_data_client import (
    DepthBook,
    MarketDataUnavailable,
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
    "risk_flags": ["near_range_high"],
    "supporting_factors": ["ema_trend_up"],
    "contradicting_factors": ["near_resistance"],
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
    start = BASE - timedelta(minutes=15 * (count - 1))
    return [
        Candle(
            open_time=start + timedelta(minutes=15 * index),
            open=Decimal(100 + index),
            high=Decimal(101 + index),
            low=Decimal(99 + index),
            close=Decimal(100 + index),
            volume=Decimal(10 + index),
        )
        for index in range(count)
    ]


def _reply(text: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        text=text if text is not None else json.dumps(VALID_RESPONSE),
        input_tokens=120,
        output_tokens=45,
        model=settings.gemini_model,
        request_id="req-abc",
        latency_ms=42,
    )


class FakeKlineMarket:
    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        return _candles(30)

    def get_depth(self, symbol: str, limit: int = 5) -> DepthBook:
        return DEPTH_OK

    def get_ticker_24h(self, symbol: str) -> Ticker24:
        return TICKER_OK


class BrokenKlineMarket(FakeKlineMarket):
    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        raise MarketDataUnavailable("sin klines")


class AdvisorBase(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import market_context_service
        from app.services.ai_advisor_service import reset_state

        market_context_service.clear_cache()
        self.addCleanup(market_context_service.clear_cache)

        self.tmpdir = tempfile.mkdtemp(prefix="ai-svc-")
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

        for field, value in (
            ("gemini_api_key", "test-key"),
            ("gemini_daily_query_limit", 100),
            ("gemini_cache_seconds", 0),
            ("gemini_breaker_failures", 3),
            ("fear_greed_url", ""),
            ("news_rss_feeds", ""),
        ):
            field_patcher = patch.object(settings, field, value)
            field_patcher.start()
            self.addCleanup(field_patcher.stop)

        reset_state()
        self.addCleanup(reset_state)

        self.market_patcher = patch(
            "app.services.ai_advisor_service.BinanceMarketDataClient",
            return_value=FakeKlineMarket(),
        )
        self.market_patcher.start()
        self.addCleanup(self.market_patcher.stop)

        self.gemini_class = patch(
            "app.services.ai_advisor_service.GeminiClient"
        )
        self.gemini_cls = self.gemini_class.start()
        self.addCleanup(self.gemini_class.stop)
        self.gemini_instance = MagicMock()
        self.gemini_cls.return_value = self.gemini_instance
        self.gemini_instance.generate.return_value = _reply()

    def _analyze(self, symbol: str = "BTCUSDT", **kwargs):
        from app.services.ai_advisor_service import analyze

        kwargs.setdefault("now", BASE)
        return analyze(symbol, db=self.db, **kwargs)

    def _events(self, name: str | None = None) -> list:
        from app.models import SystemEvent

        rows = self.db.scalars(select(SystemEvent)).all()
        if name is None:
            return list(rows)
        return [row for row in rows if row.event == name]

    def _ai_rows(self) -> list:
        from app.models import AiEvaluation

        return list(self.db.scalars(select(AiEvaluation)).all())


class ConfigStateTests(AdvisorBase):
    def test_disabled_without_api_key(self) -> None:
        with patch.object(settings, "gemini_api_key", ""):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "DISABLED")
        self.assertIsNone(outcome.evaluation)
        self.assertFalse(outcome.cached)
        self.assertEqual(self._ai_rows(), [])
        self.assertEqual(self._events("ai.consultation"), [])
        self.gemini_cls.assert_not_called()

    def test_disabled_without_model(self) -> None:
        with patch.object(settings, "gemini_model", ""):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "DISABLED")
        self.gemini_cls.assert_not_called()

    def test_local_quota_blocks_before_query(self) -> None:
        from app.models import AiEvaluation

        with patch.object(settings, "gemini_daily_query_limit", 2):
            for index in range(2):
                self.db.add(
                    AiEvaluation(
                        symbol="ETHUSDT",
                        trigger="manual",
                        status="OK",
                        created_at=BASE - timedelta(minutes=index + 1),
                    )
                )
            self.db.commit()
            outcome = self._analyze()

        self.assertEqual(outcome.state, "QUOTA_EXCEEDED")
        self.assertIsNone(outcome.evaluation)
        self.gemini_instance.generate.assert_not_called()
        self.assertEqual(len(self._ai_rows()), 2)
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "WARNING")

    def test_quota_counts_only_current_utc_day(self) -> None:
        from app.models import AiEvaluation

        self.db.add(
            AiEvaluation(
                symbol="ETHUSDT",
                trigger="manual",
                status="OK",
                created_at=BASE - timedelta(days=1),
            )
        )
        self.db.commit()
        with patch.object(settings, "gemini_daily_query_limit", 1):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "OK")

    def test_budget_blocks_when_prices_configured(self) -> None:
        with (
            patch.object(settings, "gemini_price_mtok_input", Decimal("1")),
            patch.object(settings, "gemini_price_mtok_output", Decimal("1")),
            patch.object(settings, "gemini_daily_budget_usd", Decimal("0")),
        ):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "BUDGET_EXCEEDED")
        self.assertIsNone(outcome.evaluation)
        self.gemini_instance.generate.assert_not_called()
        self.assertEqual(self._ai_rows(), [])
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "WARNING")

    def test_cost_is_recorded_from_token_usage(self) -> None:
        with (
            patch.object(settings, "gemini_price_mtok_input", Decimal("2")),
            patch.object(settings, "gemini_price_mtok_output", Decimal("6")),
            patch.object(settings, "gemini_daily_budget_usd", Decimal("10")),
        ):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "OK")
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        # (120 * 2 + 45 * 6) / 1_000_000
        self.assertEqual(rows[0].cost_usd, Decimal("0.00051"))


class SuccessPersistenceTests(AdvisorBase):
    def test_success_persists_row_event_and_source(self) -> None:
        from app.services.ai_advisor_service import PROMPT_VERSION

        outcome = self._analyze()

        self.assertEqual(outcome.state, "OK")
        self.assertFalse(outcome.cached)
        self.assertIsNotNone(outcome.evaluation)

        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.symbol, "BTCUSDT")
        self.assertEqual(row.trigger, "manual")
        self.assertEqual(row.status, "OK")
        self.assertEqual(row.decision, "WAIT")
        self.assertEqual(row.direction, "LONG")
        self.assertIsInstance(row.confidence, Decimal)
        self.assertEqual(row.request_id, "req-abc")
        self.assertTrue(row.correlation_id)
        self.assertEqual(row.model, settings.gemini_model)
        self.assertEqual(row.prompt_version, PROMPT_VERSION)
        self.assertEqual(row.latency_ms, 42)
        self.assertEqual(row.input_tokens, 120)
        self.assertEqual(row.output_tokens, 45)
        self.assertEqual(row.cost_usd, Decimal("0"))
        self.assertEqual(row.created_at, BASE)
        context = json.loads(row.context_json)
        self.assertEqual(context["asset"], "BTCUSDT")
        response = json.loads(row.response_json)
        self.assertEqual(response["decision"], "WAIT")

        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "INFO")
        self.assertEqual(events[0].result, "ok")
        self.assertEqual(events[0].asset, "BTCUSDT")
        self.assertEqual(events[0].service, "ai_advisor")
        payload = json.loads(events[0].payload_json)
        self.assertEqual(payload["state"], "OK")

        from app.models import SourceHealth
        from app.services.observability_service import KNOWN_SOURCES

        self.assertIn("gemini", KNOWN_SOURCES)
        health = self.db.get(SourceHealth, "gemini")
        self.assertIsNotNone(health)
        self.assertEqual(health.state, "HEALTHY")

    def test_client_failure_persists_error_and_marks_source(self) -> None:
        from app.services.gemini_client import GeminiUnavailable

        self.gemini_instance.generate.side_effect = GeminiUnavailable(
            "boom"
        )
        outcome = self._analyze()

        self.assertEqual(outcome.state, "ERROR")
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "ERROR")
        self.assertIn("boom", rows[0].error)
        self.assertIsNone(rows[0].decision)

        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "ERROR")
        self.assertEqual(events[0].result, "failed")

        from app.models import SourceHealth

        health = self.db.get(SourceHealth, "gemini")
        self.assertIsNotNone(health)
        self.assertEqual(health.state, "ERROR")

    def test_google_quota_maps_to_quota_state(self) -> None:
        from app.services.gemini_client import GeminiQuotaExceeded

        self.gemini_instance.generate.side_effect = GeminiQuotaExceeded(
            "HTTP 429"
        )
        outcome = self._analyze()

        self.assertEqual(outcome.state, "QUOTA_EXCEEDED")
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "ERROR")
        self.assertTrue(rows[0].error)
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "WARNING")

    def test_non_json_answer_maps_to_invalid_response(self) -> None:
        self.gemini_instance.generate.return_value = _reply(
            text="Comprar BTC ya."
        )
        outcome = self._analyze()

        self.assertEqual(outcome.state, "INVALID_RESPONSE")
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "ERROR")
        self.assertIsNone(rows[0].decision)
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "ERROR")


class ContextTests(AdvisorBase):
    def test_context_payload_is_complete_and_honest(self) -> None:
        from app.models import DailyRiskState

        self.db.add(
            DailyRiskState(
                day=BASE.date(),
                start_equity_usd=Decimal("20"),
                realized_pnl_usd=Decimal("-0.5"),
                opens_count=1,
                blocked=False,
            )
        )
        self.db.commit()

        outcome = self._analyze()
        self.assertEqual(outcome.state, "OK")

        context = json.loads(self._ai_rows()[0].context_json)
        for key in (
            "asset",
            "timestamp",
            "generated_by",
            "market",
            "features",
            "score",
            "portfolio",
            "risk",
            "constraints",
            "data_quality",
        ):
            self.assertIn(key, context)
        self.assertEqual(context["asset"], "BTCUSDT")
        self.assertEqual(context["timestamp"], BASE.isoformat())
        self.assertEqual(context["generated_by"], "crypto-bot/007")

        market = context["market"]
        self.assertEqual(
            market["ticker"]["last_price"], "100.4"
        )
        self.assertTrue(market["sources"])

        features = context["features"]
        for key in (
            "return_pct",
            "volatility_pct",
            "range_position_pct",
            "volume_zscore",
            "ema_spread_pct",
            "rsi",
        ):
            self.assertIn(key, features)

        self.assertIn("score", context["score"])
        float(context["score"]["score"])

        self.assertEqual(context["portfolio"]["open_count"], 0)
        self.assertEqual(context["portfolio"]["open_positions"], [])

        risk = context["risk"]
        self.assertEqual(risk["day"], "2026-10-07")
        self.assertEqual(risk["realized_pnl_usd"], "-0.5")
        self.assertEqual(risk["opens_count"], 1)
        self.assertFalse(risk["blocked"])

        constraints = context["constraints"]
        self.assertEqual(
            constraints["stop_loss_pct"], str(settings.stop_loss_pct)
        )
        self.assertEqual(
            constraints["configured_capital_usd"],
            str(settings.configured_capital_usd),
        )

        quality = context["data_quality"]
        self.assertEqual(quality["klines"], "ok")
        self.assertEqual(quality["market_context"], "ok")
        self.assertEqual(quality["portfolio"], "ok")
        self.assertEqual(quality["risk"], "ok")

    def test_missing_risk_state_is_null_not_invented(self) -> None:
        outcome = self._analyze()
        self.assertEqual(outcome.state, "OK")

        context = json.loads(self._ai_rows()[0].context_json)
        self.assertIsNone(context["risk"])
        self.assertEqual(context["data_quality"]["risk"], "unavailable")

    def test_open_position_is_included(self) -> None:
        from app.models import PositionStatus, PositionV2

        self.db.add(
            PositionV2(
                account_id=1,
                decision_id=1,
                symbol="BTCUSDT",
                quantity=Decimal("0.001"),
                average_entry_price=Decimal("100"),
                status=PositionStatus.OPEN,
            )
        )
        self.db.commit()

        outcome = self._analyze()
        self.assertEqual(outcome.state, "OK")

        context = json.loads(self._ai_rows()[0].context_json)
        self.assertEqual(context["portfolio"]["open_count"], 1)
        position = context["portfolio"]["open_positions"][0]
        self.assertEqual(position["symbol"], "BTCUSDT")
        self.assertEqual(position["quantity"], "0.001")

    def test_context_failure_degrades_market_but_still_consults(self) -> None:
        with patch(
            "app.services.ai_advisor_service.get_context",
            side_effect=RuntimeError("ctx down"),
        ):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "OK")
        context = json.loads(self._ai_rows()[0].context_json)
        self.assertIsNone(context["market"])
        self.assertEqual(
            context["data_quality"]["market_context"], "unavailable"
        )

    def test_klines_failure_aborts_without_query(self) -> None:
        with patch(
            "app.services.ai_advisor_service.BinanceMarketDataClient",
            return_value=BrokenKlineMarket(),
        ):
            outcome = self._analyze()

        self.assertEqual(outcome.state, "ERROR")
        self.gemini_instance.generate.assert_not_called()
        self.assertEqual(self._ai_rows(), [])
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "ERROR")


class CacheBreakerTests(AdvisorBase):
    def _patch_cache(self, seconds: int) -> None:
        patcher = patch.object(settings, "gemini_cache_seconds", seconds)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_cache_hit_skips_query_and_event(self) -> None:
        self._patch_cache(3600)

        first = self._analyze()
        second = self._analyze()

        self.assertEqual(first.state, "OK")
        self.assertFalse(first.cached)
        self.assertEqual(second.state, "OK")
        self.assertTrue(second.cached)
        self.assertEqual(self.gemini_instance.generate.call_count, 1)
        self.assertEqual(len(self._ai_rows()), 1)
        self.assertEqual(len(self._events("ai.consultation")), 1)

    def test_force_bypasses_cache(self) -> None:
        self._patch_cache(3600)

        self._analyze()
        outcome = self._analyze(force=True)

        self.assertFalse(outcome.cached)
        self.assertEqual(self.gemini_instance.generate.call_count, 2)
        self.assertEqual(len(self._ai_rows()), 2)

    def test_cache_expires_after_ttl(self) -> None:
        self._patch_cache(3600)

        self._analyze(now=BASE)
        outcome = self._analyze(now=BASE + timedelta(seconds=3601))

        self.assertFalse(outcome.cached)
        self.assertEqual(self.gemini_instance.generate.call_count, 2)

    def test_breaker_opens_after_consecutive_failures(self) -> None:
        from app.services.gemini_client import GeminiUnavailable

        with patch.object(settings, "gemini_breaker_failures", 2):
            self.gemini_instance.generate.side_effect = GeminiUnavailable(
                "down"
            )
            first = self._analyze()
            second = self._analyze()
            third = self._analyze()

        self.assertEqual(first.state, "ERROR")
        self.assertEqual(second.state, "ERROR")
        self.assertEqual(third.state, "BREAKER_OPEN")
        self.assertEqual(self.gemini_instance.generate.call_count, 2)
        self.assertEqual(len(self._ai_rows()), 2)
        events = self._events("ai.consultation")
        self.assertEqual(len(events), 3)
        self.assertEqual(events[2].level, "WARNING")

    def test_breaker_resets_after_success(self) -> None:
        from app.services.gemini_client import GeminiUnavailable

        with patch.object(settings, "gemini_breaker_failures", 2):
            self.gemini_instance.generate.side_effect = GeminiUnavailable(
                "down"
            )
            self._analyze()
            self.gemini_instance.generate.side_effect = None
            self.gemini_instance.generate.return_value = _reply()
            recovered = self._analyze()
            self.gemini_instance.generate.side_effect = GeminiUnavailable(
                "down"
            )
            after = self._analyze()

        self.assertEqual(recovered.state, "OK")
        self.assertEqual(after.state, "ERROR")
        self.assertEqual(self.gemini_instance.generate.call_count, 3)


if __name__ == "__main__":
    unittest.main()

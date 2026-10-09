"""Tests rojos — Spec 007: pasada diaria opcional de análisis (RF-8).

``run_daily_pass`` solo corre con ``GEMINI_AUTO_ANALYSIS=true``, respeta el
guard de 24 h sobre el último ``trigger="auto"``, analiza el top-N de
candidatos y para en el primer estado no ``OK`` sin reintentar.
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


class FakeKlineMarket:
    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        return _candles(30)

    def get_depth(self, symbol: str, limit: int = 5) -> DepthBook:
        return DEPTH_OK

    def get_ticker_24h(self, symbol: str) -> Ticker24:
        return TICKER_OK


class DailyPassBase(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import market_context_service
        from app.services.ai_advisor_service import reset_state

        market_context_service.clear_cache()
        self.addCleanup(market_context_service.clear_cache)

        self.tmpdir = tempfile.mkdtemp(prefix="ai-daily-")
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
            ("gemini_auto_analysis", True),
            ("gemini_auto_analysis_limit", 3),
            ("trading_symbols", "BTCUSDT,ETHUSDT"),
            ("fear_greed_url", ""),
            ("news_rss_feeds", ""),
        ):
            field_patcher = patch.object(settings, field, value)
            field_patcher.start()
            self.addCleanup(field_patcher.stop)

        reset_state()
        self.addCleanup(reset_state)

        for target in (
            "app.services.ai_advisor_service.BinanceMarketDataClient",
            "app.services.ai_daily_analysis.BinanceMarketDataClient",
        ):
            market_patcher = patch(
                target, return_value=FakeKlineMarket()
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
            request_id="req-daily",
            latency_ms=15,
        )

    def _run(self, **kwargs):
        from app.services.ai_daily_analysis import run_daily_pass

        kwargs.setdefault("now", BASE)
        kwargs.setdefault("db", self.db)
        return run_daily_pass(**kwargs)

    def _ai_rows(self) -> list:
        from app.models import AiEvaluation

        return list(self.db.scalars(select(AiEvaluation)).all())

    def _daily_events(self) -> list:
        from app.models import SystemEvent

        return [
            row
            for row in self.db.scalars(select(SystemEvent)).all()
            if row.event == "ai.daily_analysis"
        ]


class DailyPassTests(DailyPassBase):
    def test_noop_when_auto_disabled(self) -> None:
        with patch.object(settings, "gemini_auto_analysis", False):
            analyzed = self._run()

        self.assertEqual(analyzed, 0)
        self.assertEqual(self._ai_rows(), [])
        self.gemini_instance.generate.assert_not_called()
        self.assertEqual(self._daily_events(), [])

    def test_noop_when_key_missing(self) -> None:
        with patch.object(settings, "gemini_api_key", ""):
            analyzed = self._run()

        self.assertEqual(analyzed, 0)
        self.gemini_instance.generate.assert_not_called()

    def test_analyses_top_candidate_once(self) -> None:
        with patch.object(settings, "gemini_auto_analysis_limit", 1):
            analyzed = self._run()

        self.assertEqual(analyzed, 1)
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trigger, "auto")
        self.assertEqual(rows[0].symbol, "BTCUSDT")
        self.assertEqual(rows[0].status, "OK")
        self.assertEqual(self.gemini_instance.generate.call_count, 1)

        events = self._daily_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "INFO")
        payload = json.loads(events[0].payload_json)
        self.assertEqual(payload["analyzed"], 1)

    def test_skips_when_last_auto_run_is_recent(self) -> None:
        from app.models import AiEvaluation

        self.db.add(
            AiEvaluation(
                symbol="BTCUSDT",
                trigger="auto",
                status="OK",
                created_at=BASE - timedelta(hours=1),
            )
        )
        self.db.commit()

        analyzed = self._run()

        self.assertEqual(analyzed, 0)
        self.gemini_instance.generate.assert_not_called()
        self.assertEqual(len(self._ai_rows()), 1)
        self.assertEqual(self._daily_events(), [])

    def test_runs_when_last_auto_run_is_older_than_24h(self) -> None:
        from app.models import AiEvaluation

        self.db.add(
            AiEvaluation(
                symbol="BTCUSDT",
                trigger="auto",
                status="OK",
                created_at=BASE - timedelta(hours=25),
            )
        )
        self.db.commit()

        with patch.object(settings, "gemini_auto_analysis_limit", 1):
            analyzed = self._run()

        self.assertEqual(analyzed, 1)
        self.assertEqual(self.gemini_instance.generate.call_count, 1)

    def test_stops_at_first_failure_without_retry(self) -> None:
        from app.services.gemini_client import GeminiUnavailable

        self.gemini_instance.generate.side_effect = GeminiUnavailable(
            "down"
        )
        analyzed = self._run()

        self.assertEqual(analyzed, 0)
        self.assertEqual(self.gemini_instance.generate.call_count, 1)
        rows = self._ai_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trigger, "auto")
        self.assertEqual(rows[0].status, "ERROR")

        events = self._daily_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].level, "WARNING")
        payload = json.loads(events[0].payload_json)
        self.assertEqual(payload["analyzed"], 0)
        self.assertEqual(payload["stop_state"], "ERROR")

    def test_limit_defaults_to_config(self) -> None:
        with patch.object(settings, "gemini_auto_analysis_limit", 2):
            analyzed = self._run()

        self.assertEqual(analyzed, 2)
        self.assertEqual(self.gemini_instance.generate.call_count, 2)


if __name__ == "__main__":
    unittest.main()

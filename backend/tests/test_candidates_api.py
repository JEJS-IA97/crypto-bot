"""Tests rojos — Spec 006: endpoints de contexto y candidatos (RF-7).

`GET /api/bot/context/{symbol}` y `GET /api/bot/candidates`: 200 con datos
por fuente, 404 fuera del universo (D-3) y clamps de límite (caso 9).
"""

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.models import SystemEvent
from app.services.binance_market_data_client import (
    DepthBook,
    MarketDataUnavailable,
    Ticker24,
)

BASE = datetime(2020, 1, 1, 0, 0)

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


def _candles(count: int) -> list:
    from app.domain.signal_engine import Candle

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


class FakeContextMarket:
    def get_depth(self, symbol: str, limit: int = 5) -> DepthBook:
        return DEPTH_OK

    def get_ticker_24h(self, symbol: str) -> Ticker24:
        return TICKER_OK


class FakeCandidateMarket:
    """BTC/ETH con datos completos; LINK con datos insuficientes."""

    GOOD = ("BTCUSDT", "ETHUSDT")
    POOR = ("LINKUSDT",)

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list:
        if symbol in self.GOOD:
            return _candles(30)
        if symbol in self.POOR:
            return _candles(5)
        raise MarketDataUnavailable(f"sin datos de {symbol}")


class CandidatesApiBase(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import market_context_service

        market_context_service.clear_cache()
        self.addCleanup(market_context_service.clear_cache)

        self.tmpdir = tempfile.mkdtemp(prefix="cand-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "cand.db"
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )
        _enable_sqlite_foreign_keys(engine)
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

        token_patcher = patch.object(settings, "api_token", "")
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

        # Sin red: cliente falso + fuentes HTTP externas desactivadas.
        context_patcher = patch(
            "app.services.market_context_service.BinanceMarketDataClient",
            return_value=FakeContextMarket(),
        )
        context_patcher.start()
        self.addCleanup(context_patcher.stop)
        candidates_patcher = patch(
            "app.services.candidate_service.BinanceMarketDataClient",
            return_value=FakeCandidateMarket(),
        )
        candidates_patcher.start()
        self.addCleanup(candidates_patcher.stop)
        for field in ("fear_greed_url", "news_rss_feeds"):
            field_patcher = patch.object(settings, field, "")
            field_patcher.start()
            self.addCleanup(field_patcher.stop)

        self.client = TestClient(app)


class ContextEndpointTests(CandidatesApiBase):
    def test_context_200_with_serialized_blocks(self) -> None:
        response = self.client.get("/api/bot/context/BTCUSDT")
        self.assertEqual(response.status_code, 200)
        body = response.json()

        book = body["order_book"]
        self.assertEqual(book["spread_bps"], "49.8753")
        # Imbalance cuantizado a 4 decimales (misma regla que RF-2).
        self.assertEqual(book["imbalance"], "0.0000")
        self.assertEqual(book["bids"], [["100", "5"]])
        self.assertEqual(book["asks"], [["100.5", "5"]])

        self.assertEqual(body["ticker"]["last_price"], "100.4")
        self.assertEqual(body["ticker"]["change_pct_24h"], "1.25")
        self.assertIsNone(body["fear_greed"])
        self.assertEqual(body["news"], [])

        sources = body["sources"]
        self.assertEqual(sources["binance_depth"]["state"], "HEALTHY")
        self.assertEqual(sources["binance_ticker"]["state"], "HEALTHY")
        self.assertEqual(sources["fear_greed"]["state"], "DISABLED")
        self.assertEqual(sources["news_rss"]["state"], "DISABLED")
        self.assertIsNotNone(body["fetched_at"])

    def test_context_404_outside_universe(self) -> None:
        response = self.client.get("/api/bot/context/XMRUSDT")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "symbol_not_in_universe")


class CandidatesEndpointTests(CandidatesApiBase):
    def test_default_universe_ranks_good_and_excludes_rest(self) -> None:
        response = self.client.get("/api/bot/candidates")
        self.assertEqual(response.status_code, 200)
        body = response.json()

        candidates = body["candidates"]
        self.assertEqual(
            [c["symbol"] for c in candidates],
            ["BTCUSDT", "ETHUSDT"],
        )
        self.assertEqual(candidates[0]["rank"], 1)
        self.assertEqual(candidates[1]["rank"], 2)
        # Score numérico (no texto) con factores explicados.
        self.assertIsInstance(candidates[0]["score"], (int, float))
        self.assertEqual(len(candidates[0]["factors"]), 4)
        factor = candidates[0]["factors"][0]
        self.assertEqual(
            set(factor),
            {"name", "weight", "normalized", "contribution"},
        )
        self.assertIsInstance(factor["weight"], str)

        excluded = {row["symbol"]: row["filters"] for row in body["excluded"]}
        self.assertEqual(excluded["LINKUSDT"], ["missing_data"])
        self.assertIn("XRPUSDT", excluded)
        self.assertEqual(excluded["XRPUSDT"], ["data_unavailable"])
        self.assertNotIn("BTCUSDT", excluded)
        self.assertIsNotNone(body["evaluated_at"])

    def test_symbols_filter_and_limit_clamps(self) -> None:
        only = self.client.get(
            "/api/bot/candidates", params={"symbols": "BTCUSDT"}
        ).json()
        self.assertEqual(
            [c["symbol"] for c in only["candidates"]], ["BTCUSDT"]
        )
        self.assertEqual(only["candidates"][0]["rank"], 1)

        # Límite bajo → clamp a 1.
        low = self.client.get(
            "/api/bot/candidates", params={"limit": 0}
        ).json()
        self.assertEqual(len(low["candidates"]), 1)

        # Límite alto → aceptado sin error (clamp a 50).
        high = self.client.get(
            "/api/bot/candidates", params={"limit": 5000}
        )
        self.assertEqual(high.status_code, 200)

    def test_symbols_outside_universe_404(self) -> None:
        response = self.client.get(
            "/api/bot/candidates", params={"symbols": "BTCUSDT,XMRUSDT"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "symbol_not_in_universe")


class EventTests(CandidatesApiBase):
    """M8: eventos 005 `context.fetched` y `config.ignored`."""

    def test_context_fetched_event_recorded(self) -> None:
        response = self.client.get("/api/bot/context/BTCUSDT")
        self.assertEqual(response.status_code, 200)

        with self.Session() as db:
            rows = db.scalars(
                select(SystemEvent).where(
                    SystemEvent.event == "context.fetched"
                )
            ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].asset, "BTCUSDT")
        self.assertIn("binance_depth", rows[0].payload_json)

    def test_config_ignored_when_weights_invalid(self) -> None:
        raw = "momentum:0.9,volume:0.9,trend:0.05,range:0.05"
        with patch.object(settings, "candidate_weights", raw):
            response = self.client.get(
                "/api/bot/candidates", params={"symbols": "BTCUSDT"}
            )
        self.assertEqual(response.status_code, 200)

        with self.Session() as db:
            rows = db.scalars(
                select(SystemEvent).where(
                    SystemEvent.event == "config.ignored"
                )
            ).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].level, "WARNING")
        self.assertIn(raw, rows[0].payload_json)


if __name__ == "__main__":
    unittest.main()

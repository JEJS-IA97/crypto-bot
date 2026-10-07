"""Tests rojos — Spec 006: market_context_service (RF-1…RF-4, RF-8).

Order book, ticker, Fear&Greed y noticias RSS con caché TTL, degradación
honesta (`stale`/`null`/DISABLED) y salud de fuentes en `source_health`.
"""

import threading
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.services.binance_market_data_client import (
    DepthBook,
    MarketDataUnavailable,
    Ticker24,
)
from app.services.observability_service import KNOWN_SOURCES, sources_state

DEPTH_OK = DepthBook(
    last_update_id=1,
    bids=(
        (Decimal("100"), Decimal("5")),
        (Decimal("99.9"), Decimal("5")),
        (Decimal("99.8"), Decimal("5")),
        (Decimal("99.7"), Decimal("5")),
        (Decimal("99.6"), Decimal("5")),
    ),
    asks=(
        (Decimal("100.5"), Decimal("1")),
        (Decimal("100.6"), Decimal("1")),
        (Decimal("100.7"), Decimal("1")),
        (Decimal("100.8"), Decimal("1")),
        (Decimal("100.9"), Decimal("1")),
    ),
)

TICKER_OK = Ticker24(
    last_price=Decimal("100.4"),
    price_change_pct=Decimal("1.25"),
    quote_volume_24h=Decimal("123456.78"),
)

FNG_OK = {
    "data": [
        {"value": "45", "value_classification": "Fear"},
    ]
}

RSS_OK = """
<rss version="2.0">
  <channel>
    <title>Feed</title>
    <item>
      <title>Bitcoin sube</title>
      <link>https://news.example/1</link>
      <pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Repetido</title>
      <link>https://news.example/1</link>
    </item>
    <item>
      <title>Sin enlace</title>
    </item>
  </channel>
</rss>
"""


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value


class FakeDepthTickerMarket:
    """Cliente falso: depth/ticker con fallo inyectable."""

    def __init__(
        self,
        *,
        depth: DepthBook | None = None,
        ticker: Ticker24 | None = None,
        depth_error: str = "",
        ticker_error: str = "",
    ) -> None:
        self.depth = depth
        self.ticker = ticker
        self.depth_error = depth_error
        self.ticker_error = ticker_error
        self.depth_calls = 0
        self.ticker_calls = 0
        self._lock = threading.Lock()

    def get_depth(self, symbol: str, limit: int = 5) -> DepthBook:
        with self._lock:
            self.depth_calls += 1
        if self.depth_error:
            raise MarketDataUnavailable(self.depth_error)
        assert self.depth is not None
        return self.depth

    def get_ticker_24h(self, symbol: str) -> Ticker24:
        with self._lock:
            self.ticker_calls += 1
        if self.ticker_error:
            raise MarketDataUnavailable(self.ticker_error)
        assert self.ticker is not None
        return self.ticker


class ContextTestBase(unittest.TestCase):
    def setUp(self) -> None:
        from app.services import market_context_service as service

        self.service = service
        service.clear_cache()
        self.addCleanup(service.clear_cache)
        self.db = _session_factory()()
        self.clock = FakeClock()
        self.addCleanup(self.db.close)

    def _context(
        self,
        market: FakeDepthTickerMarket,
        *,
        fng_url: str = "https://api.alternative.me/fng/",
        news_feeds: str = "",
        http_get=None,
    ):
        with (
            patch.object(settings, "fear_greed_url", fng_url),
            patch.object(settings, "news_rss_feeds", news_feeds),
            patch.object(
                self.service,
                "_http_get",
                side_effect=http_get
                or _raise("no debe llamarse a HTTP"),
            ),
        ):
            return self.service.get_context(
                "BTCUSDT",
                db=self.db,
                market_data=market,
                clock=self.clock,
            )


def _raise(message: str):
    def _inner(*_args, **_kwargs):
        raise RuntimeError(message)

    return _inner


class OrderBookTests(ContextTestBase):
    def test_spread_and_imbalance(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK)
        )
        book = snapshot.order_book
        self.assertIsNotNone(book)
        # (100.5-100)/100.25*10000 = 49.8753 bps.
        self.assertEqual(book.spread_bps, Decimal("49.8753"))
        # (25-5)/(25+5) = 0.6667 sobre los 5 mejores niveles.
        self.assertEqual(book.imbalance, Decimal("0.6667"))
        self.assertEqual(len(book.bids), 5)
        self.assertEqual(len(book.asks), 5)
        self.assertEqual(
            snapshot.sources["binance_depth"].state, "HEALTHY"
        )

    def test_empty_depth_is_unavailable_not_error_500(self) -> None:
        empty = DepthBook(last_update_id=2, bids=(), asks=())
        snapshot = self._context(
            FakeDepthTickerMarket(depth=empty, ticker=TICKER_OK)
        )
        self.assertIsNone(snapshot.order_book)
        self.assertEqual(
            snapshot.sources["binance_depth"].state, "ERROR"
        )

    def test_cache_avoids_refetch_within_ttl(self) -> None:
        market = FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK)
        self._context(market)
        self.clock.value += 5  # dentro del TTL de 30 s
        self._context(market)
        self.assertEqual(market.depth_calls, 1)
        self.assertEqual(market.ticker_calls, 1)

    def test_failed_refresh_serves_stale_cache(self) -> None:
        market = FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK)
        self._context(market)

        self.clock.value += 31  # TTL vencido
        market.depth_error = "timeout 504"
        market.ticker_error = "timeout 504"
        snapshot = self._context(market)

        self.assertIsNotNone(snapshot.order_book)
        source = snapshot.sources["binance_depth"]
        self.assertEqual(source.state, "STALE")
        self.assertTrue(source.stale)
        self.assertIsNotNone(snapshot.ticker)


class FearGreedTests(ContextTestBase):
    def test_fng_parsed(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            http_get=lambda *_a, **_k: FNG_OK,
        )
        self.assertEqual(snapshot.fear_greed.value, 45)
        self.assertEqual(snapshot.fear_greed.label, "Fear")
        self.assertEqual(
            snapshot.sources["fear_greed"].state, "HEALTHY"
        )

    def test_unexpected_payload_is_unavailable(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            http_get=lambda *_a, **_k: {"foo": 1},
        )
        self.assertIsNone(snapshot.fear_greed)
        self.assertEqual(
            snapshot.sources["fear_greed"].state, "ERROR"
        )

    def test_empty_url_disables_source(self) -> None:
        market = FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK)
        with (
            patch.object(settings, "fear_greed_url", ""),
            patch.object(settings, "news_rss_feeds", ""),
            patch.object(
                self.service, "_http_get", side_effect=_raise("HTTP")
            ) as http_mock,
        ):
            snapshot = self.service.get_context(
                "BTCUSDT",
                db=self.db,
                market_data=market,
                clock=self.clock,
            )
        self.assertIsNone(snapshot.fear_greed)
        self.assertEqual(
            snapshot.sources["fear_greed"].state, "DISABLED"
        )
        http_mock.assert_not_called()


class NewsFeedTests(ContextTestBase):
    def test_rss_parsed_and_deduplicated(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            news_feeds="https://feed.example/rss",
            http_get=lambda *_a, **_k: RSS_OK,
        )
        self.assertEqual(len(snapshot.news), 1)
        item = snapshot.news[0]
        self.assertEqual(item.title, "Bitcoin sube")
        self.assertEqual(item.url, "https://news.example/1")
        self.assertEqual(
            item.published_at, datetime(2026, 10, 5, 10, 0, 0)
        )
        self.assertEqual(snapshot.sources["news_rss"].state, "HEALTHY")

    def test_invalid_date_omits_item(self) -> None:
        rss = """
        <rss version="2.0"><channel>
          <item>
            <title>Mala fecha</title>
            <link>https://news.example/2</link>
            <pubDate>not-a-date</pubDate>
          </item>
          <item>
            <title>Sin fecha</title>
            <link>https://news.example/3</link>
          </item>
        </channel></rss>
        """
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            news_feeds="https://feed.example/rss",
            http_get=lambda *_a, **_k: rss,
        )
        # Sin pubDate se conserva (published_at None); fecha inválida omite.
        self.assertEqual(
            [item.url for item in snapshot.news],
            ["https://news.example/3"],
        )
        self.assertIsNone(snapshot.news[0].published_at)

    def test_no_feeds_disables_source(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            news_feeds="",
        )
        self.assertEqual(snapshot.news, ())
        self.assertEqual(
            snapshot.sources["news_rss"].state, "DISABLED"
        )


class ContextSnapshotTests(ContextTestBase):
    def test_all_sources_tracked_with_timestamps(self) -> None:
        snapshot = self._context(
            FakeDepthTickerMarket(depth=DEPTH_OK, ticker=TICKER_OK),
            fng_url="",
            news_feeds="",
        )
        self.assertEqual(snapshot.symbol, "BTCUSDT")
        self.assertIsInstance(snapshot.fetched_at, datetime)
        self.assertIsNotNone(snapshot.ticker)
        self.assertEqual(
            snapshot.ticker.last_price, Decimal("100.4")
        )
        for name in (
            "binance_depth",
            "binance_ticker",
            "fear_greed",
            "news_rss",
        ):
            self.assertIn(name, snapshot.sources)
        for name in ("binance_depth", "binance_ticker"):
            self.assertIsNotNone(
                snapshot.sources[name].fetched_at, name
            )

    def test_total_failure_returns_null_blocks_and_no_raise(self) -> None:
        market = FakeDepthTickerMarket(
            depth_error="red caida",
            ticker_error="red caida",
        )
        snapshot = self._context(
            market,
            fng_url="https://api.alternative.me/fng/",
            news_feeds="https://feed.example/rss",
            http_get=_raise("red caida"),
        )
        self.assertIsNone(snapshot.order_book)
        self.assertIsNone(snapshot.ticker)
        self.assertIsNone(snapshot.fear_greed)
        self.assertEqual(snapshot.news, ())
        self.assertEqual(
            snapshot.sources["binance_depth"].state, "ERROR"
        )
        self.assertEqual(
            snapshot.sources["fear_greed"].state, "ERROR"
        )
        self.assertEqual(snapshot.sources["news_rss"].state, "ERROR")


class SourceHealthIntegrationTests(ContextTestBase):
    def test_failures_reach_source_health_table(self) -> None:
        market = FakeDepthTickerMarket(
            depth_error="boom", ticker_error="boom"
        )
        self._context(market, fng_url="", news_feeds="")
        states = {row["name"]: row for row in sources_state(self.db)}
        self.assertEqual(states["binance_depth"]["state"], "ERROR")
        self.assertEqual(states["binance_ticker"]["state"], "ERROR")
        for name in ("binance_depth", "fear_greed", "news_rss"):
            self.assertIn(name, KNOWN_SOURCES)


if __name__ == "__main__":
    unittest.main()

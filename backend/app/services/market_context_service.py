"""Honest market context (spec 006, RF-1…RF-4 and RF-8).

Advisory-only: the service never raises to the caller. Each source has an
in-memory TTL cache; when a refresh fails the cached value is served marked
``stale`` (source STALE), and with no cache the block comes back ``None``
(source ERROR). Disabled sources (empty URL/feeds) are never fetched.
"""

from __future__ import annotations

import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from time import monotonic
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import utc_now
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
)
from app.services.observability_service import mark_source

_HTTP_TIMEOUT_SECONDS = 5.0
_SPREAD_QUANTUM = Decimal("0.0001")
_BPS = Decimal("10000")
_NEWS_LIMIT = 10

DEPTH_SOURCE = "binance_depth"
TICKER_SOURCE = "binance_ticker"
FNG_SOURCE = "fear_greed"
NEWS_SOURCE = "news_rss"


@dataclass(frozen=True)
class ContextSource:
    state: str
    fetched_at: datetime | None
    stale: bool = False


@dataclass(frozen=True)
class OrderBookData:
    spread_bps: Decimal
    imbalance: Decimal
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]


@dataclass(frozen=True)
class TickerData:
    last_price: Decimal
    change_pct_24h: Decimal
    quote_volume_24h: Decimal


@dataclass(frozen=True)
class FearGreedData:
    value: int
    label: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published_at: datetime | None


@dataclass(frozen=True)
class ContextSnapshot:
    symbol: str
    fetched_at: datetime
    order_book: OrderBookData | None
    ticker: TickerData | None
    fear_greed: FearGreedData | None
    news: tuple[NewsItem, ...]
    sources: dict[str, ContextSource]


@dataclass
class _Entry:
    timestamp: float
    fetched_at: datetime
    value: Any


@dataclass
class _Outcome:
    value: Any
    fetched_at: datetime | None
    stale: bool
    error: str
    fetched: bool


_CACHE: dict[str, _Entry] = {}
_CACHE_LOCK = threading.Lock()


def clear_cache() -> None:
    """Drop every cached source (tests and manual refresh)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def _http_get(url: str) -> Any:
    """Plain GET: parsed JSON when possible, otherwise raw text."""
    response = httpx.request("GET", url, timeout=_HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return response.text


def _fetch_cached(
    key: str,
    ttl_seconds: float,
    tick: float,
    fetch: Callable[[], Any],
) -> _Outcome:
    """Serve fresh cache, otherwise fetch and degrade honestly (D-4)."""
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
    if entry is not None and tick - entry.timestamp <= ttl_seconds:
        return _Outcome(
            value=entry.value,
            fetched_at=entry.fetched_at,
            stale=False,
            error="",
            fetched=False,
        )
    try:
        value = fetch()
    except Exception as exc:  # any failure degrades, never raises (D-5)
        message = str(exc) or type(exc).__name__
        if entry is not None:
            return _Outcome(
                value=entry.value,
                fetched_at=entry.fetched_at,
                stale=True,
                error=message,
                fetched=True,
            )
        return _Outcome(
            value=None,
            fetched_at=None,
            stale=False,
            error=message,
            fetched=True,
        )
    moment = utc_now()
    with _CACHE_LOCK:
        _CACHE[key] = _Entry(
            timestamp=tick, fetched_at=moment, value=value
        )
    return _Outcome(
        value=value,
        fetched_at=moment,
        stale=False,
        error="",
        fetched=True,
    )


def _mark(db: Session, name: str, *, ok: bool, error: str = "") -> None:
    """Record source health (RF-8); observability never breaks context."""
    try:
        mark_source(db, name, ok=ok, error=error)
    except Exception:
        pass


def _resolve(
    *,
    key: str,
    ttl_seconds: float,
    tick: float,
    fetch: Callable[[], Any],
    source_name: str,
    db: Session,
    sources: dict[str, ContextSource],
) -> Any:
    outcome = _fetch_cached(key, ttl_seconds, tick, fetch)
    if outcome.fetched:
        _mark(db, source_name, ok=not outcome.error, error=outcome.error)
    if outcome.error and outcome.stale:
        state = "STALE"
    elif outcome.error:
        state = "ERROR"
    else:
        state = "HEALTHY"
    sources[source_name] = ContextSource(
        state=state,
        fetched_at=outcome.fetched_at,
        stale=outcome.stale,
    )
    return outcome.value


def _fetch_order_book(client: Any, symbol: str) -> OrderBookData:
    book = client.get_depth(symbol, limit=5)
    if not book.bids or not book.asks:
        raise MarketDataUnavailable(f"Empty depth for {symbol}")
    best_bid = book.bids[0][0]
    best_ask = book.asks[0][0]
    mid = (best_bid + best_ask) / Decimal(2)
    if mid <= 0:
        raise MarketDataUnavailable(f"Non-positive mid price for {symbol}")
    spread = ((best_ask - best_bid) / mid * _BPS).quantize(_SPREAD_QUANTUM)
    bid_depth = sum(quantity for _, quantity in book.bids)
    ask_depth = sum(quantity for _, quantity in book.asks)
    total = bid_depth + ask_depth
    if total <= 0:
        raise MarketDataUnavailable(f"Empty depth quantities for {symbol}")
    imbalance = ((bid_depth - ask_depth) / total).quantize(_SPREAD_QUANTUM)
    return OrderBookData(
        spread_bps=spread,
        imbalance=imbalance,
        bids=tuple(book.bids),
        asks=tuple(book.asks),
    )


def _fetch_ticker(client: Any, symbol: str) -> TickerData:
    raw = client.get_ticker_24h(symbol)
    return TickerData(
        last_price=raw.last_price,
        change_pct_24h=raw.price_change_pct,
        quote_volume_24h=raw.quote_volume_24h,
    )


def _parse_fear_greed(payload: Any) -> FearGreedData:
    if not isinstance(payload, dict):
        raise MarketDataUnavailable("Unexpected Fear&Greed payload")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise MarketDataUnavailable("Missing data in Fear&Greed payload")
    entry = data[0]
    if not isinstance(entry, dict):
        raise MarketDataUnavailable("Malformed Fear&Greed entry")
    raw_value = entry.get("value")
    label = entry.get("value_classification")
    if raw_value is None or label is None:
        raise MarketDataUnavailable("Missing Fear&Greed fields")
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise MarketDataUnavailable(
            f"Unparseable Fear&Greed value: {exc}"
        ) from exc
    if value < 0 or value > 100:
        raise MarketDataUnavailable("Fear&Greed value out of range")
    return FearGreedData(value=value, label=str(label))


def _fetch_fear_greed() -> FearGreedData:
    return _parse_fear_greed(_http_get(settings.fear_greed_url))


def _parse_rss(xml_text: str) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not link:
            continue
        published: datetime | None = None
        raw_date = node.findtext("pubDate")
        if raw_date is not None and raw_date.strip():
            try:
                parsed = parsedate_to_datetime(raw_date.strip())
            except (TypeError, ValueError):
                continue
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            published = parsed
        items.append(
            NewsItem(title=title, url=link, published_at=published)
        )
    return items


def _news_feeds() -> tuple[str, ...]:
    return tuple(
        url.strip()
        for url in settings.news_rss_feeds.split(",")
        if url.strip()
    )


def _fetch_news() -> tuple[NewsItem, ...]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    for feed in _news_feeds():
        payload = _http_get(feed)
        if not isinstance(payload, str):
            raise MarketDataUnavailable(
                f"Unexpected RSS payload for {feed}"
            )
        for item in _parse_rss(payload):
            if item.url in seen:
                continue
            seen.add(item.url)
            items.append(item)
    return tuple(items[:_NEWS_LIMIT])


def _disabled() -> ContextSource:
    return ContextSource(state="DISABLED", fetched_at=None, stale=False)


def get_context(
    symbol: str,
    *,
    db: Session,
    now: datetime | None = None,
    market_data: Any | None = None,
    clock: Callable[[], float] = monotonic,
) -> ContextSnapshot:
    """Compose the context of one symbol, degraded honestly (RF-1)."""
    client = (
        market_data if market_data is not None else BinanceMarketDataClient()
    )
    moment = now if now is not None else utc_now()
    tick = clock()
    sources: dict[str, ContextSource] = {}

    order_book = _resolve(
        key=f"depth:{symbol}",
        ttl_seconds=float(settings.depth_cache_seconds),
        tick=tick,
        fetch=lambda: _fetch_order_book(client, symbol),
        source_name=DEPTH_SOURCE,
        db=db,
        sources=sources,
    )
    ticker = _resolve(
        key=f"ticker:{symbol}",
        ttl_seconds=float(settings.depth_cache_seconds),
        tick=tick,
        fetch=lambda: _fetch_ticker(client, symbol),
        source_name=TICKER_SOURCE,
        db=db,
        sources=sources,
    )

    fear_greed: FearGreedData | None = None
    if settings.fear_greed_url.strip():
        fear_greed = _resolve(
            key="fear_greed",
            ttl_seconds=float(settings.fear_greed_cache_seconds),
            tick=tick,
            fetch=_fetch_fear_greed,
            source_name=FNG_SOURCE,
            db=db,
            sources=sources,
        )
    else:
        sources[FNG_SOURCE] = _disabled()

    news: tuple[NewsItem, ...] = ()
    if _news_feeds():
        value = _resolve(
            key="news",
            ttl_seconds=float(settings.news_cache_seconds),
            tick=tick,
            fetch=_fetch_news,
            source_name=NEWS_SOURCE,
            db=db,
            sources=sources,
        )
        news = value if value is not None else ()
    else:
        sources[NEWS_SOURCE] = _disabled()

    return ContextSnapshot(
        symbol=symbol,
        fetched_at=moment,
        order_book=order_book,
        ticker=ticker,
        fear_greed=fear_greed,
        news=news,
        sources=sources,
    )

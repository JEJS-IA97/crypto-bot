"""Public Binance market data (spec 001, RF-6 and RNF-6).

No credentials are ever sent: klines and exchangeInfo are public endpoints.
Fail-closed by design: any transport, HTTP, payload or freshness failure
raises MarketDataUnavailable so the bot never trades on bad data.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from time import monotonic
from typing import Any

import httpx

from app.domain.signal_engine import Candle

DEFAULT_BASE_URL = "https://api.binance.com"


class MarketDataUnavailable(RuntimeError):
    """Raised instead of ever returning missing or stale market data."""


@dataclass(frozen=True)
class SymbolRules:
    symbol: str
    status: str
    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal

    @property
    def tradable(self) -> bool:
        return self.status == "TRADING"


class BinanceMarketDataClient:
    """Synchronous client with a short freshness-bounded cache."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        klines_freshness_seconds: float = 30.0,
        rules_freshness_seconds: float = 300.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.klines_freshness_seconds = klines_freshness_seconds
        self.rules_freshness_seconds = rules_freshness_seconds
        self._clock = clock
        self._klines_cache: dict[
            tuple[str, str], tuple[float, list[Candle]]
        ] = {}
        self._rules_cache: dict[str, tuple[float, SymbolRules]] = {}

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(
                method="GET",
                url=url,
                params=params,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise MarketDataUnavailable(
                f"Binance request failed for {path}: {exc}"
            ) from exc
        if response.is_error:
            raise MarketDataUnavailable(
                f"Binance responded {response.status_code} for {path}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MarketDataUnavailable(
                f"Binance returned invalid JSON for {path}"
            ) from exc

    def get_klines(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = 200,
    ) -> list[Candle]:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")
        if not interval or not interval.strip():
            raise ValueError("interval must not be empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        normalized = symbol.strip().upper()
        key = (normalized, interval)
        now = self._clock()
        cached = self._klines_cache.get(key)
        if cached is not None and now - cached[0] <= self.klines_freshness_seconds:
            return list(cached[1])

        payload = self._get(
            "/api/v3/klines",
            {
                "symbol": normalized,
                "interval": interval,
                "limit": limit,
            },
        )
        candles = self._parse_klines(payload, normalized)
        if not candles:
            raise MarketDataUnavailable(f"Empty klines for {normalized}")
        self._klines_cache[key] = (now, candles)
        return list(candles)

    @staticmethod
    def _parse_klines(payload: Any, symbol: str) -> list[Candle]:
        if not isinstance(payload, list):
            raise MarketDataUnavailable(
                f"Unexpected klines payload for {symbol}"
            )
        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 6:
                raise MarketDataUnavailable(
                    f"Malformed kline row for {symbol}"
                )
            try:
                open_time = datetime.fromtimestamp(
                    int(row[0]) / 1000, tz=timezone.utc
                ).replace(tzinfo=None)
                candles.append(
                    Candle(
                        open_time=open_time,
                        open=Decimal(str(row[1])),
                        high=Decimal(str(row[2])),
                        low=Decimal(str(row[3])),
                        close=Decimal(str(row[4])),
                        volume=Decimal(str(row[5])),
                    )
                )
            except (ValueError, TypeError, ArithmeticError) as exc:
                raise MarketDataUnavailable(
                    f"Unparseable kline row for {symbol}: {exc}"
                ) from exc
        return candles

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        if not symbol or not symbol.strip():
            raise ValueError("symbol must not be empty")

        normalized = symbol.strip().upper()
        now = self._clock()
        cached = self._rules_cache.get(normalized)
        if cached is not None and now - cached[0] <= self.rules_freshness_seconds:
            return cached[1]

        payload = self._get("/api/v3/exchangeInfo", {"symbol": normalized})
        rules = self._parse_rules(payload, normalized)
        self._rules_cache[normalized] = (now, rules)
        return rules

    @staticmethod
    def _parse_rules(payload: Any, symbol: str) -> SymbolRules:
        if not isinstance(payload, dict):
            raise MarketDataUnavailable(
                f"Unexpected exchangeInfo payload for {symbol}"
            )
        entries = payload.get("symbols")
        if not isinstance(entries, list):
            raise MarketDataUnavailable(
                f"Missing symbols in exchangeInfo for {symbol}"
            )
        match = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict) and entry.get("symbol") == symbol
            ),
            None,
        )
        if match is None:
            raise MarketDataUnavailable(f"{symbol} not in exchangeInfo")

        filters = {
            entry.get("filterType"): entry
            for entry in match.get("filters", [])
            if isinstance(entry, dict)
        }
        price_filter = filters.get("PRICE_FILTER") or {}
        lot_filter = filters.get("LOT_SIZE") or {}
        notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}

        tick_size = price_filter.get("tickSize")
        step_size = lot_filter.get("stepSize")
        min_notional = notional_filter.get("minNotional")
        if tick_size is None or step_size is None or min_notional is None:
            raise MarketDataUnavailable(
                f"Incomplete trading rules for {symbol}"
            )
        try:
            return SymbolRules(
                symbol=symbol,
                status=str(match.get("status", "")),
                tick_size=Decimal(str(tick_size)),
                step_size=Decimal(str(step_size)),
                min_notional=Decimal(str(min_notional)),
            )
        except ArithmeticError as exc:
            raise MarketDataUnavailable(
                f"Unparseable trading rules for {symbol}: {exc}"
            ) from exc

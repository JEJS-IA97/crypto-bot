import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import httpx

from app.config import settings
from app.domain.signal_engine import Candle
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
    SymbolRules,
)

KLINES_PAYLOAD = [
    [1767225600000, "100.0", "101.5", "99.5", "100.5", "12.5",
     1767225899999, "1250", 100, "6.0", "600", "0"],
    [1767225900000, "100.5", "102.0", "100.0", "101.0", "9.5",
     1767226199999, "959", 90, "4.0", "400", "0"],
]

EXCHANGE_INFO_PAYLOAD = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"},
            ],
        }
    ]
}

DEPTH_PAYLOAD = {
    "lastUpdateId": 167,
    "bids": [["100.0", "5.0"], ["99.9", "4.0"]],
    "asks": [["100.5", "3.0"], ["100.6", "2.0"]],
}

TICKER_PAYLOAD = {
    "lastPrice": "100.4",
    "priceChangePercent": "1.25",
    "quoteVolume": "123456.78",
}


class BinanceMarketDataClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1000.0
        self.client = BinanceMarketDataClient(clock=lambda: self.now)

    def test_default_base_url_is_api_binance_com(self) -> None:
        self.assertEqual(self.client.base_url, "https://api.binance.com")

    def test_default_base_url_comes_from_settings(self) -> None:
        # Host configurable (p. ej. data-api.binance.vision en la nube).
        with patch.object(
            settings,
            "binance_market_data_base_url",
            "https://data-api.binance.vision",
        ):
            client = BinanceMarketDataClient(clock=lambda: self.now)
        self.assertEqual(
            client.base_url, "https://data-api.binance.vision"
        )

    def test_explicit_base_url_beats_settings(self) -> None:
        with patch.object(
            settings,
            "binance_market_data_base_url",
            "https://data-api.binance.vision",
        ):
            client = BinanceMarketDataClient(
                base_url="https://api.binance.com",
                clock=lambda: self.now,
            )
        self.assertEqual(client.base_url, "https://api.binance.com")

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_klines_ok(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(200, json=KLINES_PAYLOAD)

        candles = self.client.get_klines("btcusdt", interval="15m", limit=200)

        self.assertEqual(len(candles), 2)
        self.assertIsInstance(candles[0], Candle)
        self.assertIsInstance(candles[0].close, Decimal)
        self.assertIsInstance(candles[0].open_time, datetime)
        self.assertEqual(candles[0].open_time.tzinfo, None)
        self.assertEqual(candles[0].close, Decimal("100.5"))
        self.assertEqual(candles[0].volume, Decimal("12.5"))
        self.assertEqual(candles[1].open, Decimal("100.5"))

        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["url"],
            "https://api.binance.com/api/v3/klines",
        )
        self.assertEqual(kwargs["params"]["symbol"], "BTCUSDT")
        self.assertEqual(kwargs["params"]["interval"], "15m")
        self.assertEqual(kwargs["params"]["limit"], 200)
        headers = kwargs.get("headers") or {}
        self.assertNotIn("X-MBX-APIKEY", headers)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_cache_serves_without_second_http(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(200, json=KLINES_PAYLOAD)
        self.client.get_klines("BTCUSDT")
        self.client.get_klines("BTCUSDT")
        self.assertEqual(request_mock.call_count, 1)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_fail_closed_on_error(self, request_mock) -> None:
        # Fallo de red
        request_mock.side_effect = httpx.ConnectError("boom")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_klines("BTCUSDT")

        # Respuesta 500
        request_mock.side_effect = None
        request_mock.return_value = httpx.Response(500, text="oops")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_klines("ETHUSDT")

        # JSON inválido
        request_mock.return_value = httpx.Response(200, text="not-json")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_klines("SOLUSDT")

        # Payload vacío
        request_mock.return_value = httpx.Response(200, json=[])
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_klines("BNBUSDT")

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_stale_cache_is_never_served(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(200, json=KLINES_PAYLOAD)
        self.client.get_klines("BTCUSDT")
        request_mock.side_effect = httpx.ConnectError("down")

        # Dentro de la frescura: sirve caché sin volver a HTTP.
        self.now += 5
        cached = self.client.get_klines("BTCUSDT")
        self.assertEqual(len(cached), 2)

        # Caducada + Binance caído → fail-closed, nunca datos viejos.
        self.now += 10_000
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_klines("BTCUSDT")

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_exchange_info_ok(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(
            200, json=EXCHANGE_INFO_PAYLOAD
        )

        rules = self.client.get_exchange_info("BTCUSDT")

        self.assertIsInstance(rules, SymbolRules)
        self.assertEqual(rules.symbol, "BTCUSDT")
        self.assertTrue(rules.tradable)
        self.assertEqual(rules.tick_size, Decimal("0.01"))
        self.assertEqual(rules.step_size, Decimal("0.00001"))
        self.assertEqual(rules.min_notional, Decimal("5"))
        self.assertIsInstance(rules.min_notional, Decimal)

        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["url"],
            "https://api.binance.com/api/v3/exchangeInfo",
        )
        headers = kwargs.get("headers") or {}
        self.assertNotIn("X-MBX-APIKEY", headers)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_exchange_info_notional_filter_and_missing_rules(
        self, request_mock
    ) -> None:
        payload = {
            "symbols": [
                {
                    "symbol": "ETHUSDT",
                    "status": "BREAK",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                        {"filterType": "NOTIONAL", "minNotional": "1"},
                    ],
                }
            ]
        }
        request_mock.return_value = httpx.Response(200, json=payload)
        rules = self.client.get_exchange_info("ETHUSDT")
        self.assertEqual(rules.min_notional, Decimal("1"))
        self.assertFalse(rules.tradable)

        request_mock.return_value = httpx.Response(
            200,
            json={"symbols": [{"symbol": "SOLUSDT", "filters": []}]},
        )
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_exchange_info("SOLUSDT")

    def test_invalid_arguments_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.client.get_klines("")
        with self.assertRaises(ValueError):
            self.client.get_klines("BTCUSDT", interval="")
        with self.assertRaises(ValueError):
            self.client.get_klines("BTCUSDT", limit=0)
        with self.assertRaises(ValueError):
            self.client.get_exchange_info("")


class DepthAndTickerTests(unittest.TestCase):
    """Spec 006 M2/RF-2: get_depth y get_ticker_24h públicos (sin claves)."""

    def setUp(self) -> None:
        self.now = 1000.0
        self.client = BinanceMarketDataClient(clock=lambda: self.now)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_get_depth_ok(self, request_mock) -> None:
        from app.services.binance_market_data_client import DepthBook

        request_mock.return_value = httpx.Response(200, json=DEPTH_PAYLOAD)

        book = self.client.get_depth("btcusdt", limit=5)

        self.assertIsInstance(book, DepthBook)
        self.assertEqual(book.last_update_id, 167)
        self.assertEqual(
            book.bids[0], (Decimal("100.0"), Decimal("5.0"))
        )
        self.assertEqual(
            book.asks[0], (Decimal("100.5"), Decimal("3.0"))
        )
        self.assertIsInstance(book.bids[0][0], Decimal)

        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["url"], "https://api.binance.com/api/v3/depth"
        )
        self.assertEqual(kwargs["params"]["symbol"], "BTCUSDT")
        self.assertEqual(kwargs["params"]["limit"], 5)
        headers = kwargs.get("headers") or {}
        self.assertNotIn("X-MBX-APIKEY", headers)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_get_depth_fail_closed(self, request_mock) -> None:
        # Payload no parseable
        request_mock.return_value = httpx.Response(200, text="nope")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_depth("BTCUSDT")

        # Estructura ausente
        request_mock.return_value = httpx.Response(200, json={"bids": "?"})
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_depth("BTCUSDT")

        # Fila corrupta
        request_mock.return_value = httpx.Response(
            200,
            json={
                "lastUpdateId": 1,
                "bids": [["oops", "1"]],
                "asks": [],
            },
        )
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_depth("BTCUSDT")

        # Red caída
        request_mock.side_effect = httpx.ConnectError("boom")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_depth("BTCUSDT")

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_get_ticker_24h_ok(self, request_mock) -> None:
        from app.services.binance_market_data_client import Ticker24

        request_mock.return_value = httpx.Response(200, json=TICKER_PAYLOAD)

        ticker = self.client.get_ticker_24h("btcusdt")

        self.assertIsInstance(ticker, Ticker24)
        self.assertEqual(ticker.last_price, Decimal("100.4"))
        self.assertEqual(ticker.price_change_pct, Decimal("1.25"))
        self.assertEqual(
            ticker.quote_volume_24h, Decimal("123456.78")
        )

        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["url"],
            "https://api.binance.com/api/v3/ticker/24hr",
        )
        self.assertEqual(kwargs["params"]["symbol"], "BTCUSDT")
        headers = kwargs.get("headers") or {}
        self.assertNotIn("X-MBX-APIKEY", headers)

    @patch("app.services.binance_market_data_client.httpx.request")
    def test_get_ticker_24h_fail_closed(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(200, text="nope")
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_ticker_24h("BTCUSDT")

        request_mock.return_value = httpx.Response(200, json={})
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_ticker_24h("BTCUSDT")

        request_mock.return_value = httpx.Response(
            200, json={"lastPrice": "", "priceChangePercent": "1"}
        )
        with self.assertRaises(MarketDataUnavailable):
            self.client.get_ticker_24h("BTCUSDT")

    def test_depth_and_ticker_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            self.client.get_depth("")
        with self.assertRaises(ValueError):
            self.client.get_depth("BTCUSDT", limit=0)
        with self.assertRaises(ValueError):
            self.client.get_ticker_24h("")


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import httpx

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


class BinanceMarketDataClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1000.0
        self.client = BinanceMarketDataClient(clock=lambda: self.now)

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


if __name__ == "__main__":
    unittest.main()

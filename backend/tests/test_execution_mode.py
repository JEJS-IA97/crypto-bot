import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx

from app.config import settings
from app.services.binance_executor import BinanceExecutor, OrderRejectedError
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.binance_spot_client import BinanceSpotClient
from app.services.exchange_executor import ExchangeOrderStatus, OrderRequest

EXCHANGE_INFO_PAYLOAD = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "7.5"},
            ],
        }
    ]
}


def _spot_order_response(method, url, params=None, **kwargs):
    params = params or {}
    return httpx.Response(
        200,
        json={
            "symbol": params.get("symbol", "BTCUSDT"),
            "orderId": 42,
            "clientOrderId": params.get("newClientOrderId", ""),
            "status": "FILLED",
            "type": params.get("type", "LIMIT"),
            "side": params.get("side", "BUY"),
            "price": params.get("price", "0"),
            "origQty": str(params.get("quantity", "0")),
            "executedQty": str(params.get("quantity", "0")),
            "cummulativeQuoteQty": "8.00000000",
            "timeInForce": params.get("timeInForce", "GTC"),
        },
    )


def _request(client_order_id: str) -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=Decimal("0.080"),
        price=Decimal("100.00"),
        client_order_id=client_order_id,
    )


class ExecutionModeTests(unittest.TestCase):
    def setUp(self) -> None:
        # Un solo patch: ambos clientes comparten el módulo `httpx`.
        self.http_patcher = patch("httpx.request")
        self.http_mock = self.http_patcher.start()
        self.addCleanup(self.http_patcher.stop)

        def router(method, url, params=None, **kwargs):
            if "/api/v3/exchangeInfo" in str(url):
                return httpx.Response(200, json=EXCHANGE_INFO_PAYLOAD)
            if "/api/v3/order" in str(url):
                return _spot_order_response(method, url, params, **kwargs)
            raise AssertionError(f"unexpected URL: {url}")

        self.http_mock.side_effect = router

    def _executor(self, base_url: str) -> BinanceExecutor:
        client = BinanceSpotClient(
            "test-key-123",
            "test-secret-456",
            base_url=base_url,
        )
        return BinanceExecutor(
            client=client,
            market_data=BinanceMarketDataClient(),
        )

    @property
    def order_calls(self):
        return [
            call
            for call in self.http_mock.call_args_list
            if "/api/v3/order" in str(call.kwargs.get("url", ""))
        ]

    def test_no_live_without_flag(self) -> None:
        self.assertFalse(settings.allow_live_trading)

        executor = self._executor("https://api.binance.com")
        with self.assertRaises(OrderRejectedError) as ctx:
            executor.place_order(_request("dec-501"))

        self.assertEqual(ctx.exception.reason, "live_trading_disabled")
        # Ni órdenes ni lecturas contra producción sin la flag.
        self.assertEqual(self.http_mock.call_count, 0)

        # Con la flag explícita, la misma orden sí sale (RF-1/RF-2).
        with patch.object(settings, "allow_live_trading", True):
            result = executor.place_order(_request("dec-502"))

        self.assertEqual(result.status, ExchangeOrderStatus.FILLED)
        self.assertEqual(len(self.order_calls), 1)
        self.assertEqual(
            self.order_calls[0].kwargs["url"],
            "https://api.binance.com/api/v3/order",
        )

    def test_testnet_allowed_without_flag(self) -> None:
        executor = self._executor("https://testnet.binance.vision")
        result = executor.place_order(_request("dec-511"))

        self.assertEqual(result.status, ExchangeOrderStatus.FILLED)
        self.assertEqual(len(self.order_calls), 1)
        self.assertEqual(
            self.order_calls[0].kwargs["url"],
            "https://testnet.binance.vision/api/v3/order",
        )


if __name__ == "__main__":
    unittest.main()

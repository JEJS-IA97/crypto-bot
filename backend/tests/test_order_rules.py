import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx

from app.services.binance_executor import BinanceExecutor, OrderRejectedError
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.binance_spot_client import BinanceSpotClient
from app.services.exchange_executor import (
    ExchangeOrderStatus,
    OrderRequest,
)

# MIN_NOTIONAL = 7.5 (distinto del típico 5) para probar que el mínimo
# viene de exchangeInfo y no de un valor fijo hardcodeado (RF-11/A4).
EXCHANGE_INFO_PAYLOAD = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00100000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "7.50000000"},
            ],
        }
    ]
}


def _spot_order_response(method, url, params=None, **kwargs):
    """Respuesta de create_order que ecoa los parámetros enviados."""
    params = params or {}
    return httpx.Response(
        200,
        json={
            "symbol": params.get("symbol", "BTCUSDT"),
            "orderId": 987654,
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


def _limit_request(**overrides) -> OrderRequest:
    params = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": Decimal("0.080"),
        "price": Decimal("100.00"),
        "client_order_id": "dec-001",
    }
    params.update(overrides)
    return OrderRequest(**params)


class _BinanceExecutorTestCase(unittest.TestCase):
    """Base: un único mock de httpx.request con router por URL.

    `binance_spot_client` y `binance_market_data_client` comparten el
    mismo módulo `httpx`, así que se parchea una sola vez.
    """

    def setUp(self) -> None:
        self.http_patcher = patch("httpx.request")
        self.http_mock = self.http_patcher.start()
        self.addCleanup(self.http_patcher.stop)

        self.exchange_response = httpx.Response(
            200, json=EXCHANGE_INFO_PAYLOAD
        )
        self.order_response = _spot_order_response

        def router(method, url, params=None, **kwargs):
            if "/api/v3/exchangeInfo" in str(url):
                response = self.exchange_response
            elif "/api/v3/order" in str(url):
                response = self.order_response
            else:
                raise AssertionError(f"unexpected URL: {url}")
            if callable(response):
                return response(method, url, params, **kwargs)
            return response

        self.http_mock.side_effect = router

        client = BinanceSpotClient(
            "test-key-123",
            "test-secret-456",
            base_url="https://testnet.binance.vision",
        )
        self.executor = BinanceExecutor(
            client=client,
            market_data=BinanceMarketDataClient(),
        )

    @property
    def exchange_info_calls(self):
        return [
            call
            for call in self.http_mock.call_args_list
            if "/api/v3/exchangeInfo" in str(call.kwargs.get("url", ""))
        ]

    @property
    def order_calls(self):
        return [
            call
            for call in self.http_mock.call_args_list
            if "/api/v3/order" in str(call.kwargs.get("url", ""))
        ]


class BinanceExecutorRulesTests(_BinanceExecutorTestCase):
    def test_min_notional_from_exchange_info(self) -> None:
        # 0.05 × 100 = 5 USDT < 7.5 (MIN_NOTIONAL leído de exchangeInfo).
        too_small = _limit_request(
            quantity=Decimal("0.05"), client_order_id="dec-001"
        )
        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(too_small)
        self.assertEqual(ctx.exception.reason, "below_min_notional")
        self.assertEqual(len(self.order_calls), 0)

        # exchangeInfo se consultó (endpoint público, sin credenciales).
        self.assertEqual(len(self.exchange_info_calls), 1)
        info_kwargs = self.exchange_info_calls[0].kwargs
        self.assertEqual(
            info_kwargs["url"],
            "https://api.binance.com/api/v3/exchangeInfo",
        )
        headers = info_kwargs.get("headers") or {}
        self.assertNotIn("X-MBX-APIKEY", headers)

        # 0.080 × 100 = 8 USDT ≥ 7.5 → la orden sí se envía.
        ok = _limit_request(client_order_id="dec-002")
        result = self.executor.place_order(ok)

        self.assertEqual(result.status, ExchangeOrderStatus.FILLED)
        self.assertEqual(result.order_id, "987654")
        self.assertEqual(result.client_order_id, "dec-002")
        self.assertEqual(result.executed_quantity, Decimal("0.080"))
        self.assertEqual(result.average_price, Decimal("100"))
        self.assertEqual(len(self.order_calls), 1)

        order_kwargs = self.order_calls[0].kwargs
        self.assertEqual(
            order_kwargs["url"],
            "https://testnet.binance.vision/api/v3/order",
        )
        params = order_kwargs["params"]
        self.assertEqual(params["newClientOrderId"], "dec-002")
        self.assertEqual(params["type"], "LIMIT")
        self.assertEqual(params["timeInForce"], "GTC")
        self.assertIn("signature", params)
        self.assertEqual(
            order_kwargs["headers"]["X-MBX-APIKEY"], "test-key-123"
        )

        # Las reglas se cachean: no se vuelve a llamar a exchangeInfo.
        self.assertEqual(len(self.exchange_info_calls), 1)

    def test_step_tick_and_price_checks(self) -> None:
        # Cantidad que no múltiplo del stepSize → quantity_step.
        bad_step = _limit_request(
            quantity=Decimal("0.0005"), client_order_id="dec-101"
        )
        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(bad_step)
        self.assertEqual(ctx.exception.reason, "quantity_step")
        self.assertEqual(len(self.order_calls), 0)

        # Precio que no múltiplo del tickSize → price_tick.
        bad_tick = _limit_request(
            price=Decimal("100.005"), client_order_id="dec-102"
        )
        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(bad_tick)
        self.assertEqual(ctx.exception.reason, "price_tick")
        self.assertEqual(len(self.order_calls), 0)

        # MARKET sin precio → no se puede verificar el notional → rechazo.
        no_price = OrderRequest(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.080"),
            client_order_id="dec-103",
        )
        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(no_price)
        self.assertEqual(ctx.exception.reason, "price_required")
        self.assertEqual(len(self.order_calls), 0)

    def test_symbol_not_trading_rejected(self) -> None:
        payload = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "BREAK",
                    "filters": [
                        {"filterType": "PRICE_FILTER",
                         "tickSize": "0.01"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001"},
                        {"filterType": "MIN_NOTIONAL",
                         "minNotional": "7.5"},
                    ],
                }
            ]
        }
        self.exchange_response = httpx.Response(200, json=payload)

        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(_limit_request())
        self.assertEqual(ctx.exception.reason, "symbol_not_trading")
        self.assertEqual(len(self.order_calls), 0)

    def test_rules_unavailable_fails_closed(self) -> None:
        self.exchange_response = httpx.Response(500, text="oops")

        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(_limit_request())
        self.assertEqual(ctx.exception.reason, "rules_unavailable")
        self.assertEqual(len(self.order_calls), 0)


class ClientOrderIdTests(_BinanceExecutorTestCase):
    def test_client_order_id_unique(self) -> None:
        # Los ids generados son únicos y caben en el límite de 36 chars.
        first_id = BinanceExecutor.generate_client_order_id()
        second_id = BinanceExecutor.generate_client_order_id()
        self.assertNotEqual(first_id, second_id)
        self.assertTrue(first_id)
        self.assertLessEqual(len(first_id), 36)
        self.assertLessEqual(len(second_id), 36)

        # Idempotencia (RF-25): reenviar la misma decisión no duplica orden.
        request = _limit_request(client_order_id="dec-200")
        first = self.executor.place_order(request)
        second = self.executor.place_order(request)

        self.assertEqual(len(self.order_calls), 1)
        self.assertEqual(first.order_id, second.order_id)
        self.assertEqual(second.client_order_id, "dec-200")

        # Sin client_order_id → el executor genera uno único ≤36.
        auto = _limit_request(client_order_id=None)
        result = self.executor.place_order(auto)
        self.assertTrue(result.client_order_id)
        self.assertLessEqual(len(result.client_order_id), 36)
        self.assertEqual(len(self.order_calls), 2)

        # Id demasiado largo → rechazado con motivo, sin red.
        too_long = _limit_request(client_order_id="x" * 37)
        with self.assertRaises(OrderRejectedError) as ctx:
            self.executor.place_order(too_long)
        self.assertEqual(ctx.exception.reason, "client_order_id_too_long")
        self.assertEqual(len(self.order_calls), 2)


if __name__ == "__main__":
    unittest.main()

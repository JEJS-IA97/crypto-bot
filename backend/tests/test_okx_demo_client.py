import base64
import hashlib
import hmac
import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx

from app.services.exchange_executor import (
    ExchangeOrderStatus,
    OrderRequest,
)
from app.services.okx_demo_client import OKXDemoClient


class OKXDemoClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = OKXDemoClient(
            api_key="test-key",
            api_secret="test-secret",
            passphrase="test-passphrase",
        )

    def test_signing_matches_okx_hmac_sha256_base64(self) -> None:
        timestamp = "2026-09-30T12:00:00.000Z"
        method = "POST"
        path = "/api/v5/trade/order"
        body = '{"instId":"BTC-USDT","tdMode":"cash"}'
        payload = f"{timestamp}{method}{path}{body}"
        expected = base64.b64encode(
            hmac.new(
                b"test-secret",
                payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        self.assertEqual(
            self.client._sign(timestamp, method, path, body),
            expected,
        )

    @patch("app.services.okx_demo_client.httpx.request")
    def test_demo_header_is_present_on_request(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(
            200,
            json={"code": "0", "data": [{"ts": "1760000000000"}]},
        )
        self.client.get_server_time()
        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["headers"]["x-simulated-trading"],
            "1",
        )

    def test_symbol_mapping(self) -> None:
        self.assertEqual(
            self.client.to_inst_id("btcusdt"),
            "BTC-USDT",
        )
        self.assertEqual(
            self.client.to_inst_id("ETHUSDT"),
            "ETH-USDT",
        )

    def test_market_order_validation(self) -> None:
        request = OrderRequest(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.001"),
        )
        request.validate()

    def test_limit_order_requires_price(self) -> None:
        request = OrderRequest(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("0.001"),
        )
        with self.assertRaises(ValueError):
            request.validate()

    @patch("app.services.okx_demo_client.httpx.request")
    def test_place_order_builds_spot_demo_payload(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(
            200,
            json={
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "ordId": "123",
                        "clOrdId": "client-1",
                        "state": "live",
                        "side": "buy",
                        "ordType": "limit",
                        "sz": "0.001",
                        "accFillSz": "0",
                        "avgPx": "",
                    }
                ],
            },
        )

        result = self.client.place_order(
            OrderRequest(
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                quantity=Decimal("0.001"),
                price=Decimal("50000"),
                client_order_id="client-1",
            )
        )

        self.assertEqual(result.status, ExchangeOrderStatus.NEW)
        self.assertEqual(result.order_id, "123")
        _, kwargs = request_mock.call_args
        self.assertEqual(
            kwargs["url"],
            "https://openapi.okx.com/api/v5/trade/order",
        )
        self.assertEqual(
            kwargs["headers"]["x-simulated-trading"],
            "1",
        )
        self.assertIn(
            '"instId":"BTC-USDT"',
            kwargs["content"],
        )
        self.assertIn(
            '"tdMode":"cash"',
            kwargs["content"],
        )

    @patch("app.services.okx_demo_client.httpx.request")
    def test_balance_response_is_normalized(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(
            200,
            json={
                "code": "0",
                "data": [
                    {
                        "details": [
                            {
                                "ccy": "USDT",
                                "availBal": "5.25",
                                "frozenBal": "0.10",
                                "cashBal": "5.35",
                            }
                        ]
                    }
                ],
            },
        )

        balances = self.client.get_balances("USDT")
        self.assertEqual(len(balances), 1)
        self.assertEqual(balances[0].asset, "USDT")
        self.assertEqual(balances[0].available, Decimal("5.25"))
        self.assertEqual(balances[0].locked, Decimal("0.10"))


if __name__ == "__main__":
    unittest.main()

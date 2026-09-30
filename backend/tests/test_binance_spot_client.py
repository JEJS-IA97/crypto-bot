import hashlib
import hmac
import unittest
from unittest.mock import patch

import httpx

from app.services.binance_spot_client import BinanceAPIError, BinanceSpotClient


class BinanceSpotClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = BinanceSpotClient("test-key", "test-secret")

    def test_hmac_signature_is_deterministic(self) -> None:
        params = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "quantity": "0.001", "price": "50000", "timestamp": 1234567890000}
        expected_payload = "symbol=BTCUSDT&side=BUY&type=LIMIT&quantity=0.001&price=50000&timestamp=1234567890000"
        expected = hmac.new(b"test-secret", expected_payload.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(self.client._sign(params), expected)

    def test_limit_order_parameters(self) -> None:
        params = self.client._build_order_params("btcusdt", "buy", "limit", "0.001", "50000", "gtc", None, "order-1")
        self.assertEqual(params["symbol"], "BTCUSDT")
        self.assertEqual(params["side"], "BUY")
        self.assertEqual(params["type"], "LIMIT")
        self.assertEqual(params["timeInForce"], "GTC")

    def test_rejects_non_spot_order_types(self) -> None:
        with self.assertRaises(ValueError):
            self.client._build_order_params("BTCUSDT", "BUY", "STOP_MARKET", "0.001", None, None, None, None)

    @patch("app.services.binance_spot_client.httpx.request")
    def test_signed_account_uses_spot_endpoint(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(200, json={"accountType": "SPOT", "permissions": ["SPOT"], "balances": []})
        result = self.client.get_account()
        self.assertEqual(result["accountType"], "SPOT")
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["url"], "https://testnet.binance.vision/api/v3/account")
        self.assertIn("X-MBX-APIKEY", kwargs["headers"])
        self.assertIn("signature", kwargs["params"])

    @patch("app.services.binance_spot_client.httpx.request")
    def test_timestamp_error_resyncs_and_retries(self, request_mock) -> None:
        request_mock.side_effect = [
            httpx.Response(400, json={"code": -1021, "msg": "Timestamp outside recvWindow"}),
            httpx.Response(200, json={"serverTime": 2000000}),
            httpx.Response(200, json={"accountType": "SPOT", "permissions": ["SPOT"], "balances": []}),
        ]
        self.assertEqual(self.client.get_account()["accountType"], "SPOT")
        self.assertEqual(request_mock.call_count, 3)

    def test_missing_credentials_fail_closed(self) -> None:
        client = BinanceSpotClient("", "")
        with self.assertRaises(RuntimeError):
            client.get_account()

    @patch("app.services.binance_spot_client.httpx.request")
    def test_api_error_is_normalized(self, request_mock) -> None:
        request_mock.return_value = httpx.Response(400, json={"code": -2015, "msg": "Invalid API-key"})
        with self.assertRaises(BinanceAPIError) as context:
            self.client.get_account()
        self.assertEqual(context.exception.code, -2015)


if __name__ == "__main__":
    unittest.main()

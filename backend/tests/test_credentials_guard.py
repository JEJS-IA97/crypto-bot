import logging
import unittest
from decimal import Decimal
from unittest.mock import patch

import httpx

from app.services.binance_executor import BinanceExecutor, OrderRejectedError
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.binance_spot_client import BinanceSpotClient
from app.services.exchange_executor import OrderRequest

API_KEY = "AKIFAKIFAKIF1234"
API_SECRET = "SECRETAABBCCDD5678"

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


def _order_request(
    client_order_id="dec-301", quantity=Decimal("0.080")
) -> OrderRequest:
    return OrderRequest(
        symbol="BTCUSDT",
        side="BUY",
        order_type="LIMIT",
        quantity=quantity,
        price=Decimal("100.00"),
        client_order_id=client_order_id,
    )


class CredentialsGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        # `binance_spot_client` y `binance_market_data_client` comparten
        # el mismo módulo `httpx`, así que se parchea una sola vez.
        self.http_patcher = patch("httpx.request")
        self.http_mock = self.http_patcher.start()
        self.addCleanup(self.http_patcher.stop)

        self.order_response = httpx.Response(
            200, json={"orderId": 1, "status": "NEW", "executedQty": "0"}
        )

        def router(method, url, params=None, **kwargs):
            if "/api/v3/exchangeInfo" in str(url):
                return httpx.Response(200, json=EXCHANGE_INFO_PAYLOAD)
            if "/api/v3/order" in str(url):
                return self.order_response
            raise AssertionError(f"unexpected URL: {url}")

        self.http_mock.side_effect = router

    def _executor(self, api_key: str, api_secret: str) -> BinanceExecutor:
        client = BinanceSpotClient(
            api_key,
            api_secret,
            base_url="https://testnet.binance.vision",
        )
        return BinanceExecutor(
            client=client,
            market_data=BinanceMarketDataClient(),
        )

    def test_fails_safe_without_keys(self) -> None:
        executor = self._executor("", "")
        self.assertFalse(executor.is_configured)

        with self.assertRaises(OrderRejectedError) as ctx:
            executor.place_order(_order_request())

        self.assertEqual(ctx.exception.reason, "credentials_missing")
        # Sin claves no se toca la red: ni órdenes ni lecturas.
        self.assertEqual(self.http_mock.call_count, 0)

    def test_no_keys_in_logs(self) -> None:
        executor = self._executor(API_KEY, API_SECRET)

        records: list[str] = []

        class Collector(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record.getMessage())

        collector = Collector()
        root = logging.getLogger()
        root.addHandler(collector)
        try:
            executor.place_order(_order_request(client_order_id="dec-401"))
            with self.assertRaises(OrderRejectedError) as ctx:
                executor.place_order(
                    _order_request(
                        client_order_id="dec-402",
                        quantity=Decimal("0.05"),
                    )
                )
            # El motivo del rechazo queda registrado en el log.
            self.assertEqual(ctx.exception.reason, "below_min_notional")
        finally:
            root.removeHandler(collector)

        joined = "\n".join(records)
        self.assertIn("below_min_notional", joined)
        self.assertNotIn(API_KEY, joined)
        self.assertNotIn(API_SECRET, joined)
        self.assertNotIn(API_KEY, str(ctx.exception))
        self.assertNotIn(API_SECRET, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

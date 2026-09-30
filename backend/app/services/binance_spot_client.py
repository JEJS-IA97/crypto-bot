import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx


class BinanceAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int, code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BinanceSpotClient:
    """Minimal Binance Spot REST client; no futures, margin, transfers or withdrawals."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://testnet.binance.vision", recv_window_ms: int = 5000, timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = base_url.rstrip("/")
        self.recv_window_ms = recv_window_ms
        self.timeout_seconds = timeout_seconds
        self._time_offset_ms = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _require_credentials(self) -> None:
        if not self.is_configured:
            raise RuntimeError("Binance API credentials are not configured.")

    def _timestamp_ms(self) -> int:
        return int(time.time() * 1000) + self._time_offset_ms

    def _sign(self, params: dict[str, Any]) -> str:
        payload = urlencode(params, doseq=True)
        return hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None, signed: bool = False, retry_on_timestamp_error: bool = True) -> Any:
        request_params = dict(params or {})
        if signed:
            self._require_credentials()
            request_params["timestamp"] = self._timestamp_ms()
            request_params["recvWindow"] = self.recv_window_ms
            request_params["signature"] = self._sign(request_params)

        headers = {}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        url = f"{self.base_url}/api{path}"
        try:
            response = httpx.request(method=method, url=url, params=request_params, headers=headers, timeout=self.timeout_seconds)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Binance HTTP request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.is_error:
            code = None
            message = response.text
            if isinstance(data, dict):
                raw_code = data.get("code")
                if raw_code is not None:
                    code = int(raw_code)
                message = str(data.get("msg", message))

            if signed and code == -1021 and retry_on_timestamp_error:
                self.sync_time()
                return self._request(method, path, params=params, signed=signed, retry_on_timestamp_error=False)

            raise BinanceAPIError(
                message=(f"Binance API error {code}: {message}" if code is not None else f"Binance API error: {message}"),
                status_code=response.status_code,
                code=code,
            )

        return data

    def ping(self) -> dict:
        return self._request("GET", "/v3/ping")

    def get_server_time(self) -> int:
        data = self._request("GET", "/v3/time")
        return int(data["serverTime"])

    def sync_time(self) -> int:
        local_before = int(time.time() * 1000)
        server_time = self.get_server_time()
        local_after = int(time.time() * 1000)
        midpoint = (local_before + local_after) // 2
        self._time_offset_ms = server_time - midpoint
        return self._time_offset_ms

    def get_exchange_info(self, symbol: str | None = None) -> dict:
        params = {"symbol": symbol.upper()} if symbol else {}
        return self._request("GET", "/v3/exchangeInfo", params=params)

    def get_symbol_info(self, symbol: str) -> dict:
        normalized = symbol.upper()
        data = self.get_exchange_info(normalized)
        symbols = data.get("symbols", [])
        if not symbols:
            raise RuntimeError(f"Binance returned no symbol metadata for {normalized}.")
        return symbols[0]

    def get_account(self, omit_zero_balances: bool = True) -> dict:
        return self._request("GET", "/v3/account", params={"omitZeroBalances": "true" if omit_zero_balances else "false"}, signed=True)

    def test_order(self, symbol: str, side: str, order_type: str, quantity: Decimal | str | None = None, price: Decimal | str | None = None, time_in_force: str | None = None, quote_order_qty: Decimal | str | None = None, new_client_order_id: str | None = None) -> dict:
        params = self._build_order_params(symbol, side, order_type, quantity, price, time_in_force, quote_order_qty, new_client_order_id)
        return self._request("POST", "/v3/order/test", params=params, signed=True)

    def create_order(self, symbol: str, side: str, order_type: str, quantity: Decimal | str | None = None, price: Decimal | str | None = None, time_in_force: str | None = None, quote_order_qty: Decimal | str | None = None, new_client_order_id: str | None = None) -> dict:
        params = self._build_order_params(symbol, side, order_type, quantity, price, time_in_force, quote_order_qty, new_client_order_id)
        return self._request("POST", "/v3/order", params=params, signed=True)

    def get_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> dict:
        if order_id is None and not client_order_id:
            raise ValueError("order_id or client_order_id is required.")
        params: dict[str, Any] = {"symbol": symbol.upper()}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._request("GET", "/v3/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int | None = None, client_order_id: str | None = None) -> dict:
        if order_id is None and not client_order_id:
            raise ValueError("order_id or client_order_id is required.")
        params: dict[str, Any] = {"symbol": symbol.upper()}
        if order_id is not None:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._request("DELETE", "/v3/order", params=params, signed=True)

    @staticmethod
    def _build_order_params(symbol: str, side: str, order_type: str, quantity: Decimal | str | None, price: Decimal | str | None, time_in_force: str | None, quote_order_qty: Decimal | str | None, new_client_order_id: str | None) -> dict[str, Any]:
        normalized_side = side.upper()
        normalized_type = order_type.upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL.")
        if normalized_type not in {"LIMIT", "MARKET"}:
            raise ValueError("Only LIMIT and MARKET Spot orders are supported by this client.")
        if quantity is None and quote_order_qty is None:
            raise ValueError("quantity or quote_order_qty is required.")
        if quantity is not None and quote_order_qty is not None:
            raise ValueError("quantity and quote_order_qty cannot be used together.")

        params: dict[str, Any] = {"symbol": symbol.upper(), "side": normalized_side, "type": normalized_type}
        if quantity is not None:
            params["quantity"] = str(quantity)
        if quote_order_qty is not None:
            params["quoteOrderQty"] = str(quote_order_qty)
        if price is not None:
            params["price"] = str(price)
        if time_in_force is not None:
            params["timeInForce"] = time_in_force.upper()
        if new_client_order_id is not None:
            if not new_client_order_id.strip():
                raise ValueError("new_client_order_id cannot be empty.")
            params["newClientOrderId"] = new_client_order_id
        if normalized_type == "LIMIT":
            if price is None:
                raise ValueError("LIMIT orders require price.")
            if time_in_force is None:
                raise ValueError("LIMIT orders require time_in_force.")
        return params

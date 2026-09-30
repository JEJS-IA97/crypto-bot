from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.services.exchange_executor import (
    ExchangeBalance,
    ExchangeOrderResult,
    ExchangeOrderStatus,
    OrderRequest,
    SymbolMetadata,
)


class OKXAPIError(RuntimeError):
    def __init__(self, message: str, http_status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


class OKXDemoClient:
    """Authenticated OKX Demo Trading Spot REST client.

    This client deliberately exposes only Spot cash trading operations. It does not
    implement margin, futures, swaps, options, transfers, deposits or withdrawals.
    """

    exchange_name = "okx"

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        passphrase: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.okx_demo_api_key).strip()
        self.api_secret = (api_secret if api_secret is not None else settings.okx_demo_api_secret).strip()
        self.passphrase = (passphrase if passphrase is not None else settings.okx_demo_api_passphrase).strip()
        configured_base_url = base_url if base_url is not None else settings.okx_demo_base_url
        configured_timeout = timeout_seconds if timeout_seconds is not None else settings.okx_demo_timeout_seconds
        self.base_url = configured_base_url.rstrip("/")
        self.timeout_seconds = float(configured_timeout)
        self._time_offset_ms = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)

    def _require_credentials(self) -> None:
        if not self.is_configured:
            raise RuntimeError("OKX Demo API credentials are not configured.")

    @staticmethod
    def _format_timestamp(timestamp_ms: int | None = None) -> str:
        value = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _timestamp(self) -> str:
        return self._format_timestamp(int(time.time() * 1000) + self._time_offset_ms)

    @staticmethod
    def _build_query(params: dict[str, Any] | None) -> str:
        if not params:
            return ""
        filtered = {key: value for key, value in params.items() if value is not None}
        return urlencode(filtered, doseq=True)

    def _sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        message = f"{timestamp}{method.upper()}{request_path}{body}"
        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        query = self._build_query(params)
        request_path = path + (f"?{query}" if query else "")
        body_text = "" if body is None else _compact_json(body)
        timestamp = self._timestamp() if signed else None

        headers = {
            "Content-Type": "application/json",
            "x-simulated-trading": "1",
        }
        if signed:
            self._require_credentials()
            headers.update(
                {
                    "OK-ACCESS-KEY": self.api_key,
                    "OK-ACCESS-SIGN": self._sign(timestamp or "", method, request_path, body_text),
                    "OK-ACCESS-PASSPHRASE": self.passphrase,
                    "OK-ACCESS-TIMESTAMP": timestamp or "",
                }
            )

        try:
            response = httpx.request(
                method=method,
                url=f"{self.base_url}{path}",
                params=params,
                content=body_text or None,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"OKX HTTP request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = None

        if not isinstance(data, dict):
            raise OKXAPIError(
                message=f"OKX returned a non-JSON response with HTTP {response.status_code}.",
                http_status=response.status_code,
            )

        if response.is_error or str(data.get("code", "0")) != "0":
            code = str(data.get("code")) if data.get("code") is not None else None
            message = str(data.get("msg", response.text))
            raise OKXAPIError(
                message=f"OKX API error {code}: {message}" if code else f"OKX API error: {message}",
                http_status=response.status_code,
                code=code,
            )

        return data

    def get_server_time(self) -> int:
        data = self._request("GET", "/api/v5/public/time")
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError("OKX returned no server time.")
        return int(rows[0]["ts"])

    def sync_time(self) -> int:
        local_before = int(time.time() * 1000)
        server_time = self.get_server_time()
        local_after = int(time.time() * 1000)
        midpoint = (local_before + local_after) // 2
        self._time_offset_ms = server_time - midpoint
        return self._time_offset_ms

    @staticmethod
    def to_inst_id(symbol: str) -> str:
        normalized = symbol.upper()
        if normalized.endswith("USDT"):
            return f"{normalized[:-4]}-USDT"
        if normalized.endswith("USD"):
            return f"{normalized[:-3]}-USD"
        raise ValueError(f"Unsupported OKX spot symbol: {symbol}")

    def get_instrument(self, symbol: str) -> dict[str, Any]:
        inst_id = self.to_inst_id(symbol)
        data = self._request(
            "GET",
            "/api/v5/public/instruments",
            params={"instType": "SPOT", "instId": inst_id},
        )
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError(f"OKX returned no SPOT metadata for {symbol}.")
        return rows[0]

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        raw = self.get_instrument(symbol)
        return SymbolMetadata(
            exchange=self.exchange_name,
            symbol=symbol.upper(),
            base_asset=str(raw["baseCcy"]),
            quote_asset=str(raw["quoteCcy"]),
            status=str(raw["state"]),
            min_quantity=_decimal_or_none(raw.get("minSz")),
            max_quantity=_decimal_or_none(raw.get("maxLmtSz")),
            quantity_step=_decimal_or_none(raw.get("lotSz")),
            price_tick=_decimal_or_none(raw.get("tickSz")),
            min_notional=None,
            raw=raw,
        )

    def get_balances(self, currency: str | None = None) -> list[ExchangeBalance]:
        data = self._request(
            "GET",
            "/api/v5/account/balance",
            params={"ccy": currency.upper() if currency else None},
            signed=True,
        )
        details = data.get("data", [])
        if not details:
            return []

        result: list[ExchangeBalance] = []
        for item in details[0].get("details", []):
            available = _decimal_or_none(item.get("availBal")) or Decimal("0")
            locked = _decimal_or_none(item.get("frozenBal")) or Decimal("0")
            total = _decimal_or_none(item.get("cashBal"))
            result.append(
                ExchangeBalance(
                    exchange=self.exchange_name,
                    asset=str(item["ccy"]),
                    available=available,
                    locked=locked,
                    total=total,
                )
            )
        return result

    def place_order(self, request: OrderRequest) -> ExchangeOrderResult:
        request.validate()
        side = request.normalized_side()
        order_type = request.normalized_order_type()
        body: dict[str, Any] = {
            "instId": self.to_inst_id(request.symbol),
            "tdMode": "cash",
            "side": side.lower(),
            "ordType": order_type.lower(),
            "sz": _decimal_string(request.quantity),
        }

        if order_type == "LIMIT":
            body["px"] = _decimal_string(request.price)
        elif side == "BUY":
            body["tgtCcy"] = "base_ccy"

        if request.client_order_id:
            body["clOrdId"] = request.client_order_id

        data = self._request(
            "POST",
            "/api/v5/trade/order",
            body=body,
            signed=True,
        )
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError("OKX returned no order result.")
        return self._normalize_order_result(
            symbol=request.symbol,
            request=request,
            raw=rows[0],
        )

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        if not order_id and not client_order_id:
            raise ValueError("order_id or client_order_id is required.")

        params = {"instId": self.to_inst_id(symbol)}
        if order_id:
            params["ordId"] = order_id
        if client_order_id:
            params["clOrdId"] = client_order_id

        data = self._request(
            "GET",
            "/api/v5/trade/order",
            params=params,
            signed=True,
        )
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError(f"OKX returned no order for {symbol}.")
        request = OrderRequest(
            symbol=symbol,
            side=str(rows[0].get("side", "BUY")).upper(),
            order_type=str(rows[0].get("ordType", "MARKET")).upper(),
            quantity=_decimal_or_none(rows[0].get("sz")) or Decimal("0"),
            price=_decimal_or_none(rows[0].get("px")),
            client_order_id=rows[0].get("clOrdId") or None,
        )
        return self._normalize_order_result(symbol, request, rows[0])

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        if not order_id and not client_order_id:
            raise ValueError("order_id or client_order_id is required.")

        body = {"instId": self.to_inst_id(symbol)}
        if order_id:
            body["ordId"] = order_id
        if client_order_id:
            body["clOrdId"] = client_order_id

        data = self._request(
            "POST",
            "/api/v5/trade/cancel-order",
            body=body,
            signed=True,
        )
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError("OKX returned no cancel result.")

        row = rows[0]
        request = OrderRequest(
            symbol=symbol,
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.000000000001"),
            client_order_id=row.get("clOrdId") or client_order_id,
        )
        return self._normalize_order_result(symbol, request, row, forced_status=ExchangeOrderStatus.CANCELED)

    def _normalize_order_result(
        self,
        symbol: str,
        request: OrderRequest,
        raw: dict[str, Any],
        forced_status: ExchangeOrderStatus | None = None,
    ) -> ExchangeOrderResult:
        status = forced_status or _normalize_okx_status(raw.get("state"))
        return ExchangeOrderResult(
            exchange=self.exchange_name,
            symbol=symbol.upper(),
            order_id=str(raw["ordId"]) if raw.get("ordId") else None,
            client_order_id=str(raw["clOrdId"]) if raw.get("clOrdId") else request.client_order_id,
            status=status,
            side=str(raw.get("side", request.side)).upper(),
            order_type=str(raw.get("ordType", request.order_type)).upper(),
            requested_quantity=(_decimal_or_none(raw.get("sz")) or request.quantity),
            executed_quantity=(_decimal_or_none(raw.get("accFillSz")) or Decimal("0")),
            average_price=_decimal_or_none(raw.get("avgPx")),
            fee=_decimal_or_none(raw.get("fee")),
            fee_asset=raw.get("feeCcy") or None,
            raw=raw,
        )


def _compact_json(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_string(value: Decimal | None) -> str:
    if value is None:
        raise ValueError("Decimal value is required.")
    return format(value, "f")


def _normalize_okx_status(value: Any) -> ExchangeOrderStatus:
    mapping = {
        "live": ExchangeOrderStatus.NEW,
        "partially_filled": ExchangeOrderStatus.PARTIALLY_FILLED,
        "filled": ExchangeOrderStatus.FILLED,
        "canceled": ExchangeOrderStatus.CANCELED,
        "mmp_canceled": ExchangeOrderStatus.CANCELED,
        "rejected": ExchangeOrderStatus.REJECTED,
        "expired": ExchangeOrderStatus.EXPIRED,
    }
    return mapping.get(str(value).lower(), ExchangeOrderStatus.UNKNOWN)

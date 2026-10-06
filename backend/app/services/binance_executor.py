"""Binance Spot adapter for the `ExchangeExecutor` protocol (M7).

Fail-closed by design (spec 001 RF-11/RF-14/RF-1/RF-2/RF-25):
- every order validates the symbol rules read from `exchangeInfo`
  (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL/NOTIONAL) — no hardcoded minimums;
- without API credentials no request leaves the process;
- production URLs are refused unless `ALLOW_LIVE_TRADING=true`;
- a `clientOrderId` is idempotent per decision: retrying the same id
  returns the original result instead of creating a second order.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any, NoReturn

from app.config import settings
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
    SymbolRules,
)
from app.services.binance_spot_client import BinanceSpotClient
from app.services.exchange_executor import (
    ExchangeBalance,
    ExchangeOrderResult,
    ExchangeOrderStatus,
    OrderRequest,
    SymbolMetadata,
)

logger = logging.getLogger(__name__)

MAX_CLIENT_ORDER_ID_LENGTH = 36

REASON_CREDENTIALS_MISSING = "credentials_missing"
REASON_LIVE_DISABLED = "live_trading_disabled"
REASON_ID_TOO_LONG = "client_order_id_too_long"
REASON_PRICE_REQUIRED = "price_required"
REASON_RULES_UNAVAILABLE = "rules_unavailable"
REASON_NOT_TRADING = "symbol_not_trading"
REASON_QUANTITY_STEP = "quantity_step"
REASON_PRICE_TICK = "price_tick"
REASON_BELOW_MIN_NOTIONAL = "below_min_notional"


class OrderRejectedError(ValueError):
    """An order refused before sending; `reason` is the machine code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


def _points_to_production(base_url: str) -> bool:
    return "testnet" not in base_url.lower()


def _to_decimal(value: object, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return Decimal(default)


class BinanceExecutor:
    """`ExchangeExecutor` implementation over `BinanceSpotClient`."""

    exchange_name = "binance_spot"

    def __init__(
        self,
        client: BinanceSpotClient,
        market_data: BinanceMarketDataClient | None = None,
    ) -> None:
        self.client = client
        self.market_data = market_data or BinanceMarketDataClient()
        self._issued: dict[str, ExchangeOrderResult] = {}

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    @staticmethod
    def generate_client_order_id() -> str:
        """Unique id of at most 36 chars (Binance limit, RF-25)."""
        return f"bot-{uuid.uuid4().hex}"

    def _reject(self, reason: str, detail: str = "") -> NoReturn:
        logger.warning("binance order rejected: %s", reason)
        raise OrderRejectedError(reason, detail)

    def _require_credentials(self) -> None:
        if not self.client.is_configured:
            self._reject(
                REASON_CREDENTIALS_MISSING,
                "Binance API credentials are not configured.",
            )

    def _rules(self, symbol: str) -> SymbolRules:
        try:
            return self.market_data.get_exchange_info(symbol)
        except MarketDataUnavailable as exc:
            self._reject(REASON_RULES_UNAVAILABLE, str(exc))

    def place_order(self, request: OrderRequest) -> ExchangeOrderResult:
        request.validate()
        self._require_credentials()
        if not settings.allow_live_trading and _points_to_production(
            self.client.base_url
        ):
            self._reject(
                REASON_LIVE_DISABLED,
                "ALLOW_LIVE_TRADING is not true: refusing production order.",
            )

        provided_id = (request.client_order_id or "").strip() or None
        if provided_id is not None and len(provided_id) > (
            MAX_CLIENT_ORDER_ID_LENGTH
        ):
            self._reject(
                REASON_ID_TOO_LONG,
                f"clientOrderId longer than "
                f"{MAX_CLIENT_ORDER_ID_LENGTH} chars.",
            )
        if provided_id is not None and provided_id in self._issued:
            return self._issued[provided_id]
        client_order_id = provided_id or self.generate_client_order_id()

        if request.price is None:
            self._reject(
                REASON_PRICE_REQUIRED,
                "price is required to verify the minimum notional.",
            )

        symbol = request.symbol.upper()
        rules = self._rules(symbol)
        if not rules.tradable:
            self._reject(
                REASON_NOT_TRADING, f"{symbol} is not TRADING."
            )
        if rules.step_size <= 0 or rules.tick_size <= 0:
            self._reject(
                REASON_RULES_UNAVAILABLE,
                f"unusable trading rules for {symbol}.",
            )
        if request.quantity % rules.step_size != 0:
            self._reject(
                REASON_QUANTITY_STEP,
                f"quantity does not match stepSize {rules.step_size}.",
            )
        if request.price % rules.tick_size != 0:
            self._reject(
                REASON_PRICE_TICK,
                f"price does not match tickSize {rules.tick_size}.",
            )
        notional = request.quantity * request.price
        if notional < rules.min_notional:
            self._reject(
                REASON_BELOW_MIN_NOTIONAL,
                f"notional {notional} below MIN_NOTIONAL "
                f"{rules.min_notional} from exchangeInfo.",
            )

        side = request.normalized_side()
        order_type = request.normalized_order_type()
        payload = self.client.create_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=request.quantity,
            price=request.price if order_type == "LIMIT" else None,
            time_in_force="GTC" if order_type == "LIMIT" else None,
            new_client_order_id=client_order_id,
        )
        result = self._build_result(
            payload,
            symbol=symbol,
            side=side,
            order_type=order_type,
            requested_quantity=request.quantity,
            client_order_id=client_order_id,
        )
        if provided_id is not None:
            self._issued[provided_id] = result
        return result

    def get_balances(self) -> list[ExchangeBalance]:
        self._require_credentials()
        account = self.client.get_account()
        balances: list[ExchangeBalance] = []
        for entry in account.get("balances", []):
            if not isinstance(entry, dict):
                continue
            available = _to_decimal(entry.get("free"))
            locked = _to_decimal(entry.get("locked"))
            if available == 0 and locked == 0:
                continue
            balances.append(
                ExchangeBalance(
                    exchange=self.exchange_name,
                    asset=str(entry.get("asset", "")),
                    available=available,
                    locked=locked,
                    total=available + locked,
                )
            )
        return balances

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        rules = self._rules(symbol)
        quote = "USDT" if rules.symbol.endswith("USDT") else ""
        base = rules.symbol[: -len(quote)] if quote else rules.symbol
        return SymbolMetadata(
            exchange=self.exchange_name,
            symbol=rules.symbol,
            base_asset=base,
            quote_asset=quote,
            status=rules.status,
            min_quantity=None,
            max_quantity=None,
            quantity_step=rules.step_size,
            price_tick=rules.tick_size,
            min_notional=rules.min_notional,
        )

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        self._require_credentials()
        numeric_id = (
            int(order_id) if order_id and str(order_id).isdigit() else None
        )
        payload = self.client.get_order(
            symbol=symbol,
            order_id=numeric_id,
            client_order_id=client_order_id,
        )
        return self._result_from_payload(payload, symbol)

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        self._require_credentials()
        numeric_id = (
            int(order_id) if order_id and str(order_id).isdigit() else None
        )
        payload = self.client.cancel_order(
            symbol=symbol,
            order_id=numeric_id,
            client_order_id=client_order_id,
        )
        return self._result_from_payload(payload, symbol)

    def _build_result(
        self,
        payload: dict[str, Any],
        *,
        symbol: str,
        side: str,
        order_type: str,
        requested_quantity: Decimal,
        client_order_id: str | None,
    ) -> ExchangeOrderResult:
        executed = _to_decimal(payload.get("executedQty"))
        quote = _to_decimal(payload.get("cummulativeQuoteQty"))
        average_price = quote / executed if executed > 0 and quote > 0 else None
        status = self._parse_status(payload.get("status"))
        order_id = payload.get("orderId")
        echoed_id = payload.get("clientOrderId")
        return ExchangeOrderResult(
            exchange=self.exchange_name,
            symbol=str(payload.get("symbol") or symbol),
            order_id=str(order_id) if order_id is not None else None,
            client_order_id=str(echoed_id or client_order_id or "") or None,
            status=status,
            side=side,
            order_type=order_type,
            requested_quantity=requested_quantity,
            executed_quantity=executed,
            average_price=average_price,
            fee=None,
            fee_asset=None,
            raw=dict(payload),
        )

    def _result_from_payload(
        self, payload: dict[str, Any], symbol: str
    ) -> ExchangeOrderResult:
        return self._build_result(
            payload,
            symbol=str(payload.get("symbol") or symbol),
            side=str(payload.get("side") or ""),
            order_type=str(payload.get("type") or ""),
            requested_quantity=_to_decimal(payload.get("origQty")),
            client_order_id=str(payload.get("clientOrderId") or "") or None,
        )

    @staticmethod
    def _parse_status(raw: object) -> ExchangeOrderStatus:
        try:
            return ExchangeOrderStatus(str(raw))
        except ValueError:
            return ExchangeOrderStatus.UNKNOWN

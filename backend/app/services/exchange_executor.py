from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol


class ExchangeOrderStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExchangeBalance:
    exchange: str
    asset: str
    available: Decimal
    locked: Decimal = Decimal("0")
    total: Decimal | None = None


@dataclass(frozen=True)
class SymbolMetadata:
    exchange: str
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    min_quantity: Decimal | None = None
    max_quantity: Decimal | None = None
    quantity_step: Decimal | None = None
    price_tick: Decimal | None = None
    min_notional: Decimal | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    client_order_id: str | None = None

    def normalized_side(self) -> str:
        value = self.side.upper()
        if value not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL.")
        return value

    def normalized_order_type(self) -> str:
        value = self.order_type.upper()
        if value not in {"LIMIT", "MARKET"}:
            raise ValueError("Only LIMIT and MARKET Spot orders are supported.")
        if value == "LIMIT" and self.price is None:
            raise ValueError("LIMIT orders require price.")
        return value

    def validate(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero.")
        self.normalized_side()
        self.normalized_order_type()
        if self.client_order_id is not None and not self.client_order_id.strip():
            raise ValueError("client_order_id cannot be empty.")


@dataclass(frozen=True)
class ExchangeOrderResult:
    exchange: str
    symbol: str
    order_id: str | None
    client_order_id: str | None
    status: ExchangeOrderStatus
    side: str
    order_type: str
    requested_quantity: Decimal
    executed_quantity: Decimal
    average_price: Decimal | None
    fee: Decimal | None
    fee_asset: str | None
    raw: dict[str, Any] = field(default_factory=dict)


class ExchangeExecutor(Protocol):
    exchange_name: str

    @property
    def is_configured(self) -> bool: ...

    def get_balances(self) -> list[ExchangeBalance]: ...

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata: ...

    def place_order(self, request: OrderRequest) -> ExchangeOrderResult: ...

    def get_order(self, symbol: str, order_id: str | None = None, client_order_id: str | None = None) -> ExchangeOrderResult: ...

    def cancel_order(self, symbol: str, order_id: str | None = None, client_order_id: str | None = None) -> ExchangeOrderResult: ...

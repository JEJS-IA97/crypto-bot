from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import TradeSide
from app.schemas import SimulationOrderRequest
from app.services.exchange_executor import (
    ExchangeBalance,
    ExchangeOrderResult,
    ExchangeOrderStatus,
    OrderRequest,
    SymbolMetadata,
)
from app.services.simulation_service import execute_order


class SimulationExecutor:
    """Adapter that exposes the existing simulator through the exchange interface."""

    exchange_name = "simulation"

    def __init__(self, db: Session, account_id: int) -> None:
        self.db = db
        self.account_id = account_id

    @property
    def is_configured(self) -> bool:
        return True

    def get_balances(self) -> list[ExchangeBalance]:
        from app.services.simulation_service import get_balance

        balance = get_balance(self.db, self.account_id)
        return [
            ExchangeBalance(
                exchange=self.exchange_name,
                asset="USD",
                available=Decimal(str(balance.available_usd)),
                locked=Decimal("0"),
                total=Decimal(str(balance.total_balance_usd)),
            )
        ]

    def get_symbol_metadata(self, symbol: str) -> SymbolMetadata:
        normalized = symbol.upper()
        base = normalized[:-4] if normalized.endswith("USDT") else normalized
        quote = "USDT" if normalized.endswith("USDT") else "USD"
        return SymbolMetadata(
            exchange=self.exchange_name,
            symbol=normalized,
            base_asset=base,
            quote_asset=quote,
            status="TRADING",
            raw={"adapter": "simulation"},
        )

    def place_order(self, request: OrderRequest) -> ExchangeOrderResult:
        request.validate()
        if request.price is None:
            raise ValueError("Simulation executor requires an execution price.")

        side = TradeSide[request.normalized_side()]
        result = execute_order(
            self.db,
            self.account_id,
            SimulationOrderRequest(
                symbol=request.symbol.upper(),
                side=side,
                quantity=request.quantity,
                price=request.price,
            ),
        )

        return ExchangeOrderResult(
            exchange=self.exchange_name,
            symbol=result.symbol,
            order_id=str(result.id),
            client_order_id=request.client_order_id,
            status=ExchangeOrderStatus.FILLED,
            side=result.side.value,
            order_type=request.normalized_order_type(),
            requested_quantity=result.quantity,
            executed_quantity=result.quantity,
            average_price=result.price,
            fee=result.fee_usd,
            fee_asset="USD",
            raw={"simulation_trade_id": result.id},
        )

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        raise NotImplementedError("Simulation order lookup will be added with the persistent order lifecycle.")

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrderResult:
        raise NotImplementedError("Simulation cancellation is not applicable to immediate fills.")

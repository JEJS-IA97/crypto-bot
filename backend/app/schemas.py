from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import TradeSide


class SimulationAccountCreate(BaseModel):
    name: str = Field(
        default="Default Simulation",
        min_length=1,
        max_length=100,
    )
    initial_balance_usd: Decimal = Field(
        default=Decimal("20.00"),
        gt=Decimal("0"),
    )


class SimulationAccountResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BalanceResponse(BaseModel):
    account_id: int
    available_usd: Decimal
    invested_usd: Decimal
    market_value_usd: Decimal
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    total_balance_usd: Decimal


class PositionResponse(BaseModel):
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal
    current_price: Decimal | None = None
    market_value_usd: Decimal | None = None
    unrealized_pnl_usd: Decimal | None = None


class SimulationOrderRequest(BaseModel):
    symbol: str = Field(
        min_length=3,
        max_length=20,
        pattern=r"^[A-Z0-9]+$",
    )
    side: TradeSide
    quantity: Decimal = Field(
        gt=Decimal("0"),
    )
    price: Decimal = Field(
        gt=Decimal("0"),
    )


class TradeResponse(BaseModel):
    id: int
    symbol: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    total_usd: Decimal
    fee_usd: Decimal
    realized_pnl_usd: Decimal
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TradeHistoryResponse(BaseModel):
    id: int
    symbol: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    total_usd: Decimal
    fee_usd: Decimal
    realized_pnl_usd: Decimal
    executed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketPriceUpdateRequest(BaseModel):
    symbol: str = Field(
        min_length=3,
        max_length=20,
        pattern=r"^[A-Z0-9]+$",
    )
    price_usd: Decimal = Field(
        gt=Decimal("0"),
    )


class MarketPriceResponse(BaseModel):
    symbol: str
    price_usd: Decimal
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SimulationSummaryResponse(BaseModel):
    account_id: int
    balance: BalanceResponse
    positions: list[PositionResponse]
    recent_trades: list[TradeHistoryResponse]
    market_prices: list[MarketPriceResponse]


class SimulationResetResponse(BaseModel):
    account_id: int
    message: str
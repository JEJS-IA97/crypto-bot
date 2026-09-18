from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    BalanceResponse,
    MarketPriceResponse,
    MarketPriceUpdateRequest,
    PositionResponse,
    SimulationAccountCreate,
    SimulationAccountResponse,
    SimulationOrderRequest,
    SimulationResetResponse,
    SimulationSummaryResponse,
    TradeHistoryResponse,
    TradeResponse,
)
from app.services.bot_engine import evaluate_market
from app.services.exchange_balance_service import (
    list_exchange_balances,
    set_exchange_balance,
)
from app.services.exchange_market_service import (
    fetch_exchange_quotes,
)
from app.services.execution_price_service import (
    select_best_execution,
)
from app.services.market_sync_service import (
    synchronize_market_prices,
)
from app.services.risk_service import RiskConfig
from app.services.simulation_service import (
    create_simulation_account,
    execute_order,
    get_accounts,
    get_balance,
    get_market_prices,
    get_positions,
    get_summary,
    get_trades,
    reset_simulation_account,
    update_market_price,
)
from app.services.trade_opportunity_service import (
    find_best_opportunity,
)


router = APIRouter(
    prefix="/simulation",
    tags=["Simulation"],
)


@router.get(
    "/accounts",
    response_model=list[SimulationAccountResponse],
)
def accounts(
    db: Session = Depends(get_db),
) -> list[SimulationAccountResponse]:
    return get_accounts(db)


@router.post(
    "/accounts",
    response_model=SimulationAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    data: SimulationAccountCreate,
    db: Session = Depends(get_db),
) -> SimulationAccountResponse:
    return create_simulation_account(db, data)


@router.get(
    "/accounts/{account_id}/balance",
    response_model=BalanceResponse,
)
def account_balance(
    account_id: int,
    db: Session = Depends(get_db),
) -> BalanceResponse:
    return get_balance(db, account_id)


@router.get(
    "/accounts/{account_id}/positions",
    response_model=list[PositionResponse],
)
def account_positions(
    account_id: int,
    db: Session = Depends(get_db),
) -> list[PositionResponse]:
    return get_positions(db, account_id)


@router.get(
    "/accounts/{account_id}/trades",
    response_model=list[TradeHistoryResponse],
)
def account_trades(
    account_id: int,
    db: Session = Depends(get_db),
) -> list[TradeHistoryResponse]:
    return get_trades(db, account_id)


@router.post(
    "/accounts/{account_id}/orders",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    account_id: int,
    order: SimulationOrderRequest,
    db: Session = Depends(get_db),
) -> TradeResponse:
    return execute_order(
        db,
        account_id,
        order,
    )


@router.get(
    "/accounts/{account_id}/summary",
    response_model=SimulationSummaryResponse,
)
def account_summary(
    account_id: int,
    db: Session = Depends(get_db),
) -> SimulationSummaryResponse:
    return get_summary(db, account_id)


@router.post(
    "/accounts/{account_id}/reset",
    response_model=SimulationResetResponse,
)
def reset_account(
    account_id: int,
    db: Session = Depends(get_db),
) -> SimulationResetResponse:
    return reset_simulation_account(
        db,
        account_id,
    )


@router.put(
    "/market-prices",
    response_model=MarketPriceResponse,
)
def update_price(
    data: MarketPriceUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketPriceResponse:
    return update_market_price(
        db,
        data,
    )


@router.get(
    "/market-prices",
    response_model=list[MarketPriceResponse],
)
def market_prices(
    db: Session = Depends(get_db),
) -> list[MarketPriceResponse]:
    return get_market_prices(db)


@router.post(
    "/market-prices/synchronize",
    response_model=list[MarketPriceResponse],
)
async def synchronize_prices(
    db: Session = Depends(get_db),
) -> list[MarketPriceResponse]:
    return synchronize_market_prices(db)


@router.get("/market-prices/aggregate")
async def aggregate_market_prices(
    symbol: str = "BTCUSDT",
):
    quotes = fetch_exchange_quotes(symbol)

    return select_best_execution(quotes)


@router.get("/market-prices/opportunity")
async def market_opportunity(
    symbol: str = "BTCUSDT",
    capital_usd: Decimal = Decimal("20"),
    min_profit_usd: Decimal = Decimal("0.05"),
    min_profit_percent: Decimal = Decimal("0.10"),
):
    quotes = fetch_exchange_quotes(symbol)

    executions = select_best_execution(quotes)

    opportunity = find_best_opportunity(
        executions=executions,
        capital_usd=capital_usd,
        min_profit_usd=min_profit_usd,
        min_profit_percent=min_profit_percent,
    )

    return {
        "symbol": symbol,
        "capital_usd": capital_usd,
        "market": executions,
        "opportunity": opportunity,
    }


@router.get("/bot/evaluate")
async def evaluate_bot(
    account_id: int = 1,
    symbol: str = "BTCUSDT",
    capital_usd: Decimal = Decimal("5"),
    db: Session = Depends(get_db),
):
    config = RiskConfig(
        max_trade_usd=Decimal("5"),
        min_profit_usd=Decimal("0.05"),
        min_profit_percent=Decimal("0.10"),
        min_liquidity_usd=Decimal("10"),
        max_position_usd=Decimal("20"),
    )

    return evaluate_market(
        db=db,
        account_id=account_id,
        symbol=symbol,
        capital_usd=capital_usd,
        risk_config=config,
    )


class ExchangeBalanceUpdateRequest(BaseModel):
    exchange: str
    asset: str
    available: Decimal
    locked: Decimal = Decimal("0")


@router.get(
    "/accounts/{account_id}/exchange-balances"
)
async def account_exchange_balances(
    account_id: int,
    db: Session = Depends(get_db),
):
    return list_exchange_balances(
        db=db,
        account_id=account_id,
    )


@router.put(
    "/accounts/{account_id}/exchange-balances"
)
async def update_exchange_balance(
    account_id: int,
    payload: ExchangeBalanceUpdateRequest,
    db: Session = Depends(get_db),
):
    return set_exchange_balance(
        db=db,
        account_id=account_id,
        exchange=payload.exchange,
        asset=payload.asset,
        available=payload.available,
        locked=payload.locked,
    )
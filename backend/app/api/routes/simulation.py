from fastapi import APIRouter, Depends, status
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
    get_simulation_accounts,
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
    "/accounts",
    response_model=list[SimulationAccountResponse],
)
def accounts(
    db: Session = Depends(get_db),
) -> list[SimulationAccountResponse]:
    return get_simulation_accounts(db)
    

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
    return execute_order(db, account_id, order)


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
    return reset_simulation_account(db, account_id)


@router.put(
    "/market-prices",
    response_model=MarketPriceResponse,
)
def update_price(
    data: MarketPriceUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketPriceResponse:
    return update_market_price(db, data)


@router.get(
    "/market-prices",
    response_model=list[MarketPriceResponse],
)
def market_prices(
    db: Session = Depends(get_db),
) -> list[MarketPriceResponse]:
    return get_market_prices(db)
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    SimulationAccount,
    SimulationArbitrage,
    SimulationBalance,
    SimulationMarketPrice,
    SimulationPosition,
    SimulationTrade,
    TradeSide,
)
from app.schemas import (
    MarketPriceUpdateRequest,
    SimulationAccountCreate,
    SimulationOrderRequest,
)


MONEY_PLACES = Decimal("0.00000001")
QUANTITY_PLACES = Decimal("0.000000000001")

SIMULATION_FEE_RATE = Decimal(
    str(settings.simulation_fee_rate)
)


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def quantity_value(value: Decimal) -> Decimal:
    return Decimal(value).quantize(
        QUANTITY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def get_account(
    db: Session,
    account_id: int,
) -> SimulationAccount:
    account = db.get(
        SimulationAccount,
        account_id,
    )

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation account not found",
        )

    return account


def get_balance_record(
    db: Session,
    account_id: int,
) -> SimulationBalance:
    balance = db.scalar(
        select(SimulationBalance).where(
            SimulationBalance.account_id
            == account_id
        )
    )

    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation balance not found",
        )

    return balance


def create_simulation_account(
    db: Session,
    data: SimulationAccountCreate,
) -> SimulationAccount:
    account = SimulationAccount(
        name=data.name,
    )

    db.add(account)
    db.flush()

    balance = SimulationBalance(
        account_id=account.id,
        available_usd=money(
            data.initial_balance_usd
        ),
        invested_usd=Decimal("0"),
        realized_pnl_usd=Decimal("0"),
    )

    db.add(balance)
    db.commit()
    db.refresh(account)

    return account


def get_positions(
    db: Session,
    account_id: int,
) -> list[dict]:
    get_account(
        db,
        account_id,
    )

    positions = db.scalars(
        select(SimulationPosition)
        .where(
            SimulationPosition.account_id
            == account_id
        )
        .order_by(
            SimulationPosition.symbol
        )
    ).all()

    result = []

    for position in positions:
        market_price = db.scalar(
            select(SimulationMarketPrice).where(
                SimulationMarketPrice.symbol
                == position.symbol
            )
        )

        current_price = None
        market_value_usd = None
        unrealized_pnl_usd = None

        if market_price is not None:
            current_price = market_price.price_usd

            market_value_usd = money(
                position.quantity
                * current_price
            )

            cost_value = money(
                position.quantity
                * position.average_entry_price
            )

            unrealized_pnl_usd = money(
                market_value_usd
                - cost_value
            )

        result.append(
            {
                "symbol": position.symbol,
                "quantity": quantity_value(
                    position.quantity
                ),
                "average_entry_price": (
                    position.average_entry_price
                ),
                "current_price": current_price,
                "market_value_usd": market_value_usd,
                "unrealized_pnl_usd": (
                    unrealized_pnl_usd
                ),
            }
        )

    return result


def get_accounts(
    db: Session,
) -> list[SimulationAccount]:
    return list(
        db.scalars(
            select(
                SimulationAccount
            ).order_by(
                SimulationAccount.created_at
            )
        ).all()
    )


def get_balance(
    db: Session,
    account_id: int,
) -> dict:
    account = get_account(
        db,
        account_id,
    )

    balance = get_balance_record(
        db,
        account_id,
    )

    positions = get_positions(
        db,
        account_id,
    )

    market_value_usd = Decimal("0")
    unrealized_pnl_usd = Decimal("0")

    for position in positions:
        if position[
            "market_value_usd"
        ] is not None:
            market_value_usd += position[
                "market_value_usd"
            ]

        if position[
            "unrealized_pnl_usd"
        ] is not None:
            unrealized_pnl_usd += position[
                "unrealized_pnl_usd"
            ]

    market_value_usd = money(
        market_value_usd
    )

    unrealized_pnl_usd = money(
        unrealized_pnl_usd
    )

    total_balance_usd = money(
        balance.available_usd
        + market_value_usd
    )

    return {
        "account_id": account.id,
        "available_usd": money(
            balance.available_usd
        ),
        "invested_usd": money(
            balance.invested_usd
        ),
        "market_value_usd": (
            market_value_usd
        ),
        "realized_pnl_usd": money(
            balance.realized_pnl_usd
        ),
        "unrealized_pnl_usd": (
            unrealized_pnl_usd
        ),
        "total_balance_usd": (
            total_balance_usd
        ),
    }


def get_trades(
    db: Session,
    account_id: int,
) -> list[SimulationTrade]:
    get_account(
        db,
        account_id,
    )

    return list(
        db.scalars(
            select(SimulationTrade)
            .where(
                SimulationTrade.account_id
                == account_id
            )
            .order_by(
                SimulationTrade.executed_at.desc()
            )
        ).all()
    )


def get_market_prices(
    db: Session,
) -> list[SimulationMarketPrice]:
    return list(
        db.scalars(
            select(
                SimulationMarketPrice
            ).order_by(
                SimulationMarketPrice.symbol
            )
        ).all()
    )


def update_market_price(
    db: Session,
    data: MarketPriceUpdateRequest,
) -> SimulationMarketPrice:
    symbol = data.symbol.upper()
    price = money(
        data.price_usd
    )

    market_price = db.scalar(
        select(
            SimulationMarketPrice
        ).where(
            SimulationMarketPrice.symbol
            == symbol
        )
    )

    if market_price is None:
        market_price = SimulationMarketPrice(
            symbol=symbol,
            price_usd=price,
        )

        db.add(market_price)

    else:
        market_price.price_usd = price

    db.commit()
    db.refresh(market_price)

    return market_price


def get_market_price(
    db: Session,
    symbol: str,
) -> SimulationMarketPrice | None:
    return db.scalar(
        select(
            SimulationMarketPrice
        ).where(
            SimulationMarketPrice.symbol
            == symbol
        )
    )


def get_position(
    db: Session,
    account_id: int,
    symbol: str,
) -> SimulationPosition | None:
    return db.scalar(
        select(
            SimulationPosition
        ).where(
            SimulationPosition.account_id
            == account_id,
            SimulationPosition.symbol
            == symbol,
        )
    )


def execute_order(
    db: Session,
    account_id: int,
    order: SimulationOrderRequest,
) -> SimulationTrade:
    account = get_account(
        db,
        account_id,
    )

    balance = get_balance_record(
        db,
        account_id,
    )

    symbol = order.symbol.upper()
    side = order.side

    quantity = quantity_value(
        order.quantity
    )

    price = money(
        order.price
    )

    gross_total = money(
        quantity * price
    )

    fee_usd = money(
        gross_total
        * SIMULATION_FEE_RATE
    )

    total_cost = money(
        gross_total + fee_usd
    )

    position = get_position(
        db,
        account_id,
        symbol,
    )

    if side == TradeSide.BUY:
        if (
            balance.available_usd
            < total_cost
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Insufficient available "
                    "balance. "
                    f"Required: "
                    f"{total_cost} USD. "
                    f"Available: "
                    f"{balance.available_usd} USD."
                ),
            )

        if position is None:
            position = SimulationPosition(
                account_id=account_id,
                symbol=symbol,
                quantity=quantity,
                average_entry_price=price,
            )

            db.add(position)

        else:
            previous_quantity = (
                position.quantity
            )

            previous_cost = (
                previous_quantity
                * position.average_entry_price
            )

            new_cost = (
                quantity * price
            )

            new_quantity = (
                previous_quantity
                + quantity
            )

            position.quantity = (
                quantity_value(
                    new_quantity
                )
            )

            position.average_entry_price = (
                (
                    previous_cost
                    + new_cost
                )
                / new_quantity
            )

        balance.available_usd = money(
            balance.available_usd
            - total_cost
        )

        balance.invested_usd = money(
            balance.invested_usd
            + gross_total
        )

        realized_pnl_usd = Decimal("0")

    else:
        if position is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    f"No open position "
                    f"for {symbol}."
                ),
            )

        if quantity > position.quantity:
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Insufficient position "
                    "quantity. "
                    f"Available: "
                    f"{position.quantity}. "
                    f"Requested: {quantity}."
                ),
            )

        cost_basis = (
            quantity
            * position.average_entry_price
        )

        realized_pnl_usd = money(
            gross_total
            - cost_basis
            - fee_usd
        )

        balance.available_usd = money(
            balance.available_usd
            + gross_total
            - fee_usd
        )

        balance.invested_usd = money(
            balance.invested_usd
            - cost_basis
        )

        balance.realized_pnl_usd = money(
            balance.realized_pnl_usd
            + realized_pnl_usd
        )

        remaining_quantity = (
            quantity_value(
                position.quantity
                - quantity
            )
        )

        if remaining_quantity <= Decimal("0"):
            db.delete(position)

        else:
            position.quantity = (
                remaining_quantity
            )

    trade = SimulationTrade(
        account_id=account.id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        total_usd=gross_total,
        fee_usd=fee_usd,
        realized_pnl_usd=realized_pnl_usd,
    )

    db.add(trade)
    db.commit()
    db.refresh(trade)

    return trade


def get_summary(
    db: Session,
    account_id: int,
) -> dict:
    balance = get_balance(
        db,
        account_id,
    )

    positions = get_positions(
        db,
        account_id,
    )

    trades = get_trades(
        db,
        account_id,
    )

    market_prices = get_market_prices(
        db
    )

    return {
        "account_id": account_id,
        "balance": balance,
        "positions": positions,
        "recent_trades": trades[:10],
        "market_prices": market_prices,
    }


def reset_simulation_account(
    db: Session,
    account_id: int,
) -> dict:
    account = get_account(
        db,
        account_id,
    )

    balance = get_balance_record(
        db,
        account_id,
    )

    positions = db.scalars(
        select(SimulationPosition).where(
            SimulationPosition.account_id
            == account_id
        )
    ).all()

    trades = db.scalars(
        select(SimulationTrade).where(
            SimulationTrade.account_id
            == account_id
        )
    ).all()

    arbitrages = db.scalars(
        select(SimulationArbitrage).where(
            SimulationArbitrage.account_id
            == account_id
        )
    ).all()

    for position in positions:
        db.delete(position)

    for trade in trades:
        db.delete(trade)

    for arbitrage in arbitrages:
        db.delete(arbitrage)

    balance.available_usd = money(
        settings.simulation_initial_balance
    )

    balance.invested_usd = Decimal("0")
    balance.realized_pnl_usd = Decimal("0")

    db.commit()

    return {
        "account_id": account.id,
        "message": (
            "Simulation account reset successfully"
        ),
    }


def get_simulation_accounts(
    db: Session,
) -> list[SimulationAccount]:
    return list(
        db.scalars(
            select(
                SimulationAccount
            ).order_by(
                SimulationAccount.created_at
            )
        ).all()
    )
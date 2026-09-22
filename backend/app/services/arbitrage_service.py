from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    SimulationArbitrage,
    SimulationBalance,
)
from app.services.simulation_service import get_account


MONEY_PLACES = Decimal("0.00000001")
QUANTITY_PLACES = Decimal("0.000000000001")


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


def get_balance_record(
    db: Session,
    account_id: int,
) -> SimulationBalance:
    balance = db.scalar(
        select(SimulationBalance).where(
            SimulationBalance.account_id == account_id
        )
    )

    if balance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulation balance not found",
        )

    return balance


def get_arbitrages(
    db: Session,
    account_id: int,
) -> list[SimulationArbitrage]:
    get_account(
        db,
        account_id,
    )

    return list(
        db.scalars(
            select(SimulationArbitrage)
            .where(
                SimulationArbitrage.account_id
                == account_id
            )
            .order_by(
                SimulationArbitrage.executed_at.desc()
            )
        ).all()
    )


def _find_execution(
    executions: dict,
    options_key: str,
    exchange: str,
    symbol: str,
) -> dict:
    options = executions.get(
        options_key,
        [],
    )

    for execution in options:
        if (
            execution.get("exchange") == exchange
            and execution.get("symbol") == symbol
        ):
            return execution

    raise ValueError(
        (
            f"Execution snapshot not found for "
            f"{exchange} {symbol}."
        )
    )


def execute_arbitrage(
    db: Session,
    account_id: int,
    opportunity: dict,
    executions: dict,
) -> SimulationArbitrage:
    if opportunity.get("status") != "TRADE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The opportunity is not approved "
                "for execution."
            ),
        )

    buy_exchange = opportunity[
        "buy_exchange"
    ]

    sell_exchange = opportunity[
        "sell_exchange"
    ]

    buy_symbol = opportunity[
        "buy_symbol"
    ]

    sell_symbol = opportunity[
        "sell_symbol"
    ]

    if buy_exchange == sell_exchange:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Arbitrage requires different "
                "buy and sell exchanges."
            ),
        )

    buy_execution = _find_execution(
        executions=executions,
        options_key="buy_options",
        exchange=buy_exchange,
        symbol=buy_symbol,
    )

    sell_execution = _find_execution(
        executions=executions,
        options_key="sell_options",
        exchange=sell_exchange,
        symbol=sell_symbol,
    )

    quantity = quantity_value(
        Decimal(str(opportunity["quantity"]))
    )

    buy_price = Decimal(
        str(buy_execution["price_usd"])
    )

    sell_price = Decimal(
        str(sell_execution["price_usd"])
    )

    buy_fee_rate = Decimal(
        str(buy_execution["fee_rate"])
    )

    sell_fee_rate = Decimal(
        str(sell_execution["fee_rate"])
    )

    buy_total_usd = money(
        quantity * buy_price
    )

    buy_fee_usd = money(
        buy_total_usd * buy_fee_rate
    )

    buy_cost_usd = money(
        buy_total_usd + buy_fee_usd
    )

    sell_total_usd = money(
        quantity * sell_price
    )

    sell_fee_usd = money(
        sell_total_usd * sell_fee_rate
    )

    sell_proceeds_usd = money(
        sell_total_usd - sell_fee_usd
    )

    net_profit_usd = money(
        sell_proceeds_usd - buy_cost_usd
    )

    balance = get_balance_record(
        db,
        account_id,
    )

    if balance.available_usd < buy_cost_usd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Insufficient simulation balance. "
                f"Required: {buy_cost_usd} USD. "
                f"Available: "
                f"{balance.available_usd} USD."
            ),
        )

    try:
        balance.available_usd = money(
            balance.available_usd
            - buy_cost_usd
            + sell_proceeds_usd
        )

        balance.realized_pnl_usd = money(
            balance.realized_pnl_usd
            + net_profit_usd
        )

        arbitrage = SimulationArbitrage(
            account_id=account_id,
            symbol=opportunity["symbol"],
            base_asset=opportunity[
                "base_asset"
            ],
            quote_currency=opportunity[
                "buy_quote_currency"
            ],
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            quantity=quantity,
            buy_price=buy_price,
            sell_price=sell_price,
            buy_total_usd=buy_total_usd,
            buy_fee_usd=buy_fee_usd,
            sell_total_usd=sell_total_usd,
            sell_fee_usd=sell_fee_usd,
            net_profit_usd=net_profit_usd,
        )

        db.add(arbitrage)

        db.commit()
        db.refresh(arbitrage)

        return arbitrage

    except Exception:
        db.rollback()
        raise
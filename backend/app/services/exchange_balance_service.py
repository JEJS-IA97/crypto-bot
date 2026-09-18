from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SimulationExchangeBalance


def get_exchange_balance(
    db: Session,
    account_id: int,
    exchange: str,
    asset: str,
) -> SimulationExchangeBalance | None:
    return db.scalar(
        select(SimulationExchangeBalance).where(
            SimulationExchangeBalance.account_id == account_id,
            SimulationExchangeBalance.exchange == exchange,
            SimulationExchangeBalance.asset == asset.upper(),
        )
    )


def get_or_create_exchange_balance(
    db: Session,
    account_id: int,
    exchange: str,
    asset: str,
    initial_available: Decimal = Decimal("0"),
) -> SimulationExchangeBalance:
    normalized_exchange = exchange.lower()
    normalized_asset = asset.upper()

    balance = get_exchange_balance(
        db=db,
        account_id=account_id,
        exchange=normalized_exchange,
        asset=normalized_asset,
    )

    if balance:
        return balance

    balance = SimulationExchangeBalance(
        account_id=account_id,
        exchange=normalized_exchange,
        asset=normalized_asset,
        available=initial_available,
        locked=Decimal("0"),
    )

    db.add(balance)

    return balance


def set_exchange_balance(
    db: Session,
    account_id: int,
    exchange: str,
    asset: str,
    available: Decimal,
    locked: Decimal = Decimal("0"),
) -> SimulationExchangeBalance:
    if available < 0:
        raise ValueError(
            "Available balance cannot be negative."
        )

    if locked < 0:
        raise ValueError(
            "Locked balance cannot be negative."
        )

    balance = get_or_create_exchange_balance(
        db=db,
        account_id=account_id,
        exchange=exchange,
        asset=asset,
    )

    balance.available = available
    balance.locked = locked

    db.commit()
    db.refresh(balance)

    return balance


def adjust_available_balance(
    db: Session,
    balance: SimulationExchangeBalance,
    amount: Decimal,
) -> SimulationExchangeBalance:
    new_available = balance.available + amount

    if new_available < 0:
        raise ValueError(
            (
                f"Insufficient {balance.asset} balance "
                f"on {balance.exchange}."
            )
        )

    balance.available = new_available

    db.commit()
    db.refresh(balance)

    return balance


def list_exchange_balances(
    db: Session,
    account_id: int,
) -> list[SimulationExchangeBalance]:
    return list(
        db.scalars(
            select(SimulationExchangeBalance)
            .where(
                SimulationExchangeBalance.account_id
                == account_id
            )
            .order_by(
                SimulationExchangeBalance.exchange,
                SimulationExchangeBalance.asset,
            )
        ).all()
    )
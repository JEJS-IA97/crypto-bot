from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SimulationBalance


def get_available_balance(
    db: Session,
    account_id: int,
) -> Decimal:
    balance = db.scalar(
        select(SimulationBalance).where(
            SimulationBalance.account_id == account_id
        )
    )

    if balance is None:
        return Decimal("0")

    return Decimal(str(balance.available_usd))


def validate_arbitrage_inventory(
    db: Session,
    account_id: int,
    opportunity: dict,
) -> dict:
    required_capital = Decimal(
        str(opportunity["capital_used_usd"])
    )

    available_balance = get_available_balance(
        db=db,
        account_id=account_id,
    )

    if available_balance < required_capital:
        return {
            "approved": False,
            "reason": "Insufficient simulation balance.",
            "required_balance_usd": required_capital,
            "available_balance_usd": available_balance,
        }

    return {
        "approved": True,
        "reason": (
            "Sufficient simulation balance "
            "available."
        ),
        "required_balance_usd": required_capital,
        "available_balance_usd": available_balance,
    }
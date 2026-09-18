from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SimulationExchangeBalance


def get_exchange_asset_balance(
    db: Session,
    account_id: int,
    exchange: str,
    asset: str,
) -> SimulationExchangeBalance | None:
    return db.scalar(
        select(SimulationExchangeBalance).where(
            SimulationExchangeBalance.account_id == account_id,
            SimulationExchangeBalance.exchange == exchange.lower(),
            SimulationExchangeBalance.asset == asset.upper(),
        )
    )


def get_available_balance(
    db: Session,
    account_id: int,
    exchange: str,
    asset: str,
) -> Decimal:
    balance = get_exchange_asset_balance(
        db=db,
        account_id=account_id,
        exchange=exchange,
        asset=asset,
    )

    if balance is None:
        return Decimal("0")

    return Decimal(str(balance.available))


def validate_arbitrage_inventory(
    db: Session,
    account_id: int,
    opportunity: dict,
) -> dict:
    buy_exchange = opportunity["buy_exchange"]
    sell_exchange = opportunity["sell_exchange"]

    buy_symbol = opportunity["buy_symbol"]
    sell_symbol = opportunity["sell_symbol"]

    buy_quote_currency = opportunity[
        "buy_quote_currency"
    ]

    sell_quote_currency = opportunity[
        "sell_quote_currency"
    ]

    quantity = Decimal(
        str(opportunity["quantity"])
    )

    capital_used_usd = Decimal(
        str(opportunity["capital_used_usd"])
    )

    if buy_quote_currency != sell_quote_currency:
        return {
            "approved": False,
            "reason": (
                "Buy and sell quote currencies do not match."
            ),
        }

    buy_base_asset = _extract_base_asset(
        buy_symbol,
        buy_quote_currency,
    )

    sell_base_asset = _extract_base_asset(
        sell_symbol,
        sell_quote_currency,
    )

    if buy_base_asset != sell_base_asset:
        return {
            "approved": False,
            "reason": (
                "Buy and sell base assets do not match."
            ),
        }

    buy_quote_balance = get_available_balance(
        db=db,
        account_id=account_id,
        exchange=buy_exchange,
        asset=buy_quote_currency,
    )

    sell_base_balance = get_available_balance(
        db=db,
        account_id=account_id,
        exchange=sell_exchange,
        asset=sell_base_asset,
    )

    if buy_quote_balance < capital_used_usd:
        return {
            "approved": False,
            "reason": (
                f"Insufficient {buy_quote_currency} "
                f"on {buy_exchange}."
            ),
            "required_quote": capital_used_usd,
            "available_quote": buy_quote_balance,
        }

    if sell_base_balance < quantity:
        return {
            "approved": False,
            "reason": (
                f"Insufficient {sell_base_asset} "
                f"on {sell_exchange}."
            ),
            "required_base": quantity,
            "available_base": sell_base_balance,
        }

    return {
        "approved": True,
        "reason": (
            "Sufficient inventory available on "
            "both exchanges."
        ),
        "buy_exchange": buy_exchange,
        "sell_exchange": sell_exchange,
        "quote_asset": buy_quote_currency,
        "base_asset": buy_base_asset,
        "required_quote": capital_used_usd,
        "available_quote": buy_quote_balance,
        "required_base": quantity,
        "available_base": sell_base_balance,
    }


def _extract_base_asset(
    symbol: str,
    quote_currency: str,
) -> str:
    normalized_symbol = symbol.upper()
    normalized_quote = quote_currency.upper()

    if not normalized_symbol.endswith(normalized_quote):
        raise ValueError(
            (
                f"Symbol {symbol} does not end with "
                f"quote currency {quote_currency}."
            )
        )

    base_asset = normalized_symbol[
        : -len(normalized_quote)
    ]

    if not base_asset:
        raise ValueError(
            f"Unable to extract base asset from {symbol}."
        )

    return base_asset
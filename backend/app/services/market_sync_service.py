from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SimulationMarketPrice
from app.services.market_data_service import fetch_market_prices


DEFAULT_MARKET_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
]


def synchronize_market_prices(
    db: Session,
    symbols: list[str] | None = None,
) -> list[SimulationMarketPrice]:
    symbols_to_sync = symbols or DEFAULT_MARKET_SYMBOLS

    market_prices = fetch_market_prices(symbols_to_sync)
    synchronized_prices = []

    for market_price in market_prices:
        symbol = market_price["symbol"]
        price_usd = market_price["price_usd"]

        existing_price = db.scalar(
            select(SimulationMarketPrice).where(
                SimulationMarketPrice.symbol == symbol
            )
        )

        if existing_price:
            existing_price.price_usd = price_usd
            existing_price.updated_at = datetime.now(timezone.utc)
            synchronized_prices.append(existing_price)
            continue

        new_price = SimulationMarketPrice(
            symbol=symbol,
            price_usd=price_usd,
            updated_at=datetime.now(timezone.utc),
        )

        db.add(new_price)
        synchronized_prices.append(new_price)

    db.commit()

    for price in synchronized_prices:
        db.refresh(price)

    return synchronized_prices
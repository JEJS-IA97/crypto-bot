from decimal import Decimal
import json

import httpx

BINANCE_MARKET_URL = "https://data-api.binance.vision/api/v3/ticker/price"


def fetch_market_prices(
    symbols: list[str],
) -> list[dict]:
    """
    Obtiene los precios actuales de Binance para los símbolos indicados.
    """

    if not symbols:
        return []

    normalized_symbols = [
        symbol.strip().upper()
        for symbol in symbols
        if symbol and symbol.strip()
    ]

    if not normalized_symbols:
        return []

    # Binance espera el parámetro `symbols` como JSON.
    # separators elimina los espacios y produce:
    # ["BTCUSDT","ETHUSDT","SOLUSDT"]
    symbols_json = json.dumps(
        normalized_symbols,
        separators=(",", ":"),
    )

    params = {
        "symbols": symbols_json,
    }

    response = httpx.get(
        BINANCE_MARKET_URL,
        params=params,
        timeout=10.0,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Binance returned {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if isinstance(data, dict):
        data = [data]

    prices = []

    for item in data:
        symbol = item.get("symbol")
        price = item.get("price")

        if not symbol or price is None:
            continue

        prices.append(
            {
                "symbol": symbol,
                "price_usd": Decimal(str(price)),
            }
        )

    return prices
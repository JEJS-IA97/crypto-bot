from decimal import Decimal
from typing import Any

import httpx


BINANCE_BOOK_TICKER_URL = (
    "https://data-api.binance.vision/api/v3/ticker/bookTicker"
)

BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"

KRAKEN_TICKER_URL = "https://api.kraken.com/0/public/Ticker"

COINBASE_TICKER_URL = (
    "https://api.exchange.coinbase.com/products/{product_id}/ticker"
)


EXCHANGE_SYMBOLS = {
    "binance": "BTCUSDT",
    "bybit": "BTCUSDT",
    "kraken": "XBTUSDT",
    "coinbase": "BTC-USD",
}


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    return Decimal(str(value))


def _build_quote(
    exchange: str,
    symbol: str,
    quote_currency: str,
    bid_price: Any,
    bid_quantity: Any,
    ask_price: Any,
    ask_quantity: Any,
    last_price: Any,
    volume_24h: Any = None,
) -> dict:
    return {
        "exchange": exchange,
        "symbol": symbol,
        "quote_currency": quote_currency,
        "bid_price": _decimal(bid_price),
        "bid_quantity": _decimal(bid_quantity),
        "ask_price": _decimal(ask_price),
        "ask_quantity": _decimal(ask_quantity),
        "last_price": _decimal(last_price),
        "volume_24h": _decimal(volume_24h),
    }


def fetch_binance_quote(
    symbol: str = "BTCUSDT",
) -> dict:
    response = httpx.get(
        BINANCE_BOOK_TICKER_URL,
        params={"symbol": symbol},
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    return _build_quote(
        exchange="binance",
        symbol=symbol,
        quote_currency="USDT",
        bid_price=data.get("bidPrice"),
        bid_quantity=data.get("bidQty"),
        ask_price=data.get("askPrice"),
        ask_quantity=data.get("askQty"),
        last_price=None,
    )


def fetch_bybit_quote(
    symbol: str = "BTCUSDT",
) -> dict:
    response = httpx.get(
        BYBIT_TICKER_URL,
        params={
            "category": "spot",
            "symbol": symbol,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    result = data.get("result", {})
    ticker_list = result.get("list", [])

    if not ticker_list:
        raise RuntimeError(
            f"Bybit returned no ticker for {symbol}"
        )

    ticker = ticker_list[0]

    return _build_quote(
        exchange="bybit",
        symbol=symbol,
        quote_currency="USDT",
        bid_price=ticker.get("bid1Price"),
        bid_quantity=ticker.get("bid1Size"),
        ask_price=ticker.get("ask1Price"),
        ask_quantity=ticker.get("ask1Size"),
        last_price=ticker.get("lastPrice"),
        volume_24h=ticker.get("volume24h"),
    )


def fetch_kraken_quote(
    symbol: str = "XBTUSDT",
) -> dict:
    response = httpx.get(
        KRAKEN_TICKER_URL,
        params={
            "pair": symbol,
            "assetVersion": "1",
        },
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    errors = data.get("error", [])

    if errors:
        raise RuntimeError(
            f"Kraken returned errors: {errors}"
        )

    result = data.get("result", {})

    if not result:
        raise RuntimeError(
            f"Kraken returned no ticker for {symbol}"
        )

    ticker = next(iter(result.values()))

    return _build_quote(
        exchange="kraken",
        symbol="BTCUSDT",
        quote_currency="USDT",
        bid_price=ticker["b"][0],
        bid_quantity=ticker["b"][1],
        ask_price=ticker["a"][0],
        ask_quantity=ticker["a"][1],
        last_price=ticker["c"][0],
        volume_24h=ticker["v"][1],
    )


def fetch_coinbase_quote(
    product_id: str = "BTC-USD",
) -> dict:
    url = COINBASE_TICKER_URL.format(
        product_id=product_id,
    )

    response = httpx.get(
        url,
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    return _build_quote(
        exchange="coinbase",
        symbol="BTCUSD",
        quote_currency="USD",
        bid_price=data.get("bid"),
        bid_quantity=None,
        ask_price=data.get("ask"),
        ask_quantity=None,
        last_price=data.get("price"),
        volume_24h=data.get("volume"),
    )


def fetch_exchange_quotes(
    symbol: str = "BTCUSDT",
) -> list[dict]:
    quotes = []

    exchange_calls = [
        (
            "binance",
            lambda: fetch_binance_quote(symbol),
        ),
        (
            "bybit",
            lambda: fetch_bybit_quote(symbol),
        ),
        (
            "kraken",
            lambda: fetch_kraken_quote("XBTUSDT"),
        ),
        (
            "coinbase",
            lambda: fetch_coinbase_quote("BTC-USD"),
        ),
    ]

    for exchange, fetcher in exchange_calls:
        try:
            quote = fetcher()
            quote["status"] = "ok"
            quotes.append(quote)
        except (httpx.HTTPError, RuntimeError, KeyError) as exc:
            quotes.append(
                {
                    "exchange": exchange,
                    "symbol": symbol,
                    "status": "error",
                    "error": str(exc),
                }
            )

    return quotes


def _price_in_usd(
    price: Decimal,
    quote_currency: str,
) -> Decimal:
    """
    Para la simulación inicial tratamos USDT ≈ USD.

    Posteriormente podemos añadir una fuente USD/USDT
    para eliminar esta aproximación.
    """

    if quote_currency in {"USD", "USDT"}:
        return price

    raise ValueError(
        f"Unsupported quote currency: {quote_currency}"
    )


def find_best_market(
    quotes: list[dict],
) -> dict:
    valid_quotes = [
        quote
        for quote in quotes
        if quote.get("status") == "ok"
    ]

    if not valid_quotes:
        raise RuntimeError(
            "No exchange returned a valid market quote."
        )

    buy_candidates = [
        quote
        for quote in valid_quotes
        if quote.get("ask_price") is not None
    ]

    sell_candidates = [
        quote
        for quote in valid_quotes
        if quote.get("bid_price") is not None
    ]

    best_buy = min(
        buy_candidates,
        key=lambda quote: _price_in_usd(
            quote["ask_price"],
            quote["quote_currency"],
        ),
        default=None,
    )

    best_sell = max(
        sell_candidates,
        key=lambda quote: _price_in_usd(
            quote["bid_price"],
            quote["quote_currency"],
        ),
        default=None,
    )

    return {
        "best_buy": best_buy,
        "best_sell": best_sell,
        "quotes": quotes,
    }
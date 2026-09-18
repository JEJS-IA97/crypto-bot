from decimal import Decimal


DEFAULT_TAKER_FEES = {
    "binance": Decimal("0.0010"),
    "bybit": Decimal("0.0010"),
    "kraken": Decimal("0.0080"),
    "coinbase": Decimal("0.0060"),
}


DEFAULT_USDT_USD_RATE = Decimal("1.0")


def calculate_buy_execution(
    quote: dict,
    usd_usdt_rate: Decimal = DEFAULT_USDT_USD_RATE,
) -> dict:
    ask_price = quote.get("ask_price")

    if ask_price is None:
        raise ValueError(
            f"No ask price available for {quote['exchange']}"
        )

    exchange = quote["exchange"]
    quote_currency = quote["quote_currency"]

    fee_rate = DEFAULT_TAKER_FEES.get(
        exchange,
        Decimal("0"),
    )

    if quote_currency == "USD":
        price_usd = ask_price
    elif quote_currency == "USDT":
        price_usd = ask_price * usd_usdt_rate
    else:
        raise ValueError(
            f"Unsupported quote currency: {quote_currency}"
        )

    fee_usd = price_usd * fee_rate
    effective_price_usd = price_usd + fee_usd

    return {
        "exchange": exchange,
        "symbol": quote["symbol"],
        "side": "BUY",
        "quote_currency": quote_currency,
        "market_price": ask_price,
        "price_usd": price_usd,
        "fee_rate": fee_rate,
        "fee_usd": fee_usd,
        "effective_price_usd": effective_price_usd,
        "ask_quantity": quote.get("ask_quantity"),
    }


def calculate_sell_execution(
    quote: dict,
    usd_usdt_rate: Decimal = DEFAULT_USDT_USD_RATE,
) -> dict:
    bid_price = quote.get("bid_price")

    if bid_price is None:
        raise ValueError(
            f"No bid price available for {quote['exchange']}"
        )

    exchange = quote["exchange"]
    quote_currency = quote["quote_currency"]

    fee_rate = DEFAULT_TAKER_FEES.get(
        exchange,
        Decimal("0"),
    )

    if quote_currency == "USD":
        price_usd = bid_price
    elif quote_currency == "USDT":
        price_usd = bid_price * usd_usdt_rate
    else:
        raise ValueError(
            f"Unsupported quote currency: {quote_currency}"
        )

    fee_usd = price_usd * fee_rate
    effective_price_usd = price_usd - fee_usd

    return {
        "exchange": exchange,
        "symbol": quote["symbol"],
        "side": "SELL",
        "quote_currency": quote_currency,
        "market_price": bid_price,
        "price_usd": price_usd,
        "fee_rate": fee_rate,
        "fee_usd": fee_usd,
        "effective_price_usd": effective_price_usd,
        "bid_quantity": quote.get("bid_quantity"),
    }


def select_best_execution(
    quotes: list[dict],
    usd_usdt_rate: Decimal = DEFAULT_USDT_USD_RATE,
) -> dict:
    valid_quotes = [
        quote
        for quote in quotes
        if quote.get("status") == "ok"
    ]

    buy_executions = []
    sell_executions = []

    for quote in valid_quotes:
        if quote.get("ask_price") is not None:
            buy_executions.append(
                calculate_buy_execution(
                    quote,
                    usd_usdt_rate,
                )
            )

        if quote.get("bid_price") is not None:
            sell_executions.append(
                calculate_sell_execution(
                    quote,
                    usd_usdt_rate,
                )
            )

    best_buy = min(
        buy_executions,
        key=lambda execution: execution[
            "effective_price_usd"
        ],
        default=None,
    )

    best_sell = max(
        sell_executions,
        key=lambda execution: execution[
            "effective_price_usd"
        ],
        default=None,
    )

    return {
        "best_buy": best_buy,
        "best_sell": best_sell,
        "buy_options": buy_executions,
        "sell_options": sell_executions,
    }
from decimal import Decimal


DEFAULT_MIN_PROFIT_USD = Decimal("0.05")
DEFAULT_MIN_PROFIT_PERCENT = Decimal("0.10")


def _decimal(value) -> Decimal | None:
    if value is None:
        return None

    return Decimal(str(value))


def calculate_opportunity(
    buy_execution: dict,
    sell_execution: dict,
    capital_usd: Decimal,
    min_profit_usd: Decimal = DEFAULT_MIN_PROFIT_USD,
    min_profit_percent: Decimal = DEFAULT_MIN_PROFIT_PERCENT,
) -> dict:
    buy_price = _decimal(
        buy_execution.get("effective_price_usd")
    )

    sell_price = _decimal(
        sell_execution.get("effective_price_usd")
    )

    if buy_price is None:
        raise ValueError(
            f"No effective buy price for "
            f"{buy_execution.get('exchange')}"
        )

    if sell_price is None:
        raise ValueError(
            f"No effective sell price for "
            f"{sell_execution.get('exchange')}"
        )

    if capital_usd <= 0:
        raise ValueError(
            "Capital must be greater than zero."
        )

    buy_quantity = capital_usd / buy_price

    ask_quantity = _decimal(
        buy_execution.get("ask_quantity")
    )

    bid_quantity = _decimal(
        sell_execution.get("bid_quantity")
    )

    liquidity_limited = False

    if ask_quantity is not None and ask_quantity < buy_quantity:
        buy_quantity = ask_quantity
        liquidity_limited = True

    if bid_quantity is not None and bid_quantity < buy_quantity:
        buy_quantity = bid_quantity
        liquidity_limited = True

    if buy_quantity <= 0:
        return {
            "status": "NO_TRADE",
            "reason": "Insufficient liquidity.",
            "buy_exchange": buy_execution["exchange"],
            "sell_exchange": sell_execution["exchange"],
            "symbol": buy_execution["symbol"],
        }

    buy_liquidity_usd = None

    if ask_quantity is not None:
        buy_liquidity_usd = (
            ask_quantity * buy_price
        )

    sell_liquidity_usd = None

    if bid_quantity is not None:
        sell_liquidity_usd = (
            bid_quantity * sell_price
        )

    capital_used = buy_quantity * buy_price

    estimated_sell_value = (
        buy_quantity * sell_price
    )

    estimated_profit = (
        estimated_sell_value - capital_used
    )

    estimated_profit_percent = (
        estimated_profit / capital_used
    ) * Decimal("100")

    meets_profit_threshold = (
        estimated_profit >= min_profit_usd
        and estimated_profit_percent >= min_profit_percent
    )

    return {
        "status": (
            "TRADE"
            if meets_profit_threshold
            else "NO_TRADE"
        ),
        "buy_exchange": buy_execution["exchange"],
        "sell_exchange": sell_execution["exchange"],
        "symbol": buy_execution["symbol"],
        "capital_usd": capital_usd,
        "quantity": buy_quantity,
        "buy_effective_price_usd": buy_price,
        "sell_effective_price_usd": sell_price,
        "capital_used_usd": capital_used,
        "estimated_sell_value_usd": estimated_sell_value,
        "estimated_profit_usd": estimated_profit,
        "estimated_profit_percent": estimated_profit_percent,
        "buy_liquidity_usd": buy_liquidity_usd,
        "sell_liquidity_usd": sell_liquidity_usd,
        "liquidity_limited": liquidity_limited,
        "min_profit_usd": min_profit_usd,
        "min_profit_percent": min_profit_percent,
    }


def find_best_opportunity(
    executions: dict,
    capital_usd: Decimal,
    min_profit_usd: Decimal = DEFAULT_MIN_PROFIT_USD,
    min_profit_percent: Decimal = DEFAULT_MIN_PROFIT_PERCENT,
) -> dict:
    buy_options = executions.get(
        "buy_options",
        [],
    )

    sell_options = executions.get(
        "sell_options",
        [],
    )

    valid_buys = [
        execution
        for execution in buy_options
        if execution.get(
            "effective_price_usd"
        ) is not None
    ]

    valid_sells = [
        execution
        for execution in sell_options
        if execution.get(
            "effective_price_usd"
        ) is not None
    ]

    opportunities = []

    for buy_execution in valid_buys:
        for sell_execution in valid_sells:
            if (
                buy_execution["exchange"]
                == sell_execution["exchange"]
            ):
                continue

            try:
                opportunity = calculate_opportunity(
                    buy_execution=buy_execution,
                    sell_execution=sell_execution,
                    capital_usd=capital_usd,
                    min_profit_usd=min_profit_usd,
                    min_profit_percent=min_profit_percent,
                )

                opportunities.append(opportunity)

            except ValueError:
                continue

    if not opportunities:
        return {
            "status": "NO_TRADE",
            "reason": (
                "No valid exchange combination."
            ),
            "opportunities": [],
        }

    best_opportunity = max(
        opportunities,
        key=lambda opportunity: opportunity[
            "estimated_profit_usd"
        ],
    )

    return {
        "status": best_opportunity["status"],
        "best_opportunity": best_opportunity,
        "opportunities": opportunities,
    }
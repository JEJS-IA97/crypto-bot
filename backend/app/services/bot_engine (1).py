from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock

from sqlalchemy.orm import Session

from app.config import settings
from app.services.arbitrage_service import execute_arbitrage
from app.services.exchange_market_service import (
    fetch_exchange_quotes,
)
from app.services.execution_price_service import (
    select_best_execution,
)
from app.services.inventory_service import (
    validate_arbitrage_inventory,
)
from app.services.risk_service import (
    RiskConfig,
    validate_opportunity,
)
from app.services.trade_opportunity_service import (
    find_best_opportunity,
)


execution_lock = Lock()


def _parse_fetched_at(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def _filter_fresh_executions(
    executions: dict,
    max_quote_age_seconds: int,
) -> dict:
    now = datetime.now(timezone.utc)

    fresh_buy_options = []
    fresh_sell_options = []

    stale_buy_count = 0
    stale_sell_count = 0

    for execution in executions.get(
        "buy_options",
        [],
    ):
        fetched_at = _parse_fetched_at(
            execution.get("fetched_at")
        )

        if fetched_at is None:
            stale_buy_count += 1
            continue

        age_seconds = (
            now - fetched_at
        ).total_seconds()

        if (
            age_seconds < 0
            or age_seconds
            > max_quote_age_seconds
        ):
            stale_buy_count += 1
            continue

        fresh_buy_options.append(
            execution
        )

    for execution in executions.get(
        "sell_options",
        [],
    ):
        fetched_at = _parse_fetched_at(
            execution.get("fetched_at")
        )

        if fetched_at is None:
            stale_sell_count += 1
            continue

        age_seconds = (
            now - fetched_at
        ).total_seconds()

        if (
            age_seconds < 0
            or age_seconds
            > max_quote_age_seconds
        ):
            stale_sell_count += 1
            continue

        fresh_sell_options.append(
            execution
        )

    best_buy = min(
        fresh_buy_options,
        key=lambda execution: execution[
            "effective_price_usd"
        ],
        default=None,
    )

    best_sell = max(
        fresh_sell_options,
        key=lambda execution: execution[
            "effective_price_usd"
        ],
        default=None,
    )

    return {
        "best_buy": best_buy,
        "best_sell": best_sell,
        "buy_options": fresh_buy_options,
        "sell_options": fresh_sell_options,
        "freshness": {
            "max_quote_age_seconds": (
                max_quote_age_seconds
            ),
            "checked_at": now.isoformat(),
            "stale_buy_count": stale_buy_count,
            "stale_sell_count": stale_sell_count,
        },
    }


def _calculate_revalidation_slippage(
    first_opportunity: dict,
    second_opportunity: dict,
) -> dict:
    first_buy_price = Decimal(
        str(
            first_opportunity[
                "buy_effective_price_usd"
            ]
        )
    )
    second_buy_price = Decimal(
        str(
            second_opportunity[
                "buy_effective_price_usd"
            ]
        )
    )

    first_sell_price = Decimal(
        str(
            first_opportunity[
                "sell_effective_price_usd"
            ]
        )
    )
    second_sell_price = Decimal(
        str(
            second_opportunity[
                "sell_effective_price_usd"
            ]
        )
    )

    if (
        first_buy_price <= 0
        or first_sell_price <= 0
    ):
        raise ValueError(
            "Invalid execution price "
            "during revalidation."
        )

    buy_slippage_percent = (
        (
            second_buy_price
            - first_buy_price
        )
        / first_buy_price
    ) * Decimal("100")

    sell_slippage_percent = (
        (
            first_sell_price
            - second_sell_price
        )
        / first_sell_price
    ) * Decimal("100")

    return {
        "buy_slippage_percent": buy_slippage_percent,
        "sell_slippage_percent": sell_slippage_percent,
        "max_adverse_slippage_percent": max(
            buy_slippage_percent,
            sell_slippage_percent,
            Decimal("0"),
        ),
    }


def _prepare_market_evaluation(
    db: Session,
    account_id: int,
    symbol: str,
    capital_usd: Decimal,
    risk_config: RiskConfig,
) -> tuple[dict, dict | None, dict]:
    quotes = fetch_exchange_quotes(symbol)

    executions = select_best_execution(
        quotes
    )

    executions = _filter_fresh_executions(
        executions=executions,
        max_quote_age_seconds=(
            settings.simulation_bot_max_quote_age_seconds
        ),
    )

    if (
        executions["best_buy"] is None
        or executions["best_sell"] is None
    ):
        return (
            {
                "decision": "NO_TRADE",
                "reason": (
                    "No fresh executable market "
                    "quote is available."
                ),
                "symbol": symbol,
                "capital_usd": capital_usd,
                "market": executions,
            },
            None,
            executions,
        )

    opportunity_result = find_best_opportunity(
        executions=executions,
        capital_usd=capital_usd,
        min_profit_usd=risk_config.min_profit_usd,
        min_profit_percent=risk_config.min_profit_percent,
    )

    best_opportunity = opportunity_result.get(
        "best_opportunity"
    )

    if best_opportunity is None:
        return (
            {
                "decision": "NO_TRADE",
                "reason": "No valid opportunity found.",
                "symbol": symbol,
                "capital_usd": capital_usd,
                "market": executions,
            },
            None,
            executions,
        )

    risk_result = validate_opportunity(
        best_opportunity,
        risk_config,
    )

    if not risk_result["approved"]:
        return (
            {
                "decision": "NO_TRADE",
                "reason": risk_result["reason"],
                "symbol": symbol,
                "capital_usd": capital_usd,
                "opportunity": best_opportunity,
                "risk": risk_result,
                "market": executions,
            },
            None,
            executions,
        )

    inventory_result = validate_arbitrage_inventory(
        db=db,
        account_id=account_id,
        opportunity=best_opportunity,
    )

    if not inventory_result["approved"]:
        return (
            {
                "decision": "NO_TRADE",
                "reason": inventory_result["reason"],
                "symbol": symbol,
                "capital_usd": capital_usd,
                "opportunity": best_opportunity,
                "risk": risk_result,
                "inventory": inventory_result,
                "market": executions,
            },
            None,
            executions,
        )

    return (
        {
            "decision": "READY_TO_TRADE",
            "reason": (
                "Opportunity passed risk and "
                "simulation balance validation."
            ),
            "symbol": symbol,
            "capital_usd": capital_usd,
            "opportunity": best_opportunity,
            "risk": risk_result,
            "inventory": inventory_result,
            "market": executions,
        },
        best_opportunity,
        executions,
    )


def evaluate_market(
    db: Session,
    account_id: int,
    symbol: str,
    capital_usd: Decimal,
    risk_config: RiskConfig | None = None,
) -> dict:
    config = risk_config or RiskConfig()

    result, _, _ = _prepare_market_evaluation(
        db=db,
        account_id=account_id,
        symbol=symbol,
        capital_usd=capital_usd,
        risk_config=config,
    )

    return result


def execute_market(
    db: Session,
    account_id: int,
    symbol: str,
    capital_usd: Decimal,
    risk_config: RiskConfig | None = None,
) -> dict:
    config = risk_config or RiskConfig()

    with execution_lock:
        first_result, first_opportunity, _ = (
            _prepare_market_evaluation(
                db=db,
                account_id=account_id,
                symbol=symbol,
                capital_usd=capital_usd,
                risk_config=config,
            )
        )

        if first_opportunity is None:
            return first_result

        second_result, second_opportunity, second_executions = (
            _prepare_market_evaluation(
                db=db,
                account_id=account_id,
                symbol=symbol,
                capital_usd=capital_usd,
                risk_config=config,
            )
        )

        if second_opportunity is None:
            return {
                "decision": "NO_TRADE",
                "reason": (
                    "Opportunity disappeared during "
                    "execution revalidation."
                ),
                "symbol": symbol,
                "capital_usd": capital_usd,
                "revalidation_failed": True,
                "revalidation_failure_type": (
                    "opportunity_disappeared"
                ),
                "first_evaluation": first_result,
                "revalidation": second_result,
            }

        slippage = _calculate_revalidation_slippage(
            first_opportunity=first_opportunity,
            second_opportunity=second_opportunity,
        )

        second_result["revalidation_slippage"] = (
            slippage
        )

        max_slippage_percent = Decimal(
            str(
                settings.simulation_bot_max_slippage_percent
            )
        )

        if (
            slippage[
                "max_adverse_slippage_percent"
            ]
            > max_slippage_percent
        ):
            return {
                "decision": "NO_TRADE",
                "reason": (
                    "Market moved beyond configured "
                    "slippage tolerance during "
                    "execution revalidation."
                ),
                "symbol": symbol,
                "capital_usd": capital_usd,
                "revalidation_failed": True,
                "revalidation_failure_type": (
                    "slippage_exceeded"
                ),
                "max_slippage_percent": (
                    max_slippage_percent
                ),
                "revalidation_slippage": slippage,
                "first_evaluation": first_result,
                "revalidation": second_result,
            }

        arbitrage = execute_arbitrage(
            db=db,
            account_id=account_id,
            opportunity=second_opportunity,
            executions=second_executions,
        )

        second_result["decision"] = "TRADED"
        second_result["reason"] = (
            "Arbitrage passed execution revalidation "
            "and was executed successfully."
        )
        second_result["arbitrage"] = arbitrage

        return second_result

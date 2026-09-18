from decimal import Decimal

from sqlalchemy.orm import Session

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


def evaluate_market(
    db: Session,
    account_id: int,
    symbol: str,
    capital_usd: Decimal,
    risk_config: RiskConfig | None = None,
) -> dict:
    config = risk_config or RiskConfig()

    quotes = fetch_exchange_quotes(symbol)

    executions = select_best_execution(
        quotes
    )

    opportunity_result = find_best_opportunity(
        executions=executions,
        capital_usd=capital_usd,
        min_profit_usd=config.min_profit_usd,
        min_profit_percent=config.min_profit_percent,
    )

    best_opportunity = opportunity_result.get(
        "best_opportunity"
    )

    if best_opportunity is None:
        return {
            "decision": "NO_TRADE",
            "reason": (
                "No valid opportunity found."
            ),
            "symbol": symbol,
            "capital_usd": capital_usd,
            "market": executions,
        }

    risk_result = validate_opportunity(
        best_opportunity,
        config,
    )

    if not risk_result["approved"]:
        return {
            "decision": "NO_TRADE",
            "reason": risk_result["reason"],
            "symbol": symbol,
            "capital_usd": capital_usd,
            "opportunity": best_opportunity,
            "risk": risk_result,
            "market": executions,
        }

    inventory_result = (
        validate_arbitrage_inventory(
            db=db,
            account_id=account_id,
            opportunity=best_opportunity,
        )
    )

    if not inventory_result["approved"]:
        return {
            "decision": "NO_TRADE",
            "reason": inventory_result["reason"],
            "symbol": symbol,
            "capital_usd": capital_usd,
            "opportunity": best_opportunity,
            "risk": risk_result,
            "inventory": inventory_result,
            "market": executions,
        }

    return {
        "decision": "READY_TO_TRADE",
        "reason": (
            "Opportunity passed risk and "
            "inventory validation."
        ),
        "symbol": symbol,
        "capital_usd": capital_usd,
        "opportunity": best_opportunity,
        "risk": risk_result,
        "inventory": inventory_result,
        "market": executions,
    }
from decimal import Decimal

from app.services.exchange_market_service import (
    fetch_exchange_quotes,
)
from app.services.execution_price_service import (
    select_best_execution,
)
from app.services.risk_service import (
    RiskConfig,
    validate_opportunity,
)
from app.services.trade_opportunity_service import (
    find_best_opportunity,
)


def evaluate_market(
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
            "reason": "No valid opportunity found.",
            "symbol": symbol,
            "capital_usd": capital_usd,
            "market": executions,
        }

    risk_result = validate_opportunity(
        best_opportunity,
        config,
    )

    decision = (
        "READY_TO_TRADE"
        if risk_result["approved"]
        else "NO_TRADE"
    )

    return {
        "decision": decision,
        "symbol": symbol,
        "capital_usd": capital_usd,
        "opportunity": best_opportunity,
        "risk": risk_result,
        "market": executions,
    }
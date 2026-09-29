from decimal import Decimal

from sqlalchemy.orm import Session

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

    result, opportunity, executions = (
        _prepare_market_evaluation(
            db=db,
            account_id=account_id,
            symbol=symbol,
            capital_usd=capital_usd,
            risk_config=config,
        )
    )

    if opportunity is None:
        return result

    arbitrage = execute_arbitrage(
        db=db,
        account_id=account_id,
        opportunity=opportunity,
        executions=executions,
    )

    result["decision"] = "TRADED"
    result["reason"] = (
        "Arbitrage executed successfully."
    )
    result["arbitrage"] = arbitrage

    return result
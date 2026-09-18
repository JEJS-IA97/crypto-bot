from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskConfig:
    max_trade_usd: Decimal = Decimal("5")
    min_profit_usd: Decimal = Decimal("0.05")
    min_profit_percent: Decimal = Decimal("0.10")
    min_liquidity_usd: Decimal = Decimal("10")
    max_position_usd: Decimal = Decimal("20")


def validate_opportunity(
    opportunity: dict,
    config: RiskConfig,
) -> dict:
    if opportunity.get("status") != "TRADE":
        return {
            "approved": False,
            "reason": (
                "Opportunity does not meet "
                "profit requirements."
            ),
        }

    capital_usd = Decimal(
        str(opportunity["capital_usd"])
    )

    capital_used_usd = Decimal(
        str(opportunity["capital_used_usd"])
    )

    profit_usd = Decimal(
        str(opportunity["estimated_profit_usd"])
    )

    profit_percent = Decimal(
        str(opportunity["estimated_profit_percent"])
    )

    quantity = Decimal(
        str(opportunity["quantity"])
    )

    buy_liquidity = opportunity.get(
        "buy_liquidity_usd"
    )

    sell_liquidity = opportunity.get(
        "sell_liquidity_usd"
    )

    if capital_usd > config.max_trade_usd:
        return {
            "approved": False,
            "reason": (
                "Requested capital exceeds "
                "max_trade_usd."
            ),
        }

    if capital_used_usd > config.max_trade_usd:
        return {
            "approved": False,
            "reason": (
                "Capital required exceeds "
                "max_trade_usd."
            ),
        }

    if profit_usd < config.min_profit_usd:
        return {
            "approved": False,
            "reason": (
                "Profit is below minimum USD threshold."
            ),
        }

    if profit_percent < config.min_profit_percent:
        return {
            "approved": False,
            "reason": (
                "Profit percentage is below "
                "minimum threshold."
            ),
        }

    if buy_liquidity is not None:
        if buy_liquidity < config.min_liquidity_usd:
            return {
                "approved": False,
                "reason": (
                    "Buy-side liquidity is too low."
                ),
            }

    if sell_liquidity is not None:
        if sell_liquidity < config.min_liquidity_usd:
            return {
                "approved": False,
                "reason": (
                    "Sell-side liquidity is too low."
                ),
            }

    if quantity <= 0:
        return {
            "approved": False,
            "reason": "Calculated quantity is invalid.",
        }

    if capital_used_usd > config.max_position_usd:
        return {
            "approved": False,
            "reason": "Position limit exceeded.",
        }

    return {
        "approved": True,
        "reason": "Opportunity passed risk validation.",
    }
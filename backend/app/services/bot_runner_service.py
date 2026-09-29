import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.services.bot_engine import execute_market
from app.services.risk_service import RiskConfig


class BotRuntimeState:
    def __init__(self) -> None:
        self.running = False
        self.last_run_at: datetime | None = None
        self.last_decision: str | None = None
        self.last_reason: str | None = None
        self.last_error: str | None = None


runtime_state = BotRuntimeState()


def execute_bot_cycle() -> dict:
    db: Session = SessionLocal()

    try:
        config = RiskConfig(
            max_trade_usd=Decimal(
                str(settings.simulation_bot_max_trade_usd)
            ),
            min_profit_usd=Decimal(
                str(settings.simulation_bot_min_profit_usd)
            ),
            min_profit_percent=Decimal(
                str(settings.simulation_bot_min_profit_percent)
            ),
            min_liquidity_usd=Decimal(
                str(settings.simulation_bot_min_liquidity_usd)
            ),
            max_position_usd=Decimal(
                str(settings.simulation_bot_max_position_usd)
            ),
        )

        result = execute_market(
            db=db,
            account_id=settings.simulation_bot_account_id,
            symbol=settings.simulation_bot_symbol,
            capital_usd=Decimal(
                str(settings.simulation_bot_capital_usd)
            ),
            risk_config=config,
        )

        runtime_state.last_run_at = datetime.now(
            timezone.utc
        )
        runtime_state.last_decision = result.get(
            "decision"
        )
        runtime_state.last_reason = result.get(
            "reason"
        )
        runtime_state.last_error = None

        return result

    except Exception as exc:
        runtime_state.last_run_at = datetime.now(
            timezone.utc
        )
        runtime_state.last_decision = "ERROR"
        runtime_state.last_reason = None
        runtime_state.last_error = str(exc)

        raise

    finally:
        db.close()


async def run_bot_loop(
    stop_event: asyncio.Event,
) -> None:
    runtime_state.running = True

    try:
        while not stop_event.is_set():
            try:
                result = await asyncio.to_thread(
                    execute_bot_cycle
                )

                print(
                    "[BOT]"
                    f" decision={result.get('decision')}"
                    f" reason={result.get('reason')}"
                )

                arbitrage = result.get(
                    "arbitrage"
                )

                if arbitrage is not None:
                    print(
                        "[BOT]"
                        f" arbitrage_id={arbitrage.id}"
                        f" profit={arbitrage.net_profit_usd}"
                    )

            except Exception as exc:
                print(
                    "[BOT]"
                    f" error={exc}"
                )

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=(
                        settings.simulation_bot_interval_seconds
                    ),
                )

            except asyncio.TimeoutError:
                pass

    finally:
        runtime_state.running = False


def get_bot_status() -> dict:
    return {
        "enabled": settings.simulation_bot_enabled,
        "running": runtime_state.running,
        "account_id": settings.simulation_bot_account_id,
        "symbol": settings.simulation_bot_symbol,
        "capital_usd": settings.simulation_bot_capital_usd,
        "interval_seconds": (
            settings.simulation_bot_interval_seconds
        ),
        "last_run_at": runtime_state.last_run_at,
        "last_decision": runtime_state.last_decision,
        "last_reason": runtime_state.last_reason,
        "last_error": runtime_state.last_error,
    }
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import SimulationArbitrage
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


def utc_now_naive() -> datetime:
    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


def get_trade_limits(
    db: Session,
    account_id: int,
) -> dict:
    now = utc_now_naive()

    day_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    trades_today = db.scalar(
        select(
            func.count(
                SimulationArbitrage.id
            )
        ).where(
            SimulationArbitrage.account_id
            == account_id,
            SimulationArbitrage.executed_at
            >= day_start,
        )
    ) or 0

    latest_trade_at = db.scalar(
        select(
            SimulationArbitrage.executed_at
        )
        .where(
            SimulationArbitrage.account_id
            == account_id
        )
        .order_by(
            SimulationArbitrage.executed_at.desc()
        )
        .limit(1)
    )

    cooldown_remaining_seconds = 0

    if latest_trade_at is not None:
        elapsed_seconds = (
            now - latest_trade_at
        ).total_seconds()

        cooldown_remaining_seconds = max(
            0,
            int(
                settings.simulation_bot_cooldown_seconds
                - elapsed_seconds
            ),
        )

    daily_limit_reached = (
        trades_today
        >= settings.simulation_bot_max_trades_per_day
    )

    cooldown_active = (
        cooldown_remaining_seconds > 0
    )

    if daily_limit_reached:
        return {
            "allowed": False,
            "reason": (
                "Daily autonomous trade limit reached."
            ),
            "trades_today": trades_today,
            "max_trades_per_day": (
                settings.simulation_bot_max_trades_per_day
            ),
            "cooldown_remaining_seconds": (
                cooldown_remaining_seconds
            ),
        }

    if cooldown_active:
        return {
            "allowed": False,
            "reason": (
                "Bot cooldown is active."
            ),
            "trades_today": trades_today,
            "max_trades_per_day": (
                settings.simulation_bot_max_trades_per_day
            ),
            "cooldown_remaining_seconds": (
                cooldown_remaining_seconds
            ),
        }

    return {
        "allowed": True,
        "reason": "Execution limits passed.",
        "trades_today": trades_today,
        "max_trades_per_day": (
            settings.simulation_bot_max_trades_per_day
        ),
        "cooldown_remaining_seconds": 0,
    }


def execute_bot_cycle() -> dict:
    db: Session = SessionLocal()

    try:
        limit_result = get_trade_limits(
            db=db,
            account_id=settings.simulation_bot_account_id,
        )

        if not limit_result["allowed"]:
            runtime_state.last_run_at = datetime.now(
                timezone.utc
            )
            runtime_state.last_decision = "NO_TRADE"
            runtime_state.last_reason = (
                limit_result["reason"]
            )
            runtime_state.last_error = None

            return {
                "decision": "NO_TRADE",
                "reason": limit_result["reason"],
                "account_id": (
                    settings.simulation_bot_account_id
                ),
                "symbol": (
                    settings.simulation_bot_symbol
                ),
                "capital_usd": (
                    settings.simulation_bot_capital_usd
                ),
                "limits": limit_result,
            }

        config = RiskConfig(
            max_trade_usd=Decimal(
                str(settings.simulation_bot_max_trade_usd)
            ),
            min_profit_usd=Decimal(
                str(settings.simulation_bot_min_profit_usd)
            ),
            min_profit_percent=Decimal(
                str(
                    settings.simulation_bot_min_profit_percent
                )
            ),
            min_liquidity_usd=Decimal(
                str(
                    settings.simulation_bot_min_liquidity_usd
                )
            ),
            max_position_usd=Decimal(
                str(
                    settings.simulation_bot_max_position_usd
                )
            ),
        )

        result = execute_market(
            db=db,
            account_id=(
                settings.simulation_bot_account_id
            ),
            symbol=settings.simulation_bot_symbol,
            capital_usd=Decimal(
                str(
                    settings.simulation_bot_capital_usd
                )
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
                        f" arbitrage_id="
                        f"{arbitrage.id}"
                        f" profit="
                        f"{arbitrage.net_profit_usd}"
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
    db: Session = SessionLocal()

    try:
        limits = get_trade_limits(
            db=db,
            account_id=settings.simulation_bot_account_id,
        )

    except Exception as exc:
        limits = {
            "allowed": False,
            "reason": (
                "Unable to read execution limits."
            ),
            "error": str(exc),
        }

    finally:
        db.close()

    return {
        "enabled": settings.simulation_bot_enabled,
        "running": runtime_state.running,
        "account_id": settings.simulation_bot_account_id,
        "symbol": settings.simulation_bot_symbol,
        "capital_usd": settings.simulation_bot_capital_usd,
        "interval_seconds": (
            settings.simulation_bot_interval_seconds
        ),
        "cooldown_seconds": (
            settings.simulation_bot_cooldown_seconds
        ),
        "max_trades_per_day": (
            settings.simulation_bot_max_trades_per_day
        ),
        "trades_today": limits.get(
            "trades_today",
            0,
        ),
        "cooldown_remaining_seconds": limits.get(
            "cooldown_remaining_seconds",
            0,
        ),
        "execution_allowed": limits.get(
            "allowed",
            False,
        ),
        "execution_limit_reason": limits.get(
            "reason"
        ),
        "last_run_at": runtime_state.last_run_at,
        "last_decision": runtime_state.last_decision,
        "last_reason": runtime_state.last_reason,
        "last_error": runtime_state.last_error,
    }
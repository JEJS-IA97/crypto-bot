import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import SimulationArbitrage
from app.services.bot_engine import (
    evaluate_market,
    execute_market,
)
from app.services.risk_service import RiskConfig


class BotRuntimeState:
    def __init__(self) -> None:
        self.running = False

        self.last_run_at: datetime | None = None
        self.last_symbol: str | None = None
        self.last_decision: str | None = None
        self.last_reason: str | None = None
        self.last_error: str | None = None

        self.last_evaluated_symbols: list[
            dict
        ] = []

        self.last_trade_candidates: int = 0
        self.last_best_symbol: str | None = None
        self.last_best_profit_usd: Decimal | None = None
        self.last_best_profit_percent: Decimal | None = None


runtime_state = BotRuntimeState()


def utc_now_naive() -> datetime:
    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


def get_configured_symbols() -> list[str]:
    symbols: list[str] = []

    for raw_symbol in (
        settings.simulation_bot_symbols
        .split(",")
    ):
        symbol = raw_symbol.strip().upper()

        if symbol and symbol not in symbols:
            symbols.append(symbol)

    return symbols


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


def build_risk_config() -> RiskConfig:
    return RiskConfig(
        max_trade_usd=Decimal(
            str(
                settings.simulation_bot_max_trade_usd
            )
        ),
        min_profit_usd=Decimal(
            str(
                settings.simulation_bot_min_profit_usd
            )
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


def _build_symbol_summary(
    symbol: str,
    result: dict,
) -> dict:
    opportunity = result.get(
        "opportunity"
    )

    summary = {
        "symbol": symbol,
        "decision": result.get(
            "decision"
        ),
        "reason": result.get(
            "reason"
        ),
        "profit_usd": None,
        "profit_percent": None,
        "buy_exchange": None,
        "sell_exchange": None,
    }

    if opportunity is not None:
        profit_usd = opportunity.get(
            "estimated_profit_usd"
        )

        profit_percent = opportunity.get(
            "estimated_profit_percent"
        )

        summary["profit_usd"] = (
            Decimal(str(profit_usd))
            if profit_usd is not None
            else None
        )

        summary["profit_percent"] = (
            Decimal(str(profit_percent))
            if profit_percent is not None
            else None
        )

        summary["buy_exchange"] = (
            opportunity.get(
                "buy_exchange"
            )
        )

        summary["sell_exchange"] = (
            opportunity.get(
                "sell_exchange"
            )
        )

    return summary


def execute_bot_cycle() -> dict:
    db: Session = SessionLocal()

    try:
        symbols = get_configured_symbols()

        if not symbols:
            raise RuntimeError(
                "No simulation bot symbols configured."
            )

        limit_result = get_trade_limits(
            db=db,
            account_id=(
                settings.simulation_bot_account_id
            ),
        )

        if not limit_result["allowed"]:
            runtime_state.last_run_at = (
                datetime.now(timezone.utc)
            )

            runtime_state.last_symbol = None
            runtime_state.last_decision = (
                "NO_TRADE"
            )

            runtime_state.last_reason = (
                limit_result["reason"]
            )

            runtime_state.last_error = None

            runtime_state.last_evaluated_symbols = []
            runtime_state.last_trade_candidates = 0
            runtime_state.last_best_symbol = None
            runtime_state.last_best_profit_usd = None
            runtime_state.last_best_profit_percent = None

            return {
                "decision": "NO_TRADE",
                "reason": limit_result["reason"],
                "account_id": (
                    settings.simulation_bot_account_id
                ),
                "symbols": symbols,
                "limits": limit_result,
                "evaluated_symbols": [],
            }

        risk_config = build_risk_config()

        evaluations: list[
            tuple[str, dict]
        ] = []

        symbol_summaries: list[
            dict
        ] = []

        trade_candidates: list[
            tuple[str, dict, Decimal]
        ] = []

        for symbol in symbols:
            result = evaluate_market(
                db=db,
                account_id=(
                    settings.simulation_bot_account_id
                ),
                symbol=symbol,
                capital_usd=Decimal(
                    str(
                        settings.simulation_bot_capital_usd
                    )
                ),
                risk_config=risk_config,
            )

            evaluations.append(
                (
                    symbol,
                    result,
                )
            )

            summary = _build_symbol_summary(
                symbol=symbol,
                result=result,
            )

            symbol_summaries.append(
                summary
            )

            opportunity = result.get(
                "opportunity"
            )

            if (
                result.get("decision")
                == "READY_TO_TRADE"
                and opportunity is not None
            ):
                profit_usd = Decimal(
                    str(
                        opportunity[
                            "estimated_profit_usd"
                        ]
                    )
                )

                trade_candidates.append(
                    (
                        symbol,
                        result,
                        profit_usd,
                    )
                )

        best_scan = None

        for summary in symbol_summaries:
            profit_usd = summary.get(
                "profit_usd"
            )

            if profit_usd is None:
                continue

            if (
                best_scan is None
                or profit_usd
                > best_scan["profit_usd"]
            ):
                best_scan = {
                    "symbol": summary[
                        "symbol"
                    ],
                    "profit_usd": profit_usd,
                    "profit_percent": summary[
                        "profit_percent"
                    ],
                }

        runtime_state.last_evaluated_symbols = (
            symbol_summaries
        )

        runtime_state.last_trade_candidates = (
            len(trade_candidates)
        )

        runtime_state.last_best_symbol = (
            best_scan["symbol"]
            if best_scan is not None
            else None
        )

        runtime_state.last_best_profit_usd = (
            best_scan["profit_usd"]
            if best_scan is not None
            else None
        )

        runtime_state.last_best_profit_percent = (
            best_scan["profit_percent"]
            if best_scan is not None
            else None
        )

        if not trade_candidates:
            runtime_state.last_run_at = (
                datetime.now(timezone.utc)
            )

            runtime_state.last_symbol = (
                best_scan["symbol"]
                if best_scan is not None
                else None
            )

            runtime_state.last_decision = (
                "NO_TRADE"
            )

            runtime_state.last_reason = (
                "No configured symbol produced "
                "an executable opportunity."
            )

            runtime_state.last_error = None

            return {
                "decision": "NO_TRADE",
                "reason": (
                    "No configured symbol produced "
                    "an executable opportunity."
                ),
                "account_id": (
                    settings.simulation_bot_account_id
                ),
                "symbols": symbols,
                "evaluated_symbols": (
                    symbol_summaries
                ),
                "trade_candidates": 0,
                "best_symbol": (
                    best_scan["symbol"]
                    if best_scan is not None
                    else None
                ),
                "best_profit_usd": (
                    best_scan["profit_usd"]
                    if best_scan is not None
                    else None
                ),
                "best_profit_percent": (
                    best_scan["profit_percent"]
                    if best_scan is not None
                    else None
                ),
            }

        best_candidate = max(
            trade_candidates,
            key=lambda candidate: candidate[2],
        )

        selected_symbol = best_candidate[0]
        selected_evaluation = best_candidate[1]
        selected_profit_usd = best_candidate[2]

        selected_profit_percent = (
            selected_evaluation[
                "opportunity"
            ][
                "estimated_profit_percent"
            ]
        )

        execution_result = execute_market(
            db=db,
            account_id=(
                settings.simulation_bot_account_id
            ),
            symbol=selected_symbol,
            capital_usd=Decimal(
                str(
                    settings.simulation_bot_capital_usd
                )
            ),
            risk_config=risk_config,
        )

        runtime_state.last_run_at = (
            datetime.now(timezone.utc)
        )

        runtime_state.last_symbol = (
            selected_symbol
        )

        runtime_state.last_decision = (
            execution_result.get(
                "decision"
            )
        )

        runtime_state.last_reason = (
            execution_result.get(
                "reason"
            )
        )

        runtime_state.last_error = None

        result = {
            "decision": execution_result.get(
                "decision"
            ),
            "reason": execution_result.get(
                "reason"
            ),
            "account_id": (
                settings.simulation_bot_account_id
            ),
            "symbols": symbols,
            "evaluated_symbols": (
                symbol_summaries
            ),
            "trade_candidates": (
                len(trade_candidates)
            ),
            "selected_symbol": selected_symbol,
            "selected_profit_usd": (
                selected_profit_usd
            ),
            "selected_profit_percent": (
                selected_profit_percent
            ),
            "execution": execution_result,
        }

        if execution_result.get(
            "decision"
        ) == "TRADED":
            result["arbitrage"] = (
                execution_result.get(
                    "arbitrage"
                )
            )

        return result

    except Exception as exc:
        runtime_state.last_run_at = (
            datetime.now(timezone.utc)
        )

        runtime_state.last_decision = (
            "ERROR"
        )

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
                    f" decision="
                    f"{result.get('decision')}"
                    f" reason="
                    f"{result.get('reason')}"
                )

                selected_symbol = result.get(
                    "selected_symbol"
                )

                if selected_symbol is not None:
                    print(
                        "[BOT]"
                        f" selected_symbol="
                        f"{selected_symbol}"
                        f" candidates="
                        f"{result.get('trade_candidates')}"
                        f" profit="
                        f"{result.get('selected_profit_usd')}"
                    )

                arbitrage = result.get(
                    "arbitrage"
                )

                if arbitrage is not None:
                    print(
                        "[BOT]"
                        f" TRADED symbol="
                        f"{arbitrage.symbol}"
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
            account_id=(
                settings.simulation_bot_account_id
            ),
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
        "account_id": (
            settings.simulation_bot_account_id
        ),
        "symbols": get_configured_symbols(),
        "capital_usd": (
            settings.simulation_bot_capital_usd
        ),
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
        "cooldown_remaining_seconds": (
            limits.get(
                "cooldown_remaining_seconds",
                0,
            )
        ),
        "execution_allowed": limits.get(
            "allowed",
            False,
        ),
        "execution_limit_reason": limits.get(
            "reason"
        ),
        "last_run_at": (
            runtime_state.last_run_at
        ),
        "last_symbol": (
            runtime_state.last_symbol
        ),
        "last_decision": (
            runtime_state.last_decision
        ),
        "last_reason": (
            runtime_state.last_reason
        ),
        "last_error": (
            runtime_state.last_error
        ),
        "last_evaluated_symbols": (
            runtime_state.last_evaluated_symbols
        ),
        "last_trade_candidates": (
            runtime_state.last_trade_candidates
        ),
        "last_best_symbol": (
            runtime_state.last_best_symbol
        ),
        "last_best_profit_usd": (
            runtime_state.last_best_profit_usd
        ),
        "last_best_profit_percent": (
            runtime_state.last_best_profit_percent
        ),
    }
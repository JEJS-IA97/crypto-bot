"""Risk guard: daily loss block, open limits, cooldown and circuit breaker.

Implements spec 001 RF-4, RF-5, RF-22 and RF-26 over the persisted tables
`daily_risk_states` and `bot_runtimes`. Blocking only prevents NEW opens:
existing positions keep their stop-loss and take-profit orders (RF-4).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BotRuntime,
    DailyRiskState,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)

DAILY_LOSS_LIMIT_PCT = Decimal("5")
MAX_OPENS_PER_DAY = 10
COOLDOWN_SECONDS = 300
BREAKER_FAILURE_THRESHOLD = 5

REASON_DAILY_LOSS = "daily_loss_limit"
REASON_DAILY_OPEN_LIMIT = "daily_open_limit"
REASON_COOLDOWN = "cooldown"
REASON_POSITION_ERROR = "position_error"


def _require_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    return value


def get_daily_state(
    db: Session,
    day: date,
    start_equity_usd: Decimal,
) -> DailyRiskState:
    """Return today's risk row, creating it with the start-of-day equity."""
    if not isinstance(day, date):
        raise TypeError("day must be a date")
    start_equity_usd = _require_decimal(
        "start_equity_usd", start_equity_usd
    )
    if start_equity_usd < 0:
        raise ValueError("start_equity_usd must be >= 0")

    state = db.execute(
        select(DailyRiskState).where(DailyRiskState.day == day)
    ).scalar_one_or_none()
    if state is None:
        state = DailyRiskState(
            day=day,
            start_equity_usd=start_equity_usd,
        )
        db.add(state)
        db.commit()
    return state


def record_realized_pnl(
    db: Session,
    state: DailyRiskState,
    amount: Decimal,
) -> DailyRiskState:
    """Add realized PnL and block the day when the loss limit is reached."""
    amount = _require_decimal("amount", amount)
    state.realized_pnl_usd = state.realized_pnl_usd + amount

    limit = state.start_equity_usd * DAILY_LOSS_LIMIT_PCT / Decimal(100)
    if state.realized_pnl_usd <= -limit:
        state.blocked = True
        state.block_reason = REASON_DAILY_LOSS

    db.commit()
    return state


def register_open(db: Session, state: DailyRiskState, symbol: str) -> DailyRiskState:
    """Count one opened position towards the daily open limit (RF-5)."""
    if not symbol or not symbol.strip():
        raise ValueError("symbol must not be empty")
    state.opens_count += 1
    db.commit()
    return state


def _last_opened_buy_at(db: Session, symbol: str) -> datetime | None:
    return db.execute(
        select(SignalDecision.created_at)
        .where(
            SignalDecision.symbol == symbol,
            SignalDecision.side == TradeSide.BUY,
            SignalDecision.status.in_(
                [DecisionStatus.OPENED, DecisionStatus.CLOSED]
            ),
        )
        .order_by(SignalDecision.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def can_open(
    db: Session,
    state: DailyRiskState,
    symbol: str,
    now: datetime,
) -> tuple[bool, str]:
    """RF-4/RF-5: whether a new position may be opened for `symbol`."""
    if not symbol or not symbol.strip():
        raise ValueError("symbol must not be empty")
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")

    if state.blocked:
        return False, state.block_reason or REASON_DAILY_LOSS

    error_position = db.execute(
        select(PositionV2.id)
        .where(PositionV2.status == PositionStatus.ERROR)
        .limit(1)
    ).scalar_one_or_none()
    if error_position is not None:
        return False, REASON_POSITION_ERROR

    if state.opens_count >= MAX_OPENS_PER_DAY:
        return False, REASON_DAILY_OPEN_LIMIT

    last_opened_at = _last_opened_buy_at(db, symbol)
    if last_opened_at is not None:
        elapsed = (now - last_opened_at).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            return False, REASON_COOLDOWN
    return True, ""


def get_runtime(db: Session) -> BotRuntime:
    """Return the single bot runtime row (kill switch + breaker state)."""
    runtime = db.execute(
        select(BotRuntime).where(BotRuntime.id == 1)
    ).scalar_one_or_none()
    if runtime is None:
        runtime = BotRuntime(id=1)
        db.add(runtime)
        db.commit()
    return runtime


def record_cycle_failure(db: Session) -> BotRuntime:
    """RF-22: count a failed cycle; trip the breaker at the threshold."""
    runtime = get_runtime(db)
    runtime.consecutive_failures += 1
    if runtime.consecutive_failures >= BREAKER_FAILURE_THRESHOLD:
        runtime.breaker_active = True
        runtime.breaker_reason = (
            f"{runtime.consecutive_failures} consecutive cycle failures"
        )
    db.commit()
    return runtime


def record_cycle_success(db: Session) -> BotRuntime:
    """Clear the failure counter; the breaker stays manual-only (RF-22)."""
    runtime = get_runtime(db)
    runtime.consecutive_failures = 0
    db.commit()
    return runtime


def reset_breaker(db: Session) -> BotRuntime:
    """Manual restart after a tripped breaker (RF-22)."""
    runtime = get_runtime(db)
    runtime.breaker_active = False
    runtime.consecutive_failures = 0
    runtime.breaker_reason = None
    db.commit()
    return runtime

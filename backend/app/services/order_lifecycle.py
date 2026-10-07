"""Order lifecycle for phase 1 (spec 001 RF-13/RF-24/RF-10, module M6).

Flow over the `ExchangeExecutor` (in phase 1: `SimulationExecutor`):
a filled buy immediately gets a protective stop-loss and take-profit
(one position per symbol, mutually cancelling); closing computes PnL
with the 0.1% fee on both sides; any fill whose price deviates more
than 0.5% from the expected one registers a `TradeIncident` for the
panel without aborting the close.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.risk_math import (
    MAX_LOSS_PER_TRADE_USD,
    estimated_loss_usd,
    stop_take_prices,
)
from app.models import (
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    TradeIncident,
    utc_now,
)
from app.services.exchange_executor import ExchangeExecutor, OrderRequest
from app.services.simulation_service import QUANTITY_PLACES, money
from app.services.structured_log import emit

logger = logging.getLogger(__name__)

MAX_SLIPPAGE_PCT = Decimal("0.5")

KIND_SLIPPAGE = "slippage_exceeded"
KIND_STOP_FAILED = "stop_placement_failed"

ExitPlacer = Callable[[PositionV2, Decimal, Decimal], tuple[str, str]]

_EXIT_STATUS = {
    "stop": PositionStatus.STOPPED,
    "tp": PositionStatus.TAKE_PROFIT,
    "manual": PositionStatus.CLOSED,
}


def register_incident(
    db: Session,
    *,
    kind: str,
    symbol: str | None = None,
    decision_id: int | None = None,
    position_id: int | None = None,
    details: dict | None = None,
) -> TradeIncident:
    """Persist an incident so the panel can show it (RF-13/RF-24)."""
    incident = TradeIncident(
        kind=kind,
        symbol=symbol,
        decision_id=decision_id,
        position_id=position_id,
        details=json.dumps(details or {}, default=str, ensure_ascii=False),
    )
    db.add(incident)
    db.commit()
    return incident


def list_incidents(db: Session) -> list[TradeIncident]:
    return list(
        db.scalars(
            select(TradeIncident).order_by(TradeIncident.id.asc())
        ).all()
    )


def has_position_error(db: Session) -> bool:
    """RF-13: while a position has no stop, no new positions open."""
    row = db.execute(
        select(PositionV2.id)
        .where(PositionV2.status == PositionStatus.ERROR)
        .limit(1)
    ).scalar_one_or_none()
    return row is not None


def _record_slippage(
    db: Session,
    *,
    expected: Decimal | None,
    executed: Decimal,
    phase: str,
    symbol: str,
    decision_id: int | None,
    position_id: int | None,
) -> None:
    if expected is None or expected <= 0:
        return
    pct = (abs(executed - expected) / expected) * Decimal(100)
    if pct > MAX_SLIPPAGE_PCT:
        register_incident(
            db,
            kind=KIND_SLIPPAGE,
            symbol=symbol,
            decision_id=decision_id,
            position_id=position_id,
            details={
                "phase": phase,
                "expected": str(expected),
                "executed": str(executed),
                "slippage_pct": str(pct),
                "max_pct": str(MAX_SLIPPAGE_PCT),
            },
        )
        logger.warning(
            "slippage exceeded on %s fill for %s: %s%% > %s%%",
            phase,
            symbol,
            pct,
            MAX_SLIPPAGE_PCT,
        )


def _default_placer(
    position: PositionV2,
    stop_price: Decimal,
    take_profit_price: Decimal,
) -> tuple[str, str]:
    """Simulation placement: synthetic ids, no exchange round-trip."""
    return f"sim-stop-{position.id}", f"sim-tp-{position.id}"


def protection_after_fill(
    db: Session,
    *,
    position: PositionV2,
    decision: SignalDecision,
    fill=None,
    tick_size: Decimal,
    stop_loss_pct: Decimal | None = None,
    take_profit_pct: Decimal | None = None,
    placer: ExitPlacer | None = None,
) -> PositionV2:
    """RF-13: right after a buy fills, protect it with stop + take-profit.

    If the stop cannot be placed the position goes to `ERROR`, an
    incident is registered and `can_open` refuses new positions until
    a retry succeeds. `fill` is the `ExchangeOrderResult` of the entry.
    """
    if not isinstance(tick_size, Decimal):
        raise TypeError("tick_size must be Decimal")
    stop_pct = (
        stop_loss_pct if stop_loss_pct is not None else settings.stop_loss_pct
    )
    tp_pct = (
        take_profit_pct
        if take_profit_pct is not None
        else settings.take_profit_pct
    )

    if position.id is None:
        db.add(position)
        db.flush()

    if fill is not None:
        if fill.fee is not None:
            position.entry_fee_usd = fill.fee
        if fill.average_price is not None:
            _record_slippage(
                db,
                expected=decision.price,
                executed=fill.average_price,
                phase="entry",
                symbol=position.symbol,
                decision_id=decision.id,
                position_id=position.id,
            )
    if decision.filled_at is None:
        decision.filled_at = utc_now()

    stop_price, take_profit_price = stop_take_prices(
        entry_price=position.average_entry_price,
        stop_loss_pct=stop_pct,
        take_profit_pct=tp_pct,
        tick_size=tick_size,
    )

    # RF-13: if the loss at the stop would exceed 1 USD, reduce the size.
    # (Pre-send sizing in M4 normally prevents this path.)
    loss = estimated_loss_usd(
        entry_price=position.average_entry_price,
        stop_price=stop_price,
        quantity=position.quantity,
    )
    if loss > MAX_LOSS_PER_TRADE_USD:
        spread = position.average_entry_price - stop_price
        allowed = (MAX_LOSS_PER_TRADE_USD / spread).quantize(
            QUANTITY_PLACES, rounding="ROUND_DOWN"
        )
        position.quantity = allowed
        decision.quantity = allowed
        logger.warning(
            "order size reduced to %s for %s to keep the loss at %s USD",
            allowed,
            position.symbol,
            MAX_LOSS_PER_TRADE_USD,
        )

    position.stop_price = stop_price
    position.take_profit_price = take_profit_price

    active_placer = placer or _default_placer
    stop_order_id = ""
    tp_order_id = ""
    try:
        stop_order_id, tp_order_id = active_placer(
            position, stop_price, take_profit_price
        )
        if stop_order_id is None or not str(stop_order_id).strip():
            raise RuntimeError("stop order id missing after placement")
    except Exception as exc:
        position.status = PositionStatus.ERROR
        decision.status = DecisionStatus.ERROR
        register_incident(
            db,
            kind=KIND_STOP_FAILED,
            symbol=position.symbol,
            decision_id=decision.id,
            position_id=position.id,
            details={
                "error": str(exc),
                "stop_price": str(stop_price),
                "take_profit_price": str(take_profit_price),
            },
        )
        logger.warning(
            "stop placement failed for %s: %s", position.symbol, exc
        )
        db.commit()
        return position

    position.stop_order_id = str(stop_order_id)
    position.tp_order_id = str(tp_order_id) if tp_order_id else None
    position.status = PositionStatus.OPEN
    decision.stop_price = stop_price
    decision.take_profit_price = take_profit_price
    decision.status = DecisionStatus.OPENED
    db.commit()
    return position


def close_position(
    db: Session,
    *,
    position: PositionV2,
    decision: SignalDecision,
    executor: ExchangeExecutor,
    exit_price: Decimal,
    expected_price: Decimal | None,
    reason: str,
) -> PositionV2:
    """Fill the exit, cancel the opposite order and persist the result.

    `reason` is `stop`, `tp` or `manual`; `expected_price` is the price
    the slippage check compares against (RF-24).
    """
    if not isinstance(exit_price, Decimal):
        raise TypeError("exit_price must be Decimal")
    if expected_price is not None and not isinstance(
        expected_price, Decimal
    ):
        raise TypeError("expected_price must be Decimal")
    if reason not in _EXIT_STATUS:
        raise ValueError("reason must be stop, tp or manual.")

    fill = executor.place_order(
        OrderRequest(
            symbol=position.symbol,
            side="SELL",
            order_type="LIMIT",
            quantity=position.quantity,
            price=exit_price,
            client_order_id=f"exit-{decision.client_order_id}",
        )
    )
    executed = (
        fill.average_price
        if fill.average_price is not None
        else exit_price
    )
    sold = (
        fill.executed_quantity
        if fill.executed_quantity > 0
        else position.quantity
    )
    exit_fee = (
        fill.fee
        if fill.fee is not None
        else money(
            sold * executed * settings.simulation_fee_rate
        )
    )
    entry_fee = position.entry_fee_usd
    pnl = money(
        sold * (executed - position.average_entry_price)
        - entry_fee
        - exit_fee
    )
    fees = money(entry_fee + exit_fee)

    _record_slippage(
        db,
        expected=expected_price,
        executed=executed,
        phase="exit",
        symbol=position.symbol,
        decision_id=decision.id,
        position_id=position.id,
    )

    # One exit fills → the opposite order is cancelled (RF-13).
    if reason == "stop":
        position.tp_order_id = None
    elif reason == "tp":
        position.stop_order_id = None
    else:
        position.stop_order_id = None
        position.tp_order_id = None

    now = utc_now()
    position.status = _EXIT_STATUS[reason]
    position.closed_at = now
    decision.status = DecisionStatus.CLOSED
    decision.closed_at = now
    decision.fees_usd = fees
    decision.pnl_usd = pnl
    db.commit()

    # Spec 005, RF-1: toda salida (stop/tp/manual) deja su evento de orden.
    emit(
        service="order_lifecycle",
        event="order.filled",
        result="ok",
        asset=position.symbol,
        correlation_id=_decision_correlation(decision),
        payload={
            "side": "SELL",
            "reason": reason,
            "decision_id": decision.id,
            "position_id": position.id,
            "pnl_usd": str(pnl),
        },
        db=db,
    )
    return position


def _decision_correlation(decision: SignalDecision) -> str | None:
    """Correlation_id del ciclo que creó la decisión, si existe (RF-2)."""
    try:
        snapshot = json.loads(decision.market_snapshot_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get("correlation_id")
    return str(value) if value is not None else None


def check_exits(
    db: Session,
    *,
    position: PositionV2,
    decision: SignalDecision,
    executor: ExchangeExecutor,
    current_price: Decimal,
) -> PositionV2 | None:
    """Close the position when the current price touches stop or tp."""
    if not isinstance(current_price, Decimal):
        raise TypeError("current_price must be Decimal")
    if position.status != PositionStatus.OPEN:
        return None
    if position.stop_price is None or position.take_profit_price is None:
        return None

    if current_price <= position.stop_price:
        return close_position(
            db,
            position=position,
            decision=decision,
            executor=executor,
            exit_price=position.stop_price,
            expected_price=position.stop_price,
            reason="stop",
        )
    if current_price >= position.take_profit_price:
        return close_position(
            db,
            position=position,
            decision=decision,
            executor=executor,
            exit_price=position.take_profit_price,
            expected_price=position.take_profit_price,
            reason="tp",
        )
    return None

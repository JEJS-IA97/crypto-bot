"""Almacén de decisiones y métricas del panel (spec 001, RF-10, RF-17, RF-18).

Persiste cada decisión al emitirla (RF-10, primer momento) con su snapshot de
mercado y configuración; el resultado (fills, comisiones, PnL, fechas de
apertura/cierre) lo escriben los servicios de ciclo de vida sobre la misma fila
(RF-10, segundo momento). `get_metrics` calcula el panel (RF-17) solo con
consultas locales: latencia ≤5 s y ningún I/O de red.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    DailyRiskState,
    DecisionOrigin,
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
    SimulationMarketPrice,
    TradeSide,
    utc_now,
)
from app.services.simulation_service import get_balance_record, money

_HUNDRED = Decimal("100")
_DRAWDOWN_PLACES = Decimal("0.01")


def record_decision(
    db: Session,
    *,
    symbol: str,
    side: TradeSide,
    origin: DecisionOrigin,
    config: dict,
    snapshot: dict,
    source: str | None = None,
    quantity: Decimal | None = None,
    price: Decimal | None = None,
    client_order_id: str | None = None,
) -> SignalDecision:
    """Persiste la decisión al emitirla (RF-10): estado PENDING + snapshot.

    `client_order_id` autogenerado (prefijo ``bot-``, ≤36 caracteres) es el
    mismo que viaja a la exchange para la idempotencia de órdenes (RF-25).
    Decimales y fechas dentro de config/snapshot se serializan como texto
    (constitución #11: no se pierde precisión en el JSON).
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    if not isinstance(side, TradeSide):
        raise TypeError("side must be a TradeSide")
    if not isinstance(origin, DecisionOrigin):
        raise TypeError("origin must be a DecisionOrigin")
    for name, value in (("quantity", quantity), ("price", price)):
        if value is not None and not isinstance(value, Decimal):
            raise TypeError(f"{name} must be a Decimal")

    decision = SignalDecision(
        client_order_id=client_order_id or f"bot-{uuid.uuid4().hex}",
        symbol=symbol.strip(),
        side=side,
        origin=origin,
        source=source,
        config_json=json.dumps(config, default=str),
        market_snapshot_json=json.dumps(snapshot, default=str),
        status=DecisionStatus.PENDING,
        quantity=quantity,
        price=price,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def mark_rejected(
    db: Session,
    decision: SignalDecision,
    reason: str,
) -> SignalDecision:
    """Marca una decisión como rechazada con su motivo visible (RF-18)."""
    decision.status = DecisionStatus.REJECTED
    decision.rejection_reason = reason
    db.commit()
    db.refresh(decision)
    return decision


def list_decisions(
    db: Session,
    *,
    symbol: str | None = None,
    status: DecisionStatus | None = None,
    created_day: date | None = None,
    limit: int = 100,
) -> list[SignalDecision]:
    """Historial de decisiones, más recientes primero (RF-18).

    Filtros opcionales: par, estado y día UTC de creación (panel).
    """
    statement = select(SignalDecision).order_by(
        SignalDecision.created_at.desc(),
        SignalDecision.id.desc(),
    )
    if symbol is not None:
        statement = statement.where(SignalDecision.symbol == symbol)
    if status is not None:
        statement = statement.where(SignalDecision.status == status)
    if created_day is not None:
        start = datetime(created_day.year, created_day.month, created_day.day)
        statement = statement.where(
            SignalDecision.created_at >= start,
            SignalDecision.created_at < start + timedelta(days=1),
        )
    statement = statement.limit(limit)
    return list(db.scalars(statement).all())


def get_metrics(
    db: Session,
    *,
    account_id: int,
    day: date | None = None,
    initial_equity: Decimal | None = None,
) -> dict[str, Any]:
    """Métricas del panel (RF-17) con latencia ≤5 s y sin red.

    - saldo: caja disponible + valor de mercado de las posiciones abiertas;
    - PnL no realizado: solo se usa el precio de mercado si existe (nunca se
      inventa un precio);
    - PnL realizado: suma de los resultados de las decisiones cerradas (los
      mismos que escribe el ciclo de vida, RF-10);
    - drawdown: curva de patrimonio ``initial_equity + PnL cerrado`` en orden
      de cierre; se mide la caída desde el máximo (pico) alcanzado;
    - aperturas, pérdida y bloqueo del día: fila de riesgo diario si existe
      (esta función solo lee, nunca crea ni bloquea).

    `initial_equity` por defecto es el capital configurado
    (``settings.configured_capital_usd``); el ciclo lo pasará con el
    patrimonio real del día.
    """
    current_day = day if day is not None else utc_now().date()
    equity_start = (
        initial_equity
        if initial_equity is not None
        else settings.configured_capital_usd
    )
    if not isinstance(equity_start, Decimal):
        raise TypeError("initial_equity must be a Decimal")

    balance = get_balance_record(db, account_id)

    open_positions = list(
        db.scalars(
            select(PositionV2).where(
                PositionV2.account_id == account_id,
                PositionV2.status == PositionStatus.OPEN,
            )
        ).all()
    )
    symbols = [position.symbol for position in open_positions]
    price_rows = (
        list(
            db.scalars(
                select(SimulationMarketPrice).where(
                    SimulationMarketPrice.symbol.in_(symbols)
                )
            ).all()
        )
        if symbols
        else []
    )
    price_by_symbol = {row.symbol: row.price_usd for row in price_rows}

    market_value = Decimal("0")
    unrealized = Decimal("0")
    for position in open_positions:
        price = price_by_symbol.get(position.symbol)
        if price is None:
            continue
        market_value += position.quantity * price
        unrealized += position.quantity * (
            price - position.average_entry_price
        )

    closed = list(
        db.scalars(
            select(SignalDecision)
            .where(
                SignalDecision.status == DecisionStatus.CLOSED,
                SignalDecision.pnl_usd.is_not(None),
            )
            .order_by(
                SignalDecision.closed_at.asc(),
                SignalDecision.id.asc(),
            )
        ).all()
    )
    realized = Decimal("0")
    equity_curve = [equity_start]
    peak = equity_start
    drawdown_worst = Decimal("0")
    for decision in closed:
        realized += decision.pnl_usd or Decimal("0")
        equity = equity_curve[-1] + (decision.pnl_usd or Decimal("0"))
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        if peak > 0:
            drop = (peak - equity) * _HUNDRED / peak
            if drop > drawdown_worst:
                drawdown_worst = drop

    daily = db.scalar(
        select(DailyRiskState).where(DailyRiskState.day == current_day)
    )
    if daily is None:
        opens_today = 0
        daily_pnl = Decimal("0")
        daily_blocked = False
        block_reason = None
    else:
        opens_today = daily.opens_count
        daily_pnl = daily.realized_pnl_usd
        daily_blocked = daily.blocked
        block_reason = daily.block_reason

    daily_loss = -daily_pnl if daily_pnl < 0 else Decimal("0")
    available = balance.available_usd

    return {
        "generated_at": utc_now().isoformat(),
        "available_usd": money(available),
        "market_value_usd": money(market_value),
        "balance_usd": money(available + market_value),
        "open_positions": len(open_positions),
        "realized_pnl_usd": money(realized),
        "unrealized_pnl_usd": money(unrealized),
        "drawdown_pct": drawdown_worst.quantize(
            _DRAWDOWN_PLACES,
            rounding=ROUND_HALF_UP,
        ),
        "opens_today": opens_today,
        "daily_realized_pnl_usd": money(daily_pnl),
        "daily_loss_usd": money(daily_loss),
        "daily_blocked": daily_blocked,
        "block_reason": block_reason,
    }

"""Informe diario en texto plano para el correo (spec 002, RF-3, RF-5).

Todas las secciones están siempre presentes en la salida; cuando la fuente
de datos no existe (sin cuenta de paper, sin fila de riesgo, sin decisiones)
se imprime «sin datos» en lugar de fallar, porque el informe tiene que salir
aunque el bot esté vacío, detenido o bloqueado (RF-5). Ningún valor pasa
por `float` (constitución #11): las métricas llegan ya cuantizadas con
`money()` (8 decimales) desde `decision_store.get_metrics` (RF-17).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.risk_math import MAX_OPEN_POSITIONS
from app.models import (
    BotRuntime,
    DecisionStatus,
    SignalDecision,
    SimulationBalance,
    utc_now,
)
from app.services.decision_store import get_metrics
from app.services.phase_service import get_phase
from app.services.risk_guard_service import MAX_OPENS_PER_DAY, get_runtime

_EXECUTED_STATUSES = frozenset(
    {
        DecisionStatus.OPENED,
        DecisionStatus.CLOSED,
    }
)


def build_daily_report(
    db: Session,
    *,
    account_id: int | None = None,
    now: datetime | None = None,
) -> str:
    """Compone el informe del día (texto plano en español, UTF-8).

    `account_id` por defecto es la cuenta de paper-trading y `now` el
    instante UTC actual; ambos son parámetros para poder testear.
    """
    account = (
        account_id
        if account_id is not None
        else settings.simulation_bot_account_id
    )
    moment = now if now is not None else utc_now()

    lines = [
        f"Informe diario — crypto-bot — {moment.strftime('%Y-%m-%d')} (UTC)"
    ]

    phase = get_phase(db)
    lines.append(f"Fase: {phase.phase.value}")

    runtime = get_runtime(db)
    lines.append(f"Estado: {_state_text(runtime)}")

    balance = db.scalar(
        select(SimulationBalance).where(
            SimulationBalance.account_id == account
        )
    )
    metrics = (
        get_metrics(db, account_id=account, day=moment.date())
        if balance is not None
        else None
    )
    lines.extend(_balance_and_pnl_lines(metrics))
    lines.append(_daily_line(metrics))

    lines.append(_summary_line(db, moment))
    lines.append(_breaker_text(runtime))
    return "\n".join(lines)


def _num(value: Decimal) -> str:
    """Formatea un `Decimal` en notación fija sin pasar por `float`.

    `money()` devuelve `Decimal('0E-8')` para el cero, cuyo `str` sería
    «0E-8»; con `f` sale «0.00000000» (constitución #11).
    """
    return format(value, "f")


def _state_text(runtime: BotRuntime) -> str:
    """activo | detenido | bloqueado (motivo): el breaker manda sobre `running`."""
    if runtime.breaker_active:
        reason = runtime.breaker_reason or "circuito abierto"
        return f"bloqueado ({reason})"
    if not runtime.running:
        return "detenido"
    return "activo"


def _balance_and_pnl_lines(
    metrics: dict[str, Any] | None,
) -> list[str]:
    if metrics is None:
        return [
            "Balance: sin datos",
            "PnL: sin datos",
        ]
    return [
        (
            "Balance: "
            f"disponible {_num(metrics['available_usd'])} USDT | "
            f"posiciones {_num(metrics['market_value_usd'])} USDT | "
            f"total {_num(metrics['balance_usd'])} USDT"
        ),
        (
            "PnL: "
            f"realizado {_num(metrics['realized_pnl_usd'])} USDT | "
            f"no realizado {_num(metrics['unrealized_pnl_usd'])} USDT | "
            f"drawdown {_num(metrics['drawdown_pct'])}%"
        ),
    ]


def _daily_line(metrics: dict[str, Any] | None) -> str:
    if metrics is None:
        return "Día UTC: sin datos"
    if metrics["daily_blocked"]:
        reason = metrics["block_reason"]
        detail = (
            f"(bloqueado: sí — {reason})"
            if reason
            else "(bloqueado: sí)"
        )
    else:
        detail = "(bloqueado: no)"
    return (
        f"Día UTC: pérdida {_num(metrics['daily_loss_usd'])} USDT {detail} | "
        f"aperturas {metrics['opens_today']}/{MAX_OPENS_PER_DAY} | "
        f"posiciones abiertas {metrics['open_positions']}/{MAX_OPEN_POSITIONS}"
    )


def _summary_line(db: Session, moment: datetime) -> str:
    """Resumen de las últimas 24 h: recuento por estado y motivos de rechazo."""
    since = moment - timedelta(hours=24)
    recent = list(
        db.scalars(
            select(SignalDecision)
            .where(SignalDecision.created_at >= since)
            .order_by(
                SignalDecision.created_at.asc(),
                SignalDecision.id.asc(),
            )
        ).all()
    )
    total = len(recent)
    if total == 0:
        return "Últimas 24 h: sin datos (0 decisiones)"

    executed = sum(
        1 for decision in recent if decision.status in _EXECUTED_STATUSES
    )
    rejected = sum(
        1
        for decision in recent
        if decision.status == DecisionStatus.REJECTED
    )
    pending = sum(
        1
        for decision in recent
        if decision.status == DecisionStatus.PENDING
    )
    errors = sum(
        1
        for decision in recent
        if decision.status == DecisionStatus.ERROR
    )

    noun = "decisión" if total == 1 else "decisiones"
    line = (
        f"Últimas 24 h: {total} {noun} — "
        f"ejecutadas {executed}, rechazadas {rejected}, "
        f"pendientes {pending}, con error {errors}"
    )

    reasons: Counter[str] = Counter(
        decision.rejection_reason
        for decision in recent
        if decision.status == DecisionStatus.REJECTED
        and decision.rejection_reason
    )
    if reasons:
        ordered = sorted(
            reasons.items(),
            key=lambda item: (-item[1], item[0]),
        )
        joined = ", ".join(
            f"{reason} ({count})" for reason, count in ordered
        )
        line += f" — motivos: {joined}"
    return line


def _breaker_text(runtime: BotRuntime) -> str:
    if runtime.breaker_active:
        reason = runtime.breaker_reason or "sin motivo"
        return f"Breaker: activo ({reason})"
    return "Breaker: inactivo"

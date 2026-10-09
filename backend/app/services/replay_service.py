"""Inspección de decisiones: Why? y replay (spec 009, RF-4/RF-5).

Solo lectura sobre datos ya persistidos (D-3): snapshot de la decisión,
eventos 005 por correlation_id, ``ai_evaluations`` y posiciones. Lo no
guardado se declara en ``unavailable`` con motivo; nunca se inventa
texto (§35) ni se responde 500 por datos ausentes.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AiEvaluation,
    PositionV2,
    SignalDecision,
    SystemEvent,
)

_RISK_EVENT = "risk.evaluated"
_RISK_SERVICE = "risk_engine"


def _decimal_text(value: Decimal) -> str:
    """Texto sin notación científica ni ceros sobrantes (patrón 008)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return _decimal_text(value)
    return str(value)


def _parse_json(raw: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _decision_correlation(decision: SignalDecision) -> str | None:
    snapshot = _parse_json(decision.market_snapshot_json)
    value = snapshot.get("correlation_id")
    return str(value) if value is not None else None


def _decision_block(decision: SignalDecision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "symbol": decision.symbol,
        "side": decision.side.value,
        "status": decision.status.value,
        "rejection_reason": decision.rejection_reason,
        "quantity": _text(decision.quantity),
        "price": _text(decision.price),
        "stop_price": _text(decision.stop_price),
        "take_profit_price": _text(decision.take_profit_price),
        "pnl_usd": _text(decision.pnl_usd),
        "created_at": decision.created_at,
        "filled_at": decision.filled_at,
        "closed_at": decision.closed_at,
    }


def _latest_ai(
    db: Session, correlation_id: str
) -> AiEvaluation | None:
    return db.scalars(
        select(AiEvaluation)
        .where(AiEvaluation.correlation_id == correlation_id)
        .order_by(
            AiEvaluation.created_at.desc(),
            AiEvaluation.id.desc(),
        )
        .limit(1)
    ).first()


def _latest_risk_event(
    db: Session, correlation_id: str
) -> SystemEvent | None:
    return db.scalars(
        select(SystemEvent)
        .where(
            SystemEvent.correlation_id == correlation_id,
            SystemEvent.service == _RISK_SERVICE,
            SystemEvent.event == _RISK_EVENT,
        )
        .order_by(
            SystemEvent.created_at.desc(),
            SystemEvent.id.desc(),
        )
        .limit(1)
    ).first()


def _ai_block(row: AiEvaluation) -> dict[str, Any]:
    response = _parse_json(row.response_json)
    return {
        "decision": row.decision,
        "direction": row.direction,
        "confidence": _text(row.confidence),
        "model": row.model,
        "prompt_version": row.prompt_version,
        "latency_ms": row.latency_ms,
        "cost_usd": _text(row.cost_usd),
        "risk_flags": response.get("risk_flags") or [],
        "created_at": row.created_at,
    }


def _risk_block(event: SystemEvent) -> dict[str, Any]:
    payload = _parse_json(event.payload_json)
    keys = (
        "action",
        "reason",
        "requested_usd",
        "allowed_usd",
        "committed_usd",
        "open_positions",
    )
    return {key: payload.get(key) for key in keys}


def why_payload(
    db: Session, decision: SignalDecision
) -> dict[str, Any]:
    """Payload del panel "Why?" (spec 009, RF-4).

    Factores positivos/negativos provienen de ``supporting_factors`` y
    ``contradicting_factors`` de la última evaluación IA de la
    correlation_id; los indicadores del snapshot se exponen crudos (sin
    inventar signos). Secciones sin dato → ``unavailable`` con motivo.
    """
    snapshot = _parse_json(decision.market_snapshot_json)
    correlation_id = _decision_correlation(decision)
    unavailable: list[dict[str, str]] = []

    if correlation_id is None:
        reason = "sin correlation_id en el snapshot"
        unavailable.append({"section": "ai", "reason": reason})
        unavailable.append({"section": "risk", "reason": reason})
        ai_row = None
        risk_event = None
    else:
        ai_row = _latest_ai(db, correlation_id)
        risk_event = _latest_risk_event(db, correlation_id)
        if ai_row is None:
            unavailable.append(
                {
                    "section": "ai",
                    "reason": "sin evaluación IA para esta decisión",
                }
            )
        if risk_event is None:
            unavailable.append(
                {
                    "section": "risk",
                    "reason": "sin evento risk.evaluated",
                }
            )

    positive: list[str] = []
    negative: list[str] = []
    if ai_row is not None:
        response = _parse_json(ai_row.response_json)
        positive = [
            str(item) for item in response.get("supporting_factors") or []
        ]
        negative = [
            str(item)
            for item in response.get("contradicting_factors") or []
        ]

    indicators = snapshot.get("indicators")
    if not isinstance(indicators, dict):
        indicators = {}

    return {
        "decision": _decision_block(decision),
        "factors": {
            "positive": positive,
            "negative": negative,
            "indicators": indicators,
        },
        "ai": _ai_block(ai_row) if ai_row is not None else None,
        "risk": (
            _risk_block(risk_event) if risk_event is not None else None
        ),
        "outcome": {
            "status": decision.status.value,
            "pnl_usd": _text(decision.pnl_usd),
        },
        "unavailable": unavailable,
    }


def _event_block(row: SystemEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "level": row.level,
        "service": row.service,
        "event": row.event,
        "asset": row.asset,
        "correlation_id": row.correlation_id,
        "latency_ms": row.latency_ms,
        "result": row.result,
        "payload": _parse_json(row.payload_json),
    }


def _snapshot_block(decision: SignalDecision) -> dict[str, Any]:
    snapshot = _parse_json(decision.market_snapshot_json)
    indicators = snapshot.get("indicators")
    candles = snapshot.get("candles")
    return {
        "price": snapshot.get("price"),
        "timestamp": snapshot.get("timestamp"),
        "indicators": (
            indicators if isinstance(indicators, dict) else {}
        ),
        "candles": candles if isinstance(candles, list) else [],
        "config": _parse_json(decision.config_json),
        "correlation_id": snapshot.get("correlation_id"),
    }


def _position_block(position: PositionV2) -> dict[str, Any]:
    return {
        "symbol": position.symbol,
        "quantity": _text(position.quantity),
        "average_entry_price": _text(position.average_entry_price),
        "stop_price": _text(position.stop_price),
        "take_profit_price": _text(position.take_profit_price),
        "status": position.status.value,
        "opened_at": position.opened_at,
        "closed_at": position.closed_at,
    }


def replay_payload(
    db: Session, decision: SignalDecision
) -> dict[str, Any]:
    """Reconstrucción determinista de la decisión (spec 009, RF-5).

    Orden temporal ascendente de eventos; sin correlation_id o sin
    eventos registrados las secciones van a ``unavailable`` con motivo
    (purga o fuera de retención); mismo input ⇒ misma respuesta.
    """
    correlation_id = _decision_correlation(decision)
    unavailable: list[dict[str, str]] = []

    events: list[dict[str, Any]] = []
    ai_row: AiEvaluation | None = None

    if correlation_id is None:
        reason = "sin correlation_id en el snapshot"
        unavailable.append({"section": "events", "reason": reason})
        unavailable.append({"section": "ai", "reason": reason})
    else:
        rows = db.scalars(
            select(SystemEvent)
            .where(SystemEvent.correlation_id == correlation_id)
            .order_by(
                SystemEvent.created_at.asc(),
                SystemEvent.id.asc(),
            )
        ).all()
        events = [_event_block(row) for row in rows]
        if not rows:
            unavailable.append(
                {
                    "section": "events",
                    "reason": (
                        "sin eventos registrados (purga o fuera de "
                        "retención)"
                    ),
                }
            )
        ai_row = _latest_ai(db, correlation_id)
        if ai_row is None:
            unavailable.append(
                {
                    "section": "ai",
                    "reason": "sin evaluación IA para esta decisión",
                }
            )

    position = db.scalars(
        select(PositionV2).where(
            PositionV2.decision_id == decision.id
        )
    ).first()

    return {
        "decision": _decision_block(decision),
        "snapshot": _snapshot_block(decision),
        "events": events,
        "ai_evaluation": (
            _ai_block(ai_row) if ai_row is not None else None
        ),
        "position": (
            _position_block(position) if position is not None else None
        ),
        "outcome": {
            "status": decision.status.value,
            "pnl_usd": _text(decision.pnl_usd),
            "filled_at": decision.filled_at,
            "closed_at": decision.closed_at,
        },
        "unavailable": unavailable,
    }

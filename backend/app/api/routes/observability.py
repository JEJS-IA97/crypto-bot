"""Endpoints de observabilidad (spec 005, RF-5/RF-6/RF-7).

Solo lectura → sin token (RF-20 de la spec 001 distingue las rutas que
operan/reconfiguran de las que solo leen). Nunca devuelven secretos: el
payload ya se redacta al persistir (RF-4).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SystemEvent
from app.services.observability_service import (
    aggregates_24h,
    pipeline_state,
    sources_state,
)

router = APIRouter(
    prefix="/api/bot",
    tags=["Observability"],
)

DEFAULT_EVENTS_LIMIT = 50
MAX_EVENTS_LIMIT = 200


def clamp_limit(limit: int) -> int:
    """RF-6: el límite se acota a [1, 200]."""
    return max(1, min(limit, MAX_EVENTS_LIMIT))


def _event_payload(row: SystemEvent) -> dict:
    try:
        payload = json.loads(row.payload_json or "{}")
    except (TypeError, ValueError):
        payload = {"raw": row.payload_json}
    if not isinstance(payload, dict):
        payload = {"value": payload}
    return {
        "id": row.id,
        "created_at": row.created_at,
        "level": row.level,
        "service": row.service,
        "event": row.event,
        "asset": row.asset,
        "correlation_id": row.correlation_id,
        "mode": row.mode,
        "latency_ms": row.latency_ms,
        "result": row.result,
        "payload": payload,
    }


@router.get("/events")
def list_events(
    limit: int = DEFAULT_EVENTS_LIMIT,
    level: str | None = None,
    asset: str | None = None,
    correlation_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """RF-6: eventos más recientes con filtros opcionales."""
    statement = select(SystemEvent)
    if level:
        statement = statement.where(SystemEvent.level == level)
    if asset:
        statement = statement.where(SystemEvent.asset == asset)
    if correlation_id:
        statement = statement.where(
            SystemEvent.correlation_id == correlation_id
        )
    statement = (
        statement.order_by(
            SystemEvent.created_at.desc(),
            SystemEvent.id.desc(),
        )
        .limit(clamp_limit(limit))
    )
    rows = db.scalars(statement).all()
    return {"events": [_event_payload(row) for row in rows]}


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> dict:
    """RF-5: estado de salud de las fuentes de datos."""
    return {"sources": sources_state(db)}


@router.get("/observability")
def observability_metrics(db: Session = Depends(get_db)) -> dict:
    """RF-7: agregados técnicos de las últimas 24 h."""
    return aggregates_24h(db)


@router.get("/pipeline")
def pipeline_nodes(db: Session = Depends(get_db)) -> dict:
    """Spec 009 RF-2: canvas de nodos del pipeline (catálogo fijo)."""
    return {"nodes": pipeline_state(db)}

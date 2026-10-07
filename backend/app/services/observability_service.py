"""Persistencia y agregados de observabilidad (spec 005, RF-3/RF-5/RF-7/RF-8).

Todo funciona sobre la sesión que recibe (sin sesiones nuevas por evento,
RNF-2) y cualquier fallo lo traga el ``emit()`` de ``structured_log`` (D-3).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SourceHealth, SystemEvent, utc_now
from app.services.structured_log import redact

#: Fuentes que consume el sistema hoy (RF-5). Sin fila o sin uso: DISABLED.
KNOWN_SOURCES: tuple[str, ...] = (
    "binance_klines",
    "binance_exchange_info",
    "binance_ticker",
    "binance_depth",
    "fear_greed",
    "news_rss",
    "database",
)

#: Limite duro de ``payload_json`` en bytes (RF-3, RNF-2).
PAYLOAD_MAX_BYTES = 4096

#: Una fuente sin exito reciente se marca STALE (RF-5).
STALE_AFTER_SECONDS = 300

#: Niveles que cuentan en ``events_by_level`` (RF-7).
_LEVELS: tuple[str, ...] = ("INFO", "WARNING", "ERROR")


def _cap_payload(serialized: str) -> str:
    """Trunca el JSON del payload a ``PAYLOAD_MAX_BYTES`` (RNF-2).

    Si no cabe, se empaqueta como ``{"truncated": true, "preview": ...}``
    garantizando que el resultado codificado tambiA©n quepa.
    """
    if len(serialized.encode("utf-8")) <= PAYLOAD_MAX_BYTES:
        return serialized

    overhead = len(
        json.dumps({"truncated": True, "preview": ""}).encode("utf-8")
    )
    budget = PAYLOAD_MAX_BYTES - overhead - 8
    preview = (
        serialized.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
    )
    output = json.dumps(
        {"truncated": True, "preview": preview}, ensure_ascii=False
    )
    while len(output.encode("utf-8")) > PAYLOAD_MAX_BYTES and preview:
        preview = preview[:-1]
        output = json.dumps(
            {"truncated": True, "preview": preview}, ensure_ascii=False
        )
    return output


def record_event(
    db: Session,
    *,
    level: str,
    service: str,
    event: str,
    result: str,
    asset: str | None = None,
    correlation_id: str | None = None,
    mode: str | None = None,
    latency_ms: int | None = None,
    payload: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> SystemEvent:
    """Persiste un evento observable (RF-3) con payload redactado (RF-4)."""
    clean_payload = redact(payload) if payload else {}
    serialized = json.dumps(clean_payload, ensure_ascii=False, default=str)
    row = SystemEvent(
        created_at=created_at if created_at is not None else utc_now(),
        level=level,
        service=service,
        event=event,
        asset=asset,
        correlation_id=correlation_id,
        mode=mode or "unknown",
        latency_ms=latency_ms,
        result=result,
        payload_json=_cap_payload(serialized),
    )
    db.add(row)
    db.commit()
    return row


def mark_source(
    db: Session,
    name: str,
    *,
    ok: bool,
    error: str = "",
    now: datetime | None = None,
) -> SourceHealth:
    """Actualiza la salud de una fuente: exito -> HEALTHY, fallo -> ERROR."""
    moment = now if now is not None else utc_now()
    row = db.get(SourceHealth, name)
    if row is None:
        row = SourceHealth(name=name)
        db.add(row)
    if ok:
        row.state = "HEALTHY"
        row.last_success_at = moment
        row.last_error = None
    else:
        row.state = "ERROR"
        row.last_error = (error or "unknown error")[:200]
    row.updated_at = moment
    db.commit()
    return row


def sources_state(db: Session) -> list[dict[str, Any]]:
    """Estado efectivo de cada fuente conocida (RF-5).

    HEALTHY con A?ltimo A©xito antiguo se deriva a STALE; las fuentes sin
    fila todavA­a nunca usadas salen DISABLED.
    """
    rows = {
        row.name: row
        for row in db.scalars(select(SourceHealth)).all()
    }
    now = utc_now()
    states: list[dict[str, Any]] = []
    for name in KNOWN_SOURCES:
        row = rows.get(name)
        if row is None:
            states.append(
                {
                    "name": name,
                    "state": "DISABLED",
                    "last_success_at": None,
                    "last_error": None,
                    "updated_at": None,
                }
            )
            continue
        state = row.state
        if (
            state == "HEALTHY"
            and row.last_success_at is not None
            and (now - row.last_success_at).total_seconds()
            > STALE_AFTER_SECONDS
        ):
            state = "STALE"
        states.append(
            {
                "name": row.name,
                "state": state,
                "last_success_at": row.last_success_at,
                "last_error": row.last_error,
                "updated_at": row.updated_at,
            }
        )
    return states


def purge_old_events(
    db: Session,
    *,
    now: datetime | None = None,
    retention_days: int | None = None,
) -> int:
    """Elimina eventos mA?s antiguos que la retenciA3n; devuelve cuA?ntos (RF-8)."""
    days = (
        retention_days
        if retention_days is not None
        else settings.event_retention_days
    )
    moment = now if now is not None else utc_now()
    cutoff = moment - timedelta(days=days)
    outcome = db.execute(
        delete(SystemEvent).where(SystemEvent.created_at < cutoff)
    )
    db.commit()
    return int(outcome.rowcount or 0)


def aggregates_24h(db: Session) -> dict[str, Any]:
    """Agregados de las A?ltimas 24 h para ``GET /api/bot/observability`` (RF-7)."""
    cutoff = utc_now() - timedelta(hours=24)
    events = db.scalars(
        select(SystemEvent).where(SystemEvent.created_at >= cutoff)
    ).all()

    events_by_level = {level: 0 for level in _LEVELS}
    cycles_by_result: dict[str, int] = {}
    latest_error: SystemEvent | None = None

    for row in events:
        if row.level in events_by_level:
            events_by_level[row.level] += 1
        if row.event == "cycle.completed":
            cycles_by_result[row.result] = (
                cycles_by_result.get(row.result, 0) + 1
            )
        if row.level == "ERROR":
            if latest_error is None or (
                row.created_at,
                row.id,
            ) > (latest_error.created_at, latest_error.id):
                latest_error = row

    return {
        "events_by_level": events_by_level,
        "cycles_by_result": cycles_by_result,
        "last_error": (
            {
                "event": latest_error.event,
                "service": latest_error.service,
                "result": latest_error.result,
                "created_at": latest_error.created_at,
            }
            if latest_error is not None
            else None
        ),
        "sources_by_state": _sources_by_state(db),
    }


def _sources_by_state(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources_state(db):
        counts[source["state"]] = counts.get(source["state"], 0) + 1
    return counts

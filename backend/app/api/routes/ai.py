"""AI advisor endpoints (spec 007, RF-7).

Reading and on-demand analysis never require the token (same criterion
as RF-20 of spec 001). Universe is fixed to TRADING_SYMBOLS (D-3):
anything else is 404 and no state ever answers 500 (D-7).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AiEvaluation
from app.services.ai_advisor_service import ai_stats, analyze

router = APIRouter(
    prefix="/api/bot",
    tags=["AI"],
)

DEFAULT_LIMIT = 20
MIN_LIMIT = 1
MAX_LIMIT = 50


class AnalyzeRequest(BaseModel):
    symbol: str
    force: bool = False


def universe() -> tuple[str, ...]:
    """D-3: los pares de TRADING_SYMBOLS."""
    return tuple(
        symbol.strip().upper()
        for symbol in settings.trading_symbols.split(",")
        if symbol.strip()
    )


def _resolve_symbol(raw: str) -> str:
    normalized = raw.strip().upper()
    if normalized not in universe():
        raise HTTPException(
            status_code=404, detail="symbol_not_in_universe"
        )
    return normalized


def _clamp_limit(limit: int) -> int:
    return max(MIN_LIMIT, min(MAX_LIMIT, limit))


def _serialize_recommendation(row: AiEvaluation) -> dict[str, Any] | None:
    if row.status != "OK" or row.response_json in ("", "{}"):
        return None
    try:
        advice = json.loads(row.response_json)
    except ValueError:
        return None
    if not isinstance(advice, dict):
        return None
    for field in ("confidence", "setup_quality"):
        value = advice.get(field)
        if value is not None:
            advice[field] = float(value)
    return advice


def _serialize_evaluation(row: AiEvaluation) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "symbol": row.symbol,
        "trigger": row.trigger,
        "status": row.status,
        "decision": row.decision,
        "direction": row.direction,
        "confidence": (
            float(row.confidence) if row.confidence is not None else None
        ),
        "request_id": row.request_id,
        "correlation_id": row.correlation_id,
        "model": row.model,
        "prompt_version": row.prompt_version,
        "latency_ms": row.latency_ms,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "coste_usd": str(row.cost_usd),
        "error": row.error,
    }


def _serialize_list_item(row: AiEvaluation) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "created_at": row.created_at,
        "trigger": row.trigger,
        "status": row.status,
        "decision": row.decision,
        "confidence": (
            float(row.confidence) if row.confidence is not None else None
        ),
        "coste_usd": str(row.cost_usd),
        "model": row.model,
        "prompt_version": row.prompt_version,
        "latency_ms": row.latency_ms,
    }


@router.post("/ai/analyze")
def ai_analyze(
    payload: AnalyzeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-7: dictamen bajo demanda; todos los estados responden 200."""
    symbol = _resolve_symbol(payload.symbol)
    outcome = analyze(symbol, db=db, force=payload.force, trigger="manual")
    row = outcome.evaluation
    return {
        "state": outcome.state,
        "cached": outcome.cached,
        "recommendation": (
            _serialize_recommendation(row) if row is not None else None
        ),
        "evaluation": (
            _serialize_evaluation(row) if row is not None else None
        ),
    }


@router.get("/ai/recommendations")
def ai_recommendations(
    symbol: str | None = None,
    limit: int = DEFAULT_LIMIT,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-7: últimos dictámenes con clamps de límite y 404 de universo."""
    query = select(AiEvaluation)
    if symbol is not None:
        query = query.where(AiEvaluation.symbol == _resolve_symbol(symbol))
    rows = db.scalars(
        query.order_by(
            AiEvaluation.created_at.desc(),
            AiEvaluation.id.desc(),
        ).limit(_clamp_limit(limit))
    ).all()
    return {"recommendations": [_serialize_list_item(row) for row in rows]}


@router.get("/ai/stats")
def ai_stats_endpoint(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Spec 009 RF-1: agregados IA de 24 h para el header del panel."""
    return ai_stats(db)

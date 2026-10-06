"""Rutas de señales externas, webhook e historial (spec 001).

- `POST /api/signals/external` y `POST /api/webhooks/signal` (RF-8/RF-9):
  entrada Pydantic → validación completa (símbolo, lado, TTL, distancia de
  precio, duplicados, mínimo notional) → aceptada en cola `PENDING` para el
  loop o `REJECTED` con motivo visible (RF-18).
- `GET /api/signals/decisions` (RF-10/RF-18): historial con snapshot y
  resultado, incluidas las rechazadas con su motivo; filtros por fecha,
  símbolo y estado.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import require_control_token
from app.config import settings
from app.database import get_db
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,
    utc_now,
)
from app.schemas import ExternalSignalRequest
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
)
from app.services.decision_store import (
    list_decisions,
    mark_rejected,
    record_decision,
)
from app.services.external_signal_service import (
    REASON_INVALID_SIDE,
    REASON_UNKNOWN_SYMBOL,
    ExternalSignal,
    validate_external_signal,
)

router = APIRouter(
    prefix="/api",
    tags=["Signals"],
)

REASON_MARKET_DATA = "market_data_unavailable"


def _trading_symbols() -> set[str]:
    return {
        part.strip().upper()
        for part in settings.trading_symbols.split(",")
        if part.strip()
    }


def _persist_rejection(
    db: Session,
    payload: ExternalSignalRequest,
    reason: str,
) -> dict[str, Any]:
    """Guarda la señal rechazada con su motivo visible (RF-18, plan M12)."""
    symbol = payload.symbol.strip().upper() or payload.symbol
    try:
        side = TradeSide(payload.side.strip().upper())
    except ValueError:
        # El lado no válido se conserva en config; la fila usa un lado
        # válido como marcador de posición (columna NOT NULL).
        side = TradeSide.BUY
    decision = record_decision(
        db,
        symbol=symbol,
        side=side,
        origin=DecisionOrigin.EXTERNAL,
        source=payload.source,
        config={
            "raw_symbol": payload.symbol,
            "raw_side": payload.side,
            "price_limit": str(payload.price_limit)
            if payload.price_limit is not None
            else None,
            "quantity": str(payload.quantity)
            if payload.quantity is not None
            else None,
            "quantity_quote": str(payload.quantity_quote)
            if payload.quantity_quote is not None
            else None,
            "ttl_seconds": payload.ttl_seconds,
            "issued_at": payload.issued_at.isoformat()
            if payload.issued_at is not None
            else None,
        },
        snapshot={"rejected": True, "reason": reason},
    )
    mark_rejected(db, decision, reason)
    return {
        "estado": "rechazada",
        "motivo": reason,
        "symbol": symbol,
        "decision_id": decision.id,
    }


def _handle_signal(
    db: Session,
    payload: ExternalSignalRequest,
) -> dict[str, Any]:
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(
            status_code=422,
            detail="symbol no puede estar vacío.",
        )

    # Rechazos locales antes de tocar la red (fail-closed, sin HTTP inútil).
    if symbol not in _trading_symbols():
        return _persist_rejection(db, payload, REASON_UNKNOWN_SYMBOL)
    try:
        TradeSide(payload.side.strip().upper())
    except ValueError:
        return _persist_rejection(db, payload, REASON_INVALID_SIDE)

    signal = ExternalSignal(
        symbol=symbol,
        side=payload.side.strip(),
        price_limit=payload.price_limit,
        quantity=payload.quantity,
        quantity_quote=payload.quantity_quote,
        source=payload.source,
        issued_at=payload.issued_at,
        ttl_seconds=payload.ttl_seconds,
    )

    market = BinanceMarketDataClient()
    try:
        candles = market.get_klines(symbol)
        rules = market.get_exchange_info(symbol)
    except MarketDataUnavailable:
        return _persist_rejection(db, payload, REASON_MARKET_DATA)
    if not candles:
        return _persist_rejection(db, payload, REASON_MARKET_DATA)
    price = candles[-1].close

    validation = validate_external_signal(
        db,
        signal,
        now=utc_now(),
        current_price=price,
        rules=rules,
    )
    if not validation.accepted:
        return _persist_rejection(db, payload, validation.reason)

    decision = record_decision(
        db,
        symbol=validation.symbol,
        side=validation.side,
        origin=DecisionOrigin.EXTERNAL,
        source=payload.source,
        config={
            "price_limit": str(payload.price_limit)
            if payload.price_limit is not None
            else None,
            "quantity_quote": str(payload.quantity_quote)
            if payload.quantity_quote is not None
            else None,
            "ttl_seconds": payload.ttl_seconds,
            "issued_at": payload.issued_at.isoformat()
            if payload.issued_at is not None
            else None,
        },
        snapshot={
            "current_price": str(price),
            "tick_size": str(rules.tick_size),
            "step_size": str(rules.step_size),
            "min_notional": str(rules.min_notional),
        },
        quantity=validation.quantity,
        price=price,
    )
    return {
        "estado": "aceptada",
        "motivo": "",
        "symbol": decision.symbol,
        "side": decision.side.value,
        "quantity": str(decision.quantity),
        "decision_id": decision.id,
    }


@router.post("/signals/external")
def post_external_signal(
    payload: ExternalSignalRequest,
    db: Session = Depends(get_db),
    auth: None = Depends(require_control_token),
) -> dict[str, Any]:
    return _handle_signal(db, payload)


@router.post("/webhooks/signal")
def post_webhook_signal(
    payload: ExternalSignalRequest,
    db: Session = Depends(get_db),
    auth: None = Depends(require_control_token),
) -> dict[str, Any]:
    """Webhook de señal externa con el mismo contrato (RF-8, `?token=`)."""
    return _handle_signal(db, payload)


@router.get("/signals/decisions")
def get_signal_decisions(
    db: Session = Depends(get_db),
    symbol: str | None = Query(default=None),
    status: DecisionStatus | None = Query(default=None),
    day: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Historial de decisiones con snapshot y resultado (RF-10/RF-18)."""
    rows = list_decisions(
        db,
        symbol=symbol.strip().upper() if symbol else None,
        status=status,
        created_day=day,
        limit=limit,
    )
    return {"decisiones": [_serialize(decision) for decision in rows]}


def _serialize(decision: SignalDecision) -> dict[str, Any]:
    def _loads(text: str | None) -> dict[str, Any]:
        try:
            parsed = json.loads(text or "{}")
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _decimal(value) -> str | None:
        return str(value) if value is not None else None

    def _iso(value) -> str | None:
        return value.isoformat() if value is not None else None

    return {
        "id": decision.id,
        "client_order_id": decision.client_order_id,
        "symbol": decision.symbol,
        "side": decision.side.value,
        "origin": decision.origin.value,
        "source": decision.source,
        "status": decision.status.value,
        "rejection_reason": decision.rejection_reason,
        "quantity": _decimal(decision.quantity),
        "price": _decimal(decision.price),
        "stop_price": _decimal(decision.stop_price),
        "take_profit_price": _decimal(decision.take_profit_price),
        "fees_usd": _decimal(decision.fees_usd),
        "pnl_usd": _decimal(decision.pnl_usd),
        "created_at": _iso(decision.created_at),
        "filled_at": _iso(decision.filled_at),
        "closed_at": _iso(decision.closed_at),
        "config": _loads(decision.config_json),
        "snapshot": _loads(decision.market_snapshot_json),
    }

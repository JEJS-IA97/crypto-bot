"""Rutas del bot: kill switch, estado, métricas y fase (RF-3, RF-16…RF-20).

`stop`/`start` cambian `bot_runtime.running` persistido y despiertan el
loop con `controller.notify()`: el cambio es visible en ≤5 s sin reiniciar
el proceso. Con fase `TESTNET`/`LIVE` (o token configurado) exigen token
(RF-20). El token no se loguea ni se expone (RNF-4).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_control_token
from app.config import settings
from app.database import get_db
from app.domain.signal_engine import SignalAction
from app.domain.trend_engine import evaluate_trend
from app.models import PositionStatus, PositionV2, utc_now
from app.schemas import PhaseChangeRequest
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
)
from app.services.bot_loop import TREND_KLINE_LIMIT, controller
from app.services.decision_store import get_metrics
from app.services.phase_service import (
    get_phase,
    live_trading_blockers,
    request_phase_change,
)
from app.services.risk_guard_service import get_runtime, reset_breaker

router = APIRouter(
    prefix="/api/bot",
    tags=["Bot"],
)

# Cliente propio (con su caché de 30 s) para el panel de tendencia.
trend_market = BinanceMarketDataClient()


@router.post("/stop")
def stop_bot(
    db: Session = Depends(get_db),
    auth: None = Depends(require_control_token),
) -> dict[str, Any]:
    runtime = get_runtime(db)
    runtime.running = False
    db.commit()
    controller.notify()
    return {
        "running": False,
        "mensaje": "Bot detenido; no saldrán órdenes nuevas.",
    }


@router.post("/start")
def start_bot(
    db: Session = Depends(get_db),
    auth: None = Depends(require_control_token),
) -> dict[str, Any]:
    runtime = get_runtime(db)
    reset = runtime.breaker_active
    if reset:
        # RF-22: reinicio manual — arrancar cierra el breaker abierto.
        reset_breaker(db)
    runtime.running = True
    db.commit()
    controller.notify()
    return {
        "running": True,
        "mensaje": (
            "Bot arrancado; circuit breaker reiniciado."
            if reset
            else "Bot arrancado."
        ),
    }


@router.get("/status")
def bot_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Estado para el panel: fase, kill switch, breaker y bloqueos (RF-18)."""
    runtime = get_runtime(db)
    phase = get_phase(db)
    return {
        "fase": phase.phase.value,
        "running": runtime.running,
        "breaker_active": runtime.breaker_active,
        "consecutive_failures": runtime.consecutive_failures,
        "breaker_reason": runtime.breaker_reason,
        "live_blockers": live_trading_blockers(db),
    }


_ACTION_TEXT = {
    (True, False): "Comprará en el próximo ciclo",
    (True, True): "Mantiene la posición",
    (False, True): "Venderá en el próximo ciclo",
    (False, False): "En USDT, esperando",
}


@router.get("/trend")
def trend_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Qué hará el bot hoy: señal de tendencia diaria por par y su posición."""
    now = utc_now()
    pairs = []
    for symbol in [s.strip().upper() for s in settings.trend_symbols.split(",") if s.strip()]:
        position = db.scalars(
            select(PositionV2).where(
                PositionV2.account_id == settings.simulation_bot_account_id,
                PositionV2.symbol == symbol,
                PositionV2.status == PositionStatus.OPEN,
            )
        ).first()
        row: dict[str, Any] = {"symbol": symbol, "in_position": position is not None}
        try:
            daily = trend_market.get_klines(symbol, interval="1d", limit=TREND_KLINE_LIMIT)
        except MarketDataUnavailable as exc:
            row.update(signal="SIN DATOS", action=str(exc))
            pairs.append(row)
            continue
        result = evaluate_trend(daily, now)
        if result.action == SignalAction.HOLD:
            row.update(signal="SIN DATOS", action="Faltan velas diarias", **result.metrics)
        else:
            inside = result.action == SignalAction.BUY
            row.update(
                signal="DENTRO" if inside else "FUERA",
                action=_ACTION_TEXT[(inside, position is not None)],
                **result.metrics,
            )
        pairs.append(row)
    next_decision = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return {
        "enabled": settings.trend_enabled,
        "strategy": settings.strategy_version,
        "allocation_pct": str(settings.trend_allocation_pct),
        "next_decision_utc": next_decision.isoformat(),
        "pairs": pairs,
    }


@router.get("/metrics")
def bot_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Métricas del panel (RF-17): solo consultas locales, sin red."""
    return get_metrics(
        db,
        account_id=settings.simulation_bot_account_id,
    )


@router.get("/phase")
def get_bot_phase(db: Session = Depends(get_db)) -> dict[str, Any]:
    phase = get_phase(db)
    try:
        evidence = json.loads(phase.evidence_json or "{}")
    except ValueError:
        evidence = {}
    return {
        "fase": phase.phase.value,
        "changed_at": phase.changed_at.isoformat(),
        "changed_by": phase.changed_by,
        "evidencia": evidence,
    }


@router.post("/phase")
def change_bot_phase(
    payload: PhaseChangeRequest,
    db: Session = Depends(get_db),
    auth: None = Depends(require_control_token),
) -> Any:
    """Cambio manual de fase; 409 con el detalle si falla RF-16."""
    result = request_phase_change(
        db,
        new_phase=payload.phase,
        evidence=payload.evidence,
        changed_by="panel",
    )
    if not result["ok"]:
        return JSONResponse(
            status_code=409,
            content=jsonable_encoder(
                {
                    "ok": False,
                    "motivo": result["reason"],
                    "fase": result["phase"],
                    "falta": result.get("missing", []),
                    "metricas": result.get("metrics"),
                }
            ),
        )
    return {
        "ok": True,
        "fase": result["phase"],
        "mensaje": "Fase actualizada.",
        "evidencia": result["evidence"],
    }

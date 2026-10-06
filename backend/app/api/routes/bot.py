"""Rutas del bot: kill switch, estado, métricas y fase (RF-3, RF-16…RF-20).

`stop`/`start` cambian `bot_runtime.running` persistido y despiertan el
loop con `controller.notify()`: el cambio es visible en ≤5 s sin reiniciar
el proceso. Con fase `TESTNET`/`LIVE` (o token configurado) exigen token
(RF-20). El token no se loguea ni se expone (RNF-4).
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import require_control_token
from app.config import settings
from app.database import get_db
from app.schemas import PhaseChangeRequest
from app.services.bot_loop import controller
from app.services.decision_store import get_metrics
from app.services.phase_service import (
    get_phase,
    live_trading_blockers,
    request_phase_change,
)
from app.services.risk_guard_service import get_runtime

router = APIRouter(
    prefix="/api/bot",
    tags=["Bot"],
)


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
    runtime.running = True
    db.commit()
    controller.notify()
    return {
        "running": True,
        "mensaje": "Bot arrancado.",
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

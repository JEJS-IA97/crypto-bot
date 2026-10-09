"""Endpoints de inspección de decisiones (spec 009, RF-4/RF-5).

Solo lectura → sin token (criterio RF-20 de la 001): Why? y replay se
construyen únicamente con datos ya persistidos (D-3). Decisión
inexistente → 404; datos ausentes → secciones ``unavailable`` (nunca 500).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SignalDecision
from app.services.replay_service import replay_payload, why_payload

router = APIRouter(
    prefix="/api/bot",
    tags=["Decisions"],
)


def _resolve_decision(
    decision_id: int, db: Session
) -> SignalDecision:
    decision = db.get(SignalDecision, decision_id)
    if decision is None:
        raise HTTPException(
            status_code=404, detail="decision_not_found"
        )
    return decision


@router.get("/decisions/{decision_id}/why")
def decision_why(
    decision_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Spec 009 RF-4: factores, riesgo y resultado de una decisión."""
    return why_payload(db, _resolve_decision(decision_id, db))


@router.get("/decisions/{decision_id}/replay")
def decision_replay(
    decision_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Spec 009 RF-5: reconstrucción determinista de la decisión."""
    return replay_payload(db, _resolve_decision(decision_id, db))

"""Endpoint de exposición total (spec 008, RF-6).

Solo lectura → sin token (RF-20 de la spec 001 distingue las rutas que
operan de las que solo leen). Devuelve el snapshot del motor con los
decimales como texto; cuenta de simulación ausente ⇒ disponible ``null``
sin 500. Nunca escribe ni emite eventos.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.risk_engine_service import exposure_snapshot
from app.services.simulation_service import get_balance_record

router = APIRouter(
    prefix="/api/bot",
    tags=["Risk"],
)


@router.get("/risk/exposure")
def risk_exposure(db: Session = Depends(get_db)) -> dict:
    """RF-6: exposición total, por activo, por dirección y límites."""
    account_id = settings.simulation_bot_account_id
    try:
        available_usd = get_balance_record(db, account_id).available_usd
    except HTTPException:
        available_usd = None
    return exposure_snapshot(
        db, account_id=account_id, available_usd=available_usd
    )

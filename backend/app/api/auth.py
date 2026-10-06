"""Autenticación por token (spec 001, RF-20).

El token (`API_TOKEN` en entorno) protege las rutas que operan,
reconfiguran o cambian de fase: obligatorio en fases `TESTNET`/`LIVE`;
en `SIMULATION` solo se exige si el propietario configuró un token
(defecto: sin token, abierto). Se acepta por cabecera
`Authorization: Bearer <token>` o por query `?token=` (webhooks).
El token no se loguea ni se expone en respuestas (RNF-4).
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import BotPhaseName
from app.services.phase_service import get_phase


def require_control_token(
    db: Session = Depends(get_db),
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """401 salvo que el token presente coincida con `API_TOKEN`."""
    phase = get_phase(db).phase
    required = (
        phase != BotPhaseName.SIMULATION or bool(settings.api_token)
    )
    if not required:
        return

    presented = token
    if presented is None and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            presented = value.strip()

    expected = settings.api_token
    if not expected:
        raise HTTPException(
            status_code=401,
            detail="API_TOKEN no está configurado en el entorno.",
        )
    if presented is None or not secrets.compare_digest(
        presented, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Token no válido o ausente.",
        )

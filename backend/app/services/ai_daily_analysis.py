"""Pasada diaria opcional del analista IA (spec 007, RF-8).

Solo corre con ``GEMINI_AUTO_ANALYSIS=true`` y clave configurada; respeta
el guard de 24 h sobre el último intento ``trigger="auto"``, analiza el
top-N de candidatos y para en el primer estado no ``OK`` sin reintentar.
El loop de la spec 001 nunca importa este módulo (RF-5).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import AiEvaluation, utc_now
from app.services.ai_advisor_service import analyze
from app.services.binance_market_data_client import BinanceMarketDataClient
from app.services.observability_service import record_event

logger = logging.getLogger(__name__)

#: Intervalo del bucle fino cuando la pasada diaria está habilitada.
LOOP_SECONDS = 3600

#: Un intento ``auto`` más reciente que esto cancela la pasada (RF-8).
GUARD_HOURS = 24


def _trading_symbols() -> list[str]:
    return [
        symbol.strip().upper()
        for symbol in settings.trading_symbols.split(",")
        if symbol.strip()
    ]


def _guard_elapsed(db: Session, moment: datetime) -> bool:
    cutoff = moment - timedelta(hours=GUARD_HOURS)
    recent = db.scalars(
        select(AiEvaluation)
        .where(
            AiEvaluation.trigger == "auto",
            AiEvaluation.created_at >= cutoff,
        )
        .limit(1)
    ).first()
    return recent is None


def run_daily_pass(
    *,
    db: Session,
    now: datetime | None = None,
    market_data: Any | None = None,
    client: Any | None = None,
    limit: int | None = None,
) -> int:
    """Analiza el top-N de candidatos; devuelve cuántos quedaron en OK."""
    if not settings.gemini_auto_analysis:
        return 0
    if (
        not settings.gemini_api_key.strip()
        or not settings.gemini_model.strip()
    ):
        return 0

    moment = now if now is not None else utc_now()
    if not _guard_elapsed(db, moment):
        return 0

    effective = (
        limit if limit is not None else settings.gemini_auto_analysis_limit
    )
    md = (
        market_data
        if market_data is not None
        else BinanceMarketDataClient()
    )

    from app.services import candidate_service

    ranked = candidate_service.get_candidates(
        db,
        symbols=_trading_symbols(),
        now=moment,
        market_data=md,
        limit=effective,
    )
    symbols = [entry.symbol for entry in ranked.candidates[:effective]]

    analyzed = 0
    stop_state: str | None = None
    for symbol in symbols:
        outcome = analyze(
            symbol,
            db=db,
            now=moment,
            market_data=md,
            client=client,
            trigger="auto",
        )
        if outcome.state != "OK":
            stop_state = outcome.state
            break
        analyzed += 1

    record_event(
        db,
        level="WARNING" if stop_state is not None else "INFO",
        service="ai_advisor",
        event="ai.daily_analysis",
        result="stopped" if stop_state is not None else "ok",
        mode="analysis",
        payload={
            "analyzed": analyzed,
            "requested": len(symbols),
            "stop_state": stop_state,
        },
        created_at=moment,
    )
    return analyzed


async def daily_loop(*, stop_event: asyncio.Event) -> None:
    """Bucle fino que dispara ``run_daily_pass`` cada hora (RF-8)."""
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                run_daily_pass(db=db)
        except Exception:
            logger.exception("ai daily pass failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=LOOP_SECONDS)
        except TimeoutError:
            continue

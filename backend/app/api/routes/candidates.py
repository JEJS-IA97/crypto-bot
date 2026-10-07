"""Read-only context and candidate endpoints (spec 006, RF-7).

Same criterion as RF-20 of spec 001: reading never requires the token.
Universe is fixed to TRADING_SYMBOLS (D-3) — anything else is 404 — and
every numeric value is serialized as text except the score (D-7).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import candidate_service
from app.services.candidate_service import CandidatesResult
from app.services.market_context_service import ContextSnapshot, get_context
from app.services.structured_log import emit

router = APIRouter(
    prefix="/api/bot",
    tags=["Context"],
)


def universe() -> tuple[str, ...]:
    """D-3: los 8 pares de TRADING_SYMBOLS."""
    return tuple(
        symbol.strip().upper()
        for symbol in settings.trading_symbols.split(",")
        if symbol.strip()
    )


def resolve_symbols(raw: str | None) -> list[str]:
    """`?symbols=` (CSV) acotado al universo; vacío → universo completo."""
    known = universe()
    if raw is None or not raw.strip():
        return list(known)
    requested = [
        symbol.strip().upper()
        for symbol in raw.split(",")
        if symbol.strip()
    ]
    for symbol in dict.fromkeys(requested):
        if symbol not in known:
            raise HTTPException(
                status_code=404, detail="symbol_not_in_universe"
            )
    return list(dict.fromkeys(requested))


def _serialize_context(snapshot: ContextSnapshot) -> dict:
    order_book = None
    if snapshot.order_book is not None:
        book = snapshot.order_book
        order_book = {
            "spread_bps": str(book.spread_bps),
            "imbalance": str(book.imbalance),
            "bids": [
                [str(price), str(quantity)] for price, quantity in book.bids
            ],
            "asks": [
                [str(price), str(quantity)] for price, quantity in book.asks
            ],
        }

    ticker = None
    if snapshot.ticker is not None:
        ticker = {
            "last_price": str(snapshot.ticker.last_price),
            "change_pct_24h": str(snapshot.ticker.change_pct_24h),
            "quote_volume_24h": str(snapshot.ticker.quote_volume_24h),
        }

    fear_greed = None
    if snapshot.fear_greed is not None:
        fear_greed = {
            "value": snapshot.fear_greed.value,
            "label": snapshot.fear_greed.label,
        }

    return {
        "symbol": snapshot.symbol,
        "fetched_at": snapshot.fetched_at,
        "order_book": order_book,
        "ticker": ticker,
        "fear_greed": fear_greed,
        "news": [
            {
                "title": item.title,
                "url": item.url,
                "published_at": item.published_at,
            }
            for item in snapshot.news
        ],
        "sources": {
            name: {
                "state": source.state,
                "fetched_at": source.fetched_at,
                "stale": source.stale,
            }
            for name, source in snapshot.sources.items()
        },
    }


def _serialize_candidates(result: CandidatesResult) -> dict:
    """D-7: Decimals como texto; score como número."""
    return {
        "candidates": [
            {
                "symbol": entry.symbol,
                "score": float(entry.score),
                "rank": entry.rank,
                "factors": [
                    {
                        "name": factor.name,
                        "weight": str(factor.weight),
                        "normalized": str(factor.normalized),
                        "contribution": str(factor.contribution),
                    }
                    for factor in entry.factors
                ],
            }
            for entry in result.candidates
        ],
        "excluded": [
            {"symbol": entry.symbol, "filters": list(entry.filters)}
            for entry in result.excluded
        ],
        "evaluated_at": result.evaluated_at,
    }


@router.get("/context/{symbol}")
def read_context(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """RF-1: contexto por símbolo con estado y timestamps por fuente."""
    normalized = symbol.strip().upper()
    if normalized not in universe():
        raise HTTPException(
            status_code=404, detail="symbol_not_in_universe"
        )

    snapshot = get_context(normalized, db=db)
    degraded = any(
        source.state in ("ERROR", "STALE")
        for source in snapshot.sources.values()
    )
    emit(
        service="api.context",
        event="context.fetched",
        level="WARNING" if degraded else "INFO",
        result="degraded" if degraded else "ok",
        mode="advisory",
        asset=normalized,
        payload={
            "sources": {
                name: source.state
                for name, source in snapshot.sources.items()
            }
        },
        db=db,
    )
    return _serialize_context(snapshot)


@router.get("/candidates")
def read_candidates(
    symbols: str | None = None,
    limit: int = candidate_service.DEFAULT_LIMIT,
    db: Session = Depends(get_db),
) -> dict:
    """RF-6/RF-7: ranking explicado con filtros por candidato excluido."""
    resolved = resolve_symbols(symbols)
    result = candidate_service.get_candidates(
        db,
        symbols=resolved,
        limit=candidate_service.clamp_limit(limit),
    )
    return _serialize_candidates(result)

"""Candidate orchestration (spec 006, RF-5/RF-6/RF-8).

Advisory-only: klines → features → score → ranking for a caller-provided
symbol list. Failures are honest: a symbol whose data is unavailable or
whose features are incomplete is excluded with a filter, never scored with
estimated values. The loop of spec 001 is never touched (RF-9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.candidate_engine import (
    FactorContribution,
    normalize_weights,
    score_candidate,
)
from app.domain.feature_engine import compute_features
from app.models import utc_now
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
)
from app.services.observability_service import mark_source
from app.services.structured_log import emit

KLINE_INTERVAL = "15m"
KLINE_LIMIT = 200
DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 50


@dataclass(frozen=True)
class CandidateEntry:
    symbol: str
    score: Decimal
    rank: int
    factors: tuple[FactorContribution, ...]


@dataclass(frozen=True)
class ExcludedEntry:
    symbol: str
    filters: tuple[str, ...]


@dataclass(frozen=True)
class CandidatesResult:
    candidates: tuple[CandidateEntry, ...]
    excluded: tuple[ExcludedEntry, ...]
    evaluated_at: datetime


def clamp_limit(limit: int) -> int:
    """RF-7 / caso 9: el límite se acota a [1, 50]."""
    return max(MIN_LIMIT, min(limit, MAX_LIMIT))


def _mark_klines(db: Session, *, ok: bool, error: str = "") -> None:
    """RF-8: la salud de klines también se registra (fail-open)."""
    try:
        mark_source(db, "binance_klines", ok=ok, error=error)
    except Exception:
        pass


def _resolve_weights(db: Session) -> dict[str, Decimal]:
    """CANDIDATE_WEIGHTS válido o defecto + evento `config.ignored` (M8)."""
    raw = settings.candidate_weights
    weights, used_default = normalize_weights(raw)
    if used_default and raw and raw.strip():
        emit(
            service="candidate_service",
            event="config.ignored",
            level="WARNING",
            result="fallback",
            payload={"candidate_weights": raw},
            db=db,
        )
    return weights


def get_candidates(
    db: Session,
    *,
    symbols: list[str],
    now: datetime | None = None,
    market_data: Any | None = None,
    limit: int = DEFAULT_LIMIT,
) -> CandidatesResult:
    """Score and rank each symbol; excluded ones keep their filters."""
    client = (
        market_data if market_data is not None else BinanceMarketDataClient()
    )
    moment = now if now is not None else utc_now()
    weights = _resolve_weights(db)
    effective_limit = clamp_limit(limit)

    scored: list[CandidateEntry] = []
    excluded: list[ExcludedEntry] = []

    for symbol in symbols:
        try:
            candles = client.get_klines(
                symbol, interval=KLINE_INTERVAL, limit=KLINE_LIMIT
            )
        except (MarketDataUnavailable, ValueError) as exc:
            _mark_klines(db, ok=False, error=str(exc))
            excluded.append(
                ExcludedEntry(symbol=symbol, filters=("data_unavailable",))
            )
            continue
        _mark_klines(db, ok=True)

        features = compute_features(candles, now=moment)
        result = score_candidate(features, weights=weights)
        if result.missing:
            excluded.append(
                ExcludedEntry(symbol=symbol, filters=("missing_data",))
            )
            continue
        scored.append(
            CandidateEntry(
                symbol=symbol,
                score=result.score,
                rank=0,
                factors=result.factors,
            )
        )

    # RF-6: score descendente; empate → símbolo ascendente.
    scored.sort(key=lambda entry: (-entry.score, entry.symbol))
    ranked = tuple(
        CandidateEntry(
            symbol=entry.symbol,
            score=entry.score,
            rank=index + 1,
            factors=entry.factors,
        )
        for index, entry in enumerate(scored[:effective_limit])
    )
    return CandidatesResult(
        candidates=ranked,
        excluded=tuple(excluded),
        evaluated_at=moment,
    )

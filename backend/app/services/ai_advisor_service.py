"""Asesoría IA bajo demanda (spec 007, RF-1/RF-3/RF-4/RF-6).

Estados: ``OK | DISABLED | QUOTA_EXCEEDED | BUDGET_EXCEEDED |
BREAKER_OPEN | INVALID_RESPONSE | ERROR``. Solo se persiste fila cuando
hubo consulta a Gemini; los cortes locales dejan un evento WARNING. El
loop de la spec 001 nunca importa este módulo (RF-5).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.ai_schema import AdvisorResponse, SchemaViolation
from app.domain.candidate_engine import normalize_weights, score_candidate
from app.domain.feature_engine import FeatureVector, compute_features
from app.models import (
    AiEvaluation,
    DailyRiskState,
    PositionStatus,
    PositionV2,
    utc_now,
)
from app.services.binance_market_data_client import (
    BinanceMarketDataClient,
    MarketDataUnavailable,
)
from app.services.gemini_client import (
    GeminiClient,
    GeminiQuotaExceeded,
    GeminiUnavailable,
)
from app.services.market_context_service import ContextSnapshot, get_context
from app.services.observability_service import mark_source, record_event

#: Versión del prompt persistida con cada dictamen (RF-6).
PROMPT_VERSION = "007-v1"

_KLINE_INTERVAL = "15m"
_KLINE_LIMIT = 200
_COST_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class AnalysisOutcome:
    """Resultado de una consulta: estado, fila (si la hubo) y si hubo caché."""

    state: str
    evaluation: AiEvaluation | None
    cached: bool


_consecutive_failures = 0
_breaker_opened_at: datetime | None = None


def reset_state() -> None:
    """Vacía breaker y fallos consecutivos (tests y arranque del proceso)."""
    global _consecutive_failures, _breaker_opened_at
    _consecutive_failures = 0
    _breaker_opened_at = None


def analyze(
    symbol: str,
    *,
    db: Session,
    now: datetime | None = None,
    market_data: Any | None = None,
    client: Any | None = None,
    force: bool = False,
    trigger: str = "manual",
) -> AnalysisOutcome:
    """Dictamen de un símbolo: contexto honesto + Gemini + persistencia."""
    moment = now if now is not None else utc_now()

    if (
        not settings.gemini_api_key.strip()
        or not settings.gemini_model.strip()
    ):
        return AnalysisOutcome("DISABLED", None, False)

    if not force:
        cached = _cached_evaluation(db, symbol, moment)
        if cached is not None:
            return AnalysisOutcome("OK", cached, True)

    if _budget_exceeded(db, moment):
        _emit(
            db,
            state="BUDGET_EXCEEDED",
            level="WARNING",
            result="degraded",
            symbol=symbol,
            moment=moment,
        )
        return AnalysisOutcome("BUDGET_EXCEEDED", None, False)

    if _quota_exceeded(db, moment):
        _emit(
            db,
            state="QUOTA_EXCEEDED",
            level="WARNING",
            result="degraded",
            symbol=symbol,
            moment=moment,
        )
        return AnalysisOutcome("QUOTA_EXCEEDED", None, False)

    if _breaker_open(moment):
        _emit(
            db,
            state="BREAKER_OPEN",
            level="WARNING",
            result="degraded",
            symbol=symbol,
            moment=moment,
        )
        return AnalysisOutcome("BREAKER_OPEN", None, False)

    return _consult(
        db,
        symbol,
        moment,
        market_data=market_data,
        client=client,
        trigger=trigger,
    )


def _consult(
    db: Session,
    symbol: str,
    moment: datetime,
    *,
    market_data: Any | None,
    client: Any | None,
    trigger: str,
) -> AnalysisOutcome:
    correlation_id = uuid.uuid4().hex
    md = (
        market_data
        if market_data is not None
        else BinanceMarketDataClient()
    )

    try:
        candles = md.get_klines(
            symbol, interval=_KLINE_INTERVAL, limit=_KLINE_LIMIT
        )
    except (MarketDataUnavailable, ValueError) as exc:
        mark_source(db, "binance_klines", ok=False, error=str(exc), now=moment)
        _emit(
            db,
            state="ERROR",
            level="ERROR",
            result="failed",
            symbol=symbol,
            moment=moment,
            correlation_id=correlation_id,
            payload={"error": str(exc)},
        )
        return AnalysisOutcome("ERROR", None, False)
    mark_source(db, "binance_klines", ok=True, now=moment)

    features = compute_features(candles, now=moment)
    weights, _used_default = normalize_weights(settings.candidate_weights)
    score = score_candidate(features, weights=weights)
    context = _build_context(
        db,
        symbol=symbol,
        moment=moment,
        md=md,
        features=features,
        score=score,
    )
    prompt = _build_prompt(context)

    gemini = client if client is not None else GeminiClient()
    request_id = uuid.uuid4().hex
    reply = None
    advice: AdvisorResponse | None = None
    error: str | None = None
    state: str
    level: str
    result: str

    try:
        reply = gemini.generate(prompt, request_id=request_id)
    except GeminiQuotaExceeded as exc:
        state = "QUOTA_EXCEEDED"
        error = str(exc)
        level = "WARNING"
        result = "degraded"
        mark_source(db, "gemini", ok=False, error=error, now=moment)
    except GeminiUnavailable as exc:
        state = "ERROR"
        error = str(exc)
        level = "ERROR"
        result = "failed"
        mark_source(db, "gemini", ok=False, error=error, now=moment)
        _record_failure(moment)
    else:
        mark_source(db, "gemini", ok=True, now=moment)
        try:
            advice = AdvisorResponse.from_json(reply.text)
        except SchemaViolation as exc:
            state = "INVALID_RESPONSE"
            error = str(exc)
            level = "ERROR"
            result = "failed"
            mark_source(db, "gemini", ok=False, error=error, now=moment)
        else:
            state = "OK"
            level = "INFO"
            result = "ok"
            _reset_failures()

    cost = _cost_of(reply)
    row = AiEvaluation(
        symbol=symbol,
        trigger=trigger,
        status="OK" if state == "OK" else "ERROR",
        decision=advice.decision if advice is not None else None,
        direction=advice.direction if advice is not None else None,
        confidence=advice.confidence if advice is not None else None,
        request_id=(
            reply.request_id if reply is not None else request_id
        ),
        correlation_id=correlation_id,
        model=settings.gemini_model,
        prompt_version=PROMPT_VERSION,
        latency_ms=reply.latency_ms if reply is not None else None,
        input_tokens=reply.input_tokens if reply is not None else 0,
        output_tokens=reply.output_tokens if reply is not None else 0,
        cost_usd=cost,
        context_json=json.dumps(context, ensure_ascii=False, default=str),
        response_json=(
            json.dumps(
                advice.model_dump(mode="json"),
                ensure_ascii=False,
                default=str,
            )
            if advice is not None
            else "{}"
        ),
        error=error,
        created_at=moment,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    payload: dict[str, Any] = {
        "decision": row.decision,
        "request_id": request_id,
        "coste_usd": str(cost),
        "model": settings.gemini_model,
        "prompt_version": PROMPT_VERSION,
    }
    if error is not None:
        payload["error"] = error
    _emit(
        db,
        state=state,
        level=level,
        result=result,
        symbol=symbol,
        moment=moment,
        correlation_id=correlation_id,
        latency_ms=row.latency_ms,
        payload=payload,
    )
    return AnalysisOutcome(state, row, False)


def _emit(
    db: Session,
    *,
    state: str,
    level: str,
    result: str,
    symbol: str,
    moment: datetime,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    body: dict[str, Any] = {"state": state}
    if payload:
        body.update(payload)
    record_event(
        db,
        level=level,
        service="ai_advisor",
        event="ai.consultation",
        result=result,
        asset=symbol,
        correlation_id=correlation_id,
        mode="analysis",
        latency_ms=latency_ms,
        payload=body,
        created_at=moment,
    )


def _day_start(moment: datetime) -> datetime:
    return datetime.combine(moment.date(), time.min)


def _quota_exceeded(db: Session, moment: datetime) -> bool:
    used = len(
        db.scalars(
            select(AiEvaluation).where(
                AiEvaluation.created_at >= _day_start(moment)
            )
        ).all()
    )
    return used >= settings.gemini_daily_query_limit


def _budget_exceeded(db: Session, moment: datetime) -> bool:
    priced = (
        settings.gemini_price_mtok_input > 0
        or settings.gemini_price_mtok_output > 0
    )
    if not priced:
        return False
    amounts = db.scalars(
        select(AiEvaluation.cost_usd).where(
            AiEvaluation.created_at >= _day_start(moment)
        )
    ).all()
    used = sum(
        (amount for amount in amounts if amount is not None),
        Decimal("0"),
    )
    return used >= settings.gemini_daily_budget_usd


def _cached_evaluation(
    db: Session, symbol: str, moment: datetime
) -> AiEvaluation | None:
    if settings.gemini_cache_seconds <= 0:
        return None
    cutoff = moment - timedelta(seconds=settings.gemini_cache_seconds)
    rows = db.scalars(
        select(AiEvaluation)
        .where(
            AiEvaluation.symbol == symbol,
            AiEvaluation.status == "OK",
            AiEvaluation.created_at >= cutoff,
            AiEvaluation.created_at <= moment,
        )
        .order_by(AiEvaluation.created_at.desc(), AiEvaluation.id.desc())
    ).all()
    return rows[0] if rows else None


def _breaker_open(moment: datetime) -> bool:
    global _consecutive_failures, _breaker_opened_at
    if _breaker_opened_at is None:
        return False
    elapsed = (moment - _breaker_opened_at).total_seconds()
    if elapsed < settings.gemini_breaker_seconds:
        return True
    _breaker_opened_at = None
    _consecutive_failures = 0
    return False


def _record_failure(moment: datetime) -> None:
    global _consecutive_failures, _breaker_opened_at
    _consecutive_failures += 1
    if _consecutive_failures >= settings.gemini_breaker_failures:
        _breaker_opened_at = moment


def _reset_failures() -> None:
    global _consecutive_failures, _breaker_opened_at
    _consecutive_failures = 0
    _breaker_opened_at = None


def _cost_of(reply: Any) -> Decimal:
    if reply is None:
        return Decimal("0")
    total = (
        Decimal(reply.input_tokens) * settings.gemini_price_mtok_input
        + Decimal(reply.output_tokens) * settings.gemini_price_mtok_output
    ) / Decimal("1000000")
    return total.quantize(_COST_QUANTUM)


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal(1)))
    return str(normalized)


def _decimal_or_none(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _serialize_snapshot(snapshot: ContextSnapshot) -> dict[str, Any]:
    order_book = None
    if snapshot.order_book is not None:
        order_book = {
            "spread_bps": str(snapshot.order_book.spread_bps),
            "imbalance": str(snapshot.order_book.imbalance),
            "bids": [
                [str(price), str(quantity)]
                for price, quantity in snapshot.order_book.bids
            ],
            "asks": [
                [str(price), str(quantity)]
                for price, quantity in snapshot.order_book.asks
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
        "order_book": order_book,
        "ticker": ticker,
        "fear_greed": fear_greed,
        "news": [
            {
                "title": item.title,
                "url": item.url,
                "published_at": (
                    item.published_at.isoformat()
                    if item.published_at is not None
                    else None
                ),
            }
            for item in snapshot.news
        ],
        "sources": {
            name: {
                "state": source.state,
                "stale": source.stale,
                "fetched_at": (
                    source.fetched_at.isoformat()
                    if source.fetched_at is not None
                    else None
                ),
            }
            for name, source in snapshot.sources.items()
        },
    }


def _serialize_features(features: FeatureVector) -> dict[str, str | None]:
    return {
        "return_pct": _decimal_or_none(features.return_pct),
        "volatility_pct": _decimal_or_none(features.volatility_pct),
        "range_position_pct": _decimal_or_none(
            features.range_position_pct
        ),
        "volume_zscore": _decimal_or_none(features.volume_zscore),
        "ema_spread_pct": _decimal_or_none(features.ema_spread_pct),
        "rsi": _decimal_or_none(features.rsi),
    }


def _build_context(
    db: Session,
    *,
    symbol: str,
    moment: datetime,
    md: Any,
    features: FeatureVector,
    score: Any,
) -> dict[str, Any]:
    try:
        snapshot = get_context(symbol, db=db, now=moment, market_data=md)
    except Exception:
        market: dict[str, Any] | None = None
        market_quality = "unavailable"
    else:
        market = _serialize_snapshot(snapshot)
        degraded = any(
            source.state == "ERROR"
            for source in snapshot.sources.values()
        )
        market_quality = "degraded" if degraded else "ok"

    positions = db.scalars(
        select(PositionV2).where(PositionV2.status == PositionStatus.OPEN)
    ).all()
    portfolio = {
        "open_count": len(positions),
        "open_positions": [
            {
                "symbol": position.symbol,
                "quantity": _money(position.quantity),
                "average_entry_price": _money(
                    position.average_entry_price
                ),
                "stop_price": _money(position.stop_price),
                "take_profit_price": _money(position.take_profit_price),
            }
            for position in positions
        ],
    }

    risk_row = db.scalar(
        select(DailyRiskState).where(DailyRiskState.day == moment.date())
    )
    risk: dict[str, Any] | None = None
    if risk_row is not None:
        risk = {
            "day": str(risk_row.day),
            "start_equity_usd": _money(risk_row.start_equity_usd),
            "realized_pnl_usd": _money(risk_row.realized_pnl_usd),
            "opens_count": risk_row.opens_count,
            "blocked": bool(risk_row.blocked),
            "block_reason": risk_row.block_reason,
        }

    score_block: dict[str, Any] | None = None
    if not score.missing:
        score_block = {
            "score": str(score.score),
            "factors": [
                asdict(factor) if is_dataclass(factor) else str(factor)
                for factor in score.factors
            ],
        }

    return {
        "asset": symbol,
        "timestamp": moment.isoformat(),
        "generated_by": "crypto-bot/007",
        "market": market,
        "features": _serialize_features(features),
        "score": score_block,
        "portfolio": portfolio,
        "risk": risk,
        "constraints": {
            "stop_loss_pct": str(settings.stop_loss_pct),
            "take_profit_pct": str(settings.take_profit_pct),
            "configured_capital_usd": str(
                settings.configured_capital_usd
            ),
            "trading_symbols": [
                part.strip()
                for part in settings.trading_symbols.split(",")
                if part.strip()
            ],
        },
        "data_quality": {
            "klines": "ok",
            "market_context": market_quality,
            "portfolio": "ok",
            "risk": "ok" if risk_row is not None else "unavailable",
        },
    }


def _build_prompt(context: dict[str, Any]) -> str:
    payload = json.dumps(context, ensure_ascii=False, default=str)
    return (
        "You are a cautious analyst for a small spot-crypto bot "
        "(20 USD capital, risk <= 1 USD per trade). "
        "Answer with ONE JSON object only, no prose, no markdown.\n"
        "Schema: decision (BUY|SELL|WAIT), direction (LONG|NEUTRAL; spot "
        "never SHORT), confidence (0..1), setup_quality (0..1), "
        "risk_flags[], supporting_factors[], contradicting_factors[], "
        "invalidating_conditions[], time_horizon (string), "
        "suggested_entry_zone (string|null), suggested_stop_zone "
        "(string|null), suggested_take_profit_zone (string|null), "
        "reason_codes[] (short machine codes), required_next_check "
        "(string), data_quality (object of string reasons).\n"
        "Rules: never invent data; qualify every gap using data_quality; "
        "prefer WAIT when evidence is weak or conflicting.\n"
        "Context JSON:\n" + payload
    )


def ai_stats(db: Session) -> dict[str, Any]:
    """Agregados de las consultas IA de las últimas 24 h (spec 009, RF-1).

    Ceros explícitos sin filas (queries/coste); ``avg_latency_ms`` es la
    media de las filas con latencia conocida y ``None`` si no la hay.
    El coste viaja como texto (Decimal, nunca float).
    """
    cutoff = utc_now() - timedelta(hours=24)
    rows = db.scalars(
        select(AiEvaluation).where(AiEvaluation.created_at >= cutoff)
    ).all()

    by_status: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    cost_total = Decimal("0")
    latencies: list[int] = []

    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        if row.decision:
            by_decision[row.decision] = (
                by_decision.get(row.decision, 0) + 1
            )
        if row.cost_usd is not None:
            cost_total += row.cost_usd
        if row.latency_ms is not None:
            latencies.append(row.latency_ms)

    avg_latency_ms = (
        int(sum(latencies) / len(latencies)) if latencies else None
    )
    return {
        "queries_24h": len(rows),
        "cost_usd_24h": str(cost_total),
        "avg_latency_ms": avg_latency_ms,
        "by_status": by_status,
        "by_decision": by_decision,
        "generated_at": utc_now(),
    }

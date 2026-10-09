"""Núcleo de aprendizaje (spec 010): hipótesis, estados y memoria.

Hipótesis (lo que el sistema sospecha) y conocimiento (lo que superó
criterios estadísticos) son entidades separadas; ninguna transición es
silenciosa (§17) y este módulo jamás toca ejecución, riesgo de
escritura ni el analista IA (RF-5).
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    DecisionStatus,
    Hypothesis,
    HypothesisStatus,
    SignalDecision,
    utc_now,
)
from app.services.structured_log import emit

#: Máquina de estados (spec 010, D-3). `VALIDATED → ACTIVE` es manual.
ALLOWED_TRANSITIONS: dict[HypothesisStatus, frozenset[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: frozenset(
        {HypothesisStatus.TESTING, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.TESTING: frozenset(
        {HypothesisStatus.VALIDATED, HypothesisStatus.REJECTED}
    ),
    HypothesisStatus.VALIDATED: frozenset(
        {HypothesisStatus.ACTIVE}
    ),
    HypothesisStatus.ACTIVE: frozenset(
        {HypothesisStatus.DEPRECATED}
    ),
    HypothesisStatus.DEPRECATED: frozenset(),
    HypothesisStatus.REJECTED: frozenset(),
}

#: Estados que exigen motivo explícito en la transición.
REASON_REQUIRED = frozenset(
    {
        HypothesisStatus.ACTIVE,
        HypothesisStatus.REJECTED,
    }
)


def _json_text(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _parse_dt(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def create_hypothesis(
    db: Session,
    *,
    statement: str,
    origin_data: Any = None,
    assets_json: Any = None,
    observed_period_start: Any = None,
    observed_period_finish: Any = None,
    market_regime: str | None = None,
    source: str = "operator",
) -> Hypothesis:
    """Registra una hipótesis en PROPOSED (RF-1). Sin humo: defaults 0."""
    if not str(statement).strip():
        raise ValueError("statement no puede estar vacío.")

    hypothesis = Hypothesis(
        statement=str(statement).strip(),
        origin_data_json=_json_text(origin_data, "{}"),
        assets_json=_json_text(assets_json, "[]"),
        observed_period_start=_parse_dt(observed_period_start),
        observed_period_finish=_parse_dt(observed_period_finish),
        market_regime=market_regime,
        source=source,
        status=HypothesisStatus.PROPOSED,
        version=1,
    )
    db.add(hypothesis)
    db.commit()
    db.refresh(hypothesis)

    emit(
        service="learning",
        event="hypothesis.proposed",
        result="ok",
        payload={
            "hypothesis_id": hypothesis.id,
            "statement": hypothesis.statement,
            "source": hypothesis.source,
        },
        db=db,
    )
    return hypothesis


def list_hypotheses(
    db: Session,
    *,
    status: str | HypothesisStatus | None = None,
    limit: int = 50,
) -> list[Hypothesis]:
    """Lista hipótesis, opcionalmente filtradas por estado (RF-1/RF-4)."""
    query = select(Hypothesis).order_by(Hypothesis.id.desc())
    if status is not None:
        value = (
            status
            if isinstance(status, HypothesisStatus)
            else HypothesisStatus(str(status))
        )
        query = query.where(Hypothesis.status == value)
    return list(db.scalars(query.limit(limit)).all())


def transition_hypothesis(
    db: Session,
    hypothesis: Hypothesis,
    to: str | HypothesisStatus,
    reason: str | None = None,
) -> Hypothesis:
    """Aplica una transición de la máquina D-3; invalida ⇒ ValueError."""
    target = (
        to
        if isinstance(to, HypothesisStatus)
        else HypothesisStatus(str(to))
    )
    current = hypothesis.status

    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ValueError(
            f"transición inválida: {current.value} → {target.value}"
        )

    clean_reason = str(reason).strip() if reason else ""
    if target in REASON_REQUIRED and not clean_reason:
        raise ValueError(
            f"la transición a {target.value} exige un motivo."
        )

    hypothesis.status = target
    hypothesis.version = (hypothesis.version or 1) + 1
    hypothesis.updated_at = utc_now()
    if target is HypothesisStatus.REJECTED:
        hypothesis.rejection_reason = clean_reason
    db.commit()
    db.refresh(hypothesis)

    emit(
        service="learning",
        event="hypothesis.transitioned",
        result="ok",
        payload={
            "hypothesis_id": hypothesis.id,
            "from": current.value,
            "to": target.value,
            "reason": clean_reason or None,
            "version": hypothesis.version,
        },
        db=db,
    )
    return hypothesis


def evaluate_hypothesis(
    db: Session,
    hypothesis: Hypothesis,
    *,
    now: datetime | None = None,
) -> Hypothesis:
    """Evaluación estadística determinista (RF-2).

    Cruza la hipótesis (activos + ventana + régimen declarados) con las
    decisiones cerradas ya persistidas; sin datos suficientes ⇒ TESTING
    con motivo visible, nunca pasa de estado sola hacia ACTIVE.
    """
    if hypothesis.status is not HypothesisStatus.TESTING:
        raise ValueError(
            f"solo se evalúa en TESTING; estado actual: {hypothesis.status.value}"
        )

    assets_raw = json.loads(hypothesis.assets_json or "[]")
    assets = {str(a) for a in assets_raw} if assets_raw else set()
    start = hypothesis.observed_period_start
    finish = hypothesis.observed_period_finish

    if not assets or start is None or finish is None:
        hypothesis.evaluation_note = "sin universo declarado"
        hypothesis.updated_at = utc_now()
        db.commit()
        db.refresh(hypothesis)
        emit(
            service="learning",
            event="hypothesis.evaluated",
            result="ok",
            payload={
                "hypothesis_id": hypothesis.id,
                "case_count": 0,
                "favorable_cases": 0,
                "unfavorable_cases": 0,
                "note": "sin universo declarado",
            },
            db=db,
        )
        return hypothesis

    query = (
        select(SignalDecision)
        .where(SignalDecision.status == DecisionStatus.CLOSED)
        .where(SignalDecision.symbol.in_(assets))
        .where(SignalDecision.closed_at.isnot(None))
        .where(SignalDecision.closed_at >= start)
        .where(SignalDecision.closed_at <= finish)
        .where(SignalDecision.pnl_usd.isnot(None))
    )
    rows = list(db.scalars(query).all())

    case_count = len(rows)
    favorable = sum(1 for r in rows if (r.pnl_usd or Decimal(0)) > 0)
    unfavorable = case_count - favorable

    if case_count > 0:
        confidence: Decimal | None = (
            Decimal(favorable) / Decimal(case_count)
        ).quantize(Decimal("0.000001"))
    else:
        confidence = None

    hypothesis.case_count = case_count
    hypothesis.favorable_cases = favorable
    hypothesis.unfavorable_cases = unfavorable
    hypothesis.confidence = confidence
    hypothesis.updated_at = utc_now()

    min_cases = int(settings.learning_min_cases)
    min_ratio = Decimal(str(settings.learning_min_favorable_ratio))

    note = ""
    if case_count < min_cases:
        note = f"muestra insuficiente: {case_count}/{min_cases}"
    elif confidence is not None and confidence >= min_ratio:
        note = f"ratio {confidence} ≥ umbral {min_ratio}; validada"
    else:
        note = f"ratio {confidence} < umbral {min_ratio}; sigue en TESTING"

    hypothesis.evaluation_note = note
    db.commit()
    db.refresh(hypothesis)

    emit(
        service="learning",
        event="hypothesis.evaluated",
        result="ok",
        payload={
            "hypothesis_id": hypothesis.id,
            "case_count": case_count,
            "favorable_cases": favorable,
            "unfavorable_cases": unfavorable,
            "confidence": str(confidence) if confidence is not None else None,
            "note": note,
        },
        db=db,
    )

    if (
        case_count >= min_cases
        and confidence is not None
        and confidence >= min_ratio
    ):
        transition_hypothesis(db, hypothesis, HypothesisStatus.VALIDATED)
        emit(
            service="learning",
            event="hypothesis.validated",
            result="ok",
            payload={
                "hypothesis_id": hypothesis.id,
                "case_count": case_count,
                "confidence": str(confidence),
            },
            db=db,
        )

    return hypothesis

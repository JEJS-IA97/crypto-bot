"""Endpoints de learning (spec 010, RF-4/RF-8).

Autenticados con `API_TOKEN` (patrón 001 RF-20). Lecturas y
mutaciones son auditadas con eventos `service="learning"`.
Sin humo: nada aquí toca órdenes ni riesgo (RF-5).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_control_token
from app.database import get_db
from app.models import Hypothesis, StrategyVersion
from app.services.learning_service import (
    create_hypothesis,
    create_manual_knowledge,
    evaluate_hypothesis,
    list_knowledge,
    list_strategy_versions,
    list_hypotheses,
    mark_rollback,
    register_strategy_version,
    transition_hypothesis,
)

router = APIRouter(
    prefix="/api/learning",
    tags=["Learning"],
    dependencies=[Depends(require_control_token)],
)


class HypothesisCreate(BaseModel):
    statement: str
    origin_data: dict[str, Any] | None = None
    assets_json: Any = None
    observed_period_start: str | None = None
    observed_period_finish: str | None = None
    market_regime: str | None = None
    source: str = "operator"


class TransitionRequest(BaseModel):
    to: str
    reason: str | None = None


class StrategyVersionCreate(BaseModel):
    version: str
    config_json: Any = {}
    evidence_json: Any = []
    backtest_ref: str | None = None
    paper_results_ref: str | None = None
    motive: str


class RollbackRequest(BaseModel):
    reason: str


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _hypothesis_payload(h: Hypothesis) -> dict[str, Any]:
    return {
        "id": h.id,
        "statement": h.statement,
        "origin_data_json": h.origin_data_json,
        "case_count": h.case_count,
        "favorable_cases": h.favorable_cases,
        "unfavorable_cases": h.unfavorable_cases,
        "confidence": _decimal_text(h.confidence),
        "observed_period_start": (
            h.observed_period_start.isoformat()
            if h.observed_period_start
            else None
        ),
        "observed_period_finish": (
            h.observed_period_finish.isoformat()
            if h.observed_period_finish
            else None
        ),
        "assets_json": h.assets_json,
        "market_regime": h.market_regime,
        "status": h.status.value,
        "version": h.version,
        "source": h.source,
        "rejection_reason": h.rejection_reason,
        "evaluation_note": h.evaluation_note,
        "created_at": h.created_at.isoformat()
        if h.created_at
        else None,
        "updated_at": h.updated_at.isoformat()
        if h.updated_at
        else None,
    }


def _knowledge_payload(k: Any) -> dict[str, Any]:
    return {
        "id": k.id,
        "hypothesis_id": k.hypothesis_id,
        "statement": k.statement,
        "evidence_json": k.evidence_json,
        "sample_size": k.sample_size,
        "confidence_interval_json": k.confidence_interval_json,
        "works_when_json": k.works_when_json,
        "fails_when_json": k.fails_when_json,
        "validated_at": k.validated_at.isoformat()
        if k.validated_at
        else None,
        "version": k.version,
        "observed_impact": k.observed_impact,
        "status": k.status.value,
        "rollback_reason": k.rollback_reason,
        "deprecated_at": k.deprecated_at.isoformat()
        if k.deprecated_at
        else None,
        "created_at": k.created_at.isoformat()
        if k.created_at
        else None,
    }


def _strategy_version_payload(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "version": s.version,
        "config_json": s.config_json,
        "evidence_json": s.evidence_json,
        "backtest_ref": s.backtest_ref,
        "paper_results_ref": s.paper_results_ref,
        "motive": s.motive,
        "rolled_back_at": s.rolled_back_at.isoformat()
        if s.rolled_back_at
        else None,
        "rollback_reason": s.rollback_reason,
        "created_at": s.created_at.isoformat()
        if s.created_at
        else None,
    }


def _get_hypothesis(hypothesis_id: int, db: Session) -> Hypothesis:
    hypothesis = db.get(Hypothesis, hypothesis_id)
    if hypothesis is None:
        raise HTTPException(
            status_code=404, detail="hypothesis_not_found"
        )
    return hypothesis


@router.get("/hypotheses")
def list_hypotheses_endpoint(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """RF-4: lista hipótesis con decimales como texto."""
    rows = list_hypotheses(db, status=status, limit=limit)
    return [_hypothesis_payload(h) for h in rows]


@router.post("/hypotheses", status_code=201)
def create_hypothesis_endpoint(
    payload: HypothesisCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-1/RF-4: alta de hipótesis en PROPOSED."""
    hypothesis = create_hypothesis(
        db,
        statement=payload.statement,
        origin_data=payload.origin_data,
        assets_json=payload.assets_json,
        observed_period_start=payload.observed_period_start,
        observed_period_finish=payload.observed_period_finish,
        market_regime=payload.market_regime,
        source=payload.source,
    )
    return _hypothesis_payload(hypothesis)


@router.post("/hypotheses/{hypothesis_id}/transition")
def transition_hypothesis_endpoint(
    hypothesis_id: int,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-3/RF-4: transición de máquina de estados."""
    hypothesis = _get_hypothesis(hypothesis_id, db)
    try:
        hypothesis = transition_hypothesis(
            db,
            hypothesis,
            payload.to,
            reason=payload.reason,
        )
    except ValueError as exc:
        if "exige un motivo" in str(exc):
            raise HTTPException(status_code=422, detail=str(exc))
        raise HTTPException(status_code=409, detail=str(exc))
    return _hypothesis_payload(hypothesis)


@router.post("/hypotheses/{hypothesis_id}/evaluate")
def evaluate_hypothesis_endpoint(
    hypothesis_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-2/RF-4: evaluación estadística determinista."""
    hypothesis = _get_hypothesis(hypothesis_id, db)
    try:
        hypothesis = evaluate_hypothesis(db, hypothesis)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _hypothesis_payload(hypothesis)


@router.get("/knowledge")
def list_knowledge_endpoint(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """RF-3/RF-4: lista conocimiento confirmado."""
    rows = list_knowledge(db, status=status)
    return [_knowledge_payload(k) for k in rows]


@router.post("/knowledge", status_code=201)
def create_knowledge_endpoint(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-3/RF-4: conocimiento manual (sin hipótesis)."""
    try:
        knowledge = create_manual_knowledge(
            db,
            statement=payload["statement"],
            evidence=payload.get("evidence"),
            works_when=payload.get("works_when"),
            fails_when=payload.get("fails_when"),
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"campo faltante: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _knowledge_payload(knowledge)


@router.get("/strategy-versions")
def list_strategy_versions_endpoint(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """RF-6/RF-4: lista versiones de estrategia."""
    rows = list_strategy_versions(db)
    return [_strategy_version_payload(s) for s in rows]


@router.post("/strategy-versions", status_code=201)
def create_strategy_version_endpoint(
    payload: StrategyVersionCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-6/RF-4: registra una versión (append-only)."""
    try:
        row = register_strategy_version(
            db,
            version=payload.version,
            config_json=payload.config_json,
            evidence_json=payload.evidence_json,
            backtest_ref=payload.backtest_ref,
            paper_results_ref=payload.paper_results_ref,
            motive=payload.motive,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _strategy_version_payload(row)


@router.post("/strategy-versions/{version_id}/rollback")
def rollback_strategy_version_endpoint(
    version_id: int,
    payload: RollbackRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """RF-6/RF-4: marca rollback en una versión."""
    row = db.get(StrategyVersion, version_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail="strategy_version_not_found"
        )
    try:
        row = mark_rollback(db, row, reason=payload.reason)
    except ValueError as exc:
        if "exige un motivo" in str(exc):
            raise HTTPException(status_code=422, detail=str(exc))
        raise HTTPException(status_code=409, detail=str(exc))
    return _strategy_version_payload(row)

"""Fases del bot y criterios de paso (spec 001, RF-16, RF-2 / D-9, D-7).

- La fase activa vive en BD (fila única ``bot_phases``) y solo cambia a
  través de este servicio: cambio manual del propietario (RF-16).
- ``request_phase_change`` exige el criterio D-9 para SIMULATION→TESTNET:
  ≥30 días de paper-trading, ≥15 operaciones, PnL neto >0 tras comisiones,
  drawdown ≤10% y backtest con signo positivo en validación Y test (la
  evidencia del backtest llega en el payload); TESTNET→LIVE exige además
  testnet rentable. Sin cumplirlo devuelve el detalle de lo que falta.
- ``live_trading_blockers`` (RF-2): con ``ALLOW_LIVE_TRADING=true`` y fase
  ≠ LIVE, o sin aporte configurado, el real queda bloqueado con motivo
  visible para el panel; el valor de la cuenta por ganancias nunca bloquea
  (D-7: el límite es sobre lo aportado).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BotPhase,
    BotPhaseName,
    DecisionStatus,
    SignalDecision,
    utc_now,
)

MIN_PAPER_DAYS = 30
MIN_PAPER_OPERATIONS = 15
MAX_DRAWDOWN_PCT = Decimal("10")

VALIDATION_EVIDENCE_KEY = "backtest_validation_net_pnl"
TEST_EVIDENCE_KEY = "backtest_test_net_pnl"

_PHASE_ORDER = (
    BotPhaseName.SIMULATION,
    BotPhaseName.TESTNET,
    BotPhaseName.LIVE,
)

_HUNDRED = Decimal("100")
_DRAWDOWN_PLACES = Decimal("0.01")


def get_phase(db: Session) -> BotPhase:
    """Fase activa (fila única, id=1); la crea en SIMULATION si no existe."""
    phase = db.get(BotPhase, 1)
    if phase is None:
        phase = BotPhase(id=1, phase=BotPhaseName.SIMULATION)
        db.add(phase)
        db.commit()
        db.refresh(phase)
    return phase


def paper_metrics(db: Session) -> dict[str, Any]:
    """Métricas de paper-trading del periodo completo, sin red (RF-16)."""
    first_decision_at = db.scalar(
        select(func.min(SignalDecision.created_at))
    )
    now = utc_now()
    paper_days = (
        (now - first_decision_at).days if first_decision_at is not None else 0
    )

    operations = (
        db.scalar(
            select(func.count())
            .select_from(SignalDecision)
            .where(SignalDecision.status == DecisionStatus.CLOSED)
        )
        or 0
    )

    closed = list(
        db.scalars(
            select(SignalDecision)
            .where(
                SignalDecision.status == DecisionStatus.CLOSED,
                SignalDecision.pnl_usd.is_not(None),
            )
            .order_by(
                SignalDecision.closed_at.asc(),
                SignalDecision.id.asc(),
            )
        ).all()
    )
    equity = settings.configured_capital_usd
    if not isinstance(equity, Decimal):
        raise TypeError("configured_capital_usd must be a Decimal")
    realized = Decimal("0")
    peak = equity
    drawdown_worst = Decimal("0")
    for decision in closed:
        realized += decision.pnl_usd or Decimal("0")
        equity += decision.pnl_usd or Decimal("0")
        if equity > peak:
            peak = equity
        if peak > 0:
            drop = (peak - equity) * _HUNDRED / peak
            if drop > drawdown_worst:
                drawdown_worst = drop

    return {
        "paper_days": paper_days,
        "operations": operations,
        "realized_pnl_usd": realized.quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        ),
        "drawdown_pct": drawdown_worst.quantize(
            _DRAWDOWN_PLACES, rounding=ROUND_HALF_UP
        ),
    }


def testnet_metrics(db: Session, phase: BotPhase) -> dict[str, Any]:
    """Operaciones cerradas desde que la fase activa pasó a TESTNET."""
    closed = list(
        db.scalars(
            select(SignalDecision)
            .where(
                SignalDecision.status == DecisionStatus.CLOSED,
                SignalDecision.pnl_usd.is_not(None),
                SignalDecision.closed_at.is_not(None),
                SignalDecision.closed_at >= phase.changed_at,
            )
        ).all()
    )
    realized = sum(
        ((decision.pnl_usd or Decimal("0")) for decision in closed),
        Decimal("0"),
    )
    return {
        "testnet_operations": len(closed),
        "testnet_net_pnl_usd": realized.quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        ),
    }


def _evidence_decimal(
    evidence: dict[str, Any] | None,
    key: str,
) -> Decimal | None:
    if not isinstance(evidence, dict):
        return None
    raw = evidence.get(key)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _missing_criteria(
    db: Session,
    *,
    new_phase: BotPhaseName,
    evidence: dict[str, Any] | None,
    phase: BotPhase,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Criterios D-9 pendientes; el detalle va en español para el panel."""
    metrics = paper_metrics(db)
    missing: list[dict[str, str]] = []

    if metrics["paper_days"] < MIN_PAPER_DAYS:
        missing.append(
            {
                "criterion": "paper_days",
                "detail": (
                    f"{metrics['paper_days']} días de paper-trading; "
                    f"se exigen ≥{MIN_PAPER_DAYS}"
                ),
            }
        )
    if metrics["operations"] < MIN_PAPER_OPERATIONS:
        missing.append(
            {
                "criterion": "operations",
                "detail": (
                    f"{metrics['operations']} operaciones cerradas; "
                    f"se exigen ≥{MIN_PAPER_OPERATIONS}"
                ),
            }
        )
    if metrics["realized_pnl_usd"] <= 0:
        missing.append(
            {
                "criterion": "net_pnl",
                "detail": (
                    f"PnL neto {metrics['realized_pnl_usd']} USD; "
                    "debe ser >0 tras comisiones"
                ),
            }
        )
    if metrics["drawdown_pct"] > MAX_DRAWDOWN_PCT:
        missing.append(
            {
                "criterion": "drawdown_pct",
                "detail": (
                    f"drawdown {metrics['drawdown_pct']}%; "
                    f"el máximo es {MAX_DRAWDOWN_PCT}%"
                ),
            }
        )

    validation = _evidence_decimal(evidence, VALIDATION_EVIDENCE_KEY)
    if validation is None or validation <= 0:
        missing.append(
            {
                "criterion": "backtest_validation",
                "detail": (
                    f"falta {VALIDATION_EVIDENCE_KEY} > 0 en la evidencia "
                    "del backtest"
                ),
            }
        )
    test = _evidence_decimal(evidence, TEST_EVIDENCE_KEY)
    if test is None or test <= 0:
        missing.append(
            {
                "criterion": "backtest_test",
                "detail": (
                    f"falta {TEST_EVIDENCE_KEY} > 0 en la evidencia "
                    "del backtest"
                ),
            }
        )

    evidence_values: dict[str, Any] = {
        "backtest_validation_net_pnl": (
            str(validation) if validation is not None else None
        ),
        "backtest_test_net_pnl": str(test) if test is not None else None,
    }

    if new_phase is BotPhaseName.LIVE:
        tn = testnet_metrics(db, phase)
        metrics.update(tn)
        evidence_values.update(
            {
                "testnet_operations": tn["testnet_operations"],
                "testnet_net_pnl_usd": str(tn["testnet_net_pnl_usd"]),
            }
        )
        if (
            tn["testnet_operations"] < 1
            or tn["testnet_net_pnl_usd"] <= 0
        ):
            missing.append(
                {
                    "criterion": "testnet_profitable",
                    "detail": (
                        "testnet sin rentabilidad: "
                        f"{tn['testnet_operations']} ops y PnL "
                        f"{tn['testnet_net_pnl_usd']} USD; "
                        "se exige PnL >0 durante TESTNET"
                    ),
                }
            )

    return missing, {**metrics, **evidence_values}


def request_phase_change(
    db: Session,
    *,
    new_phase: BotPhaseName | str,
    evidence: dict[str, Any] | None = None,
    changed_by: str = "manual",
) -> dict[str, Any]:
    """Cambio manual de fase con los criterios RF-16 bloqueantes.

    Solo avanza un paso (SIMULATION→TESTNET→LIVE) y nunca sin cumplir D-9;
    si algo falta, devuelve ``missing`` con el detalle sin tocar la BD.
    """
    if isinstance(new_phase, str):
        try:
            new_phase = BotPhaseName(new_phase)
        except ValueError:
            return {
                "ok": False,
                "reason": "invalid_phase",
                "phase": new_phase,
            }
    if not isinstance(new_phase, BotPhaseName):
        return {"ok": False, "reason": "invalid_phase", "phase": None}

    current = get_phase(db)
    if current.phase == new_phase:
        return {
            "ok": False,
            "reason": "phase_already_set",
            "phase": current.phase.value,
        }

    current_index = _PHASE_ORDER.index(current.phase)
    target_index = _PHASE_ORDER.index(new_phase)
    if target_index != current_index + 1:
        return {
            "ok": False,
            "reason": "non_consecutive_phase",
            "phase": current.phase.value,
        }

    missing, metrics = _missing_criteria(
        db,
        new_phase=new_phase,
        evidence=evidence,
        phase=current,
    )
    if missing:
        return {
            "ok": False,
            "reason": "criteria_not_met",
            "phase": current.phase.value,
            "missing": missing,
            "metrics": metrics,
        }

    payload = {
        "previous_phase": current.phase.value,
        "paper_days": metrics["paper_days"],
        "operations": metrics["operations"],
        "net_pnl_usd": str(metrics["realized_pnl_usd"]),
        "drawdown_pct": str(metrics["drawdown_pct"]),
        "backtest_validation_net_pnl": metrics[
            "backtest_validation_net_pnl"
        ],
        "backtest_test_net_pnl": metrics["backtest_test_net_pnl"],
    }
    if new_phase is BotPhaseName.LIVE:
        payload["testnet_operations"] = metrics["testnet_operations"]
        payload["testnet_net_pnl_usd"] = str(
            metrics["testnet_net_pnl_usd"]
        )

    current.phase = new_phase
    current.changed_at = utc_now()
    current.evidence_json = json.dumps(payload, default=str)
    current.changed_by = changed_by
    db.commit()
    db.refresh(current)

    return {
        "ok": True,
        "phase": new_phase.value,
        "evidence": payload,
    }


def live_trading_blockers(db: Session) -> list[dict[str, str]]:
    """Motivos visibles (RF-2) que impiden operar en dinero real."""
    blockers: list[dict[str, str]] = []
    if not settings.allow_live_trading:
        blockers.append(
            {
                "reason": "live_trading_disabled",
                "detail": (
                    "ALLOW_LIVE_TRADING no es true: el bot no envía órdenes "
                    "a producción."
                ),
            }
        )
    current = get_phase(db)
    if current.phase is not BotPhaseName.LIVE:
        blockers.append(
            {
                "reason": "phase_not_live",
                "detail": (
                    f"fase activa {current.phase.value}; para operar en real "
                    "hace falta la fase LIVE (RF-16)"
                ),
            }
        )
    if settings.configured_capital_usd <= 0:
        blockers.append(
            {
                "reason": "no_capital_configured",
                "detail": (
                    "CONFIGURED_CAPITAL_USD debe ser >0: el límite de real "
                    "se aplica sobre lo aportado (RF-2, D-7)"
                ),
            }
        )
    return blockers

"""Risk engine v2 (spec 008): veto y redimensión con auditoría.

Envuelve ``risk_guard.can_open`` (D-1): las cuatro razones de la 001
llegan intactas y se añaden ``max_open_positions`` (RF-3), ``max_exposure``
(RF-4) y ``correlated_exposure`` con resize (RF-5). Cada evaluación emite
un evento ``risk.evaluated`` (RF-7). Sin red y sin nada del analista IA
de la 007 (RF-9): solo velas ya descargadas, la sesión en curso y eventos
observables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.portfolio_math import (
    correlate_closes,
    floor_to_step,
    halved_share,
)
from app.domain.risk_math import (
    MAX_LOSS_PER_TRADE_USD,
    MAX_OPEN_POSITIONS,
    MAX_POSITION_SHARE,
)
from app.models import PositionStatus, PositionV2
from app.services.risk_guard_service import (
    BREAKER_FAILURE_THRESHOLD,
    COOLDOWN_SECONDS,
    DAILY_LOSS_LIMIT_PCT,
    MAX_OPENS_PER_DAY,
    can_open,
)
from app.services.structured_log import emit

REASON_MAX_OPEN_POSITIONS = "max_open_positions"
REASON_MAX_EXPOSURE = "max_exposure"
REASON_CORRELATED_EXPOSURE = "correlated_exposure"

EVENT_NAME = "risk.evaluated"
SERVICE_NAME = "risk_engine"


class RiskAction(str, Enum):
    """Resultado de una evaluación de apertura."""

    ALLOW = "allow"
    RESIZED = "resized"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class RiskAssessment:
    """Decisión de apertura con toda la evidencia para auditarla."""

    action: RiskAction
    reason: str
    symbol: str
    requested_usd: Decimal
    allowed_usd: Decimal
    allowed_quantity: Decimal | None
    committed_usd: Decimal
    available_usd: Decimal
    exposure_cap_usd: Decimal
    open_positions: int
    correlations: dict[str, str | None]
    max_correlation: Decimal | None
    resize_applied: bool


def _exposure_cap() -> Decimal:
    """Tope total = RISK_MAX_TOTAL_EXPOSURE_PCT % del capital aportado."""
    capital = settings.configured_capital_usd
    return capital * settings.risk_max_total_exposure_pct / Decimal(100)


def _decimal_text(value: Decimal) -> str:
    """Texto sin notación científica ni ceros sobrantes (RF-6/RF-7)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def limits_snapshot() -> dict[str, Any]:
    """Límites vigentes (RF-6/RF-7): decimales como texto, enteros como tal."""
    return {
        "daily_loss_limit_pct": str(DAILY_LOSS_LIMIT_PCT),
        "max_opens_per_day": MAX_OPENS_PER_DAY,
        "max_loss_per_trade_usd": str(MAX_LOSS_PER_TRADE_USD),
        "max_position_share": str(MAX_POSITION_SHARE),
        "max_open_positions": MAX_OPEN_POSITIONS,
        "max_total_exposure_pct": str(settings.risk_max_total_exposure_pct),
        "correlation_threshold": str(settings.risk_correlation_threshold),
        "cooldown_seconds": COOLDOWN_SECONDS,
        "breakers_failures": BREAKER_FAILURE_THRESHOLD,
    }


def _open_positions(db: Session, account_id: int) -> list[PositionV2]:
    return list(
        db.scalars(
            select(PositionV2).where(
                PositionV2.account_id == account_id,
                PositionV2.status == PositionStatus.OPEN,
            )
        ).all()
    )


def _committed(positions: list[PositionV2]) -> Decimal:
    return sum(
        (row.quantity * row.average_entry_price for row in positions),
        Decimal(0),
    )


def _correlations(
    positions: list[PositionV2],
    *,
    symbol: str,
    candles: list,
    other_candles: dict,
) -> tuple[dict[str, str | None], Decimal | None]:
    """Correlación (D-2) con cada par abierto distinto del candidato.

    ``None`` por par cuando no hay datos suficientes ("unknown"); el máximo
    solo considera las correlaciones calculadas.
    """
    candidate_closes = [candle.close for candle in candles]
    correlations: dict[str, str | None] = {}
    computed: list[Decimal] = []
    for row in positions:
        if row.symbol == symbol:
            continue
        other = other_candles.get(row.symbol)
        if not other:
            correlations[row.symbol] = None
            continue
        value = correlate_closes(
            candidate_closes, [candle.close for candle in other]
        )
        correlations[row.symbol] = (
            _decimal_text(value) if value is not None else None
        )
        if value is not None:
            computed.append(value)
    return correlations, (max(computed) if computed else None)


def evaluate_open(
    db: Session,
    *,
    symbol: str,
    now: datetime,
    state,
    account_id: int,
    quantity: Decimal,
    price: Decimal,
    candles: list,
    other_candles: dict,
    step_size: Decimal,
    min_notional_usd: Decimal,
    available_usd: Decimal,
    correlation_id: str | None = None,
) -> RiskAssessment:
    """Evalúa una apertura (D-1): delega la 001 y añade topes nuevos.

    Orden: 1) ``risk_guard.can_open`` → 2) ≤3 posiciones abiertas →
    3) exposición total → 4) correlación/resize (D-3) → 5) evento
    ``risk.evaluated`` en todos los caminos.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must not be empty")
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    for name, value in (
        ("quantity", quantity),
        ("price", price),
        ("step_size", step_size),
        ("min_notional_usd", min_notional_usd),
        ("available_usd", available_usd),
    ):
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be Decimal")
        if name != "available_usd" and value <= 0:
            raise ValueError(f"{name} must be > 0")
    if not isinstance(other_candles, dict):
        raise TypeError("other_candles must be a dict")

    capital = settings.configured_capital_usd
    exposure_cap = _exposure_cap()
    requested = quantity * price
    positions = _open_positions(db, account_id)
    committed = _committed(positions)

    action = RiskAction.ALLOW
    reason = ""
    allowed_quantity: Decimal | None = quantity
    allowed_usd = requested
    correlations: dict[str, str | None] = {}
    max_correlation: Decimal | None = None
    resize_applied = False

    guard_ok, guard_reason = can_open(db, state, symbol, now)
    if not guard_ok:
        action = RiskAction.BLOCKED
        reason = guard_reason
        allowed_quantity = None
        allowed_usd = Decimal(0)
    elif len(positions) >= MAX_OPEN_POSITIONS:
        action = RiskAction.BLOCKED
        reason = REASON_MAX_OPEN_POSITIONS
        allowed_quantity = None
        allowed_usd = Decimal(0)
    elif committed + requested > exposure_cap:
        action = RiskAction.BLOCKED
        reason = REASON_MAX_EXPOSURE
        allowed_quantity = None
        allowed_usd = Decimal(0)
    else:
        correlations, max_correlation = _correlations(
            positions,
            symbol=symbol,
            candles=candles,
            other_candles=other_candles,
        )
        threshold = settings.risk_correlation_threshold
        if max_correlation is not None and max_correlation >= threshold:
            target = min(requested, halved_share(capital))
            resized_quantity = floor_to_step(target / price, step_size)
            resized_usd = resized_quantity * price
            if (
                resized_quantity > 0
                and resized_usd >= min_notional_usd
                and resized_usd < requested
            ):
                action = RiskAction.RESIZED
                reason = REASON_CORRELATED_EXPOSURE
                allowed_quantity = resized_quantity
                allowed_usd = resized_usd
                resize_applied = True

    assessment = RiskAssessment(
        action=action,
        reason=reason,
        symbol=symbol,
        requested_usd=requested,
        allowed_usd=allowed_usd,
        allowed_quantity=allowed_quantity,
        committed_usd=committed,
        available_usd=available_usd,
        exposure_cap_usd=exposure_cap,
        open_positions=len(positions),
        correlations=correlations,
        max_correlation=max_correlation,
        resize_applied=resize_applied,
    )
    emit(
        service=SERVICE_NAME,
        event=EVENT_NAME,
        level="INFO" if action == RiskAction.ALLOW else "WARNING",
        result=action.value,
        asset=symbol,
        correlation_id=correlation_id,
        payload={
            "symbol": assessment.symbol,
            "action": assessment.action.value,
            "reason": assessment.reason,
            "requested_usd": _decimal_text(assessment.requested_usd),
            "allowed_usd": _decimal_text(assessment.allowed_usd),
            "committed_usd": _decimal_text(assessment.committed_usd),
            "exposure_cap_usd": _decimal_text(assessment.exposure_cap_usd),
            "open_positions": assessment.open_positions,
            "correlations": assessment.correlations,
            "max_correlation": (
                _decimal_text(assessment.max_correlation)
                if assessment.max_correlation is not None
                else None
            ),
            "resize_applied": assessment.resize_applied,
            "limits": limits_snapshot(),
        },
        db=db,
    )
    return assessment


def exposure_snapshot(
    db: Session,
    *,
    account_id: int,
    available_usd: Decimal | None = None,
) -> dict[str, Any]:
    """Instantánea de exposición total (RF-6): decimales como texto."""
    capital = settings.configured_capital_usd
    exposure_cap = _exposure_cap()
    positions = _open_positions(db, account_id)
    committed = _committed(positions)
    open_count = len(positions)

    by_asset: dict[str, Decimal] = {}
    for row in positions:
        value = row.quantity * row.average_entry_price
        by_asset[row.symbol] = by_asset.get(row.symbol, Decimal(0)) + value

    if capital > 0:
        exposure_pct = (
            committed / capital * Decimal(100)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        exposure_pct = Decimal("0.00")
    headroom = exposure_cap - committed
    if headroom < 0:
        headroom = Decimal(0)

    return {
        "capital_usd": _decimal_text(capital),
        "committed_usd": _decimal_text(committed),
        "available_usd": (
            _decimal_text(available_usd)
            if available_usd is not None
            else None
        ),
        "exposure_cap_usd": _decimal_text(exposure_cap),
        "exposure_pct": _decimal_text(exposure_pct),
        "headroom_usd": _decimal_text(headroom),
        "open_positions": open_count,
        "max_open_positions": MAX_OPEN_POSITIONS,
        "by_asset": {
            symbol: _decimal_text(value)
            for symbol, value in by_asset.items()
        },
        "by_direction": {"LONG": _decimal_text(committed), "NEUTRAL": "0"},
        "limits": limits_snapshot(),
    }

"""External (copy) signal validation — spec 001 RF-8/RF-9/RF-23.

A copy signal is a client payload `{symbol, side, price_limit?, quantity?,
quantity_quote?, source, issued_at, ttl_seconds?}` that may override the
technical signal of the same symbol. Validation is fail-closed: any
unmet condition rejects the signal with a machine-readable reason.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.risk_math import MAX_POSITION_SHARE, calculate_order_size
from app.domain.signal_engine import SignalAction
from app.models import DecisionStatus, SignalDecision, TradeSide
from app.services.binance_market_data_client import SymbolRules
from app.services.risk_guard_service import COOLDOWN_SECONDS

EXTERNAL_CONFLICT_REASON = "contradicha por señal externa"

REASON_UNKNOWN_SYMBOL = "unknown_symbol"
REASON_INVALID_SIDE = "invalid_side"
REASON_EXPIRED = "signal_expired"
REASON_BAD_TIMESTAMP = "signal_timestamp_invalid"
REASON_PRICE_TOO_FAR = "price_too_far"
REASON_DUPLICATE = "duplicate_signal"
REASON_INVALID_QUANTITY = "invalid_quantity"


def _require_optional_decimal(name: str, value: object) -> None:
    if value is not None and not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")


@dataclass(frozen=True)
class ExternalSignal:
    """Normalized copy-signal payload (RF-8)."""

    symbol: str
    side: str
    price_limit: Decimal | None = None
    quantity: Decimal | None = None
    quantity_quote: Decimal | None = None
    source: str = ""
    issued_at: datetime | None = None
    ttl_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(self.side, str) or not self.side.strip():
            raise ValueError("side must be a non-empty string")
        if not isinstance(self.source, str):
            raise ValueError("source must be a string")
        if self.issued_at is not None and not isinstance(
            self.issued_at, datetime
        ):
            raise TypeError("issued_at must be a datetime")
        if self.ttl_seconds is not None and not isinstance(
            self.ttl_seconds, int
        ):
            raise TypeError("ttl_seconds must be int")
        _require_optional_decimal("price_limit", self.price_limit)
        _require_optional_decimal("quantity", self.quantity)
        _require_optional_decimal("quantity_quote", self.quantity_quote)


@dataclass(frozen=True)
class SignalValidation:
    """Outcome of validating one external signal."""

    accepted: bool
    reason: str
    symbol: str = ""
    side: TradeSide | None = None
    quantity: Decimal | None = None


@dataclass(frozen=True)
class ConflictResolution:
    """RF-23: on opposite signals over the same symbol, external wins."""

    external_wins: bool
    technical_reason: str


def _trading_symbols() -> set[str]:
    return {
        part.strip().upper()
        for part in settings.trading_symbols.split(",")
        if part.strip()
    }


def _is_duplicate(
    db: Session,
    symbol: str,
    side: TradeSide,
    now: datetime,
) -> bool:
    cutoff = now - timedelta(seconds=COOLDOWN_SECONDS)
    row = db.execute(
        select(SignalDecision.id)
        .where(
            SignalDecision.symbol == symbol,
            SignalDecision.side == side,
            SignalDecision.status != DecisionStatus.REJECTED,
            SignalDecision.created_at >= cutoff,
        )
        .limit(1)
    ).scalar_one_or_none()
    return row is not None


def validate_external_signal(
    db: Session,
    signal: ExternalSignal,
    *,
    now: datetime,
    current_price: Decimal,
    rules: SymbolRules,
) -> SignalValidation:
    """RF-8/RF-9: validate one copy signal and size it when missing.

    Rejection reasons: unknown_symbol, invalid_side, signal_expired,
    signal_timestamp_invalid, price_too_far, duplicate_signal,
    invalid_quantity, below_min_notional, insufficient_balance.
    """
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")
    if not isinstance(current_price, Decimal):
        raise TypeError("current_price must be Decimal")
    if current_price <= 0:
        raise ValueError("current_price must be > 0")

    symbol = signal.symbol.strip().upper()
    if symbol not in _trading_symbols():
        return SignalValidation(False, REASON_UNKNOWN_SYMBOL, symbol)

    try:
        side = TradeSide(signal.side.strip().upper())
    except ValueError:
        return SignalValidation(False, REASON_INVALID_SIDE, symbol)

    ttl = signal.ttl_seconds
    if ttl is None:
        ttl = settings.signal_ttl_seconds
    issued_at = signal.issued_at
    if issued_at is None:
        issued_at = now
    if issued_at > now:
        return SignalValidation(False, REASON_BAD_TIMESTAMP, symbol)
    if (now - issued_at).total_seconds() > ttl:
        return SignalValidation(False, REASON_EXPIRED, symbol)

    if signal.price_limit is not None:
        if current_price <= 0:
            raise ValueError("current_price must be > 0")
        distance_pct = (
            abs(signal.price_limit - current_price) / current_price
        ) * Decimal(100)
        if distance_pct > settings.max_signal_price_distance_pct:
            return SignalValidation(False, REASON_PRICE_TOO_FAR, symbol)

    if _is_duplicate(db, symbol, side, now):
        return SignalValidation(False, REASON_DUPLICATE, symbol)

    sizing_price = current_price
    if signal.quantity is None:
        capital = settings.configured_capital_usd
        if signal.quantity_quote is not None:
            if signal.quantity_quote <= 0:
                return SignalValidation(
                    False, REASON_INVALID_QUANTITY, symbol
                )
            capital = signal.quantity_quote / MAX_POSITION_SHARE
        result = calculate_order_size(
            price=sizing_price,
            capital_usd=capital,
            available_usd=settings.configured_capital_usd,
            min_notional_usd=rules.min_notional,
            step_size=rules.step_size,
            stop_loss_pct=settings.stop_loss_pct,
        )
        if result.discarded:
            return SignalValidation(False, result.reason, symbol)
        quantity = result.quantity
    else:
        quantity = signal.quantity
        if quantity <= 0:
            return SignalValidation(False, REASON_INVALID_QUANTITY, symbol)
        if quantity * sizing_price < rules.min_notional:
            return SignalValidation(False, "below_min_notional", symbol)

    return SignalValidation(True, "", symbol, side, quantity)


def resolve_signal_conflict(
    *,
    technical_symbol: str,
    technical_action: SignalAction,
    external_symbol: str,
    external_side: TradeSide,
) -> ConflictResolution:
    """RF-23: external signal prevails over an opposite technical one."""
    same_symbol = technical_symbol.strip().upper() == (
        external_symbol.strip().upper()
    )
    if not same_symbol:
        return ConflictResolution(False, "")
    if technical_action == SignalAction.HOLD:
        return ConflictResolution(False, "")

    opposite = (
        technical_action == SignalAction.BUY
        and external_side == TradeSide.SELL
    ) or (
        technical_action == SignalAction.SELL
        and external_side == TradeSide.BUY
    )
    if opposite:
        return ConflictResolution(True, EXTERNAL_CONFLICT_REASON)
    return ConflictResolution(False, "")

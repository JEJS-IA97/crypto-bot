"""Risk math for order sizing and protective orders (spec 001, RF-12/RF-13).

Pure module: no network, no database, no framework imports. All amounts are
Decimal (constitution #11).
"""

from dataclasses import dataclass
from decimal import Decimal

MAX_LOSS_PER_TRADE_USD = Decimal("1")
MAX_OPEN_POSITIONS = 3
MAX_POSITION_SHARE = Decimal("0.25")
HUNDRED = Decimal("100")


def _require_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} must be Decimal")
    return value


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value // step) * step


def _ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
    floored = _floor_to_step(value, step)
    if floored == value:
        return floored
    return floored + step


@dataclass(frozen=True)
class SizingResult:
    quantity: Decimal | None
    notional_usd: Decimal | None
    estimated_loss_usd: Decimal | None
    discarded: bool
    reason: str


def can_open_position(open_positions: int) -> bool:
    """RF-12: at most 3 positions open at the same time."""
    if not isinstance(open_positions, int) or isinstance(open_positions, bool):
        raise TypeError("open_positions must be int")
    if open_positions < 0:
        raise ValueError("open_positions must be >= 0")
    return open_positions < MAX_OPEN_POSITIONS


def calculate_order_size(
    *,
    price: Decimal,
    capital_usd: Decimal,
    available_usd: Decimal,
    min_notional_usd: Decimal,
    step_size: Decimal,
    stop_loss_pct: Decimal,
    max_loss_per_trade_usd: Decimal = MAX_LOSS_PER_TRADE_USD,
) -> SizingResult:
    """Size an order respecting RF-11/RF-12/RF-13.

    Target quote = max(min_notional, 25% of capital), floored to step, raised
    by one step only when needed to satisfy the exchange minimum, then capped
    by the available balance and by the maximum loss allowed at the stop.
    """
    price = _require_decimal("price", price)
    capital_usd = _require_decimal("capital_usd", capital_usd)
    available_usd = _require_decimal("available_usd", available_usd)
    min_notional_usd = _require_decimal("min_notional_usd", min_notional_usd)
    step_size = _require_decimal("step_size", step_size)
    stop_loss_pct = _require_decimal("stop_loss_pct", stop_loss_pct)
    max_loss_per_trade_usd = _require_decimal(
        "max_loss_per_trade_usd", max_loss_per_trade_usd
    )

    if price <= 0:
        raise ValueError("price must be > 0")
    if step_size <= 0:
        raise ValueError("step_size must be > 0")
    if stop_loss_pct <= 0 or stop_loss_pct >= HUNDRED:
        raise ValueError("stop_loss_pct must be in (0, 100)")
    if capital_usd < 0 or available_usd < 0 or min_notional_usd < 0:
        raise ValueError("amounts must be >= 0")
    if max_loss_per_trade_usd <= 0:
        raise ValueError("max_loss_per_trade_usd must be > 0")

    target_quote = max(
        min_notional_usd,
        capital_usd * MAX_POSITION_SHARE,
    )

    quantity = _floor_to_step(target_quote / price, step_size)
    notional = quantity * price

    if notional < min_notional_usd:
        quantity += step_size
        notional = quantity * price
    if quantity <= 0 or notional < min_notional_usd:
        return SizingResult(None, None, None, True, "below_min_notional")

    if notional > available_usd:
        quantity = _floor_to_step(available_usd / price, step_size)
        notional = quantity * price
        if notional < min_notional_usd:
            quantity += step_size
            notional = quantity * price
        if quantity <= 0 or notional < min_notional_usd:
            return SizingResult(None, None, None, True, "insufficient_balance")
        if notional > available_usd:
            return SizingResult(None, None, None, True, "insufficient_balance")

    risk_cap_notional = max_loss_per_trade_usd / (stop_loss_pct / HUNDRED)
    if notional > risk_cap_notional:
        quantity = _floor_to_step(risk_cap_notional / price, step_size)
        notional = quantity * price
        if quantity <= 0 or notional < min_notional_usd:
            return SizingResult(
                None, None, None, True, "stop_loss_exceeds_max"
            )

    estimated_loss = notional * stop_loss_pct / HUNDRED
    if estimated_loss > max_loss_per_trade_usd:
        return SizingResult(None, None, None, True, "stop_loss_exceeds_max")

    return SizingResult(quantity, notional, estimated_loss, False, "")


def stop_take_prices(
    *,
    entry_price: Decimal,
    stop_loss_pct: Decimal,
    take_profit_pct: Decimal,
    tick_size: Decimal,
) -> tuple[Decimal, Decimal]:
    """Stop rounded toward the entry, take-profit rounded down (RF-13)."""
    entry_price = _require_decimal("entry_price", entry_price)
    stop_loss_pct = _require_decimal("stop_loss_pct", stop_loss_pct)
    take_profit_pct = _require_decimal("take_profit_pct", take_profit_pct)
    tick_size = _require_decimal("tick_size", tick_size)

    if entry_price <= 0:
        raise ValueError("entry_price must be > 0")
    if tick_size <= 0:
        raise ValueError("tick_size must be > 0")
    if stop_loss_pct <= 0 or stop_loss_pct >= HUNDRED:
        raise ValueError("stop_loss_pct must be in (0, 100)")
    if take_profit_pct <= 0:
        raise ValueError("take_profit_pct must be > 0")

    exact_stop = entry_price * (Decimal(1) - stop_loss_pct / HUNDRED)
    if exact_stop <= 0:
        raise ValueError("stop_loss_pct too large for entry_price")

    stop = _ceil_to_step(exact_stop, tick_size)
    if stop >= entry_price:
        stop = entry_price - tick_size
    if stop <= 0:
        raise ValueError("stop price must be > 0")

    exact_take = entry_price * (Decimal(1) + take_profit_pct / HUNDRED)
    take = _floor_to_step(exact_take, tick_size)
    if take <= entry_price:
        take = entry_price + tick_size

    return stop, take


def estimated_loss_usd(
    *,
    entry_price: Decimal,
    stop_price: Decimal,
    quantity: Decimal,
) -> Decimal:
    """Loss realized if the stop fills: qty * (entry - stop)."""
    entry_price = _require_decimal("entry_price", entry_price)
    stop_price = _require_decimal("stop_price", stop_price)
    quantity = _require_decimal("quantity", quantity)
    if stop_price >= entry_price:
        raise ValueError("stop_price must be below entry_price")
    if quantity < 0:
        raise ValueError("quantity must be >= 0")
    return quantity * (entry_price - stop_price)

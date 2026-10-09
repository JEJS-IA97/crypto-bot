"""Portfolio math for the risk engine (spec 008, D-2/D-3).

Pure module: no network, no database, no framework imports. All amounts
are Decimal (constitution #11).
"""

from decimal import Decimal

from app.domain.risk_math import MAX_POSITION_SHARE


def _require_decimal_list(name: str, values: list[Decimal]) -> None:
    if not isinstance(values, list):
        raise TypeError(f"{name} must be a list of Decimal")
    for value in values:
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must contain only Decimal values")


def pct_returns(closes: list[Decimal]) -> list[Decimal]:
    """Period-over-period percentage returns of a close series."""
    _require_decimal_list("closes", closes)
    returns: list[Decimal] = []
    for index in range(len(closes) - 1):
        current = closes[index]
        following = closes[index + 1]
        if current <= 0:
            raise ValueError("closes must be > 0")
        returns.append((following - current) / current)
    return returns


def pearson(xs: list[Decimal], ys: list[Decimal]) -> Decimal | None:
    """Pearson correlation of two equal-length series.

    Returns ``None`` when it cannot be computed honestly: fewer than two
    points, mismatched lengths or zero variance on either side. The result
    is clamped to [-1, 1] so rounding never escapes the range.
    """
    _require_decimal_list("xs", xs)
    _require_decimal_list("ys", ys)
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    count = Decimal(len(xs))
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count

    covariance = Decimal(0)
    var_x = Decimal(0)
    var_y = Decimal(0)
    for x_value, y_value in zip(xs, ys):
        delta_x = x_value - mean_x
        delta_y = y_value - mean_y
        covariance = covariance + delta_x * delta_y
        var_x = var_x + delta_x * delta_x
        var_y = var_y + delta_y * delta_y

    if var_x <= 0 or var_y <= 0:
        return None
    denominator = (var_x * var_y).sqrt()
    if denominator <= 0:
        return None

    result = covariance / denominator
    if result > 1:
        return Decimal(1)
    if result < -1:
        return Decimal(-1)
    return result


def correlate_closes(
    candidate: list[Decimal],
    other: list[Decimal],
    *,
    window: int = 60,
    min_returns: int = 30,
) -> Decimal | None:
    """Correlation of the last ``window`` closes of both series (D-2).

    ``None`` (unknown) when either side is shorter than the window, the
    window yields fewer than ``min_returns`` points or a side has no
    variance. The caller never blocks on ``None``.
    """
    if not isinstance(window, int) or isinstance(window, bool):
        raise TypeError("window must be int")
    if not isinstance(min_returns, int) or isinstance(min_returns, bool):
        raise TypeError("min_returns must be int")
    if window < 2 or min_returns < 1:
        raise ValueError("window >= 2 and min_returns >= 1 required")
    _require_decimal_list("candidate", candidate)
    _require_decimal_list("other", other)
    if len(candidate) < window or len(other) < window:
        return None

    candidate_returns = pct_returns(candidate[-window:])
    other_returns = pct_returns(other[-window:])
    if len(candidate_returns) < min_returns:
        return None
    return pearson(candidate_returns, other_returns)


def halved_share(capital_usd: Decimal) -> Decimal:
    """Half of the position share: 12.5% of the capital (D-3)."""
    if not isinstance(capital_usd, Decimal):
        raise TypeError("capital_usd must be Decimal")
    if capital_usd < 0:
        raise ValueError("capital_usd must be >= 0")
    return capital_usd * MAX_POSITION_SHARE / Decimal(2)


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Floor ``value`` down to a multiple of ``step`` (never rounds up)."""
    if not isinstance(value, Decimal):
        raise TypeError("value must be Decimal")
    if not isinstance(step, Decimal):
        raise TypeError("step must be Decimal")
    if step <= 0:
        raise ValueError("step must be > 0")
    return (value // step) * step

"""Candidate scoring with explicit weights (spec 006, RF-6).

Pure module: no network, no database, no framework imports. The score is the
weighted sum of normalized factors (0-100); as soon as one required feature
is ``None`` the candidate is excluded with ``missing`` (D-6, fail-closed).
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.domain.feature_engine import FeatureVector

_SCORE_PLACES = Decimal("0.01")
_HUNDRED = Decimal("100")

DEFAULT_WEIGHTS: dict[str, Decimal] = {
    "momentum": Decimal("0.30"),
    "volume": Decimal("0.25"),
    "trend": Decimal("0.25"),
    "range": Decimal("0.20"),
}

# Factor → FeatureVector attribute (all mandatory, D-6).
_FACTOR_FEATURE: dict[str, str] = {
    "momentum": "return_pct",
    "volume": "volume_zscore",
    "trend": "ema_spread_pct",
    "range": "range_position_pct",
}


@dataclass(frozen=True)
class FactorContribution:
    name: str
    weight: Decimal
    normalized: Decimal
    contribution: Decimal


@dataclass(frozen=True)
class CandidateScore:
    score: Decimal
    factors: tuple[FactorContribution, ...]
    missing: tuple[str, ...]


def _clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _normalize(name: str, value: Decimal) -> Decimal:
    """Clamp and scale one raw feature to the 0..1 factor range."""
    if name in ("momentum", "volume"):
        low, high = Decimal("-2"), Decimal("2")
        return (_clamp(value, low, high) + Decimal(2)) / Decimal(4)
    if name == "trend":
        low, high = Decimal("-1"), Decimal("1")
        return (_clamp(value, low, high) + Decimal(1)) / Decimal(2)
    return _clamp(value / _HUNDRED, Decimal(0), Decimal(1))


def normalize_weights(raw: str | None) -> tuple[dict[str, Decimal], bool]:
    """Parse a ``key:weight`` CSV; return ``(weights, used_default)``.

    Any garbage (missing key, unknown key, non-numeric, sum != 1) falls back
    to ``DEFAULT_WEIGHTS`` instead of failing.
    """
    if not raw:
        return dict(DEFAULT_WEIGHTS), True
    parsed: dict[str, Decimal] = {}
    try:
        for chunk in raw.split(","):
            key, separator, value = chunk.strip().partition(":")
            key = key.strip()
            if not separator or not key:
                return dict(DEFAULT_WEIGHTS), True
            if key not in DEFAULT_WEIGHTS or key in parsed:
                return dict(DEFAULT_WEIGHTS), True
            weight = Decimal(value.strip())
            if weight < 0:
                return dict(DEFAULT_WEIGHTS), True
            parsed[key] = weight
    except (InvalidOperation, ValueError):
        return dict(DEFAULT_WEIGHTS), True
    if set(parsed) != set(DEFAULT_WEIGHTS):
        return dict(DEFAULT_WEIGHTS), True
    if sum(parsed.values(), Decimal(0)) != Decimal(1):
        return dict(DEFAULT_WEIGHTS), True
    ordered = {key: parsed[key] for key in DEFAULT_WEIGHTS}
    return ordered, False


def score_candidate(
    features: FeatureVector,
    *,
    weights: dict[str, Decimal] | None = None,
) -> CandidateScore:
    """Score one candidate 0-100 with explained factors (RF-6)."""
    active = dict(DEFAULT_WEIGHTS) if weights is None else weights
    missing = tuple(
        name
        for name in DEFAULT_WEIGHTS
        if getattr(features, _FACTOR_FEATURE[name]) is None
    )
    if missing:
        return CandidateScore(
            score=Decimal(0), factors=(), missing=missing
        )

    factors: list[FactorContribution] = []
    total = Decimal(0)
    for name in DEFAULT_WEIGHTS:
        weight = active.get(name, DEFAULT_WEIGHTS[name])
        raw = getattr(features, _FACTOR_FEATURE[name])
        normalized = _normalize(name, raw)
        contribution = weight * normalized
        factors.append(
            FactorContribution(
                name=name,
                weight=weight,
                normalized=normalized,
                contribution=contribution,
            )
        )
        total += contribution
    score = (total * _HUNDRED).quantize(_SCORE_PLACES, rounding=ROUND_HALF_UP)
    return CandidateScore(
        score=score, factors=tuple(factors), missing=()
    )

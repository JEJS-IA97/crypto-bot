"""Tests rojos — Spec 006: candidate_engine (RF-6).

Score 0-100 con pesos explícitos, contribuciones por factor y exclusión
fail-closed con `missing_data` (D-6).
"""

import unittest
from decimal import Decimal

from app.domain.feature_engine import FeatureVector


def _vector(**overrides) -> FeatureVector:
    values = {
        "return_pct": Decimal("0"),
        "volatility_pct": Decimal("1"),
        "range_position_pct": Decimal("50"),
        "volume_zscore": Decimal("0"),
        "ema_spread_pct": Decimal("0"),
        "rsi": Decimal("50"),
    }
    values.update(overrides)
    return FeatureVector(**values)


class ScoringTests(unittest.TestCase):
    def test_perfect_factors_score_100(self) -> None:
        from app.domain.candidate_engine import score_candidate

        perfect = _vector(
            return_pct=Decimal("2"),    # clamp máx +2%
            volume_zscore=Decimal("2"),  # clamp máx +2
            ema_spread_pct=Decimal("1"),  # clamp máx +1%
            range_position_pct=Decimal("100"),
        )
        result = score_candidate(perfect)
        self.assertEqual(result.score, Decimal("100"))
        self.assertEqual(result.missing, ())
        self.assertEqual(len(result.factors), 4)

    def test_worst_factors_score_0(self) -> None:
        from app.domain.candidate_engine import score_candidate

        worst = _vector(
            return_pct=Decimal("-2"),
            volume_zscore=Decimal("-2"),
            ema_spread_pct=Decimal("-1"),
            range_position_pct=Decimal("0"),
        )
        result = score_candidate(worst)
        self.assertEqual(result.score, Decimal("0"))
        self.assertEqual(result.missing, ())

    def test_mid_values_expected_score(self) -> None:
        from app.domain.candidate_engine import score_candidate

        mid = _vector(
            return_pct=Decimal("1"),      # norm (1+2)/4 = 0.75
            volume_zscore=Decimal("0.5"),  # norm (0.5+2)/4 = 0.625
            ema_spread_pct=Decimal("0.5"),  # norm (0.5+1)/2 = 0.75
            range_position_pct=Decimal("50"),  # norm 0.5
        )
        result = score_candidate(mid)
        # 100*(0.30*0.75 + 0.25*0.625 + 0.25*0.75 + 0.20*0.5)
        # = 100*(0.225 + 0.15625 + 0.1875 + 0.10) = 66.875 → 66.88
        self.assertEqual(result.score, Decimal("66.88"))

    def test_contributions_sum_to_score(self) -> None:
        from app.domain.candidate_engine import score_candidate

        vector = _vector(
            return_pct=Decimal("1"),
            volume_zscore=Decimal("0.5"),
            ema_spread_pct=Decimal("0.5"),
            range_position_pct=Decimal("70"),
        )
        result = score_candidate(vector)
        total = sum(
            (factor.contribution for factor in result.factors),
            Decimal("0"),
        )
        self.assertAlmostEqual(
            float(total * 100), float(result.score), places=1
        )

    def test_missing_feature_excludes_candidate(self) -> None:
        from app.domain.candidate_engine import score_candidate

        vector = _vector(return_pct=None)
        result = score_candidate(vector)
        self.assertEqual(result.missing, ("momentum",))
        self.assertEqual(result.score, Decimal("0"))

    def test_default_weights_sum_to_one(self) -> None:
        from app.domain.candidate_engine import DEFAULT_WEIGHTS

        total = sum(DEFAULT_WEIGHTS.values(), Decimal("0"))
        self.assertEqual(total, Decimal("1"))
        self.assertEqual(
            set(DEFAULT_WEIGHTS),
            {"momentum", "volume", "trend", "range"},
        )

    def test_normalize_weights_accepts_valid_csv(self) -> None:
        from app.domain.candidate_engine import normalize_weights

        weights, used_default = normalize_weights(
            "momentum:0.5,volume:0.3,trend:0.1,range:0.1"
        )
        self.assertFalse(used_default)
        self.assertEqual(weights["momentum"], Decimal("0.5"))
        self.assertEqual(
            sum(weights.values(), Decimal("0")), Decimal("1")
        )

    def test_normalize_weights_falls_back_on_garbage(self) -> None:
        from app.domain.candidate_engine import (
            DEFAULT_WEIGHTS,
            normalize_weights,
        )

        for raw in (
            None,
            "",
            "foo:1",
            "momentum:0.9,volume:0.9,trend:0.05,range:0.05",
            "momentum:x,volume:0.5,trend:0.3,range:0.2",
        ):
            weights, used_default = normalize_weights(raw)
            self.assertTrue(used_default, f"debía usar defecto: {raw!r}")
            self.assertEqual(weights, DEFAULT_WEIGHTS)


if __name__ == "__main__":
    unittest.main()

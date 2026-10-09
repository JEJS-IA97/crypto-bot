"""Tests rojos — Spec 008: matemática de cartera (RF-5, D-2/D-3).

Módulo puro (sin red, sin BD) con los rendimientos y el coeficiente de
Pearson que el risk engine usa para decidir la redimensión correlacionada.
"""

import unittest
from decimal import Decimal

from app.domain.portfolio_math import (
    correlate_closes,
    floor_to_step,
    halved_share,
    pct_returns,
    pearson,
)
from app.domain.risk_math import MAX_POSITION_SHARE


def _rising(count: int = 60, start: str = "100") -> list[Decimal]:
    base = Decimal(start)
    return [base + Decimal(index) for index in range(count)]


def _falling(count: int = 60, start: str = "200") -> list[Decimal]:
    base = Decimal(start)
    return [base - Decimal(index) for index in range(count)]


def _constant(count: int = 60) -> list[Decimal]:
    return [Decimal("100") for _ in range(count)]


class PctReturnsTests(unittest.TestCase):
    def test_returns_are_period_over_period(self) -> None:
        returns = pct_returns([Decimal("100"), Decimal("101"), Decimal("102")])
        self.assertEqual(len(returns), 2)
        self.assertEqual(returns[0], (Decimal("101") - Decimal("100")) / Decimal("100"))
        self.assertEqual(returns[1], (Decimal("102") - Decimal("101")) / Decimal("101"))

    def test_too_few_closes_returns_empty(self) -> None:
        self.assertEqual(pct_returns([]), [])
        self.assertEqual(pct_returns([Decimal("100")]), [])

    def test_decimal_only(self) -> None:
        with self.assertRaises(TypeError):
            pct_returns([Decimal("100"), 101.0])  # type: ignore[list-item]


class PearsonTests(unittest.TestCase):
    def test_identical_series_is_one(self) -> None:
        values = _rising()
        result = pearson(values, values)
        self.assertIsInstance(result, Decimal)
        self.assertLessEqual(result, Decimal("1"))
        self.assertGreaterEqual(result, Decimal("1") - Decimal("1e-12"))

    def test_inverse_series_is_minus_one(self) -> None:
        values = _rising()
        result = pearson(values, list(reversed(values)))
        self.assertIsInstance(result, Decimal)
        self.assertGreaterEqual(result, Decimal("-1") - Decimal("1e-12"))
        self.assertLessEqual(result, Decimal("-1") + Decimal("1e-12"))

    def test_constant_series_is_none(self) -> None:
        self.assertIsNone(pearson(_constant(), _rising()))

    def test_too_few_points_is_none(self) -> None:
        self.assertIsNone(pearson([Decimal("1")], [Decimal("2")]))
        self.assertIsNone(pearson([], []))

    def test_mismatched_lengths_is_none(self) -> None:
        self.assertIsNone(
            pearson(_rising(10), _rising(9))
        )

    def test_is_symmetric(self) -> None:
        left = _rising()
        right = [value * Decimal("2") + Decimal("7") for value in _rising()]
        self.assertEqual(pearson(left, right), pearson(right, left))

    def test_decimal_only(self) -> None:
        with self.assertRaises(TypeError):
            pearson([1.0, 2.0], [3.0, 4.0])  # type: ignore[arg-type]


class CorrelateClosesTests(unittest.TestCase):
    def test_identical_windows_are_correlated(self) -> None:
        result = correlate_closes(_rising(), _rising())
        self.assertIsInstance(result, Decimal)
        self.assertGreaterEqual(result, Decimal("0.99"))

    def test_short_window_is_unknown(self) -> None:
        self.assertIsNone(correlate_closes(_rising(10), _rising(10)))

    def test_constant_closes_are_unknown(self) -> None:
        self.assertIsNone(correlate_closes(_constant(), _constant()))


class HalvedShareTests(unittest.TestCase):
    def test_is_half_of_the_position_share(self) -> None:
        self.assertEqual(halved_share(Decimal("100")), Decimal("12.5"))
        expected = Decimal("20") * MAX_POSITION_SHARE / Decimal("2")
        self.assertEqual(halved_share(Decimal("20")), expected)

    def test_decimal_only(self) -> None:
        with self.assertRaises(TypeError):
            halved_share(100.0)  # type: ignore[arg-type]


class FloorToStepTests(unittest.TestCase):
    def test_floor_is_conservative(self) -> None:
        self.assertEqual(
            floor_to_step(Decimal("6.25"), Decimal("0.1")), Decimal("6.2")
        )
        self.assertEqual(
            floor_to_step(Decimal("6.2"), Decimal("0.1")), Decimal("6.2")
        )
        self.assertEqual(
            floor_to_step(Decimal("100"), Decimal("3")), Decimal("99")
        )


if __name__ == "__main__":
    unittest.main()

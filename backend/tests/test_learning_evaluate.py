"""Tests rojos — Spec 010: evaluación estadística determinista (RF-2).

Cruza hipótesis con ``SignalDecision`` CLOSED ya persistidas: muestra,
favorables/desfavorables, confianza (ratio Decimal) y nota de muestra
insuficiente; VALIDATED solo automáticamente desde TESTING.
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    SignalDecision,
    TradeSide,
)
from app.services.learning_service import (
    create_hypothesis,
    evaluate_hypothesis,
    transition_hypothesis,
)

NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class EvaluateHypothesisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self._counter = 0

        for attr, value in (
            ("learning_min_cases", 5),
            ("learning_min_favorable_ratio", Decimal("0.60")),
            ("learning_window_days", 90),
        ):
            patcher = patch.object(settings, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self.db.close()

    def _closed(
        self,
        symbol: str,
        pnl: str,
        closed_at: datetime | None = None,
    ) -> None:
        self._counter += 1
        self.db.add(
            SignalDecision(
                client_order_id=f"eval-{self._counter}",
                symbol=symbol,
                side=TradeSide.BUY,
                origin=DecisionOrigin.TECHNICAL,
                status=DecisionStatus.CLOSED,
                config_json="{}",
                market_snapshot_json="{}",
                quantity=Decimal("0.1"),
                price=Decimal("100"),
                pnl_usd=Decimal(pnl),
                closed_at=closed_at or NOW,
            )
        )
        self.db.commit()

    def _testing(self, **overrides) -> object:
        params = {
            "statement": "ORB gana en sesiones de alta volatilidad",
            "assets_json": '["BTCUSDT"]',
            "observed_period_start": (
                NOW - timedelta(days=60)
            ).isoformat(),
            "observed_period_finish": NOW.isoformat(),
        }
        params.update(overrides)
        hypothesis = create_hypothesis(self.db, **params)
        transition_hypothesis(self.db, hypothesis, "TESTING")
        return hypothesis

    def test_insufficient_sample_stays_testing_with_note(self) -> None:
        hypothesis = self._testing()
        self._closed("BTCUSDT", "0.50")
        self._closed("BTCUSDT", "-0.20")

        evaluate_hypothesis(self.db, hypothesis, now=NOW)

        self.assertEqual(hypothesis.status, "TESTING")
        self.assertEqual(hypothesis.case_count, 2)
        self.assertEqual(hypothesis.favorable_cases, 1)
        self.assertEqual(hypothesis.unfavorable_cases, 1)
        self.assertEqual(Decimal(hypothesis.confidence), Decimal("0.50"))
        self.assertIn("insuficiente", hypothesis.evaluation_note)

    def test_ratio_above_threshold_validates(self) -> None:
        hypothesis = self._testing()
        for pnl in ("0.50", "0.40", "0.30", "0.20", "-0.10"):
            self._closed("BTCUSDT", pnl)

        evaluate_hypothesis(self.db, hypothesis, now=NOW)

        self.assertEqual(hypothesis.status, "VALIDATED")
        self.assertEqual(hypothesis.case_count, 5)
        self.assertEqual(hypothesis.favorable_cases, 4)
        self.assertEqual(hypothesis.unfavorable_cases, 1)
        self.assertEqual(Decimal(hypothesis.confidence), Decimal("0.80"))

    def test_ratio_below_threshold_stays_testing(self) -> None:
        hypothesis = self._testing()
        for pnl in ("0.50", "-0.40", "-0.30", "-0.20", "-0.10"):
            self._closed("BTCUSDT", pnl)

        evaluate_hypothesis(self.db, hypothesis, now=NOW)

        self.assertEqual(hypothesis.status, "TESTING")
        self.assertEqual(Decimal(hypothesis.confidence), Decimal("0.20"))
        self.assertTrue(hypothesis.evaluation_note)

    def test_evaluate_outside_testing_is_forbidden(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")

        with self.assertRaises(ValueError):
            evaluate_hypothesis(self.db, hypothesis, now=NOW)

    def test_assets_filter_counts_only_declared_symbols(self) -> None:
        hypothesis = self._testing()
        self._closed("BTCUSDT", "0.50")
        self._closed("BTCUSDT", "0.40")
        self._closed("BTCUSDT", "0.30")
        self._closed("BTCUSDT", "0.20")
        self._closed("ETHUSDT", "-0.90")

        evaluate_hypothesis(self.db, hypothesis, now=NOW)

        self.assertEqual(hypothesis.case_count, 4)
        self.assertEqual(hypothesis.status, "VALIDATED")

    def test_window_excludes_older_decisions(self) -> None:
        hypothesis = self._testing()
        fresh = NOW - timedelta(days=10)
        stale = NOW - timedelta(days=120)
        self._closed("BTCUSDT", "0.50", closed_at=fresh)
        self._closed("BTCUSDT", "0.40", closed_at=fresh)
        self._closed("BTCUSDT", "0.30", closed_at=fresh)
        self._closed("BTCUSDT", "0.20", closed_at=fresh)
        self._closed("BTCUSDT", "-0.10", closed_at=fresh)
        self._closed("BTCUSDT", "-9.99", closed_at=stale)

        evaluate_hypothesis(self.db, hypothesis, now=NOW)

        self.assertEqual(hypothesis.case_count, 5)
        self.assertEqual(hypothesis.status, "VALIDATED")

    def test_evaluation_is_deterministic(self) -> None:
        hypothesis = self._testing()
        for pnl in ("0.50", "-0.40", "-0.30", "-0.20", "-0.10"):
            self._closed("BTCUSDT", pnl)

        evaluate_hypothesis(self.db, hypothesis, now=NOW)
        first = (
            hypothesis.case_count,
            hypothesis.favorable_cases,
            str(hypothesis.confidence),
            hypothesis.status,
        )
        evaluate_hypothesis(self.db, hypothesis, now=NOW)
        second = (
            hypothesis.case_count,
            hypothesis.favorable_cases,
            str(hypothesis.confidence),
            hypothesis.status,
        )

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

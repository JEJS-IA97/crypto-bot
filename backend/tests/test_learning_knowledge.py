"""Tests rojos — Spec 010: conocimiento confirmado y rollback (RF-3).

La promoción VALIDATED→ACTIVE es manual y crea la fila de knowledge con
evidencia e intervalo Wald; el rollback marca DEPRECATED sin borrar;
el conocimiento degradado no vuelve a ACTIVE.
"""

import json
import unittest
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import SystemEvent
from app.services.learning_service import (
    create_hypothesis,
    create_manual_knowledge,
    list_knowledge,
    transition_hypothesis,
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class KnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def _validated_with_samples(self, fav: int, unfav: int):
        hypothesis = create_hypothesis(
            self.db,
            statement="ORB funciona en aperturas de alta volatilidad",
            assets_json='["BTCUSDT"]',
        )
        transition_hypothesis(self.db, hypothesis, "TESTING")
        hypothesis.case_count = fav + unfav
        hypothesis.favorable_cases = fav
        hypothesis.unfavorable_cases = unfav
        hypothesis.confidence = Decimal(fav) / Decimal(fav + unfav)
        hypothesis.status = "VALIDATED"
        hypothesis.version = 3
        self.db.commit()
        return hypothesis

    def test_active_promotion_creates_knowledge(self) -> None:
        hypothesis = self._validated_with_samples(fav=4, unfav=1)

        transition_hypothesis(
            self.db, hypothesis, "ACTIVE", reason="umbral superado"
        )

        self.assertEqual(hypothesis.status, "ACTIVE")
        rows = list_knowledge(self.db, status="ACTIVE")
        self.assertEqual(len(rows), 1)
        knowledge = rows[0]
        self.assertEqual(knowledge.hypothesis_id, hypothesis.id)
        self.assertEqual(knowledge.statement, hypothesis.statement)
        self.assertEqual(knowledge.sample_size, 5)
        self.assertEqual(knowledge.version, 1)
        self.assertIsNotNone(knowledge.validated_at)

        interval = json.loads(knowledge.confidence_interval_json)
        self.assertIsNotNone(interval)
        self.assertIn("low", interval)
        self.assertIn("high", interval)
        self.assertLessEqual(
            Decimal(interval["low"]), Decimal("0.80")
        )
        self.assertGreaterEqual(
            Decimal(interval["high"]), Decimal("0.80")
        )

        events = list(
            self.db.scalars(
                select(SystemEvent).where(
                    SystemEvent.service == "learning",
                    SystemEvent.event == "knowledge.promoted",
                )
            ).all()
        )
        self.assertEqual(len(events), 1)

    def test_active_requires_reason(self) -> None:
        hypothesis = self._validated_with_samples(fav=4, unfav=1)

        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "ACTIVE")

        self.assertEqual(hypothesis.status, "VALIDATED")
        self.assertEqual(list_knowledge(self.db), [])

    def test_rollback_marks_deprecated_and_keeps_row(self) -> None:
        hypothesis = self._validated_with_samples(fav=4, unfav=1)
        transition_hypothesis(
            self.db, hypothesis, "ACTIVE", reason="umbral superado"
        )

        transition_hypothesis(
            self.db,
            hypothesis,
            "DEPRECATED",
            reason="contradicciones en paper reciente",
        )

        self.assertEqual(hypothesis.status, "DEPRECATED")
        rows = list_knowledge(self.db, status="DEPRECATED")
        self.assertEqual(len(rows), 1)
        knowledge = rows[0]
        self.assertIsNotNone(knowledge.deprecated_at)
        self.assertEqual(
            knowledge.rollback_reason,
            "contradicciones en paper reciente",
        )

        events = list(
            self.db.scalars(
                select(SystemEvent).where(
                    SystemEvent.service == "learning",
                    SystemEvent.event == "knowledge.rolled_back",
                )
            ).all()
        )
        self.assertEqual(len(events), 1)

    def test_deprecated_knowledge_cannot_return_to_active(self) -> None:
        hypothesis = self._validated_with_samples(fav=4, unfav=1)
        transition_hypothesis(
            self.db, hypothesis, "ACTIVE", reason="umbral superado"
        )
        transition_hypothesis(
            self.db, hypothesis, "DEPRECATED", reason="falló"
        )

        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "ACTIVE")

    def test_rollback_requires_reason(self) -> None:
        hypothesis = self._validated_with_samples(fav=4, unfav=1)
        transition_hypothesis(
            self.db, hypothesis, "ACTIVE", reason="umbral superado"
        )

        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "DEPRECATED")

        self.assertEqual(hypothesis.status, "ACTIVE")

    def test_manual_knowledge_without_hypothesis(self) -> None:
        knowledge = create_manual_knowledge(
            self.db,
            statement="El drawdown diario ≥5% bloquea aperturas",
            evidence={"source": "constitucion", "ref": "RF-16"},
        )

        self.assertIsNone(knowledge.hypothesis_id)
        self.assertEqual(knowledge.status, "ACTIVE")
        self.assertEqual(knowledge.version, 1)

    def test_manual_knowledge_requires_evidence(self) -> None:
        with self.assertRaises(ValueError):
            create_manual_knowledge(
                self.db,
                statement="sin evidencia",
                evidence={},
            )


if __name__ == "__main__":
    unittest.main()

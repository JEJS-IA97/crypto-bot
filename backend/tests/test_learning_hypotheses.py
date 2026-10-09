"""Tests rojos — Spec 010: hipótesis y máquina de estados (RF-1/RF-3).

Modelo ``Hypothesis``, creación con defaults honestos, listado y
transiciones de la máquina PROPOSED→TESTING→VALIDATED→ACTIVE→DEPRECATED
con ``REJECTED`` lateral; toda transición emite evento 005 ``learning``.
"""

import json
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.models import SystemEvent
from app.services.learning_service import (
    create_hypothesis,
    list_hypotheses,
    transition_hypothesis,
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class HypothesisModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def test_create_with_honest_defaults(self) -> None:
        hypothesis = create_hypothesis(
            self.db,
            statement="Funding extremo anticipa reversiones",
        )

        self.assertEqual(hypothesis.status, "PROPOSED")
        self.assertEqual(hypothesis.version, 1)
        self.assertEqual(hypothesis.case_count, 0)
        self.assertEqual(hypothesis.favorable_cases, 0)
        self.assertEqual(hypothesis.unfavorable_cases, 0)
        self.assertIsNone(hypothesis.confidence)
        self.assertEqual(hypothesis.source, "operator")
        self.assertIsNotNone(hypothesis.created_at)
        self.assertIsNotNone(hypothesis.updated_at)

    def test_list_filters_by_status(self) -> None:
        create_hypothesis(self.db, statement="una")
        other = create_hypothesis(self.db, statement="dos")
        transition_hypothesis(self.db, other, "TESTING")

        proposed = list_hypotheses(self.db, status="PROPOSED")
        testing = list_hypotheses(self.db, status="TESTING")

        self.assertEqual([h.statement for h in proposed], ["una"])
        self.assertEqual([h.statement for h in testing], ["dos"])

    def test_legal_transition_updates_status_and_version(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")

        transition_hypothesis(self.db, hypothesis, "TESTING")

        self.assertEqual(hypothesis.status, "TESTING")
        self.assertEqual(hypothesis.version, 2)

    def test_transition_emits_learning_event(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")
        transition_hypothesis(self.db, hypothesis, "TESTING")

        events = list(
            self.db.scalars(
                select(SystemEvent).where(
                    SystemEvent.service == "learning"
                )
            ).all()
        )
        transitions = [
            event for event in events
            if event.event == "hypothesis.transitioned"
        ]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(
            json.loads(transitions[0].payload_json)["from"], "PROPOSED"
        )
        self.assertEqual(
            json.loads(transitions[0].payload_json)["to"], "TESTING"
        )

    def test_proposed_to_active_is_forbidden(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")

        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "ACTIVE")

        self.assertEqual(hypothesis.status, "PROPOSED")
        self.assertEqual(hypothesis.version, 1)

    def test_deprecated_cannot_return_to_active(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")
        transition_hypothesis(self.db, hypothesis, "TESTING")
        # VALIDATED → ACTIVE se prueba en test_learning_knowledge.
        hypothesis.status = "ACTIVE"
        hypothesis.version = 3
        self.db.commit()

        transition_hypothesis(self.db, hypothesis, "DEPRECATED")
        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "ACTIVE")

    def test_rejected_requires_reason(self) -> None:
        hypothesis = create_hypothesis(self.db, statement="una")

        with self.assertRaises(ValueError):
            transition_hypothesis(self.db, hypothesis, "REJECTED")

        self.assertEqual(hypothesis.status, "PROPOSED")


if __name__ == "__main__":
    unittest.main()

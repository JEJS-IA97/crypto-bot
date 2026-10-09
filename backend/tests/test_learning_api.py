"""Tests rojos — Spec 010: API de learning (RF-4).

`/api/learning/*` con `API_TOKEN` (patrón 001 RF-20): 401 sin token
configurado/exigido, 200/201 en lecturas y altas, 409 en transiciones
ilegales o evaluación fuera de TESTING, 422 sin motivo obligatorio,
404 para hipótesis inexistente.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.main import app
from app.services.learning_service import (
    create_hypothesis,
    transition_hypothesis,
)


class LearningApiBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="learning-api-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        path = Path(self.tmpdir) / "learning.db"
        engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )
        _enable_sqlite_foreign_keys(engine)
        Base.metadata.create_all(engine)
        self.engine = engine
        self.addCleanup(engine.dispose)
        self.factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )
        patcher = patch("app.database.SessionLocal", self.factory)
        patcher.start()
        self.addCleanup(patcher.stop)

        token_patcher = patch.object(settings, "api_token", "sekret")
        token_patcher.start()
        self.addCleanup(token_patcher.stop)

        self.client = TestClient(app)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": "Bearer sekret"}


class LearningAuthTests(LearningApiBase):
    def test_missing_token_is_401(self) -> None:
        response = self.client.get("/api/learning/hypotheses")
        self.assertEqual(response.status_code, 401)

    def test_wrong_token_is_401(self) -> None:
        response = self.client.get(
            "/api/learning/hypotheses",
            headers={"Authorization": "Bearer otro"},
        )
        self.assertEqual(response.status_code, 401)


class LearningEndpointsTests(LearningApiBase):
    def test_create_and_list_hypotheses(self) -> None:
        created = self.client.post(
            "/api/learning/hypotheses",
            headers=self._auth(),
            json={"statement": "funding extremo ⇒ reversión"},
        )
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertEqual(body["status"], "PROPOSED")
        self.assertEqual(body["version"], 1)
        self.assertEqual(body["source"], "operator")
        self.assertEqual(body["case_count"], 0)
        self.assertIsNone(body["confidence"])

        listed = self.client.get(
            "/api/learning/hypotheses",
            headers=self._auth(),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

    def test_transition_endpoint_and_invalid_409(self) -> None:
        db = self.factory()
        try:
            hypothesis = create_hypothesis(
                db, statement="una", assets_json="[]"
            )
            hypothesis_id = hypothesis.id
        finally:
            db.close()

        ok = self.client.post(
            f"/api/learning/hypotheses/{hypothesis_id}/transition",
            headers=self._auth(),
            json={"to": "TESTING"},
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "TESTING")

        invalid = self.client.post(
            f"/api/learning/hypotheses/{hypothesis_id}/transition",
            headers=self._auth(),
            json={"to": "ACTIVE", "reason": "salto ilegal"},
        )
        self.assertEqual(invalid.status_code, 409)

    def test_active_without_reason_is_422(self) -> None:
        db = self.factory()
        try:
            hypothesis = create_hypothesis(db, statement="una")
            transition_hypothesis(db, hypothesis, "TESTING")
            hypothesis.status = "VALIDATED"
            hypothesis.case_count = 5
            hypothesis.favorable_cases = 5
            hypothesis.unfavorable_cases = 0
            hypothesis.confidence = None
            hypothesis.version = 3
            db.commit()
            hypothesis_id = hypothesis.id
        finally:
            db.close()

        response = self.client.post(
            f"/api/learning/hypotheses/{hypothesis_id}/transition",
            headers=self._auth(),
            json={"to": "ACTIVE"},
        )
        self.assertEqual(response.status_code, 422)

    def test_evaluate_endpoint(self) -> None:
        db = self.factory()
        try:
            hypothesis = create_hypothesis(db, statement="una")
            hypothesis_id = hypothesis.id
        finally:
            db.close()

        forbidden = self.client.post(
            f"/api/learning/hypotheses/{hypothesis_id}/evaluate",
            headers=self._auth(),
        )
        self.assertEqual(forbidden.status_code, 409)

        db = self.factory()
        try:
            from app.models import Hypothesis

            row = db.get(Hypothesis, hypothesis_id)
            transition_hypothesis(db, row, "TESTING")
        finally:
            db.close()

        ok = self.client.post(
            f"/api/learning/hypotheses/{hypothesis_id}/evaluate",
            headers=self._auth(),
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["status"], "TESTING")

    def test_knowledge_list(self) -> None:
        response = self.client.get(
            "/api/learning/knowledge",
            headers=self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_unknown_hypothesis_is_404(self) -> None:
        response = self.client.post(
            "/api/learning/hypotheses/99999/transition",
            headers=self._auth(),
            json={"to": "TESTING"},
        )
        self.assertEqual(response.status_code, 404)

    def test_strategy_versions_endpoints(self) -> None:
        listed = self.client.get(
            "/api/learning/strategy-versions",
            headers=self._auth(),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json(), [])

        created = self.client.post(
            "/api/learning/strategy-versions",
            headers=self._auth(),
            json={
                "version": "orb-001-v4",
                "config_json": {"stop_loss_pct": "0.02"},
                "evidence_json": [],
                "backtest_ref": "split-2026q2",
                "motive": "ajuste de stop tras validación",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["version"], "orb-001-v4")

        rolled = self.client.post(
            f"/api/learning/strategy-versions/{created.json()['id']}/rollback",
            headers=self._auth(),
            json={"reason": "peor rendimiento en paper"},
        )
        self.assertEqual(rolled.status_code, 200)
        self.assertIsNotNone(rolled.json()["rolled_back_at"])


if __name__ == "__main__":
    unittest.main()

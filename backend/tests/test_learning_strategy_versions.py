"""Tests rojos — Spec 010: registro de versiones de estrategia (RF-6).

`strategy_versions` es append-only y auditivo: registra cambios con
evidencia y marca rollback; nunca aplica configuración por sí mismo
(la aplicación sigue siendo manual, patrón env/config de la 001).
"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.services.learning_service import (
    list_strategy_versions,
    mark_rollback,
    register_strategy_version,
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class StrategyVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()

    def test_register_appends_versions(self) -> None:
        first = register_strategy_version(
            self.db,
            version="orb-001-v4",
            config_json={"stop_loss_pct": "0.02"},
            motive="ajuste de stop",
            backtest_ref="split-2026q2",
        )
        second = register_strategy_version(
            self.db,
            version="orb-001-v5",
            config_json={"stop_loss_pct": "0.025"},
            motive="review walk-forward",
        )

        rows = list_strategy_versions(self.db)
        self.assertEqual(
            [row.version for row in rows],
            ["orb-001-v4", "orb-001-v5"],
        )
        self.assertEqual(first.motive, "ajuste de stop")
        self.assertEqual(second.backtest_ref, None)
        self.assertIsNone(first.rolled_back_at)

    def test_register_does_not_apply_config(self) -> None:
        before = settings.strategy_version

        register_strategy_version(
            self.db,
            version="orb-001-v4",
            config_json={"strategy_version": "orb-001-v4"},
            motive="solo registro",
        )

        self.assertEqual(settings.strategy_version, before)

    def test_rollback_marks_row_with_reason(self) -> None:
        row = register_strategy_version(
            self.db,
            version="orb-001-v4",
            config_json={},
            motive="ajuste",
        )

        marked = mark_rollback(
            self.db, row, reason="peor rendimiento en paper"
        )

        self.assertIsNotNone(marked.rolled_back_at)
        self.assertEqual(
            marked.rollback_reason, "peor rendimiento en paper"
        )

    def test_rollback_requires_reason(self) -> None:
        row = register_strategy_version(
            self.db, version="orb-001-v4", config_json={}, motive="x"
        )

        with self.assertRaises(ValueError):
            mark_rollback(self.db, row, reason="")

    def test_double_rollback_is_forbidden(self) -> None:
        row = register_strategy_version(
            self.db, version="orb-001-v4", config_json={}, motive="x"
        )
        mark_rollback(self.db, row, reason="primero")

        with self.assertRaises(ValueError):
            mark_rollback(self.db, row, reason="segundo")


if __name__ == "__main__":
    unittest.main()

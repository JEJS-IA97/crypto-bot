"""Tests rojos — Spec 010: aislamiento de learning (RF-5).

Los servicios y rutas de learning no pueden importar ni invocar el loop
de órdenes, la ejecución, el risk engine de escritura ni el analista IA:
la memoria auditable no auto-modifica el bot (§17).
"""

import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

LEARNING_SOURCES = [
    BACKEND / "app" / "services" / "learning_service.py",
    BACKEND / "app" / "api" / "routes" / "learning.py",
]

FORBIDDEN_IMPORTS = (
    "bot_loop",
    "order_lifecycle",
    "exchange_executor",
    "simulation_executor",
    "risk_engine_service",
    "risk_guard_service",
    "ai_advisor_service",
    "bot_runner_service",
)


class LearningIsolationTests(unittest.TestCase):
    def test_learning_sources_do_not_import_trading_machinery(
        self,
    ) -> None:
        for source in LEARNING_SOURCES:
            with self.subTest(source=source.name):
                self.assertTrue(
                    source.exists(),
                    f"falta {source} (T2-T4 aún no implementados)",
                )
                text = source.read_text(encoding="utf-8")
                for forbidden in FORBIDDEN_IMPORTS:
                    self.assertNotIn(
                        f"import {forbidden}",
                        text,
                        f"{source.name} importa {forbidden}",
                    )
                    self.assertNotIn(
                        f"from app.services.{forbidden}",
                        text,
                        f"{source.name} importa {forbidden}",
                    )


if __name__ == "__main__":
    unittest.main()

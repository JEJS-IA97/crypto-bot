"""Aislamiento de la spec 011: sin red, sin BD, sin ejecución (RF-8)."""

from __future__ import annotations

import importlib
import inspect
import unittest

SERVICE_MODULES = (
    "app.services.walk_forward_service",
    "run_walk_forward",
)

FORBIDDEN = (
    "httpx",
    "requests",
    "urllib",
    "bot_loop",
    "order_lifecycle",
    "decision_store",
    "sqlalchemy",
    "ai_advisor",
    "get_session",
    "get_db",
)


class WalkForwardIsolationTest(unittest.TestCase):
    """RF-8: la corrida es offline y no toca el runtime del bot."""

    def test_modules_do_not_reference_forbidden_imports(self) -> None:
        for name in SERVICE_MODULES:
            module = importlib.import_module(name)
            source = inspect.getsource(module)
            with self.subTest(module=name):
                for token in FORBIDDEN:
                    self.assertNotIn(token, source)

    def test_service_imports_are_offline_only(self) -> None:
        # La cadena completa (dominio + motor ORB + lab) es stdlib/pura.
        module = importlib.import_module("app.services.walk_forward_service")
        source = inspect.getsource(module)
        self.assertIn("strategy_lab_service", source)
        self.assertNotIn("app.db", source)
        self.assertNotIn("SessionLocal", source)


if __name__ == "__main__":
    unittest.main()

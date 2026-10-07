"""Tests rojos — Spec 007: aislamiento IA ↔ ejecución (RF-5/RF-9).

El loop de la spec 001 y la ruta de órdenes no pueden saber nada de la IA,
y el asesor no puede importar módulos de ejecución.
"""

import importlib
import inspect
import unittest

EXECUTION_MODULES = (
    "app.services.bot_loop",
    "app.services.order_lifecycle",
    "app.services.decision_store",
    "app.services.execution_price_service",
)


class IsolationTests(unittest.TestCase):
    def test_execution_modules_do_not_reference_ai(self) -> None:
        for name in EXECUTION_MODULES:
            module = importlib.import_module(name)
            source = inspect.getsource(module)
            with self.subTest(module=name):
                self.assertNotIn("ai_advisor", source)
                self.assertNotIn("ai_daily", source)
                self.assertNotIn("AiEvaluation", source)
                self.assertNotIn("gemini", source.lower())

    def test_order_routes_do_not_reference_ai(self) -> None:
        module = importlib.import_module("app.api.routes.bot")
        source = inspect.getsource(module)
        self.assertNotIn("ai_advisor", source)
        self.assertNotIn("AiEvaluation", source)

    def test_advisor_exists_and_does_not_import_execution(self) -> None:
        module = importlib.import_module("app.services.ai_advisor_service")
        source = inspect.getsource(module)
        self.assertNotIn("bot_loop", source)
        self.assertNotIn("order_lifecycle", source)
        self.assertNotIn("decision_store", source)
        self.assertNotIn("execution_price_service", source)

    def test_daily_pass_exists_and_does_not_import_execution(self) -> None:
        module = importlib.import_module("app.services.ai_daily_analysis")
        source = inspect.getsource(module)
        self.assertNotIn("bot_loop", source)
        self.assertNotIn("order_lifecycle", source)
        self.assertNotIn("decision_store", source)


if __name__ == "__main__":
    unittest.main()

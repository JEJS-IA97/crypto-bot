"""RF-21: la zona congelada multi-exchange no cambia y sigue en verde.

Fija por SHA-256 los 8 ficheros congelados (y sus tests) en el estado del
inicio de la fase 1 y ejecuta la suite multi-exchange existente. Si alguien
toca un fichero congelado, el hash falla; si su suite se rompe, el runner
embebido falla.
"""

import hashlib
import io
import json
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
BASELINE_PATH = REPO_ROOT / "specs" / "001-bot-binance-spot" / "frozen_zone.json"

FROZEN_FILES = (
    "app/services/arbitrage_service.py",
    "app/services/trade_opportunity_service.py",
    "app/services/execution_price_service.py",
    "app/services/bot_engine.py",
    "app/services/bot_runner_service.py",
    "app/services/exchange_market_service.py",
    "app/services/okx_demo_client.py",
    "app/services/market_sync_service.py",
)

FROZEN_TEST_FILES = (
    "tests/test_arbitrage_execution.py",
    "tests/test_quote_execution_controls.py",
    "tests/test_revalidation_metrics.py",
    "tests/test_execution_lock.py",
    "tests/test_okx_demo_client.py",
    "tests/test_collect_market_snapshots.py",
)

FROZEN_TEST_MODULES = tuple(
    path.replace("/", ".").removesuffix(".py")
    for path in FROZEN_TEST_FILES
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class FrozenZoneTest(unittest.TestCase):
    def test_frozen_files_unchanged_and_green(self) -> None:
        self.assertTrue(
            BASELINE_PATH.exists(),
            f"Falta la línea base de congelación: {BASELINE_PATH}",
        )
        with BASELINE_PATH.open("r", encoding="utf-8") as handle:
            baseline = json.load(handle)

        changed: list[str] = []
        for relative in FROZEN_FILES:
            expected = baseline.get("files", {}).get(relative)
            actual = _sha256(BACKEND_ROOT / relative)
            if expected != actual:
                changed.append(relative)

        changed_tests: list[str] = []
        for relative in FROZEN_TEST_FILES:
            expected = baseline.get("tests", {}).get(relative)
            actual = _sha256(BACKEND_ROOT / relative)
            if expected != actual:
                changed_tests.append(relative)

        self.assertEqual(
            changed,
            [],
            "Ficheros congelados modificados desde el inicio de la"
            f" fase 1 (RF-21): {changed}",
        )
        self.assertEqual(
            changed_tests,
            [],
            "Tests de la zona congelada modificados (RF-21):"
            f" {changed_tests}",
        )

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromNames(FROZEN_TEST_MODULES)
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(
            suite
        )
        self.assertTrue(
            result.wasSuccessful(),
            "La suite multi-exchange congelada dejó de estar en"
            f" verde:\n{stream.getvalue()[-3000:]}",
        )


if __name__ == "__main__":
    unittest.main()

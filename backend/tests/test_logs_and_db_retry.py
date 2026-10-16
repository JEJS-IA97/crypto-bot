"""Paso 0c: log rotado 5×5 MB, httpx a WARNING y reintento ante caídas de Neon."""

import logging
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

from app.config import settings
from app.services import bot_loop
from app.services.bot_loop import CycleReport, run_once
from app.services.structured_log import configure_logging


def _db_down() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("SSL connection closed"))


class RotatingLogTests(unittest.TestCase):
    def test_log_file_uses_rotating_handler_and_quiets_httpx(self) -> None:
        root = logging.getLogger()
        original = list(root.handlers)
        root.handlers.clear()
        httpx_level = logging.getLogger("httpx").level
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "logs" / "bot.log"
            try:
                with patch.object(settings, "log_file", str(path)):
                    handler = configure_logging()
                self.assertIsInstance(handler, RotatingFileHandler)
                self.assertEqual(handler.maxBytes, 5 * 1024 * 1024)
                self.assertEqual(handler.backupCount, 5)
                self.assertTrue(path.parent.is_dir())
                self.assertEqual(
                    logging.getLogger("httpx").level, logging.WARNING
                )
            finally:
                for added in list(root.handlers):
                    root.removeHandler(added)
                    added.close()
                root.handlers.extend(original)
                logging.getLogger("httpx").setLevel(httpx_level)


@patch.object(bot_loop.time, "sleep")
class DbRetryTests(unittest.TestCase):
    def test_transient_db_error_is_retried(self, sleep: MagicMock) -> None:
        db = MagicMock()
        with patch.object(
            bot_loop,
            "_execute_cycle",
            side_effect=[_db_down(), CycleReport(status="ok")],
        ) as cycle:
            report = bot_loop._execute_cycle_with_db_retry(db)

        self.assertEqual(report.status, "ok")
        self.assertEqual(cycle.call_count, 2)
        db.rollback.assert_called_once()
        sleep.assert_called_once_with(2)

    def test_gives_up_after_backoff(self, sleep: MagicMock) -> None:
        with patch.object(
            bot_loop, "_execute_cycle", side_effect=_db_down()
        ) as cycle:
            with self.assertRaises(OperationalError):
                bot_loop._execute_cycle_with_db_retry(MagicMock())

        self.assertEqual(cycle.call_count, 4)
        self.assertEqual(
            [c.args[0] for c in sleep.call_args_list], [2, 5, 10]
        )

    def test_failed_cycle_rolls_back_session(self, sleep: MagicMock) -> None:
        # Sin rollback, marcar fuente / fase / breaker fallaba en cascada.
        db = MagicMock()
        with patch.object(
            bot_loop, "_execute_cycle", side_effect=RuntimeError("boom")
        ):
            report = run_once(db, market_data=MagicMock(), symbols=["BTCUSDT"])

        self.assertEqual(report.status, "failed")
        db.rollback.assert_called()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()

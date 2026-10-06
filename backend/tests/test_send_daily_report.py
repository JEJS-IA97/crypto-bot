"""Tests del CLI del informe diario (spec 002, RF-3, RF-4, RF-5)."""

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import send_daily_report
from app.config import settings
from app.services.email_service import EmailSendError

SMTP_VALUES = {
    "report_to": "owner@example.com",
    "smtp_user": "bot@example.com",
    "smtp_pass": "secret-pass",
    "smtp_host": "smtp.example.com",
    "smtp_port": 2525,
}


class CliConfigGuardTests(unittest.TestCase):
    def test_missing_report_to_exits(self) -> None:
        with (
            patch.object(settings, "report_to", ""),
            patch.object(settings, "smtp_user", "bot@example.com"),
            patch.object(settings, "smtp_pass", "secret-pass"),
            patch.object(send_daily_report, "send_email") as send,
        ):
            with self.assertRaises(SystemExit) as ctx:
                send_daily_report.main([])
        self.assertIn("REPORT_TO", str(ctx.exception))
        send.assert_not_called()

    def test_missing_smtp_user_exits(self) -> None:
        with (
            patch.object(settings, "report_to", "owner@example.com"),
            patch.object(settings, "smtp_user", ""),
            patch.object(settings, "smtp_pass", "secret-pass"),
            patch.object(send_daily_report, "send_email") as send,
        ):
            with self.assertRaises(SystemExit) as ctx:
                send_daily_report.main([])
        self.assertIn("SMTP_USER", str(ctx.exception))
        send.assert_not_called()

    def test_missing_smtp_pass_exits(self) -> None:
        with (
            patch.object(settings, "report_to", "owner@example.com"),
            patch.object(settings, "smtp_user", "bot@example.com"),
            patch.object(settings, "smtp_pass", ""),
            patch.object(send_daily_report, "send_email") as send,
        ):
            with self.assertRaises(SystemExit) as ctx:
                send_daily_report.main([])
        self.assertIn("SMTP_PASS", str(ctx.exception))
        send.assert_not_called()


class CliSendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="daily-report-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.db_path = Path(self.tmpdir) / "report.db"
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(bind=self.engine)

        self.patchers = [
            patch.object(send_daily_report.database, "engine", self.engine),
            patch.object(
                send_daily_report.database,
                "SessionLocal",
                self.factory,
            ),
            *(patch.object(settings, key, value) for key, value in SMTP_VALUES.items()),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_empty_database_sends_sin_datos(self) -> None:
        with patch.object(send_daily_report, "send_email") as send:
            code = send_daily_report.main([])

        self.assertEqual(code, 0)
        send.assert_called_once()
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["to"], SMTP_VALUES["report_to"])
        self.assertEqual(kwargs["host"], SMTP_VALUES["smtp_host"])
        self.assertEqual(kwargs["port"], SMTP_VALUES["smtp_port"])
        self.assertEqual(kwargs["user"], SMTP_VALUES["smtp_user"])
        self.assertEqual(kwargs["password"], SMTP_VALUES["smtp_pass"])
        self.assertTrue(
            kwargs["subject"].startswith("Informe diario — crypto-bot — ")
        )
        self.assertIn("Fase: SIMULATION", kwargs["body"])
        self.assertIn("Estado: activo", kwargs["body"])
        self.assertIn("Balance: sin datos", kwargs["body"])
        self.assertIn("Últimas 24 h: sin datos", kwargs["body"])

        self.assertTrue(self.db_path.exists())
        tables = inspect(self.engine).get_table_names()
        self.assertIn("bot_phases", tables)
        self.assertIn("signal_decisions", tables)

    def test_date_argument_targets_given_day_at_report_hour(self) -> None:
        with (
            patch.object(send_daily_report, "send_email") as send,
            patch.object(
                send_daily_report,
                "build_daily_report",
                return_value="X",
            ) as build,
        ):
            code = send_daily_report.main(["--date", "2026-10-01"])

        self.assertEqual(code, 0)
        self.assertEqual(
            build.call_args.kwargs["now"],
            datetime(2026, 10, 1, 8, 0),
        )
        self.assertEqual(
            send.call_args.kwargs["subject"],
            "Informe diario — crypto-bot — 2026-10-01 (UTC)",
        )

    def test_invalid_date_exits_before_sending(self) -> None:
        with patch.object(send_daily_report, "send_email") as send:
            with self.assertRaises(SystemExit) as ctx:
                send_daily_report.main(["--date", "hoy"])
        self.assertIn("YYYY-MM-DD", str(ctx.exception))
        send.assert_not_called()

    def test_send_failure_propagates_for_ci_visibility(self) -> None:
        with patch.object(
            send_daily_report,
            "send_email",
            side_effect=EmailSendError("boom"),
        ):
            with self.assertRaises(EmailSendError):
                send_daily_report.main([])


if __name__ == "__main__":
    unittest.main()

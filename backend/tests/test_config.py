import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import _enable_sqlite_foreign_keys, engine as app_engine


def _settings_without_env() -> Settings:
    """Settings cargadas sin .env ni variables de entorno heredadas."""
    clean = {k: v for k, v in os.environ.items() if k != "ALLOW_LIVE_TRADING"}
    with patch.dict(os.environ, clean, clear=True):
        return Settings(_env_file=None)


class ConfigTests(unittest.TestCase):
    def test_live_trading_disabled_by_default(self) -> None:
        settings = _settings_without_env()
        self.assertIs(settings.allow_live_trading, False)
        self.assertEqual(settings.configured_capital_usd, Decimal("20"))
        self.assertEqual(settings.api_token, "")

    def test_live_trading_enabled_by_env(self) -> None:
        with patch.dict(os.environ, {"ALLOW_LIVE_TRADING": "true"}, clear=True):
            settings = Settings(_env_file=None)
        self.assertIs(settings.allow_live_trading, True)

    def test_trading_settings_defaults(self) -> None:
        settings = _settings_without_env()
        self.assertEqual(settings.stop_loss_pct, Decimal("2.0"))
        self.assertEqual(settings.take_profit_pct, Decimal("4.0"))
        self.assertEqual(settings.max_signal_price_distance_pct, Decimal("1.0"))
        self.assertEqual(settings.signal_ttl_seconds, 300)
        self.assertEqual(settings.trading_interval_seconds, 60)
        symbols = [s.strip() for s in settings.trading_symbols.split(",") if s.strip()]
        self.assertEqual(len(symbols), 8)
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("LINKUSDT", symbols)

    def test_email_settings_defaults(self) -> None:
        """Spec 002 RF-7: defaults de Gmail y fail-closed por defecto (RF-4)."""
        settings = _settings_without_env()
        self.assertEqual(settings.smtp_host, "smtp.gmail.com")
        self.assertEqual(settings.smtp_port, 587)
        self.assertEqual(settings.smtp_user, "")
        self.assertEqual(settings.smtp_pass, "")
        self.assertEqual(settings.report_to, "")

    def test_email_settings_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_PORT": "2525",
                "SMTP_USER": "bot@example.com",
                "SMTP_PASS": "app-password",
                "REPORT_TO": "owner@example.com",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.smtp_host, "smtp.example.com")
        self.assertEqual(settings.smtp_port, 2525)
        self.assertEqual(settings.smtp_user, "bot@example.com")
        self.assertEqual(settings.smtp_pass, "app-password")
        self.assertEqual(settings.report_to, "owner@example.com")

    def test_keepalive_settings(self) -> None:
        """Spec 002 RF-1: sin KEEPALIVE_URL el servicio no se vigila."""
        settings = _settings_without_env()
        self.assertEqual(settings.keepalive_url, "")
        with patch.dict(
            os.environ,
            {"KEEPALIVE_URL": "https://crypto-bot.onrender.com"},
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(
            settings.keepalive_url,
            "https://crypto-bot.onrender.com",
        )


class ForeignKeyTests(unittest.TestCase):
    def test_foreign_keys_on(self) -> None:
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        with engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)

    def test_foreign_keys_enforced(self) -> None:
        engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql(
                "CREATE TABLE child ("
                "id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id))"
            )
        with self.assertRaises(IntegrityError), engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO child (id, parent_id) VALUES (1, 999)")

    def test_app_engine_has_foreign_keys(self) -> None:
        with app_engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)


if __name__ == "__main__":
    unittest.main()

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
        # D-11: RR 1:1 — take-profit igual al stop-loss.
        self.assertEqual(settings.take_profit_pct, Decimal("2.0"))
        self.assertEqual(settings.max_signal_price_distance_pct, Decimal("1.0"))
        self.assertEqual(settings.signal_ttl_seconds, 300)
        self.assertEqual(settings.trading_interval_seconds, 60)
        symbols = [s.strip() for s in settings.trading_symbols.split(",") if s.strip()]
        self.assertEqual(len(symbols), 8)
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("LINKUSDT", symbols)

    def test_orb_symbols_default(self) -> None:
        """D-12: los 4 pares ORB; el resto solo opera con señales externas."""
        settings = _settings_without_env()
        symbols = [
            s.strip() for s in settings.orb_symbols.split(",") if s.strip()
        ]
        self.assertEqual(
            symbols, ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        )
        trading = {
            s.strip()
            for s in settings.trading_symbols.split(",")
            if s.strip()
        }
        self.assertTrue(set(symbols) <= trading)

    def test_observability_settings_defaults(self) -> None:
        """Spec 005 RF-1/RF-8: retencion, nivel de log y version."""
        settings = _settings_without_env()
        self.assertEqual(settings.event_retention_days, 30)
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.strategy_version, "orb-001-v3")

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

    def test_context_settings_defaults(self) -> None:
        """Spec 006 D-2/RF-3/RF-4/RF-6: fuentes declaradas, TTLs y pesos."""
        settings = _settings_without_env()
        self.assertEqual(
            settings.fear_greed_url, "https://api.alternative.me/fng/"
        )
        # Vacío = fuente DISABLED por defecto (D-2: sin humo).
        self.assertEqual(settings.news_rss_feeds, "")
        self.assertEqual(settings.depth_cache_seconds, 30)
        self.assertEqual(settings.fear_greed_cache_seconds, 21600)
        self.assertEqual(settings.news_cache_seconds, 900)
        self.assertEqual(
            settings.candidate_weights,
            "momentum:0.30,volume:0.25,trend:0.25,range:0.20",
        )

    def test_context_settings_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FEAR_GREED_URL": "",
                "NEWS_RSS_FEEDS": "https://feed.example/rss",
                "DEPTH_CACHE_SECONDS": "10",
                "FEAR_GREED_CACHE_SECONDS": "600",
                "NEWS_CACHE_SECONDS": "60",
                "CANDIDATE_WEIGHTS": "momentum:0.5,volume:0.5",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.fear_greed_url, "")
        self.assertEqual(settings.news_rss_feeds, "https://feed.example/rss")
        self.assertEqual(settings.depth_cache_seconds, 10)
        self.assertEqual(settings.fear_greed_cache_seconds, 600)
        self.assertEqual(settings.news_cache_seconds, 60)
        self.assertEqual(settings.candidate_weights, "momentum:0.5,volume:0.5")


    def test_gemini_settings_defaults(self) -> None:
        """Spec 007 RF-3/RF-4/D-2: sin clave (DISABLED), solo free tier 0 USD."""
        settings = _settings_without_env()
        self.assertEqual(settings.gemini_api_key, "")
        self.assertEqual(settings.gemini_model, "gemini-2.5-flash")
        self.assertEqual(
            settings.gemini_base_url,
            "https://generativelanguage.googleapis.com/v1beta",
        )
        self.assertEqual(settings.gemini_timeout_seconds, 10)
        self.assertEqual(settings.gemini_max_retries, 2)
        self.assertEqual(settings.gemini_daily_query_limit, 4)
        self.assertEqual(settings.gemini_cache_seconds, 3600)
        self.assertEqual(settings.gemini_breaker_failures, 3)
        self.assertEqual(settings.gemini_breaker_seconds, 900)
        self.assertIs(settings.gemini_auto_analysis, False)
        self.assertEqual(settings.gemini_auto_analysis_limit, 3)
        self.assertEqual(settings.gemini_daily_budget_usd, Decimal("0"))
        self.assertEqual(settings.gemini_price_mtok_input, Decimal("0"))
        self.assertEqual(settings.gemini_price_mtok_output, Decimal("0"))

    def test_gemini_settings_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GEMINI_API_KEY": "env-key",
                "GEMINI_MODEL": "gemini-2.5-pro",
                "GEMINI_DAILY_QUERY_LIMIT": "10",
                "GEMINI_AUTO_ANALYSIS": "true",
                "GEMINI_AUTO_ANALYSIS_LIMIT": "2",
                "GEMINI_DAILY_BUDGET_USD": "1.5",
                "GEMINI_PRICE_MTOK_INPUT": "0.5",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.gemini_api_key, "env-key")
        self.assertEqual(settings.gemini_model, "gemini-2.5-pro")
        self.assertEqual(settings.gemini_daily_query_limit, 10)
        self.assertIs(settings.gemini_auto_analysis, True)
        self.assertEqual(settings.gemini_auto_analysis_limit, 2)
        self.assertEqual(settings.gemini_daily_budget_usd, Decimal("1.5"))
        self.assertEqual(settings.gemini_price_mtok_input, Decimal("0.5"))


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

    def test_app_engine_dialect_and_foreign_keys(self) -> None:
        """RF-2: el engine sigue a DATABASE_URL; FK=PRAGMA solo en SQLite."""
        if app_engine.dialect.name == "sqlite":
            with app_engine.connect() as conn:
                self.assertEqual(
                    conn.exec_driver_sql("PRAGMA foreign_keys").scalar(),
                    1,
                )
        else:
            self.assertEqual(app_engine.dialect.name, "postgresql")


if __name__ == "__main__":
    unittest.main()

"""Compatibilidad Postgres sin servidor ni red (spec 002, RF-2).

Verifica que (a) todo el esquema compila con el dialecto `postgresql`,
(b) los guards de SQLite (PRAGMA/`check_same_thread`) no se aplican a
Postgres y (c) `DATABASE_URL` se lee del entorno (secretos de Render y
GitHub Actions).
"""

import os
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

import app.database as database
import app.models  # noqa: F401  # registra las tablas en Base.metadata
from app.config import Settings

POSTGRES_URL = "postgresql+psycopg://bot:secret@db.example.com:5432/crypto"


class SchemaPortabilityTests(unittest.TestCase):
    def test_all_tables_create_on_postgresql(self) -> None:
        dialect = postgresql.dialect()
        tables = database.Base.metadata.sorted_tables
        self.assertGreater(len(tables), 0)
        for table in tables:
            statement = str(CreateTable(table).compile(dialect=dialect))
            self.assertIn("CREATE TABLE", statement)
            self.assertIn(table.name, statement)


class EngineOptionsTests(unittest.TestCase):
    def test_sqlite_options(self) -> None:
        options = database._engine_options("sqlite:///./crypto_bot.db")
        self.assertEqual(
            options["connect_args"],
            {"check_same_thread": False},
        )
        self.assertIs(options["pool_pre_ping"], False)

    def test_postgresql_options_enable_pre_ping(self) -> None:
        options = database._engine_options(POSTGRES_URL)
        self.assertEqual(options["connect_args"], {})
        self.assertIs(options["pool_pre_ping"], True)


class DialectGuardTests(unittest.TestCase):
    def test_sqlite_engine_registers_pragma_listener(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with patch("app.database.event.listens_for") as listens:
            database._enable_sqlite_foreign_keys(engine)
        listens.assert_called_once()

    def test_postgresql_engine_skips_pragma_listener(self) -> None:
        engine = create_engine(POSTGRES_URL)
        self.addCleanup(engine.dispose)
        self.assertEqual(engine.dialect.name, "postgresql")
        with patch("app.database.event.listens_for") as listens:
            database._enable_sqlite_foreign_keys(engine)
        listens.assert_not_called()


class DatabaseUrlEnvTests(unittest.TestCase):
    def test_database_url_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": POSTGRES_URL},
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.database_url, POSTGRES_URL)


if __name__ == "__main__":
    unittest.main()

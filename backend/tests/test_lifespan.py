"""Auto-arranque del bot en el lifespan (spec 002, RF-1)."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.main import add_missing_columns, app


class LifespanBotStartTests(unittest.TestCase):
    def test_bot_task_started_when_enabled(self) -> None:
        started: list[object] = []

        async def fake_run(*, stop_event):
            started.append(stop_event)
            await stop_event.wait()

        with (
            patch.object(settings, "simulation_bot_enabled", True),
            patch("app.main.bot_loop.run", fake_run),
        ):
            with TestClient(app):
                pass

        self.assertEqual(len(started), 1)

    def test_bot_task_not_started_when_disabled(self) -> None:
        started: list[object] = []

        async def fake_run(*, stop_event):
            started.append(stop_event)
            await stop_event.wait()

        with (
            patch.object(settings, "simulation_bot_enabled", False),
            patch("app.main.bot_loop.run", fake_run),
        ):
            with TestClient(app):
                pass

        self.assertEqual(started, [])


class AddMissingColumnsTests(unittest.TestCase):
    """`create_all` no añade columnas: el drift rompía los fills (10/10)."""

    def test_adds_missing_columns_and_is_idempotent(self) -> None:
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE simulation_trades"
                    " (id INTEGER PRIMARY KEY)"
                )
            )

        add_missing_columns(engine)
        add_missing_columns(engine)

        columns = {
            column["name"]
            for column in inspect(engine).get_columns("simulation_trades")
        }
        self.assertIn("decision_id", columns)
        self.assertIn("symbol", columns)

    def test_missing_tables_are_left_to_create_all(self) -> None:
        engine = create_engine("sqlite://")

        add_missing_columns(engine)


if __name__ == "__main__":
    unittest.main()

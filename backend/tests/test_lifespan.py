"""Auto-arranque del bot en el lifespan (spec 002, RF-1)."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


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


if __name__ == "__main__":
    unittest.main()

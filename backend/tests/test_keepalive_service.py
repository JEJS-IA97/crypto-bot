"""Tests del keepalive antispin-down (spec 002, RF-1)."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.keepalive_service import (
    keepalive_loop,
    run_ping,
    should_keepalive,
)


class _FakeClient:
    """Cliente async mínimo para inyectar en `keepalive_loop`."""

    def __init__(self, get):
        self._get = get

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, *, timeout=None):
        return await self._get(url, timeout=timeout)


class ShouldKeepaliveTests(unittest.TestCase):
    def test_empty_and_non_http_urls_are_disabled(self) -> None:
        self.assertFalse(should_keepalive(""))
        self.assertFalse(should_keepalive("ftp://example.com"))

    def test_http_urls_are_enabled(self) -> None:
        self.assertTrue(
            should_keepalive("https://crypto-bot.onrender.com")
        )
        self.assertTrue(should_keepalive("http://localhost:8000"))


class RunPingTests(unittest.TestCase):
    def test_response_received_returns_true(self) -> None:
        client = AsyncMock()
        client.get.return_value = httpx.Response(200)
        ok = asyncio.run(run_ping("https://crypto-bot.onrender.com", client=client))
        self.assertTrue(ok)
        client.get.assert_awaited_once_with(
            "https://crypto-bot.onrender.com",
            timeout=10,
        )

    def test_network_error_returns_false_without_raising(self) -> None:
        client = AsyncMock()
        client.get.side_effect = httpx.ConnectError("red caída")
        ok = asyncio.run(run_ping("https://crypto-bot.onrender.com", client=client))
        self.assertFalse(ok)


class KeepaliveLoopTests(unittest.TestCase):
    def test_pings_immediately_and_exits_with_stop_event(self) -> None:
        stop = asyncio.Event()
        calls: list[str] = []

        async def fake_get(url, *, timeout=None):
            calls.append(url)
            stop.set()
            return httpx.Response(200)

        asyncio.run(
            keepalive_loop(
                stop,
                url="https://crypto-bot.onrender.com",
                interval_seconds=540,
                client_factory=lambda: _FakeClient(fake_get),
            )
        )
        self.assertEqual(calls, ["https://crypto-bot.onrender.com"])

    def test_repeats_until_stop_event(self) -> None:
        stop = asyncio.Event()
        count = 0

        async def fake_get(url, *, timeout=None):
            nonlocal count
            count += 1
            if count >= 3:
                stop.set()
            return httpx.Response(200)

        asyncio.run(
            keepalive_loop(
                stop,
                url="https://crypto-bot.onrender.com",
                interval_seconds=0,
                client_factory=lambda: _FakeClient(fake_get),
            )
        )
        self.assertEqual(count, 3)


class LifespanTests(unittest.TestCase):
    def test_keepalive_task_started_when_url_configured(self) -> None:
        started: list[str] = []

        async def fake_loop(stop_event, *, url):
            started.append(url)
            await stop_event.wait()

        with (
            patch.object(
                settings,
                "keepalive_url",
                "https://crypto-bot.onrender.com",
            ),
            patch("app.main.keepalive_loop", fake_loop),
        ):
            with TestClient(app):
                pass

        self.assertEqual(started, ["https://crypto-bot.onrender.com"])

    def test_no_keepalive_task_when_url_is_empty(self) -> None:
        started: list[str] = []

        async def fake_loop(stop_event, *, url):
            started.append(url)
            await stop_event.wait()

        with (
            patch.object(settings, "keepalive_url", ""),
            patch("app.main.keepalive_loop", fake_loop),
        ):
            with TestClient(app):
                pass

        self.assertEqual(started, [])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from app.signals import discord_watch as dw


class Resp:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class Client:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        if url.endswith("/users/@me/guilds"):
            return Resp([{"id": "1", "name": "José"}])
        if url.endswith("/guilds/1/channels"):
            return Resp([{"id": "10", "name": "senales", "type": 5}, {"id": "11", "name": "voz", "type": 2}])
        if params and "after" in params:
            return Resp([{"id": "102", "content": "b"}, {"id": "101", "content": "a"}])
        return Resp([{"id": "100", "content": "x"}])


class DiscordWatchTests(unittest.TestCase):
    def test_lists_text_channels_and_reads_only_new(self):
        client = Client()
        with patch.object(dw.settings, "discord_bot_token", "t"):
            dw._last.clear()
            self.assertEqual([c["id"] for c in dw.text_channels(client)], ["10"])
            self.assertEqual(dw.new_messages(client, "10"), [])  # primera lectura: solo marca
            self.assertEqual([m["id"] for m in dw.new_messages(client, "10")], ["101", "102"])
            self.assertEqual(dw._last["10"], "102")
        self.assertTrue(all(h == {"Authorization": "Bot t"} for _, _, h in client.calls))

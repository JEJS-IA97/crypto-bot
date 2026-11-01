import unittest
from unittest.mock import patch

from app.lab import bingx_feed as bf

H = 3_600_000


class Resp:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class Client:
    def get(self, url, params=None, timeout=None):
        if url.endswith("/price"):
            return Resp({"code": 0, "data": {"price": "88.5"}})
        # más nueva primero e incluye la vela abierta (como BingX)
        return Resp({"code": 0, "data": [{"time": t * H, "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "9"}
                                          for t in (10, 9, 8)]})


class Runner:
    timeframes = ["1h"]

    def __init__(self):
        self.bars, self.prices, self.closed = {}, {}, []

    def on_price(self, name, price):
        self.prices[name] = price

    def on_bar_closed(self, name, tf, bar):
        self.closed.append((name, tf, bar.ts))


class BingxFeedTests(unittest.TestCase):
    def test_klines_closed_and_oldest_first(self):
        bars = bf.klines(Client(), "HYPE-USDT", "1h", 3, now_ms=10 * H + 1)
        self.assertEqual([b.ts for b in bars], [8 * H, 9 * H])

    def test_poll_feeds_prices_and_new_closed_bars(self):
        runner = Runner()
        with patch.object(bf.settings, "lab_bingx_symbols", "HYPE-USDT:HYPEUSDT"):
            bf.poll_once(runner, Client(), now_ms=10 * H + 1)
        self.assertEqual(str(runner.prices["HYPEUSDT"]), "88.5")
        self.assertEqual(runner.closed, [("HYPEUSDT", "1h", 8 * H), ("HYPEUSDT", "1h", 9 * H)])

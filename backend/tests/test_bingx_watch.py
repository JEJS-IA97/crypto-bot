import unittest
from unittest.mock import patch

from app.signals import bingx_watch as bw


class Resp:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class Client:
    def __init__(self):
        self.urls = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append((url, headers))
        if "/contract/v1/allOrders" in url:
            return Resp({"code": 0, "data": [{"symbol": "ZEC-USDT", "side": "BUY", "time": 0, "profit": "0"}]})
        if "/user/income" in url:
            return Resp({"code": 0, "data": [{"symbol": "ZEC-USDT"}, {"symbol": "ZEC-USDT"}]})
        return Resp({"code": 0, "data": {"positionHistory": [
            {"symbol": "ZEC-USDT", "positionSide": "LONG", "openTime": 0, "updateTime": 1_800_000, "avgPrice": "10",
             "avgClosePrice": "11", "netProfit": "0.5", "leverage": 15},
            {"symbol": "ZEC-USDT", "positionSide": "SHORT", "openTime": 3_600_000, "updateTime": 7_200_000, "avgPrice": "11",
             "avgClosePrice": "11.2", "netProfit": "-0.25", "leverage": 15}]}})


class BingxWatchTests(unittest.TestCase):
    def test_reads_only_with_signed_gets_and_builds_style(self):
        client = Client()
        with patch.object(bw.settings, "bingx_api_key", "k"), patch.object(bw.settings, "bingx_api_secret", "s"), \
                patch.object(bw, "OUT", bw.Path(self._testMethodName + ".json")), patch("app.brain.evolve.remember"):
            report = bw.run_once(client)
        bw.Path(self._testMethodName + ".json").unlink()
        self.assertEqual(len(client.urls), 3)  # income + 1 par (sin duplicados) + futuros estándar
        self.assertTrue(all("signature=" in u and h == {"X-BX-APIKEY": "k"} for u, h in client.urls))
        st = report["resumen"]
        self.assertEqual((st["posiciones"], st["acierto"], st["payoff"], st["largos_pct"]), (2, 50.0, 2.0, 50))
        self.assertIn("ZEC-USDT", bw.lessons(st)[0])

    def test_api_error_raises(self):
        class Bad:
            def get(self, *a, **k):
                return Resp({"code": 100001, "msg": "signature error"})

        with self.assertRaises(RuntimeError):
            bw._get(Bad(), "/x")

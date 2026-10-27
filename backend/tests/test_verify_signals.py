"""Verificación de señales binarias de divisas contra velas reales (Yahoo simulado)."""

import unittest
from datetime import datetime, timezone

from app.signals import verify

SENT = datetime(2026, 10, 20, 13, 28, tzinfo=timezone.utc)  # 10:28 en UTC-3
SIGNAL = {"kind": "binaria", "asset": "AUD/CAD", "otc": False, "direction": "UP", "time": "10:30",
          "utc_offset": -3, "expiry_min": 1, "gales": 0}


class FakeYahoo:
    def __init__(self, opens_closes):
        self.data = opens_closes

    def get(self, url, params, headers, timeout):
        self.url = url
        ts = sorted(self.data)
        payload = {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [
            {"open": [self.data[t][0] for t in ts], "close": [self.data[t][1] for t in ts]}]}}]}}
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: payload})()


class VerifyTests(unittest.TestCase):
    def test_entry_time_uses_signal_timezone(self):
        self.assertEqual(verify.entry_utc(SIGNAL, SENT), datetime(2026, 10, 20, 13, 30, tzinfo=timezone.utc))

    def test_call_wins_when_price_rises_over_expiry(self):
        t = int(datetime(2026, 10, 20, 13, 30, tzinfo=timezone.utc).timestamp())
        yahoo = FakeYahoo({t: (0.9100, 0.9104)})
        out = verify.verify(SIGNAL, SENT, datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc), yahoo)
        self.assertEqual(out["result"], "gana")
        self.assertIn("AUDCAD=X", yahoo.url)
        put = verify.verify({**SIGNAL, "direction": "DOWN"}, SENT, datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc), yahoo)
        self.assertEqual(put["result"], "pierde")

    def test_waits_until_expiry_and_scores_channel(self):
        self.assertIsNone(verify.verify(SIGNAL, SENT, datetime(2026, 10, 20, 13, 31, tzinfo=timezone.utc), FakeYahoo({})))
        score = verify.channel_score([{"result": "gana"}] * 6 + [{"result": "pierde"}] * 4)
        self.assertEqual(score["acierto_real"], 60.0)
        self.assertEqual(score["resultado_1usd"], 1.1)


class BinanceMapTests(unittest.TestCase):
    def test_maps_signal_currencies_to_binance_pairs(self):
        symbols = {"EURUSDT", "USDTTRY", "USDTBRL", "BTCUSDT"}
        self.assertEqual(verify.binance_pair("EUR/USD", symbols), "EURUSDT")
        self.assertEqual(verify.binance_pair("USD/TRY", symbols), "USDTTRY")
        self.assertIsNone(verify.binance_pair("AUD/CAD", symbols))


class AlertTests(unittest.TestCase):
    def test_only_approved_strategies_alert(self):
        from decimal import Decimal

        from app.signals import alerts

        alerts.outbox.clear()
        pos = type("P", (), {"side": "LONG", "entry": Decimal("82000"), "stop": None, "take_profit": None, "regime": "ema_rsi_4h"})()
        alerts.on_open(type("S", (), {"name": "orb_ny", "label": "ORB"})(), "BTCUSDT", pos)
        alerts.on_open(type("S", (), {"name": "principal", "label": "Cuenta principal"})(), "BTCUSDT", pos)
        self.assertEqual(len(alerts.outbox), 1)
        self.assertIn("COMPRA BTC", alerts.outbox[0])


if __name__ == "__main__":
    unittest.main()

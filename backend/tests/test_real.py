import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path
from unittest import mock

from app.lab import real


class FakeClient:
    def __init__(self):
        self.orders = []

    def get_account(self):
        return {"balances": [{"asset": "USDT", "free": "17.88"}]}

    def get_symbol_info(self, symbol):
        return {"filters": [{"filterType": "LOT_SIZE", "stepSize": "0.01000000"}]}

    def create_order(self, symbol, side, order_type, quantity=None, quote_order_qty=None):
        self.orders.append((symbol, side, quantity, quote_order_qty))
        if side == "BUY":
            return {"orderId": 1, "executedQty": "1.000", "cummulativeQuoteQty": "6.00",
                    "fills": [{"commission": "0.001", "commissionAsset": "SOL"}]}
        return {"orderId": 2, "executedQty": quantity, "cummulativeQuoteQty": "6.30",
                "fills": [{"commission": "0.0063", "commissionAsset": "USDT"}]}


class RealTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = mock.patch.object(real, "STATE", Path(self.tmp.name) / "r.json")
        self.p.start()
        self.e = mock.patch.object(real, "enabled", return_value=True)
        self.e.start()

    def tearDown(self):
        self.p.stop()
        self.e.stop()
        self.tmp.cleanup()

    def test_buy_then_sell_received_qty_floored(self):
        c = FakeClient()
        pos = real.open_long("SOLUSDT", note=lambda *a: None, client=c)
        self.assertEqual(D(pos["qty"]), D("0.999"))
        closed = real.close_long("SOLUSDT", "4h", note=lambda *a: None, client=c)
        self.assertEqual(c.orders[1], ("SOLUSDT", "SELL", "0.99", None))
        self.assertEqual(D(closed["pnl"]), D("0.2937"))
        self.assertEqual(real.load()["abiertas"], {})

    def test_limits_max_open_and_daily_loss(self):
        c = FakeClient()
        for s in ("AUSDT", "BUSDT", "CUSDT", "DUSDT"):
            real.open_long(s, note=lambda *a: None, client=c)
        self.assertEqual(len(real.load()["abiertas"]), real.REAL_MAX_OPEN)
        state = {"abiertas": {}, "cerradas": [{"pnl": "-3.1", "dia": __import__("time").strftime("%Y-%m-%d", __import__("time").gmtime())}]}
        real._save(state)
        self.assertIsNone(real.open_long("EUSDT", note=lambda *a: None, client=c))

    def test_disabled_does_nothing(self):
        self.e.stop()
        with mock.patch.object(real.settings, "allow_live_trading", False):
            self.assertIsNone(real.open_long("SOLUSDT", client=FakeClient()))
        self.e.start()


if __name__ == "__main__":
    unittest.main()

import unittest

from app.signals import okx_watch


class FakeClient:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, params=None, timeout=None):
        body = self.pages[url.rsplit("/", 1)[1] + ":" + params.get("instType", "")]
        return type("R", (), {"json": lambda self: {"code": "0", "data": body}})()


HIST = [
    {"pnl": "30", "posSide": "long", "openTime": "0", "closeTime": "7200000", "lever": "10", "instId": "BTC-USDT-SWAP"},
    {"pnl": "-10", "posSide": "short", "openTime": "0", "closeTime": "3600000", "lever": "10", "instId": "PEPE-USDT-SWAP"},
]


class OkxWatchTests(unittest.TestCase):
    def test_style_from_closed_positions(self):
        s = okx_watch.style(HIST)
        self.assertEqual((s["acierto"], s["payoff"], s["largos_pct"], s["horas_mediana"]), (50.0, 3.0, 50, 1.5))
        self.assertEqual(s["en_nuestros_pares_pct"], 50)

    def test_profiles_skip_short_histories_and_build_lessons(self):
        rank = {"nickName": "A", "uniqueCode": "X", "leadDays": "400", "pnl": "1000", "pnlRatio": "0.25", "copyTraderNum": "3"}
        young = {**rank, "nickName": "B", "leadDays": "30"}
        pages = {
            "public-lead-traders:SPOT": [{"ranks": []}],
            "public-lead-traders:SWAP": [{"ranks": [rank, young]}],
            "public-stats:SWAP": [{"curCopyTraderPnl": "500", "profitDays": "200", "lossDays": "150"}],
            "public-subpositions-history:SWAP": HIST,
        }
        rows = okx_watch.profiles(FakeClient(pages))
        self.assertEqual([r["nombre"] for r in rows], ["A"])
        self.assertEqual(rows[0]["pnl_copiadores_usd"], 500)
        self.assertTrue(any("copiadores +500" in line for line in okx_watch.lessons(rows)))


if __name__ == "__main__":
    unittest.main()

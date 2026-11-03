import unittest

from app.signals import pick_vision as pv

ROWS = [
    {"Date": "31/10/2026", "HomeTeam": "Man United", "AwayTeam": "Chelsea", "FTHG": "2", "FTAG": "1", "FTR": "H",
     "HC": "6", "AC": "3", "HY": "2", "AY": "3", "HR": "0", "AR": "0"},
    {"Date": "31/10/2026", "HomeTeam": "Real Madrid", "AwayTeam": "Barcelona", "FTHG": "0", "FTAG": "0", "FTR": "D"},
]


class PickVisionTests(unittest.TestCase):
    def test_match_by_similar_names_and_date(self):
        pick = {"local": "Manchester United", "visitante": "Chelsea FC", "fecha": "2026-11-01"}
        self.assertEqual(pv.match_row(pick, ROWS)["AwayTeam"], "Chelsea")
        self.assertIsNone(pv.match_row({"local": "Boca", "visitante": "River", "fecha": None}, ROWS))

    def test_settle_markets(self):
        mu, rm = ROWS
        self.assertTrue(pv.settle_pick({"mercado": "1x2", "lado": "1"}, mu))
        self.assertTrue(pv.settle_pick({"mercado": "goles", "lado": "mas", "linea": 2.5}, mu))
        self.assertTrue(pv.settle_pick({"mercado": "ambos_marcan", "lado": "si"}, mu))
        self.assertFalse(pv.settle_pick({"mercado": "doble_oportunidad", "lado": "12"}, rm))
        self.assertTrue(pv.settle_pick({"mercado": "tarjetas", "lado": "mas", "linea": 3.5}, mu))
        self.assertIsNone(pv.settle_pick({"mercado": "corners", "lado": "mas", "linea": 8.5}, rm))  # sin datos
        self.assertIsNone(pv.settle_pick({"mercado": "otro"}, mu))

import unittest

from app.signals import bet_tips


class BetTipsTests(unittest.TestCase):
    def test_parse_tip_spanish(self):
        tip = bet_tips.parse_tip("⚽ Atlético Mineiro vs Cruzeiro\nPronóstico: gana Mineiro\nCuota: 1.64 (Betano)")
        self.assertEqual((tip["partido"], tip["cuota"]), ("Atlético Mineiro vs Cruzeiro", 1.64))
        self.assertIn("Mineiro", tip["pick"])
        self.assertIsNone(bet_tips.parse_tip("Buenos días equipo, hoy hay picks"))

    def test_results_and_channel_summary(self):
        self.assertEqual(bet_tips.result_of("✅✅ Green"), "ganada")
        self.assertEqual(bet_tips.result_of("❌"), "perdida")
        self.assertIsNone(bet_tips.result_of("vamos!"))
        rows = [{"kind": "apuesta", "cuota": 2.0, "resultado": "ganada"},
                {"kind": "apuesta", "cuota": 1.5, "resultado": "perdida"},
                {"kind": "apuesta", "cuota": 1.8}]
        s = bet_tips.channel_bets(rows)
        self.assertEqual((s["picks"], s["con_resultado"], s["sin_reportar"], s["unidades"]), (3, 2, 1, 0.0))


if __name__ == "__main__":
    unittest.main()

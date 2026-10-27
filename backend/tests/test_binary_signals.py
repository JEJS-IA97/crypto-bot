"""Parser de canales de opciones binarias con mensajes reales."""

import unittest

from app.signals.binary import describe, parse_binary

JOSE = """🟢 SEÑAL GRATUITA 🟢
• Huso Horario: UTC-3
• USD/NGN (OTC) • ABAJO 🔴 • 09:30
• Caducidad en 5 minutos (M5)
• Hacer 2 reentradas si se pierde"""

FACUNDO = """📊 Activo: USD/COP (OTC)
🕐 Zona horaria: UTC -3
💰 Expiración: M1
⏰ Señal: 10:06 - ABAJO 🔽
1º GALE: 10:07
2º GALE: 10:08"""

ELITE = "🛰 POCKET OPTION [M1]\n💷 EURCHF\n💎 M1\n⌚️ 10:36:00\n🔼 call"

REPORT = """📊 Informe General (19/10) 📊
USD/PKR • 07:45 ✔️
USD/PKR • 09:00 ✖️
EUR/CHF • 11:25 ✔️
Marcador: ✔️ 28 x 8 ❌"""


class BinaryParserTests(unittest.TestCase):
    def test_jose_signal(self):
        p = parse_binary(JOSE)
        self.assertEqual((p["asset"], p["otc"], p["direction"], p["time"]), ("USD/NGN", True, "DOWN", "09:30"))
        self.assertEqual((p["expiry_min"], p["gales"], p["utc_offset"]), (5, 2, -3))

    def test_facundo_signal_with_gales(self):
        p = parse_binary(FACUNDO)
        self.assertEqual((p["asset"], p["direction"], p["time"], p["expiry_min"]), ("USD/COP", "DOWN", "10:06", 1))
        self.assertEqual(p["gales"], 2)

    def test_elite_real_forex_pair_is_not_otc(self):
        p = parse_binary(ELITE)
        self.assertEqual((p["asset"], p["otc"], p["direction"], p["broker"]), ("EUR/CHF", False, "UP", "Pocket Option"))

    def test_nelson_am_time(self):
        p = parse_binary("🇪🇺EUR/USD 👉ARRIBA👈 5 minutos a las 09:00am y entraré con $1,000")
        self.assertEqual((p["asset"], p["direction"], p["time"], p["expiry_min"]), ("EUR/USD", "UP", "09:00", 5))

    def test_results_and_reports(self):
        self.assertEqual(parse_binary("WIN ✅")["result"], "win")
        self.assertEqual(parse_binary("✖️ Loss")["result"], "loss")
        self.assertEqual(parse_binary("GANADA EN EL MARTINGALA 2 ✔️")["result"], "win gale 2")
        self.assertEqual(parse_binary("El Profit no llegó, el enfoque continúa")["result"], "loss")
        report = parse_binary(REPORT)
        self.assertEqual((report["kind"], report["wins"], report["losses"]), ("informe", 2, 1))

    def test_promotions_are_not_signals(self):
        for text in ("👆🏼 Escríbeme para darte acceso ahora mismo: ➡️ @JoseAlvarezTrader ✅",
                     "Solo tenemos 8 cupos, familia!", "☀️", ""):
            self.assertIsNone(parse_binary(text), text)
        self.assertEqual(describe(None), "no es señal")
        self.assertTrue(describe(parse_binary(JOSE)).endswith("OTC"))


if __name__ == "__main__":
    unittest.main()

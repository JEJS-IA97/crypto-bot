import unittest

from app.bets import safe


def game(home, away, hg, ag, corners=(5, 4), cards=(2, 1), fouls=(11, 10)):
    return {"FTR": "H" if hg > ag else "A" if ag > hg else "D", "HomeTeam": home, "AwayTeam": away,
            "FTHG": hg, "FTAG": ag, "HTHG": min(hg, 1), "HTAG": 0, "HC": corners[0], "AC": corners[1],
            "HY": cards[0], "AY": cards[1], "HR": 0, "AR": 0, "HF": fouls[0], "AF": fouls[1]}


class SafeMarketsTests(unittest.TestCase):
    def test_hit_and_missing_data(self):
        row = game("A", "B", 2, 1)
        self.assertTrue(safe.hit("goles_o1.5", row))
        self.assertFalse(safe.hit("goles_u3.5", game("A", "B", 3, 1)))
        self.assertIsNone(safe.hit("corners_o7.5", {"FTHG": 1, "FTAG": 0}))

    def test_probability_needs_games_and_shrinks_to_league(self):
        history = [game("Goleador", f"X{i}", 3, 1) for i in range(6)] + [game(f"Y{i}", "Visita", 2, 2) for i in range(6)]
        history += [game("Z", "W", 0, 0)] * 6
        stats = safe.build_stats(history)
        p = safe.probability(stats, "Goleador", "Visita", "goles_o1.5")
        self.assertTrue(12 / 18 < p < 1)  # 12/12 del equipo, encogido hacia la liga (12/18)
        self.assertIsNone(safe.probability(stats, "Goleador", "Nuevo", "goles_o1.5"))

    def test_safe_picks_top_two_and_parlay(self):
        history = [game("A", f"X{i}", 3, 1) for i in range(40)] + [game(f"Y{i}", "B", 2, 2) for i in range(40)]
        stats = safe.build_stats(history)
        picks = safe.safe_picks(stats, {"HomeTeam": "A", "AwayTeam": "B"})
        self.assertEqual(len(picks), safe.PER_MATCH)
        self.assertTrue(all(p["fair_prob"] >= safe.MIN_PROB and p["odds"] > 1 for p in picks))
        legs = [(f"m{i}", {**picks[0]}) for i in range(4)]
        parlays = safe.safe_parlays(legs)
        self.assertEqual(len(parlays), 1)
        self.assertEqual(parlays[0]["match"].count(" + "), 2)


class FiveLegTests(unittest.TestCase):
    def test_five_leg_parlay(self):
        legs = [(f"m{i}", {"strategy": "seguro", "selection": "goles_o0.5", "fair_prob": 0.9, "odds": 1.14}) for i in range(11)]
        out = safe.safe_parlays(legs, size=5)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["strategy"], "parley5_seguro")
        self.assertEqual(out[0]["match"].count(" + "), 4)
        self.assertAlmostEqual(out[0]["fair_prob"], 0.9 ** 5)

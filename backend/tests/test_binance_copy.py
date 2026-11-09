import unittest

from app.signals import binance_copy as bc


def pos(pid, opened, side="Long", cost=100.0, close=110.0, status="All Closed", lev="3"):
    return {"positionId": pid, "opened": opened, "closed": opened + 1, "side": side, "avgCost": cost,
            "avgClosePrice": close, "status": status, "leverage": lev, "symbol": "BTCUSDT"}


class CopyTests(unittest.TestCase):
    def test_only_new_closed_positions_after_start_count_once(self):
        state = {"inicio": 1000, "traders": {}}
        rows = [pos("a", 500), pos("b", 2000), pos("c", 2000, status="Partially Closed"),
                pos("d", 3000, side="Short", cost=100, close=90, lev="20")]
        added = bc.apply(state, "1", "T", rows)
        self.assertEqual([t["lado"] for t in added], ["LONG", "SHORT"])
        self.assertEqual(added[1]["x"], 5.0)  # apalancamiento con tope
        self.assertEqual(bc.apply(state, "1", "T", rows), [])
        b = bc.board(state)[0]
        self.assertEqual(b["copias"], 2)
        self.assertGreater(b["saldo"], 40)


if __name__ == "__main__":
    unittest.main()

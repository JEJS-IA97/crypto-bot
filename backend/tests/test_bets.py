import unittest
from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.bets import engine as bets
from app.database import Base

FIXTURES = (
    "Div,Date,Time,HomeTeam,AwayTeam,BFEH,BFED,BFEA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA\n"
    "E2,28/10/2026,19:45,Leicester,Wigan,1.40,5.0,9.0,1.48,5.2,9.5,1.25,4.9,8.0\n"
    "I1,28/10/2026,20:00,Inter,Lecce,1.20,7.0,15.0,1.22,7.5,17.0,1.18,7.0,14.0\n"
    "SC0,28/10/2026,20:00,Celtic,Hearts,1.25,6.0,11.0,1.27,6.5,12.0,1.22,6.0,10.5\n"
)
RESULTS = {
    "/mmz4281/2627/E2.csv": "Div,Date,Time,HomeTeam,AwayTeam,FTR,BFECH,BFECD,BFECA\nE2,28/10/2026,19:45,Leicester,Wigan,H,1.35,5.2,10\n",
    "/mmz4281/2627/I1.csv": "Div,Date,Time,HomeTeam,AwayTeam,FTR\nI1,28/10/2026,20:00,Inter,Lecce,D\n",
    "/mmz4281/2627/SC0.csv": "Div,Date,Time,HomeTeam,AwayTeam,FTR\nSC0,28/10/2026,20:00,Celtic,Hearts,H\n",
}


class Client:
    def get(self, url, timeout=None, params=None, headers=None):
        path = url.replace(bets.FD, "")
        body = FIXTURES if path == "/fixtures.csv" else RESULTS.get(path)
        return type("R", (), {"status_code": 200 if body else 404, "content": (body or "").encode()})()


class BetsTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)

    def test_fair_removes_margin(self):
        probs = bets.fair([1.9, 1.9])
        self.assertAlmostEqual(probs[0], 0.5)
        self.assertIsNone(bets.fair([1.9, 0]))

    def test_value_needs_price_above_fair(self):
        row = {"BFEH": "1.40", "BFED": "5.0", "BFEA": "9.0", "MaxH": "1.48", "MaxD": "5.2", "MaxA": "9.5"}
        self.assertEqual([p["selection"] for p in bets.value_picks(row)], ["H"])

    def test_scan_then_settle_with_controls_and_clv(self):
        now = datetime(2026, 10, 28, 8, 0)
        with self.factory() as db:
            self.assertGreater(bets.scan_europe(db, Client(), now), 0)
            self.assertEqual(bets.scan_europe(db, Client(), now), 0)  # no duplica
            strategies = {p.strategy for p in db.scalars(select(bets.BetPick))}
            self.assertEqual(strategies, {"valor", "favorito_130", "parley3_130"})
            bets.settle_europe(db, Client(), datetime(2026, 10, 30))
            picks = db.scalars(select(bets.BetPick)).all()
            parley = next(p for p in picks if p.strategy == "parley3_130")
            self.assertEqual(parley.status, "perdida")  # el Inter empató
            value = next(p for p in picks if p.strategy == "valor")
            self.assertEqual((value.status, value.pnl), ("ganada", Decimal("0.48")))
            self.assertGreater(value.clv_pct, 0)
            rows = {r["strategy"]: r for r in bets.summary(db)}
            self.assertEqual(rows["valor"]["roi"], 48.0)


if __name__ == "__main__":
    unittest.main()

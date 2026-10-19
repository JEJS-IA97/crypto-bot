"""Cerebro que aprende: examen fuera de muestra, promoción, retiro y memoria."""

import math
import random
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.brain import evolve
from app.config import settings
from app.database import Base
from app.lab import models as lab_models  # noqa: F401
from app.lab.bars import TF_MINUTES, Bar, resample
from app.lab.engine import Trade
from app.lab.regime import RegimeLookup

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def trending_history(days: int = 400, drift: float = 0.0004) -> evolve.History:
    """Serie 5m sintética con tendencia alcista y ruido (determinista)."""
    rng = random.Random(7)
    price, bars, ts = 100.0, [], 1_700_000_000_000
    for _ in range(days * 288):
        o = price
        price *= math.exp(drift / 12 + rng.gauss(0, 0.002))
        bars.append(Bar(ts, o, max(o, price) * 1.001, min(o, price) * 0.999, price, 1.0))
        ts += 300_000
    by_tf = {tf: {"BTCUSDT": bars if m == 5 else resample(bars, m)} for tf, m in TF_MINUTES.items()}
    split = int(bars[-1].ts - (bars[-1].ts - bars[0].ts) * 0.25)
    return evolve.History(by_tf, {"BTCUSDT": RegimeLookup(by_tf["1h"]["BTCUSDT"])}, split, days * 0.75, days * 0.25)


def trade(name: str, r: float, i: int) -> Trade:
    return Trade(name, Decimal("100"), "BTCUSDT", "LONG", Decimal("1"), Decimal("1"), Decimal("1"), i, i + 1,
                 Decimal(str(r)), Decimal("0.1"), Decimal(str(r)), "rango", "stop")


class EvolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = trending_history()

    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        tmp = tempfile.mkdtemp(prefix="evolve-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        patcher = patch.object(settings, "brain_dir", tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dir = Path(tmp)

    def test_clip_keeps_params_in_range_and_fast_below_slow(self):
        p = evolve.clip("tendencia", {"tf": "5m", "fast": 500, "slow": 60})
        self.assertEqual(p["tf"], "4h")
        self.assertLess(p["fast"], p["slow"])
        self.assertIsNone(evolve.clip("martingala", {}))

    def test_trend_genome_passes_exam_on_trending_market(self):
        params = {"tf": "1d", "fast": 20, "slow": 50}
        result = evolve.examine(evolve.Evolved("t", "tendencia", params), self.history)
        self.assertGreater(result["in"]["trades"] + result["out"]["trades"], 0)
        ok, why = evolve.verdict({"in": {**result["in"], "trades": 20, "profit_factor": 2},
                                  "out": {**result["out"], "trades": 8, "net_pnl": 5, "profit_factor": 1.5,
                                          "monte_carlo": {"dd_p95": 10}}})
        self.assertTrue(ok, why)

    def test_verdict_rejects_losers_and_explains_why(self):
        base = {"trades": 30, "profit_factor": 1.5, "net_pnl": 3, "max_dd_pct": 5, "monte_carlo": {"dd_p95": 10}}
        ok, why = evolve.verdict({"in": base, "out": {**base, "net_pnl": -1, "profit_factor": 0.8}})
        self.assertFalse(ok)
        self.assertIn("examen", why)

    def test_evolve_once_records_every_candidate_and_writes_memory(self):
        with self.factory() as db:
            out = evolve.evolve_once(db, self.history, ideas=[{"familia": "tendencia", "params": {"tf": "1d", "fast": 20, "slow": 50}}],
                                     now=NOW, rng=random.Random(1))
            rows = db.scalars(select(evolve.BrainGenome).where(evolve.BrainGenome.origin != "fija")).all()
        self.assertEqual(len(rows), out["tested"])
        self.assertIn("gemini", {r.origin for r in rows})
        self.assertTrue(all(r.note for r in rows))
        memory = (self.dir / "memoria.md").read_text(encoding="utf-8")
        self.assertIn("Probé", memory)

    def test_review_live_retires_losers_and_benches_static(self):
        with self.factory() as db:
            db.add(evolve.BrainGenome(name="evo_x", family="tendencia", params={"tf": "1d", "fast": 20, "slow": 50},
                                      origin="azar", status="live", metrics={}, note=""))
            db.commit()
            trades = [trade("evo_x", -0.5, i) for i in range(16)] + [trade("orb_ny", -0.5, i) for i in range(31)]
            notes = evolve.review_live(db, trades)
            status = {r.name: r.status for r in db.scalars(select(evolve.BrainGenome))}
            evolved, benched = evolve.live_strategies(db)
        self.assertEqual(status["evo_x"], "retirada")
        self.assertEqual(status["orb_ny"], "banca")
        self.assertEqual(status["trend_daily"], "live")
        self.assertIn("orb_ny", benched)
        self.assertEqual(evolved, [])
        self.assertTrue(any("Lección" in n for n in notes))

    def test_confidence_prefers_proven_winners(self):
        trades = [trade("a", 1.0, i) for i in range(30)] + [trade("b", 1.0, 0)] + [trade("c", -1, i) for i in range(30)]
        w = evolve.confidence(trades, ["a", "b", "c"])
        self.assertGreater(w["a"], w["b"])
        self.assertEqual(w["c"], 0)


if __name__ == "__main__":
    unittest.main()

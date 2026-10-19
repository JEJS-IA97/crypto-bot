"""Cerebro: conclusiones propias, Gemini (simulado) y Markdown en docs/brain."""

import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.brain import analyst
from app.config import settings
from app.database import Base
from app.lab import live, models as lab_models  # noqa: F401
from app.lab.models import LabAccountState, LabTrade

NOW = datetime(2026, 10, 16, 16, 0, tzinfo=timezone.utc)

BACKTEST = {
    "rows": [
        {"label": "A", "capital": 100, "by_regime": {"rango · vol media": {"trades": 12, "expectancy": 0.05}}},
        {"label": "B", "capital": 100, "by_regime": {"rango · vol media": {"trades": 30, "expectancy": -0.2}}},
        {"label": "C", "capital": 100, "by_regime": {"rango · vol media": {"trades": 3, "expectancy": 9.0}}},
        {"label": "A", "capital": 20, "by_regime": {"rango · vol media": {"trades": 50, "expectancy": 5.0}}},
    ]
}


class FakeRunner:
    def status(self):
        return {"regimes": {"BNBUSDT": "rango · vol media"}, "prices": {"BNBUSDT": 730.0}}


class BrainTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(bind=engine)
        with self.factory() as db:
            db.add(LabAccountState(strategy="orb_ny", capital=Decimal("20"), cash=Decimal("19")))
            for i in range(3):
                db.add(LabTrade(
                    strategy="orb_ny", capital=Decimal("20"), symbol="BNBUSDT", side="LONG",
                    qty=Decimal("0.01"), entry=Decimal("730"), notional=Decimal("7.3"),
                    entry_fee=Decimal("0.0073"), opened_ts=0, regime="rango · vol media",
                    status="CLOSED", exit_price=Decimal("728"), closed_ts=int(NOW.timestamp() * 1000) - i,
                    pnl=Decimal("-0.03"), fees=Decimal("0.0146"), r_multiple=Decimal("-1"), reason="stop",
                ))
            db.commit()
        tmp = tempfile.mkdtemp(prefix="brain-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.dir = Path(tmp) / "brain"
        self.patches = [
            patch.object(settings, "brain_dir", str(self.dir)),
            patch.object(live, "runner", FakeRunner()),
            patch.object(analyst, "_backtest", lambda: BACKTEST),
            patch.object(analyst, "refresh_data", lambda: None),
            patch.object(analyst.evolve, "load_history", lambda *a, **k: None),
            patch.object(analyst, "index_memory", lambda: False),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_index_memory_runs_graphify_with_gemini_key(self):
        self.patches[-1].stop()
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch.object(settings, "gemini_api_key", "k-test"), \
                patch.object(analyst.shutil, "which", return_value="graphify"), \
                patch.object(analyst.subprocess, "run", return_value=ok) as run:
            self.assertTrue(analyst.index_memory())
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], ["graphify", "extract", str(self.dir)])
        self.assertEqual(kwargs["env"]["GEMINI_API_KEY"], "k-test")
        with patch.object(settings, "gemini_api_key", ""):
            self.assertFalse(analyst.index_memory())
        self.patches[-1].start()

    def test_best_by_regime_needs_evidence_and_uses_100_usd_rows(self):
        self.assertEqual(analyst.best_by_regime(BACKTEST)["rango · vol media"], ("A", 0.05, 12))

    def test_findings_mention_regime_and_live_ranking(self):
        with self.factory() as db:
            ctx = analyst.gather_context(db, 4)
        notes = analyst.findings(ctx)
        self.assertTrue(any("BNBUSDT" in n and "A" in n for n in notes))
        self.assertTrue(any("3 operaciones cerradas" in n for n in notes))

    def test_parse_json_tolerates_ansi_and_prose(self):
        text = '\x1b[32mRespuesta:\x1b[0m aquí va {"resumen": "ok", "hipotesis": []} fin'
        self.assertEqual(analyst.parse_json(text)["resumen"], "ok")
        self.assertIsNone(analyst.parse_json("sin json"))

    def test_run_once_with_llm_writes_diary_and_hypotheses(self):
        answer = {"resumen": "Mercado en rango.", "alertas": ["ORB pierde"], "hipotesis": [{"titulo": "ORB solo en tendencia", "razon": "pierde en rango", "como_probar": "filtro ER>0.3"}]}
        with patch.object(analyst.evolve, "ask_ideas", return_value=([], "", answer)) as ask:
            path = analyst.run_once(self.factory, now=NOW)
            analyst.run_once(self.factory, now=NOW)  # misma hipótesis: no se duplica
        self.assertIn("ranking_vivo", ask.call_args.args[0])
        diary = path.read_text(encoding="utf-8")
        self.assertIn("Mercado en rango.", diary)
        self.assertIn("ORB pierde", diary)
        hypotheses = (self.dir / "hipotesis.md").read_text(encoding="utf-8")
        self.assertEqual(hypotheses.count("### ORB solo en tendencia"), 1)
        self.assertTrue((self.dir / "README.md").exists())
        self.assertEqual(analyst.seconds_until_due(NOW.timestamp()), 4 * 3600)

    def test_llm_down_still_writes_statistics(self):
        with patch.object(analyst.evolve, "ask_ideas", return_value=([], "Gemini no respondió (429)", None)):
            path = analyst.run_once(self.factory, now=NOW)
        diary = path.read_text(encoding="utf-8")
        self.assertIn("LLM no disponible", diary)
        self.assertIn("429", diary)
        self.assertIn("Lo que dicen los datos", diary)
        self.assertIn("no pude examinar", diary)


if __name__ == "__main__":
    unittest.main()

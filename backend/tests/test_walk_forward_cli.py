"""Corrida walk-forward end-to-end: gate, reporte y CLI (spec 011)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.services.walk_forward_service import (
    WalkForwardConfig,
    render_report,
    run_walk_forward,
)
from fixtures_klines import (
    ranging_win_day,
    sl_loss_day,
    trend_hourly_flat,
    write_klines_jsonl,
)
from run_walk_forward import main

_START = date(2026, 4, 1)


def _write_dataset(root: Path, days: int, day_factory) -> None:
    candles = []
    for offset in range(days):
        candles += day_factory(_START + timedelta(days=offset))
    write_klines_jsonl(root / "BTCUSDT.jsonl", candles)


def _write_hourly(root: Path, symbols: tuple[str, ...] = ("BTCUSDT",)) -> None:
    # Spec 012, D-8: el walk-forward exige velas 1h para el filtro.
    hourly_dir = root / "hourly"
    hourly_dir.mkdir(parents=True, exist_ok=True)
    end = datetime.combine(_START + timedelta(days=20), datetime.min.time())
    candles = trend_hourly_flat(count=24 * 20, end=end)
    for symbol in symbols:
        write_klines_jsonl(hourly_dir / f"{symbol}.jsonl", candles)


def _config(data_dir: Path, **overrides: object) -> WalkForwardConfig:
    defaults: dict[str, object] = {
        "symbols": ("BTCUSDT",),
        "train_days": 10,
        "test_days": 5,
        "step_days": 5,
        "data_dir": data_dir,
        "hourly_dir": data_dir / "hourly",
    }
    defaults.update(overrides)
    return WalkForwardConfig(**defaults)  # type: ignore[arg-type]


class RunWalkForwardTest(unittest.TestCase):
    """RF-5/RF-6: gate PASA ⇔ agregado > 0, determinismo, multi-símbolo."""

    def test_positive_dataset_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, ranging_win_day)
            _write_hourly(root)
            result = run_walk_forward(_config(root))

        self.assertEqual(result.verdict, "PASA")
        self.assertGreater(result.aggregate.net_pnl_usd, Decimal("0"))
        self.assertEqual(len(result.folds), 1)
        self.assertIn("BTCUSDT", result.buy_hold_usd)
        self.assertGreater(result.folds[0].metrics.trades, 0)
        # Selección TP=1 en días de rango (const. #9).
        self.assertEqual(
            result.folds[0].best_take_profit_pct, Decimal("1.0")
        )

    def test_negative_dataset_fails_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, sl_loss_day)
            _write_hourly(root)
            result = run_walk_forward(_config(root))

        self.assertEqual(result.verdict, "NO PASA")
        self.assertLess(result.aggregate.net_pnl_usd, Decimal("0"))

    def test_multi_symbol_pooling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for symbol in ("BTCUSDT", "ETHUSDT"):
                candles = []
                for offset in range(15):
                    candles += ranging_win_day(_START + timedelta(days=offset))
                write_klines_jsonl(root / f"{symbol}.jsonl", candles)
            _write_hourly(root, symbols=("BTCUSDT", "ETHUSDT"))
            result = run_walk_forward(
                _config(root, symbols=("BTCUSDT", "ETHUSDT"))
            )

        self.assertEqual(result.verdict, "PASA")
        self.assertEqual(set(result.buy_hold_usd), {"BTCUSDT", "ETHUSDT"})

    def test_missing_symbol_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                run_walk_forward(_config(root))  # sin ficheros

    def test_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, ranging_win_day)
            _write_hourly(root)
            first = run_walk_forward(_config(root))
            second = run_walk_forward(_config(root))
        self.assertEqual(first, second)
        self.assertEqual(render_report(first), render_report(second))


class RenderReportTest(unittest.TestCase):
    """RF-5: secciones obligatorias del Markdown en español."""

    def test_sections_and_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, ranging_win_day)
            _write_hourly(root)
            result = run_walk_forward(_config(root))
            report = render_report(result)

        self.assertIn("Walk-forward ORB", report)
        self.assertIn("Costes", report)
        self.assertIn("Fold", report)
        self.assertIn("Agregado out-of-sample", report)
        self.assertIn("Buy & hold", report)
        self.assertIn("BTCUSDT", report)
        self.assertIn("PASA", report)


class CliTest(unittest.TestCase):
    """RF-7: exit 0 completada / exit 1 error de entrada."""

    def test_success_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, ranging_win_day)
            _write_hourly(root)
            out = root / "reports"
            code = main(
                [
                    "--symbols",
                    "BTCUSDT",
                    "--train-days",
                    "10",
                    "--test-days",
                    "5",
                    "--step-days",
                    "5",
                    "--data-dir",
                    str(root),
                    "--hourly-dir",
                    str(root / "hourly"),
                    "--output-dir",
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            reports = list(out.glob("walk-forward-*.md"))
            self.assertEqual(len(reports), 1)
            content = reports[0].read_text(encoding="utf-8")
            self.assertIn("PASA", content)

    def test_missing_dataset_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--data-dir", tmp, "--symbols", "BTCUSDT"])
        self.assertEqual(code, 1)


class PersistRunTest(unittest.TestCase):
    """Spec 012, RF-4: la corrida queda persistida con veredicto y pnl."""

    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.database import Base, _enable_sqlite_foreign_keys

        self.engine = create_engine("sqlite://")
        _enable_sqlite_foreign_keys(self.engine)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_run_is_persisted_with_verdict_and_pnl(self) -> None:
        from app.models import WalkForwardRun

        from run_walk_forward import persist_run

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_dataset(root, 15, ranging_win_day)
            _write_hourly(root)
            result = run_walk_forward(_config(root))
            report = root / "report.md"
            report.write_text("x", encoding="utf-8")

            run_id = persist_run(result, self.factory, report_path=report)

        session = self.factory()
        try:
            run = session.get(WalkForwardRun, run_id)
            self.assertIsNotNone(run)
            assert run is not None
            self.assertEqual(run.verdict, result.verdict)
            self.assertEqual(
                run.net_pnl_usd, str(result.aggregate.net_pnl_usd)
            )
            self.assertEqual(run.trades, result.aggregate.trades)
            self.assertEqual(run.folds, len(result.folds))
            self.assertEqual(run.symbols_json, '["BTCUSDT"]')
            self.assertEqual(run.report_path, str(report))
            self.assertIsNotNone(run.created_at)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()

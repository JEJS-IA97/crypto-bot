"""CLI walk-forward ORB (spec 011, RF-7): corrida offline + reporte Markdown.

Uso (desde ``backend``):
    python run_walk_forward.py [--symbols BTCUSDT,...] [--train-days 180]
        [--test-days 30] [--step-days 30] [--data-dir data/klines]
        [--fee-rate 0.0010] [--slippage-pct 0.05] [--output-dir reports]

Exit 0 = corrida completada (sea PASA o NO PASA); exit 1 = error de
entrada/dataset. El veredicto queda en el reporte y en consola.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.config import Settings
from app.services.walk_forward_service import (
    WalkForwardConfig,
    render_report,
    run_walk_forward,
)


def build_parser() -> argparse.ArgumentParser:
    settings = Settings()
    defaults = tuple(
        symbol.strip()
        for symbol in settings.orb_symbols.split(",")
        if symbol.strip()
    )
    parser = argparse.ArgumentParser(
        description="Backtest walk-forward de ORB con gate PASA/NO PASA."
    )
    parser.add_argument(
        "--symbols",
        default=",".join(defaults),
        help="Símbolos separados por coma (default: orb_symbols de config).",
    )
    parser.add_argument("--train-days", type=int, default=180)
    parser.add_argument("--test-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--data-dir", type=Path, default=Path("data/klines"))
    parser.add_argument("--fee-rate", type=str, default="0.0010")
    parser.add_argument("--slippage-pct", type=str, default="0.05")
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = WalkForwardConfig(
            symbols=tuple(
                symbol.strip()
                for symbol in args.symbols.split(",")
                if symbol.strip()
            ),
            train_days=args.train_days,
            test_days=args.test_days,
            step_days=args.step_days,
            fee_rate=Decimal(args.fee_rate),
            slippage_pct=Decimal(args.slippage_pct),
            data_dir=args.data_dir,
        )
        result = run_walk_forward(config)
    except (ValueError, TypeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    report = render_report(result)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.output_dir / f"walk-forward-{stamp}.md"
    path.write_text(report, encoding="utf-8")

    print(f"Reporte: {path}")
    print(f"Veredicto: {result.verdict}")
    print(f"PnL neto agregado: {result.aggregate.net_pnl_usd} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

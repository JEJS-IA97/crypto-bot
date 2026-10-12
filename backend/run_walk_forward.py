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
    WalkForwardResult,
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
    parser.add_argument(
        "--hourly-dir",
        type=Path,
        default=Path("data/klines_1h"),
        help="Velas 1h para el filtro de tendencia (spec 012, D-8).",
    )
    parser.add_argument("--fee-rate", type=str, default="0.0010")
    parser.add_argument("--slippage-pct", type=str, default="0.05")
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser


def persist_run(
    result: WalkForwardResult,
    session_factory,
    report_path: Path | None = None,
) -> int:
    """Persiste la corrida en ``walk_forward_runs`` (spec 012, RF-4).

    Devuelve el id de la fila. El veredicto y las métricas agregadas se
    guardan como texto para no perder la precisión de los Decimals.
    """
    import json

    from app.models import WalkForwardRun, utc_now

    aggregate = result.aggregate
    run = WalkForwardRun(
        created_at=utc_now(),
        symbols_json=json.dumps(list(result.config.symbols)),
        verdict=result.verdict,
        net_pnl_usd=str(aggregate.net_pnl_usd),
        return_pct=str(aggregate.return_pct),
        max_drawdown_pct=str(aggregate.max_drawdown_pct),
        expectancy_usd=str(aggregate.expectancy_usd),
        trades=aggregate.trades,
        folds=len(result.folds),
        hold_start=(
            str(result.folds[0].test_start) if result.folds else None
        ),
        hold_end=(
            str(result.folds[-1].test_end) if result.folds else None
        ),
        report_path=str(report_path) if report_path else None,
    )
    session = session_factory()
    try:
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id
    finally:
        session.close()


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
            hourly_dir=args.hourly_dir,
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

    # Spec 012, RF-4: persiste la corrida para exigir la última al
    # cambiar de fase (D-9). Si la BD falla, el reporte ya quedó escrito.
    try:
        from app.database import SessionLocal

        run_id = persist_run(result, SessionLocal, report_path=path)
        print(f"Corrida persistida (id={run_id})")
    except Exception as exc:  # noqa: BLE001 — el reporte manda, la BD es best-effort
        print(f"Aviso: no se pudo persistir la corrida: {exc}", file=sys.stderr)

    print(f"Reporte: {path}")
    print(f"Veredicto: {result.verdict}")
    print(f"PnL neto agregado: {result.aggregate.net_pnl_usd} USD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

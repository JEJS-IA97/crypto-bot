"""Backtest del torneo sobre las velas 5m guardadas (365 días).

Uso (desde backend/):
    .venv\\Scripts\\python.exe -m app.lab.backtest
Escribe reports/lab-backtest.json (lo sirve la API) y reports/lab-backtest.md.
"""

from __future__ import annotations

import argparse
import heapq
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.lab.bars import TF_MINUTES, Bar, load_jsonl, resample
from app.lab.engine import Account, dec
from app.lab.metrics import summarize
from app.lab.regime import RegimeLookup
from app.lab.strategies import STRATEGIES, Strategy

CAPITALS = (Decimal("20"), Decimal("50"), Decimal("100"))
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
REPORT_JSON = Path("reports/lab-backtest.json")


def run_strategy(
    strategy: Strategy,
    bars_by_symbol: dict[str, list[Bar]],
    regimes: dict[str, RegimeLookup],
    capitals=CAPITALS,
) -> list[Account]:
    """Recorre todas las velas del timeframe de la estrategia en orden temporal."""
    accounts = [Account(strategy.name, c) for c in capitals]
    signals = {s: strategy.signals(b) for s, b in bars_by_symbol.items()}
    entry_index: dict[tuple[int, str], int] = {}
    last_price: dict[str, Decimal] = {}
    tf_ms = TF_MINUTES[strategy.timeframe] * 60_000
    events = heapq.merge(
        *[
            [(b.ts, s, i) for i, b in enumerate(bars)]
            for s, bars in bars_by_symbol.items()
        ]
    )
    for ts, symbol, i in events:
        bar = bars_by_symbol[symbol][i]
        close_ts = ts + tf_ms
        last_price[symbol] = dec(bar.c)
        for n, account in enumerate(accounts):
            position = account.positions.get(symbol)
            if position is not None:
                hit = position.hit(dec(bar.l), dec(bar.h))
                if hit:
                    account.close(symbol, hit[1], close_ts, hit[0])
                elif strategy.max_hold and i - entry_index[(n, symbol)] >= strategy.max_hold:
                    account.close(symbol, dec(bar.c), close_ts, "tiempo")
                elif strategy.exit_now(bars_by_symbol[symbol], i, position.side):
                    account.close(symbol, dec(bar.c), close_ts, "salida")
                continue
            signal = signals[symbol][i]
            if signal is None:
                continue
            opened = account.open(
                symbol=symbol,
                side=signal.side,
                price=dec(bar.c),
                stop=dec(signal.stop) if signal.stop is not None else None,
                take_profit=dec(signal.take_profit) if signal.take_profit is not None else None,
                ts=close_ts,
                regime=regimes[symbol].at(close_ts),
                prices=last_price,
            )
            if opened:
                entry_index[(n, symbol)] = i
    for account in accounts:  # cierra lo abierto al último precio
        for symbol in list(account.positions):
            account.close(symbol, last_price[symbol], close_ts, "fin del test")
    return accounts


def run(data_dir: Path, symbols=DEFAULT_SYMBOLS, strategies=STRATEGIES) -> dict:
    raw = {s: load_jsonl(data_dir / f"{s}.jsonl") for s in symbols}
    first = min(b[0].ts for b in raw.values())
    last = max(b[-1].ts for b in raw.values())
    days = (last - first) / 86_400_000
    regimes = {s: RegimeLookup(resample(b, 60)) for s, b in raw.items()}
    by_tf = {
        tf: {s: (b if tf == "5m" else resample(b, m)) for s, b in raw.items()}
        for tf, m in TF_MINUTES.items()
    }
    rows = []
    for strategy in strategies:
        for account in run_strategy(strategy, by_tf[strategy.timeframe], regimes):
            rows.append(
                {
                    "strategy": strategy.name,
                    "label": strategy.label,
                    "timeframe": strategy.timeframe,
                    "description": strategy.description,
                    "capital": float(account.capital),
                    "skipped_min_notional": account.skipped,
                    **summarize(account.trades, account.capital, days),
                }
            )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "from": datetime.fromtimestamp(first / 1000, timezone.utc).date().isoformat(),
        "to": datetime.fromtimestamp(last / 1000, timezone.utc).date().isoformat(),
        "days": round(days, 1),
        "symbols": list(symbols),
        "rules": "comisión 0,10 %/lado, slippage 0,05 %, riesgo 2 %/trade, sin apalancamiento, mínimo 5 USD",
        "rows": rows,
    }


def render_markdown(result: dict) -> str:
    lines = [
        f"# Torneo de estrategias — backtest {result['from']} → {result['to']}",
        "",
        f"Pares: {', '.join(result['symbols'])}. Reglas: {result['rules']}.",
        "",
        "| Estrategia | Capital | Trades | Trades/día | Acierto % | PF | Esperanza (R) | Retorno % | DD máx % | DD p95 MC % | Sharpe |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(result["rows"], key=lambda r: (-r["return_pct"], r["capital"])):
        mc = r["monte_carlo"] or {}
        lines.append(
            f"| {r['label']} | {r['capital']:.0f} | {r['trades']} | {r['trades_per_day']} "
            f"| {r['win_rate']} | {r['profit_factor']} | {r['expectancy_r']} "
            f"| {r['return_pct']} | {r['max_dd_pct']} | {mc.get('dd_p95')} | {r['sharpe']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest del torneo de estrategias")
    parser.add_argument("--data-dir", default="data/klines")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    args = parser.parse_args()
    result = run(Path(args.data_dir), tuple(args.symbols.split(",")))
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT_JSON.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")
    print(f"Reporte: {REPORT_JSON} y {REPORT_JSON.with_suffix('.md')} ({len(result['rows'])} cuentas)")


if __name__ == "__main__":
    main()

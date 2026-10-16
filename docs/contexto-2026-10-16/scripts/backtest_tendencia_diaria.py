"""Backtest de referencia de la regla de tendencia diaria (contexto 2026-10-16).

Reproduce en Python el cálculo que se hizo en el navegador con velas 1d de
Binance (2017-08 → 2026-10-15). NO es código de producción: es la "verdad de
referencia" contra la que la spec 013 debe validar su motor (±10 %).

Reglas (sin look-ahead):
- Señal al cierre del día t; la posición rige el retorno de t → t+1.
- Coste 0.15 % por cambio de posición (0.10 % comisión + 0.05 % slippage).
- Solo largos; fuera de mercado = USDT sin interés.
- Sharpe anualizado con retornos diarios × √365.

Entrada: archivos JSONL como los de collect_klines.py (campos open_time en ms y
close como string), p. ej. data/klines_1d/BTCUSDT.jsonl. Descargar con:
    python collect_klines.py --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT --interval 1d --days 3400 --data-dir data/klines_1d
(verificar que collect_klines.py acepte --interval 1d; si no, añadirlo en la spec).

Uso:
    python backtest_tendencia_diaria.py data/klines_1d/BTCUSDT.jsonl [--fast 50 --slow 200]
    python backtest_tendencia_diaria.py data/klines_1d/BTCUSDT.jsonl --sensitivity
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

COST = 0.0015


@dataclass(frozen=True)
class Result:
    cagr_pct: float
    total_pct: float
    max_dd_pct: float
    sharpe: float
    switches: int
    exposure_pct: float


def load_closes(path: Path) -> tuple[list[int], list[float]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows.sort(key=lambda r: int(r["open_time"]))
    # descarta la vela del día en curso (incompleta)
    today = datetime.now(timezone.utc).date()
    rows = [r for r in rows if datetime.fromtimestamp(int(r["open_time"]) / 1000, timezone.utc).date() < today]
    return [int(r["open_time"]) for r in rows], [float(r["close"]) for r in rows]


def sma_series(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= n:
            acc -= values[i - n]
        if i >= n - 1:
            out[i] = acc / n
    return out


def run(times: list[int], closes: list[float], signal: list[int], warmup: int, from_ms: int = 0) -> Result:
    pos, eq, peak, mdd, switches, in_mkt, n = 0, 1.0, 1.0, 0.0, 0, 0, 0
    rets: list[float] = []
    for i in range(warmup, len(closes) - 1):
        want = signal[i]
        if times[i] < from_ms:
            pos = want
            continue
        if want != pos:
            eq *= 1 - COST
            switches += 1
            pos = want
        r = closes[i + 1] / closes[i] - 1 if pos else 0.0
        eq *= 1 + r
        rets.append(math.log(1 + r))
        n += 1
        in_mkt += pos
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak)
    years = n / 365
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((x - mean) ** 2 for x in rets) / len(rets))
    return Result(
        cagr_pct=round((eq ** (1 / years) - 1) * 100, 1),
        total_pct=round((eq - 1) * 100, 0),
        max_dd_pct=round(mdd * 100, 1),
        sharpe=round(mean / sd * math.sqrt(365), 2) if sd else 0.0,
        switches=switches,
        exposure_pct=round(in_mkt / n * 100, 0),
    )


def trend_signal(closes: list[float], fast: int, slow: int) -> list[int]:
    f, s = sma_series(closes, fast), sma_series(closes, slow)
    return [1 if (f[i] is not None and s[i] is not None and c > f[i] and c > s[i]) else 0 for i, c in enumerate(closes)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--fast", type=int, default=50)
    ap.add_argument("--slow", type=int, default=200)
    ap.add_argument("--sensitivity", action="store_true")
    args = ap.parse_args()
    times, closes = load_closes(args.path)
    warm = max(200, args.slow)
    y1 = int(datetime(2025, 10, 15, tzinfo=timezone.utc).timestamp() * 1000)
    y3 = int(datetime(2023, 10, 15, tzinfo=timezone.utc).timestamp() * 1000)
    if args.sensitivity:
        for f in (20, 30, 50, 70, 100):
            for s in (100, 150, 200, 250):
                if f < s:
                    print(f"{f}/{s}", run(times, closes, trend_signal(closes, f, s), s))
        return
    bh = [1] * len(closes)
    sig = trend_signal(closes, args.fast, args.slow)
    for name, sg in (("buy&hold", bh), (f"sma{args.fast}&{args.slow}", sig)):
        print(name, "ALL", run(times, closes, sg, warm))
        print(name, "3Y ", run(times, closes, sg, warm, y3))
        print(name, "1Y ", run(times, closes, sg, warm, y1))
    i = len(closes) - 1
    f, s = sma_series(closes, args.fast)[i], sma_series(closes, args.slow)[i]
    print(f"Señal al último cierre: close={closes[i]} sma{args.fast}={f:.4f} sma{args.slow}={s:.4f} -> {'DENTRO' if sig[i] else 'USDT'}")


if __name__ == "__main__":
    main()

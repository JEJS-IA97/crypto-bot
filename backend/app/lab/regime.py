"""Régimen de mercado por hora: tendencia vs rango × volatilidad baja/media/alta.

- Tendencia/rango: eficiencia de Kaufman en 24 h (|cambio neto| / recorrido
  total). ≥ 0,30 = tendencia; menos = rango.
- Volatilidad: ATR(14)/precio comparado con sus últimos 30 días (720 h):
  tercio inferior = baja, medio = media, superior = alta.
"""

from __future__ import annotations

import bisect

from app.lab import indicators as ind
from app.lab.bars import Bar

ER_WINDOW = 24
VOL_WINDOW = 720
TREND_THRESHOLD = 0.30


def regime_series(hourly: list[Bar]) -> list[str]:
    closes = [b.c for b in hourly]
    a = ind.atr(hourly)
    vol = [a[i] / closes[i] if a[i] else None for i in range(len(hourly))]
    out = []
    for i in range(len(hourly)):
        if i < ER_WINDOW or vol[i] is None:
            out.append("sin datos")
            continue
        path = sum(abs(closes[j] - closes[j - 1]) for j in range(i - ER_WINDOW + 1, i + 1))
        er = abs(closes[i] - closes[i - ER_WINDOW]) / path if path else 0
        trend = "tendencia" if er >= TREND_THRESHOLD else "rango"
        past = sorted(v for v in vol[max(0, i - VOL_WINDOW) : i + 1] if v is not None)
        rank = bisect.bisect_left(past, vol[i]) / len(past)
        level = "vol baja" if rank < 1 / 3 else "vol media" if rank < 2 / 3 else "vol alta"
        out.append(f"{trend} · {level}")
    return out


class RegimeLookup:
    """Régimen vigente en un instante: el de la última hora CERRADA."""

    def __init__(self, hourly: list[Bar]) -> None:
        self.closes_at = [b.ts + 3_600_000 for b in hourly]
        self.labels = regime_series(hourly)

    def at(self, ts: int) -> str:
        i = bisect.bisect_right(self.closes_at, ts) - 1
        return self.labels[i] if i >= 0 else "sin datos"

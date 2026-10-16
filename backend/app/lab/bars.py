"""Velas ligeras para el laboratorio (floats para señales; el dinero va en Decimal)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

TF_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
MINUTE_MS = 60_000


@dataclass(frozen=True, slots=True)
class Bar:
    ts: int  # open time, ms UTC
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: float


def load_jsonl(path: str | Path) -> list[Bar]:
    """Velas del recolector (`collect_klines.py`), ordenadas por tiempo."""
    bars = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            bars.append(
                Bar(
                    int(row["open_time"]),
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row["volume"]),
                )
            )
    bars.sort(key=lambda b: b.ts)
    return bars


def resample(bars: list[Bar], minutes: int) -> list[Bar]:
    """Agrupa velas menores en velas de `minutes` (alineadas a UTC).

    Solo emite buckets completos: un bucket a medias (fin del dataset)
    se descarta para no usar una vela sin cerrar.
    """
    if not bars:
        return []
    size = minutes * MINUTE_MS
    step = bars[1].ts - bars[0].ts if len(bars) > 1 else size
    per_bucket = max(1, size // step)
    out: list[Bar] = []
    bucket: list[Bar] = []
    current = None
    for bar in bars:
        start = bar.ts - bar.ts % size
        if start != current:
            if bucket and len(bucket) == per_bucket:
                out.append(_merge(current, bucket))
            bucket = []
            current = start
        bucket.append(bar)
    if bucket and len(bucket) == per_bucket:
        out.append(_merge(current, bucket))
    return out


def _merge(start: int, bucket: list[Bar]) -> Bar:
    return Bar(
        start,
        bucket[0].o,
        max(b.h for b in bucket),
        min(b.l for b in bucket),
        bucket[-1].c,
        sum(b.v for b in bucket),
    )

"""Indicadores causales (cada valor i solo usa datos hasta i). None = sin datos."""

from __future__ import annotations

import math

from app.lab.bars import Bar

Series = list[float | None]


def ema(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(values[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def sma(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= n:
            acc -= values[i - n]
        if i >= n - 1:
            out[i] = acc / n
    return out


def stdev(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1 : i + 1]
        mean = sum(window) / n
        out[i] = math.sqrt(sum((x - mean) ** 2 for x in window) / n)
    return out


def rsi(closes: list[float], n: int = 14) -> Series:
    out: Series = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / n, losses / n
    out[n] = 100 - 100 / (1 + avg_g / avg_l) if avg_l else 100.0
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (n - 1) + max(d, 0)) / n
        avg_l = (avg_l * (n - 1) + max(-d, 0)) / n
        out[i] = 100 - 100 / (1 + avg_g / avg_l) if avg_l else 100.0
    return out


def atr(bars: list[Bar], n: int = 14) -> Series:
    out: Series = [None] * len(bars)
    if len(bars) <= n:
        return out
    trs = [bars[0].h - bars[0].l]
    for i in range(1, len(bars)):
        prev = bars[i - 1].c
        trs.append(max(bars[i].h - bars[i].l, abs(bars[i].h - prev), abs(bars[i].l - prev)))
    value = sum(trs[1 : n + 1]) / n
    out[n] = value
    for i in range(n + 1, len(bars)):
        value = (value * (n - 1) + trs[i]) / n
        out[i] = value
    return out


def highest_prev(values: list[float], n: int) -> Series:
    """Máximo de las `n` velas ANTERIORES a i (sin incluir i)."""
    out: Series = [None] * len(values)
    for i in range(n, len(values)):
        out[i] = max(values[i - n : i])
    return out


def lowest_prev(values: list[float], n: int) -> Series:
    out: Series = [None] * len(values)
    for i in range(n, len(values)):
        out[i] = min(values[i - n : i])
    return out


def session_vwap(bars: list[Bar]) -> Series:
    """VWAP que se reinicia cada día UTC."""
    out: Series = [None] * len(bars)
    day = None
    pv = vol = 0.0
    for i, b in enumerate(bars):
        d = b.ts // 86_400_000
        if d != day:
            day, pv, vol = d, 0.0, 0.0
        typical = (b.h + b.l + b.c) / 3
        pv += typical * b.v
        vol += b.v
        out[i] = pv / vol if vol else b.c
    return out

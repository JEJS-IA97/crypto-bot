"""Estrategias del torneo. Misma interfaz para backtest y vivo.

`signals(bars)` devuelve, para cada vela CERRADA i, una señal de entrada
(o None) calculada solo con datos hasta i. El motor entra al precio actual
justo después del cierre. Las salidas son por stop / take-profit, por
`max_hold` velas, o por `exit_now` (reglas de salida propias).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.lab import indicators as ind
from app.lab.bars import Bar

NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Signal:
    side: str  # LONG | SHORT
    stop: float | None
    take_profit: float | None


class Strategy:
    name = ""
    label = ""
    timeframe = "15m"
    warmup = 210  # velas que necesita en vivo
    max_hold: int | None = None
    description = ""

    def signals(self, bars: list[Bar]) -> list[Signal | None]:
        raise NotImplementedError

    def exit_now(self, bars: list[Bar], i: int, side: str) -> bool:
        return False


def _long(entry: float, stop: float, reward_r: float) -> Signal | None:
    risk = entry - stop
    return Signal("LONG", stop, entry + reward_r * risk) if risk > 0 else None


def _short(entry: float, stop: float, reward_r: float) -> Signal | None:
    risk = stop - entry
    return Signal("SHORT", stop, entry - reward_r * risk) if risk > 0 else None


class OrbNY(Strategy):
    """Opening Range Breakout de la apertura de Nueva York (9:30–10:00)."""

    name = "orb_ny"
    label = "ORB Nueva York 9:30–10:00"
    timeframe = "5m"
    warmup = 700
    max_hold = 72  # 6 h: se cierra antes del cierre de NY
    trend_filter = False
    description = (
        "Rango 9:30–10:00 NY; rompimiento al alza = long, a la baja = short, "
        "hasta las 12:00. Stop en la mitad del rango, objetivo 2R. 1 trade/día."
    )

    def signals(self, bars):
        out: list[Signal | None] = [None] * len(bars)
        trend = ind.ema([b.c for b in bars], 600) if self.trend_filter else None
        day = None
        hi = lo = None
        traded = False
        for i, b in enumerate(bars):
            t = datetime.fromtimestamp(b.ts / 1000, timezone.utc).astimezone(NY)
            if t.date() != day:
                day, hi, lo, traded = t.date(), None, None, False
            minutes = t.hour * 60 + t.minute
            if 570 <= minutes < 600:  # velas que abren 9:30–9:55
                hi = b.h if hi is None else max(hi, b.h)
                lo = b.l if lo is None else min(lo, b.l)
                continue
            if traded or hi is None or not 600 <= minutes < 720:
                continue
            mid = (hi + lo) / 2
            want_long = b.c > hi
            want_short = b.c < lo
            if trend is not None and trend[i] is not None:
                want_long = want_long and b.c > trend[i]
                want_short = want_short and b.c < trend[i]
            if want_long:
                out[i], traded = _long(b.c, mid, 2), True
            elif want_short:
                out[i], traded = _short(b.c, mid, 2), True
        return out


class OrbNYTrend(OrbNY):
    name = "orb_ny_trend"
    label = "ORB NY + filtro de tendencia"
    trend_filter = True
    description = OrbNY.description + " Solo a favor de la EMA ≈50 de 1h."


class ImpulsePullback(Strategy):
    """Impulso → pullback a la EMA20 → continuación (la de Alex Ruiz)."""

    name = "impulse_pullback"
    label = "Impulso-pullback-continuación"
    timeframe = "15m"
    description = (
        "Tendencia (EMA50 vs EMA200) con impulso reciente a máximos/mínimos de "
        "20 velas; entra cuando el pullback toca la EMA20 y la vela retoma la "
        "dirección. Stop en el extremo del pullback, objetivo 2R."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        e20, e50, e200 = ind.ema(c, 20), ind.ema(c, 50), ind.ema(c, 200)
        hh = ind.highest_prev([b.h for b in bars], 20)
        ll = ind.lowest_prev([b.l for b in bars], 20)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(215, len(bars)):
            b = bars[i]
            if None in (e20[i], e50[i], e200[i]):
                continue
            recent = range(i - 12, i)
            touched = any(bars[j].l <= e20[j] <= bars[j].h for j in range(i - 3, i))
            if e50[i] > e200[i] and b.c > e200[i]:
                impulse = any(hh[j] is not None and bars[j].h > hh[j] for j in recent)
                if impulse and touched and b.c > e20[i] and b.c > b.o:
                    out[i] = _long(b.c, min(x.l for x in bars[i - 5 : i + 1]), 2)
            elif e50[i] < e200[i] and b.c < e200[i]:
                impulse = any(ll[j] is not None and bars[j].l < ll[j] for j in recent)
                if impulse and touched and b.c < e20[i] and b.c < b.o:
                    out[i] = _short(b.c, max(x.h for x in bars[i - 5 : i + 1]), 2)
        return out


class EmaCross(Strategy):
    name = "ema_cross"
    label = "Cruce EMA 9/21 + EMA200"
    timeframe = "15m"
    description = "Cruce de EMA9 sobre EMA21 a favor de la EMA200. Stop 1,5 ATR, objetivo 3 ATR."

    def signals(self, bars):
        c = [b.c for b in bars]
        f, s, t, a = ind.ema(c, 9), ind.ema(c, 21), ind.ema(c, 200), ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(1, len(bars)):
            if None in (f[i - 1], s[i - 1], t[i], a[i]):
                continue
            up = f[i - 1] <= s[i - 1] and f[i] > s[i]
            down = f[i - 1] >= s[i - 1] and f[i] < s[i]
            if up and c[i] > t[i]:
                out[i] = Signal("LONG", c[i] - 1.5 * a[i], c[i] + 3 * a[i])
            elif down and c[i] < t[i]:
                out[i] = Signal("SHORT", c[i] + 1.5 * a[i], c[i] - 3 * a[i])
        return out


class RsiReversion(Strategy):
    name = "rsi_reversion"
    label = "Reversión RSI (5m)"
    timeframe = "5m"
    max_hold = 24
    description = (
        "Compra sobreventa (RSI<25) en tendencia alcista y vende sobrecompra "
        "(RSI>75) en bajista. Stop 1,5 ATR, objetivo 1,5 ATR, máx. 2 h."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        r, t, a = ind.rsi(c), ind.ema(c, 200), ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(len(bars)):
            if None in (r[i], t[i], a[i]):
                continue
            if r[i] < 25 and c[i] > t[i]:
                out[i] = Signal("LONG", c[i] - 1.5 * a[i], c[i] + 1.5 * a[i])
            elif r[i] > 75 and c[i] < t[i]:
                out[i] = Signal("SHORT", c[i] + 1.5 * a[i], c[i] - 1.5 * a[i])
        return out


class BollingerSqueeze(Strategy):
    name = "bollinger_squeeze"
    label = "Ruptura de Bollinger tras compresión"
    timeframe = "15m"
    description = (
        "Bandas de Bollinger (20, 2) estrechas (mínimo de 100 velas) y cierre "
        "fuera de la banda. Stop en la media, objetivo 2R."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        mid, sd = ind.sma(c, 20), ind.stdev(c, 20)
        width = [
            (4 * sd[i] / mid[i]) if mid[i] and sd[i] is not None else None
            for i in range(len(bars))
        ]
        out: list[Signal | None] = [None] * len(bars)
        for i in range(120, len(bars)):
            if None in (mid[i], sd[i], width[i - 1]):
                continue
            past = [w for w in width[i - 100 : i] if w is not None]
            if not past or width[i - 1] > min(past) * 1.1:
                continue
            upper, lower = mid[i] + 2 * sd[i], mid[i] - 2 * sd[i]
            if c[i] > upper:
                out[i] = _long(c[i], mid[i], 2)
            elif c[i] < lower:
                out[i] = _short(c[i], mid[i], 2)
        return out


class VwapReversion(Strategy):
    name = "vwap_reversion"
    label = "Reversión al VWAP (5m)"
    timeframe = "5m"
    max_hold = 48
    description = (
        "Precio a más de 1 % del VWAP del día con RSI extremo: apuesta a la "
        "vuelta al VWAP (objetivo). Stop 1,5 ATR, máx. 4 h."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        vw, r, a = ind.session_vwap(bars), ind.rsi(c), ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(len(bars)):
            if None in (vw[i], r[i], a[i]):
                continue
            dev = (c[i] - vw[i]) / vw[i]
            if dev < -0.01 and r[i] < 35:
                out[i] = Signal("LONG", c[i] - 1.5 * a[i], vw[i])
            elif dev > 0.01 and r[i] > 65:
                out[i] = Signal("SHORT", c[i] + 1.5 * a[i], vw[i])
        return out


class DonchianBreakout(Strategy):
    name = "donchian_breakout"
    label = "Ruptura Donchian 55 (1h)"
    timeframe = "1h"
    description = "Cierre por encima/debajo del máximo/mínimo de 55 horas. Stop 2 ATR, objetivo 4 ATR."

    def signals(self, bars):
        c, a = [b.c for b in bars], ind.atr(bars)
        hh = ind.highest_prev([b.h for b in bars], 55)
        ll = ind.lowest_prev([b.l for b in bars], 55)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(len(bars)):
            if None in (hh[i], ll[i], a[i]):
                continue
            if c[i] > hh[i]:
                out[i] = Signal("LONG", c[i] - 2 * a[i], c[i] + 4 * a[i])
            elif c[i] < ll[i]:
                out[i] = Signal("SHORT", c[i] + 2 * a[i], c[i] - 4 * a[i])
        return out


class EmaRsi4h(Strategy):
    """La del video 'Claude para trading': EMA21/89 + RSI + ATR en 4h."""

    name = "ema_rsi_4h"
    label = "EMA 21/89 + RSI (4h, video Claude)"
    timeframe = "4h"
    warmup = 120
    description = (
        "EMA21 sobre EMA89 y RSI cruzando 50 al alza = long (y al revés short). "
        "Stop 2 ATR, objetivo 4 ATR."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        f, s, r, a = ind.ema(c, 21), ind.ema(c, 89), ind.rsi(c), ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(1, len(bars)):
            if None in (f[i], s[i], r[i - 1], r[i], a[i]):
                continue
            if f[i] > s[i] and r[i - 1] <= 50 < r[i]:
                out[i] = Signal("LONG", c[i] - 2 * a[i], c[i] + 4 * a[i])
            elif f[i] < s[i] and r[i - 1] >= 50 > r[i]:
                out[i] = Signal("SHORT", c[i] + 2 * a[i], c[i] - 4 * a[i])
        return out


class TrendDaily(Strategy):
    name = "trend_daily"
    label = "Tendencia diaria SMA50 y SMA200"
    timeframe = "1d"
    description = "Comprado solo si el cierre diario está sobre SMA50 y SMA200; sale al perderlas. Sin stop fijo."

    def _inside(self, bars):
        c = [b.c for b in bars]
        f, s = ind.sma(c, 50), ind.sma(c, 200)
        return [
            f[i] is not None and s[i] is not None and c[i] > f[i] and c[i] > s[i]
            for i in range(len(bars))
        ]

    def signals(self, bars):
        inside = self._inside(bars)
        return [Signal("LONG", None, None) if x else None for x in inside]

    def exit_now(self, bars, i, side):
        return not self._inside(bars[: i + 1])[-1]


STRATEGIES: list[Strategy] = [
    OrbNY(),
    OrbNYTrend(),
    ImpulsePullback(),
    EmaCross(),
    RsiReversion(),
    BollingerSqueeze(),
    VwapReversion(),
    DonchianBreakout(),
    EmaRsi4h(),
    TrendDaily(),
]
BY_NAME = {s.name: s for s in STRATEGIES}

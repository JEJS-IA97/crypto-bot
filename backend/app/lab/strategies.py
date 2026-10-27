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
    regime_filter = False  # True: solo entra si BTC diario cierra sobre su SMA20 (lo aplica el torneo)
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


class BollingerTrend1h(Strategy):
    """Investigación 2026-10-25 (research/lab_2026_10_25.py): la única idea que no perdió ni en
    entreno (+0.2 %) ni en examen (+6.0 %, DD 11 %) en un año en que las monedas cayeron 32–74 %."""

    name = "bollinger_trend_1h"
    label = "Bollinger 2.5σ 1h + BTC sobre SMA20"
    timeframe = "1h"
    warmup = 60
    max_hold = 72
    regime_filter = True
    description = (
        "Cierre que cruza sobre la banda de Bollinger (20, 2.5σ) en 1h, solo si BTC diario está "
        "sobre su SMA20. Stop 2 ATR, objetivo 4 ATR (2R), máx. 3 días."
    )

    def signals(self, bars):
        c = [b.c for b in bars]
        mid, sd, a = ind.sma(c, 20), ind.stdev(c, 20), ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(21, len(bars)):
            if None in (mid[i], sd[i], mid[i - 1], sd[i - 1], a[i]):
                continue
            if c[i] > mid[i] + 2.5 * sd[i] and c[i - 1] <= mid[i - 1] + 2.5 * sd[i - 1]:
                out[i] = _long(c[i], c[i] - 2 * a[i], 2)
        return out


class Breakout168h1h(Strategy):
    """Video TradingLab #1 + filtro BTC (research 2026-10-25: entreno −10.6 %, examen +4.1 %). En paper para medir."""

    name = "ruptura_7d_1h"
    label = "Ruptura de 7 días 1h + BTC sobre SMA20"
    timeframe = "1h"
    warmup = 210
    max_hold = 120
    regime_filter = True
    description = "Cierre sobre la SMA200 y sobre el máximo de las 168 h previas. Stop 3 ATR, objetivo 9 ATR (3R), máx. 5 días."

    def signals(self, bars):
        c, a = [b.c for b in bars], ind.atr(bars)
        hh, sma = ind.highest_prev([b.h for b in bars], 168), ind.sma(c, 200)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(len(bars)):
            if None not in (hh[i], sma[i], a[i]) and c[i] > hh[i] and c[i] > sma[i]:
                out[i] = _long(c[i], c[i] - 3 * a[i], 3)
        return out


class Momentum48h1h(Strategy):
    """Video TradingLab #3 + filtro BTC (research: entreno +6.2 %, examen −8.8 %). En paper para medir."""

    name = "momentum_48h_1h"
    label = "Momentum 48 h > 3 % + BTC sobre SMA20"
    timeframe = "1h"
    warmup = 60
    max_hold = 120
    regime_filter = True
    description = "El retorno de 48 h cruza +3 % al alza. Stop 3 ATR, objetivo 6 ATR (2R), máx. 5 días."

    def signals(self, bars):
        c, a = [b.c for b in bars], ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(49, len(bars)):
            r, prev = c[i] / c[i - 48] - 1, c[i - 1] / c[i - 49] - 1
            if a[i] is not None and r > 0.03 >= prev:
                out[i] = _long(c[i], c[i] - 3 * a[i], 2)
        return out


class Momentum48hShort1h(Strategy):
    """Experimento de cortos (paper, Spot no permite cortos reales): caída de 48 h > 3 % con BTC
    BAJO su SMA20. Research 2026-10-27: entreno +67 % (meses de caída), examen −1.3 % (PF 0.98)."""

    name = "momentum_48h_corto"
    label = "Corto: caída 48 h > 3 % con BTC bajo SMA20 (paper)"
    timeframe = "1h"
    warmup = 60
    max_hold = 120
    regime_filter = "bear"
    description = "Vende en corto cuando el retorno de 48 h cruza −3 %. Stop 3 ATR, objetivo 6 ATR. Solo en paper."

    def signals(self, bars):
        c, a = [b.c for b in bars], ind.atr(bars)
        out: list[Signal | None] = [None] * len(bars)
        for i in range(49, len(bars)):
            r, prev = c[i] / c[i - 48] - 1, c[i - 1] / c[i - 49] - 1
            if a[i] is not None and r < -0.03 <= prev:
                out[i] = _short(c[i], c[i] + 3 * a[i], 2)
        return out


ALL_STRATEGIES: list[Strategy] = [
    BollingerTrend1h(),
    Momentum48hShort1h(),
    Breakout168h1h(),
    Momentum48h1h(),
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
# Torneo en vivo: solo las fijas que no perdieron en vivo (2026-10-24, ~240 trades).
# Las demás quedan en ALL_STRATEGIES para backtest y en el cerebro como "retirada".
STRATEGIES: list[Strategy] = [s for s in ALL_STRATEGIES if s.name in ("ema_rsi_4h", "bollinger_trend_1h", "ruptura_7d_1h", "momentum_48h_1h", "momentum_48h_corto")]
RETIRED = {
    "orb_ny": "PF 0.60 en 10 trades", "orb_ny_trend": "PF 0.95 en 12 trades, comisiones > ganancia",
    "impulse_pullback": "PF 0.60 en 11 trades", "ema_cross": "PF 0.46 en 10 trades",
    "rsi_reversion": "5m: las comisiones se comen la reversión", "bollinger_squeeze": "PF 0.21 en 9 trades",
    "vwap_reversion": "PF 0.38 en 15 trades", "donchian_breakout": "PF 0.03 en 8 trades",
    "trend_daily": "0 de 3, la cubre la familia tendencia del cerebro",
}
BY_NAME = {s.name: s for s in ALL_STRATEGIES}

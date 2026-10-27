"""Réplica del ensemble Donchian de Zarattini, Pagani & Barbon (2025) en velas diarias de Binance.

Reglas (issue #137 de DeFi-TraderStack, resumen del paper):
- 9 lookbacks: 5, 10, 20, 30, 60, 90, 150, 250, 360 días.
- Entrada de cada submodelo: cierre > máximo de cierres de la ventana previa.
- Salida: trailing stop = max(stop previo, punto medio del canal); sale si el cierre lo pierde.
- Peso por moneda = media de submodelos activos × min(1, 25 % / vol 90 d anualizada). Solo largos, sin apalancamiento.
Costes 0.15 % por unidad de cambio de peso. Compara con SMA50&SMA200 y con comprar y mantener.
Uso: python ensemble_1d.py data/klines_1d
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LOOKS = (5, 10, 20, 30, 60, 90, 150, 250, 360)
COST = 0.0015


def load(folder):
    out = {}
    for f in sorted(Path(folder).glob("*.jsonl")):
        rows = [json.loads(x) for x in f.open()]
        df = pd.DataFrame(rows)
        t = df["open_time"] if "open_time" in df else df[df.columns[0]]
        s = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(t, unit="ms", utc=True))
        out[f.stem] = s[~s.index.duplicated()].sort_index()
    return out


def ensemble_weight(c: pd.Series) -> pd.Series:
    subs = []
    for n in LOOKS:
        hi = c.rolling(n).max().shift()
        lo = c.rolling(n).min().shift()
        mid = (hi + lo) / 2
        pos, stop, w = 0, np.nan, []
        for i in range(len(c)):
            if pos == 0 and not np.isnan(hi.iloc[i]) and c.iloc[i] > hi.iloc[i]:
                pos, stop = 1, mid.iloc[i]
            elif pos == 1:
                stop = max(stop, mid.iloc[i]) if not np.isnan(mid.iloc[i]) else stop
                if c.iloc[i] < stop:
                    pos = 0
            w.append(pos)
        subs.append(pd.Series(w, index=c.index))
    signal = pd.concat(subs, axis=1).mean(axis=1)
    vol = c.pct_change().rolling(90).std() * np.sqrt(365)
    return (signal * (0.25 / vol).clip(upper=1.0)).fillna(0)


def sma_weight(c):
    return ((c > c.rolling(50).mean()) & (c > c.rolling(200).mean())).astype(float)


def stats(w: pd.Series, c: pd.Series) -> dict:
    r = c.pct_change().fillna(0)
    w = w.shift().fillna(0)  # decide al cierre, opera al día siguiente
    net = w * r - w.diff().abs().fillna(0) * COST
    eq = (1 + net).cumprod()
    years = len(eq) / 365
    dd = (1 - eq / eq.cummax()).max()
    sharpe = net.mean() / net.std() * np.sqrt(365) if net.std() else 0
    by_year = {str(y): round((1 + g).prod() * 100 - 100, 1) for y, g in net.groupby(net.index.year)}
    return {"cagr": round((eq.iloc[-1] ** (1 / years) - 1) * 100, 1), "dd": round(dd * 100, 1),
            "sharpe": round(sharpe, 2), "exposicion": round(w.mean() * 100, 0), "por_año": by_year}


def main():
    data = load(sys.argv[1])
    for sym, c in data.items():
        print(sym, str(c.index[0])[:10], "→", str(c.index[-1])[:10])
        print("  comprar y mantener", json.dumps(stats(pd.Series(1.0, index=c.index), c)))
        print("  SMA50 y SMA200    ", json.dumps(stats(sma_weight(c), c)))
        print("  ensemble Donchian ", json.dumps(stats(ensemble_weight(c), c)))
    # cartera 50/50 BTC+ETH con cada regla
    idx = data["BTCUSDT"].index.intersection(data["ETHUSDT"].index)
    for name, fn in (("SMA", sma_weight), ("ensemble", ensemble_weight)):
        r = sum(0.5 * (fn(data[s].loc[idx]).shift().fillna(0) * data[s].loc[idx].pct_change().fillna(0)
                       - fn(data[s].loc[idx]).shift().fillna(0).diff().abs().fillna(0) * COST) for s in ("BTCUSDT", "ETHUSDT"))
        eq = (1 + r).cumprod()
        print(f"cartera BTC+ETH {name}: cagr {round((eq.iloc[-1] ** (365 / len(eq)) - 1) * 100, 1)} dd {round((1 - eq / eq.cummax()).max() * 100, 1)} "
              f"sharpe {round(r.mean() / r.std() * np.sqrt(365), 2)} último año {round((eq.iloc[-1] / eq.iloc[-366] - 1) * 100, 1)}")


if __name__ == "__main__":
    main()

"""¿Qué añade el lado corto (1x, sin apalancamiento) a la tendencia diaria? + rendimiento del USDT en cash."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
COST = 0.0015
def load(folder):
    out = {}
    for f in sorted(Path(folder).glob("*.jsonl")):
        df = pd.DataFrame([json.loads(x) for x in f.open()])
        s = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["open_time"], unit="ms", utc=True))
        out[f.stem] = s[~s.index.duplicated()].sort_index()
    return out
def stats(w, c, cash_apy=0.0, funding=0.0):
    r = c.pct_change().fillna(0); w = w.shift().fillna(0)
    net = w * r - w.diff().abs().fillna(0) * COST + (1 - w.abs()) * cash_apy / 365 - (w < 0) * funding / 365
    eq = (1 + net).cumprod(); yrs = len(eq) / 365
    by = {str(y): round(((1 + g).prod() - 1) * 100) for y, g in net.groupby(net.index.year)}
    return {"cagr": round((eq.iloc[-1] ** (1 / yrs) - 1) * 100, 1), "dd": round((1 - eq / eq.cummax()).max() * 100, 1),
            "sharpe": round(net.mean() / net.std() * np.sqrt(365), 2), "por_año": by}
data = load(sys.argv[1])
for sym in ("BTCUSDT", "ETHUSDT"):
    c = data[sym]; up = (c > c.rolling(50).mean()) & (c > c.rolling(200).mean()); dn = (c < c.rolling(50).mean()) & (c < c.rolling(200).mean())
    lo = up.astype(float); ls = up.astype(float) - dn.astype(float)
    print(sym)
    print("  solo largos          ", stats(lo, c))
    print("  largos + USDT al 4%  ", stats(lo, c, 0.04))
    print("  largos y cortos 1x   ", stats(ls, c, 0.0, 0.05))
    print("  largos+cortos+USDT4% ", stats(ls, c, 0.04, 0.05))

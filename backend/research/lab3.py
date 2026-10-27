"""Experimentos 2026-10-27 sobre lo que José pasó y aún no se había probado.

1) Salida parcial del video "win rate": cobrar la mitad en +1R y mover el stop a la entrada.
2) Cortos (paper): las mismas ideas al revés cuando BTC está BAJO su SMA20 (régimen bajista).
3) Pausa tras racha: si pierde 5 de las últimas 10, no entra en 48 h.
Uso: python lab3.py data/klines   (usa el caché data/k5.pkl de lab2)
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import lab2  # noqa: E402

COST = lab2.COST


def simulate(df, entry, stop, target, max_hold, partial=False):
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    ent = entry.fillna(False).to_numpy()
    st, tg = stop.to_numpy(), target.to_numpy()
    trades, i, n = [], 0, len(df)
    while i < n - 1:
        if not ent[i]:
            i += 1
            continue
        px, s, t = o[i + 1], st[i], tg[i]
        if np.isnan(s) or s >= px:
            i += 1
            continue
        r1, half, j, out = px + (px - s), False, i + 1, None
        while j < n:
            if l[j] <= s:
                out = min(s, o[j])
                break
            if partial and not half and h[j] >= r1:
                half, s = True, px  # cobra la mitad en +1R y el resto queda a coste cero
            if h[j] >= t:
                out = max(t, o[j])
                break
            if j - i >= max_hold:
                out = c[j]
                break
            j += 1
        if out is None:
            break
        ret = (0.5 * (r1 / px - 1) + 0.5 * (out / px - 1) if half else out / px - 1) - COST
        trades.append({"t": df.index[i + 1], "x": df.index[min(j, n - 1)], "ret": ret, "risk": max((px - s if not half else px - st[i]) / px, 0.002)})
        i = j
    return trades


def pause_after_streak(trades):
    """Quita las entradas que caen en una pausa de 48 h tras perder 5 de las últimas 10."""
    out, last, pause_until = [], [], None
    for tr in sorted(trades, key=lambda x: x["t"]):
        if pause_until is not None and tr["t"] < pause_until:
            continue
        out.append(tr)
        last = (last + [tr["ret"] > 0])[-10:]
        if len(last) == 10 and last.count(False) >= 5:
            pause_until, last = tr["x"] + pd.Timedelta(hours=48), []
    return out


def invert(df):
    """Un corto sobre p ≈ un largo sobre 1/p (aprox. para movimientos pequeños)."""
    return pd.DataFrame({"open": 1 / df.open, "high": 1 / df.low, "low": 1 / df.high, "close": 1 / df.close, "vol": df.vol})


IDEAS = {
    "bollinger_1h": (lab2.s_bollinger, {"z": 2.5, "k": 2.0, "rr": 2.0, "hold": 72}),
    "ruptura_168h": (lab2.s_breakout_96h, {"look": 168, "k": 3.0, "rr": 3.0, "hold": 120}),
    "momentum48": (lab2.s_mom48, {"x": 0.03, "k": 3.0, "rr": 2.0, "hold": 120}),
}


def main():
    data = lab2.load(Path(sys.argv[1]))
    frames = {s: lab2.resample(df, "1h") for s, df in data.items()}
    btc = lab2.resample(data["BTCUSDT"], "1D").close
    bull = (btc > btc.rolling(20).mean()).shift()
    split = list(frames.values())[0].index[int(len(list(frames.values())[0]) * 2 / 3)]
    for name, (fn, p) in IDEAS.items():
        for side in ("largo", "corto"):
            for partial in (False, True):
                for pause in (False, True):
                    tr = []
                    for s, df in frames.items():
                        d = df if side == "largo" else invert(df)
                        e, st, tg, _, hold = fn(d, p)
                        gate = bull if side == "largo" else ~bull.astype(bool)
                        e = e & gate.reindex(d.index, method="ffill").fillna(False).astype(bool)
                        tr += simulate(d, e, st, tg, hold, partial)
                    if pause:
                        tr = pause_after_streak(tr)
                    a = lab2.score([t for t in tr if t["t"] < split])
                    b = lab2.score([t for t in tr if t["t"] >= split])
                    print(json.dumps({"idea": name, "lado": side, "parcial_1R": partial, "pausa_racha": pause,
                                      "entreno": [a["n"], a["pnl_pct"], a["pf"], a["win"]],
                                      "examen": [b["n"], b["pnl_pct"], b["pf"], b["win"], b["dd"]]}), flush=True)


if __name__ == "__main__":
    main()

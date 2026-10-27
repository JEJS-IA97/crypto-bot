"""Investigación 2026-10-25: busca estrategias rentables en Spot (solo largos) con datos reales.

Uso: python research/lab_2026_10_25.py data/klines  (velas de 5 min, jsonl de collect_klines)
Costes: 0.1 % por lado + 0.05 % de deslizamiento. Riesgo 2 % por trade cuando hay stop.
Reglas: los parámetros se eligen SOLO con los primeros 2/3 del año (entreno) y se reporta
el último 1/3 (examen) tal cual. Si una idea no gana en examen, se descarta.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

FEE, SLIP, RISK = 0.001, 0.0005, 0.02
COST = 2 * (FEE + SLIP)


def load(folder: Path) -> dict[str, pd.DataFrame]:
    cache = folder.parent / "k5.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    out = {}
    for f in sorted(folder.glob("*.jsonl")):
        rows = [json.loads(line) for line in f.open()]
        df = pd.DataFrame(rows)[["open_time", "open", "high", "low", "close", "quote_volume"]].astype(float)
        df.index = pd.to_datetime(df.open_time, unit="ms", utc=True)
        out[f.stem] = df.drop(columns="open_time").rename(columns={"quote_volume": "vol"})
    pd.to_pickle(out, cache)
    return out


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "vol": "sum"}).dropna()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df.close.shift()
    tr = pd.concat([df.high - df.low, (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(s: pd.Series, n: int) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n).mean()
    return 100 - 100 / (1 + up / dn)


# --- motor: entra en la apertura de la vela siguiente a la señal -------------------------

def simulate(df: pd.DataFrame, entry: pd.Series, stop: pd.Series | None, target: pd.Series | None,
             exit_sig: pd.Series | None, max_hold: int) -> list[dict]:
    """Trades long de una serie. stop/target en precio (fijados en la vela de señal)."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    ent = entry.fillna(False).to_numpy()
    st = stop.to_numpy() if stop is not None else None
    tg = target.to_numpy() if target is not None else None
    ex = exit_sig.fillna(False).to_numpy() if exit_sig is not None else None
    trades, i, n = [], 0, len(df)
    while i < n - 1:
        if not ent[i]:
            i += 1
            continue
        px = o[i + 1]
        s = st[i] if st is not None else np.nan
        t = tg[i] if tg is not None else np.nan
        if not np.isnan(s) and s >= px:
            i += 1
            continue
        j, out, why = i + 1, None, "tiempo"
        while j < n:
            if not np.isnan(s) and l[j] <= s:
                out, why = min(s, o[j]), "stop"
                break
            if not np.isnan(t) and h[j] >= t:
                out, why = max(t, o[j]), "tp"
                break
            if ex is not None and ex[j] and j + 1 < n:
                out, why = o[j + 1], "salida"
                j += 1
                break
            if j - i >= max_hold:
                out = c[j]
                break
            j += 1
        if out is None:
            break  # sigue abierta al final: no se cuenta
        ret = out / px - 1 - COST
        risk = (px - s) / px if not np.isnan(s) else RISK / 0.25  # sin stop: 25 % del capital
        trades.append({"t": df.index[i + 1], "x": df.index[min(j, n - 1)], "ret": ret, "risk": max(risk, 0.002), "why": why})
        i = j
    return trades


def score(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "pnl_pct": 0.0, "pf": 0.0, "win": 0.0, "exp_r": 0.0, "dd": 0.0}
    # tamaño: arriesgar 2 % del capital (como la cuenta principal), máximo 100 % del capital
    # cartera real: máximo 3 posiciones a la vez, cada una ≤ 1/3 del capital (como la cuenta principal)
    eq, peak, dd, wins, losses = 1.0, 1.0, 0.0, 0.0, 0.0
    rs, open_until, taken = [], [], []
    for tr in sorted(trades, key=lambda x: x["t"]):
        open_until = [x for x in open_until if x > tr["t"]]
        if len(open_until) >= 3:
            continue
        open_until.append(tr.get("x", tr["t"]))
        taken.append(tr)
        frac = min(1 / 3, RISK / tr["risk"])
        g = frac * tr["ret"]
        eq *= 1 + g
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
        wins += max(g, 0)
        losses += max(-g, 0)
        rs.append(tr["ret"] / tr["risk"])
    trades = taken
    return {"n": len(trades), "pnl_pct": round((eq - 1) * 100, 2), "pf": round(wins / losses, 2) if losses else 99.0,
            "win": round(np.mean([t["ret"] > 0 for t in trades]) * 100, 1), "exp_r": round(float(np.mean(rs)), 3),
            "dd": round(dd * 100, 2)}


# --- ideas -----------------------------------------------------------------------------------

def s_breakout_96h(df1h, p):  # video TradingLab #1: cierre > SMA200 y > máximo 96 h, stop ATR
    a = atr(df1h)
    hi = df1h.high.rolling(p["look"]).max().shift()
    e = (df1h.close > df1h.close.rolling(200).mean()) & (df1h.close > hi)
    return e, df1h.close - p["k"] * a, df1h.close + p["rr"] * p["k"] * a, None, p["hold"]


def s_bollinger(df1h, p):  # video #2: cierre sobre banda superior
    m = df1h.close.rolling(20).mean()
    sd = df1h.close.rolling(20).std()
    a = atr(df1h)
    e = (df1h.close > m + p["z"] * sd) & (df1h.close.shift() <= (m + p["z"] * sd).shift())
    return e, df1h.close - p["k"] * a, df1h.close + p["rr"] * p["k"] * a, None, p["hold"]


def s_mom48(df1h, p):  # video #3: retorno 48 h cruza +X %
    r = df1h.close / df1h.close.shift(48) - 1
    a = atr(df1h)
    e = (r > p["x"]) & (r.shift() <= p["x"])
    return e, df1h.close - p["k"] * a, df1h.close + p["rr"] * p["k"] * a, None, p["hold"]


def s_rsi2(df1h, p):  # Connors: sobreventa extrema dentro de tendencia, sale al recuperar la media
    r = rsi(df1h.close, 2)
    sma = df1h.close.rolling(200).mean()
    e = (df1h.close > sma) & (r < p["lvl"])
    ex = df1h.close > df1h.close.rolling(5).mean()
    a = atr(df1h)
    return e, df1h.close - p["k"] * a, None, ex, p["hold"]


def s_smc_pullback(df5, p):  # video PA Academy adaptado a 5m: contexto 15m, compra en la zona del impulso
    c15 = resample(df5, "15min").close
    trend = (c15.ewm(span=50).mean() > c15.ewm(span=200).mean()).reindex(df5.index, method="ffill")
    body = df5.close - df5.open
    impulse = (body > 0) & (body.shift(1) > 0) & (body.shift(2) > 0) & (df5.close > df5.high.rolling(20).max().shift())
    zone_lo = df5.low.shift(3).where(impulse).ffill(limit=p["wait"])
    zone_hi = df5.open.shift(2).where(impulse).ffill(limit=p["wait"])
    e = trend & ~impulse & (df5.low <= zone_hi) & (df5.close > zone_lo)
    stop = zone_lo * 0.999
    return e, stop, df5.close + p["rr"] * (df5.close - stop), None, p["hold"]


def s_volbreak_daily(dfd, p):  # Larry Williams: rompe apertura + k·rango de ayer, sale al cierre
    rng = (dfd.high - dfd.low).shift()
    lvl = dfd.open + p["k"] * rng
    trend = dfd.close.shift() > dfd.close.rolling(p["sma"]).mean().shift()
    # entra dentro de la vela: se modela como la misma vela (entrada = nivel, salida = cierre)
    hit = trend & (dfd.high >= lvl)
    ret = (dfd.close / lvl.clip(lower=dfd.open) - 1 - COST).where(hit)
    return [{"t": t, "ret": r, "risk": RISK / 0.25, "why": "cierre"} for t, r in ret.dropna().items()]


IDEAS = {
    "ruptura_96h_1h": (s_breakout_96h, "1h", {"look": [48, 96, 168], "k": [2.0, 3.0], "rr": [2.0, 3.0], "hold": [120]}),
    "bollinger_1h": (s_bollinger, "1h", {"z": [2.0, 2.5], "k": [2.0, 3.0], "rr": [2.0, 3.0], "hold": [72]}),
    "momentum48_1h": (s_mom48, "1h", {"x": [0.03, 0.05, 0.08], "k": [2.0, 3.0], "rr": [2.0, 3.0], "hold": [120]}),
    "rsi2_1h": (s_rsi2, "1h", {"lvl": [5, 10], "k": [3.0, 5.0], "hold": [24, 48]}),
    "smc_5m": (s_smc_pullback, "5min", {"wait": [6, 12], "rr": [2.0, 3.0], "hold": [48]}),
}


def run_idea(data, name, fn, rule, grid):
    frames = {s: (df if rule == "5min" else resample(df, rule)) for s, df in data.items()}
    btc = resample(data["BTCUSDT"], "1D").close
    grid = {**grid, "regime": [0, 20, 50]}  # 0 = sin filtro; N = solo si BTC diario > SMA N
    split = min(df.index[0] for df in frames.values()) + (max(df.index[-1] for df in frames.values()) - min(df.index[0] for df in frames.values())) * 2 / 3
    best = None
    for combo in itertools.product(*grid.values()):
        p = dict(zip(grid, combo))
        per = {}
        for s, df in frames.items():
            e, st, tg, ex, hold = fn(df, p)
            if p["regime"]:
                ok = (btc > btc.rolling(p["regime"]).mean()).shift().reindex(df.index, method="ffill").fillna(False)
                e = e & ok
            per[s] = simulate(df, e, st, tg, ex, hold)
        train = [t for tr in per.values() for t in tr if t["t"] < split]
        sc = score(train)
        key = sc["pnl_pct"] if sc["n"] >= 15 else -1e9
        print("  ", name, p, "entreno", sc["pnl_pct"], "pf", sc["pf"], "n", sc["n"], flush=True)
        if best is None or key > best[0]:
            best = (key, p, per, sc)
    _, p, per, train_sc = best
    test = [t for tr in per.values() for t in tr if t["t"] >= split]
    by_sym = {s: score([t for t in tr if t["t"] >= split]) for s, tr in per.items()}
    return {"idea": name, "params": p, "train": train_sc, "test": score(test),
            "test_winners": sorted(s for s, v in by_sym.items() if v["n"] >= 3 and v["pnl_pct"] > 0), "split": str(split)[:10]}


def rotation(data, look: int, top: int, sma: int, rebalance: str = "1D"):
    """Momentum entre pares: cada día compra las `top` con mayor retorno a `look` días que estén sobre su SMA."""
    closes = pd.DataFrame({s: resample(df, rebalance).close for s, df in data.items()}).dropna()
    mom = closes / closes.shift(look) - 1
    above = closes > closes.rolling(sma).mean()
    rets = closes.pct_change().shift(-1)
    held_prev, eq = set(), [1.0]
    for t in closes.index[max(look, sma):-1]:
        cand = mom.loc[t][above.loc[t]].dropna().sort_values(ascending=False)
        held = set(cand.index[:top][cand.iloc[:top] > 0])
        turnover = len(held ^ held_prev) / max(top, 1)
        r = np.mean([rets.loc[t, s] for s in held]) if held else 0.0
        eq.append(eq[-1] * (1 + r * (len(held) / top) - turnover * (FEE + SLIP)))
        held_prev = held
    eq = pd.Series(eq)
    dd = (1 - eq / eq.cummax()).max()
    return eq, dd, closes.index[max(look, sma)]


def main() -> None:
    data = load(Path(sys.argv[1]))
    only = sys.argv[2] if len(sys.argv) > 2 else None
    print("datos:", {s: (str(df.index[0])[:10], str(df.index[-1])[:10]) for s, df in list(data.items())[:1]})
    bh = {s: round((df.close.iloc[-1] / df.close.iloc[0] - 1) * 100, 1) for s, df in data.items()}
    print("comprar y mantener (año):", bh)
    results = []
    for name, (fn, rule, grid) in IDEAS.items():
        if only and only != name:
            continue
        res = run_idea(data, name, fn, rule, grid)
        results.append(res)
        print(json.dumps(res, default=str))
    if only and only != "diario":
        return
    daily = {s: resample(df, "1D") for s, df in data.items()}
    split = list(daily.values())[0].index[int(len(list(daily.values())[0]) * 2 / 3)]
    vb = []
    for k, sma in itertools.product([0.5, 0.7], [20, 50]):
        tr = [t for df in daily.values() for t in s_volbreak_daily(df, {"k": k, "sma": sma})]
        vb.append(({"k": k, "sma": sma}, score([t for t in tr if t["t"] < split]), score([t for t in tr if t["t"] >= split])))
    p, a, b = max(vb, key=lambda x: x[1]["pnl_pct"])
    print(json.dumps({"idea": "volbreak_1d", "params": p, "train": a, "test": b}))
    rot = []
    for look, top, sma in itertools.product([7, 14, 30], [1, 2, 3], [20, 50]):
        eq, dd, start = rotation(data, look, top, sma)
        cut = int(len(eq) * 2 / 3)
        rot.append(({"look": look, "top": top, "sma": sma}, eq.iloc[cut] / eq.iloc[0] - 1, eq.iloc[-1] / eq.iloc[cut] - 1, dd))
    p, tr_, te, dd = max(rot, key=lambda x: x[1])
    print(json.dumps({"idea": "rotacion_momentum_1d", "params": p, "train_pct": round(tr_ * 100, 2),
                      "test_pct": round(te * 100, 2), "dd_total": round(dd * 100, 2)}))


if __name__ == "__main__":
    main()

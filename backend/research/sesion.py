"""Hipótesis "Quantumxx": a horas fijas (apertura de sesión) entra a favor del movimiento de las 4 h previas,
toma ganancia corta (TP) en ≤60 min. Se prueba en 10 pares (velas 5m, ~1 año) con comisión de futuros."""
import itertools, sys
import numpy as np, pandas as pd
data = pd.read_pickle(sys.argv[1])
COST = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0004
rows = []
for hours, tp, sl, hold, mode, minmove in itertools.product(
        [(8,), (16,), (8, 16), (0, 4, 8, 12, 16, 20)], [0.004, 0.006, 0.01], [0.004, 0.008, 0.015], [6, 12], ["sigue", "contra"], [0.0, 0.01]):
    tr, te = [], []
    for sym, df in data.items():
        idx = df.index
        o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
        pos = np.where(np.isin(idx.hour, hours) & (idx.minute == 0))[0]
        split = idx[int(len(idx) * 2 / 3)]
        for i in pos:
            if i < 48 or i + hold >= len(c):
                continue
            prev = c[i - 1] / o[i - 48] - 1
            if abs(prev) < minmove:
                continue
            d = np.sign(prev) * (1 if mode == "sigue" else -1)
            if d == 0:
                continue
            e = o[i]; r = None
            for j in range(i, i + hold):
                up, dn = h[j] / e - 1, l[j] / e - 1
                fav, adv = (up, dn) if d > 0 else (-dn, -up)
                if adv <= -sl: r = -sl; break
                if fav >= tp: r = tp; break
            if r is None:
                r = d * (c[i + hold - 1] / e - 1)
            (tr if idx[i] < split else te).append(r - COST)
    a, b = np.array(tr), np.array(te)
    rows.append((hours, tp, sl, hold * 5, mode, minmove, len(a), a.mean() * 100, (a > 0).mean() * 100, len(b), b.mean() * 100, (b > 0).mean() * 100))
res = pd.DataFrame(rows, columns=["horas", "tp", "sl", "min", "modo", "mov_min", "n_ent", "ent_%", "acierto_ent", "n_ex", "ex_%", "acierto_ex"])
print("Ganan en entreno Y examen (ordenado por examen):")
g = res[(res["ent_%"] > 0) & (res["ex_%"] > 0)].sort_values("ex_%", ascending=False)
print(g.head(12).round(3).to_string(index=False) if len(g) else "ninguna")
print("\nMejores en entreno:")
print(res.sort_values("ent_%", ascending=False).head(6).round(3).to_string(index=False))

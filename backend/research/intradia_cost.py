"""Cómo se mueve el precio a corto plazo y qué queda después de comisiones (10 pares, velas 5m, ~1 año).

1) Tamaño típico del movimiento por horizonte (5m … 4h) frente al coste ida y vuelta.
2) Estacionalidad por hora UTC (¿hay horas con sesgo?).
3) Después de un movimiento fuerte en N min, ¿sigue (momentum) o se devuelve (reversión) en los
   siguientes M min? Se mide el retorno neto medio, con entreno (2/3) y examen (1/3).
Costes: taker 0,10 %/lado (0,20 % ida y vuelta) y maker con BNB 0,075 %/lado (0,15 %).
Uso: python intradia.py data/k5.pkl
"""

import itertools
import json
import sys

import numpy as np
import pandas as pd

TAKER, MAKER = 0.0020, float(sys.argv[2])
data = pd.read_pickle(sys.argv[1])
H = {"5m": 1, "10m": 2, "20m": 4, "30m": 6, "1h": 12, "2h": 24, "4h": 48}

import sys as _s
if False:
  pass
# 3) movimiento fuerte → ¿sigue o se devuelve?
print("\n== 3) Tras un movimiento fuerte: retorno neto medio por operación (maker 0,15 %) ==")
results = []
for (look_n, look), (hold_n, hold), z in itertools.product(
        [("15m", 3), ("30m", 6), ("1h", 12), ("4h", 48)], [("15m", 3), ("30m", 6), ("1h", 12), ("4h", 48)], [2.0, 3.0]):
    for mode in ("sigue", "se devuelve"):
        tr, te = [], []
        for sym, df in data.items():
            c = df.close
            past = c / c.shift(hold) - 1 if False else c / c.shift(look) - 1
            sd = past.rolling(2000).std()
            fut = c.shift(-hold) / c - 1
            sig = (past > z * sd) | (past < -z * sd)
            direction = np.sign(past) if mode == "sigue" else -np.sign(past)
            ret = (direction * fut - MAKER)[sig]
            ret = ret[~ret.index.duplicated()].dropna()
            ret = ret.iloc[::max(hold, 1)]  # sin operaciones solapadas
            split = c.index[int(len(c) * 2 / 3)]
            tr.append(ret[ret.index < split])
            te.append(ret[ret.index >= split])
        a, b = pd.concat(tr), pd.concat(te)
        results.append((look, hold, z, mode, len(a), a.mean() * 100, len(b), b.mean() * 100, (b > 0).mean() * 100))
res = pd.DataFrame(results, columns=["mira", "mantiene", "z", "modo", "n_ent", "ent_%", "n_ex", "ex_%", "acierto_ex"])
res = res.sort_values("ent_%", ascending=False)
print(res.head(12).round(3).to_string(index=False))
print("\nMejores en examen que también ganan en entreno:")
good = res[(res["ent_%"] > 0) & (res["ex_%"] > 0)].sort_values("ex_%", ascending=False)
print(good.head(10).round(3).to_string(index=False) if len(good) else "ninguna")

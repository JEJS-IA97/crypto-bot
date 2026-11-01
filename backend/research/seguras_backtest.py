"""¿Las "seguras" del modelo aciertan lo que dicen? Backtest sin mirar el futuro.

Temporada 2025/26 de 12 ligas: cada partido se predice con lo jugado antes (2024/25 + 2025/26
hasta la víspera). Se reporta acierto real vs probabilidad media y ROI a la cuota mínima.
Uso: python -m research.seguras_backtest
"""
import csv
import io
from collections import defaultdict
from datetime import datetime

import httpx

from app.bets import safe

LEAGUES = ["E0", "E1", "SP1", "D1", "I1", "F1", "N1", "P1", "B1", "T1", "SC0", "G1"]
H = {"User-Agent": "Mozilla/5.0"}


def load(season, div):
    r = httpx.get(f"https://football-data.co.uk/mmz4281/{season}/{div}.csv", headers=H, follow_redirects=True, timeout=30)
    rows = [x for x in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", "replace"))) if x.get("FTR")]
    for x in rows:
        x["_d"] = datetime.strptime(x["Date"], "%d/%m/%Y" if len(x["Date"]) == 10 else "%d/%m/%y")
    return rows


res = defaultdict(lambda: [0, 0, 0.0, 0.0])  # n, aciertos, suma prob, pnl a cuota mínima
for div in LEAGUES:
    prev, cur = load("2425", div), load("2526", div)
    cur.sort(key=lambda x: x["_d"])
    days = sorted({x["_d"] for x in cur})
    for d in days:
        stats = safe.build_stats(prev + [x for x in cur if x["_d"] < d])
        for row in (x for x in cur if x["_d"] == d):
            for p in safe.safe_picks(stats, row):
                h = safe.hit(p["selection"], row)
                if h is None:
                    continue
                r = res[p["selection"]]
                r[0] += 1; r[1] += h; r[2] += p["fair_prob"]; r[3] += (p["odds"] - 1) if h else -1
tot = [0, 0, 0.0, 0.0]
print(f"{'mercado':16} {'n':>5} {'acierto':>8} {'prob':>6} {'ROI@min':>8}")
for m, (n, w, sp, pnl) in sorted(res.items(), key=lambda x: -x[1][0]):
    print(f"{m:16} {n:5} {w/n*100:7.1f}% {sp/n*100:5.1f}% {pnl/n*100:7.2f}%")
    tot = [tot[0] + n, tot[1] + w, tot[2] + sp, tot[3] + pnl]
print(f"{'TOTAL':16} {tot[0]:5} {tot[1]/tot[0]*100:7.1f}% {tot[2]/tot[0]*100:5.1f}% {tot[3]/tot[0]*100:7.2f}%")

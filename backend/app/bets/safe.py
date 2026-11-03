"""Mercados "seguros" más allá de 1X2: goles, primer tiempo, córners, tarjetas, faltas y "marca".

Cómo se estima la probabilidad de cada mercado en un partido (sin modelo de Poisson, que salía
sobreconfiado): frecuencia con que pasó en los partidos de local del equipo local y en los de
visitante del visitante (esta temporada y la anterior), encogida hacia la media de la liga.
Se apuesta (en paper) cuando la probabilidad es ≥ MIN_PROB; la cuota que se registra es la
"cuota mínima" (justa +3 %). Si el modelo está bien calibrado, el ROI a esa cuota queda ≈ +3 %;
si sale negativo, las "seguras" no lo son tanto como dice el modelo. Con esa cifra se sabe qué
cuota exigirle a la casa antes de poner dinero.
Goleadores: football-data no publica quién marca, así que no se pueden liquidar (fuera).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

MIN_PROB = 0.85
MARGIN = 1.03
SHRINK = 40  # partidos "virtuales" de la media de liga (backtest 2025/26: con 8 sobreestimaba 2,2 pts; con 40, 0,9)
# Córners: aun así el modelo prometía ~91 % y salía ~84-88 % → se descuenta lo que sobraba.
CALIBRATION = {"corners_o6.5": -0.07, "corners_o7.5": -0.07, "corners_u13.5": -0.04}
MIN_GAMES = 5
PER_MATCH = 2  # mercados por partido (los de mayor probabilidad)


def _f(row: dict, *cols: str) -> float | None:
    try:
        return sum(float(row[c]) for c in cols)
    except (KeyError, TypeError, ValueError):
        return None


def _gt(cols: tuple[str, ...], line: float) -> Callable[[dict], bool | None]:
    def hit(row: dict) -> bool | None:
        v = _f(row, *cols)
        return None if v is None else v > line
    return hit


def _lt(cols: tuple[str, ...], line: float) -> Callable[[dict], bool | None]:
    def hit(row: dict) -> bool | None:
        v = _f(row, *cols)
        return None if v is None else v < line
    return hit


GOALS, HT = ("FTHG", "FTAG"), ("HTHG", "HTAG")
CORNERS, CARDS, FOULS = ("HC", "AC"), ("HY", "AY", "HR", "AR"), ("HF", "AF")
# código → (texto, función de acierto sobre la fila del resultado)
MARKETS: dict[str, tuple[str, Callable[[dict], bool | None]]] = {
    "goles_o0.5": ("Más de 0,5 goles", _gt(GOALS, 0.5)),
    "goles_o1.5": ("Más de 1,5 goles", _gt(GOALS, 1.5)),
    "goles_u3.5": ("Menos de 3,5 goles", _lt(GOALS, 3.5)),
    "goles_u4.5": ("Menos de 4,5 goles", _lt(GOALS, 4.5)),
    "gol_1t": ("Gol en el primer tiempo", _gt(HT, 0.5)),
    "local_marca": ("El local marca", _gt(("FTHG",), 0.5)),
    "visita_marca": ("El visitante marca", _gt(("FTAG",), 0.5)),
    "corners_o6.5": ("Más de 6,5 córners", _gt(CORNERS, 6.5)),
    "corners_o7.5": ("Más de 7,5 córners", _gt(CORNERS, 7.5)),
    "corners_u13.5": ("Menos de 13,5 córners", _lt(CORNERS, 13.5)),
    "tarjetas_o1.5": ("Más de 1,5 tarjetas", _gt(CARDS, 1.5)),
    "tarjetas_o2.5": ("Más de 2,5 tarjetas", _gt(CARDS, 2.5)),
    "tarjetas_u6.5": ("Menos de 6,5 tarjetas", _lt(CARDS, 6.5)),
    "faltas_o18.5": ("Más de 18,5 faltas", _gt(FOULS, 18.5)),
}


def hit(market: str, row: dict) -> bool | None:
    """¿Se cumplió el mercado en el partido? None si la liga no publica ese dato."""
    return MARKETS[market][1](row) if market in MARKETS else None


def build_stats(history: list[dict]) -> dict:
    """Por liga: aciertos de cada mercado en la liga y por equipo (como local / como visitante)."""
    league = defaultdict(lambda: [0, 0])
    home = defaultdict(lambda: [0, 0])
    away = defaultdict(lambda: [0, 0])
    for row in history:
        if not row.get("FTR"):
            continue
        for m in MARKETS:
            h = hit(m, row)
            if h is None:
                continue
            for bucket, k in ((league, m), (home, (row["HomeTeam"], m)), (away, (row["AwayTeam"], m))):
                bucket[k][0] += int(h)
                bucket[k][1] += 1
    return {"league": dict(league), "home": dict(home), "away": dict(away)}


def probability(stats: dict, home_team: str, away_team: str, market: str) -> float | None:
    base = stats["league"].get(market)
    h = stats["home"].get((home_team, market))
    a = stats["away"].get((away_team, market))
    if not base or not h or not a or h[1] < MIN_GAMES or a[1] < MIN_GAMES:
        return None
    rate = base[0] / base[1]
    return (h[0] + a[0] + SHRINK * rate) / (h[1] + a[1] + SHRINK) + CALIBRATION.get(market, 0.0)


def min_odds(prob: float) -> float:
    return round(MARGIN / prob, 3)


def safe_picks(stats: dict, row: dict) -> list[dict]:
    """Los mercados más probables del partido que pasan MIN_PROB (máximo PER_MATCH)."""
    found = []
    for m in MARKETS:
        p = probability(stats, row["HomeTeam"], row["AwayTeam"], m)
        if p is not None and p >= MIN_PROB:
            found.append({"strategy": "seguro", "selection": m, "fair_prob": p, "odds": min_odds(p)})
    return sorted(found, key=lambda x: -x["fair_prob"])[:PER_MATCH]


def safe_parlays(picks: list[tuple[str, dict]], size: int = 3) -> list[dict]:
    """Parley de `size` seguras de partidos distintos (las más probables primero)."""
    best: dict[str, dict] = {}
    for match_key, p in picks:
        if match_key not in best or p["fair_prob"] > best[match_key]["fair_prob"]:
            best[match_key] = p
    ranked = sorted(best.items(), key=lambda x: -x[1]["fair_prob"])
    out = []
    for i in range(0, len(ranked) - size + 1, size):
        group = ranked[i:i + size]
        prob, odds = 1.0, 1.0
        for _, p in group:
            prob *= p["fair_prob"]
            odds *= p["odds"]
        out.append({"strategy": "parley_seguro" if size == 3 else f"parley{size}_seguro", "match": " + ".join(k for k, _ in group),
                    "selection": ",".join(p["selection"] for _, p in group), "odds": round(odds, 3), "fair_prob": prob})
    return out

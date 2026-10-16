"""Ratios del torneo (los de un trader): acierto, R:R, esperanza, PF, DD, Sharpe,
Monte Carlo y desglose por régimen. Equity y DD sobre PnL realizado.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from decimal import Decimal

from app.lab.engine import Trade

MC_RUNS = 500


def _f(x: Decimal | float | None, places: int = 2) -> float | None:
    return None if x is None else round(float(x), places)


def max_drawdown_pct(capital: float, pnls: list[float]) -> float:
    equity = peak = capital
    worst = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return worst * 100


def monte_carlo(capital: float, pnls: list[float], runs: int = MC_RUNS) -> dict:
    """Reordena los trades al azar `runs` veces: ¿qué tan mala pudo ser la racha?"""
    if len(pnls) < 5:
        return {}
    rng = random.Random(42)
    finals, dds = [], []
    for _ in range(runs):
        sample = pnls[:]
        rng.shuffle(sample)
        finals.append(sum(sample) / capital * 100)
        dds.append(min(100.0, max_drawdown_pct(capital, sample)))
    finals.sort()
    dds.sort()
    # Rachas: con orden aleatorio el retorno final es el mismo; lo que cambia
    # es el camino. Se reporta el DD del peor 5 % y la racha perdedora real.
    return {
        "dd_p50": round(dds[runs // 2], 2),
        "dd_p95": round(dds[int(runs * 0.95)], 2),
    }


def _longest_losing_streak(pnls: list[float]) -> int:
    best = run = 0
    for p in pnls:
        run = run + 1 if p <= 0 else 0
        best = max(best, run)
    return best


def summarize(trades: list[Trade], capital: Decimal, days: float | None = None) -> dict:
    cap = float(capital)
    pnls = [float(t.pnl) for t in sorted(trades, key=lambda t: t.closed_ts)]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    rs = [float(t.r_multiple) for t in trades if t.r_multiple is not None]
    daily: dict[int, float] = defaultdict(float)
    for t in trades:
        daily[t.closed_ts // 86_400_000] += float(t.pnl)
    sharpe = None
    if len(daily) >= 5:
        rets = [v / cap for v in daily.values()]
        mean = sum(rets) / len(rets)
        sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets))
        sharpe = round(mean / sd * math.sqrt(365), 2) if sd else None
    by_regime: dict[str, dict] = {}
    for label in sorted({t.regime for t in trades}):
        sub = [float(t.pnl) for t in trades if t.regime == label]
        by_regime[label] = {
            "trades": len(sub),
            "win_rate": round(sum(1 for p in sub if p > 0) / len(sub) * 100, 1),
            "pnl": round(sum(sub), 2),
            "expectancy": round(sum(sub) / len(sub), 4),
        }
    net = sum(pnls)
    return {
        "trades": len(pnls),
        "trades_per_day": round(len(pnls) / days, 2) if days else None,
        "long_trades": sum(1 for t in trades if t.side == "LONG"),
        "short_trades": sum(1 for t in trades if t.side == "SHORT"),
        "win_rate": round(len(wins) / len(pnls) * 100, 1) if pnls else None,
        "avg_win": round(gross_win / len(wins), 4) if wins else None,
        "avg_loss": round(-gross_loss / len(losses), 4) if losses else None,
        "payoff": round((gross_win / len(wins)) / (gross_loss / len(losses)), 2)
        if wins and losses and gross_loss
        else None,
        "expectancy_usd": round(net / len(pnls), 4) if pnls else None,
        "expectancy_r": round(sum(rs) / len(rs), 3) if rs else None,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "net_pnl": round(net, 2),
        "fees": round(sum(float(t.fees) for t in trades), 2),
        "return_pct": round(net / cap * 100, 2),
        "max_dd_pct": round(max_drawdown_pct(cap, pnls), 2),
        "sharpe": sharpe,
        "losing_streak": _longest_losing_streak(pnls),
        "monte_carlo": monte_carlo(cap, pnls),
        "by_regime": by_regime,
    }

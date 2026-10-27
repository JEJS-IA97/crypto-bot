"""Cerebro que aprende: propone estrategias, las prueba y decide cuáles operan.

Ciclo (cada vez que corre el analista):
1. Genera candidatas: mutaciones de las que ya ganan, familias al azar
   (más probabilidad a las familias que más aprueban) e ideas de Gemini.
2. Las prueba en el histórico: 75 % de las velas para ver si funcionan y el
   25 % más reciente, que no vio nadie, como examen (fuera de muestra), con
   comisiones, slippage, Monte Carlo y dos vecinos de parámetros (robustez).
3. Las que aprueban entran al torneo en vivo (paper) con 100 USD.
4. En vivo: tras 15 operaciones, las que pierden se retiran; las fijas del
   torneo que pierden con 30+ operaciones se mandan a la banca (no abren más).
5. Cada decisión se anota en docs/brain/memoria.md y en la BD: es la memoria
   que se le pasa a Gemini la próxima vez.

Pocos grados de libertad por familia (≤4) para no sobreajustar.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import settings
from app.database import Base
from app.lab import indicators as ind
from app.lab.backtest import run_strategy
from app.lab.bars import TF_MINUTES, Bar, load_jsonl, resample
from app.lab.engine import Trade
from app.lab.metrics import summarize
from app.lab.regime import RegimeLookup
from app.lab.strategies import STRATEGIES, Signal, Strategy, _long
from app.models import utc_now

logger = logging.getLogger(__name__)

EVOLVED_CAPITAL = 100
MAX_LIVE = 8
CANDIDATES_PER_RUN = 10
LIVE_MIN_TRADES = 15
STATIC_MIN_TRADES = 30
PAIR_MIN_TRADES = 8  # trades de una estrategia en un par antes de juzgarla en ese par
FAST_RETIRE_TRADES = 4  # diarias: con 4 cierres y -3 % ya no se espera a 15
FAST_RETIRE_PCT = -3.0
MAX_PER_KIND = 2  # vivas por familia y timeframe: 8 "tendencia 1d" casi iguales eran una sola apuesta x8

# familia → {parámetro: (mín, máx, tipo)}; "tf" se elige de la lista.
FAMILIES: dict[str, dict[str, Any]] = {
    "tendencia": {
        "tf": ["4h", "1d"],
        "fast": (10, 100, int),
        "slow": (50, 250, int),
    },
    "donchian": {
        "tf": ["1h", "4h"],
        "n": (20, 120, int),
        "stop_atr": (1.5, 4.0, float),
        "tp_atr": (2.0, 8.0, float),
    },
    "ema_rsi": {
        "tf": ["1h", "4h"],
        "fast": (8, 50, int),
        "slow": (50, 200, int),
        "stop_atr": (1.5, 4.0, float),
        "tp_atr": (2.0, 8.0, float),
    },
    "momentum": {
        "tf": ["4h", "1d"],
        "lookback": (6, 60, int),
        "min_ret": (0.0, 0.15, float),
    },
    "reversion": {
        "tf": ["15m", "1h"],
        "rsi_low": (15, 35, int),
        "stop_atr": (1.0, 3.0, float),
        "tp_atr": (1.0, 4.0, float),
    },
}

DESCRIPTIONS = {
    "tendencia": "Comprado si el cierre está sobre SMA{fast} y SMA{slow} ({tf}); sale al perder alguna.",
    "donchian": "Compra al romper el máximo de {n} velas ({tf}) sobre SMA200. Stop {stop_atr} ATR, objetivo {tp_atr} ATR.",
    "ema_rsi": "EMA{fast} sobre EMA{slow} y RSI cruza 50 al alza ({tf}). Stop {stop_atr} ATR, objetivo {tp_atr} ATR.",
    "momentum": "Comprado mientras el retorno de las últimas {lookback} velas ({tf}) supere {min_ret:.0%}; sale al perderlo.",
    "reversion": "RSI<{rsi_low} sobre SMA200 ({tf}): compra el rebote. Stop {stop_atr} ATR, objetivo {tp_atr} ATR, máx. 24 velas.",
}


class BrainGenome(Base):
    __tablename__ = "brain_genomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    family: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict] = mapped_column(JSON)
    origin: Mapped[str] = mapped_column(String(20))  # azar | mutación | gemini | fija
    status: Mapped[str] = mapped_column(String(12), index=True)  # live | banca | retirada | rechazada
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


# --- estrategia paramétrica -------------------------------------------------


class Evolved(Strategy):
    def __init__(self, name: str, family: str, params: dict[str, Any]) -> None:
        self.name, self.family, self.params = name, family, params
        self.timeframe = params["tf"]
        self.symbols = set(params.get("symbols") or [])  # vacío = todos
        self.label = f"{family} {_short_params(params)}"
        self.description = DESCRIPTIONS[family].format(**params) + (
            f" Solo en {', '.join(s.replace('USDT', '') for s in sorted(self.symbols))}." if self.symbols else "")
        self.max_hold = 24 if family == "reversion" else None
        self.warmup = 260

    def _inside(self, bars: list[Bar]) -> list[bool]:
        c = [b.c for b in bars]
        f, s = ind.sma(c, self.params["fast"]), ind.sma(c, self.params["slow"])
        return [f[i] is not None and s[i] is not None and c[i] > f[i] and c[i] > s[i] for i in range(len(c))]

    def _momentum(self, bars: list[Bar]) -> list[bool]:
        n, edge = self.params["lookback"], self.params["min_ret"]
        return [i >= n and bars[i].c / bars[i - n].c - 1 > edge for i in range(len(bars))]

    def signals(self, bars: list[Bar]) -> list[Signal | None]:
        p, c = self.params, [b.c for b in bars]
        if self.family == "tendencia":
            return [Signal("LONG", None, None) if x else None for x in self._inside(bars)]
        if self.family == "momentum":
            return [Signal("LONG", None, None) if x else None for x in self._momentum(bars)]
        a, t = ind.atr(bars), ind.sma(c, 200)
        out: list[Signal | None] = [None] * len(bars)
        if self.family == "donchian":
            hh = ind.highest_prev([b.h for b in bars], p["n"])
            for i in range(len(bars)):
                if None not in (hh[i], a[i], t[i]) and c[i] > hh[i] and c[i] > t[i]:
                    out[i] = _long(c[i], c[i] - p["stop_atr"] * a[i], p["tp_atr"] / p["stop_atr"])
        elif self.family == "ema_rsi":
            f, s, r = ind.ema(c, p["fast"]), ind.ema(c, p["slow"]), ind.rsi(c)
            for i in range(1, len(bars)):
                if None not in (f[i], s[i], r[i - 1], r[i], a[i]) and f[i] > s[i] and r[i - 1] <= 50 < r[i]:
                    out[i] = _long(c[i], c[i] - p["stop_atr"] * a[i], p["tp_atr"] / p["stop_atr"])
        elif self.family == "reversion":
            r = ind.rsi(c)
            for i in range(len(bars)):
                if None not in (r[i], a[i], t[i]) and r[i] < p["rsi_low"] and c[i] > t[i]:
                    out[i] = _long(c[i], c[i] - p["stop_atr"] * a[i], p["tp_atr"] / p["stop_atr"])
        return out

    def exit_now(self, bars: list[Bar], i: int, side: str) -> bool:
        if self.family == "momentum":
            return not self._momentum(bars[: i + 1])[-1]
        return self.family == "tendencia" and not self._inside(bars[: i + 1])[-1]


def _short_params(params: dict[str, Any]) -> str:
    tf, *rest = [v for k, v in params.items() if k != "symbols"]
    return f"{tf} · " + " / ".join(str(v) for v in rest)


def clip(family: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Valida/recorta parámetros (vienen de mutaciones o de Gemini)."""
    spec = FAMILIES.get(family)
    if spec is None:
        return None
    out: dict[str, Any] = {"tf": params.get("tf") if params.get("tf") in spec["tf"] else spec["tf"][0]}
    for key, value in spec.items():
        if key == "tf":
            continue
        low, high, kind = value
        try:
            x = kind(params.get(key, (low + high) / 2))
        except (TypeError, ValueError):
            return None
        out[key] = kind(round(min(max(x, low), high), 2))
    if "fast" in out and out["fast"] >= out["slow"]:
        out["fast"] = max(spec["fast"][0], out["slow"] // 2)
    return out


def random_genome(rng: random.Random, family: str) -> dict[str, Any]:
    spec = FAMILIES[family]
    raw = {k: (rng.choice(v) if k == "tf" else rng.uniform(v[0], v[1])) for k, v in spec.items()}
    return clip(family, raw)


def mutate(rng: random.Random, family: str, params: dict[str, Any], scale: float = 0.2) -> dict[str, Any]:
    raw = {k: v for k, v in params.items() if k != "symbols"}  # los pares los decide el examen
    key = rng.choice([k for k in raw if k != "tf"])
    raw[key] = params[key] * (1 + rng.uniform(-scale, scale))
    if rng.random() < 0.15:
        raw["tf"] = rng.choice(FAMILIES[family]["tf"])
    return clip(family, raw)


def genome_name(family: str, params: dict[str, Any]) -> str:
    values = [str(v) for k, v in params.items() if k != "symbols"]
    return ("evo_" + family + "_" + "_".join(values)).replace(".", "p")[:60]


# --- examen en el histórico -------------------------------------------------


@dataclass
class History:
    by_tf: dict[str, dict[str, list[Bar]]]
    regimes: dict[str, RegimeLookup]
    split_ts: int  # desde aquí: fuera de muestra
    days_in: float
    days_out: float


def load_history(data_dir: Path, symbols: list[str], oos_fraction: float = 0.25) -> History | None:
    raw = {s: load_jsonl(data_dir / f"{s}.jsonl") for s in symbols if (data_dir / f"{s}.jsonl").exists()}
    if not raw:
        return None
    first = min(b[0].ts for b in raw.values())
    last = max(b[-1].ts for b in raw.values())
    split = int(last - (last - first) * oos_fraction)
    days = (last - first) / 86_400_000
    by_tf = {tf: {s: (b if m == 5 else resample(b, m)) for s, b in raw.items()} for tf, m in TF_MINUTES.items()}
    daily = data_dir.parent / "klines_1d"
    for s in raw:  # 1d con años de historia si existen (la SMA200 diaria lo necesita)
        if (daily / f"{s}.jsonl").exists():
            # Solo 260 días antes del periodo de examen (calentamiento de la SMA200): con años
            # de historia la cuenta se capitalizaba desde 2017 y el examen daba +700 USD falsos.
            start = first - 260 * 86_400_000
            by_tf["1d"][s] = [b for b in load_jsonl(daily / f"{s}.jsonl") if b.ts >= start]
    regimes = {s: RegimeLookup(by_tf["1h"][s]) for s in raw}
    return History(by_tf, regimes, split, days * (1 - oos_fraction), days * oos_fraction)


def _split(trades: list[Trade], split_ts: int) -> tuple[list[Trade], list[Trade]]:
    return [t for t in trades if t.opened_ts < split_ts], [t for t in trades if t.opened_ts >= split_ts]


def examine(strategy: Strategy, history: History) -> dict[str, Any]:
    account = run_strategy(strategy, history.by_tf[strategy.timeframe], history.regimes, capitals=(EVOLVED_CAPITAL,))[0]
    ins, outs = _split(account.trades, history.split_ts)
    from decimal import Decimal

    cap = Decimal(EVOLVED_CAPITAL)
    by_symbol = {}
    for t in account.trades:
        row = by_symbol.setdefault(t.symbol, {"in": 0.0, "out": 0.0})
        row["out" if t.opened_ts >= history.split_ts else "in"] += float(t.pnl)
    return {"in": summarize(ins, cap, history.days_in), "out": summarize(outs, cap, history.days_out),
            "symbols": by_symbol}


def winning_symbols(result: dict[str, Any]) -> list[str]:
    """Pares donde la estrategia ganó en entrenamiento Y en el examen: solo ahí opera."""
    return sorted(s for s, v in result.get("symbols", {}).items() if v["in"] > 0 and v["out"] > 0)


def verdict(result: dict[str, Any], min_out_trades: int = 6) -> tuple[bool, str]:
    """Reglas del examen. Devuelve (aprueba, motivo legible)."""
    i, o = result["in"], result["out"]
    if i["trades"] < 15:
        return False, f"pocas operaciones en entrenamiento ({i['trades']})"
    if (i["profit_factor"] or 0) < 1.1:
        return False, f"no gana en entrenamiento (PF {i['profit_factor']})"
    if o["trades"] < min_out_trades:
        return False, f"pocas operaciones en el examen ({o['trades']})"
    if o["net_pnl"] <= 0 or (o["profit_factor"] or 0) < 1.05:
        return False, f"pierde en el examen fuera de muestra ({o['net_pnl']:+.2f} USD, PF {o['profit_factor']})"
    dd95 = (o.get("monte_carlo") or {}).get("dd_p95") or o["max_dd_pct"]
    if dd95 > 35:
        return False, f"drawdown Monte Carlo p95 de {dd95} %"
    return True, f"examen +{o['net_pnl']:.2f} USD, PF {o['profit_factor']}, {o['trades']} trades"


def robust(family: str, params: dict[str, Any], history: History, rng: random.Random) -> bool:
    """Dos vecinos con parámetros ±15 %: si la idea es real, no se cae al moverla un poco."""
    ok = 0
    for _ in range(2):
        neighbor = mutate(rng, family, params, scale=0.15)
        result = examine(Evolved("vecino", family, neighbor), history)
        ok += result["out"]["net_pnl"] > 0
    return ok >= 1


# --- memoria ----------------------------------------------------------------


def remember(lines: list[str], now: datetime) -> None:
    if not lines:
        return
    path = Path(settings.brain_dir) / "memoria.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# Memoria del cerebro\n\nLo que el bot probó y aprendió. Se le pasa a Gemini en cada ciclo.\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {now:%Y-%m-%d %H:%M} UTC\n" + "\n".join(f"- {x}" for x in lines) + "\n")


def recent_memory(max_chars: int = 3000) -> str:
    path = Path(settings.brain_dir) / "memoria.md"
    return path.read_text(encoding="utf-8")[-max_chars:] if path.exists() else ""


def family_odds(db: Session) -> dict[str, float]:
    """Lo aprendido sobre dónde buscar: tasa de aprobación (suavizada) por familia."""
    rows = db.scalars(select(BrainGenome).where(BrainGenome.origin != "fija")).all()
    odds = {}
    for family in FAMILIES:
        mine = [r for r in rows if r.family == family]
        passed = sum(1 for r in mine if r.status in ("live", "retirada"))
        odds[family] = (passed + 1) / (len(mine) + 2)
    return odds


# --- decisiones en vivo -----------------------------------------------------


def live_stats(trades: list[Trade], name: str) -> dict[str, Any]:
    from decimal import Decimal

    mine = [t for t in trades if t.strategy == name]
    capital = mine[0].capital if mine else Decimal(EVOLVED_CAPITAL)
    return summarize(mine, capital)


def review_live(db: Session, trades: list[Trade]) -> list[str]:
    """Retira evolucionadas que pierden y manda a la banca a las fijas que pierden."""
    from app.lab.strategies import RETIRED

    notes = []
    known = {g.name: g for g in db.scalars(select(BrainGenome))}
    for name, why in RETIRED.items():
        row = known.get(name)
        if row is not None and row.status in ("live", "banca"):
            row.status, row.note = "retirada", f"fuera del torneo: perdió en vivo ({why})"
            notes.append(f"{name}: {row.note}.")
    for strategy in STRATEGIES:
        if strategy.name not in known:
            row = BrainGenome(name=strategy.name, family="fija", params={"tf": strategy.timeframe},
                              origin="fija", status="live", metrics={})
            db.add(row)
            known[strategy.name] = row
    for row in known.values():
        if row.status not in ("live", "banca"):
            continue
        stats = live_stats(trades, row.name)
        row.metrics = {**(row.metrics or {}), "vivo": {k: stats[k] for k in ("trades", "net_pnl", "expectancy_r", "profit_factor", "win_rate")}}
        label = row.name
        if row.status == "live":
            pairs = set((row.metrics or {}).get("banca_pares", []))
            for symbol in {t.symbol for t in trades if t.strategy == row.name}:
                mine = [t for t in trades if t.strategy == row.name and t.symbol == symbol]
                if f"{row.name}|{symbol}" not in pairs and len(mine) >= PAIR_MIN_TRADES and sum(float(t.pnl) for t in mine) < 0:
                    pairs.add(f"{row.name}|{symbol}")
                    notes.append(f"{label} deja de operar {symbol}: {len(mine)} trades, {sum(float(t.pnl) for t in mine):+.2f} USD en ese par.")
            row.metrics = {**row.metrics, "banca_pares": sorted(pairs)}
        if row.origin == "fija":
            losing = stats["trades"] >= STATIC_MIN_TRADES and (stats["expectancy_r"] or stats["expectancy_usd"] or 0) < -0.1
            if row.status == "live" and losing:
                row.status, row.note = "banca", f"a la banca: {stats['trades']} trades, {stats['net_pnl']:+.2f} USD"
                notes.append(f"{label}: {row.note}.")
        elif row.status == "live" and stats["trades"] >= FAST_RETIRE_TRADES and stats["return_pct"] <= FAST_RETIRE_PCT:
            row.status = "retirada"
            row.note = f"en vivo {stats['return_pct']:+.2f} % en {stats['trades']} trades: no se espera a 15"
            notes.append(f"Retirada {label}: {row.note}.")
        elif row.status == "live" and stats["trades"] >= LIVE_MIN_TRADES:
            if stats["net_pnl"] < 0 or (stats["expectancy_r"] or 0) < 0:
                row.status = "retirada"
                row.note = f"aprobó el examen pero en vivo perdió {stats['net_pnl']:+.2f} USD en {stats['trades']} trades"
                notes.append(f"Retirada {label}: {row.note}. Lección: su backtest no se sostuvo en vivo.")
        row.updated_at = utc_now()
    kinds: dict[tuple[str, str], list[BrainGenome]] = {}
    for row in known.values():
        if row.status == "live" and row.origin != "fija":
            kinds.setdefault((row.family, row.params.get("tf", "")), []).append(row)
    for (family, tf), rows in kinds.items():
        rows.sort(key=lambda r: (-(((r.metrics or {}).get("vivo") or {}).get("net_pnl") or 0), r.id or 0))
        for row in rows[MAX_PER_KIND:]:
            row.status, row.note = "retirada", f"clon: ya hay {MAX_PER_KIND} {family} {tf} vivas mejores (no diversifica)"
            notes.append(f"Retirada {row.name}: {row.note}.")
    db.commit()
    return notes


def confidence(trades: list[Trade], names: list[str]) -> dict[str, float]:
    """Peso de cada estrategia viva: esperanza en R encogida hacia 0 con pocos trades."""
    scores = {}
    for name in names:
        rs = [float(t.r_multiple) for t in trades if t.strategy == name and t.r_multiple is not None]
        n = len(rs)
        scores[name] = max(0.0, (sum(rs) / n) * n / (n + 20)) if n else 0.0
    total = sum(scores.values())
    return {k: round(v / total, 3) if total else 0.0 for k, v in scores.items()}


# --- ciclo ------------------------------------------------------------------


def revalidate(db: Session, history: History) -> list[str]:
    """Re-examina las evolucionadas vivas con datos frescos y las reglas actuales."""
    notes = []
    for row in db.scalars(select(BrainGenome).where(BrainGenome.status == "live", BrainGenome.origin != "fija")):
        params = {k: v for k, v in row.params.items() if k != "symbols"}
        result = examine(Evolved(row.name, row.family, params), history)
        ok, why = verdict(result, 3 if params["tf"] == "1d" else 6)
        symbols = winning_symbols(result)
        if not ok or not symbols:
            row.status, row.note = "retirada", f"no pasó el re-examen: {why if not ok else 'ningún par gana'}"
            notes.append(f"Retirada {row.name}: {row.note}.")
        elif sorted(symbols) != sorted(row.params.get("symbols") or []):
            row.params = {**params, "symbols": symbols}
            notes.append(f"{row.name} ahora opera solo en {', '.join(symbols)}.")
        row.updated_at = utc_now()
    db.commit()
    return notes


def candidates(db: Session, rng: random.Random, ideas: list[dict]) -> list[tuple[str, dict, str]]:
    seen = {g.name for g in db.scalars(select(BrainGenome))}
    out: list[tuple[str, dict, str]] = []

    def add(family: str, params: dict | None, origin: str) -> None:
        if params is None:
            return
        name = genome_name(family, params)
        if name not in seen:
            seen.add(name)
            out.append((family, params, origin))

    for idea in ideas:
        add(idea.get("familia", ""), clip(idea.get("familia", ""), idea.get("params") or {}), "gemini")
    winners = db.scalars(select(BrainGenome).where(BrainGenome.status == "live", BrainGenome.origin != "fija")).all()
    for row in winners:
        add(row.family, mutate(rng, row.family, row.params), "mutación")
    odds = family_odds(db)
    families, weights = list(odds), list(odds.values())
    while len(out) < CANDIDATES_PER_RUN:
        family = rng.choices(families, weights)[0]
        add(family, random_genome(rng, family), "azar")
    return out[: CANDIDATES_PER_RUN + len(ideas)]


def evolve_once(db: Session, history: History, ideas: list[dict] | None = None,
                live_trades: list[Trade] | None = None, now: datetime | None = None,
                rng: random.Random | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    rng = rng or random.Random()
    notes = review_live(db, live_trades or []) + revalidate(db, history)
    live_count = len(db.scalars(select(BrainGenome).where(BrainGenome.status == "live", BrainGenome.origin != "fija")).all())
    tested, promoted = 0, []
    per_kind: dict[tuple[str, str], int] = {}
    for r in db.scalars(select(BrainGenome).where(BrainGenome.status == "live", BrainGenome.origin != "fija")):
        per_kind[(r.family, r.params.get("tf", ""))] = per_kind.get((r.family, r.params.get("tf", "")), 0) + 1
    exams = {
        r.name: (r.family, r.metrics["examen"]["out"]["trades"], r.metrics["examen"]["out"]["net_pnl"])
        for r in db.scalars(select(BrainGenome).where(BrainGenome.status == "live"))
        if (r.metrics or {}).get("examen")
    }
    for family, params, origin in candidates(db, rng, ideas or []):
        name = genome_name(family, params)
        strategy = Evolved(name, family, params)
        result = examine(strategy, history)
        ok, why = verdict(result, 3 if params["tf"] == "1d" else 6)  # diario: pocas señales por diseño
        twin = next((n for n, out in exams.items() if out == (family, result["out"]["trades"], result["out"]["net_pnl"])), None)
        if ok and twin:
            ok, why = False, f"clon de {twin} (mismo resultado)"
        if ok and per_kind.get((family, params["tf"]), 0) >= MAX_PER_KIND:
            ok, why = False, f"ya hay {MAX_PER_KIND} {family} {params['tf']} vivas (no diversifica)"
        if ok and not robust(family, params, history, rng):
            ok, why = False, why + ", pero sus vecinos pierden (frágil)"
        symbols = winning_symbols(result) if ok else []
        if ok and not symbols:
            ok, why = False, why + ", pero ningún par gana en entrenamiento y examen a la vez"
        if ok:
            params = {**params, "symbols": symbols}
            why += f" · opera solo en {', '.join(s.replace('USDT', '') for s in symbols)}"
        status = "live" if ok and live_count < MAX_LIVE else "rechazada"
        if ok and status == "rechazada":
            why += " (aprobó, pero no hay cupo en el torneo)"
        db.add(BrainGenome(name=name, family=family, params=params, origin=origin, status=status,
                           metrics={"examen": {k: {m: result[k][m] for m in ("trades", "net_pnl", "profit_factor", "expectancy_r", "max_dd_pct")} for k in ("in", "out")}},
                           note=why))
        tested += 1
        if ok:
            exams[name] = (family, result["out"]["trades"], result["out"]["net_pnl"])
        if status == "live":
            live_count += 1
            per_kind[(family, params["tf"])] = per_kind.get((family, params["tf"]), 0) + 1
            promoted.append(name)
            notes.append(f"Aprobada ({origin}) {strategy.label}: {why}. Entra al torneo en vivo con {EVOLVED_CAPITAL} USD.")
        elif origin == "gemini":
            notes.append(f"Idea de Gemini rechazada, {strategy.label}: {why}.")
    db.commit()
    odds = family_odds(db)
    notes.append(
        f"Probé {tested} estrategias nuevas, aprobaron {len(promoted)}. "
        "Probabilidad de aprobar por familia: " + ", ".join(f"{k} {v:.0%}" for k, v in odds.items()) + "."
    )
    remember(notes, now)
    return {"tested": tested, "promoted": promoted, "notes": notes}


def live_strategies(db: Session) -> tuple[list[Strategy], set[str]]:
    """Lo que el torneo en vivo debe correr: evolucionadas vivas y nombres en banca."""
    rows = db.scalars(select(BrainGenome)).all()
    evolved = [Evolved(r.name, r.family, r.params) for r in rows if r.status == "live" and r.origin != "fija"]
    benched = {r.name for r in rows if r.status in ("banca", "retirada")}
    benched |= {p for r in rows for p in (r.metrics or {}).get("banca_pares", [])}
    return evolved, benched


def ask_ideas(context: dict[str, Any]) -> tuple[list[dict], str, dict | None]:
    """Gemini: lectura del mercado + hasta 3 estrategias concretas dentro de las familias."""
    if not settings.gemini_api_key.strip():
        return [], "sin GEMINI_API_KEY", None
    from app.services.gemini_client import GeminiClient

    spec = {f: {k: (v if k == "tf" else [v[0], v[1]]) for k, v in s.items()} for f, s in FAMILIES.items()}
    prompt = (
        "Eres un trader cuantitativo senior que dirige un torneo de estrategias en paper "
        "(Binance spot, comisión 0,10 %/lado, solo largos para las nuevas). Aprende de la memoria: no "
        "repitas ideas rechazadas y explica qué patrón ves. Responde SOLO JSON con claves: "
        '"resumen" (máx. 6 frases), "alertas" (lista), "hipotesis" (lista de {"titulo","razon","como_probar"}), '
        '"estrategias" (máx. 3, cada una {"familia","params","por_que"} usando EXACTAMENTE estas familias '
        f"y rangos: {json.dumps(spec)}).\n\nMEMORIA:\n{recent_memory()}\n\nDATOS:\n"
        + json.dumps(context, ensure_ascii=False, default=str)[:12000]
    )
    try:
        reply = GeminiClient(timeout_seconds=60).generate(prompt, request_id=f"brain-{utc_now():%Y%m%d%H%M}")
        answer = json.loads(reply.text)
    except Exception as exc:  # noqa: BLE001 — el cerebro sigue sin LLM
        return [], f"Gemini no respondió ({type(exc).__name__}: {str(exc)[:120]})", None
    ideas = [x for x in answer.get("estrategias") or [] if isinstance(x, dict)]
    return ideas[:3], "", answer

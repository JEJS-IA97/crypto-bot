"""Apuestas deportivas en paper: ¿gana el precio o gana lo "seguro"?

Research (23.223 partidos, 2019–2026): los favoritos "seguros" aciertan mucho pero pierden
(margen de la casa), el parley de favoritos pierde más (−6,8 %) y apostar cuando una casa
paga más que la cuota justa de una referencia afilada ganó (+1,8 %). Aquí se prueban las
tres en vivo, 1 unidad por apuesta, y se mide ROI y CLV (cuánto mejor fue tu cuota que la
de cierre: la señal de ventaja que no depende de la suerte).

Fuentes:
- Fútbol europeo: football-data.co.uk (fixtures.csv y resultados por temporada, gratis).
  Referencia "justa": Pinnacle (PS) si está, si no Betfair Exchange (BFE), si no la media.
- Fútbol de América, NBA y MLB: The Odds API (ODDS_API_KEY, plan gratis) con Pinnacle.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import DateTime, Integer, Numeric, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app import database
from app.config import settings
from app.database import Base
from app.models import utc_now

logger = logging.getLogger(__name__)

FD = "https://www.football-data.co.uk"
ODDS = "https://api.the-odds-api.com/v4"
ODDS_SPORTS = ("soccer_brazil_campeonato", "soccer_argentina_primera_division", "basketball_nba")
# Plan gratis: 500 créditos/mes. Buscar cada 12 h (3 créditos) y liquidar cada 24 h (≤6) ≈ 360/mes.
ODDS_SCAN_EVERY, ODDS_SETTLE_EVERY = timedelta(hours=12), timedelta(hours=24)
_last_call: dict[str, datetime] = {}
MIN_EV, MAX_EV, MAX_VALUE_ODDS = 0.02, 0.10, 3.0  # >10 % suele ser un error de cuota
SAFE_ODDS = 1.30
STAKE = Decimal("1")
STRATEGIES = {
    "valor": "Valor: la mejor cuota paga ≥2 % más que la cuota justa (cuota ≤3)",
    "favorito_130": "Control: favorito 'seguro' (cuota ≤1,30) a cuota media",
    "parley3_130": "Control: parley de 3 favoritos ≤1,30",
}


class BetPick(Base):
    __tablename__ = "bet_picks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy: Mapped[str] = mapped_column(String(20), index=True)
    sport: Mapped[str] = mapped_column(String(40))
    league: Mapped[str] = mapped_column(String(40))
    match: Mapped[str] = mapped_column(String(160), index=True)  # clave "liga|fecha|local|visitante" (o varias, si es parley)
    selection: Mapped[str] = mapped_column(String(60))  # H / D / A, o nombre del equipo
    kickoff: Mapped[datetime] = mapped_column(DateTime)
    odds: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    fair_prob: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    stake: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=STAKE)
    status: Mapped[str] = mapped_column(String(10), default="abierta", index=True)  # abierta | ganada | perdida | nula
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    clv_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


# --- matemáticas --------------------------------------------------------------------------

def fair(odds: list[float]) -> list[float] | None:
    """Probabilidades sin el margen de la casa (normalización proporcional)."""
    if not odds or any(not o or o <= 1 for o in odds):
        return None
    inv = [1 / o for o in odds]
    total = sum(inv)
    return [x / total for x in inv]


def _num(row: dict, key: str) -> float | None:
    try:
        value = float(row.get(key) or "")
        return value if value > 1 else None
    except ValueError:
        return None


def reference(row: dict, closing: bool = False) -> list[float] | None:
    c = "C" if closing else ""
    for prefix in ("PS", "BFE", "Avg"):
        probs = fair([_num(row, f"{prefix}{c}{x}") for x in "HDA"])
        if probs:
            return probs
    return None


def season_code(day: datetime) -> str:
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def kickoff(row: dict) -> datetime | None:
    try:
        d = datetime.strptime(f"{row['Date']} {row.get('Time') or '15:00'}", "%d/%m/%Y %H:%M")
    except (KeyError, ValueError):
        return None
    # football-data publica la hora del Reino Unido (con horario de verano) → UTC sin zona
    return d.replace(tzinfo=ZoneInfo("Europe/London")).astimezone(timezone.utc).replace(tzinfo=None)


def key(row: dict) -> str:
    return f"{row['Div']}|{row['Date']}|{row['HomeTeam']}|{row['AwayTeam']}"


# --- elegir apuestas (funciones puras, testeables) ----------------------------------------

def value_picks(row: dict) -> list[dict]:
    probs = reference(row)
    if probs is None:
        return []
    out = []
    for i, side in enumerate("HDA"):
        best = _num(row, f"Max{side}")
        if best and best <= MAX_VALUE_ODDS and MIN_EV < best * probs[i] - 1 < MAX_EV:
            out.append({"strategy": "valor", "selection": side, "odds": best, "fair_prob": probs[i]})
    return out


def favourite(row: dict) -> dict | None:
    home, away = _num(row, "AvgH"), _num(row, "AvgA")
    if not home or not away:
        return None
    side, odds = ("H", home) if home < away else ("A", away)
    return {"strategy": "favorito_130", "selection": side, "odds": odds} if odds <= SAFE_ODDS else None


def parlays(favs: list[tuple[str, dict]]) -> list[dict]:
    """Grupos de 3 favoritos ≤1,30 (por orden de inicio) → un parley por grupo."""
    favs = sorted(favs, key=lambda x: x[0])
    out = []
    for i in range(0, len(favs) - 2, 3):
        group = favs[i:i + 3]
        odds = 1.0
        for _, f in group:
            odds *= f["odds"]
        out.append({"strategy": "parley3_130", "match": " + ".join(k for k, _ in group),
                    "selection": ",".join(f["selection"] for _, f in group), "odds": round(odds, 3)})
    return out


# --- fútbol europeo (football-data) -------------------------------------------------------

def _csv(client, path: str) -> list[dict]:
    response = client.get(FD + path, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    if response.status_code != 200:
        logger.warning("bets: %s -> HTTP %s", path, response.status_code)
        return []
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig", "replace"))))


def scan_europe(db: Session, client=None, now: datetime | None = None) -> int:
    client = client or httpx
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    known = {(p.strategy, p.match, p.selection) for p in db.scalars(select(BetPick).where(BetPick.status == "abierta"))}
    new, favs = 0, []
    for row in _csv(client, "/fixtures.csv"):
        start = kickoff(row)
        if start is None or not (now < start < now + timedelta(hours=48)):
            continue
        picks = value_picks(row)
        fav = favourite(row)
        if fav:
            picks.append(fav)
            favs.append((key(row), fav))
        for p in picks:
            if (p["strategy"], key(row), p["selection"]) in known:
                continue
            db.add(BetPick(strategy=p["strategy"], sport="fútbol", league=row["Div"], match=key(row), selection=p["selection"],
                           kickoff=start, odds=Decimal(str(p["odds"])),
                           fair_prob=Decimal(str(round(p["fair_prob"], 4))) if p.get("fair_prob") else None))
            new += 1
    already = {m for (s, m, _) in known if s == "parley3_130"}
    taken = {part for m in already for part in m.split(" + ")}
    for p in parlays([f for f in favs if f[0] not in taken]):
        db.add(BetPick(strategy=p["strategy"], sport="fútbol", league="varias", match=p["match"][:160], selection=p["selection"],
                       kickoff=now + timedelta(hours=48), odds=Decimal(str(p["odds"]))))
        new += 1
    db.commit()
    return new


def settle_europe(db: Session, client=None, now: datetime | None = None) -> int:
    client = client or httpx
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    results: dict[str, dict] = {}
    loaded: set[tuple[str, str]] = set()

    def lookup(match_key: str) -> dict | None:
        div, date, *_ = match_key.split("|")
        season = season_code(datetime.strptime(date, "%d/%m/%Y"))
        if (season, div) not in loaded:
            loaded.add((season, div))
            for r in _csv(client, f"/mmz4281/{season}/{div}.csv"):
                if r.get("FTR"):
                    results[key(r)] = r
        return results.get(match_key)

    done = 0
    for pick in db.scalars(select(BetPick).where(BetPick.status == "abierta", BetPick.sport == "fútbol")):
        legs = pick.match.split(" + ")
        sides = pick.selection.split(",") if pick.strategy == "parley3_130" else [pick.selection]
        rows = [lookup(k) for k in legs]
        if any(r is None for r in rows):
            if pick.kickoff < now - timedelta(days=10):
                pick.status, pick.pnl = "nula", Decimal(0)  # sin resultado publicado: se anula
                done += 1
            continue
        won = all(r["FTR"] == s for r, s in zip(rows, sides))
        pick.status = "ganada" if won else "perdida"
        pick.pnl = (pick.odds - 1) * pick.stake if won else -pick.stake
        if len(rows) == 1:
            close = reference(rows[0], closing=True)
            if close:
                pick.clv_pct = Decimal(str(round((float(pick.odds) * close["HDA".index(sides[0])] - 1) * 100, 2)))
        done += 1
    db.commit()
    return done


# --- América, NBA y MLB (The Odds API, opcional) ------------------------------------------

def _due(name: str, every: timedelta, now: datetime) -> bool:
    if now - _last_call.get(name, datetime.min) < every:
        return False
    _last_call[name] = now
    return True


def scan_odds_api(db: Session, client=None, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if not settings.odds_api_key or not _due("scan", ODDS_SCAN_EVERY, now):
        return 0
    client = client or httpx
    known = {(p.strategy, p.match, p.selection) for p in db.scalars(select(BetPick).where(BetPick.status == "abierta"))}
    new = 0
    for sport in ODDS_SPORTS:
        events = client.get(f"{ODDS}/sports/{sport}/odds", timeout=30, params={
            "apiKey": settings.odds_api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"}).json()
        if not isinstance(events, list):
            logger.warning("bets: odds api %s: %s", sport, events)
            continue
        for ev in events:
            start = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
            if not (now < start < now + timedelta(hours=48)):
                continue
            books = {b["key"]: {o["name"]: o["price"] for o in b["markets"][0]["outcomes"]} for b in ev.get("bookmakers", []) if b.get("markets")}
            ref = books.get("pinnacle") or books.get("betfair_ex_eu")
            if not ref:
                continue
            names = list(ref)
            probs = fair([ref[n] for n in names])
            match = f"{sport}|{start:%Y-%m-%d}|{ev['home_team']}|{ev['away_team']}|{ev['id']}"[:160]
            for name, p in zip(names, probs or []):
                best = max((b.get(name, 0) for k, b in books.items() if k not in ("pinnacle", "betfair_ex_eu")), default=0)
                if best and best <= MAX_VALUE_ODDS and MIN_EV < best * p - 1 < MAX_EV and ("valor", match, name) not in known:
                    db.add(BetPick(strategy="valor", sport=sport.split("_")[0], league=sport, match=match, selection=name[:60],
                                   kickoff=start, odds=Decimal(str(best)), fair_prob=Decimal(str(round(p, 4)))))
                    new += 1
    db.commit()
    return new


def settle_odds_api(db: Session, client=None, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if not settings.odds_api_key or not _due("settle", ODDS_SETTLE_EVERY, now):
        return 0
    client = client or httpx
    open_picks = [p for p in db.scalars(select(BetPick).where(BetPick.status == "abierta", BetPick.sport != "fútbol"))]
    done = 0
    for sport in {p.league for p in open_picks}:
        scores = client.get(f"{ODDS}/sports/{sport}/scores", timeout=30,
                            params={"apiKey": settings.odds_api_key, "daysFrom": 3}).json()
        finished = {s["id"]: s for s in scores if isinstance(s, dict) and s.get("completed")}
        for pick in (p for p in open_picks if p.league == sport):
            game = finished.get(pick.match.rsplit("|", 1)[-1])
            if not game or not game.get("scores"):
                continue
            pts = {s["name"]: float(s["score"]) for s in game["scores"]}
            top = max(pts.values())
            winners = [n for n, v in pts.items() if v == top]
            winner = winners[0] if len(winners) == 1 else "Draw"
            won = pick.selection == winner
            pick.status = "ganada" if won else "perdida"
            pick.pnl = (pick.odds - 1) * pick.stake if won else -pick.stake
            done += 1
    db.commit()
    return done


# --- resumen y bucle ------------------------------------------------------------------------

def summary(db: Session) -> list[dict]:
    rows = []
    for name, label in STRATEGIES.items():
        picks = db.scalars(select(BetPick).where(BetPick.strategy == name)).all()
        settled = [p for p in picks if p.status in ("ganada", "perdida")]
        pnl = sum((p.pnl for p in settled), Decimal(0))
        clvs = [float(p.clv_pct) for p in settled if p.clv_pct is not None]
        rows.append({
            "strategy": name, "label": label, "abiertas": sum(1 for p in picks if p.status == "abierta"),
            "liquidadas": len(settled), "ganadas": sum(1 for p in settled if p.status == "ganada"),
            "acierto": round(sum(1 for p in settled if p.status == "ganada") / len(settled) * 100, 1) if settled else None,
            "pnl": float(pnl), "roi": round(float(pnl) / len(settled) * 100, 2) if settled else None,
            "clv_medio": round(sum(clvs) / len(clvs), 2) if clvs else None,
            "cuota_media": round(sum(float(p.odds) for p in settled) / len(settled), 2) if settled else None,
        })
    return rows


def run_once(session_factory=None) -> dict:
    with (session_factory or database.SessionLocal)() as db:
        out = {}
        for name, fn in (("europa", scan_europe), ("america", scan_odds_api)):
            try:
                out[f"nuevas_{name}"] = fn(db)
            except Exception as exc:  # noqa: BLE001 — una fuente caída no frena a la otra
                db.rollback()
                logger.warning("bets: scan %s failed (%s)", name, exc)
        for name, fn in (("europa", settle_europe), ("america", settle_odds_api)):
            try:
                out[f"liquidadas_{name}"] = fn(db)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.warning("bets: settle %s failed (%s)", name, exc)
        return out


async def bets_loop(stop_event: asyncio.Event) -> None:
    """Cada 6 h: busca apuestas de las próximas 48 h y liquida las terminadas."""
    while not stop_event.is_set():
        try:
            logger.info("bets: %s", await asyncio.to_thread(run_once))
        except Exception as exc:  # noqa: BLE001
            logger.warning("bets: cycle failed (%s)", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=6 * 3600)
        except TimeoutError:
            pass

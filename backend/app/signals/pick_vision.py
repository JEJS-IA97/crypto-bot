"""Pronósticos que llegan en IMAGEN (Telegram de tipsters como La Fiebre del Pick): Gemini los lee
y el bot los liquida él mismo con los resultados de football-data, sin creerle al canal.

- extract_picks: imagen (+ texto) → lista de picks {local, visitante, mercado, linea, lado, cuota, fecha}.
- settle_pick: compara un pick con la fila del resultado (goles, ambos marcan, 1X2, doble oportunidad).
- match_row: encuentra el partido en los CSV por nombres parecidos y fecha ±2 días.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from app.config import settings

logger = logging.getLogger(__name__)

DAILY_LIMIT = 40  # imágenes por día (cuota gratis de Gemini)
_used: dict[str, int] = {}

PROMPT = (
    "Eres un analista de apuestas. La imagen (y el texto) es un pronóstico deportivo de un tipster. "
    "Extrae CADA apuesta de fútbol que recomienda. Responde SOLO JSON: "
    '{"picks": [{"local": str, "visitante": str, "fecha": "YYYY-MM-DD" o null, '
    '"mercado": uno de ["1x2","doble_oportunidad","goles","ambos_marcan","corners","tarjetas","otro"], '
    '"lado": para 1x2 "1"/"X"/"2", doble oportunidad "1X"/"X2"/"12", goles/corners/tarjetas "mas"/"menos", '
    'ambos_marcan "si"/"no", "linea": número o null (p. ej. 2.5), "cuota": número o null, "texto": str}]}. '
    "Si no hay pronósticos de fútbol, devuelve {\"picks\": []}. No inventes partidos ni cuotas."
)


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|cd|ud|club|de|the|afc)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def similar(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def extract_picks(image: bytes, mime: str, caption: str = "", today: str | None = None) -> list[dict]:
    """Gemini lee la imagen; respeta un tope diario de imágenes."""
    if not settings.gemini_api_key.strip():
        return []
    day = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _used.get(day, 0) >= DAILY_LIMIT:
        return []
    _used[day] = _used.get(day, 0) + 1
    from app.brain.evolve import flash_models
    from app.services.gemini_client import GeminiClient

    models = [settings.gemini_model] + [m.strip() for m in settings.gemini_fallback_models.split(",") if m.strip()] + flash_models()
    prompt = PROMPT + f"\nHoy es {day}. Texto que acompaña la imagen: {caption[:800]}"
    for model in dict.fromkeys(models):
        try:
            reply = GeminiClient(model=model, timeout_seconds=60, max_retries=1).generate(
                prompt, request_id=f"pick-{day}", image=(image, mime))
            picks = json.loads(reply.text).get("picks") or []
            return [p for p in picks if isinstance(p, dict) and p.get("local") and p.get("visitante")][:20]
        except Exception as exc:  # noqa: BLE001 — siguiente modelo
            logger.info("pick_vision: %s failed (%s)", model, type(exc).__name__)
    return []


def match_row(pick: dict, rows: list[dict]) -> dict | None:
    """Fila de football-data del mismo partido (nombres parecidos, fecha ±2 días si la hay)."""
    when = None
    if pick.get("fecha"):
        try:
            when = datetime.strptime(pick["fecha"], "%Y-%m-%d")
        except ValueError:
            when = None
    best, score = None, 0.0
    for r in rows:
        if not r.get("FTR"):
            continue
        if when is not None:
            try:
                d = datetime.strptime(r["Date"], "%d/%m/%Y")
            except (KeyError, ValueError):
                continue
            if abs(d - when) > timedelta(days=2):
                continue
        s = min(similar(pick["local"], r.get("HomeTeam", "")), similar(pick["visitante"], r.get("AwayTeam", "")))
        if s > score:
            best, score = r, s
    return best if score >= 0.72 else None


def settle_pick(pick: dict, row: dict) -> bool | None:
    """True ganó, False perdió, None si el mercado no se puede comprobar con el CSV."""
    try:
        hg, ag = int(row["FTHG"]), int(row["FTAG"])
    except (KeyError, TypeError, ValueError):
        return None
    market, side = (pick.get("mercado") or "").lower(), str(pick.get("lado") or "").upper()
    line = pick.get("linea")
    if market == "1x2":
        return {"1": hg > ag, "X": hg == ag, "2": hg < ag}.get(side)
    if market == "doble_oportunidad":
        return {"1X": hg >= ag, "X2": hg <= ag, "12": hg != ag}.get(side)
    if market == "ambos_marcan":
        both = hg > 0 and ag > 0
        return both if side in ("SI", "SÍ") else (not both) if side == "NO" else None
    totals = {"goles": ("FTHG", "FTAG"), "corners": ("HC", "AC"), "tarjetas": ("HY", "AY", "HR", "AR")}
    if market in totals and line is not None:
        try:
            value = sum(float(row[c]) for c in totals[market])
        except (KeyError, TypeError, ValueError):
            return None
        return value > float(line) if side == "MAS" else value < float(line) if side == "MENOS" else None
    return None

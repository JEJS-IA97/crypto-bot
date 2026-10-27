"""Contexto de mercado que el bot no veía: calendario macro, Fear & Greed y datos de futuros.

- Calendario: FOMC (Fed) y CPI de EE. UU. La cuenta principal no abre posiciones desde 12 h
  antes hasta 6 h después (la volatilidad de esas horas no la modela ninguna estrategia).
- Cada hora guarda en data/context.jsonl: Fear & Greed (alternative.me), funding, open
  interest y ratio largo/corto de cuentas (futuros de Binance, públicos). Solo se registran
  como contexto para que el cerebro pruebe hipótesis con ellos; no disparan operaciones.
Fuentes de fechas: federalreserve.gov vía fedratecalc.com y bls.gov (revisadas el 27-oct-2026).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

UTC = timezone.utc
# Hora UTC de cada publicación (FOMC 14:00 ET, CPI 08:30 ET, ajustado por horario de verano).
MACRO_EVENTS: list[tuple[datetime, str]] = [
    (datetime(2026, 10, 28, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2026, 11, 10, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2026, 12, 9, 19, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2026, 12, 10, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 1, 13, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 1, 27, 19, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 2, 11, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 3, 10, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 3, 17, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 4, 13, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 4, 28, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 5, 12, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 6, 9, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 6, 10, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 7, 14, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 7, 28, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 8, 11, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 9, 14, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 9, 15, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 10, 14, 12, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 10, 27, 18, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 11, 10, 13, 30, tzinfo=UTC), "CPI EE. UU."),
    (datetime(2027, 12, 8, 19, 0, tzinfo=UTC), "FOMC (Fed)"),
    (datetime(2027, 12, 10, 13, 30, tzinfo=UTC), "CPI EE. UU."),
]
BEFORE, AFTER = timedelta(hours=12), timedelta(hours=6)
OUT = Path("data/context.jsonl")
FAPI = "https://fapi.binance.com"
latest: dict = {}


def macro_blackout(now: datetime | None = None) -> str | None:
    """Nombre del evento si estamos dentro de su ventana de no-entrada."""
    now = now or datetime.now(UTC)
    for when, name in MACRO_EVENTS:
        if when - BEFORE <= now <= when + AFTER:
            return f"{name} {when:%d-%m %H:%M} UTC"
    return None


def next_event(now: datetime | None = None) -> dict | None:
    now = now or datetime.now(UTC)
    for when, name in MACRO_EVENTS:
        if when + AFTER >= now:
            return {"evento": name, "utc": when.isoformat(), "horas": round((when - now).total_seconds() / 3600, 1)}
    return None


def snapshot(client=None) -> dict:
    """Una foto del contexto; cada fuente que falla queda como 'no disponible'."""
    client = client or httpx
    out: dict = {"ts": datetime.now(UTC).isoformat()}
    try:
        fng = client.get("https://api.alternative.me/fng/", params={"limit": 1}, timeout=15).json()["data"][0]
        out["fear_greed"] = {"valor": int(fng["value"]), "texto": fng["value_classification"]}
    except Exception as exc:  # noqa: BLE001
        out["fear_greed"] = f"no disponible ({type(exc).__name__})"
    for sym in ("BTCUSDT", "ETHUSDT"):
        try:
            prem = client.get(f"{FAPI}/fapi/v1/premiumIndex", params={"symbol": sym}, timeout=15).json()
            oi = client.get(f"{FAPI}/fapi/v1/openInterest", params={"symbol": sym}, timeout=15).json()
            ls = client.get(f"{FAPI}/futures/data/globalLongShortAccountRatio",
                            params={"symbol": sym, "period": "1h", "limit": 1}, timeout=15).json()
            out[sym] = {
                "funding_pct": round(float(prem["lastFundingRate"]) * 100, 4),
                "open_interest": float(oi["openInterest"]),
                "largos_vs_cortos": float(ls[0]["longShortRatio"]) if ls else None,
            }
        except Exception as exc:  # noqa: BLE001
            out[sym] = f"no disponible ({type(exc).__name__})"
    return out


def run_once(client=None) -> dict:
    snap = snapshot(client)
    latest.clear()
    latest.update(snap)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    return snap


async def context_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(run_once)
        except Exception as exc:  # noqa: BLE001
            logger.warning("context: snapshot failed (%s)", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except TimeoutError:
            pass

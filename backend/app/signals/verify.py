"""Comprueba las señales binarias de divisas contra el precio real (Yahoo Finance, velas de 1 min).

Solo pares de mercado real: las OTC usan un precio que genera el propio broker y no se
pueden comprobar. Se evalúa la ENTRADA original, sin gales (la martingala esconde pérdidas).
Resultado en `parsed["verificada"]`: gana / pierde / empate / sin datos.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from app import database

logger = logging.getLogger(__name__)

CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SPECIAL = {"XAU/USD": "GC=F", "XAG/USD": "SI=F"}
PAYOUT = 0.85  # pago típico de Quotex/Pocket en divisas reales: break-even ≈ 54 % de acierto


def yahoo_symbol(asset: str) -> str:
    return SPECIAL.get(asset, asset.replace("/", "") + "=X")


def entry_utc(parsed: dict, sent_at: datetime) -> datetime:
    """Hora de la señal (en su huso) → UTC, el mismo día del mensaje o el siguiente."""
    hour, minute = (int(x) for x in parsed["time"].split(":"))
    offset = timedelta(hours=parsed.get("utc_offset", -3))
    local_sent = sent_at + offset
    entry = local_sent.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if entry < local_sent - timedelta(minutes=30):
        entry += timedelta(days=1)
    return (entry - offset).replace(tzinfo=timezone.utc)


def judge(direction: str, entry_price: float, exit_price: float) -> str:
    if exit_price == entry_price:
        return "empate"
    won = exit_price > entry_price if direction == "UP" else exit_price < entry_price
    return "gana" if won else "pierde"


def fetch_minutes(asset: str, start: datetime, end: datetime, client=None) -> dict[int, tuple[float, float]]:
    """{epoch_minuto: (open, close)} entre start y end."""
    client = client or httpx
    response = client.get(
        CHART.format(symbol=yahoo_symbol(asset)),
        params={"interval": "1m", "period1": int(start.timestamp()), "period2": int(end.timestamp())},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = (response.json().get("chart", {}).get("result") or [None])[0] or {}
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    out = {}
    for ts, o, c in zip(result.get("timestamp") or [], quote.get("open") or [], quote.get("close") or []):
        if o is not None and c is not None:
            out[ts // 60 * 60] = (o, c)
    return out


def verify(parsed: dict, sent_at: datetime, now: datetime, client=None) -> dict | None:
    """Devuelve el veredicto o None si aún no venció la expiración."""
    entry = entry_utc(parsed, sent_at)
    minutes = parsed.get("expiry_min") or 5
    exit_at = entry + timedelta(minutes=minutes)
    if now < exit_at + timedelta(minutes=3):
        return None
    if now - entry > timedelta(days=6):
        return {"result": "sin datos", "why": "demasiado vieja para velas de 1 min"}
    candles = fetch_minutes(parsed["asset"], entry - timedelta(minutes=2), exit_at + timedelta(minutes=2), client)
    first = candles.get(int(entry.timestamp()))
    last = candles.get(int((exit_at - timedelta(minutes=1)).timestamp()))
    if not (first and last):
        return {"result": "sin datos", "why": "mercado cerrado o sin velas"}
    return {"result": judge(parsed["direction"], first[0], last[1]), "entry_price": first[0],
            "exit_price": last[1], "entry_utc": entry.isoformat()}


def verify_pending(session_factory=None, now: datetime | None = None, client=None) -> int:
    """Revisa las señales binarias de divisas reales que aún no tienen veredicto."""
    from app.signals.telegram import TelegramSignal

    now = now or datetime.now(timezone.utc)
    done = 0
    with (session_factory or database.SessionLocal)() as db:
        for row in db.scalars(select(TelegramSignal)):
            parsed = row.parsed or {}
            if parsed.get("kind") != "binaria" or parsed.get("otc") or "verificada" in parsed:
                continue
            try:
                verdict = verify(parsed, row.created_at.replace(tzinfo=timezone.utc), now, client)
            except Exception as exc:  # noqa: BLE001 — Yahoo caído: se reintenta en el próximo ciclo
                logger.warning("verify: %s failed (%s)", parsed.get("asset"), exc)
                continue
            if verdict is not None:
                row.parsed = {**parsed, "verificada": verdict}
                done += 1
        db.commit()
    return done


def channel_score(signals: list[dict]) -> dict:
    """Acierto comprobado y resultado con 1 USD fijo por señal (sin gales)."""
    wins = sum(1 for s in signals if s.get("result") == "gana")
    losses = sum(1 for s in signals if s.get("result") == "pierde")
    n = wins + losses
    return {
        "comprobadas": n,
        "ganadas_reales": wins,
        "perdidas_reales": losses,
        "acierto_real": round(wins / n * 100, 1) if n else None,
        "resultado_1usd": round(wins * PAYOUT - losses, 2),
    }

"""Señales de tus grupos de Telegram → cuentas virtuales del torneo.

Cada chat es un "trader" más: sus señales se operan en paper (100 USD, mismas
comisiones que el resto) y el torneo mide si ese grupo de verdad gana. Nada de
esto toca dinero real.

Lee con tu cuenta de usuario (Telethon), no con un bot: un bot no puede leer
grupos ajenos. La sesión se crea una vez con `python telegram_login.py`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app import database
from app.config import settings
from app.database import Base
from app.lab import live, store
from app.lab.strategies import Strategy
from app.models import utc_now
from app.signals.binary import describe, parse_binary

logger = logging.getLogger(__name__)

SESSION_PATH = Path("data/telegram")  # telethon añade .session
CAPITAL = Decimal("100")

_NUM = r"(\d[\d,]*\.?\d*)"
PAIR = re.compile(r"\b([A-Z0-9]{2,10}?)\s*[/-]?\s*USDT\b")
TAG = re.compile(r"[#$]([A-Z0-9]{2,10})\b")
LONG = re.compile(r"\b(LONG|BUY|COMPRA|COMPRAR|ALCISTA|BULLISH)\b", re.I)
SHORT = re.compile(r"\b(SHORT|SELL|VENTA|VENDER|BAJISTA|BEARISH)\b", re.I)
ENTRY = re.compile(r"\b(?:ENTRY|ENTRADA|ENTRAR|BUY ZONE|ZONA)\b[^\d]{0,15}" + _NUM, re.I)
STOP = re.compile(r"\b(?:SL|STOP[\s-]?LOSS|STOP|PARAR)\b[^\d]{0,15}" + _NUM, re.I)
TP = re.compile(r"\b(?:TP\s?\d?|TAKE[\s-]?PROFIT|TARGET|OBJETIVO)\b[^\d]{0,15}" + _NUM, re.I)


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def parse_signal(text: str) -> dict | None:
    """Mensaje → {symbol, side, entry, stop, take_profit} o None si no es una señal."""
    if not text:
        return None
    upper = text.upper()
    side = "LONG" if LONG.search(upper) else "SHORT" if SHORT.search(upper) else None
    stop = STOP.search(upper)
    if side is None or stop is None:
        return None  # sin stop no se copia: es la regla #1 de riesgo
    match = PAIR.search(upper) or TAG.search(upper)  # par explícito (BTCUSDT, BTC/USDT) o #BTC / $BTC
    if match is None or match.group(1).isdigit():
        return None
    symbol = match.group(1)
    entry = ENTRY.search(upper)
    tp = TP.search(upper)
    return {
        "symbol": f"{symbol}USDT",
        "side": side,
        "entry": _num(entry.group(1)) if entry else None,
        "stop": _num(stop.group(1)),
        "take_profit": _num(tp.group(1)) if tp else None,
    }


class TelegramSignal(Base):
    __tablename__ = "telegram_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_title: Mapped[str] = mapped_column(String(120))
    message_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    outcome: Mapped[str] = mapped_column(String(60))  # abierta | no es señal | par no seguido | …
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class TelegramSource(Strategy):
    """Cuenta del torneo para un chat: no genera señales sola, solo recibe las del grupo."""

    timeframe = "1d"
    warmup = 0
    max_hold = 14  # días: una señal que no tocó stop ni objetivo en 2 semanas se cierra

    def __init__(self, chat_id: int, title: str) -> None:
        self.name = f"tg_{abs(chat_id)}"[:60]
        self.label = f"Telegram · {title}"[:80]
        self.description = f"Señales del chat de Telegram «{title}» operadas en paper."

    def signals(self, bars):
        return [None] * len(bars)


def apply_signal(chat_id: int, title: str, parsed: dict | None, runner=None, session_factory=None) -> str:
    """Abre la operación en la cuenta virtual del chat. Devuelve el resultado legible."""
    runner = runner or live.runner
    if parsed is None:
        return "no es señal"
    if runner is None:
        return "torneo apagado"
    symbol = parsed["symbol"]
    price = runner.prices.get(symbol)
    if price is None:
        return f"par no seguido ({symbol})"
    source = TelegramSource(chat_id, title)
    factory = session_factory or runner.session_factory
    if source.name not in {s.name for s in runner.strategies}:
        runner.strategies.append(source)
        with factory() as db:
            runner.accounts.update(store.load_accounts(db, [source.name], (CAPITAL,)))
    account = runner.accounts[(source.name, CAPITAL)]
    stop = Decimal(str(parsed["stop"]))
    tp = Decimal(str(parsed["take_profit"])) if parsed.get("take_profit") else None
    regime = runner.regimes[symbol].at(int(time.time() * 1000)) if symbol in runner.regimes else "sin datos"
    opened = account.open(symbol=symbol, side=parsed["side"], price=price, stop=stop, take_profit=tp,
                          ts=int(time.time() * 1000), regime=regime, prices=runner.prices)
    if opened is None:
        return "no abierta (stop incoherente, ya hay posición o nominal < 5 USD)"
    with factory() as db:
        store.save_open(db, account, opened)
    if hasattr(runner, "mirror"):  # la cuenta principal copia si este chat ya demostró que gana
        runner.mirror(source.name, symbol, parsed["side"], stop, tp, int(time.time() * 1000))
    return "abierta"


def classify(chat_id: int, title: str, text: str) -> tuple[dict | None, str]:
    """Cripto con stop → se opera en paper; si no, se lee como binaria/resultado/informe."""
    parsed = parse_signal(text)
    if parsed is None:
        parsed = parse_binary(text)
        return parsed, describe(parsed)
    try:
        return parsed, apply_signal(chat_id, title, parsed)
    except Exception:  # noqa: BLE001 — un mensaje raro no tumba el lector
        logger.exception("telegram: could not apply signal")
        return parsed, "error"


def reclassify(session_factory=None) -> int:
    """Relee los mensajes guardados como 'no es señal' con el parser binario."""
    from sqlalchemy import select

    changed = 0
    with (session_factory or database.SessionLocal)() as db:
        for row in db.scalars(select(TelegramSignal).where(TelegramSignal.outcome == "no es señal")):
            parsed = parse_binary(row.text)
            if parsed:
                row.parsed, row.outcome = parsed, describe(parsed)
                changed += 1
        db.commit()
    return changed


def restore_sources(runner) -> None:
    """Tras un reinicio, vuelve a registrar los chats que ya tienen cuenta."""
    from sqlalchemy import select

    with runner.session_factory() as db:
        chats = {r.chat_id: r.chat_title for r in db.scalars(select(TelegramSignal).where(TelegramSignal.outcome == "abierta"))}
    for chat_id, title in chats.items():
        source = TelegramSource(chat_id, title)
        if source.name not in {s.name for s in runner.strategies}:
            runner.strategies.append(source)
    with runner.session_factory() as db:
        runner.accounts.update(store.load_accounts(db, [TelegramSource(c, t).name for c, t in chats.items()], (CAPITAL,)))


CHATS_FILE = Path("data/telegram_chats.json")
MIN_HIT_RATE = 55.0  # binarias con pago 0.85: por debajo de ~54 % se pierde dinero


def chat_verdicts(db, trades=None) -> dict[int, str]:
    """Chats a silenciar → motivo. Se decide con resultados, no con lo que prometen."""
    from sqlalchemy import select

    from app.signals.verify import channel_score

    stats: dict[int, dict] = {}
    for chat_id, parsed in db.execute(select(TelegramSignal.chat_id, TelegramSignal.parsed)):
        s = stats.setdefault(chat_id, {"msgs": 0, "signals": 0, "otc": 0, "verified": []})
        s["msgs"] += 1
        parsed = parsed or {}
        if parsed.get("kind") == "binaria" or ("symbol" in parsed and "stop" in parsed):
            s["signals"] += 1
            s["otc"] += 1 if parsed.get("otc") else 0
        if parsed.get("verificada"):
            s["verified"].append(parsed["verificada"])
    pnl: dict[str, list] = {}
    for t in trades if trades is not None else store.closed_trades(db):
        if t.strategy.startswith("tg_"):
            pnl.setdefault(t.strategy, []).append(t.pnl)
    out = {}
    for chat_id, s in stats.items():
        score = channel_score(s["verified"])
        mine = pnl.get(f"tg_{abs(chat_id)}", [])
        if score["comprobadas"] >= 10 and score["acierto_real"] < MIN_HIT_RATE:
            out[chat_id] = f"acierto real {score['acierto_real']} % en {score['comprobadas']} (< {MIN_HIT_RATE:.0f} %)"
        elif len(mine) >= 5 and sum(mine) < 0:
            out[chat_id] = f"en paper pierde {float(sum(mine)):+.2f} USD en {len(mine)} trades"
        elif s["signals"] >= 20 and s["otc"] == s["signals"]:
            out[chat_id] = "solo OTC: precio inventado por el broker, imposible de comprobar"
        elif s["msgs"] >= 40 and s["signals"] == 0:
            out[chat_id] = f"{s['msgs']} mensajes y ninguna señal operable"
    return out


def _chats() -> list[str | int]:
    out: list[str | int] = []
    for raw in settings.telegram_chats.split(","):
        raw = raw.strip()
        if raw:
            out.append(int(raw) if raw.lstrip("-").isdigit() else raw)
    return out


async def telegram_loop(stop_event: asyncio.Event) -> None:
    """Escucha TODOS tus grupos y canales (los nuevos entran solos) y silencia los que no sirven."""
    if not (settings.telegram_api_id and settings.telegram_api_hash):
        logger.info("telegram: not configured (TELEGRAM_API_ID/HASH/CHATS)")
        return
    if not SESSION_PATH.with_suffix(".session").exists():
        logger.warning("telegram: no session, run python telegram_login.py once")
        return
    from telethon import TelegramClient, events

    client = TelegramClient(str(SESSION_PATH), settings.telegram_api_id, settings.telegram_api_hash)
    configured = {c for c in _chats() if isinstance(c, int)}
    muted: dict[int, str] = {}

    @client.on(events.NewMessage())
    async def on_message(event) -> None:
        if event.is_private or event.chat_id in muted:
            return
        chat = await event.get_chat()
        title = getattr(chat, "title", None) or getattr(chat, "username", None) or str(event.chat_id)
        parsed, outcome = classify(event.chat_id, title, event.raw_text or "")
        if parsed is None and event.chat_id not in configured:
            return  # de grupos nuevos solo se guarda lo que parece señal (privacidad)
        with database.SessionLocal() as db:
            db.add(TelegramSignal(chat_id=event.chat_id, chat_title=title[:120], message_id=event.id,
                                  text=(event.raw_text or "")[:4000], parsed=parsed, outcome=outcome))
            db.commit()

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("telegram: session expired, run python telegram_login.py")
            return
        if live.runner:
            restore_sources(live.runner)
        logger.info("telegram: %s stored messages reclassified", reclassify())

        async def refresh() -> None:
            with database.SessionLocal() as db:
                muted.clear()
                muted.update(await asyncio.to_thread(chat_verdicts, db))
            dialogs = []
            async for d in client.iter_dialogs():
                if d.is_group or d.is_channel:
                    dialogs.append({"id": d.id, "title": d.name, "kind": "canal" if d.is_channel and not d.is_group else "grupo",
                                    "silenciado": muted.get(d.id), "configurado": d.id in configured})
            CHATS_FILE.write_text(json.dumps(dialogs, ensure_ascii=False, indent=1), encoding="utf-8")
            logger.info("telegram: %s groups/channels, %s muted", len(dialogs), sum(1 for d in dialogs if d["silenciado"]))

        try:
            await refresh()
        except Exception:  # noqa: BLE001 — sin la lista se sigue escuchando igual
            logger.warning("telegram: refresh failed", exc_info=True)
        from app.signals import alerts
        from app.signals.verify import verify_pending

        tick = 0
        while not stop_event.is_set():
            while alerts.outbox:  # avisos de compra/venta a tus Mensajes guardados
                text = alerts.outbox.pop(0)
                try:
                    await client.send_message("me", text)
                except Exception:  # noqa: BLE001
                    logger.warning("telegram: could not send alert", exc_info=True)
            if tick and tick % 240 == 0:  # cada ~hora: grupos nuevos y quién se silencia
                try:
                    await refresh()
                except Exception:  # noqa: BLE001
                    logger.warning("telegram: refresh failed", exc_info=True)
            if tick % 20 == 0:  # cada ~5 min: veredicto de las señales de divisas reales
                checked = await asyncio.to_thread(verify_pending)
                if checked:
                    logger.info("telegram: %s binary signals verified against real prices", checked)
            tick += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15)
            except TimeoutError:
                pass
    finally:
        await client.disconnect()

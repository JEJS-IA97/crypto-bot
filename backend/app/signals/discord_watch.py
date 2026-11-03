"""Lector de Discord (solo lectura) para las comunidades que José "sigue" en su servidor.

Cómo llegan los mensajes: en cada comunidad, José pulsa "Seguir" en su canal de anuncios de
señales o pronósticos y elige su propio servidor; Discord copia ahí cada mensaje. El bot de José
(DISCORD_BOT_TOKEN) lee esos canales por la API REST cada minuto. Los textos pasan por el mismo
clasificador que Telegram; las imágenes de pronósticos las lee Gemini. No escribe nunca.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
EVERY_SECONDS = 60
_last: dict[str, str] = {}  # último id leído por canal


def _get(client, path: str, **params):
    r = client.get(API + path, params=params, headers={"Authorization": f"Bot {settings.discord_bot_token}"}, timeout=20)
    if r.status_code == 429:
        raise RuntimeError("discord rate limit")
    r.raise_for_status()
    return r.json()


def text_channels(client) -> list[dict]:
    out = []
    for guild in _get(client, "/users/@me/guilds"):
        for ch in _get(client, f"/guilds/{guild['id']}/channels"):
            if ch.get("type") in (0, 5):  # texto o anuncios
                out.append({"id": ch["id"], "name": f"{guild['name']} · #{ch['name']}"})
    return out


def new_messages(client, channel_id: str) -> list[dict]:
    """Mensajes nuevos desde la última lectura (en la primera, solo marca dónde va)."""
    if channel_id not in _last:
        msgs = _get(client, f"/channels/{channel_id}/messages", limit=1)
        _last[channel_id] = msgs[0]["id"] if msgs else "0"
        return []
    msgs = _get(client, f"/channels/{channel_id}/messages", after=_last[channel_id], limit=50)
    if msgs:
        _last[channel_id] = max(msgs, key=lambda m: int(m["id"]))["id"]
    return sorted(msgs, key=lambda m: int(m["id"]))


def store(channel: dict, msg: dict, client) -> str:
    """Clasifica y guarda un mensaje como si viniera de Telegram (mismo tablero y verificación)."""
    from app import database
    from app.signals.pick_vision import extract_picks
    from app.signals.telegram import TelegramSignal, classify

    text = msg.get("content") or ""
    for emb in msg.get("embeds") or []:  # los anuncios seguidos suelen venir como embed
        text += "\n" + " ".join(str(emb.get(k) or "") for k in ("title", "description"))
    chat_id = -int(channel["id"]) % (2**62)  # id negativo propio para no chocar con Telegram
    title = f"Discord · {channel['name']}"[:120]
    images = [a["url"] for a in msg.get("attachments") or [] if (a.get("content_type") or "").startswith("image/")]
    with database.SessionLocal() as db:
        if images:
            picks = []
            for url in images[:3]:
                try:
                    img = client.get(url, timeout=30).content
                    picks += extract_picks(img, "image/png", text)
                except Exception:  # noqa: BLE001
                    logger.warning("discord: image failed", exc_info=True)
            if picks:
                db.add(TelegramSignal(chat_id=chat_id, chat_title=title, message_id=int(msg["id"]) % (2**62), text=text[:4000],
                                      parsed={"kind": "apuesta_img", "picks": picks}, outcome=f"{len(picks)} pronósticos (imagen)"))
                db.commit()
                return "imagen"
        parsed, outcome = classify(chat_id, title, text)
        db.add(TelegramSignal(chat_id=chat_id, chat_title=title, message_id=int(msg["id"]) % (2**62), text=text[:4000],
                              parsed=parsed, outcome=outcome))
        db.commit()
        return outcome


async def discord_loop(stop_event: asyncio.Event) -> None:
    if not settings.discord_bot_token.strip():
        logger.info("discord: no DISCORD_BOT_TOKEN, skipping")
        return
    channels: list[dict] = []
    tick = 0
    while not stop_event.is_set():
        try:
            if tick % 30 == 0:  # cada 30 min re-lista canales (los nuevos "seguidos" entran solos)
                channels = await asyncio.to_thread(text_channels, httpx)
                logger.info("discord: %s channels", len(channels))
            for ch in channels:
                for msg in await asyncio.to_thread(new_messages, httpx, ch["id"]):
                    await asyncio.to_thread(store, ch, msg, httpx)
        except Exception as exc:  # noqa: BLE001
            logger.warning("discord: poll failed (%s)", exc)
        tick += 1
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=EVERY_SECONDS)
        except TimeoutError:
            pass

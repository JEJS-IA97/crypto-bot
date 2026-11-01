"""Segunda fuente del torneo: pares que solo están en BingX (HYPE, oro, Brent) con su API pública.

Las mismas estrategias corren sobre ellos en paper. Los 15 pares de Binance también existen como
perpetuos en BingX con la misma comisión que modelan las estrategias "_futuros" (0,02 % maker /
0,05 % taker, revisado el 31-oct-2026), así que lo que gane el torneo se puede llevar a BingX.
Sin claves: precio cada 30 s y velas cerradas al terminar cada intervalo.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.config import settings
from app.lab.bars import TF_MINUTES, Bar

logger = logging.getLogger(__name__)

BASE = "https://open-api.bingx.com"
POLL_SECONDS = 30


def pairs() -> dict[str, str]:
    """{nombre interno: símbolo de BingX}, p. ej. {"GOLDUSDT": "NCCOGOLD2USD-USDT"}."""
    out = {}
    for item in settings.lab_bingx_symbols.split(","):
        if ":" in item:
            bx, name = item.strip().split(":", 1)
            out[name.strip().upper()] = bx.strip()
    return out


def klines(client, bx: str, tf: str, limit: int, now_ms: int) -> list[Bar]:
    """Velas CERRADAS, de la más vieja a la más nueva (BingX las da al revés e incluye la abierta)."""
    data = client.get(f"{BASE}/openApi/swap/v3/quote/klines", params={"symbol": bx, "interval": tf, "limit": limit},
                      timeout=15).json()
    if data.get("code") not in (0, "0"):
        raise RuntimeError(f"bingx klines {bx}: {data.get('msg')}")
    tf_ms = TF_MINUTES[tf] * 60_000
    bars = [Bar(int(k["time"]), float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"]), float(k["volume"]))
            for k in data.get("data") or []]
    return sorted((b for b in bars if b.ts + tf_ms <= now_ms), key=lambda b: b.ts)


def price(client, bx: str) -> str:
    data = client.get(f"{BASE}/openApi/swap/v2/quote/price", params={"symbol": bx}, timeout=15).json()
    return data["data"]["price"]


def seed(runner, client=None) -> None:
    from app.lab.live import HISTORY, RegimeLookup, dec

    client = client or httpx
    now_ms = int(time.time() * 1000)
    for name, bx in pairs().items():
        try:
            for tf in runner.timeframes:
                for attempt in range(3):
                    try:
                        runner.bars[(name, tf)] = klines(client, bx, tf, HISTORY, now_ms)
                        break
                    except RuntimeError:
                        if attempt == 2:
                            raise
                        time.sleep(5)
                time.sleep(1.5)  # BingX corta ráfagas ("请稍后重试" = reintenta luego)
            runner.regimes[name] = RegimeLookup(runner.bars.get((name, "1h"), []))
            runner.prices[name] = dec(price(client, bx))
        except Exception as exc:  # noqa: BLE001 — un par que falla no frena a los demás
            logger.warning("bingx feed: seed %s failed (%s)", name, exc)


def poll_once(runner, client=None, now_ms: int | None = None) -> None:
    from app.lab.live import dec

    client = client or httpx
    now_ms = now_ms or int(time.time() * 1000)
    for name, bx in pairs().items():
        try:
            runner.on_price(name, dec(price(client, bx)))
            for tf in runner.timeframes:
                series = runner.bars.get((name, tf), [])
                tf_ms = TF_MINUTES[tf] * 60_000
                if series and now_ms < series[-1].ts + 2 * tf_ms:
                    continue  # la siguiente vela aún no cerró
                time.sleep(1)  # BingX corta ráfagas al cambiar la hora (varias velas cierran juntas)
                for bar in klines(client, bx, tf, 3, now_ms):
                    runner.on_bar_closed(name, tf, bar)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bingx feed: %s failed (%s)", name, exc)


async def bingx_feed_loop(runner, stop_event: asyncio.Event) -> None:
    if not pairs():
        return
    await asyncio.to_thread(seed, runner)
    logger.info("bingx feed: %s pairs (%s)", len(pairs()), ", ".join(pairs()))
    while not stop_event.is_set():
        await asyncio.to_thread(poll_once, runner)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=POLL_SECONDS)
        except TimeoutError:
            pass

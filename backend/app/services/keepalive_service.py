"""Keepalive antispin-down del web service gratuito de Render (spec 002, RF-1).

Render free duerme el servicio tras 15 min sin tráfico inbound; este módulo
petitiona la propia URL pública cada ``KEEPALIVE_INTERVAL_SECONDS`` (9 min,
margen sobre el spin-down) para mantenerlo despierto dentro del límite de
750 h/mes (D-5). Solo se activa con ``KEEPALIVE_URL`` configurada (en local
queda vacía y el bucle no arranca).

Cualquier error de red se registra únicamente con el tipo de excepción y se
ignora: el keepalive nunca tumbaría el servicio ni loguea credenciales
(RF-4 / RNF-3).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL_SECONDS = 540
PING_TIMEOUT_SECONDS = 10


def should_keepalive(url: str) -> bool:
    """True si hay una URL pública http(s) que vigilar."""
    return url.startswith(("http://", "https://"))


async def run_ping(url: str, *, client: httpx.AsyncClient) -> bool:
    """Un ping a la URL pública: `True` si hubo respuesta HTTP.

    Cualquier respuesta (aunque sea 4xx/5xx) llega al servicio y cuenta
    como tráfico; solo un error de transporte cuenta como fallo y no se
    propaga (el keepalive no debe tumbar la aplicación).
    """
    try:
        await client.get(url, timeout=PING_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        logger.warning("keepalive error: %s", type(exc).__name__)
        return False
    return True


async def keepalive_loop(
    stop_event: asyncio.Event,
    *,
    url: str,
    interval_seconds: int = KEEPALIVE_INTERVAL_SECONDS,
    client_factory: Callable[[], Any] | None = None,
) -> None:
    """Ping inmediato y después cada `interval_seconds` hasta `stop_event`."""
    factory = client_factory or httpx.AsyncClient
    async with factory() as client:
        while not stop_event.is_set():
            await run_ping(url, client=client)
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval_seconds,
                )
            except TimeoutError:
                continue

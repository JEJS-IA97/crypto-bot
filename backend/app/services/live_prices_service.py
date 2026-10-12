"""Precios en vivo para el panel (caché corta contra Binance).

Separado de `market_sync_service` porque ese fichero está en la zona
congelada multi-exchange (RF-21, spec 001) y no debe tocarse.
"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.schemas import MarketPriceResponse
from app.services.market_sync_service import synchronize_market_prices
from app.services.simulation_service import get_market_prices

# Caché: el panel refresca cada segundo y Binance no necesita un ticker
# por petición (una llamada cada _LIVE_TTL_SECONDS).
_LIVE_TTL_SECONDS = 2.0
_live_cache: dict[str, object] = {"at": 0.0, "prices": []}


def live_market_prices(
    db: Session,
    ttl_seconds: float = _LIVE_TTL_SECONDS,
) -> list[MarketPriceResponse]:
    """Sincroniza con Binance (caché corta); si falla, sirve la BD.

    La tabla sola queda congelada: el panel veía siempre el mismo precio
    porque nada la refrescaba.
    """
    now = time.monotonic()
    cached = _live_cache["prices"]
    if cached and now - float(_live_cache["at"]) < ttl_seconds:
        return list(cached)

    try:
        synchronized = synchronize_market_prices(db)
    except Exception:
        return [
            MarketPriceResponse.model_validate(price)
            for price in get_market_prices(db)
        ]

    prices = [
        MarketPriceResponse.model_validate(price)
        for price in synchronized
    ]
    _live_cache["at"] = now
    _live_cache["prices"] = prices
    return list(prices)

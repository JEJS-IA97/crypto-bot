"""Precios en vivo del panel: caché corta contra Binance + fallback (BD)."""

import time
import unittest
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, SimulationMarketPrice
from app.services import live_prices_service
from app.services.live_prices_service import live_market_prices

FETCH = "app.services.market_sync_service.fetch_market_prices"


class LiveMarketPricesTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        live_prices_service._live_cache["at"] = 0.0
        live_prices_service._live_cache["prices"] = []

    def tearDown(self) -> None:
        self.db.close()

    def _seed(self, symbol: str, price: str) -> None:
        self.db.add(
            SimulationMarketPrice(
                symbol=symbol,
                price_usd=Decimal(price),
            )
        )
        self.db.commit()

    def test_sincroniza_y_cachea_durante_el_ttl(self) -> None:
        with patch(
            FETCH,
            return_value=[
                {"symbol": "BTCUSDT", "price_usd": Decimal("123")}
            ],
        ) as fetch:
            first = live_market_prices(self.db)
            second = live_market_prices(self.db)

        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(first[0].price_usd, Decimal("123"))
        self.assertEqual(second[0].price_usd, Decimal("123"))

    def test_cache_vencido_vuelve_a_llamar_a_binance(self) -> None:
        with patch(
            FETCH,
            return_value=[
                {"symbol": "BTCUSDT", "price_usd": Decimal("123")}
            ],
        ) as fetch:
            live_market_prices(self.db)
            live_prices_service._live_cache["at"] = (
                time.monotonic() - 10.0
            )
            live_market_prices(self.db)

        self.assertEqual(fetch.call_count, 2)

    def test_falla_de_binance_cae_en_la_bd(self) -> None:
        self._seed("BTCUSDT", "999")

        with patch(
            FETCH,
            side_effect=RuntimeError("Binance returned 500"),
        ):
            prices = live_market_prices(self.db)

        self.assertEqual(prices[0].symbol, "BTCUSDT")
        self.assertEqual(prices[0].price_usd, Decimal("999"))


if __name__ == "__main__":
    unittest.main()

from decimal import Decimal
from pathlib import Path
import sys
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base
from app.models import (
    SimulationAccount,
    SimulationArbitrage,
    SimulationBalance,
)
from app.services.arbitrage_service import execute_arbitrage


class ArbitrageExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={
                "check_same_thread": False,
            },
        )

        Base.metadata.create_all(
            bind=self.engine
        )

        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

    def tearDown(self) -> None:
        Base.metadata.drop_all(
            bind=self.engine
        )

        self.engine.dispose()

    def test_profitable_arbitrage_executes_and_updates_balance(
        self,
    ) -> None:
        db: Session = self.session_factory()

        try:
            account = SimulationAccount(
                name="Arbitrage Test"
            )

            db.add(account)
            db.flush()

            balance = SimulationBalance(
                account_id=account.id,
                available_usd=Decimal("20.48650000"),
                invested_usd=Decimal("0"),
                realized_pnl_usd=Decimal("0"),
            )

            db.add(balance)
            db.commit()

            initial_balance = balance.available_usd

            executions = {
                "buy_options": [
                    {
                        "exchange": "binance",
                        "symbol": "BTCUSDT",
                        "side": "BUY",
                        "quote_currency": "USDT",
                        "market_price": Decimal("84000"),
                        "price_usd": Decimal("84000"),
                        "fee_rate": Decimal("0.001"),
                        "fee_usd": Decimal("84"),
                        "effective_price_usd": Decimal("84084"),
                        "ask_quantity": Decimal("1"),
                    }
                ],
                "sell_options": [
                    {
                        "exchange": "bybit",
                        "symbol": "BTCUSDT",
                        "side": "SELL",
                        "quote_currency": "USDT",
                        "market_price": Decimal("85500"),
                        "price_usd": Decimal("85500"),
                        "fee_rate": Decimal("0.001"),
                        "fee_usd": Decimal("85.5"),
                        "effective_price_usd": Decimal("85414.5"),
                        "bid_quantity": Decimal("1"),
                    }
                ],
            }

            quantity = (
                Decimal("5")
                / Decimal("84084")
            )

            opportunity = {
                "status": "TRADE",
                "buy_exchange": "binance",
                "sell_exchange": "bybit",
                "buy_symbol": "BTCUSDT",
                "sell_symbol": "BTCUSDT",
                "symbol": "BTCUSDT",
                "base_asset": "BTC",
                "buy_quote_currency": "USDT",
                "sell_quote_currency": "USDT",
                "capital_usd": Decimal("5"),
                "quantity": quantity,
                "buy_effective_price_usd": Decimal("84084"),
                "sell_effective_price_usd": Decimal("85414.5"),
                "capital_used_usd": Decimal("5"),
                "estimated_sell_value_usd": (
                    quantity
                    * Decimal("85414.5")
                ),
                "estimated_profit_usd": (
                    quantity
                    * Decimal("85414.5")
                    - Decimal("5")
                ),
                "estimated_profit_percent": Decimal(
                    "1"
                ),
                "buy_liquidity_usd": Decimal("84084"),
                "sell_liquidity_usd": Decimal("85414.5"),
                "liquidity_limited": False,
                "min_profit_usd": Decimal("0.05"),
                "min_profit_percent": Decimal("0.10"),
            }

            arbitrage = execute_arbitrage(
                db=db,
                account_id=account.id,
                opportunity=opportunity,
                executions=executions,
            )

            db.refresh(balance)

            self.assertIsNotNone(
                arbitrage.id
            )

            self.assertEqual(
                arbitrage.account_id,
                account.id,
            )

            self.assertEqual(
                arbitrage.symbol,
                "BTCUSDT",
            )

            self.assertEqual(
                arbitrage.buy_exchange,
                "binance",
            )

            self.assertEqual(
                arbitrage.sell_exchange,
                "bybit",
            )

            self.assertGreater(
                arbitrage.net_profit_usd,
                Decimal("0"),
            )

            self.assertGreater(
                balance.available_usd,
                initial_balance,
            )

            self.assertGreater(
                balance.realized_pnl_usd,
                Decimal("0"),
            )

            stored_arbitrages = list(
                db.scalars(
                    select(
                        SimulationArbitrage
                    ).where(
                        SimulationArbitrage.account_id
                        == account.id
                    )
                ).all()
            )

            self.assertEqual(
                len(stored_arbitrages),
                1,
            )

            stored = stored_arbitrages[0]

            self.assertEqual(
                stored.id,
                arbitrage.id,
            )

            print()
            print(
                "ARBITRAGE TEST PASSED"
            )
            print(
                f"Initial balance: "
                f"{initial_balance}"
            )
            print(
                f"Final balance: "
                f"{balance.available_usd}"
            )
            print(
                f"Net profit: "
                f"{arbitrage.net_profit_usd}"
            )
            print(
                f"Arbitrage ID: "
                f"{arbitrage.id}"
            )

        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle, StrategyConfig
from app.models import (
    DecisionStatus,
    PositionStatus,
    PositionV2,
    SignalDecision,
)
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import SymbolRules
from app.services.bot_loop import run_once
from app.services.exchange_executor import OrderRequest
from app.services.risk_guard_service import get_runtime
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import create_simulation_account


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def buy_candles() -> list[Candle]:
    """Serie determinista que el motor evalúa como BUY (RF-7)."""
    base = datetime(2026, 10, 5, 0, 0)
    price = Decimal("100")
    closes = []
    for index in range(57):
        closes.append(price)
        price = (
            price + Decimal("0.1")
            if index % 2 == 0
            else price - Decimal("0.1")
        )
    closes.append(price - Decimal("0.1"))
    closes.append(price - Decimal("0.1") + Decimal("0.5"))
    candles = []
    previous = None
    for index, close in enumerate(closes):
        open_price = previous if previous is not None else close
        volume = (
            Decimal("200") if index == len(closes) - 1 else Decimal("100")
        )
        candles.append(
            Candle(
                open_time=base + timedelta(minutes=15 * index),
                open=open_price,
                high=close + Decimal("0.05"),
                low=close - Decimal("0.05"),
                close=close,
                volume=volume,
            )
        )
        previous = close
    return candles


class FakeMarketData:
    def __init__(self, candles_by_symbol: dict) -> None:
        self._candles = candles_by_symbol
        self.kline_calls: list[str] = []

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        self.kline_calls.append(symbol)
        return list(self._candles[symbol])

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol=symbol,
            status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )


class KillSwitchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="kill-switch",
                initial_balance_usd=Decimal("50"),
            ),
        )
        self.market = FakeMarketData(
            {
                "BTCUSDT": buy_candles(),
                "ETHUSDT": buy_candles(),
            }
        )
        self.symbols = ["BTCUSDT", "ETHUSDT"]

    def tearDown(self) -> None:
        self.db.close()

    def _count(self, model) -> int:
        return len(list(self.db.scalars(select(model)).all()))

    def test_stop_during_cycle(self) -> None:
        runtime = get_runtime(self.db)
        self.assertTrue(runtime.running)

        inner = SimulationExecutor(self.db, self.account.id)
        db = self.db
        state = {"flipped": False}

        class StoppingExecutor:
            exchange_name = "simulation"

            def __init__(self) -> None:
                self.calls: list[OrderRequest] = []

            def place_order(self, request: OrderRequest):
                self.calls.append(request)
                result = inner.place_order(request)
                if not state["flipped"]:
                    # El kill switch cae mientras se llena la primera orden.
                    state["flipped"] = True
                    runtime.running = False
                    db.commit()
                return result

        executor = StoppingExecutor()

        # Ciclo 1: la primera orden llena y durante ella se detiene el bot;
        # el resto del ciclo no emite ninguna orden nueva (RF-3).
        report = run_once(
            self.db,
            market_data=self.market,
            symbols=self.symbols,
            account_id=self.account.id,
            strategy=StrategyConfig(),
            executor=executor,
        )
        self.assertEqual(report.status, "stopped")
        self.assertEqual(report.opened, 1)
        self.assertEqual(report.closed, 0)
        self.assertEqual(len(executor.calls), 1)

        positions = list(self.db.scalars(select(PositionV2)).all())
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "BTCUSDT")
        self.assertEqual(positions[0].status, PositionStatus.OPEN)
        self.assertIsNotNone(positions[0].stop_order_id)
        self.assertIsNotNone(positions[0].tp_order_id)

        # Ni orden ni decisión para ETH: nada nuevo sale tras el stop.
        eth_decisions = list(
            self.db.scalars(
                select(SignalDecision).where(
                    SignalDecision.symbol == "ETHUSDT"
                )
            ).all()
        )
        self.assertEqual(eth_decisions, [])
        btc_decision = self.db.scalars(
            select(SignalDecision).where(
                SignalDecision.symbol == "BTCUSDT"
            )
        ).one()
        self.assertEqual(btc_decision.status, DecisionStatus.OPENED)

        # Ciclo 2: detenido → ni siquiera descarga datos.
        klines_so_far = list(self.market.kline_calls)
        report = run_once(
            self.db,
            market_data=self.market,
            symbols=self.symbols,
            account_id=self.account.id,
            strategy=StrategyConfig(),
            executor=executor,
        )
        self.assertEqual(report.status, "stopped")
        self.assertEqual(report.opened, 0)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(self.market.kline_calls, klines_so_far)
        self.assertEqual(self._count(SignalDecision), 1)
        self.assertEqual(self._count(PositionV2), 1)

        # Reanudar sin reiniciar: ETH abre y BTC queda protegido (RF-3).
        runtime = get_runtime(self.db)
        runtime.running = True
        self.db.commit()
        report = run_once(
            self.db,
            market_data=self.market,
            symbols=self.symbols,
            account_id=self.account.id,
            strategy=StrategyConfig(),
            executor=executor,
        )
        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 1)
        self.assertEqual(len(executor.calls), 2)
        self.assertEqual(self._count(PositionV2), 2)
        eth_decision = self.db.scalars(
            select(SignalDecision).where(
                SignalDecision.symbol == "ETHUSDT"
            )
        ).one()
        self.assertEqual(eth_decision.status, DecisionStatus.OPENED)


if __name__ == "__main__":
    unittest.main()

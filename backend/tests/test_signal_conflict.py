import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle, StrategyConfig
from app.models import (
    DecisionOrigin,
    DecisionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import SymbolRules
from app.services.bot_loop import run_once
from app.services.exchange_executor import OrderRequest
from app.services.external_signal_service import EXTERNAL_CONFLICT_REASON
from app.services.simulation_executor import SimulationExecutor
from app.services.simulation_service import create_simulation_account


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def buy_candles() -> list[Candle]:
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

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        return list(self._candles[symbol])

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol=symbol,
            status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )


class RecordingExecutor:
    exchange_name = "simulation"

    def __init__(self, inner: SimulationExecutor) -> None:
        self._inner = inner
        self.calls: list[OrderRequest] = []

    def place_order(self, request: OrderRequest):
        self.calls.append(request)
        return self._inner.place_order(request)


class SignalConflictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="conflict",
                initial_balance_usd=Decimal("50"),
            ),
        )
        self.market = FakeMarketData({"BTCUSDT": buy_candles()})

    def tearDown(self) -> None:
        self.db.close()

    def test_external_wins(self) -> None:
        # Señal externa en cola: vender mientras la técnica dice comprar.
        external = SignalDecision(
            client_order_id="ext-sell-conflict-0001",
            symbol="BTCUSDT",
            side=TradeSide.SELL,
            origin=DecisionOrigin.EXTERNAL,
            source="copia-proveedor",
            status=DecisionStatus.PENDING,
            config_json="{}",
            market_snapshot_json="{}",
        )
        self.db.add(external)
        self.db.commit()

        executor = RecordingExecutor(
            SimulationExecutor(self.db, self.account.id)
        )
        report = run_once(
            self.db,
            market_data=self.market,
            symbols=["BTCUSDT"],
            account_id=self.account.id,
            strategy=StrategyConfig(),
            executor=executor,
        )

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 0)
        # RF-23: gana la externa → la técnica no emite ninguna orden.
        self.assertEqual(executor.calls, [])
        self.assertEqual(self.db.scalars(select(PositionV2)).all(), [])

        decisions = list(self.db.scalars(select(SignalDecision)).all())
        self.assertEqual(len(decisions), 2)
        technical = next(
            item
            for item in decisions
            if item.origin == DecisionOrigin.TECHNICAL
        )
        self.assertEqual(technical.status, DecisionStatus.REJECTED)
        self.assertEqual(
            technical.rejection_reason, EXTERNAL_CONFLICT_REASON
        )

        external_row = next(
            item
            for item in decisions
            if item.origin == DecisionOrigin.EXTERNAL
        )
        self.assertEqual(external_row.status, DecisionStatus.REJECTED)
        self.assertEqual(
            external_row.rejection_reason, "no_position_to_close"
        )
        self.assertEqual(report.rejected, 2)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
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

NY = ZoneInfo("America/New_York")
SESSION_DAY = date(2026, 10, 5)  # EDT (UTC-4)
NOW_IN_WINDOW = (
    datetime(2026, 10, 5, 9, 35, tzinfo=NY)
    .astimezone(timezone.utc)
    .replace(tzinfo=None)
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _ny_utc(hour: int, minute: int) -> datetime:
    moment = datetime(
        SESSION_DAY.year, SESSION_DAY.month, SESSION_DAY.day, hour, minute,
        tzinfo=NY,
    )
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def candles_15m() -> list[Candle]:
    base = datetime(2026, 10, 5, 0, 0)
    return [
        Candle(
            open_time=base + timedelta(minutes=15 * index),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("100"),
        )
        for index in range(60)
    ]


def orb_candles() -> list[Candle]:
    """Rango 9:00–9:25 + rompimiento alcista en la vela de las 9:30."""
    candles = []
    for minute in (0, 5, 10, 15, 20, 25):
        candles.append(
            Candle(
                open_time=_ny_utc(9, minute),
                open=Decimal("100"),
                high=Decimal("100.5"),
                low=Decimal("99.5"),
                close=Decimal("100"),
                volume=Decimal("100"),
            )
        )
    candles.append(
        Candle(
            open_time=_ny_utc(9, 30),
            open=Decimal("100"),
            high=Decimal("106.5"),
            low=Decimal("99.8"),
            close=Decimal("106"),
            volume=Decimal("200"),
        )
    )
    return candles


class FakeMarketData:
    def __init__(self, candles_15m_by_symbol: dict, candles_5m: list[Candle]):
        self._candles_15m = candles_15m_by_symbol
        self._candles_5m = candles_5m
        self.kline_calls: list[tuple[str, str]] = []

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        self.kline_calls.append((symbol, interval))
        if interval == "5m":
            return list(self._candles_5m)
        return list(self._candles_15m[symbol])

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
        self.market = FakeMarketData(
            {"BTCUSDT": candles_15m()}, orb_candles()
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_external_wins(self) -> None:
        # Señal externa en cola: vender mientras el ORB dice comprar.
        external = SignalDecision(
            client_order_id="ext-sell-conflict-0001",
            symbol="BTCUSDT",
            side=TradeSide.SELL,
            origin=DecisionOrigin.EXTERNAL,
            source="copia-proveedor",
            status=DecisionStatus.PENDING,
            config_json="{}",
            market_snapshot_json="{}",
            created_at=NOW_IN_WINDOW,
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
            executor=executor,
            now=NOW_IN_WINDOW,
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
        # El snapshot de la técnica conserva el rango ORB (RF-10).
        snapshot = json.loads(technical.market_snapshot_json)
        self.assertEqual(snapshot["indicators"]["range_high"], "100.5")

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

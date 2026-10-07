import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import Candle
from app.models import (
    BotRuntime,
    DecisionOrigin,
    DecisionStatus,
    PositionV2,
    SignalDecision,
    TradeSide,
)
from app.schemas import SimulationAccountCreate
from app.services.binance_market_data_client import (
    MarketDataUnavailable,
    SymbolRules,
)
from app.services.bot_loop import run_once
from app.services.risk_guard_service import (
    BREAKER_FAILURE_THRESHOLD,
    get_daily_state,
    get_runtime,
    record_cycle_failure,
    record_cycle_success,
    reset_breaker,
)
from app.services.simulation_service import create_simulation_account

# Mediodía en Nueva York (EDT): fuera de la ventana ORB.
NOW_OUTSIDE = datetime(2026, 10, 5, 16, 0)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class CircuitBreakerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.session = self.session_factory()

    def tearDown(self) -> None:
        self.session.close()

    def test_stops_after_5_failures(self) -> None:
        self.assertEqual(BREAKER_FAILURE_THRESHOLD, 5)

        for _ in range(BREAKER_FAILURE_THRESHOLD - 1):
            runtime = record_cycle_failure(self.session)
        self.assertFalse(runtime.breaker_active)
        self.assertEqual(
            runtime.consecutive_failures, BREAKER_FAILURE_THRESHOLD - 1
        )

        runtime = record_cycle_failure(self.session)
        self.assertTrue(runtime.breaker_active)
        self.assertEqual(runtime.consecutive_failures, BREAKER_FAILURE_THRESHOLD)
        self.assertIn("5", runtime.breaker_reason)

        # Un ciclo bueno reinicia el contador pero NO el breaker (RF-22:
        # reinicio manual).
        runtime = record_cycle_success(self.session)
        self.assertEqual(runtime.consecutive_failures, 0)
        self.assertTrue(runtime.breaker_active)

        runtime = reset_breaker(self.session)
        self.assertFalse(runtime.breaker_active)
        self.assertEqual(runtime.consecutive_failures, 0)
        self.assertIsNone(runtime.breaker_reason)

    def test_success_before_threshold_keeps_counter_clean(self) -> None:
        record_cycle_failure(self.session)
        record_cycle_failure(self.session)
        runtime = record_cycle_success(self.session)
        self.assertEqual(runtime.consecutive_failures, 0)
        self.assertFalse(runtime.breaker_active)

        record_cycle_failure(self.session)
        runtime = record_cycle_success(self.session)
        self.assertEqual(runtime.consecutive_failures, 0)

    def test_runtime_is_a_single_row(self) -> None:
        first = get_runtime(self.session)
        second = get_runtime(self.session)
        self.assertEqual(first.id, second.id)
        rows = self.session.execute(select(BotRuntime)).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertTrue(first.running)
        self.assertFalse(first.breaker_active)

    def test_breaker_state_persists_across_sessions(self) -> None:
        for _ in range(BREAKER_FAILURE_THRESHOLD):
            record_cycle_failure(self.session)
        self.session.close()

        with self.session_factory() as fresh:
            runtime = get_runtime(fresh)
            self.assertTrue(runtime.breaker_active)
            self.assertEqual(
                runtime.consecutive_failures, BREAKER_FAILURE_THRESHOLD
            )

    def test_daily_state_usable_independently(self) -> None:
        state = get_daily_state(self.session, date(2026, 10, 2), Decimal("20"))
        self.assertFalse(state.blocked)


def _buy_candles() -> list[Candle]:
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


class _BrokenMarket:
    """Datos de Binance caídos: el ciclo debe fallar sin operar (RNF-6)."""

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        raise MarketDataUnavailable("exchange offline")

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        raise MarketDataUnavailable("exchange offline")


class _FakeMarket:
    def __init__(self) -> None:
        self.kline_calls: list[tuple[str, str]] = []

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 200
    ) -> list[Candle]:
        self.kline_calls.append((symbol, interval))
        if interval == "5m":
            return []
        return _buy_candles()

    def get_exchange_info(self, symbol: str) -> SymbolRules:
        return SymbolRules(
            symbol=symbol,
            status="TRADING",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )


class BreakerBlocksOrdersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_factory = _session_factory()
        self.db = self.session_factory()
        self.account = create_simulation_account(
            self.db,
            SimulationAccountCreate(
                name="breaker-loop",
                initial_balance_usd=Decimal("50"),
            ),
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_breaker_blocks_orders(self) -> None:
        # 5 ciclos con los datos caídos → el breaker se activa (RF-22).
        for _ in range(BREAKER_FAILURE_THRESHOLD):
            report = run_once(
                self.db,
                market_data=_BrokenMarket(),
                symbols=["BTCUSDT"],
                account_id=self.account.id,
                now=NOW_OUTSIDE,
            )
            self.assertEqual(report.status, "failed")
            self.assertIn("offline", report.error)

        runtime = get_runtime(self.db)
        self.assertTrue(runtime.breaker_active)
        self.assertEqual(
            runtime.consecutive_failures, BREAKER_FAILURE_THRESHOLD
        )

        # Con el breaker activo ni siquiera se descargan datos: sin órdenes.
        good = _FakeMarket()
        report = run_once(
            self.db,
            market_data=good,
            symbols=["BTCUSDT"],
            account_id=self.account.id,
            now=NOW_OUTSIDE,
        )
        self.assertEqual(report.status, "breaker")
        self.assertEqual(good.kline_calls, [])
        self.assertEqual(self.db.scalars(select(PositionV2)).all(), [])
        self.assertEqual(self.db.scalars(select(SignalDecision)).all(), [])

        # Reinicio manual → el loop vuelve a operar (RF-22).
        reset_breaker(self.db)
        self.db.add(
            SignalDecision(
                client_order_id="ext-buy-breaker-0001",
                symbol="BTCUSDT",
                side=TradeSide.BUY,
                origin=DecisionOrigin.EXTERNAL,
                source="copia-proveedor",
                status=DecisionStatus.PENDING,
                config_json="{}",
                market_snapshot_json="{}",
                created_at=NOW_OUTSIDE,
            )
        )
        self.db.commit()
        good = _FakeMarket()
        report = run_once(
            self.db,
            market_data=good,
            symbols=["BTCUSDT"],
            account_id=self.account.id,
            now=NOW_OUTSIDE,
        )
        self.assertEqual(report.status, "ok")
        self.assertEqual(report.opened, 1)
        self.assertEqual(good.kline_calls, [("BTCUSDT", "15m")])
        positions = list(self.db.scalars(select(PositionV2)).all())
        self.assertEqual(len(positions), 1)
        runtime = get_runtime(self.db)
        self.assertFalse(runtime.breaker_active)
        self.assertEqual(runtime.consecutive_failures, 0)


if __name__ == "__main__":
    unittest.main()

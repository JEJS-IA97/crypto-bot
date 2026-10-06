import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, _enable_sqlite_foreign_keys
from app.domain.signal_engine import SignalAction
from app.models import DecisionOrigin, DecisionStatus, SignalDecision, TradeSide
from app.services.binance_market_data_client import SymbolRules
from app.services.external_signal_service import (
    EXTERNAL_CONFLICT_REASON,
    ExternalSignal,
    resolve_signal_conflict,
    validate_external_signal,
)

NOW = datetime(2026, 10, 1, 12, 0, 0)

RULES = SymbolRules(
    symbol="BTCUSDT",
    status="TRADING",
    tick_size=Decimal("0.01"),
    step_size=Decimal("0.001"),
    min_notional=Decimal("5"),
)


def _session_factory():
    engine = create_engine("sqlite://")
    _enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _signal(**overrides) -> ExternalSignal:
    params = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "price_limit": Decimal("100.50"),
        "quantity": Decimal("0.05"),
        "quantity_quote": None,
        "source": "telegram-grupo-x",
        "issued_at": NOW - timedelta(seconds=10),
    }
    params.update(overrides)
    return ExternalSignal(**params)


class TtlAndPriceDistanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _session_factory()()

    def tearDown(self) -> None:
        self.session.close()

    def _validate(self, signal, price=Decimal("100")):
        return validate_external_signal(
            self.session,
            signal,
            now=NOW,
            current_price=price,
            rules=RULES,
        )

    def test_ttl_and_price_distance(self) -> None:
        # Señal válida con cantidad explícita.
        result = self._validate(_signal())
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.symbol, "BTCUSDT")
        self.assertEqual(result.side, TradeSide.BUY)
        self.assertEqual(result.quantity, Decimal("0.05"))

        # Caducada (TTL por defecto 300 s).
        stale = _signal(issued_at=NOW - timedelta(seconds=301))
        result = self._validate(stale)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_expired")

        # TTL personalizado más corto.
        short_ttl = _signal(issued_at=NOW - timedelta(seconds=40),
                            ttl_seconds=30)
        result = self._validate(short_ttl)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_expired")

        # Marca temporal futura → inválida.
        future = _signal(issued_at=NOW + timedelta(seconds=60))
        result = self._validate(future)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_timestamp_invalid")

        # Precio lejano: 105 vs 100 = 5% > 1% permitido.
        far = _signal(price_limit=Decimal("105"))
        result = self._validate(far)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "price_too_far")

        # Precio dentro de la banda permitida (0,5% ≤ 1%).
        near = _signal(price_limit=Decimal("100.50"))
        self.assertTrue(self._validate(near).accepted)

    def test_quantity_computed_via_risk_math_when_missing(self) -> None:
        # Sin cantidad → tamaño por defecto: max(5, 25% de 20) = 5 USD.
        auto = _signal(quantity=None, quantity_quote=None)
        result = self._validate(auto)
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.quantity, Decimal("0.05"))

        # Con quantity_quote → importe objetivo (capital = quote / 25%).
        quoted = _signal(quantity=None, quantity_quote=Decimal("10"))
        result = self._validate(quoted)
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(result.quantity, Decimal("0.1"))

    def test_rejects_non_decimal_amounts(self) -> None:
        with self.assertRaises(TypeError):
            _signal(price_limit=100.5)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            _signal(quantity=0.05)  # type: ignore[arg-type]

    def test_issued_at_with_timezone_is_normalized(self) -> None:
        # RFC3339 con offset (+00:00): no debe reventar la comparación.
        fresh = _signal(
            issued_at=(NOW - timedelta(seconds=10)).replace(
                tzinfo=timezone.utc
            )
        )
        result = self._validate(fresh)
        self.assertTrue(result.accepted, result.reason)

        stale = _signal(
            issued_at=(NOW - timedelta(seconds=301)).replace(
                tzinfo=timezone.utc
            )
        )
        result = self._validate(stale)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_expired")

        future = _signal(
            issued_at=(NOW + timedelta(seconds=60)).replace(
                tzinfo=timezone.utc
            )
        )
        result = self._validate(future)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_timestamp_invalid")

    def test_issued_at_with_non_utc_offset_is_normalized(self) -> None:
        # El mismo instante (NOW-10s UTC) expresado en +05:00 sigue fresco.
        local = (NOW - timedelta(seconds=10)) + timedelta(hours=5)
        offset = _signal(
            issued_at=local.replace(tzinfo=timezone(timedelta(hours=5)))
        )
        result = self._validate(offset)
        self.assertTrue(result.accepted, result.reason)

        stale_local = (NOW - timedelta(seconds=301)) + timedelta(hours=5)
        stale = _signal(
            issued_at=stale_local.replace(
                tzinfo=timezone(timedelta(hours=5))
            )
        )
        result = self._validate(stale)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "signal_expired")


class DuplicateAndSymbolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = _session_factory()()

    def tearDown(self) -> None:
        self.session.close()

    def _validate(self, signal, price=Decimal("100")):
        return validate_external_signal(
            self.session,
            signal,
            now=NOW,
            current_price=price,
            rules=RULES,
        )

    def _insert_decision(self, symbol, side, status, created_at):
        self.session.add(
            SignalDecision(
                client_order_id=f"dec-{symbol}-{side}-{created_at.timestamp()}",
                symbol=symbol,
                side=side,
                origin=DecisionOrigin.TECHNICAL,
                status=status,
                config_json="{}",
                market_snapshot_json="{}",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        self.session.commit()

    def test_duplicate_and_unknown_symbol(self) -> None:
        # Compra reciente en BTCUSDT → la repetida es duplicada.
        self._insert_decision(
            "BTCUSDT", TradeSide.BUY, DecisionStatus.OPENED,
            NOW - timedelta(seconds=50),
        )
        result = self._validate(_signal())
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "duplicate_signal")

        # El lado contrario no es duplicado.
        opposite = _signal(side="SELL")
        result = self._validate(opposite)
        self.assertTrue(result.accepted, result.reason)

        # Par fuera de la lista de 8 → desconocido.
        unknown = _signal(symbol="PEPEUSDT")
        result = self._validate(unknown)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "unknown_symbol")

        # Lado inválido.
        bad_side = _signal(side="HOLD")
        result = self._validate(bad_side)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "invalid_side")

        # Las decisiones rechazadas no generan duplicado.
        self._insert_decision(
            "ETHUSDT", TradeSide.BUY, DecisionStatus.REJECTED,
            NOW - timedelta(seconds=10),
        )
        eth = _signal(symbol="ETHUSDT")
        result = self._validate(eth)
        self.assertTrue(result.accepted, result.reason)

        # Fuera del cooldown (300 s) la señal ya no cuenta como duplicada.
        self._insert_decision(
            "SOLUSDT", TradeSide.BUY, DecisionStatus.OPENED,
            NOW - timedelta(seconds=400),
        )
        sol = _signal(symbol="SOLUSDT")
        result = self._validate(sol)
        self.assertTrue(result.accepted, result.reason)


class ConflictTests(unittest.TestCase):
    def test_external_wins_on_conflict(self) -> None:
        resolution = resolve_signal_conflict(
            technical_symbol="BTCUSDT",
            technical_action=SignalAction.BUY,
            external_symbol="BTCUSDT",
            external_side=TradeSide.SELL,
        )
        self.assertTrue(resolution.external_wins)
        self.assertEqual(resolution.technical_reason,
                         EXTERNAL_CONFLICT_REASON)

        resolution = resolve_signal_conflict(
            technical_symbol="ETHUSDT",
            technical_action=SignalAction.SELL,
            external_symbol="ETHUSDT",
            external_side=TradeSide.BUY,
        )
        self.assertTrue(resolution.external_wins)
        self.assertEqual(resolution.technical_reason,
                         EXTERNAL_CONFLICT_REASON)

    def test_no_conflict_when_same_direction_or_other_symbol(self) -> None:
        same_direction = resolve_signal_conflict(
            technical_symbol="BTCUSDT",
            technical_action=SignalAction.BUY,
            external_symbol="BTCUSDT",
            external_side=TradeSide.BUY,
        )
        self.assertFalse(same_direction.external_wins)
        self.assertEqual(same_direction.technical_reason, "")

        other_symbol = resolve_signal_conflict(
            technical_symbol="BTCUSDT",
            technical_action=SignalAction.BUY,
            external_symbol="ETHUSDT",
            external_side=TradeSide.SELL,
        )
        self.assertFalse(other_symbol.external_wins)
        self.assertEqual(other_symbol.technical_reason, "")

    def test_hold_never_conflicts(self) -> None:
        resolution = resolve_signal_conflict(
            technical_symbol="BTCUSDT",
            technical_action=SignalAction.HOLD,
            external_symbol="BTCUSDT",
            external_side=TradeSide.SELL,
        )
        self.assertFalse(resolution.external_wins)
        self.assertEqual(resolution.technical_reason, "")

    def test_ttl_default_matches_settings(self) -> None:
        self.assertEqual(settings.signal_ttl_seconds, 300)


if __name__ == "__main__":
    unittest.main()

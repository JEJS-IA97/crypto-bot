import unittest
from decimal import Decimal

from app.domain.risk_math import (
    MAX_LOSS_PER_TRADE_USD,
    MAX_OPEN_POSITIONS,
    SizingResult,
    calculate_order_size,
    can_open_position,
    estimated_loss_usd,
    stop_take_prices,
)


def _size(**overrides):
    params = {
        "price": Decimal("100"),
        "capital_usd": Decimal("20"),
        "available_usd": Decimal("20"),
        "min_notional_usd": Decimal("5"),
        "step_size": Decimal("0.001"),
        "stop_loss_pct": Decimal("2"),
    }
    params.update(overrides)
    return calculate_order_size(**params)


class OrderSizingTests(unittest.TestCase):
    def test_min_notional_cap_and_rounding(self) -> None:
        # Objetivo = max(min_notional 5, 25% de 20 = 5) = 5; 5/100 = 0.05 exacto.
        result = _size()
        self.assertIsInstance(result, SizingResult)
        self.assertFalse(result.discarded, result.reason)
        self.assertEqual(result.quantity, Decimal("0.05"))
        self.assertEqual(result.notional_usd, Decimal("5"))
        self.assertGreaterEqual(
            result.notional_usd, Decimal("5")
        )  # cumple mínimo notional
        self.assertLessEqual(
            result.notional_usd,
            max(Decimal("5"), Decimal("20") * Decimal("0.25")),
        )

        # Piso al step se queda bajo el mínimo → se sube un solo step.
        stepped = _size(
            price=Decimal("30"),
            step_size=Decimal("0.01"),
        )
        self.assertFalse(stepped.discarded, stepped.reason)
        self.assertEqual(stepped.quantity, Decimal("0.17"))
        self.assertGreaterEqual(
            stepped.notional_usd, Decimal("5")
        )
        self.assertLessEqual(stepped.notional_usd, Decimal("20"))  # saldo

        # Mínimo pequeño: el tope de 25% manda.
        capped = _size(min_notional_usd=Decimal("1"))
        self.assertFalse(capped.discarded, capped.reason)
        self.assertLessEqual(capped.notional_usd, Decimal("5"))

        # Saldo insuficiente para el mínimo notional → descartada.
        poor = _size(available_usd=Decimal("4"))
        self.assertTrue(poor.discarded)
        self.assertEqual(poor.reason, "insufficient_balance")
        self.assertIsNone(poor.quantity)

    def test_open_position_cap(self) -> None:
        self.assertEqual(MAX_OPEN_POSITIONS, 3)
        self.assertTrue(can_open_position(0))
        self.assertTrue(can_open_position(2))
        self.assertFalse(can_open_position(3))
        self.assertFalse(can_open_position(4))

    def test_decimal_types(self) -> None:
        result = _size()
        self.assertIsInstance(result.quantity, Decimal)
        self.assertIsInstance(result.notional_usd, Decimal)
        self.assertIsInstance(result.estimated_loss_usd, Decimal)

        with self.assertRaises(TypeError):
            _size(price=100.0)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            _size(capital_usd=20.0)  # type: ignore[arg-type]

        stop, take = stop_take_prices(
            entry_price=Decimal("100"),
            stop_loss_pct=Decimal("2"),
            take_profit_pct=Decimal("4"),
            tick_size=Decimal("0.01"),
        )
        self.assertIsInstance(stop, Decimal)
        self.assertIsInstance(take, Decimal)


class LossCapTests(unittest.TestCase):
    def test_loss_capped_at_1usd(self) -> None:
        self.assertEqual(MAX_LOSS_PER_TRADE_USD, Decimal("1"))

        # Stop 2% sobre 5 USD → pérdida 0.10 USD ≤ 1 USD.
        normal = _size()
        self.assertFalse(normal.discarded, normal.reason)
        self.assertEqual(normal.estimated_loss_usd, Decimal("0.10"))
        self.assertLessEqual(
            normal.estimated_loss_usd, MAX_LOSS_PER_TRADE_USD
        )

        # Stop 30%: para arriesgar ≤1 USD haría falta 3.33 USD < mínimo 5.
        wide_stop = _size(stop_loss_pct=Decimal("30"))
        self.assertTrue(wide_stop.discarded)
        self.assertEqual(wide_stop.reason, "stop_loss_exceeds_max")
        self.assertIsNone(wide_stop.quantity)

        # La cantidad reducida por riesgo nunca supera el tope de pérdida.
        reduced = _size(
            stop_loss_pct=Decimal("4"),
            min_notional_usd=Decimal("1"),
        )
        self.assertFalse(reduced.discarded, reduced.reason)
        self.assertLessEqual(
            reduced.estimated_loss_usd, MAX_LOSS_PER_TRADE_USD
        )

    def test_stop_and_take_prices_are_conservative(self) -> None:
        entry = Decimal("100.07")
        stop, take = stop_take_prices(
            entry_price=entry,
            stop_loss_pct=Decimal("2"),
            take_profit_pct=Decimal("4"),
            tick_size=Decimal("0.1"),
        )
        exact_stop = entry * (Decimal(1) - Decimal("0.02"))
        exact_take = entry * (Decimal(1) + Decimal("0.04"))
        # Stop redondeado hacia la entrada (pérdida ≤ la estimada)...
        self.assertGreaterEqual(stop, exact_stop)
        self.assertLess(stop, entry)
        # ...y take redondeado hacia abajo (objetivo alcanzable antes).
        self.assertLessEqual(take, exact_take)
        self.assertGreater(take, entry)
        # Pérdida real con el stop redondeado ≤ 1 USD con qty de 5 USD.
        loss = estimated_loss_usd(
            entry_price=entry,
            stop_price=stop,
            quantity=Decimal("0.05"),
        )
        self.assertLessEqual(loss, MAX_LOSS_PER_TRADE_USD)

    def test_invalid_inputs_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _size(step_size=Decimal("0"))
        with self.assertRaises(ValueError):
            _size(stop_loss_pct=Decimal("0"))
        with self.assertRaises(ValueError):
            _size(stop_loss_pct=Decimal("-1"))
        with self.assertRaises(ValueError):
            stop_take_prices(
                entry_price=Decimal("100"),
                stop_loss_pct=Decimal("2"),
                take_profit_pct=Decimal("4"),
                tick_size=Decimal("0"),
            )
        with self.assertRaises(ValueError):
            estimated_loss_usd(
                entry_price=Decimal("100"),
                stop_price=Decimal("101"),
                quantity=Decimal("1"),
            )


if __name__ == "__main__":
    unittest.main()

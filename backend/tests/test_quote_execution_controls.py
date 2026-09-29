import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from app.services.bot_engine import (
    _calculate_revalidation_slippage,
    _filter_fresh_executions,
    execute_market,
)


class QuoteExecutionControlsTest(unittest.TestCase):
    def test_freshness_rejects_stale_and_missing_timestamps(self) -> None:
        now = datetime.now(timezone.utc)

        executions = {
            "buy_options": [
                {
                    "exchange": "binance",
                    "effective_price_usd": Decimal("100"),
                    "fetched_at": now.isoformat(),
                },
                {
                    "exchange": "bybit",
                    "effective_price_usd": Decimal("101"),
                    "fetched_at": (
                        now - timedelta(seconds=6)
                    ).isoformat(),
                },
                {
                    "exchange": "kraken",
                    "effective_price_usd": Decimal("102"),
                },
            ],
            "sell_options": [
                {
                    "exchange": "binance",
                    "effective_price_usd": Decimal("105"),
                    "fetched_at": now.isoformat(),
                },
                {
                    "exchange": "bybit",
                    "effective_price_usd": Decimal("104"),
                    "fetched_at": (
                        now - timedelta(seconds=6)
                    ).isoformat(),
                },
            ],
        }

        result = _filter_fresh_executions(
            executions,
            max_quote_age_seconds=5,
        )

        self.assertEqual(
            len(result["buy_options"]),
            1,
        )
        self.assertEqual(
            len(result["sell_options"]),
            1,
        )
        self.assertEqual(
            result["freshness"]["stale_buy_count"],
            2,
        )
        self.assertEqual(
            result["freshness"]["stale_sell_count"],
            1,
        )
        self.assertEqual(
            result["best_buy"]["exchange"],
            "binance",
        )
        self.assertEqual(
            result["best_sell"]["exchange"],
            "binance",
        )

    def test_slippage_calculation_uses_adverse_movement(self) -> None:
        first = {
            "buy_effective_price_usd": Decimal("100"),
            "sell_effective_price_usd": Decimal("101"),
        }
        second = {
            "buy_effective_price_usd": Decimal("100.10"),
            "sell_effective_price_usd": Decimal("100.90"),
        }

        result = _calculate_revalidation_slippage(
            first,
            second,
        )

        self.assertAlmostEqual(
            float(result["buy_slippage_percent"]),
            0.10,
            places=6,
        )
        self.assertAlmostEqual(
            float(result["sell_slippage_percent"]),
            0.0990099,
            places=6,
        )
        self.assertAlmostEqual(
            float(result["max_adverse_slippage_percent"]),
            0.10,
            places=6,
        )

    def test_execute_market_blocks_when_slippage_tolerance_is_exceeded(self) -> None:
        first_opportunity = {
            "status": "TRADE",
            "buy_effective_price_usd": Decimal("100"),
            "sell_effective_price_usd": Decimal("101"),
        }
        second_opportunity = {
            "status": "TRADE",
            "buy_effective_price_usd": Decimal("100.30"),
            "sell_effective_price_usd": Decimal("101"),
        }

        first_result = {
            "decision": "READY_TO_TRADE",
            "opportunity": first_opportunity,
        }
        second_result = {
            "decision": "READY_TO_TRADE",
            "opportunity": second_opportunity,
        }

        executions = {
            "buy_options": [],
            "sell_options": [],
        }

        calls = {"execute": 0}

        def fake_prepare(*args, **kwargs):
            if not hasattr(fake_prepare, "called"):
                fake_prepare.called = 1
                return (
                    first_result,
                    first_opportunity,
                    executions,
                )

            return (
                second_result,
                second_opportunity,
                executions,
            )

        def fake_execute_arbitrage(*args, **kwargs):
            calls["execute"] += 1
            return object()

        with patch(
            "app.services.bot_engine._prepare_market_evaluation",
            side_effect=fake_prepare,
        ), patch(
            "app.services.bot_engine.execute_arbitrage",
            side_effect=fake_execute_arbitrage,
        ):
            result = execute_market(
                db=None,
                account_id=1,
                symbol="BTCUSDT",
                capital_usd=Decimal("5"),
            )

        self.assertEqual(
            result["decision"],
            "NO_TRADE",
        )
        self.assertTrue(
            result["revalidation_failed"]
        )
        self.assertEqual(
            result["revalidation_failure_type"],
            "slippage_exceeded",
        )
        self.assertEqual(
            calls["execute"],
            0,
        )


if __name__ == "__main__":
    unittest.main()

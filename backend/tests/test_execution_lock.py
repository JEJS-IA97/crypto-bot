import threading
import time
import unittest
from unittest.mock import patch

from app.services.bot_engine import execute_market


class ExecutionLockTest(unittest.TestCase):
    def test_execute_market_is_serialized(self) -> None:
        active_calls = 0
        max_active_calls = 0
        counter_lock = threading.Lock()

        def fake_prepare(
            db,
            account_id,
            symbol,
            capital_usd,
            risk_config,
        ):
            nonlocal active_calls
            nonlocal max_active_calls

            with counter_lock:
                active_calls += 1
                max_active_calls = max(
                    max_active_calls,
                    active_calls,
                )

            time.sleep(0.05)

            with counter_lock:
                active_calls -= 1

            opportunity = {
                "status": "TRADE",
                "symbol": symbol,
            }

            return (
                {
                    "decision": "READY_TO_TRADE",
                    "symbol": symbol,
                },
                opportunity,
                {},
            )

        def fake_execute_arbitrage(
            db,
            account_id,
            opportunity,
            executions,
        ):
            return object()

        errors = []

        def worker() -> None:
            try:
                execute_market(
                    db=None,
                    account_id=1,
                    symbol="BTCUSDT",
                    capital_usd=5,
                )
            except Exception as exc:
                errors.append(exc)

        with patch(
            "app.services.bot_engine._prepare_market_evaluation",
            side_effect=fake_prepare,
        ), patch(
            "app.services.bot_engine.execute_arbitrage",
            side_effect=fake_execute_arbitrage,
        ):
            first = threading.Thread(
                target=worker
            )
            second = threading.Thread(
                target=worker
            )

            first.start()
            second.start()

            first.join()
            second.join()

        self.assertEqual(
            errors,
            [],
        )

        self.assertEqual(
            max_active_calls,
            1,
        )


if __name__ == "__main__":
    unittest.main()

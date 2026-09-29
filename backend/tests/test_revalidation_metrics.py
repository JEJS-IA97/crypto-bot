import unittest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import SimulationBotCycle
from app.services.bot_runner_service import (
    REVALIDATION_FAILURE_REASON,
    get_revalidation_failures_today,
    utc_now_naive,
)


class RevalidationMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite://",
            connect_args={
                "check_same_thread": False,
            },
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def test_counts_only_today_and_matching_account_reason(self) -> None:
        now = utc_now_naive()
        day_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        with Session(self.engine) as db:
            db.add_all(
                [
                    SimulationBotCycle(
                        account_id=1,
                        executed_at=now,
                        decision="NO_TRADE",
                        reason=REVALIDATION_FAILURE_REASON,
                        evaluated_symbols_json="[]",
                    ),
                    SimulationBotCycle(
                        account_id=1,
                        executed_at=now,
                        decision="NO_TRADE",
                        reason="No configured symbol produced an executable opportunity.",
                        evaluated_symbols_json="[]",
                    ),
                    SimulationBotCycle(
                        account_id=2,
                        executed_at=now,
                        decision="NO_TRADE",
                        reason=REVALIDATION_FAILURE_REASON,
                        evaluated_symbols_json="[]",
                    ),
                    SimulationBotCycle(
                        account_id=1,
                        executed_at=day_start - timedelta(seconds=1),
                        decision="NO_TRADE",
                        reason=REVALIDATION_FAILURE_REASON,
                        evaluated_symbols_json="[]",
                    ),
                ]
            )
            db.commit()

            failures = get_revalidation_failures_today(
                db=db,
                account_id=1,
            )

        self.assertEqual(failures, 1)


if __name__ == "__main__":
    unittest.main()

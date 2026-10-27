import asyncio
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.services import bot_loop
from app.services.risk_guard_service import get_runtime


class Feed:
    def __init__(self, ok):
        self.ok = ok

    def get_klines(self, *a, **k):
        if not self.ok:
            raise OSError("451")
        return [1, 2]


class BreakerProbeTests(unittest.TestCase):
    def test_breaker_from_connection_failures_resets_when_feed_returns(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        with factory() as db:
            rt = get_runtime(db)
            rt.breaker_active, rt.breaker_reason, rt.running = True, "5 consecutive cycle failures", True
            db.commit()
        stop = asyncio.Event()
        calls = []

        def runner(db, **kwargs):
            calls.append(1)
            stop.set()

        asyncio.run(asyncio.wait_for(bot_loop.run(stop_event=stop, session_factory=factory, cycle_runner=runner,
                                                  market_data=Feed(True), symbols=["BTCUSDT"], interval_seconds=0.01), 5))
        with factory() as db:
            self.assertFalse(get_runtime(db).breaker_active)
        self.assertEqual(calls, [1])
        self.assertFalse(bot_loop._feed_ok(Feed(False)))


if __name__ == "__main__":
    unittest.main()
